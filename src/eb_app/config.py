from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(raw: str | None) -> bool:
    if raw is None or raw.strip() == "":
        return False
    return raw.strip().lower() in frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class Settings:
    """環境変数から読む実行時設定（import 時ではなく create_app ごとに読み直す）。"""

    enable_mock_ui: bool
    auth_mode: str
    env: str
    monthly_report_database_url: str | None
    monthly_report_prompt_version: str
    app_version: str
    openrouter_api_key: str | None
    openrouter_model_report: str
    openrouter_model_light: str
    openrouter_timeout_seconds: float
    openrouter_max_tokens: int | None
    cloud_run_worker_job_project_id: str | None
    cloud_run_worker_job_region: str | None
    cloud_run_worker_job_name: str | None
    cloud_run_worker_trigger_access_token: str | None
    cloud_run_worker_trigger_timeout_seconds: float
    google_workspace_access_token: str | None
    google_oauth_client_id: str | None
    google_oauth_client_secret: str | None
    google_token_encryption_key: str | None
    google_token_encryption_key_version: str
    supabase_url: str | None
    supabase_anon_key: str | None
    google_oauth_scopes: str
    supabase_jwt_secret: str | None
    supabase_jwt_audience: str
    allowed_email_domain: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            enable_mock_ui=_truthy(os.environ.get("EB_ENABLE_MOCK_UI")),
            auth_mode=os.environ.get("EB_AUTH_MODE", "supabase").strip().lower() or "supabase",
            env=os.environ.get("EB_ENV", "local").strip().lower() or "local",
            monthly_report_database_url=(
                os.environ.get("EB_MONTHLY_REPORT_DATABASE_URL", "").strip() or None
            ),
            monthly_report_prompt_version=(
                os.environ.get("EB_MONTHLY_REPORT_PROMPT_VERSION", "").strip()
                or "monthly-report-v20260516.1"
            ),
            app_version=(
                os.environ.get("EB_APP_VERSION", "").strip()
                or os.environ.get("K_REVISION", "").strip()
                or os.environ.get("GITHUB_SHA", "").strip()
                or "local"
            ),
            openrouter_api_key=(os.environ.get("OPENROUTER_API_KEY", "").strip() or None),
            openrouter_model_report=(
                os.environ.get("OPENROUTER_MODEL_REPORT", "").strip()
                or os.environ.get("OPENROUTER_MODEL", "").strip()
                or "anthropic/claude-sonnet-4.6"
            ),
            openrouter_model_light=(
                os.environ.get("OPENROUTER_MODEL_LIGHT", "").strip()
                or os.environ.get("OPENROUTER_MODEL", "").strip()
                or "openai/gpt-4.1-mini"
            ),
            openrouter_timeout_seconds=float(
                os.environ.get("OPENROUTER_TIMEOUT", "").strip() or "120"
            ),
            openrouter_max_tokens=_optional_int(os.environ.get("OPENROUTER_MAX_TOKENS")),
            cloud_run_worker_job_project_id=(
                os.environ.get("EB_CLOUD_RUN_WORKER_JOB_PROJECT_ID", "").strip() or None
            ),
            cloud_run_worker_job_region=(
                os.environ.get("EB_CLOUD_RUN_WORKER_JOB_REGION", "").strip() or None
            ),
            cloud_run_worker_job_name=(
                os.environ.get("EB_CLOUD_RUN_WORKER_JOB_NAME", "").strip() or None
            ),
            cloud_run_worker_trigger_access_token=(
                os.environ.get("EB_CLOUD_RUN_WORKER_TRIGGER_ACCESS_TOKEN", "").strip()
                or None
            ),
            cloud_run_worker_trigger_timeout_seconds=float(
                os.environ.get("EB_CLOUD_RUN_WORKER_TRIGGER_TIMEOUT_SECONDS", "").strip()
                or "15"
            ),
            google_workspace_access_token=(
                os.environ.get("EB_GOOGLE_WORKSPACE_ACCESS_TOKEN", "").strip() or None
            ),
            google_oauth_client_id=(
                os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip() or None
            ),
            google_oauth_client_secret=(
                os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip() or None
            ),
            google_token_encryption_key=(
                os.environ.get("EB_GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip() or None
            ),
            google_token_encryption_key_version=(
                os.environ.get("EB_GOOGLE_TOKEN_ENCRYPTION_KEY_VERSION", "").strip()
                or "local-v1"
            ),
            supabase_url=(os.environ.get("SUPABASE_URL", "").strip() or None),
            supabase_anon_key=(os.environ.get("SUPABASE_ANON_KEY", "").strip() or None),
            google_oauth_scopes=(
                os.environ.get("EB_GOOGLE_OAUTH_SCOPES", "").strip()
                or "openid email profile https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/spreadsheets.readonly https://www.googleapis.com/auth/drive.readonly"
            ),
            supabase_jwt_secret=(
                os.environ.get("SUPABASE_JWT_SECRET", "").strip() or None
            ),
            supabase_jwt_audience=(
                os.environ.get("SUPABASE_JWT_AUDIENCE", "").strip() or "authenticated"
            ),
            allowed_email_domain=(
                os.environ.get("EB_ALLOWED_EMAIL_DOMAIN", "").strip()
                or "tomonokai-corp.com"
            ),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def _optional_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    return int(raw.strip())
