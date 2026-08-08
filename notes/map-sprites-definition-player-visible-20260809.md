# map-sprites definition_ptr 玩家可见闭环（2026-08-09）

`0x0853F140` 是 43 条 definition/animation 指针对。静态链
`0x08080B08 → 0x08063494 → 0x080625A4 → 0x08062668` 已证明按 ID×8
把两指针安装到 task `+0x1C/+0x20`；本轮补上 definition 字段的最终画面闭环。

## 实验

- 输入：基础 ROM 与自然快照 `scenario-41-combat-dialogue.ss9`；零按键。
- 基线：entry 1 `definition_ptr = 0x0812F5D8`。
- 候选：只改 entry 1 为 `0x0812F7CC`（entry 37 的两 component definition）。
- 实际 ROM 差异：仅 `0x53F148..0x53F149` 两字节。
- 受控步骤：快照中自然存在的 ID 1 task 123（`0x0300588C`）已处于终止后
  inactive 状态；脚本只恢复 active bit，并把各自 ROM 表的 entry 1 definition
  物化到 task `+0x1C`。不修改 animation、tile base、VRAM 或 PRAM。
- 两个变体都命中 task 123 的 `0x0806298C` frame-select 和 `0x08063108`
  OAM-compose；候选 component pointer 为 `0x0812F7A0`。
- 等待边界后的两个完整帧再保存状态与截图。

结果：最终画面在 `(178,64)..(215,71)` 改变 213 像素；OAM 改变 15 字节，
IWRAM 差异仅为 task definition 的两个实际变化字节及对应 shadow-OAM 字节；
IO、PRAM、VRAM、EWRAM 完全相同。修复证据绑定后重跑的两次 mGBA 峰值均为
108.70 MiB，guard 均 completed/0、无残留进程。

## 证据边界

该闭环证明 entry 1 `definition_ptr` 能沿真实 frame/OAM 管线改变最终画面，因此
bank 提升为 `runtime_verified`。它是受控 task 重新激活与字段物化，不声称在本轮
自然输入中重新进入 loader，也不声称 entry 37 definition 与 entry 1 tile base
具有生产兼容性。可复验证据位于
`artifacts/map-sprites-definition-id1-pixel-ab-v1/`。

verifier 会从 `rom/base.gba` 重建两个 ROM 并核对精确两字节差分，同时绑定仓库内
Lua 的规范绝对路径/哈希与受信 mGBA 的规范绝对路径/当前文件哈希。这是当前
macOS Intel 工作机上的运行时复验条件：换机或更换 checkout 位置后，必须把仓库
与相同哈希的受信 mGBA 都放到 guard 声明的绝对路径；仅复制 artifact、源码和 ROM
不足以通过运行时工具复验。
