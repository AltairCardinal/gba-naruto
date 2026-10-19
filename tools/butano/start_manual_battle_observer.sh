#!/bin/sh
set -eu

fail()
{
  printf '启动失败：%s\n' "$1" >&2
  exit 1
}

check_only=0
case "${1:-}" in
  --check)
    check_only=1
    shift
    ;;
  "")
    ;;
  *)
    fail "未知参数：$1"
    ;;
esac
test "$#" -eq 0 || fail "参数过多"

script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
repo_dir=$(CDPATH= cd "$script_dir/../.." && pwd -P)
run_id=$(date +%Y%m%d-%H%M%S)
run_dir="$repo_dir/artifacts/butano-battle-manual-observer-$run_id"
latest_file="$repo_dir/artifacts/manual-battle-observer-latest.txt"
elf_path="$repo_dir/butano-sequel/butano-sequel.elf"
source_rom_path="$repo_dir/butano-sequel/butano-sequel.gba"
run_rom_path="$run_dir/konoha-battle-manual-observer.gba"
run_save_path="$run_dir/konoha-battle-manual-observer.sav"
reset_save="$repo_dir/artifacts/butano-battle-manual-acceptance-20260728-01/reset-scenario49-generation8.sav"
mgba_path="$repo_dir/build/signed-tooling/mGBA.app/Contents/MacOS/mGBA"
observer_script="$repo_dir/tools/butano/mgba_manual_battle_observer.lua"

test -f "$elf_path" || fail "找不到当前 ELF：$elf_path"
test -f "$source_rom_path" ||
  fail "找不到当前构建的 ROM：$source_rom_path"
test -f "$reset_save" || fail "找不到场景 49 重置存档：$reset_save"
test -x "$mgba_path" || fail "找不到可执行的 mGBA：$mgba_path"
test -f "$observer_script" || fail "找不到观察器脚本：$observer_script"
command -v nm >/dev/null 2>&1 || fail "系统中找不到 nm"
command -v awk >/dev/null 2>&1 || fail "系统中找不到 awk"
command -v python3 >/dev/null 2>&1 || fail "系统中找不到 python3"

battle_address=$(nm -n "$elf_path" | awk '$3 == "konoha_battle_runtime_telemetry" { print "0x" $1; exit }')
campaign_address=$(nm -n "$elf_path" | awk '$3 == "konoha_battle_campaign_runtime_telemetry" { print "0x" $1; exit }')
assert_address=$(nm -n "$elf_path" | awk '$3 == "_ZN3_bn6assert4showEPKcS2_S2_iRKN2bn12istring_baseE" { print "0x" $1; exit }')
test -n "$battle_address" || fail "当前 ELF 缺少战斗遥测符号"
test -n "$campaign_address" || fail "当前 ELF 缺少战役遥测符号"
test -n "$assert_address" || fail "当前 ELF 缺少 Butano 断言符号"

if test "$check_only" -eq 1; then
  printf '启动器检查通过。\n'
  printf '战斗遥测地址：%s\n' "$battle_address"
  printf '战役遥测地址：%s\n' "$campaign_address"
  printf 'Butano 断言地址：%s\n' "$assert_address"
  exit 0
fi

mkdir -p "$run_dir" || fail "无法创建诊断目录：$run_dir"
cp "$source_rom_path" "$run_rom_path" ||
  fail "无法复制当前构建的 ROM"
cp "$reset_save" "$run_save_path" ||
  fail "无法恢复场景 49 重置存档"
printf '%s\n' "$run_dir" > "$latest_file" ||
  fail "无法写入最新诊断目录指针"

printf '诊断目录：%s\n' "$run_dir"
printf '请在 mGBA 中人工复现；卡住后等待至少 5 秒，再关闭 mGBA。\n'

set +e
python3 "$repo_dir/tools/run_guarded.py" \
  --summary "$run_dir/guard.json" \
  --lock-file "$repo_dir/build/resource-guard/heavy.lock" \
  --cwd "$repo_dir" \
  --min-available-mib 1024 \
  --max-tree-rss-mib 1024 \
  --wall-timeout-s 1800 \
  --idle-timeout-s 1800 \
  --mgba-crash-report-dir /Users/altair/Library/Logs/DiagnosticReports \
  --mgba-crash-latch "$repo_dir/build/resource-guard/mgba-crash-latch.json" \
  --mgba-crash-baseline "$repo_dir/build/resource-guard/mgba-crash-baseline.json" \
  -- \
  /usr/bin/env \
  MGBA_MANUAL_BATTLE_OBSERVER_OUTPUT_DIR="$run_dir" \
  MGBA_MANUAL_BATTLE_OBSERVER_BATTLE_TELEMETRY_ADDRESS="$battle_address" \
  MGBA_MANUAL_BATTLE_OBSERVER_CAMPAIGN_TELEMETRY_ADDRESS="$campaign_address" \
  MGBA_MANUAL_BATTLE_OBSERVER_ASSERT_ADDRESS="$assert_address" \
  "$mgba_path" \
  --script "$observer_script" \
  "$run_rom_path"
launcher_exit_code=$?
set -e

printf 'mGBA 已关闭，日志保存在：%s\n' "$run_dir"
exit "$launcher_exit_code"
