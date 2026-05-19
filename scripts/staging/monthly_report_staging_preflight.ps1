param(
    [string]$ProjectId = "gen-lang-client-0360012476",
    [string]$Region = "asia-northeast1",
    [string]$ServiceName = "monthly-report-workshop-staging",
    [string]$JobName = "monthly-report-worker-staging"
)

$ErrorActionPreference = "Stop"

$script:Failures = @()

function Test-Step {
    param(
        [string]$Label,
        [bool]$Condition,
        [string]$SuccessMessage,
        [string]$FailureMessage
    )

    if ($Condition) {
        Write-Host "[OK]  $Label - $SuccessMessage"
        return
    }

    Write-Host "[NG]  $Label - $FailureMessage"
    $script:Failures += $Label
}

function Test-CommandExists {
    param([string]$CommandName)
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Get-GcloudValue {
    param([string[]]$Arguments)
    try {
        return (& gcloud @Arguments 2>$null).Trim()
    } catch {
        return ""
    }
}

function Test-GcloudResourceExists {
    param([string[]]$Arguments)
    try {
        & gcloud @Arguments 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

Write-Host "== Monthly Report Workshop staging preflight =="
Write-Host "project=$ProjectId region=$Region service=$ServiceName job=$JobName"

Test-Step `
    -Label "Dockerfile" `
    -Condition (Test-Path "Dockerfile") `
    -SuccessMessage "repo root Dockerfile is present" `
    -FailureMessage "Dockerfile is missing"

Test-Step `
    -Label "requirements-app.txt" `
    -Condition (Test-Path "requirements-app.txt") `
    -SuccessMessage "application dependency file is present" `
    -FailureMessage "requirements-app.txt is missing"

$migrationFiles = @(Get-ChildItem "supabase/migrations" -Filter "*.sql" -ErrorAction SilentlyContinue)
Test-Step `
    -Label "Supabase migrations" `
    -Condition ($migrationFiles.Count -gt 0) `
    -SuccessMessage "$($migrationFiles.Count) migration files found" `
    -FailureMessage "no SQL migration files found under supabase/migrations"

Test-Step `
    -Label "gcloud CLI" `
    -Condition (Test-CommandExists "gcloud") `
    -SuccessMessage "gcloud is available" `
    -FailureMessage "gcloud is not installed or not on PATH"

if (Test-CommandExists "gcloud") {
    $activeProject = Get-GcloudValue -Arguments @("config", "get-value", "project")
    Test-Step `
        -Label "gcloud project" `
        -Condition ($activeProject -eq $ProjectId) `
        -SuccessMessage "active project is $activeProject" `
        -FailureMessage "active project is '$activeProject' (expected '$ProjectId')"

    $account = Get-GcloudValue -Arguments @("auth", "list", "--filter=status:ACTIVE", "--format=value(account)")
    Test-Step `
        -Label "gcloud auth" `
        -Condition (-not [string]::IsNullOrWhiteSpace($account)) `
        -SuccessMessage "active account is $account" `
        -FailureMessage "no active gcloud account"

    $requiredApis = @(
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "artifactregistry.googleapis.com",
        "secretmanager.googleapis.com",
        "iam.googleapis.com",
        "docs.googleapis.com",
        "drive.googleapis.com",
        "sheets.googleapis.com"
    )

    $enabledApis = @(gcloud services list --enabled --project $ProjectId --format="value(config.name)" 2>$null)
    foreach ($api in $requiredApis) {
        Test-Step `
            -Label "api:$api" `
            -Condition ($enabledApis -contains $api) `
            -SuccessMessage "enabled" `
            -FailureMessage "not enabled"
    }

    $runtimeServiceAccount = "monthly-report-staging@$ProjectId.iam.gserviceaccount.com"
    $serviceAccountExists = Test-GcloudResourceExists -Arguments @(
        "iam",
        "service-accounts",
        "describe",
        $runtimeServiceAccount,
        "--project",
        $ProjectId
    )
    Test-Step `
        -Label "service-account:$runtimeServiceAccount" `
        -Condition $serviceAccountExists `
        -SuccessMessage "exists" `
        -FailureMessage "not found"
}

$requiredEnv = @(
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "OPENROUTER_MODEL_REPORT",
    "OPENROUTER_MODEL_LIGHT",
    "EB_MONTHLY_REPORT_PROMPT_VERSION",
    "EB_APP_VERSION"
)

foreach ($name in $requiredEnv) {
    $value = [Environment]::GetEnvironmentVariable($name)
    Test-Step `
        -Label "env:$name" `
        -Condition (-not [string]::IsNullOrWhiteSpace($value)) `
        -SuccessMessage "configured" `
        -FailureMessage "missing from current shell environment"
}

$requiredSecrets = @(
    "mrf-staging-eb-monthly-report-database-url",
    "mrf-staging-supabase-jwt-secret",
    "mrf-staging-google-oauth-client-secret",
    "mrf-staging-google-token-encryption-key",
    "mrf-staging-openrouter-api-key"
)

if (Test-CommandExists "gcloud") {
    foreach ($secretName in $requiredSecrets) {
        $secretPath = Get-GcloudValue -Arguments @(
            "secrets",
            "describe",
            $secretName,
            "--project",
            $ProjectId
        )
        Test-Step `
            -Label "secret:$secretName" `
            -Condition (-not [string]::IsNullOrWhiteSpace($secretPath)) `
            -SuccessMessage "exists" `
            -FailureMessage "not found in Secret Manager"

        if (-not [string]::IsNullOrWhiteSpace($secretPath)) {
            $enabledVersions = @(gcloud secrets versions list $secretName --project $ProjectId --format="value(name)" 2>$null)
            Test-Step `
                -Label "secret-version:$secretName" `
                -Condition ($enabledVersions.Count -gt 0) `
                -SuccessMessage "$($enabledVersions.Count) version(s) present" `
                -FailureMessage "no secret versions uploaded yet"
        }
    }
}

Write-Host ""
if ($script:Failures.Count -eq 0) {
    Write-Host "Preflight passed. Next: deploy image, run browser smoke, Cloud Run Job worker smoke, then live E2E."
    exit 0
}

Write-Host "Preflight failed. Resolve these items first:"
foreach ($failure in $script:Failures) {
    Write-Host " - $failure"
}
exit 1
