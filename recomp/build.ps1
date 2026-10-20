# build.ps1 — 端到端构建「火影忍者：木叶战记」原生重编译移植版
#
# 流程：
#   1. 准备框架（自建 gba_recompile / gba_scan）
#   2. 静态重编译 BIOS（LLE，精确路径）—— 关键：没有它 BIOS 的 IRQ 向量
#      0x18 会落到解释器，游戏永远等不到 iret，IRQ 循环卡死
#   3. 静态重编译卡带 ROM（用 config/naruto_konoha_senki.toml）
#   4. CMake 配置 + 编译游戏可执行文件
#   5. 暂存 TCC（自愈重编译编译器）与子模块头（overlay 编译需要）
#   6. 跑 N 帧并导出 PNG
#
# 用法：
#   .\build.ps1 -Bios .\bios\gba_bios.bin -Rom ..\rom\base.gba -Frames 20000
#
# 前置：
#   * Visual Studio 2022 BuildTools（含 C++ 桌面开发、MSVC、Windows SDK）
#   * SDL2 开发库（默认取 ..\build\sdl2\SDL2-2.30.9）
#   * 玩家自己主机导出的 gba_bios.bin（16 KB，SHA-1 300c20df…d3492）
#   * 自己合法持有的卡带 ROM
#
# ⚠ 本文件必须存为 **UTF-8 with BOM**。
#   PowerShell 5.1 读无 BOM 的 .ps1 会按 ANSI(GBK) 解码，中文注释的乱码会吃掉引号，
#   直接报 ParserError（且报错行号指向不相干的位置）。

param(
    [string]$Bios     = "$PSScriptRoot\bios\gba_bios.bin",
    [string]$Rom      = "$PSScriptRoot\..\rom\base.gba",
    [string]$Work     = "$PSScriptRoot\..\build",
    [string]$Sdl2     = "$PSScriptRoot\..\build\sdl2\SDL2-2.30.9",
    [string]$Config   = "$PSScriptRoot\config\naruto_konoha_senki.toml",
    [int]   $Frames   = 20000,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# ── 原生命令封装 ─────────────────────────────────────────────────────
# 为什么需要它：PowerShell 5.1 下 $ErrorActionPreference='Stop' 时，
# 原生命令只要往 stderr 写**任何一行**（哪怕是普通提示）就会被当成终止性错误。
# gbarecomp 的工具把 "[finder] ... budget exhausted" 这类**警告**写进 stderr，
# 于是脚本会误判成失败而中断。正确做法是看 $LASTEXITCODE，而不是 stderr。
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$What = '',
        [switch]$AllowFailure,
        [string]$LogPath = ''
    )
    if ($What) { Write-Host "==> $What" }
    # 关键：调用期间把错误偏好降为 Continue。
    # PowerShell 5.1 下，$ErrorActionPreference='Stop' 时原生命令往 stderr 写任何一行
    # （哪怕只是 "[finder] ... budget exhausted" 这种**警告**）都会变成终止性错误。
    # 成功与否只看 $LASTEXITCODE。
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

# ── 工具定位 ─────────────────────────────────────────────────────────
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$cmake = & $vswhere -latest -products * -find 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe' |
         Select-Object -First 1
if (-not $cmake) { throw '找不到 Visual Studio 自带的 CMake，请安装 VS2022 BuildTools 的 C++ 桌面开发。' }

$Framework = Join-Path $Work 'gbarecomp-src'
$BuildDir  = Join-Path $Work 'naruto-recomp-build'
$ExeDir    = Join-Path $BuildDir 'Release'
$RunDir    = Join-Path $Work 'naruto-recomp-run'
$GenDir    = Join-Path $Work 'gbarecomp-out-cfg'

# ── 1. 框架 ──────────────────────────────────────────────────────────
if (-not (Test-Path $Framework)) {
    Write-Host '==> 克隆框架'
    Invoke-Native -FilePath 'git' -Arguments @('clone','--depth','1','https://github.com/mstan/gbarecomp.git',$Framework) | Out-Null
    Invoke-Native -FilePath 'git' -Arguments @('-C',$Framework,'submodule','update','--init','--depth','1','--recursive') | Out-Null
}
if (-not (Test-Path "$Framework\build-vs\Release\gba_recompile.exe")) {
    Write-Host '==> 编译框架工具 gba_recompile / gba_scan'
    Invoke-Native -FilePath $cmake -Arguments @('-S',$Framework,'-B',"$Framework\build-vs",'-A','x64') | Out-Null
    Invoke-Native -FilePath $cmake -Arguments @('--build',"$Framework\build-vs",'--config','Release','--target','gba_recompile','gba_scan','--parallel','16') | Out-Null
}

# 给框架打补丁：让 overlay 编译时链接宿主 exe（Stage-2 自愈层的前提）。
# 框架的 runtime 库是在**本工程**里通过 add_subdirectory 编译的，
# 所以补丁应用后只需要重新构建本工程，框架工具本身不用重建。
Write-Host '==> 应用框架补丁（overlay 链接宿主 exe）'
& "$PSScriptRoot\patch-gbarecomp-overlay.ps1" -FrameworkRoot $Framework
$Recomp = "$Framework\build-vs\Release\gba_recompile.exe"

# ── 2. 静态重编译 BIOS（LLE）──────────────────────────────────────────
if (-not (Test-Path $Bios)) { throw "找不到 BIOS：$Bios" }
Copy-Item -LiteralPath $Bios -Destination "$Framework\bios\gba_bios.bin" -Force
Invoke-Native -FilePath $Recomp -What '静态重编译 BIOS（LLE，770 个函数）' `
    -Arguments @('--bios',"$Framework\bios\gba_bios.bin",'--config',"$Framework\bios\gba_bios.toml",'--out',"$Framework\src\runtime\generated_bios") | Out-Null

# ── 3. 静态重编译卡带 ROM ─────────────────────────────────────────────
if (-not (Test-Path $Rom)) { throw "找不到 ROM：$Rom" }
if (-not (Test-Path $Config)) { throw "找不到重编译配置：$Config" }
Write-Host "    配置：$Config"
Invoke-Native -FilePath $Recomp -What '静态重编译卡带 ROM' `
    -Arguments @('--rom',$Rom,'--config',$Config,'--out',$GenDir) | Out-Null

# ── 4. 编译游戏可执行文件 ─────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Host '==> CMake 配置 + 编译'
    Invoke-Native -FilePath $cmake -Arguments @(
        '-S', $PSScriptRoot, '-B', $BuildDir, '-A', 'x64',
        "-DGBARECOMP_ROOT=$($Framework -replace '\\','/')",
        "-DGENERATED_DIR=$($GenDir  -replace '\\','/')",
        "-DSDL2_INCLUDE_DIR=$(("$Sdl2\include") -replace '\\','/')",
        "-DSDL2_LIBRARY=$(("$Sdl2\lib\x64\SDL2.lib") -replace '\\','/')") | Out-Null
    Invoke-Native -FilePath $cmake -Arguments @('--build',$BuildDir,'--config','Release','--parallel','16') | Out-Null
    Copy-Item -LiteralPath "$Sdl2\lib\x64\SDL2.dll" -Destination "$ExeDir\SDL2.dll" -Force
}

# ── 5. 暂存自愈编译器（TCC）与子模块头 ───────────────────────────────
Write-Host '==> 暂存 TCC（自愈重编译编译器）'
& "$Framework\tools\fetch_tcc.ps1" -Toolchain "$ExeDir\overlay_toolchain"
# main 分支的 runtime_arm_types.h 用相对路径引用子模块，暂存目录要还原这个结构，
# 否则 tcc 编译 overlay 时报 "include file not found"。
$arc = "$ExeDir\external\arm-recomp-core\profiles\armv4t_gba"
New-Item -ItemType Directory -Force -Path $arc | Out-Null
Copy-Item -LiteralPath "$Framework\external\arm-recomp-core\profiles\armv4t_gba\runtime_arm_types.h" `
          -Destination "$arc\runtime_arm_types.h" -Force

# ── 5b. 给 overlay shim 补上宿主符号声明 ──────────────────────────────
#
# 背景（上游框架缺陷，非本工程问题）：
#   框架的 src/recompile/emit_function.cpp 给「带函数内续执行点」的函数
#   生成一段 alias 路由前导码，其中引用 `g_runtime_resume_pc`。
#   静态语料能编过，是因为 src/armv4t/runtime_arm.h 声明了它；
#   但 overlay 用的 shim（src/runtime/overlay_runtime_arm.h）**没有**这份声明
#   → tcc 编译 overlay 时报：'g_runtime_resume_pc' undeclared
#   → 自愈层整条路断掉。
#
# 为什么在暂存副本上改而不是改框架：
#   build/gbarecomp-src 是第三方检出（mstan/gbarecomp），不是本仓库代码。
#   在那里打补丁会在下次重新 clone 时丢失，也会让本地产物与上游状态不一致。
#   框架本来就提供了「把 shim 头摊平到 <exe>/overlay_toolchain/include」的机制
#   （tools/fetch_tcc.ps1 干的），而运行时在 GBARECOMP_HEAL_BACKEND=auto-no-gcc
#   下会用这份暂存副本 —— 所以补丁落在**暂存副本**上，
#   对上游零侵入、可随每次构建重新生成、且对任意上游版本都能幂等应用。
#
# 声明为什么必须带 __declspec(dllimport)：
#   overlay 是 DLL，要访问宿主进程里的符号只能走**导入表**，
#   而导入表需要 (模块名, 符号名)。tcc 的两种失败信息已经把边界划清楚了：
#     · 只给声明，不带宿主 exe
#         → undefined symbol 'g_runtime_resume_pc'
#     · 带了宿主 exe，但声明没有 dllimport
#         → undefined symbol 'g_runtime_resume_pc', missing __declspec(dllimport)?
#     · 两者都给
#         → 链接成功；dumpbin /imports 显示
#              NarutoKonohaSenkiRecomp.exe
#                                     0 g_runtime_resume_pc
#   宿主 exe 导出该符号由 recomp/CMakeLists.txt 的 /EXPORT:g_runtime_resume_pc 负责；
#   宿主 exe 出现在 tcc 命令行里由 recomp/patch-gbarecomp-overlay.ps1 负责。
$shim = "$ExeDir\overlay_toolchain\include\overlay_runtime_arm.h"
if (Test-Path -LiteralPath $shim) {
    $shimText = Get-Content -LiteralPath $shim -Raw
    if ($shimText -notmatch 'g_runtime_resume_pc') {
        $decl = @'

// ── Host-exported resume-PC slot (patched by recomp/build.ps1) ──────────
// The emitter writes the same alias-routing prologue into the static corpus
// and into the overlay body. The static corpus gets this declaration from
// src/armv4t/runtime_arm.h, but the overlay shim does not — tcc then fails
// with "'g_runtime_resume_pc' undeclared" and the whole Stage-2 self-heal
// path is dead.
//
// __declspec(dllimport) is REQUIRED, not cosmetic: the overlay is a DLL, so
// it can only reach a host-owned symbol through the import table, and the
// import entry needs the dllimport storage class to be emitted correctly.
// The host exe exports the symbol (recomp/CMakeLists.txt:
// /EXPORT:g_runtime_resume_pc) and is passed to the overlay compiler
// (recomp/patch-gbarecomp-overlay.ps1).
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
        Write-Host '    overlay shim already declares g_runtime_resume_pc (upstream fixed) — no patch needed'
    }
} else {
    Write-Host "    WARN: overlay shim header not found: $shim"
}

# ── 6. 准备运行目录并跑起来 ───────────────────────────────────────────
New-Item -ItemType Directory -Force -Path "$RunDir\roms","$RunDir\bios" | Out-Null
Copy-Item -LiteralPath $Rom  -Destination "$RunDir\roms\naruto_konoha_senki_cn.gba" -Force
Copy-Item -LiteralPath $Bios -Destination "$RunDir\bios\gba_bios.bin" -Force
Copy-Item -LiteralPath "$PSScriptRoot\game.toml" -Destination "$RunDir\game.toml" -Force

# 两个测量用的环境变量，缺一不可：
#
#  1. GBARECOMP_NO_LAUNCHER=1
#     跳过图形启动器界面。无窗口批处理运行时没有交互界面去点「开始」，
#     留着启动器会一直等输入。
#
#  2. GBARECOMP_HEAL_CACHE=<运行目录下的独立缓存，且按配置文件名隔离>
#     自愈层（tcc overlay）的产物缓存根。**必须指到干净目录**：
#     框架判定 FULLY_STATIC 的条件是
#       fully_static = (misses == 0) && (healed == 0) && (interpreted_insns == 0)
#     而上一轮跑留下的热缓存会被加载成 healed=1 —— 于是即使覆盖率真的打满，
#     日志也会报 `dispatch_misses=0` 却 `self_heal_coverage=NOT_STATIC`，
#     看起来像还有缺口，其实只是缓存残留。
#     这里每次都指到运行目录下的独立缓存，保证标签反映的是**本次**构建的真相。
#     按配置文件名再分一层目录：框架的缓存子路径只按 ROM sha1 分，
#     同一 ROM 的不同配置会共用同一批 overlay —— 用对照配置做实验时
#     会把产物留给正式构建，必须隔开。
$env:GBARECOMP_NO_LAUNCHER = '1'
# 按配置**内容**哈希分目录，而不是文件名：框架的缓存子路径只按 ROM sha1 分，
# 同一 ROM 的不同配置会共用同一批 overlay —— 用对照配置做实验时会把产物
# 留给正式构建。文件名相同但内容不同的配置同样会撞车，所以取内容哈希。
$cfgBytes = [System.IO.File]::ReadAllBytes($Config)
$sha = [System.Security.Cryptography.SHA1]::Create()
$cfgHash = ([BitConverter]::ToString($sha.ComputeHash($cfgBytes))).Replace('-','').Substring(0,8).ToLower()
$cfgTag = [System.IO.Path]::GetFileNameWithoutExtension($Config) + '_' + $cfgHash
$env:GBARECOMP_HEAL_CACHE = "$RunDir\heal_cache_$cfgTag"
New-Item -ItemType Directory -Force -Path $env:GBARECOMP_HEAL_CACHE | Out-Null

#  3. GBARECOMP_HEAL_BACKEND=auto-no-gcc
#     让运行时走「已发布形态」：强制用 <exe>/overlay_toolchain 里暂存的
#     tcc + 暂存 shim 头，而不是开发机的框架源码目录。
#     这一步是必须的——5b 打的补丁落在**暂存副本**上；
#     若运行时去读框架源码里那份没补丁的 shim，补丁等于没打。
#     正式发布形态下玩家机上本来就只有暂存副本，所以这也是生产路径。
$env:GBARECOMP_HEAL_BACKEND = 'auto-no-gcc'

Write-Host "==> 跑 $Frames 帧并导出 PNG"
Push-Location $RunDir
try {
    Invoke-Native -FilePath "$ExeDir\NarutoKonohaSenkiRecomp.exe" -Arguments @(
        '--rom','roms/naruto_konoha_senki_cn.gba',
        '--bios','bios/gba_bios.bin',
        '--frames',"$Frames",
        '--no-window',
        '--dump-png',"shot_$Frames.png") `
        -LogPath (Join-Path $RunDir ("run_{0}.out" -f $Frames)) | Out-Null
} finally {
    Pop-Location
}

# 汇总指标（人可读 + 可判定）
$log = Join-Path $RunDir ("run_{0}.out" -f $Frames)
Write-Host ''
Write-Host '==> 覆盖率指标'
if (Test-Path -LiteralPath $log) {
    Get-Content -LiteralPath $log | Select-String -Pattern 'bios_backend=|self_heal_coverage=|pal_nonzero=|final_pc=|bounded_run ' |
        ForEach-Object { Write-Host ('    ' + $_.Line) }
} else {
    Write-Host '    （运行日志未落盘，跳过）'
}

Write-Host ''
Write-Host '完成。产物：'
Get-ChildItem $RunDir -Filter "shot_$Frames.png" | ForEach-Object { Write-Host ('  ' + $_.FullName) }
