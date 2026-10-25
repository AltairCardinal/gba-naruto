<#
.SYNOPSIS
    Prove that every step of the S49 packaging pipeline really turns the
    pipeline red when it is broken.

.DESCRIPTION
    The pipeline has a `--selftest-break <step>` switch.  It does **not**
    weaken a check: it breaks the *input* of that step (a truncated ROM, an
    empty directory, a deliberately failing unit test, a regressed report,
    ...), so the step's own success criterion has to fire.

    This script runs the pipeline once per step with that step broken and
    records the exit code of every run.  A non-zero exit code means the
    pipeline noticed; an exit code of 0 means **the pipeline itself has a
    bug** and the step's criterion did not fire.

    The runs write into a scratch package directory, so the real package's
    receipt is never touched.  The results land in
    ``build/s49-package/evidence/selftest-break.txt`` and are rendered in
    the 1:1 report.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/s49_package/run_selftests.ps1

    # a private package directory (so a parallel stream's package is not
    # overwritten):
    powershell -NoProfile -ExecutionPolicy Bypass -File tools/s49_package/run_selftests.ps1 `
        -PackageDir 'build\s49-package-u4'
#>
param(
  # The package directory whose evidence/ folder receives the results.
  # The default keeps the historical location.
  [string]$PackageDir = 'build\s49-package'
)

$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$package = Join-Path $repo $PackageDir
$scratch = Join-Path $package 'selftest-scratch'
$evidence = Join-Path $package 'evidence'
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$log = Join-Path $evidence 'selftest-break.txt'

# step number, the step's name, the pipeline arguments that select it
$cases = @(
  @{ step = 1;  name = 'build';         args = @('--only', '1') },
  @{ step = 2;  name = 'unit-tests';    args = @('--only', '2') },
  @{ step = 3;  name = 'smoke';         args = @('--only', '3') },
  @{ step = 4;  name = 'headless';      args = @('--only', '4') },
  @{ step = 5;  name = 'judgment';      args = @('--only', '5') },
  @{ step = 6;  name = 'overlay';       args = @('--from', '5', '--to', '6') },
  @{ step = 7;  name = 'idle-frames';   args = @('--only', '7') },
  @{ step = 8;  name = 'outline-wave';  args = @('--only', '8') },
  @{ step = 9;  name = 'blackfade';     args = @('--only', '9') },
  @{ step = 10; name = 'audio';         args = @('--only', '10') },
  @{ step = 11; name = 'save-boundary'; args = @('--only', '11') }
)

'' | Out-File -FilePath $log -Encoding UTF8
$red = 0
$notRed = 0
foreach ($case in $cases) {
  $name = $case.name
  $arguments = @('tools/s49_package/run_pipeline.py') + $case.args +
               @('--selftest-break', $name, '--out', $scratch)
  $output = & python @arguments 2>&1 | Out-String
  $code = $LASTEXITCODE
  $verdict = if ($code -eq 0) { 'NOT RED (BUG)' } else { 'RED' }
  if ($code -eq 0) { $notRed++ } else { $red++ }
  Add-Content -Path $log -Encoding UTF8 -Value "=== selftest-break $name (step $($case.step)): exit=$code -> $verdict"
  Add-Content -Path $log -Encoding UTF8 -Value (($output -split "`r?`n" |
      Where-Object { $_ -match '^\s+!|^\s+\.|^--- step|^pipeline' }) -join "`n")
  Write-Output "=== selftest-break $name (step $($case.step)): exit=$code -> $verdict"
}
Add-Content -Path $log -Encoding UTF8 -Value "=== summary: $red red, $notRed not red"
Write-Output "=== summary: $red red, $notRed not red"
Write-Output "results in $log"
if ($notRed -gt 0) { exit 1 }
exit 0
