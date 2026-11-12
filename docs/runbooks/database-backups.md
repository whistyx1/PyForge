# PyForge database backups

The production database is SQLite at `/data/db.sqlite3` inside the web container's persistent Docker volume. The host runs the backup command with the EC2 instance role; no AWS access keys are stored on the server or in this repository.

## Automatic backup

Ansible installs and enables `pyforge-backup.timer`. It schedules a backup daily at 02:00 UTC, with up to a 15-minute randomized delay. `Persistent=true` makes systemd run a missed scheduled backup after the server starts again. A backup can also be requested on the server at any time:

```sh
sudo pyforge-backup backup
```

The command waits for the same lock used by deployments and migrations while it creates a consistent SQLite snapshot and reads the successful image tag. It releases that lock before the S3 upload, so a slow upload does not hold up deployment. The snapshot is integrity-checked; its SHA-256 and image tag are stored as metadata on the same S3 object. The command prints the object key only after the upload succeeds. Temporary local files are removed when the command exits.

The bucket blocks public access, requires TLS, uses S3-managed encryption, and expires backup objects after 14 days. Expiration is performed asynchronously by S3. Terraform protects the bucket with `prevent_destroy`; a full `terraform destroy` will stop until that protection is deliberately reviewed and removed. The bucket and stored objects continue to incur S3 storage charges while they exist.

## Check a backup without restoring production

Use the exact key printed by `pyforge-backup backup` or supplied by the operator:

```sh
sudo pyforge-backup verify 'backups/YYYY/MM/DD/object.sqlite3'
```

Verification downloads the database to a private temporary directory, reads its S3 object metadata, checks the SHA-256 value and SQLite integrity, then opens the database with the application image tag recorded with the backup. The container has no network access, uses a read-only mount, and never accesses the production database volume. Verification does not take the deployment lock. The temporary download is removed when verification finishes.

To inspect recent keys, use the server's instance role:

```sh
aws s3 ls 's3://<bucket-name>/backups/' --recursive
```

Replace `<bucket-name>` with the value from `terraform output -raw backup_bucket_name` in the current Terraform state.

## Production restore procedure

Production restore is deliberately a manual, reviewed operation. Do not copy a backup over the live database while Django is running.

1. Choose the desired backup key and run `sudo pyforge-backup verify '<key>'`. Stop if checksum, SQLite integrity, or application migration checks fail.
2. Create a fresh pre-restore backup with `sudo pyforge-backup backup` and record its key. This is the recovery point for returning to the current database.
3. Confirm the exact production restore target and schedule downtime. Stop the web container and confirm it is stopped. Keep all other processes that could write the database stopped for the entire restore.
4. Download the chosen backup to a staging file on the same persistent volume and validate its checksum and SQLite integrity again. Preserve the current `db.sqlite3` **and any `db.sqlite3-wal` and `db.sqlite3-shm` sidecars together** in a separate recovery directory on the volume. These files form one SQLite state; copying only the main database can lose committed data or apply a stale write-ahead log to the restored file.
5. With all writers still stopped, remove the old main database and its `-wal`/`-shm` sidecars from the production path, then atomically move the validated standalone snapshot into place as `db.sqlite3`. Set ownership and permissions compatible with the container's UID 1000. Do not put the old sidecars beside the new snapshot.
6. Start the web service and check `/health/` and the site. If it does not become healthy, stop it again; remove the restored database and any new sidecars, then move the preserved original database **and its matching sidecars** back before restarting. Do not mix sidecars from different database versions.

The steps above describe the safety sequence; this project does not yet provide an automated production-restore command. Never run a restore against `/data/db.sqlite3` until the selected key, pre-restore backup, stopped service, and rollback copy have been checked by a human.
