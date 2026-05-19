# FastAPI Base Project

Small FastAPI base with Jinja2, HTMX fragments, Tailwind/DaisyUI-friendly templates, Pydantic v2 settings, guarded mock auth, pytest, and Cloud Run-ready container settings.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
$env:APP_AUTH_MODE="mock"
$env:APP_ENV="local"
uvicorn base_app.main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/fragments/summary`

## Checks

```powershell
python scripts/check.py
```

The check script runs `python -m compileall src tests` and `python -m pytest` from
the scaffold root, so copied projects have one consistent local quality entrypoint.

## UI Components

Use `UI_COMPONENTS.md` as the UI convention sheet before adding screens.

- Default to Tailwind CSS + DaisyUI for LMS/admin/workflow UI.
- Keep Flowbite out of the base unless a concrete screen needs it.
- Use Alpine.js only for small local state.
- Keep normal UI responses as HTML pages or HTMX fragments.

The sample template uses CDN-based Tailwind/DaisyUI so the scaffold looks usable immediately. For production, replace CDN loading with a compiled Tailwind build that scans `src/base_app/templates/**/*.html`.

## Layout

```text
src/base_app/
  main.py              app factory and router wiring
  config.py            Pydantic v2 settings
  auth.py              current-user dependency with local mock mode
  routers/
    health.py          Cloud Run-safe health endpoint
    pages.py           Jinja page and HTMX fragment routes
  templates/
    base.html
    home.html
    fragments/summary.html
tests/
```

## Production Notes

- Do not run production with `APP_AUTH_MODE=mock`.
- Keep browser UI on secure HTTP-only cookies and CSRF for write actions.
- Keep Bearer token auth for API, E2E, worker, or migration compatibility paths.
- Put Supabase/Postgres access behind dependencies that receive the current user and preserve RLS boundaries.
- Inject secrets at runtime. Do not commit `.env` or secret values.
- Prepare both staging and production. Use separate Cloud Run services, databases, OAuth redirect URIs, and runtime secrets, then promote to production only after staging migrations, focused tests, smoke checks, and auth/OAuth checks pass.
