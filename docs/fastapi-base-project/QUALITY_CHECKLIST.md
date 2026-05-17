# FastAPI Base Project Checklist

Use this checklist after copying the scaffold.

## 1. App Shape

- [ ] `create_app()` builds the FastAPI app without external network or database calls.
- [ ] Routers are small and call dependencies/services through `Depends()`.
- [ ] Settings are read through `get_settings()` and can be overridden in tests.
- [ ] Templates are under the app package, not a process-dependent working directory.

## 2. Auth And RLS Direction

- [ ] Local mock auth is blocked for `production`, `prod`, and `prd`.
- [ ] Production UI auth uses secure HTTP-only cookies and CSRF for write actions.
- [ ] Bearer token auth is treated as an API/E2E/internal compatibility path.
- [ ] Supabase/Postgres writes are designed around user identity and RLS, not service role by default.
- [ ] Service role or direct DB access is limited to admin, migration, or worker contexts.

## 3. HTMX/UI Boundary

- [ ] Normal UI routes return full HTML pages or HTML fragments.
- [ ] HTMX actions can swap the returned HTML without client-side JSON assembly.
- [ ] Error responses have user-safe messages and do not leak secrets or raw PII.
- [ ] Tailwind CSS + DaisyUI are the default component layer for operational UI.
- [ ] Flowbite or another JS-heavy component library is not added without a specific screen-level reason.
- [ ] Alpine.js is limited to local UI state and does not become global application state.
- [ ] Tables/sections are used for dense admin/LMS workflows; cards are limited to repeated items or modals.

## 4. Cloud Run

- [ ] `/healthz` has no database, auth, or external API dependency.
- [ ] Container uses `$PORT`.
- [ ] Secrets are runtime-injected, never committed.
- [ ] Background jobs do not rely on per-process memory when more than one worker may run.
- [ ] Blocking sync I/O is kept in `def` routes/services or explicitly sent to a threadpool.

## 5. Staging / Production

- [ ] `staging` and `production` have separate Cloud Run services.
- [ ] `staging` and `production` have separate databases or Supabase projects.
- [ ] OAuth redirect URIs are registered per environment and do not cross over.
- [ ] Runtime secrets are separated per environment.
- [ ] Migrations, focused tests, smoke checks, and auth/OAuth checks run in staging before production promotion.

## 6. Quality Gates

- [ ] `python -m compileall src tests`
- [ ] `pytest`
- [ ] `uvicorn base_app.main:app --app-dir src --host 127.0.0.1 --port 8000`
- [ ] Manual `GET /healthz`
- [ ] Manual page and fragment smoke check
