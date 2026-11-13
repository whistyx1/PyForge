# PyForge database backups

The production database is SQLite at `/data/db.sqlite3` inside the web container's persistent Docker volume. The host runs the backup command with the EC2 instance role; no AWS access keys are stored on the server or in this repository. Follow the [migration and image rollback policy](#migration-and-image-rollback-policy) when changing the schema.

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

Verification downloads the database to a private temporary directory, reads its S3 object metadata, checks the SHA-256 value and SQLite integrity, then opens the database with the exact GHCR image digest recorded with new backups. If that image is not cached, the command pulls it by digest before starting the verification container. The container itself has no network access, uses a read-only mount, and never accesses the production database volume. Verification does not take the deployment lock. The temporary download is removed when verification finishes.

Older backups have only an image tag. They remain verifiable with that tag when the image is cached, but the command warns that a mutable tag cannot prove the exact image contents. It does not automatically pull a tag-only image. If the image is unavailable, verification fails; retain the corresponding image in GHCR for future recovery checks.

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

For a newly created, empty EC2 instance, Ansible installs `pyforge-restore`; the command creates the Docker volume if needed. Choose a verified S3 key and run the command before starting the web container:

```sh
sudo pyforge-restore 'backups/YYYY/MM/DD/object.sqlite3'
```

The command takes the deployment lock and refuses a running web container, invalid keys, and any existing database or SQLite sidecars. It downloads the object once to a private temporary directory, checks its checksum and SQLite integrity, and verifies that same snapshot with the matching image before installing it in the empty Docker volume with UID 1000 ownership. The final file creation refuses to replace an existing database. After success, run the normal deployment command for the image tag recorded with the backup, then check `/health/` and the site. If startup fails, stop and investigate; keep the restored file and original S3 backup intact. For a live database restore, follow the reviewed manual procedure above instead.

## Migration and image rollback policy

An image rollback does not undo a database migration. If a migration succeeds and the new image later fails readiness, the deployment script can start the previous image against the already migrated database. The previous image must remain compatible with that schema for automatic image rollback to work. The script reports that migrations were not reversed; it does not automatically restore a database backup.

Use an expand-and-contract rollout for schema changes that could break the previous image:

1. **Expand:** add new tables or nullable/defaulted columns while preserving the old schema. Deploy code that can work with both forms. Keep the old image able to use the expanded schema.
2. **Switch:** deploy code that reads and writes the new schema. Backfill data in a separately reviewed operation when needed. Keep the old schema available for the rollback window.
3. **Contract:** only in a later release, after rollback to code using the old schema is no longer required, remove old columns or tables.

Before deployment, review each migration for compatibility with both the current and previous image. For a risky schema change, test the previous image against a copy of the post-migration database before release where practical. A readiness response alone does not prove every application path is compatible.

If migration succeeds but the new image fails readiness, the deploy script tries the last successful image and returns a failed deployment result. Check whether the previous image becomes healthy. If it does not, keep deployment traffic stopped, preserve the database, and follow the reviewed production restore procedure below only when restoring the backup is appropriate. A restore can discard writes made after that backup, so confirm the chosen recovery point and preserve a fresh backup first. Never treat restarting the old image as a database rollback.

PyForge currently has no application-owned Django migrations; Django's installed apps still have their own migrations. Apply this policy when adding or changing PyForge application models and migrations.
