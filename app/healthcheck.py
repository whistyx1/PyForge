"""Probe Django through the container's loopback interface."""

import json
from urllib.request import urlopen


HEALTH_URL = 'http://127.0.0.1:8000/health/'


def is_ready():
    try:
        with urlopen(HEALTH_URL, timeout=2) as response:
            return response.status == 200 and json.load(response) == {'status': 'ok'}
    except (OSError, ValueError):
        return False


if __name__ == '__main__':
    raise SystemExit(0 if is_ready() else 1)
