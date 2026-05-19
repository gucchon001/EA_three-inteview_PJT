param(
    [string]$ProjectId = "gen-lang-client-0360012476",
    [string]$Region = "asia-northeast1",
    [string]$WorkerJobName = "monthly-report-worker-staging",
    [string]$EnvironmentName = "staging",
    [string[]]$NotificationChannels = @(),
    [string]$RunbookUrl = "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/staging-deploy-runbook.md",
    [string]$SecurityOperationsUrl = "https://github.com/gucchon001/EA_three-inteview_PJT/blob/main/docs/monthly-report-workshop/security-operations.md",
    [string]$OutputDirectory = "",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$CommandName)
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Resolve-NotificationChannels {
    param(
        [string]$ProjectId,
        [string[]]$NotificationChannels
    )

    $resolved = @()
    foreach ($channel in $NotificationChannels) {
        $normalized = $channel.Trim()
        if (-not $normalized) {
            continue
        }
        if ($normalized.StartsWith("projects/")) {
            $resolved += $normalized
            continue
        }
        $resolved += "projects/$ProjectId/notificationChannels/$normalized"
    }
    return $resolved
}

function New-RunbookMarkdown {
    param(
        [string]$EnvironmentName,
        [string]$RunbookUrl,
        [string]$SecurityOperationsUrl,
        [string]$WorkerJobName
    )

    return @"
## Monthly Report Workshop $EnvironmentName alert

- Worker job: `$WorkerJobName`
- Primary runbook: $RunbookUrl
- Security / manual recovery: $SecurityOperationsUrl
- Baseline success execution: `monthly-report-worker-staging-fpfks` (2026-05-19)

Keep notification payloads PII-safe. Do not paste report bodies, source text, prompt text, tokens, or secrets into incident notes.
"@
}

function New-LogMetricConfig {
    param(
        [string]$Description,
        [string]$Filter
    )

    return @{
        description = $Description
        filter = $Filter
        metricDescriptor = @{
            metricKind = "DELTA"
            valueType = "INT64"
            unit = "1"
            labels = @(
                @{
                    key = "stage"
                    valueType = "STRING"
                    description = "monthly report pipeline stage"
                },
                @{
                    key = "error_type"
                    valueType = "STRING"
                    description = "normalized worker error type"
                },
                @{
                    key = "resolved_model"
                    valueType = "STRING"
                    description = "resolved provider model when available"
                },
                @{
                    key = "prompt_version"
                    valueType = "STRING"
                    description = "prompt version when available"
                }
            )
        }
        labelExtractors = @{
            stage = "EXTRACT(jsonPayload.stage)"
            error_type = "EXTRACT(jsonPayload.error_type)"
            resolved_model = "EXTRACT(jsonPayload.resolved_model)"
            prompt_version = "EXTRACT(jsonPayload.prompt_version)"
        }
    }
}

function New-AlertPolicies {
    param(
        [string]$WorkerJobName,
        [string]$EnvironmentName,
        [string[]]$NotificationChannels,
        [string]$RunbookUrl,
        [string]$SecurityOperationsUrl
    )

    $documentation = New-RunbookMarkdown `
        -EnvironmentName $EnvironmentName `
        -RunbookUrl $RunbookUrl `
        -SecurityOperationsUrl $SecurityOperationsUrl `
        -WorkerJobName $WorkerJobName

    $channels = @($NotificationChannels)

    return @(
        @{
            displayName = "monthly-report-$EnvironmentName-worker-manual-recovery"
            documentation = @{
                content = $documentation
                mimeType = "text/markdown"
            }
            combiner = "OR"
            conditions = @(
                @{
                    displayName = "worker summary status manual_recovery_required"
                    conditionMatchedLog = @{
                        filter = @"
resource.type="cloud_run_job"
resource.labels.job_name="$WorkerJobName"
jsonPayload.status="manual_recovery_required"
"@
                    }
                }
            )
            enabled = $true
            notificationChannels = $channels
            alertStrategy = @{
                notificationRateLimit = @{
                    period = "300s"
                }
                autoClose = "86400s"
            }
            severity = "ERROR"
        },
        @{
            displayName = "monthly-report-$EnvironmentName-worker-failed-spike"
            documentation = @{
                content = $documentation
                mimeType = "text/markdown"
            }
            combiner = "OR"
            conditions = @(
                @{
                    displayName = "worker failed count >= 3 in 1h"
                    conditionThreshold = @{
                        filter = @"
resource.type="cloud_run_job"
resource.labels.job_name="$WorkerJobName"
metric.type="logging.googleapis.com/user/monthly_report_worker_failed_count"
"@
                        comparison = "COMPARISON_GT"
                        thresholdValue = 2
                        duration = "0s"
                        aggregations = @(
                            @{
                                alignmentPeriod = "3600s"
                                perSeriesAligner = "ALIGN_DELTA"
                                crossSeriesReducer = "REDUCE_SUM"
                                groupByFields = @(
                                    "metric.label.stage",
                                    "metric.label.error_type"
                                )
                            }
                        )
                        trigger = @{
                            count = 1
                        }
                    }
                }
            )
            enabled = $true
            notificationChannels = $channels
            alertStrategy = @{
                autoClose = "86400s"
            }
            severity = "WARNING"
        },
        @{
            displayName = "monthly-report-$EnvironmentName-worker-fetch-sources-stale"
            documentation = @{
                content = $documentation
                mimeType = "text/markdown"
            }
            combiner = "OR"
            conditions = @(
                @{
                    displayName = "worker summary failed at fetch_sources"
                    conditionMatchedLog = @{
                        filter = @"
resource.type="cloud_run_job"
resource.labels.job_name="$WorkerJobName"
jsonPayload.job_stage="fetch_sources"
(jsonPayload.status="failed" OR jsonPayload.status="retry_scheduled")
"@
                    }
                }
            )
            enabled = $true
            notificationChannels = $channels
            alertStrategy = @{
                notificationRateLimit = @{
                    period = "300s"
                }
                autoClose = "86400s"
            }
            severity = "WARNING"
        }
    )
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine)
}

function Test-GcloudSuccess {
    param([string[]]$Arguments)
    & gcloud @Arguments 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

function Upsert-LogMetric {
    param(
        [string]$ProjectId,
        [string]$MetricName,
        [string]$ConfigPath
    )

    if (Test-GcloudSuccess -Arguments @("logging", "metrics", "describe", $MetricName, "--project", $ProjectId)) {
        Write-Host "[UPDATE] log metric $MetricName"
        & gcloud logging metrics update $MetricName --project $ProjectId --config-from-file $ConfigPath
        return
    }

    Write-Host "[CREATE] log metric $MetricName"
    & gcloud logging metrics create $MetricName --project $ProjectId --config-from-file $ConfigPath
}

function Get-AlertPolicyNameByDisplayName {
    param(
        [string]$ProjectId,
        [string]$DisplayName
    )

    $raw = & gcloud alpha monitoring policies list --project $ProjectId --format json
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        return $null
    }

    $policies = $raw | ConvertFrom-Json
    foreach ($policy in $policies) {
        if ($policy.displayName -eq $DisplayName) {
            return $policy.name
        }
    }
    return $null
}

function Upsert-AlertPolicy {
    param(
        [string]$ProjectId,
        [string]$DisplayName,
        [string]$ConfigPath
    )

    $existingName = Get-AlertPolicyNameByDisplayName -ProjectId $ProjectId -DisplayName $DisplayName
    if ($existingName) {
        Write-Host "[UPDATE] alert policy $DisplayName"
        & gcloud alpha monitoring policies update $existingName --project $ProjectId --policy-from-file $ConfigPath
        return
    }

    Write-Host "[CREATE] alert policy $DisplayName"
    & gcloud alpha monitoring policies create --project $ProjectId --policy-from-file $ConfigPath
}

if (-not (Test-CommandExists "gcloud")) {
    throw "gcloud is not installed or not on PATH"
}

$resolvedChannels = Resolve-NotificationChannels -ProjectId $ProjectId -NotificationChannels $NotificationChannels
if ($Apply -and $resolvedChannels.Count -eq 0) {
    throw "-Apply requires at least one -NotificationChannels value"
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "monthly-report-staging-monitoring"
}
Ensure-Directory -Path $OutputDirectory

$metricName = "monthly_report_worker_failed_count"
$metricConfigPath = Join-Path $OutputDirectory "$metricName.json"
$metricConfig = New-LogMetricConfig `
    -Description "Counts monthly report worker provider/validation failures for Cloud Run alerting." `
    -Filter @'
(resource.type="cloud_run_revision" OR resource.type="cloud_run_job")
jsonPayload.component="monthly_report_workshop"
(jsonPayload.event="monthly_report.provider_failed" OR jsonPayload.event="monthly_report.validation_failed")
'@
Write-JsonFile -Path $metricConfigPath -Value $metricConfig

$policies = New-AlertPolicies `
    -WorkerJobName $WorkerJobName `
    -EnvironmentName $EnvironmentName `
    -NotificationChannels $resolvedChannels `
    -RunbookUrl $RunbookUrl `
    -SecurityOperationsUrl $SecurityOperationsUrl

$policyPaths = @()
foreach ($policy in $policies) {
    $path = Join-Path $OutputDirectory ($policy.displayName + ".json")
    Write-JsonFile -Path $path -Value $policy
    $policyPaths += $path
}

Write-Host "== Monthly Report Workshop staging monitoring config =="
Write-Host "project=$ProjectId region=$Region worker_job=$WorkerJobName"
Write-Host "output_directory=$OutputDirectory"
Write-Host "runbook_url=$RunbookUrl"
Write-Host "security_operations_url=$SecurityOperationsUrl"
if ($resolvedChannels.Count -gt 0) {
    Write-Host "notification_channels=$($resolvedChannels -join ', ')"
} else {
    Write-Host "notification_channels=(none configured yet)"
}
Write-Host ""
Write-Host "Generated files:"
Write-Host " - $metricConfigPath"
foreach ($path in $policyPaths) {
    Write-Host " - $path"
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Preview only. No Cloud Logging metrics or Cloud Monitoring policies were changed."
    Write-Host "Re-run with -Apply and at least one -NotificationChannels value to create/update resources."
    exit 0
}

Upsert-LogMetric -ProjectId $ProjectId -MetricName $metricName -ConfigPath $metricConfigPath
foreach ($policy in $policies) {
    $path = Join-Path $OutputDirectory ($policy.displayName + ".json")
    Upsert-AlertPolicy -ProjectId $ProjectId -DisplayName $policy.displayName -ConfigPath $path
}

Write-Host ""
Write-Host "Monitoring resources are up to date."
exit 0
