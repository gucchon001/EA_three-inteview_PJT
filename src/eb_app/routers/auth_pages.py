from __future__ import annotations

import html
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from eb_app.auth.dependencies import _current_user_from_supabase_token
from eb_app.auth.session_cookie import set_auth_session_cookie
from eb_app.config import get_settings

router = APIRouter()


class AuthSessionCookieRequest(BaseModel):
    access_token: str = Field(min_length=1)


@router.get("/auth/google", include_in_schema=False)
def google_auth_start() -> HTMLResponse:
    return _auth_bridge_page(mode="start")


@router.get("/auth/callback", include_in_schema=False)
def google_auth_callback() -> HTMLResponse:
    return _auth_bridge_page(mode="callback")


@router.post("/auth/session-cookie", include_in_schema=False, status_code=204)
def set_supabase_auth_session_cookie(
    payload: AuthSessionCookieRequest,
    request: Request,
) -> Response:
    settings = get_settings()
    token = payload.access_token.strip()
    _current_user_from_supabase_token(f"Bearer {token}", settings)
    response = Response(status_code=204)
    set_auth_session_cookie(response, request, token)
    return response


@router.get("/monthly-report-workshop/e2e", include_in_schema=False)
def monthly_report_workshop_e2e() -> HTMLResponse:
    settings = get_settings()
    config = {
        "supabaseUrl": settings.supabase_url,
        "supabaseAnonKey": settings.supabase_anon_key,
        "googleScopes": settings.google_oauth_scopes,
    }
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_ANON_KEY", settings.supabase_anon_key),
        )
        if not value
    ]
    return HTMLResponse(_render_monthly_report_e2e(config=config, missing=missing))


def _auth_bridge_page(*, mode: str) -> HTMLResponse:
    settings = get_settings()
    config = {
        "mode": mode,
        "supabaseUrl": settings.supabase_url,
        "supabaseAnonKey": settings.supabase_anon_key,
        "googleScopes": settings.google_oauth_scopes,
        "callbackPath": "/auth/callback",
    }
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_ANON_KEY", settings.supabase_anon_key),
        )
        if not value
    ]
    body = _render_auth_bridge(config=config, missing=missing)
    return HTMLResponse(body)


def _render_auth_bridge(*, config: dict, missing: list[str]) -> str:
    config_json = json.dumps(config, ensure_ascii=False)
    missing_html = "".join(f"<li>{html.escape(name)}</li>" for name in missing)
    disabled = "disabled" if missing else ""
    status = (
        "Missing public Supabase settings."
        if missing
        else "Ready to connect Supabase Google provider."
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Google OAuth E2E Bridge</title>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f7f8;
      color: #172026;
      display: grid;
      place-items: center;
    }}
    main {{
      width: min(720px, calc(100vw - 32px));
      background: #ffffff;
      border: 1px solid #d9e0e3;
      border-radius: 8px;
      padding: 28px;
      box-shadow: 0 16px 40px rgba(23, 32, 38, 0.08);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    p {{
      line-height: 1.7;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 12px 16px;
      background: #176b5d;
      color: #ffffff;
      font-weight: 700;
      cursor: pointer;
    }}
    button:disabled {{
      opacity: .45;
      cursor: not-allowed;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
    }}
    pre {{
      white-space: pre-wrap;
      background: #eef3f4;
      border-radius: 6px;
      padding: 12px;
    }}
    .warn {{
      color: #8a4b00;
    }}
    .ok {{
      color: #176b5d;
    }}
  </style>
</head>
<body>
<main>
  <h1>Google OAuth E2E Bridge</h1>
  <p id="status">{html.escape(status)}</p>
  <ul>{missing_html}</ul>
  <button id="signin" {disabled}>Googleで接続</button>
  <pre id="log"></pre>
</main>
<script type="module">
  import {{ createClient }} from "https://esm.sh/@supabase/supabase-js@2";

  const config = {config_json};
  const log = document.querySelector("#log");
  const status = document.querySelector("#status");
  const button = document.querySelector("#signin");

  function write(message) {{
    log.textContent = message;
  }}

  function safeError(error) {{
    return error?.message || String(error || "unknown error");
  }}

  if (config.supabaseUrl && config.supabaseAnonKey) {{
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);

    button?.addEventListener("click", async () => {{
      write("Starting Google OAuth...");
      const redirectTo = new URL(config.callbackPath, window.location.origin).toString();
      const {{ error }} = await supabase.auth.signInWithOAuth({{
        provider: "google",
        options: {{
          redirectTo,
          scopes: config.googleScopes,
          queryParams: {{
            access_type: "offline",
            prompt: "consent"
          }}
        }}
      }});
      if (error) write(`OAuth start failed: ${{safeError(error)}}`);
    }});

    if (config.mode === "callback") {{
      await completeCallback(supabase);
    }}
  }}

  async function completeCallback(supabase) {{
    write("Completing Supabase callback...");
    const code = new URLSearchParams(window.location.search).get("code");
    if (code) {{
      const {{ error }} = await supabase.auth.exchangeCodeForSession(code);
      if (error) {{
        write(`Session exchange failed: ${{safeError(error)}}`);
        return;
      }}
    }}

    const {{ data, error }} = await supabase.auth.getSession();
    if (error || !data?.session) {{
      write(`Session not found: ${{safeError(error)}}`);
      return;
    }}

    const session = data.session;
    const cookieResponse = await fetch("/auth/session-cookie", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ access_token: session.access_token }})
    }});
    if (!cookieResponse.ok) {{
      status.className = "warn";
      write(`Session cookie setup failed: HTTP ${{cookieResponse.status}}`);
      return;
    }}

    const providerRefreshToken = session.provider_refresh_token;
    if (!providerRefreshToken) {{
      status.className = "warn";
      write("Supabase session has no provider_refresh_token. Re-consent with access_type=offline / prompt=consent, or revoke the app consent and try again.");
      return;
    }}

    const response = await fetch("/api/auth/google-oauth/supabase-session", {{
      method: "POST",
      headers: {{
        "Authorization": `Bearer ${{session.access_token}}`,
        "Content-Type": "application/json"
      }},
      body: JSON.stringify({{
        supabase_user_id: session.user.id,
        provider: "google",
        provider_user_id: session.user.app_metadata?.provider_id || null,
        email: session.user.email,
        provider_refresh_token: providerRefreshToken,
        scope: config.googleScopes
      }})
    }});

    const result = await response.json().catch(() => ({{}}));
    if (!response.ok) {{
      status.className = "warn";
      write(`Credential store failed: HTTP ${{response.status}} ${{result.detail || ""}}`);
      return;
    }}

    status.className = "ok";
    write(`Google refresh token stored. credential_id=${{result.credential_id}}, scope=${{result.scope}}`);
  }}
</script>
</body>
</html>"""


def _render_monthly_report_e2e(*, config: dict, missing: list[str]) -> str:
    config_json = json.dumps(config, ensure_ascii=False)
    missing_html = "".join(f"<li>{html.escape(name)}</li>" for name in missing)
    disabled = "disabled" if missing else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Monthly Report Workshop Live E2E</title>
  <style>
    :root {{
      --ink: #172026;
      --muted: #667780;
      --line: #d9e0e3;
      --panel: #ffffff;
      --bg: #f5f7f8;
      --accent: #176b5d;
      --warn: #8a4b00;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 24px clamp(16px, 4vw, 40px);
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    main {{
      width: min(1120px, calc(100vw - 32px));
      margin: 24px auto 48px;
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 18px;
    }}
    h1, h2 {{
      margin: 0;
      letter-spacing: 0;
    }}
    h1 {{
      font-size: 24px;
    }}
    h2 {{
      font-size: 16px;
    }}
    p {{
      line-height: 1.7;
      color: var(--muted);
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    label {{
      display: grid;
      gap: 6px;
      margin-top: 12px;
      font-size: 13px;
      color: var(--muted);
    }}
    input, textarea {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      color: var(--ink);
      background: #fff;
      font: inherit;
    }}
    textarea {{
      min-height: 88px;
      resize: vertical;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 10px 13px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{
      background: #33444c;
    }}
    button:disabled {{
      opacity: .45;
      cursor: not-allowed;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }}
    .status {{
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 6px;
      background: #eef3f4;
      color: var(--muted);
      font-size: 13px;
    }}
    .warn {{
      color: var(--warn);
    }}
    pre {{
      min-height: 420px;
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #101820;
      color: #d8f3ee;
      border-radius: 8px;
      padding: 16px;
      overflow: auto;
    }}
    @media (max-width: 860px) {{
      main {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
<header>
  <h1>Monthly Report Workshop Live E2E</h1>
  <p>Supabase Google login後に、1ジョブで source取得、OpenRouter生成、validation、artifact保存まで確認する開発用ページです。</p>
</header>
<main>
  <section>
    <h2>Run Settings</h2>
    <div id="auth-status" class="status">Checking session...</div>
    <ul>{missing_html}</ul>
    <div class="actions">
      <button id="signin" {disabled}>Googleで接続</button>
      <button id="refresh-session" class="secondary" {disabled}>セッション更新</button>
    </div>

    <label>target_month
      <input id="target-month" value="2026-05" autocomplete="off">
    </label>
    <label>household_key
      <input id="household-key" value="live-e2e-household" autocomplete="off">
    </label>
    <label>Google Doc IDs（1行1件）
      <textarea id="doc-ids" placeholder="docs document id"></textarea>
    </label>
    <label>Sheet ranges（spreadsheet_id | range | display_name）
      <textarea id="sheet-ranges" placeholder="spreadsheet_id | A1:Z100 | 面談記録"></textarea>
    </label>
    <label>prompt_scope_notes
      <textarea id="prompt-scope-notes" placeholder="対象生徒、対象外情報、家庭向け本文へ混ぜない情報など"></textarea>
    </label>
    <div class="actions">
      <button id="run-e2e" {disabled}>1ジョブE2Eを実行</button>
      <button id="load-result" class="secondary" {disabled}>結果を再取得</button>
    </div>
    <div id="job-status" class="status">job_id: none</div>
  </section>
  <section>
    <pre id="log"></pre>
  </section>
</main>
<script type="module">
  import {{ createClient }} from "https://esm.sh/@supabase/supabase-js@2";

  const config = {config_json};
  const log = document.querySelector("#log");
  const authStatus = document.querySelector("#auth-status");
  const jobStatus = document.querySelector("#job-status");
  const signInButton = document.querySelector("#signin");
  const refreshButton = document.querySelector("#refresh-session");
  const runButton = document.querySelector("#run-e2e");
  const loadButton = document.querySelector("#load-result");
  let supabase = null;
  let session = null;
  let currentJobId = null;

  function append(message, data) {{
    const line = data === undefined ? message : `${{message}}\\n${{JSON.stringify(data, null, 2)}}`;
    log.textContent = `${{log.textContent}}${{log.textContent ? "\\n\\n" : ""}}${{line}}`;
  }}

  function safeError(error) {{
    return error?.message || String(error || "unknown error");
  }}

  function bearerHeaders() {{
    return {{
      "Authorization": `Bearer ${{session.access_token}}`,
      "X-EB-Caller-Intent": "e2e",
      "Content-Type": "application/json"
    }};
  }}

  async function api(path, options = {{}}) {{
    const response = await fetch(path, {{
      ...options,
      headers: {{
        ...bearerHeaders(),
        ...(options.headers || {{}})
      }}
    }});
    const body = await response.json().catch(() => ({{}}));
    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}} ${{body.detail || response.statusText}}`);
    }}
    return body;
  }}

  function parseDocIds() {{
    return document.querySelector("#doc-ids").value
      .split(/\\r?\\n/)
      .map((value) => value.trim())
      .filter(Boolean);
  }}

  function parseSheetRanges() {{
    return document.querySelector("#sheet-ranges").value
      .split(/\\r?\\n/)
      .map((value) => value.trim())
      .filter(Boolean)
      .map((line) => {{
        const [spreadsheet_id, range_name, display_name] = line.split("|").map((part) => part.trim());
        return {{ spreadsheet_id, range_name, display_name: display_name || undefined }};
      }});
  }}

  function setJob(job) {{
    currentJobId = job.job_id;
    jobStatus.textContent = `job_id: ${{currentJobId}} / status: ${{job.status}} / stage: ${{job.current_stage || "none"}}`;
  }}

  async function refreshSession() {{
    if (!supabase) return;
    const {{ data, error }} = await supabase.auth.getSession();
    if (error || !data?.session) {{
      session = null;
      authStatus.className = "status warn";
      authStatus.textContent = `No Supabase session: ${{safeError(error)}}`;
      runButton.disabled = true;
      loadButton.disabled = true;
      return;
    }}
    session = data.session;
    authStatus.className = "status";
    authStatus.textContent = `Signed in: ${{session.user.email || session.user.id}}`;
    runButton.disabled = false;
    loadButton.disabled = !currentJobId;
  }}

  async function runE2E() {{
    log.textContent = "";
    await refreshSession();
    if (!session) return;

    append("1. Creating monthly report job...");
    const job = await api("/api/monthly-reports/jobs", {{
      method: "POST",
      body: JSON.stringify({{
        target_month: document.querySelector("#target-month").value,
        household_key: document.querySelector("#household-key").value,
        prompt_scope_notes: document.querySelector("#prompt-scope-notes").value || null
      }})
    }});
    setJob(job);
    append("Job created.", job);

    append("2. Fetching Google Workspace sources...");
    const sources = await api(`/api/monthly-reports/jobs/${{currentJobId}}/fetch-google-sources`, {{
      method: "POST",
      body: JSON.stringify({{
        doc_ids: parseDocIds(),
        sheet_ranges: parseSheetRanges()
      }})
    }});
    append("Sources saved.", sources);

    append("3. Running OpenRouter workflow...");
    const generated = await api(`/api/monthly-reports/jobs/${{currentJobId}}/run-openrouter`, {{
      method: "POST"
    }});
    setJob(generated);
    append("Workflow finished.", generated);

    await loadResult();
  }}

  async function loadResult() {{
    if (!session || !currentJobId) return;
    const [job, sources, artifacts, validations, llmCalls] = await Promise.all([
      api(`/api/monthly-reports/jobs/${{currentJobId}}`),
      api(`/api/monthly-reports/jobs/${{currentJobId}}/sources`),
      api(`/api/monthly-reports/jobs/${{currentJobId}}/artifacts`),
      api(`/api/monthly-reports/jobs/${{currentJobId}}/validations`),
      api(`/api/monthly-reports/jobs/${{currentJobId}}/llm-calls`)
    ]);
    setJob(job);
    append("4. Current result.", {{ job, sources, artifacts, validations, llm_calls: llmCalls }});
  }}

  if (config.supabaseUrl && config.supabaseAnonKey) {{
    supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    signInButton?.addEventListener("click", async () => {{
      const redirectTo = new URL("/auth/callback", window.location.origin).toString();
      const {{ error }} = await supabase.auth.signInWithOAuth({{
        provider: "google",
        options: {{
          redirectTo,
          scopes: config.googleScopes,
          queryParams: {{ access_type: "offline", prompt: "consent" }}
        }}
      }});
      if (error) append(`OAuth start failed: ${{safeError(error)}}`);
    }});
    refreshButton?.addEventListener("click", refreshSession);
    runButton?.addEventListener("click", () => runE2E().catch((error) => append(`E2E failed: ${{safeError(error)}}`)));
    loadButton?.addEventListener("click", () => loadResult().catch((error) => append(`Load failed: ${{safeError(error)}}`)));
    refreshSession();
  }} else {{
    authStatus.className = "status warn";
    authStatus.textContent = "Missing public Supabase settings.";
  }}
</script>
</body>
</html>"""
