# PowerShell helper (Windows-side git; the remake tree is a Windows worktree so
# WSL git cannot read it).  Dumps `git show HEAD:<path>` into the Y1 shadow
# include dir with LF + no BOM, and verifies build/head-baseline matches HEAD.
$ErrorActionPreference = 'Stop'
$repo = 'D:\Shell\Github\gba-naruto-butano'
$rel = 'butano-sequel/game/include/konoha/battle_scene_presentation_event.h'
$dst = 'D:\Github\gba-naruto\build\y1-size\head\konoha\battle_scene_presentation_event.h'
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'git'
$psi.Arguments = "-C $repo show HEAD:$rel"
$psi.RedirectStandardOutput = $true
$psi.UseShellExecute = $false
$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$p = [System.Diagnostics.Process]::Start($psi)
$txt = $p.StandardOutput.ReadToEnd()
$p.WaitForExit()
if ($p.ExitCode -ne 0) { throw "git show failed ($($p.ExitCode))" }
$txt = $txt -replace "`r`n", "`n"
[System.IO.File]::WriteAllText($dst, $txt, (New-Object System.Text.UTF8Encoding($false)))
"wrote $((Get-Item $dst).Length) bytes -> $dst"

$bl = 'D:\Github\gba-naruto\build\head-baseline\butano-sequel\game\include\konoha\battle_scene_presentation_event.h'
if (Test-Path $bl) {
    $blt = ([System.IO.File]::ReadAllText($bl) -replace "`r`n", "`n")
    if ($blt -ceq $txt) { 'MATCH: build/head-baseline == git HEAD' }
    else { 'DIFFER: build/head-baseline != git HEAD' }
}
