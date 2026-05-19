# RLS / Direct DB Boundary Audit

## Position

- Canonical/auxiliary: P1-16 implementation audit note
- Related docs: `development-plan.md`, `security-operations.md`, `api-definition.md`, `data-design.md`
- Last updated: 2026-05-19

## Decisions

- Supabase RLS is the primary boundary for normal user operations.
- Direct DB / server store access remains allowed for worker, admin, migration, retention deletion, and server-only maintenance.
- Normal HTMX UI already uses RLS read-store for reads and RLS read preflight for the main write actions. Full RLS write is the next migration, not a prerequisite for the current MVP skeleton.
- JSON APIs remain available for worker, E2E, admin scripts, and future integration. They must not be used by the normal UI for DOM updates, and JSON write APIs now have a caller-intent matrix in `api-definition.md`.

## Current Boundary Map

| Area | Current implementation | Boundary status | Next action |
|---|---|---|---|
| HTML list/detail/status/preview/sources/validation reads | `SupabaseMonthlyReportReadStore` first, fallback to direct store for mock/admin/config gaps | Acceptable for current P1-16 | Keep focused tests; remove fallback only after production auth is stable |
| HTML source save | RLS read preflight, then user-JWT Supabase source write when available; mock/admin fallback direct | Improved, acceptable for current P1-16 | Keep focused tests and revisit only if source snapshots move to Storage-backed RPC |
| HTML Google source fetch | RLS read preflight, server-side Google token handling, then user-JWT Supabase source write when available; mock/admin fallback direct | Improved, acceptable for current P1-16 | Keep token refresh server-side; leave direct DB only for credential lookup and workflow paths |
| HTML edited markdown save | RLS read preflight, then user-JWT Supabase artifact write when available; mock/admin fallback direct | Improved, acceptable for current P1-16 | Keep focused tests; revisit when artifact payloads move to Storage-backed RPC |
| HTML feedback save | RLS read preflight, then user-JWT Supabase client write when available; mock/admin fallback remains direct | First full-RLS write POC | Keep focused tests; add real Postgres/Supabase RLS write smoke when env is available |
| HTML run/start | RLS read preflight, then direct stage/workflow mutation | Transitional, worker-adjacent | Keep direct until worker/job state machine is fully server-owned |
| HTML rerun | RLS read preflight, then direct rerun write | Transitional | Keep direct until job clone semantics and active-limit checks are moved behind RPC/service layer |
| JSON reads | RLS read-store first for normal users | Acceptable | Maintain as future integration read path |
| JSON source/artifact/feedback writes | RLS read preflight, then user-JWT Supabase write when available; mock/admin fallback direct | Improved, still mixed boundary | Keep caller-intent matrix current and decide whether to freeze on this shape or move selected routes behind RPC |
| JSON validation/stage/fail/cancel/run APIs | Direct store | Internal/admin/worker leaning | `start` / `complete-stage` / `fail` / `cancel` / `run-*` / `rerun` now require `X-EB-Caller-Intent` (`e2e` or `admin`) in nonmock; keep shrinking toward worker/admin-only paths |
| Worker workflow | Direct Postgres store | Allowed | Keep direct; add idempotent persistence and heartbeat/stuck handling |
| Migrations/retention deletion | Direct DB | Allowed | Add runbooks and dry-run tests before production |

## Current Direct DB Inventory

Direct DB is still the intended boundary for these categories:

- Worker-owned execution:
  `src/eb_app/monthly_reports/worker.py`, `src/eb_app/monthly_reports/worker_entry.py`, `src/eb_app/monthly_reports/workflow.py`
- Server-side audit and credential handling:
  `src/eb_app/routers/monthly_reports.py` via `_record_job_audit_log(...)` and `_resolve_google_workspace_access_token(...)`
- Retention / maintenance:
  `src/eb_app/monthly_reports/retention.py`, `src/eb_app/monthly_reports/retention_entry.py`
- Store construction / fallback:
  `_get_store()` in `src/eb_app/routers/monthly_reports.py` for mock/admin/config-gap fallback and server-owned paths

Direct DB remains in normal request code for these transitional paths:

- `POST /api/monthly-reports/jobs`
  Job create stays a service-owned direct insert, even for normal authenticated users. Auth decides the effective owner; the request body does not.
- Job state mutation routes:
  `start`, `complete-stage`, `fail`, `manual-recovery/fail`, `cancel`, `run-mock`, `run-openrouter`, `rerun`
  These remain direct DB routes, but in nonmock they now require explicit `X-EB-Caller-Intent` and are no longer treated as generic normal-user JSON writes.
- Audit log writes and Google OAuth credential refresh lookups

Routes that were previously listed as direct but are now moved off the critical path for normal user writes:

- HTML/JSON manual source save
- HTML/JSON Google source persistence
- HTML edited markdown save
- HTML/JSON append-only artifact save
- HTML/JSON feedback save

## Direct DB Calls To Keep

- `worker_entry.py` and `worker.py`: claims, retries, job state transitions, LLM workflow persistence.
- `workflow.py`: records artifacts, validations, LLM logs, reproducibility metadata as part of server-owned job execution.
- Retention deletion and future maintenance scripts.
- Admin-only tuning and recovery routes, once role checks are explicit.

## Direct DB Calls To Migrate First

1. `POST /api/monthly-reports/jobs`
   - Still direct store for create + active-limit enforcement.
   - Likely next high-value boundary decision: keep as service-owned insert or move to RLS/RPC.

2. Job state mutation routes
   - `start`, `complete-stage`, `fail`, `manual-recovery/fail`, `cancel`, `run-mock`, `run-openrouter`, `rerun`
   - These should not drift into "normal user generic JSON write" territory. 2026-05-19 first split: nonmock callers must declare `X-EB-Caller-Intent: e2e|admin`, and `admin` requires an admin role.
   - `manual-recovery/fail` is the first explicit admin-only stuck-job recovery command and records only PII-safe audit metadata.

3. Audit log and credential infrastructure
   - `_record_job_audit_log(...)`
   - `_resolve_google_workspace_access_token(...)` via `PostgresGoogleOAuthCredentialStore`
   - These are expected server-owned direct DB paths and should be documented rather than forced behind RLS.

4. `POST /monthly-reports/jobs/{job_id}/fragments/feedback`
   - Lowest risk: append-only, small payload, already has idempotency and preflight.
   - 2026-05-18 first POC done: normal Supabase users write through the user-JWT Supabase client into `monthly_report_feedback`; mock/admin fallback remains direct.

5. `POST /monthly-reports/jobs/{job_id}/fragments/edited-markdown`
   - Medium risk: append-only artifact, larger content, needs storage-path future compatibility.
   - 2026-05-19 moved to the user-JWT Supabase artifact write path for normal Supabase users; remaining question is whether Storage migration should replace this with RPC.

## Routes Requiring Role Split Before Full Migration

- `POST /api/monthly-reports/jobs/{job_id}/validations`
  First split done: nonmock callers now need `X-EB-Caller-Intent: e2e|admin`, matching the other internal/admin/E2E JSON mutation routes.
- `POST /api/monthly-reports/jobs/{job_id}/start`
- `POST /api/monthly-reports/jobs/{job_id}/complete-stage`
- `POST /api/monthly-reports/jobs/{job_id}/fail`
- `POST /api/monthly-reports/jobs/{job_id}/manual-recovery/fail`
- `POST /api/monthly-reports/jobs/{job_id}/cancel`
- `POST /api/monthly-reports/jobs/{job_id}/run-mock`
- `POST /api/monthly-reports/jobs/{job_id}/run-openrouter`
- `POST /api/monthly-reports/jobs`
- `POST /api/monthly-reports/jobs/{job_id}/rerun`

These should become one of:

- internal/admin route with explicit role check,
- worker-only code path not exposed to normal users,
- normal UI route backed by RLS/RPC and CSRF,
- E2E-only route disabled in production.

## Acceptance Criteria For Next P1-16 Slice

- Keep the role/caller-intent table in `api-definition.md` current whenever a JSON write route changes.
- Keep a single inventory of allowed direct DB paths and update it when a route moves categories.
- Keep `POST /api/monthly-reports/jobs` documented and tested as a service-owned direct insert.
- Add explicit role/caller intent for the remaining direct JSON mutation routes before production hardening.
- Keep `X-EB-Caller-Intent` enforced and documented for the direct JSON mutation routes until they move to worker-only/admin-only/RPC boundaries.
- Add focused tests for:
  - owner can write via RLS/RPC,
  - non-owner cannot write,
  - direct store fallback remains available for mock/admin,
  - idempotency still prevents double-write.
- Keep worker and workflow direct DB paths unchanged.

## Revision History

| Date | Change |
|---|---|
| 2026-05-17 | Initial direct DB boundary audit after P1-16 read/preflight migration |
| 2026-05-18 | Feedback save moved to first user-JWT Supabase write POC with direct fallback for mock/admin |
| 2026-05-18 | Added JSON write API caller-intent matrix to `api-definition.md` and made it the tracking point for public/internal route split |
| 2026-05-19 | Manual source save / Google source persistence moved to user-JWT Supabase write when available; inventory narrowed to job create, state mutation, audit, worker, credential, and retention paths |
| 2026-05-19 | `start` / `complete-stage` / `fail` / `cancel` / `run-*` / `rerun` now require explicit `X-EB-Caller-Intent` in nonmock, making the internal/admin/E2E split executable in code |
