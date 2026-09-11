[CmdletBinding()]
param(
    [string]$SkillSpectorPython = ""
)

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

if ([string]::IsNullOrWhiteSpace($SkillSpectorPython)) {
    $skillSpectorPythonExe = $pythonExe
} elseif (Test-Path -LiteralPath $SkillSpectorPython -PathType Leaf) {
    $skillSpectorPythonExe = (Resolve-Path -LiteralPath $SkillSpectorPython).Path
} else {
    $skillSpectorPythonExe = (Get-Command $SkillSpectorPython -ErrorAction Stop).Source
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
    # tools\stage_scan_input.py also restores the index line endings: exact
    # fingerprints hash file content, and a checkout made before .gitattributes
    # keeps CRLF text files that CI checks out as LF, which would otherwise report
    # every baselined finding as new on that machine.
    #
    # Gate signal is the JSON report's issues array, not $LASTEXITCODE:
    # SkillSpector's exit code reflects an aggregate risk-score threshold (see its
    # docs/SUPPRESSION.md), not "any un-suppressed finding present", so relying on
    # exit code alone would silently let new LOW/MEDIUM findings through.
    param(
        [Parameter(Mandatory)]
        [string]$RepoRoot
    )

    & $script:skillSpectorPythonExe -c "import skillspector" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw ("Required SkillSpector self-scan cannot run in the selected Python. " +
            "Install requirements-security.txt before running " +
            "this canonical gate.")
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

    # Lift the scanner's time ceilings for the self-scan. They bound pathological
    # input, but a large file on slow storage sits close enough to them that machine
    # load decides whether the scan completes -- the same tree then passes or exits 2
    # depending on what else is running. A gate has to be reproducible, so here we buy
    # completeness with wall time.
    #
    # 86400 (one day), not 0. SKILLSPECTOR_MAX_WORKFLOW_SECONDS has been upstream's own
    # variable since SkillSpector 2.11.1, and upstream rejects 0, negatives and
    # non-finite values with a warning and falls back to its 600-second default -- so
    # "0" would silently mean 600 s. A large positive value means the same thing under
    # every build. SKILLSPECTOR_MAX_STATIC_SECONDS (per artifact, default 30 s) exists
    # only in the SanHsien fork and takes the same value; builds without it ignore it,
    # which is the previous behaviour rather than a silent weakening.
    $previousStaticBudget = $env:SKILLSPECTOR_MAX_STATIC_SECONDS
    $previousWorkflowBudget = $env:SKILLSPECTOR_MAX_WORKFLOW_SECONDS
    $previousPythonHashSeed = $env:PYTHONHASHSEED
    $env:SKILLSPECTOR_MAX_STATIC_SECONDS = "86400"
    # The whole repository is scanned as one bundle, so the graph-wide budget is the
    # binding one (60 s before SkillSpector 2.11.1, 600 s after): once it expires every
    # remaining file is recorded as runtime_limit with no findings, which reads as a
    # clean scan. Lift both or the gate reports "no findings" for files it never opened.
    $env:SKILLSPECTOR_MAX_WORKFLOW_SECONDS = "86400"
    # Fix interpreter hash order as a second stability guard. The wrapper below
    # also serializes analyzer branches, which prevents nondeterministic merges.
    $env:PYTHONHASHSEED = "0"
    try {
        Write-Host "==> SkillSpector self-scan (git-tracked files, staged copy)"
        & $script:pythonExe tools\stage_scan_input.py --repo $RepoRoot --dest $stageDir `
            --exclude .skillspector-baseline.yaml
        if ($LASTEXITCODE -ne 0) {
            throw "Staging the SkillSpector scan input failed with exit code $LASTEXITCODE"
        }

        & $script:skillSpectorPythonExe tools\run_skillspector.py $stageDir `
            --output $reportPath --baseline $baselinePath
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
            throw "skillspector scan crashed (exit code $LASTEXITCODE); see $reportPath"
        }
        & $script:pythonExe tools\check_skillspector_report.py $reportPath
        $reportCheckExit = $LASTEXITCODE
        if ($reportCheckExit -eq 1) {
            throw ("SkillSpector found new, un-baselined finding(s). Review " +
                $reportPath + " and either fix the content or add a reviewed exact " +
                "fingerprint with a specific reason -- do not rubber-stamp real findings.")
        }
        if ($reportCheckExit -ne 0) {
            throw ("SkillSpector did not fully account for every applicable analyzer; " +
                "the security gate fails closed. Review " + $reportPath)
        }
        Write-Host "SkillSpector self-scan: no new findings."
    } finally {
        Remove-Item -Recurse -Force -LiteralPath $stageDir -ErrorAction SilentlyContinue
        $env:SKILLSPECTOR_MAX_STATIC_SECONDS = $previousStaticBudget
        $env:SKILLSPECTOR_MAX_WORKFLOW_SECONDS = $previousWorkflowBudget
        $env:PYTHONHASHSEED = $previousPythonHashSeed
    }
}

Invoke-SkillSpectorSelfScan -RepoRoot $repoRoot

Write-Host "WINDOWS DEV CHECK GREEN"
