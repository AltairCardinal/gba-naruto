#!/usr/bin/env pwsh
# patch-overlay-host-link.ps1 — 给 gbarecomp 框架打补丁：让 overlay 编译时链接宿主 exe
#
# 用法：
#   .\patch-overlay-host-link.ps1 -FrameworkRoot C:\path\to\gbarecomp-src
#
# ── 为什么需要 ──────────────────────────────────────────────────────────
#
# Stage-2 自愈层把「被桥接的函数」现场编译成 DLL 再加载进宿主进程。
# 框架的 src/recompile/emit_function.cpp 给「带函数内续执行点」的函数生成一段
# alias 路由前导码，其中引用宿主全局 g_runtime_resume_pc：
#
#     if (g_runtime_resume_pc) {
#         uint32_t _resume = g_runtime_resume_pc; g_runtime_resume_pc = 0u;
#         switch (_resume) { case 0x...: goto L_...; }
#     }
#
# 静态语料能编过是因为 src/armv4t/runtime_arm.h 声明了它；
# 但 overlay 走的是另一套 shim（src/runtime/overlay_runtime_arm.h），它没有这份声明。
# 就算补上声明，Windows PE 还有第二道墙：overlay 是 DLL，要访问宿主进程里的符号
# 只能走**导入表**，而导入表需要 (模块名, 符号名)。
#
# tcc 的三种失败信息把边界划得很清楚（实测）：
#
#   声明情况                      命令行带宿主 exe      结果
#   ─────────────────────────     ──────────────────     ──────────────────────────────
#   无声明                        否                    'g_runtime_resume_pc' undeclared
#   有声明（无 dllimport）          否                    undefined symbol 'g_runtime_resume_pc'
#   有声明（无 dllimport）          是                    undefined symbol 'g_runtime_resume_pc',
#                                                            missing __declspec(dllimport)?
#   有声明（__declspec(dllimport)） 是                    ✔ 链接成功
#
#   链接成功后 dumpbin /imports 会看到：
#       <宿主 exe>
#                    0 g_runtime_resume_pc
#
# 本脚本只做**三件套里的第三件**：把宿主 exe 路径加进 overlay 的编译命令行
# （tcc 与 gcc 两条都加）。另外两件由你自己的工程承担：
#
#   1. shim 的声明要带 __declspec(dllimport)
#      → 打补丁在**暂存副本** <exe>/overlay_toolchain/include/overlay_runtime_arm.h 上
#        （框架本来就提供摊平机制 tools/fetch_tcc.ps1，运行时在
#         GBARECOMP_HEAL_BACKEND=auto-no-gcc 下用这份副本）
#   2. 宿主 exe 要导出该符号
#      → CMakeLists.txt 里 target_link_options(<exe> PRIVATE /EXPORT:g_runtime_resume_pc)
#
# ── 为什么要打在框架上而不是改框架仓库 ──────────────────────────────────
#
# gbarecomp-src 是第三方检出（mstan/gbarecomp）。直接改它的源码会在下次
# 重新 clone 时丢失，也会让本地产物与上游状态不一致。本脚本把补丁逻辑
# 收在**你的工程里**，由构建脚本每次 clone 后调用：
#   * 对上游零侵入（改动只在本地检出里）
#   * 幂等：已打过补丁直接跳过
#   * 锚点对不上就**抛错**，不会静默跳过（上游改了结构时要人来判断）
#   * 框架的 runtime 库是在你的工程里通过 add_subdirectory 编译的，
#     所以补丁应用后只需重新构建你的工程，框架工具本身不用重建。
#
# ⚠ 本文件必须存为 **UTF-8 with BOM**（PowerShell 5.1 的老规矩）。

param(
    [Parameter(Mandatory = $true)]
    [string]$FrameworkRoot
)

$ErrorActionPreference = 'Stop'

$src = Join-Path $FrameworkRoot 'src\runtime\overlay_compile.cpp'
if (-not (Test-Path -LiteralPath $src)) {
    throw "找不到框架源码：$src（-FrameworkRoot 指错了？）"
}

$text = [System.IO.File]::ReadAllText($src)

if ($text -match '\[gba-static-recomp patch\]') {
    Write-Host '    overlay 补丁已存在，跳过'
    return
}

# ── 补丁 1：在 overlay_include_flags() 之后算出宿主 exe 路径 ──────────────
$pat1 = '(?m)^(\s*)const std::string inc = overlay_include_flags\(\);\r?$'
$rep1 = @'
$1const std::string inc = overlay_include_flags();
$1// [gba-static-recomp patch] Link the overlay against the host executable.
$1// Windows PE gives a DLL no other way to reach a symbol owned by the
$1// process that loads it: the import table needs (module, symbol).
$1// Without the host exe on the command line tcc fails with
$1// "undefined symbol 'g_runtime_resume_pc'"; with it but without a
$1// __declspec(dllimport) declaration it fails with
$1// "missing __declspec(dllimport)?".
$1std::string host_exe;
$1#ifdef _WIN32
$1{
$1    char hbuf[MAX_PATH];
$1    DWORD hn = GetModuleFileNameA(nullptr, hbuf, sizeof(hbuf));
$1    if (hn > 0 && hn < sizeof(hbuf)) host_exe = hbuf;
$1}
$1#endif
$1const std::string host_arg =
$1    host_exe.empty() ? std::string() : (" \"" + host_exe + "\"");
'@
$new = [regex]::Replace($text, $pat1, $rep1)
if ($new -eq $text) { throw '补丁锚点 1 未找到：overlay_include_flags() 附近结构可能已变，请人工核对。' }
$text = $new

# ── 补丁 2：tcc 命令行追加宿主 exe ─────────────────────────────────────
# 结尾必须带 \r?$：多行模式下 $ 只在 \n 前成立，CRLF 源码里 \r 会挡在中间。
$pat2 = '(?m)^(\s*)" \\"" \+ cpath\.generic_string\(\) \+ "\\"";\r?$'
$rep2 = '$1" \"" + cpath.generic_string() + "\"" + host_arg;'
$new = [regex]::Replace($text, $pat2, $rep2)
if ($new -eq $text) { throw '补丁锚点 2 未找到：tcc 命令行可能已变，请人工核对。' }
$text = $new

# ── 补丁 3：gcc 命令行追加宿主 exe ─────────────────────────────────────
$pat3 = '(?m)^(\s*)plat;\r?$'
$rep3 = '$1plat + host_arg;'
$new = [regex]::Replace($text, $pat3, $rep3)
if ($new -eq $text) { throw '补丁锚点 3 未找到：gcc 命令行可能已变，请人工核对。' }
$text = $new

[System.IO.File]::WriteAllText($src, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Host '    patched gbarecomp/src/runtime/overlay_compile.cpp: overlay now links against the host exe'
