"""Readiness behavior without a database or a real network connection."""

import runpy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from healthcheck import HEALTH_URL, is_ready


PROBE_SCRIPT = Path(__file__).resolve().parents[1] / 'app' / 'healthcheck.py'


def response_with(status, body):
    response = BytesIO(body)
    response.status = status
    return response


class HealthEndpointTests(SimpleTestCase):
    def test_health_returns_expected_json_without_database_access(self):
        response = self.client.get('/health/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.json(), {'status': 'ok'})


class ContainerProbeTests(SimpleTestCase):
    @patch('healthcheck.urlopen')
    def test_probe_accepts_exact_success_response(self, urlopen):
        urlopen.return_value = response_with(200, b'{"status":"ok"}')

        self.assertTrue(is_ready())
        urlopen.assert_called_once_with(HEALTH_URL, timeout=2)

    @patch('healthcheck.urlopen')
    def test_probe_rejects_non_200_responses(self, urlopen):
        for status in (204, 500):
            with self.subTest(status=status):
                urlopen.return_value = response_with(status, b'{"status":"ok"}')
                self.assertFalse(is_ready())

    @patch('healthcheck.urlopen')
    def test_probe_rejects_unexpected_or_invalid_json(self, urlopen):
        for body in (b'{"status":"down"}', b'{"status":"ok","extra":1}', b'not json'):
            with self.subTest(body=body):
                urlopen.return_value = response_with(200, body)
                self.assertFalse(is_ready())

    @patch('healthcheck.urlopen')
    def test_probe_rejects_connection_error_and_timeout(self, urlopen):
        for error in (ConnectionRefusedError(), TimeoutError()):
            with self.subTest(error=type(error).__name__):
                urlopen.side_effect = error
                self.assertFalse(is_ready())

    @patch('urllib.request.urlopen')
    def test_probe_command_exits_zero_only_for_ready_response(self, urlopen):
        for status, expected_exit in ((200, 0), (500, 1)):
            with self.subTest(status=status):
                urlopen.return_value = response_with(status, b'{"status":"ok"}')
                with self.assertRaises(SystemExit) as stopped:
                    runpy.run_path(str(PROBE_SCRIPT), run_name='__main__')
                self.assertEqual(stopped.exception.code, expected_exit)
