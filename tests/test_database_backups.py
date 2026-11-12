"""Local backup/verification behavior and infrastructure contract tests."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "infra/ansible/files/pyforge-backup"
KEY = "backups/2026/11/12/20261112T010000Z-test-1.sqlite3"
FLOCK = """#!{python}
import fcntl
import sys
import time
if sys.argv[1:] == ['-u', '9']:
    fcntl.flock(9, fcntl.LOCK_UN)
    sys.exit(0)
if sys.argv[1:] != ['--wait', '7200', '9']:
    sys.exit(2)
while True:
    try:
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.exit(0)
    except BlockingIOError:
        time.sleep(0.01)
"""
AWS = """#!{python}
import json
import os
import shutil
import sys
import time
from pathlib import Path
args = sys.argv[1:]
events = Path(os.environ['TEST_EVENTS'])
if args[:2] == ['s3api', 'head-object']:
    bucket = args[args.index('--bucket') + 1]
    key = args[args.index('--key') + 1]
    with events.open('a') as log:
        log.write('head:' + bucket + ':' + key + '\\n')
    metadata = Path(os.environ['TEST_METADATA']) / bucket / key
    if not metadata.exists():
        sys.exit(8)
    print(metadata.read_text())
    sys.exit(0)
if args[:2] != ['s3', 'cp']:
    sys.exit(2)
src, dst = args[2:4]
with events.open('a') as log:
    log.write('aws-start:' + src + ':' + dst + '\\n')
if os.environ.get('TEST_AWS_HOLD') == '1':
    time.sleep(0.4)
if os.environ.get('TEST_AWS_FAIL') == '1':
    sys.exit(7)
def path(value):
    if value.startswith('s3://'):
        return Path(os.environ['TEST_S3']) / value[5:]
    return Path(value)
source, target = path(src), path(dst)
if not source.exists():
    sys.exit(8)
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)
if '--metadata' in args:
    values = dict(part.split('=', 1) for part in args[args.index('--metadata') + 1].split(','))
    metadata = Path(os.environ['TEST_METADATA']) / dst[5:]
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(values))
with events.open('a') as log:
    log.write('aws-end:' + src + ':' + dst + '\\n')
""".format(python=sys.executable)
DOCKER = """#!/bin/bash
printf 'docker:%s\\n' "$*" >> "$TEST_EVENTS"
if [[ "$1" == run ]]; then
    [[ "$*" == *'--pull=never --network none --user 0:0'* ]] || exit 2
    [[ "$*" == *'readonly'* ]] || exit 3
    [[ "$*" == *'ghcr.io/whistyx1/pyforge:ready-tag'* ]] || exit 4
    [[ "$*" == *'python manage.py migrate --check'* ]] || exit 5
    [[ "$TEST_DOCKER_FAIL" == 1 ]] && exit 6
fi
exit 0
"""

class DatabaseBackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.s3 = self.root / "s3"
        self.s3.mkdir()
        self.metadata = self.root / "metadata"
        self.metadata.mkdir()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.events = self.root / "events"
        self.db = self.root / "production.sqlite3"
        self.tag = self.root / "last-successful-image-tag"
        self.tag.write_text("ready-tag\n")
        self._command("aws", AWS)
        self._command("docker", DOCKER)
        if shutil.which("flock") is None:
            self._command("flock", FLOCK.format(python=sys.executable))
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE sample (value TEXT)")
            con.execute("INSERT INTO sample VALUES ('committed')")
        con.close()

    def _command(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def _start(self, *args, **flags):
        env = os.environ.copy()
        env.update({
            "PATH": f'{self.bin}{os.pathsep}{env["PATH"]}',
            "PYFORGE_DB_PATH": str(self.db),
            "PYFORGE_SUCCESSFUL_TAG_FILE": str(self.tag),
            "PYFORGE_BACKUP_BUCKET": "test-bucket",
            "PYFORGE_BACKUP_REGION": "us-east-1",
            "PYFORGE_BACKUP_KEY": KEY,
            "PYFORGE_BACKUP_TMPDIR": str(self.tmp),
            "PYFORGE_DEPLOY_LOCK_FILE": str(self.root / "deploy.lock"),
            "TEST_S3": str(self.s3),
            "TEST_METADATA": str(self.metadata),
            "TEST_EVENTS": str(self.events),
            "TEST_AWS_FAIL": "1" if flags.get("aws_fail") else "0",
            "TEST_AWS_HOLD": "1" if flags.get("aws_hold") else "0",
            "TEST_DOCKER_FAIL": "1" if flags.get("docker_fail") else "0",
        })
        process = subprocess.Popen(["bash", str(SCRIPT), *args], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self._stop, process)
        return process

    @staticmethod
    def _stop(process):
        if process.poll() is None:
            process.kill()
            process.communicate()

    def _run(self, *args, **flags):
        process = self._start(*args, **flags)
        out, err = process.communicate(timeout=5)
        return process.returncode, out + err

    def _object(self):
        return self.s3 / "test-bucket" / KEY

    def _assert_clean(self):
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_backup_uploads_consistent_snapshot_and_metadata_then_cleans_temp(self):
        code, output = self._run("backup")
        self.assertEqual(code, 0, output)
        obj = self._object()
        with sqlite3.connect(obj) as con:
            self.assertEqual(con.execute("SELECT value FROM sample").fetchall(), [("committed",)])
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        con.close()
        metadata = json.loads((self.metadata / "test-bucket" / KEY).read_text())
        self.assertEqual(metadata, {
            "sha256": hashlib.sha256(obj.read_bytes()).hexdigest(),
            "image-tag": "ready-tag",
        })
        self.assertFalse(Path(str(obj) + ".meta").exists())
        self.assertIn("Uploaded PyForge database snapshot", output)
        self.assertEqual(sum(line.startswith("aws-end:") for line in self.events.read_text().splitlines()), 1)
        self._assert_clean()

    def test_invalid_database_and_failed_upload_never_report_success(self):
        self.db.write_bytes(b"invalid sqlite")
        code, output = self._run("backup")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Uploaded PyForge", output)
        self.assertFalse(self._object().exists())
        self._assert_clean()
        self.db.unlink()
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE sample (value TEXT)")
        con.close()
        code, output = self._run("backup", aws_fail=True)
        self.assertNotEqual(code, 0)
        self.assertNotIn("Uploaded PyForge", output)
        self._assert_clean()

    def test_backup_waits_for_shared_deployment_lock(self):
        lock = self.root / "deploy.lock"
        lock.touch()
        import fcntl
        with lock.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            process = self._start("backup")
            time.sleep(0.15)
            self.assertFalse(self.events.exists())
            fcntl.flock(handle, fcntl.LOCK_UN)
        out, err = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, out + err)
        self._assert_clean()

    def test_backup_releases_lock_before_network_upload(self):
        import fcntl

        process = self._start("backup", aws_hold=True)
        deadline = time.monotonic() + 3
        while (not self.events.exists() or "aws-start:" not in self.events.read_text()) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("aws-start:", self.events.read_text())
        with (self.root / "deploy.lock").open("r") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
        out, err = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, out + err)
        self._assert_clean()

    def test_verify_does_not_wait_for_deployment_lock(self):
        import fcntl

        self.assertEqual(self._run("backup")[0], 0)
        with (self.root / "deploy.lock").open("r") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            process = self._start("verify", KEY)
            out, err = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, out + err)
            fcntl.flock(handle, fcntl.LOCK_UN)
        self._assert_clean()

    def test_verify_isolated_matching_image_and_does_not_change_production(self):
        self.assertEqual(self._run("backup")[0], 0)
        before = self.db.read_bytes()
        code, output = self._run("verify", KEY)
        self.assertEqual(code, 0, output)
        self.assertIn("Verified isolated backup restore", output)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertIn("docker:run --rm --pull=never --network none --user 0:0", self.events.read_text())
        self.assertIn("head:test-bucket:" + KEY, self.events.read_text())
        self._assert_clean()

    def test_verify_rejects_bad_key_checksum_corrupt_database_and_image_failure(self):
        code, output = self._run("verify", "../outside.sqlite3")
        self.assertNotEqual(code, 0)
        self.assertIn("Backup key must", output)
        self.assertFalse(self.events.exists())
        self.assertEqual(self._run("backup")[0], 0)
        obj = self._object()
        obj.write_bytes(obj.read_bytes() + b"tamper")
        code, output = self._run("verify", KEY)
        self.assertNotEqual(code, 0)
        self.assertIn("checksum mismatch", output)
        obj.write_bytes(b"not sqlite")
        (self.metadata / "test-bucket" / KEY).write_text(json.dumps({
            "sha256": hashlib.sha256(obj.read_bytes()).hexdigest(),
            "image-tag": "ready-tag",
        }))
        code, output = self._run("verify", KEY)
        self.assertNotEqual(code, 0)
        self.assertNotIn("Verified isolated", output)
        self._assert_clean()
        self.assertEqual(self._run("backup")[0], 0)
        code, output = self._run("verify", KEY, docker_fail=True)
        self.assertNotEqual(code, 0)
        self.assertNotIn("Verified isolated", output)
        self._assert_clean()

    def test_static_s3_iam_and_timer_contract(self):
        terraform = (ROOT / "infra/terraform/backups.tf").read_text()
        for token in ("prevent_destroy = true", "block_public_acls       = true",
                      "block_public_policy     = true", "ignore_public_acls      = true",
                      "restrict_public_buckets = true", 'sse_algorithm = "AES256"',
                      "days = 14", '"s3:PutObject"', '"s3:GetObject"', '"s3:ListBucket"'):
            self.assertIn(token, terraform)
        self.assertNotIn('"s3:DeleteObject"', terraform)
        timer = (ROOT / "infra/ansible/templates/pyforge-backup.timer.j2").read_text()
        service = (ROOT / "infra/ansible/templates/pyforge-backup.service.j2").read_text()
        site = (ROOT / "infra/ansible/site.yml").read_text()
        runbook = (ROOT / "docs/runbooks/database-backups.md").read_text()
        self.assertIn("Persistent=true", timer)
        self.assertIn("OnCalendar=*-*-* 02:00:00 UTC", timer)
        self.assertIn("ExecStart=/usr/local/bin/pyforge-backup backup", service)
        backup_install = site.split("dest: /usr/local/bin/pyforge-backup", 1)[1].split("- name:", 1)[0]
        self.assertIn("mode: '0750'", backup_install)
        self.assertIn("name: pyforge-backup.timer", site)
        self.assertIn("db.sqlite3-wal", runbook)
        self.assertIn("db.sqlite3-shm", runbook)
