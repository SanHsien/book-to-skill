[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory)]
        [string]$Label,
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    Write-Host "==> $Label"
    & $script:pythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-PythonStep -Label "Compile maintained Python" -Arguments @(
    "-m", "compileall", "-q", "book_to_skill", "scripts", "tests", "tools"
)
Invoke-PythonStep -Label "Ruff (E9 + F)" -Arguments @(
    "-m", "ruff", "check", "--select", "E9,F", "--target-version", "py310",
    "book_to_skill", "scripts", "tests", "tools"
)
Invoke-PythonStep -Label "Pytest" -Arguments @("-m", "pytest", "tests", "-q")
Invoke-PythonStep -Label "Validate SKILL.md" -Arguments @(
    "tools\validate_skill.py", "SKILL.md"
)

function Invoke-SkillSpectorSelfScan {
    # Pre-publish self-scan: run the SkillSpector security scanner against the
    # skill this repo distributes, the same way a downstream host would scan it
    # before installing (docs/install.md: hosts git-clone the whole repo into
    # their skills folder, so the repo root *is* the installed skill). Ratchet,
    # not one-time: new findings (anything not already in
    # .skillspector-baseline.yaml) fail this gate; they must be reviewed and
    # either fixed or added to the baseline with a specific reason -- never
    # rubber-stamped.
    #
    # Scan target: a staged copy of "git ls-files --cached --others
    # --exclude-standard" (tracked + trackable-untracked files), not the working
    # tree directly. This mirrors exactly what git-clone would ship and excludes
    # local-only, gitignored artifacts (.venv, .ruff_cache, __pycache__,
    # downloaded books, generated output) that would otherwise make findings
    # unstable across machines and inflate scan time on content nobody installs.
    #
    # Gate signal is the JSON report's issues array, not $LASTEXITCODE:
    # SkillSpector's exit code reflects an aggregate risk-score threshold (see its
    # docs/SUPPRESSION.md), not "any un-suppressed finding present", so relying on
    # exit code alone would silently let new LOW/MEDIUM findings through.
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot
    )

    $skillSpectorCmd = Get-Command skillspector -ErrorAction SilentlyContinue
    if (-not $skillSpectorCmd) {
        Write-Host "==> SkillSpector self-scan (skipped: 'skillspector' not found on PATH)"
        return
    }

    $baselinePath = Join-Path $RepoRoot ".skillspector-baseline.yaml"
    if (-not (Test-Path -LiteralPath $baselinePath)) {
        throw ("Missing " + $baselinePath + " -- generate baseline entries with " +
            "'skillspector baseline <staged-copy> --no-llm --reason ...' before " +
            "this gate can run.")
    }

    $reportDir = Join-Path $RepoRoot ".skillspector-reports"
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    $reportPath = Join-Path $reportDir "book-to-skill.json"

    $stageDir = Join-Path ([IO.Path]::GetTempPath()) (
        "skillspector-stage-book-to-skill-" + [IO.Path]::GetRandomFileName()
    )
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

    try {
        Write-Host "==> SkillSpector self-scan (git-tracked files, staged copy)"
        $files = git -C $RepoRoot ls-files --cached --others --exclude-standard |
            Where-Object { $_ -ne ".skillspector-baseline.yaml" }
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files failed with exit code $LASTEXITCODE"
        }
        foreach ($relativePath in $files) {
            $source = Join-Path $RepoRoot $relativePath
            $destination = Join-Path $stageDir $relativePath
            $destinationDir = Split-Path -Parent $destination
            if ($destinationDir -and -not (Test-Path -LiteralPath $destinationDir)) {
                New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
            }
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }

        & $skillSpectorCmd.Source scan $stageDir --no-llm --format json --output $reportPath --baseline $baselinePath
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
            throw "skillspector scan crashed (exit code $LASTEXITCODE); see $reportPath"
        }
        $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
        if ($report.issues.Count -gt 0) {
            throw ("SkillSpector found " + $report.issues.Count + " new, un-baselined " +
                "finding(s). Review " + $reportPath + " and either fix the content or add a " +
                "reviewed fingerprint/rule to .skillspector-baseline.yaml with a " +
                "specific reason -- do not rubber-stamp CRITICAL or otherwise real " +
                "findings into the baseline.")
        }
        Write-Host "SkillSpector self-scan: no new findings."
    } finally {
        Remove-Item -Recurse -Force -LiteralPath $stageDir -ErrorAction SilentlyContinue
    }
}

Invoke-SkillSpectorSelfScan -RepoRoot $repoRoot

Write-Host "WINDOWS DEV CHECK GREEN"
