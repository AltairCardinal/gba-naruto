#!/usr/bin/env pwsh
# Build Lua 5.4 as a static library for the mGBA probe (MSVC / cl.exe).
#
# mGBA's Lua script engine (src/script/engines/lua.c) links against liblua.
# This Windows box has no Lua dev package and no admin rights, so the sources
# are compiled straight into a static lib that the probe links.
#
# Usage (from a VS x64 developer prompt, or via vcvars64):
#     pwsh -File tools/build_lua_lib.ps1
#
# Output:
#     $TOOLCHAIN\lua-$VERSION\src        -> include dir (lua.h, luaconf.h, ...)
#     $TOOLCHAIN\lua-$VERSION-build\lua54.lib
param(
    [string]$LuaVersion = '5.4.7',
    [string]$Toolchain = $(if ($env:KONOHA_TOOLCHAIN) { $env:KONOHA_TOOLCHAIN } else { 'D:\Shell\toolchain' })
)

$ErrorActionPreference = 'Stop'

$archive = Join-Path $Toolchain "lua-$LuaVersion.tar.gz"
$srcDir = Join-Path $Toolchain "lua-$LuaVersion"
$buildDir = Join-Path $Toolchain "lua-$LuaVersion-build"

if (-not (Test-Path $archive)) { throw "missing $archive" }

if (-not (Test-Path $srcDir)) {
    Write-Host '== extracting =='
    tar -xf $archive -C $Toolchain
    if ($LASTEXITCODE -ne 0) { throw "tar failed ($LASTEXITCODE)" }
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$luaSrc = Join-Path $srcDir 'src'

# The interpreter and compiler drivers are programs, not library sources.
$sources = Get-ChildItem $luaSrc -Filter '*.c' |
    Where-Object { $_.Name -notin @('lua.c', 'luac.c') } |
    Select-Object -ExpandProperty Name

Write-Host "== compiling $($sources.Count) sources =="
$objs = @()
foreach ($name in $sources) {
    $obj = Join-Path $buildDir ($name -replace '\.c$', '.obj')
    & cl.exe /nologo /c /O2 /MT /W3 "/I$buildDir" "/I$luaSrc" "/Fo$obj" (Join-Path $luaSrc $name) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "cl.exe failed on $name ($LASTEXITCODE)" }
    $objs += $obj
}

Write-Host '== archiving =='
$lib = Join-Path $buildDir 'lua54.lib'
& lib.exe /nologo "/OUT:$lib" @objs | Out-Null
if ($LASTEXITCODE -ne 0) { throw "lib.exe failed ($LASTEXITCODE)" }

Write-Host "OK  include: $luaSrc"
Write-Host "OK  library: $lib"
Write-Host "OK  objects: $($objs.Count)"
