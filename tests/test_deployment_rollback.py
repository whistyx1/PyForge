"""Behavioral tests of the deploy script's local rollback path."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'infra/ansible/files/pyforge-deploy'
IMAGE = 'ghcr.io/whistyx1/pyforge:'

FLOCK_SHIM = '''#!{python}
import fcntl
import time
import sys
if sys.argv[1:] != ['--wait', '120', '9']:
    sys.exit(2)
while True:
    try:
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.exit(0)
    except BlockingIOError:
        time.sleep(0.01)
'''

DOCKER_MOCK = '''#!/bin/bash
printf '%s:%s:%s\\n' "$PYFORGE_TEST_LABEL" "$PYFORGE_IMAGE_TAG" "$*" >> "$PYFORGE_TEST_EVENTS"
if [[ "$1 $2" == 'image tag' ]]; then
    [[ "$PYFORGE_TEST_MISSING_PRIOR" == 1 ]] && exit 1
    source_tag="${3##*:}"
    target_tag="${4##*:}"
    cp "$PYFORGE_TEST_IMAGES/$source_tag" "$PYFORGE_TEST_IMAGES/$target_tag" || exit 1
elif [[ "$1 $2" == 'image rm' ]]; then
    target_tag="${3##*:}"
    rm -f "$PYFORGE_TEST_IMAGES/$target_tag"
elif [[ "$1 $2" == 'compose pull' ]]; then
    if [[ "$PYFORGE_TEST_MUTATE_TAG" == 1 ]]; then
        printf 'replacement-image\\n' > "$PYFORGE_TEST_IMAGES/$PYFORGE_IMAGE_TAG"
    fi
    [[ "$PYFORGE_TEST_PULL_FAIL" == 1 ]] && exit 1
elif [[ "$1 $2" == 'image inspect' ]]; then
    if [[ "$*" != *'--format'* ]]; then
        [[ "$PYFORGE_TEST_MISSING_PRIOR" == 1 ]] && exit 1
        target_tag="${3##*:}"
        [[ -f "$PYFORGE_TEST_IMAGES/$target_tag" ]] || exit 1
        exit 0
    fi
    if [[ "$PYFORGE_TEST_NO_HEALTH" == 1 ]]; then
        printf 'missing\\n'
    else
        printf 'present\\n'
    fi
elif [[ "$1 $2" == 'compose up' ]]; then
    if [[ "$*" == *'--pull never'* ]]; then
        printf 'rollback-start:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
        sleep "$PYFORGE_TEST_ROLLBACK_HOLD"
        [[ "$PYFORGE_TEST_ROLLBACK_FAIL" == 1 ]] && exit 1
        printf '%s\\n' "$PYFORGE_IMAGE_TAG" > "$PYFORGE_TEST_RUNTIME"
        cp "$PYFORGE_TEST_IMAGES/$PYFORGE_IMAGE_TAG" "$PYFORGE_TEST_RUNTIME_IMAGE"
        printf 'rollback-end:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
    else
        [[ "$PYFORGE_TEST_READY_FAIL" == 1 ]] && exit 1
        printf 'replacement-image\\n' > "$PYFORGE_TEST_IMAGES/$PYFORGE_IMAGE_TAG"
        printf '%s\\n' "$PYFORGE_IMAGE_TAG" > "$PYFORGE_TEST_RUNTIME"
        printf 'replacement-image\\n' > "$PYFORGE_TEST_RUNTIME_IMAGE"
    fi
fi
exit 0
'''


class DeploymentRollbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.events = self.root / 'events'
        self.runtime = self.root / 'runtime'
        self.runtime_image = self.root / 'runtime-image'
        self.images = self.root / 'images'
        self.images.mkdir()
        self.record = self.root / 'last-successful-image-tag'
        self._command('aws', '#!/bin/bash\nprintf "mock-secret-value\\n"\n')
        self._command('docker', DOCKER_MOCK)
        self._command('mv', '''#!/bin/bash
printf 'record-start:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
sleep "$PYFORGE_TEST_RECORD_HOLD"
/bin/mv "$@"
result=$?
printf 'record-end:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
exit "$result"
''')
        if shutil.which('flock') is None:
            self._command('flock', FLOCK_SHIM.format(python=sys.executable))

    def _command(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def _start(self, label='release', tag='new', **flags):
        env = os.environ.copy()
        env.update({
            'PATH': f'{self.bin}{os.pathsep}{env["PATH"]}',
            'PYFORGE_DEPLOY_DIR': str(self.root),
            'PYFORGE_DEPLOY_LOCK_FILE': str(self.root / 'deploy.lock'),
            'PYFORGE_TEST_EVENTS': str(self.events),
            'PYFORGE_TEST_RUNTIME': str(self.runtime),
            'PYFORGE_TEST_RUNTIME_IMAGE': str(self.runtime_image),
            'PYFORGE_TEST_IMAGES': str(self.images),
            'PYFORGE_TEST_LABEL': label,
            'PYFORGE_TEST_MISSING_PRIOR': '0',
            'PYFORGE_TEST_PULL_FAIL': '0',
            'PYFORGE_TEST_NO_HEALTH': '0',
            'PYFORGE_TEST_READY_FAIL': '0',
            'PYFORGE_TEST_ROLLBACK_FAIL': '0',
            'PYFORGE_TEST_ROLLBACK_HOLD': '0',
            'PYFORGE_TEST_RECORD_HOLD': '0',
            'PYFORGE_TEST_MUTATE_TAG': '0',
        })
        env.update({f'PYFORGE_TEST_{key.upper()}': str(value) for key, value in flags.items()})
        process = subprocess.Popen(
            ['bash', str(SCRIPT), tag], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self._stop, process)
        return process

    @staticmethod
    def _stop(process):
        if process.poll() is None:
            process.kill()
            process.communicate()

    def _run(self, **kwargs):
        process = self._start(**kwargs)
        stdout, stderr = process.communicate(timeout=5)
        self.assertNotIn('mock-secret-value', stdout + stderr)
        return process.returncode, stderr

    def _events(self):
        return self.events.read_text().splitlines() if self.events.exists() else []

    def _existing(self):
        self.record.write_text('old\n')
        self.runtime.write_text('old\n')
        self.runtime_image.write_text('original-image\n')
        (self.images / 'old').write_text('original-image\n')

    def _assert_no_rollback_alias(self):
        self.assertEqual(list(self.images.glob('rollback-*')), [])

    def test_healthy_deployment_records_new_tag(self):
        code, stderr = self._run()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.record.read_text(), 'new\n')
        self.assertEqual(self.runtime.read_text(), 'new\n')
        self.assertIn('passed readiness checks', stderr)
        self._assert_no_rollback_alias()

    def test_pull_or_health_validation_failure_preserves_record_and_runtime(self):
        for flag in ('pull_fail', 'no_health'):
            with self.subTest(flag=flag):
                self._existing()
                code, _ = self._run(**{flag: 1})
                self.assertNotEqual(code, 0)
                self.assertEqual(self.record.read_text(), 'old\n')
                self.assertEqual(self.runtime.read_text(), 'old\n')
                self.assertEqual((self.images / 'old').read_text(), 'original-image\n')
                self._assert_no_rollback_alias()
                self.assertFalse(any('rollback-start:' in event for event in self._events()))

    def test_failed_readiness_rolls_back_without_pull_and_returns_failure(self):
        self._existing()
        code, stderr = self._run(ready_fail=1)
        self.assertNotEqual(code, 0)
        self.assertIn('Rollback to the last successful image (old) succeeded', stderr)
        self.assertEqual(self.runtime.read_text(), 'old\n')
        self.assertEqual(self.record.read_text(), 'old\n')
        self.assertEqual((self.images / 'old').read_text(), 'original-image\n')
        self._assert_no_rollback_alias()
        rollback = [event for event in self._events() if 'compose up' in event and '--pull never' in event]
        self.assertEqual(len(rollback), 1)
        self.assertTrue(rollback[0].startswith('release:old:'))
        self.assertEqual(sum('compose pull' in event for event in self._events()), 1)

    def test_missing_rollback_target_is_reported_separately(self):
        code, stderr = self._run(ready_fail=1)
        self.assertNotEqual(code, 0)
        self.assertIn('Rollback unavailable: no last successful image recorded', stderr)
        self.assertFalse(self.record.exists())
        self._assert_no_rollback_alias()

    def test_missing_recorded_image_is_reported_before_replacement(self):
        self._existing()
        code, stderr = self._run(missing_prior=1)
        self.assertNotEqual(code, 0)
        self.assertIn('last successful image', stderr.lower())
        self.assertEqual(self.record.read_text(), 'old\n')
        self.assertEqual(self.runtime.read_text(), 'old\n')
        self.assertFalse(any('compose pull' in event for event in self._events()))
        self._assert_no_rollback_alias()

    def test_rollback_failure_is_reported_separately_and_record_is_unchanged(self):
        self._existing()
        code, stderr = self._run(ready_fail=1, rollback_fail=1)
        self.assertNotEqual(code, 0)
        self.assertIn('Rollback to the last successful image (old) failed', stderr)
        self.assertEqual(self.record.read_text(), 'old\n')
        self._assert_no_rollback_alias()

    def test_same_tag_retry_restores_original_image_after_failed_readiness(self):
        self._existing()
        code, stderr = self._run(tag='old', ready_fail=1, mutate_tag=1)
        self.assertNotEqual(code, 0)
        self.assertIn('Rollback to the last successful image (old) succeeded', stderr)
        self.assertEqual(self.record.read_text(), 'old\n')
        self.assertEqual(self.runtime.read_text(), 'old\n')
        self.assertEqual(self.runtime_image.read_text(), 'original-image\n')
        self.assertEqual((self.images / 'old').read_text(), 'original-image\n')
        self._assert_no_rollback_alias()

    def test_same_tag_pull_failure_restores_original_image_before_replacement(self):
        self._existing()
        code, _ = self._run(tag='old', pull_fail=1, mutate_tag=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.record.read_text(), 'old\n')
        self.assertEqual(self.runtime.read_text(), 'old\n')
        self.assertEqual(self.runtime_image.read_text(), 'original-image\n')
        self.assertEqual((self.images / 'old').read_text(), 'original-image\n')
        self.assertFalse(any('compose up' in event for event in self._events()))
        self._assert_no_rollback_alias()

    def test_lock_stays_held_through_rollback_and_record_update(self):
        self._existing()
        first = self._start('first', ready_fail=1, rollback_hold=0.4)
        deadline = time.monotonic() + 3
        while 'rollback-start:first' not in self._events() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn('rollback-start:first', self._events())
        second = self._start('second', tag='next')
        first.communicate(timeout=5)
        second.communicate(timeout=5)
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        events = self._events()
        self.assertLess(events.index('rollback-end:first'), next(i for i, event in enumerate(events) if event.startswith('second:')))
        self.assertEqual(self.record.read_text(), 'next\n')
        self._assert_no_rollback_alias()

    def test_lock_stays_held_through_successful_record_update(self):
        self._existing()
        first = self._start('first', tag='new', record_hold=0.4)
        deadline = time.monotonic() + 3
        while 'record-start:first' not in self._events() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn('record-start:first', self._events())
        second = self._start('second', tag='next')
        first.communicate(timeout=5)
        second.communicate(timeout=5)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        events = self._events()
        self.assertLess(events.index('record-end:first'), next(i for i, event in enumerate(events) if event.startswith('second:')))
        self.assertEqual(self.record.read_text(), 'next\n')
        self._assert_no_rollback_alias()
