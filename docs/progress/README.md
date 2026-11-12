# PyForge progress

This log records work completed in the repository. The product roadmap remains in `docs/pyforge-product-plan.md`.

## 2026-11-07

- Inspected the Django site and product plan. The current application serves landing, documentation, future plans, and a deployment setup prototype. Project analysis and deployment are still planned.
- Added repository guidance in `AGENTS.md` and established this progress log.
- Added four project-scoped Codex agent roles for frontend, backend, tests, and review.
- Consolidated repeated landing-page CTA markup into a Django partial and grouped identical page and heading styles in the stylesheet. Visible behavior is unchanged.
- Verification: Django system check, JavaScript syntax check, home-page render/link checks, and `git diff --check` passed.
- Verification: `python app/manage.py check` passed during the inspection.
- Added Django page and setup-screen JavaScript validation tests. The Django suite and Node test suite pass. Browser interaction tests remain for a later stage.
- Moved both suites into the top-level `tests/` directory and updated the test commands.
- Configured WhiteNoise to serve collected Django static files from the container. The Docker build now runs `collectstatic`; local generated static files are excluded from Git and the build context.
- Verification: rebuilt `pyforge:0.1.0`, confirmed the homepage and stylesheet both return HTTP 200, ran Django's system check in the container, and verified Gunicorn runs as non-root UID 1000.
- Made Django's debug mode, secret key, allowed hosts, and SQLite path configurable through environment variables. The container defaults to debug off, requires the secret key and hosts, and provides a writable `/data` directory for a future persistent volume.
- Verification: rebuilt `pyforge:0.1.0`; missing production settings fail at startup, configured production and local development checks pass, SQLite migrations run as the container user, and the homepage and stylesheet return HTTP 200 in production mode.
- Added a Compose service with a persistent SQLite volume and a private environment file. The local Compose configuration validated, migrations completed, and the website loaded on localhost.
- Added Terraform for the VPC, public subnet, SSH access, and Ubuntu EC2 instance. Terraform applied 10 resources; the instance was later replaced to use a new project SSH key. Docker Engine and Compose were installed and verified on the instance.
- Stopped and then destroyed the 10 Terraform-managed lab resources to prepare for a fresh Ansible provisioning test. Terraform state is empty.

## 2026-11-10

- Reorganized Terraform configuration under `infra/terraform/` and added the EC2 instance role permissions for SSM, GitHub Actions OIDC, and the Django secret in Parameter Store.
- Added Ansible dynamic inventory and server configuration for Docker, Docker Compose, AWS CLI, the server Compose file, and the deployment script. Ansible completed successfully against the running EC2 instance.
- Added a GitHub Actions workflow that runs checks, publishes an image tagged by commit SHA, stores the Django secret as a SecureString parameter, and invokes the deploy script through SSM.
- Merged the deployment branch into `main`. The first main-branch workflow run passed its test, publish, and deploy jobs; the EC2 deploy script pulled the image and started the Compose service successfully.
- The container still binds to localhost on the server. Public access and HTTPS remain to be configured; the live site has not yet been checked through a browser or SSH tunnel.

## 2026-11-11

- Added Terraform security-group rules for public HTTP and HTTPS, and pinned the existing Ubuntu AMI so a future AMI update does not replace the server unexpectedly.
- Extended Ansible to install Caddy and Certbot, serve the ACME HTTP challenge, request a short-lived Let's Encrypt certificate for the EC2 public IP, and configure Caddy to proxy HTTPS traffic to the loopback-only Django container.
- Added a Certbot systemd timer and deploy hook. The hook copies the renewed certificate and private key into a Caddy-readable directory with restricted permissions, then reloads Caddy.
- Configured Caddy's default SNI for direct IP access and Django's trusted proxy header. Updated the server Compose template with the public IP in `DJANGO_ALLOWED_HOSTS`.
- GitHub Actions passed its checks, published the commit-tagged image, and deployed it through AWS Systems Manager. The public HTTPS homepage returned HTTP 200; the container remains bound to `127.0.0.1:8000`, behind Caddy.
- Verification: Ansible syntax check and playbook succeeded; Caddy and the Certbot renewal timer are active; the installed certificate contains the EC2 IP and has a one-week validity period; `curl -I https://18.207.181.130` returned HTTP 200.

## 2026-11-12

- Migrated the public site to `https://pyforge.duckdns.org`. Ansible updates DuckDNS from EC2 metadata, Caddy manages the hostname's HTTPS certificate, and Django allows the hostname.
- Added narrowly scoped Parameter Store access for the DuckDNS token. GitHub Actions stores the repository secret as a SecureString; the EC2 updater reads it from Parameter Store and the token is not kept in the repository.
- Replaced Certbot's IP-certificate timer with a systemd DuckDNS updater timer that runs on boot and every five minutes. The previous Certbot renewal timer is disabled.
- Verification: GitHub Actions test, publish, and deploy jobs passed; Ansible completed with no failures; `https://pyforge.duckdns.org` returned HTTP 200 and HTTP redirected to HTTPS; the DuckDNS timer is active. Terraform formatting and validation, Ansible syntax, shell syntax, and `git diff --check` passed.
- Added a Django readiness endpoint, a container health probe, and a bounded deployment wait. Verification: 9 Django tests, 5 Node tests, shell/Python syntax, and whitespace checks passed. The local image built successfully; Docker reported healthy with production-style allowed hosts and unhealthy when the probe host was excluded. Live rollout remains pending.

## Next step

- Verify the new container readiness check locally and review its behavior before a live rollout.
- Walk through the Terraform, Ansible, Docker, Caddy, DuckDNS, and GitHub Actions configuration line by line, as requested.
- Connect project intake to backend validation and analysis, then build the review flow described in the product plan.
