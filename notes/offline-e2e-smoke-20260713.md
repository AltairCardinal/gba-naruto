# 离线 build → 原生 mGBA E2E smoke（2026-07-13）

## 已闭合子门槛

`tools/run_offline_e2e.py` 将现有能力串成一个失败即非零的本机流程：

1. `tools/automated_test.py --json-output` 重建正式 ROM 并持久化 25 项检查；
2. 对比实际输出 ROM SHA-1/size 与 build report；
3. 原生 `/usr/games/mgba` 载入 tracked `actionable-move-grid.ss9`；
4. 从同一 snapshot 断言 battle ID、地图尺寸和两个关键单位坐标；
5. 把每个命令、退出码、输入 hash 和断言写入 `artifacts/e2e/`。

2026-07-13 正式报告位于 `artifacts/e2e/offline-smoke-20260713/`：

- build checks：25/25；
- ROM：`build/naruto-sequel-dev.gba`，SHA-1
  `8018d23fe80efe15f8f55c01aa8eb04f3ccb921f`，6291456 bytes；
- checkpoint SHA-256：
  `4821a3a6694d32871a23bbea6a93ba1724663cb4a3c6e5f691d4fd48a5635fac`；
- 原生 mGBA：未超时，PC `0x0806112E`；
- battle 41；map `36×44` / grid `9×22`；
- Naruto `(4,10)`；Iruka `(4,4)`。

## 工具修正

`mgba-headless-snapshot.py` 的 snapshot 模式原先直接抛出
`subprocess.TimeoutExpired`，会丢弃 mGBA 已输出的内存。现在与 probe 模式一致：
超时时保留 stdout/stderr、解析 memory dump，并显式标记 `timed_out`。同时 snapshot
接受 CLI timeout 上限。本次 E2E 通过 `--frames 1` 正常退出，没有依赖超时恢复。

## 尚未闭合的完整 E2E

本轮 runtime smoke 只闭合“正式构建 → 原生模拟器加载 → 已知战斗态 → 持久机器报告”。
后续 `tests/test_editor_build_integration.py` 已另行闭合完整 mirror DB 中 map-header
单字段编辑的隔离正式 build，但仍不包含：

- 浏览器编辑器 UI/API 修改 → 隔离 build ID → 下载 ROM；
- 玩家可见中文文本 OCR；
- 完整剧情、战斗、存档长程回归；
- 后端 build-ID API 验证读取自身产物；
- Linux 可用的中文 OCR（仓内现有 helper 是 macOS Mach-O）。

因此 P0-Step 7 只是完成“离线无 OCR runtime smoke”子项，不能宣称全面 E2E 完成。
