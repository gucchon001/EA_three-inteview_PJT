param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceUrl
)

$ErrorActionPreference = "Stop"

function Invoke-SmokeCheck {
    param(
        [string]$Label,
        [string]$Url,
        [int[]]$AllowedStatusCodes
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -MaximumRedirection 0
        $statusCode = [int]$response.StatusCode
    } catch {
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        } else {
            throw
        }
    }

    if ($AllowedStatusCodes -contains $statusCode) {
        Write-Host "[OK]  $Label - HTTP $statusCode"
        return $true
    }

    Write-Host "[NG]  $Label - HTTP $statusCode"
    return $false
}

$baseUrl = $ServiceUrl.TrimEnd("/")
$checks = @(
    @{ Label = "/health"; Url = "$baseUrl/health"; Allowed = @(200) },
    @{ Label = "/monthly-reports/jobs"; Url = "$baseUrl/monthly-reports/jobs"; Allowed = @(200, 302, 303, 401) },
    @{ Label = "/auth/google"; Url = "$baseUrl/auth/google"; Allowed = @(200, 302, 303) }
)

$failed = $false
Write-Host "== Monthly Report Workshop staging smoke =="
Write-Host "service_url=$baseUrl"

foreach ($check in $checks) {
    $ok = Invoke-SmokeCheck -Label $check.Label -Url $check.Url -AllowedStatusCodes $check.Allowed
    if (-not $ok) {
        $failed = $true
    }
}

if ($failed) {
    Write-Host "Smoke failed. Check service URL, ingress policy, and OAuth redirect configuration."
    exit 1
}

Write-Host "Smoke passed. Next: run normal UI live E2E."
exit 0
