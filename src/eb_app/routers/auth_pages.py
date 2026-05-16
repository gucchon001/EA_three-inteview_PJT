from __future__ import annotations

import html
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from eb_app.config import get_settings

router = APIRouter()


@router.get("/auth/google", include_in_schema=False)
def google_auth_start() -> HTMLResponse:
    return _auth_bridge_page(mode="start")


@router.get("/auth/callback", include_in_schema=False)
def google_auth_callback() -> HTMLResponse:
    return _auth_bridge_page(mode="callback")


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
