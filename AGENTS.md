# Working on PyForge

## Project overview

PyForge is intended to be a local web tool for deploying Django, FastAPI, and Flask applications to a user-controlled Linux server. The product scope and development stages are in `docs/pyforge-product-plan.md`. Treat that document as a plan, not as evidence that a feature already works.

The current application is a Django site in `app/`. It serves a landing page, documentation, future plans, and a deployment setup prototype. The setup page currently handles inputs in browser JavaScript; it does not upload projects, analyze them, or deploy anything. The three projects in `examples/` are reference applications.

## Repository map

- `app/config/`: Django settings and root URL configuration.
- `app/landing/`: page views, templates, and static assets.
- `tests/`: Django page tests and Node-based setup-screen validation tests.
- `app/landing/static/landing/deployment_setup.js`: client-side setup interactions.
- `examples/`: small Django, FastAPI, and Flask applications for future analyzer and deployment work.
- `docs/pyforge-product-plan.md`: intended workflows, architecture, and milestones.
- `docs/progress/`: concise records of completed work and the next step.
- `.codex/agents/`: project-scoped frontend, backend, test, and reviewer agent roles.

## Local development

From the repository root, use the existing `.venv` if available. Otherwise create a virtual environment and install `requirements.txt`.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/manage.py migrate
python app/manage.py runserver
```

Run Django checks with `python app/manage.py check` and application tests with `python app/manage.py test tests`. Use the matching example application's own requirements when working inside `examples/`.

Run setup-screen JavaScript validation tests with `node --test tests/*.test.cjs`.

## Implementation guidance

- Keep the local-first workflow and explicit review before any server-changing operation.
- Validate project input and server settings on the backend. Browser validation is only for immediate feedback.
- Do not execute commands built from raw user input. Keep generated Docker files and deployment steps reviewable.
- Treat uploaded archives, repository contents, paths, and server addresses as untrusted input. Check archive paths and size limits before extraction.
- Use the local SSH agent for authentication and verify the server host key. Never collect or commit private keys, credentials, or secrets.
- Keep secrets out of plans and logs. Avoid adding real deployment operations to a normal page request; long-running work belongs in a separate process.
- Add focused tests for behavior added or changed, especially validation, analysis, planning, and deployment boundaries.
- Preserve existing uncommitted user changes unless the task requires modifying those files.
- After substantive project work, update `docs/progress/README.md` with what changed, how it was checked, and what remains. Keep entries factual and dated; do not mark planned features as complete.

## Current development settings

`app/config/settings.py` defaults to development mode for local commands. The container defaults to `DJANGO_DEBUG=false` and requires `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` at runtime. Its SQLite path defaults to `/data/db.sqlite3`; mount persistent storage at `/data` before deployment. Do not assume that the deployment claims on the landing page are implemented.
