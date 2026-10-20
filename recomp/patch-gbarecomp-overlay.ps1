<#
.SYNOPSIS
    给 gbarecomp 框架的 overlay_compile.cpp 打一个补丁，让 Stage-2 自愈层
    能把「被桥接的函数」编译成 DLL 并从宿主进程导入符号。

.DESCRIPTION
    为什么需要这个补丁（上游缺陷，非本工程引入）：

      框架的 src/recompile/emit_function.cpp 给「带函数内续执行点」的函数生成
      一段 alias 路由前导码，其中引用宿主全局 g_runtime_resume_pc：

          if (g_runtime_resume_pc) {
              uint32_t _resume = g_runtime_resume_pc; g_runtime_resume_pc = 0u;
              switch (_resume) { case 0x...: goto L_...; }
          }

      静态语料能编过，是因为 src/armv4t/runtime_arm.h 声明了它。
      但 overlay 走的是另一套 shim（src/runtime/overlay_runtime_arm.h），
      它没有这份声明，于是 tcc 报 "g_runtime_resume_pc undeclared"。

      就算把声明补上，Windows PE 还有第二道墙：
      overlay 是 DLL，要访问宿主进程里的符号，必须走导入表；
      而导入表需要 (模块名, 符号名)。tcc 的两种失败信息把边界划得很清楚：

        · 只给声明，不给宿主 exe
            undefined symbol 'g_runtime_resume_pc'
        · 给了宿主 exe，但声明没有 __declspec(dllimport)
            undefined symbol 'g_runtime_resume_pc', missing __declspec(dllimport)?
        · 两者都给
            链接成功；dumpbin /imports 显示
              <宿主 exe>
                                  0 g_runtime_resume_pc

      框架的 tcc 命令行原本既不带宿主 exe，shim 也没有 dllimport 声明，
      所以 Stage-2 在 Windows 上是断的。gcc 分支同理。

    本补丁做一件事：把宿主 exe 路径加进 overlay 的编译命令行（tcc 与 gcc 两条都加）。
    另外两件事由本仓库自己承担，不动框架：
      · shim 的 dllimport 声明  -> recomp/build.ps1 在暂存副本上打
      · 宿主 exe 导出该符号    -> recomp/CMakeLists.txt 的 /EXPORT:g_runtime_resume_pc

    本脚本幂等：已打过补丁则直接跳过。
    匹配用正则（行尾无关），所以对 LF / CRLF 两种源码都适用。

.PARAMETER FrameworkRoot
    gbarecomp 框架检出根目录（含 src/runtime/overlay_compile.cpp）。

.EXAMPLE
    .\patch-gbarecomp-overlay.ps1 -FrameworkRoot ..\build\gbarecomp-src
#>
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

if ($text -match '\[naruto-recomp patch\]') {
    Write-Host '    overlay 补丁已存在，跳过'
    return
}

# ── 补丁 1：在 overlay_include_flags() 之后算出宿主 exe 路径 ──────────────
$pat1 = '(?m)^(\s*)const std::string inc = overlay_include_flags\(\);\r?$'
$rep1 = @'
$1const std::string inc = overlay_include_flags();
$1// [naruto-recomp patch] Link the overlay against the host executable.
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
