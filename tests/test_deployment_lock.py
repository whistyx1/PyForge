"""Exercise the deployment script's file lock without AWS or Docker services."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


DEPLOY_SCRIPT = Path(__file__).resolve().parents[1] / 'infra/ansible/files/pyforge-deploy'

FLOCK_SHIM = '''#!{python}
import fcntl
import os
import sys
import time

if sys.argv[1:] != ['--wait', '120', '9']:
    sys.exit(2)
deadline = time.monotonic() + float(os.environ.get('PYFORGE_TEST_MAX_WAIT', '120'))
while True:
    try:
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.exit(0)
    except BlockingIOError:
        if time.monotonic() >= deadline:
            sys.exit(1)
        time.sleep(0.01)
'''


class DeploymentLockTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.bin_dir = self.root / 'bin'
        self.bin_dir.mkdir()
        self.events = self.root / 'events'
        self.lock_file = self.root / 'deploy.lock'

        self._write_command('aws', '#!/bin/bash\nprintf "aws:%s\\n" "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"\nprintf "test-secret\\n"\n')
        self._write_command('docker', '''#!/bin/bash
if [[ "$1 $2" == 'compose pull' ]]; then
    printf 'pull-start:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
    printf 'pull-end:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
    [[ "$PYFORGE_TEST_FAIL" == '1' ]] && exit 7
elif [[ "$1 $2" == 'compose up' ]]; then
    printf 'ready-start:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
    sleep "$PYFORGE_TEST_HOLD"
    printf 'ready-end:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
elif [[ "$1 $2" == 'image inspect' ]]; then
    printf 'present\\n'
fi
exit 0
''')
        if shutil.which('flock') is None:
            self._write_command('flock', FLOCK_SHIM.format(python=sys.executable))

    def _write_command(self, name, content, directory=None):
        path = (directory or self.bin_dir) / name
        path.write_text(content)
        path.chmod(0o755)

    def _start(self, label, *, hold='0', fail=False, short_wait=False):
        env = os.environ.copy()
        env.update({
            'PATH': f'{self.bin_dir}{os.pathsep}{env["PATH"]}',
            'PYFORGE_DEPLOY_LOCK_FILE': str(self.lock_file),
            'PYFORGE_DEPLOY_DIR': str(self.root),
            'PYFORGE_TEST_EVENTS': str(self.events),
            'PYFORGE_TEST_LABEL': label,
            'PYFORGE_TEST_HOLD': hold,
            'PYFORGE_TEST_FAIL': '1' if fail else '0',
        })
        if short_wait:
            shim_bin = self.root / 'timeout-bin'
            shim_bin.mkdir(exist_ok=True)
            self._write_command('flock', FLOCK_SHIM.format(python=sys.executable), shim_bin)
            env['PATH'] = f'{shim_bin}{os.pathsep}{env["PATH"]}'
            env['PYFORGE_TEST_MAX_WAIT'] = '0.15'
        process = subprocess.Popen(
            ['bash', str(DEPLOY_SCRIPT), label], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self._stop_if_running, process)
        return process

    @staticmethod
    def _stop_if_running(process):
        if process.poll() is None:
            process.kill()
            process.communicate()

    def _wait_for_event(self, expected):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if self.events.exists() and expected in self.events.read_text().splitlines():
                return
            time.sleep(0.01)
        self.fail(f'No event {expected!r}; observed {self._events()!r}')

    def _events(self):
        return self.events.read_text().splitlines() if self.events.exists() else []

    def test_concurrent_deployments_do_not_overlap_protected_operations(self):
        first = self._start('first', hold='0.4')
        self._wait_for_event('ready-start:first')
        second = self._start('second')

        self.assertEqual(first.communicate(timeout=5)[0], '')
        self.assertEqual(second.communicate(timeout=5)[0], '')
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        self.assertEqual(self._events(), [
            'aws:first', 'pull-start:first', 'pull-end:first',
            'ready-start:first', 'ready-end:first',
            'aws:second', 'pull-start:second', 'pull-end:second',
            'ready-start:second', 'ready-end:second',
        ])

    def test_lock_is_released_after_failed_deployment(self):
        failed = self._start('failed', fail=True)
        failed.communicate(timeout=5)
        self.assertEqual(failed.returncode, 7)

        following = self._start('following')
        following.communicate(timeout=5)
        self.assertEqual(following.returncode, 0)
        self.assertEqual(self._events(), [
            'aws:failed', 'pull-start:failed', 'pull-end:failed',
            'aws:following', 'pull-start:following', 'pull-end:following',
            'ready-start:following', 'ready-end:following',
        ])

    def test_wait_timeout_exits_without_starting_second_deployment(self):
        first = self._start('first', hold='0.6')
        self._wait_for_event('ready-start:first')
        timed_out = self._start('timed-out', short_wait=True)

        _, stderr = timed_out.communicate(timeout=5)
        first.communicate(timeout=5)
        self.assertEqual(timed_out.returncode, 1)
        self.assertIn('held the lock for more than 120 seconds', stderr)
        self.assertEqual(first.returncode, 0)
        self.assertNotIn('aws:timed-out', self._events())
