# FastAPI Base Project

## Purpose

This is the copyable base scaffold for a production-ready FastAPI service learned from this repo.

It is intentionally small:

- Python 3.12 + FastAPI
- Pydantic v2 settings via `pydantic-settings`
- Jinja2 page rendering and HTMX fragment rendering
- Tailwind CSS + DaisyUI-friendly SSR component conventions
- Local mock auth with a hard production guard
- Health endpoint for Cloud Run probes
- Focused pytest checks for health, auth, pages, and fragments
- Dockerfile and run commands for Cloud Run readiness
- Staging / production split checklist

Copy `templates/fastapi-base-project/` into a new repository, rename `base_app`, then run the checks below.

## UI Layer

The base project assumes normal browser UI is server-rendered with Jinja2 and updated with HTMX fragments. For LMS, admin, and workflow tools, use Tailwind CSS + DaisyUI as the default component layer:

- Use DaisyUI `table`, `badge`, `progress`, `steps`, `alert`, `form-control`, `input`, `select`, `textarea`, `btn`, `modal`, and `collapse` before adding another component library.
- Keep Flowbite out of the default scaffold. Add it only when a concrete screen needs a component DaisyUI cannot cover, and document the JavaScript dependency.
- Use Alpine.js only for small local UI state such as modal visibility, tabs, and toast timing.
- Prefer table/section layouts for operational screens. Use cards for repeated items, not as nested page sections.
- Return DaisyUI alert/status fragments for HTMX errors; do not assemble DOM from JSON in browser JavaScript for normal UI.

The copyable template includes CDN-based Tailwind/DaisyUI for quick local smoke checks. Production projects should replace that with a compiled Tailwind build that scans Jinja templates.

## Quality And Execution Assurance

Run these gates before handing the project to another engineer or deploying:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m compileall src tests
pytest
uvicorn base_app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Manual smoke checks:

- `GET /healthz` returns `{"status":"ok",...}`.
- `GET /` renders the Jinja page.
- `GET /fragments/summary` returns an HTML fragment.
- Local mock auth is allowed only when `APP_ENV=local` or `APP_ENV=test`.
- Production auth mode is not left as `mock`.

Cloud Run readiness checks:

- Container listens on `$PORT`.
- `PYTHONUNBUFFERED=1` is set.
- Runtime config is read from environment variables, not import-time globals.
- Secrets are injected by Secret Manager or equivalent runtime secret injection.
- Health endpoint has no database or external API dependency.
- Long-running work is not stored in in-memory process state.

Environment readiness checks:

- Prepare both `staging` and `production`; do not deploy directly from local to production.
- Use separate Cloud Run services, databases, OAuth redirect URIs, and runtime secrets.
- Run migrations, focused tests, smoke checks, and auth/OAuth checks in staging before promotion.
- Keep staging data synthetic or explicitly approved test data; never mix production data into staging.

## Files

| Path | Role |
|---|---|
| `templates/fastapi-base-project/README.md` | Scaffold quickstart |
| `templates/fastapi-base-project/UI_COMPONENTS.md` | Tailwind/DaisyUI component conventions |
| `templates/fastapi-base-project/src/base_app/main.py` | App factory and router wiring |
| `templates/fastapi-base-project/src/base_app/config.py` | Pydantic v2 settings |
| `templates/fastapi-base-project/src/base_app/auth.py` | Mock auth dependency and guard |
| `templates/fastapi-base-project/src/base_app/routers/health.py` | Cloud Run-safe health endpoint |
| `templates/fastapi-base-project/src/base_app/routers/pages.py` | Jinja/HTMX example routes |
| `templates/fastapi-base-project/tests/` | Focused regression tests |
| `templates/fastapi-base-project/.env.example` | Local env contract with no secrets |
| `templates/fastapi-base-project/Dockerfile` | Conservative Cloud Run container |

## Extension Points

Add project-specific modules after the base is green:

- `db/`: Supabase/Postgres client factories and RLS-aware accessors.
- `schemas/`: Pydantic request and response models.
- `services/`: business logic with external I/O isolated from routers.
- `templates/<feature>/fragments/`: HTMX fragments returned directly by page actions.
- `tests/test_<feature>.py`: focused tests for each new boundary.

Keep normal browser UI on SSR/HTMX HTML responses. JSON APIs are best reserved for workers, scripts, E2E helpers, and external integrations.
