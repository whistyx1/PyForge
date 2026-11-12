"""Migration ordering and failure boundaries for the deployment script."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "infra/ansible/files/pyforge-deploy"
FLOCK = """#!{python}
import fcntl
import sys
import time
if sys.argv[1:] != ['--wait', '120', '9']:
    sys.exit(2)
while True:
    try:
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.exit(0)
    except BlockingIOError:
        time.sleep(0.01)
"""
DOCKER = """#!/bin/bash
printf '%s:%s:%s\\n' "$PYFORGE_TEST_LABEL" "$PYFORGE_IMAGE_TAG" "$*" >> "$PYFORGE_TEST_EVENTS"
if [[ "$1 $2" == 'image inspect' && "$*" == *'--format'* ]]; then
    printf 'present\\n'
elif [[ "$1 $2" == 'compose stop' ]]; then
    printf 'stopped\\n' > "$PYFORGE_TEST_STATE"
elif [[ "$1 $2" == 'compose run' ]]; then
    [[ "$*" == 'compose run --rm --no-deps --pull never -T web python manage.py migrate --noinput' ]] || exit 2
    [[ "$(cat "$PYFORGE_TEST_STATE")" == stopped ]] || exit 3
    [[ "$DJANGO_SECRET_KEY" == 'mock-secret-value' ]] || exit 4
    printf 'migration-start:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
    sleep "$PYFORGE_TEST_HOLD"
    [[ "$PYFORGE_TEST_MIGRATE_FAIL" == 1 ]] && exit 5
    printf 'migration-end:%s\\n' "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"
elif [[ "$1 $2" == 'compose up' ]]; then
    if [[ "$*" != *'--pull never'* && "$PYFORGE_TEST_READY_FAIL" == 1 ]]; then
        exit 6
    fi
    printf 'running:%s\\n' "$PYFORGE_IMAGE_TAG" > "$PYFORGE_TEST_STATE"
fi
exit 0
"""

class DeploymentMigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.events = self.root / "events"
        self.state = self.root / "state"
        self.record = self.root / "last-successful-image-tag"
        self._command("aws", '#!/bin/bash\nprintf "aws:%s\\n" "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"\nprintf "mock-secret-value\\n"\n')
        self._command("docker", DOCKER)
        self._command("mv", '#!/bin/bash\nprintf "record:%s\\n" "$PYFORGE_TEST_LABEL" >> "$PYFORGE_TEST_EVENTS"\n/bin/mv "$@"\n')
        if shutil.which("flock") is None:
            self._command("flock", FLOCK.format(python=sys.executable))

    def _command(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def _start(self, label="first", tag="new", migrate_fail=False, ready_fail=False, hold="0"):
        env = os.environ.copy()
        env.update({
            "PATH": f'{self.bin}{os.pathsep}{env["PATH"]}',
            "PYFORGE_DEPLOY_DIR": str(self.root),
            "PYFORGE_DEPLOY_LOCK_FILE": str(self.root / "deploy.lock"),
            "PYFORGE_TEST_EVENTS": str(self.events),
            "PYFORGE_TEST_STATE": str(self.state),
            "PYFORGE_TEST_LABEL": label,
            "PYFORGE_TEST_MIGRATE_FAIL": "1" if migrate_fail else "0",
            "PYFORGE_TEST_READY_FAIL": "1" if ready_fail else "0",
            "PYFORGE_TEST_HOLD": hold,
        })
        process = subprocess.Popen(["bash", str(SCRIPT), tag], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
        self.assertNotIn("mock-secret-value", stdout + stderr)
        return process.returncode, stderr

    def _events(self):
        return self.events.read_text().splitlines() if self.events.exists() else []

    def _previous(self):
        self.record.write_text("old\n")
        self.state.write_text("running:old\n")

    def test_no_pending_migration_stops_web_runs_one_off_then_records_after_readiness(self):
        code, stderr = self._run()
        self.assertEqual(code, 0, stderr)
        events = self._events()
        self.assertEqual([event for event in events if ":compose " in event], [
            "first:new:compose pull",
            "first:new:compose stop web",
            "first:new:compose run --rm --no-deps --pull never -T web python manage.py migrate --noinput",
            "first:new:compose up -d --remove-orphans --wait --wait-timeout 60",
        ])
        self.assertLess(events.index("migration-end:first"), events.index("record:first"))
        self.assertEqual(self.state.read_text(), "running:new\n")
        self.assertEqual(self.record.read_text(), "new\n")

    def test_failed_migration_leaves_web_stopped_without_app_rollback_or_record_change(self):
        self._previous()
        code, stderr = self._run(migrate_fail=True)
        self.assertNotEqual(code, 0)
        self.assertIn("Database migration failed. Web remains stopped", stderr)
        self.assertEqual(self.state.read_text(), "stopped\n")
        self.assertEqual(self.record.read_text(), "old\n")
        self.assertFalse(any(":compose up" in event for event in self._events()))

    def test_readiness_failure_after_migration_rolls_back_image(self):
        self._previous()
        code, stderr = self._run(ready_fail=True)
        self.assertNotEqual(code, 0)
        self.assertIn("Rollback to the last successful image (old) succeeded", stderr)
        self.assertIn("migrations", stderr.lower())
        events = self._events()
        self.assertLess(events.index("migration-end:first"), events.index("first:new:compose up -d --remove-orphans --wait --wait-timeout 60"))
        self.assertIn("first:old:compose up -d --remove-orphans --pull never --wait --wait-timeout 60", events)
        self.assertEqual(self.state.read_text(), "running:old\n")
        self.assertEqual(self.record.read_text(), "old\n")

    def test_second_deployment_waits_while_first_is_migrating(self):
        first = self._start(hold="0.4")
        deadline = time.monotonic() + 3
        while "migration-start:first" not in self._events() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("migration-start:first", self._events())
        second = self._start("second", "next")
        first.communicate(timeout=5)
        second.communicate(timeout=5)
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        events = self._events()
        self.assertLess(events.index("record:first"), events.index("aws:second"))
