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

## Next step

- Write an Ansible playbook for server configuration, recreate the EC2 stack with Terraform, then test provisioning on the fresh instance. Add a public web entry point and HTTPS before exposing the site.
- Connect project intake to backend validation and analysis, then build the review flow described in the product plan.
