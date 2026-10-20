# build-recomp.ps1 — GBA 静态重编译端到端流水线（模板）
#
# 复制到你的 game repo 后改参数即可。两个必填参数：ROM 与 BIOS。
#
#   .\build-recomp.ps1 -Rom C:\roms\game.gba -Bios C:\bios\gba_bios.bin -Frames 20000
#
# 前置：
#   * Visual Studio 2022 BuildTools（C++ 桌面开发）+ Windows SDK
#   * SDL2 开发库（可选；缺了只能无窗口跑）
#   * 框架源码 build\gbarecomp-src（见 references/build-setup.md）
#   * 重编译配置 config\<game>.toml、运行时配置 game.toml
#   * 本目录下的 scripts\patch-overlay-host-link.ps1（修 Stage-2 自愈层，见 §6b）
#
# ⚠ 本文件必须存为 **UTF-8 with BOM**：
#   PowerShell 5.1 读无 BOM 的 .ps1 会按 ANSI(GBK) 解码，中文注释的乱码会吃掉引号 → ParserError。
#   如果用工具重写本文件，记得把 BOM 加回来。

param(
    [Parameter(Mandatory = $true)][string]$Rom,
    [Parameter(Mandatory = $true)][string]$Bios,
    [string]$Config   = "$PSScriptRoot\config\game.toml",
    [string]$GameToml = "$PSScriptRoot\game.toml",
    [string]$Work     = "$PSScriptRoot\..\build",
    [string]$Sdl2     = "$PSScriptRoot\..\build\sdl2\SDL2-2.30.9",
    [int]   $Frames   = 20000,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# ── 原生命令封装 ─────────────────────────────────────────────────────
# PowerShell 5.1 下 $ErrorActionPreference='Stop' 时，原生命令只要往 stderr 写任何一行
# （哪怕只是 warning）就会变成终止性错误。框架工具会把
#   "[finder] ... budget exhausted" 这类 warning 写进 stderr（退出码仍是 0，产物正常），
# 于是脚本会误判失败而中断。**只看 $LASTEXITCODE 判断成败。**
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$What = '',
        [switch]$AllowFailure,
        [string]$LogPath = ''
    )
    if ($What) { Write-Host "==> $What" }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0
    try {
        $output = & $FilePath @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    $text = ''
    foreach ($line in @($output)) {
        if ($null -eq $line) { continue }
        if ($line -is [System.Management.Automation.ErrorRecord]) {
            $s = $line.ToString()
        } else {
            $s = [string]$line
        }
        Write-Host ('    ' + $s)
        $text += $s + "`r`n"
    }
    if ($LogPath) {
        # UTF-8 无 BOM：日志要能被 node 脚本按 utf8 直接读。
        [System.IO.File]::WriteAllText($LogPath, $text, (New-Object System.Text.UTF8Encoding($false)))
    }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "命令失败（exit=$code）：$FilePath $($Arguments -join ' ')"
    }
    return $code
}

# ── 定位工具 ─────────────────────────────────────────────────────────
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$cmake = & $vswhere -latest -products * -find 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe' |
         Select-Object -First 1
if (-not $cmake) { throw '找不到 Visual Studio 自带的 CMake，请安装 VS2022 BuildTools 的 C++ 桌面开发。' }

$Framework = Join-Path $Work 'gbarecomp-src'
$BuildDir  = Join-Path $Work 'recomp-build'
$ExeDir    = Join-Path $BuildDir 'Release'
$RunDir    = Join-Path $Work 'recomp-run'
$GenDir    = Join-Path $Work 'recomp-generated'
$Recomp    = "$Framework\build-vs\Release\gba_recompile.exe"

# ── 1. 框架 ──────────────────────────────────────────────────────────
if (-not (Test-Path $Framework)) {
    Write-Host '==> 克隆框架'
    Invoke-Native -FilePath 'git' -Arguments @('clone','--depth','1','https://github.com/mstan/gbarecomp.git',$Framework) | Out-Null
    Invoke-Native -FilePath 'git' -Arguments @('-C',$Framework,'submodule','update','--init','--depth','1','--recursive') | Out-Null
}
if (-not (Test-Path $Recomp)) {
    Write-Host '==> 编译框架工具 gba_recompile / gba_scan'
    Invoke-Native -FilePath $cmake -Arguments @('-S',$Framework,'-B',"$Framework\build-vs",'-A','x64') | Out-Null
    Invoke-Native -FilePath $cmake -Arguments @('--build',"$Framework\build-vs",'--config','Release','--target','gba_recompile','gba_scan','--parallel','16') | Out-Null
}

# ── 1b. 给框架打补丁（Stage-2 自愈层的前提）────────────────────────────
# 框架原版的 overlay 编译命令行不带宿主 exe → tcc 链接出来的 DLL 解析不到
# 宿主符号 → 自愈层整条路断掉。补丁脚本幂等；锚点对不上会抛错。
# 框架的 runtime 库是在**本工程**里通过 add_subdirectory 编译的，
# 所以补丁应用后只需重新构建本工程，框架工具本身不用重建。
$patcher = Join-Path $PSScriptRoot 'scripts\patch-overlay-host-link.ps1'
if (Test-Path -LiteralPath $patcher) {
    Write-Host '==> 应用框架补丁（overlay 链接宿主 exe）'
    & $patcher -FrameworkRoot $Framework
}

# ── 2. 探测 ROM（拿入口与存档芯片）────────────────────────────────────
Write-Host '==> 探测 ROM'
Invoke-Native -FilePath "$Framework\build-vs\Release\gba_scan.exe" -Arguments @($Rom) | Out-Null

# ── 3. 静态重编译 BIOS（LLE）──────────────────────────────────────────
# 必须做：只用 HLE BIOS 时，BIOS 的 IRQ 向量 0x18 走解释器，
# 游戏等不到 iret → 死循环 → 全白屏。
if (-not (Test-Path $Bios)) { throw "找不到 BIOS：$Bios" }
Copy-Item -LiteralPath $Bios -Destination "$Framework\bios\gba_bios.bin" -Force
Invoke-Native -FilePath $Recomp -What '静态重编译 BIOS（LLE）' -Arguments @(
    '--bios', "$Framework\bios\gba_bios.bin",
    '--config', "$Framework\bios\gba_bios.toml",
    '--out', "$Framework\src\runtime\generated_bios") | Out-Null

# ── 4. 静态重编译卡带 ROM ─────────────────────────────────────────────
if (-not (Test-Path $Rom))   { throw "找不到 ROM：$Rom" }
if (-not (Test-Path $Config)) { throw "找不到重编译配置：$Config" }
Invoke-Native -FilePath $Recomp -What '静态重编译卡带 ROM' -Arguments @(
    '--rom', $Rom, '--config', $Config, '--out', $GenDir) | Out-Null

# ── 5. 编译游戏可执行文件 ─────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Host '==> CMake 配置 + 编译'
    $cmakeArgs = @('-S', $PSScriptRoot, '-B', $BuildDir, '-A', 'x64',
                   "-DGBARECOMP_ROOT=$($Framework -replace '\\','/')",
                   "-DGENERATED_DIR=$($GenDir -replace '\\','/')")
    if (Test-Path $Sdl2) {
        $cmakeArgs += "-DSDL2_INCLUDE_DIR=$(("$Sdl2\include") -replace '\\','/')"
        $cmakeArgs += "-DSDL2_LIBRARY=$(("$Sdl2\lib\x64\SDL2.lib") -replace '\\','/')"
    }
    Invoke-Native -FilePath $cmake -Arguments $cmakeArgs | Out-Null
    Invoke-Native -FilePath $cmake -Arguments @('--build',$BuildDir,'--config','Release','--parallel','16') | Out-Null
    if (Test-Path "$Sdl2\lib\x64\SDL2.dll") {
        Copy-Item -LiteralPath "$Sdl2\lib\x64\SDL2.dll" -Destination "$ExeDir\SDL2.dll" -Force
    }
}

# ── 6. 暂存自愈编译器（TCC）与子模块目录结构 ───────────────────────────
Write-Host '==> 暂存 TCC（自愈重编译编译器）'
& "$Framework\tools\fetch_tcc.ps1" -Toolchain "$ExeDir\overlay_toolchain"
# main 分支的 runtime_arm_types.h 用 ../../external/arm-recomp-core/... 相对引用，
# 暂存目录必须还原这个结构，否则 tcc 报 "include file not found"。
$arc = "$ExeDir\external\arm-recomp-core\profiles\armv4t_gba"
New-Item -ItemType Directory -Force -Path $arc | Out-Null
Copy-Item -LiteralPath "$Framework\external\arm-recomp-core\profiles\armv4t_gba\runtime_arm_types.h" `
          -Destination "$arc\runtime_arm_types.h" -Force

# ── 6b. 给暂存的 overlay shim 补上宿主符号声明 ─────────────────────────
#
# 打补丁的位置是**暂存副本**（<exe>/overlay_toolchain/include/），不是框架源码——
# 对上游零侵入、可随每次构建重新生成、且幂等。
#
# 声明必须带 __declspec(dllimport)：overlay 是 DLL，访问宿主符号只能走导入表，
# 而导入表需要 (模块名, 符号名)。三件套各自的归属：
#   · 声明（本步）        → 暂存副本上的补丁
#   · 宿主 exe 导出符号   → 你的 CMakeLists.txt: /EXPORT:g_runtime_resume_pc
#   · 命令行带宿主 exe    → scripts/patch-overlay-host-link.ps1（第 1b 步）
$shim = "$ExeDir\overlay_toolchain\include\overlay_runtime_arm.h"
if (Test-Path -LiteralPath $shim) {
    $shimText = Get-Content -LiteralPath $shim -Raw
    if ($shimText -notmatch 'g_runtime_resume_pc') {
        $decl = @'

// ── Host-exported resume-PC slot (patched by build-recomp.ps1) ─────────
// The emitter writes the same alias-routing prologue into the static corpus
// and into the overlay body. The static corpus gets this declaration from
// src/armv4t/runtime_arm.h, but the overlay shim does not — tcc then fails
// with "'g_runtime_resume_pc' undeclared" and the whole Stage-2 self-heal
// path is dead.
//
// __declspec(dllimport) is REQUIRED, not cosmetic: the overlay is a DLL, so
// it can only reach a host-owned symbol through the import table, and the
// import entry needs the dllimport storage class to be emitted correctly.
#ifdef _WIN32
__declspec(dllimport) extern uint32_t g_runtime_resume_pc;
#else
extern uint32_t g_runtime_resume_pc;
#endif
'@
        $anchor = 'extern const GbaOverlayCallbacks* g_ovl;'
        if ($shimText.Contains($anchor)) {
            $shimText = $shimText.Replace($anchor, $anchor + $decl)
            [System.IO.File]::WriteAllText($shim, $shimText, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host '    patched overlay shim: declared g_runtime_resume_pc (dllimport)'
        } else {
            Write-Host '    WARN: overlay shim anchor not found — skipped g_runtime_resume_pc patch'
        }
    } else {
        Write-Host '    overlay shim already declares g_runtime_resume_pc — no patch needed'
    }
} else {
    Write-Host "    WARN: overlay shim header not found: $shim"
}

# ── 7. 准备运行目录并跑起来 ───────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "$RunDir\roms","$RunDir\bios" | Out-Null
Copy-Item -LiteralPath $Rom   -Destination "$RunDir\roms\game.gba" -Force
Copy-Item -LiteralPath $Bios  -Destination "$RunDir\bios\gba_bios.bin" -Force
Copy-Item -LiteralPath $GameToml -Destination "$RunDir\game.toml" -Force

# 三个环境变量，缺一不可：
#
#  1. GBARECOMP_NO_LAUNCHER=1
#     跳过图形启动器。无窗口批处理运行时没有界面去点「开始」，留着启动器会一直等。
#
#  2. GBARECOMP_HEAL_CACHE=<独立缓存目录，按配置内容哈希分>
#     自愈层（tcc overlay）的产物缓存根。**必须指到干净目录**：
#     框架判 FULLY_STATIC 的条件是
#       fully_static = (misses == 0) && (healed == 0) && (interpreted_insns == 0)
#     而上一轮留下的 overlay 热缓存会被加载成 healed=1 —— 于是即使覆盖率真的打满，
#     日志也会报 `dispatch_misses=0` 却 `self_heal_coverage=NOT_STATIC`，
#     看起来像还有缺口，其实只是缓存残留。
#     框架的缓存子路径只按 ROM sha1 分，同一 ROM 的不同配置会共用同一批 overlay，
#     所以这里再按**配置内容哈希**分一层——否则用对照配置做实验会污染正式构建。
#
#  3. GBARECOMP_HEAL_BACKEND=auto-no-gcc
#     让运行时走「已发布形态」：用 <exe>/overlay_toolchain 里暂存的 tcc + 暂存 shim 头，
#     而不是开发机的框架源码目录。6b 的补丁落在暂存副本上，这一步是必须的。
#     正式发布形态下玩家机上本来就只有暂存副本，所以这也是生产路径。
$env:GBARECOMP_NO_LAUNCHER = '1'
$env:GBARECOMP_HEAL_BACKEND = 'auto-no-gcc'
$cfgBytes = [System.IO.File]::ReadAllBytes($Config)
$sha = [System.Security.Cryptography.SHA1]::Create()
$cfgHash = ([BitConverter]::ToString($sha.ComputeHash($cfgBytes))).Replace('-','').Substring(0,8).ToLower()
$cfgTag = [System.IO.Path]::GetFileNameWithoutExtension($Config) + '_' + $cfgHash
$env:GBARECOMP_HEAL_CACHE = "$RunDir\heal_cache_$cfgTag"
New-Item -ItemType Directory -Force -Path $env:GBARECOMP_HEAL_CACHE | Out-Null

Write-Host "==> 跑 $Frames 帧并导出 PNG"
$runLog = Join-Path $RunDir ("run_{0}.out" -f $Frames)
Push-Location $RunDir
try {
    $exe = Get-ChildItem $ExeDir -Filter '*.exe' | Select-Object -First 1
    if (-not $exe) { throw "找不到可执行文件：$ExeDir" }
    Invoke-Native -FilePath $exe.FullName -Arguments @(
        '--rom','roms/game.gba', '--bios','bios/gba_bios.bin',
        '--frames',"$Frames", '--no-window', '--dump-png',"shot_$Frames.png") `
        -LogPath $runLog | Out-Null
} finally {
    Pop-Location
}

# ── 8. 汇总指标 ─────────────────────────────────────────────────────
Write-Host ''
Write-Host '==> 指标汇总'
$summary = Join-Path $PSScriptRoot 'scripts\summarize-run-log.mjs'
if (Test-Path $summary) {
    Invoke-Native -FilePath 'node' -Arguments @($summary, $runLog) | Out-Null
}
Write-Host "产物：$RunDir\shot_$Frames.png"
Write-Host "日志：$runLog"
