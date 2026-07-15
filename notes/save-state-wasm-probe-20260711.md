# Save-state WASM SRAM probe（2026-07-11）

## 目标与方法

在现有可重复的标题→新游戏→首战 WASM 路线中，于导航前后读取 save-state bank
记录的七个唯一 SRAM 目标，每条读取 20 字节，并按 `~sum(first19) & 0xFF`
检查第 20 字节。

探针更新：

- `play/_scripts/runtime-formation-probe-lib.js`：新增 checksum、20 字节记录解析和
  before/after 比较；
- `play/_scripts/runtime-formation-probe.js`：读取 `0x0E000000 + offset`；
- `play/_scripts/runtime-formation-probe.test.js`：新增两项纯函数回归测试；当前
  Node 测试 21/21。

读取偏移：`0x001C, 0x0028, 0x002C, 0x0214, 0x0590, 0x1290, 0x17D8`。

## 结果

导航成功到首战：battle ID 40、slot 1 character ID 1、坐标 `(4,4)`，formation
唯一匹配 group 40 / variant 0。七条 SRAM 记录 before/after 均为 `FF×20`：

- `changed=false`；
- `erased=true`；
- 没有有效 checksum；
- 因此新游戏初始化和进入首战不会自动触发这七条存档写入。

Artifact：

- result SHA-256：`46d296b7492817177caa3802b5603c419735e134e80419aa3116e71ecc433c83`
- screenshot SHA-256：`91467ba071911066c9b099bcee077066e5034003c6cc685d5ac7c0040b0a44a6`

临时原始文件：`/private/tmp/save-state-runtime-result.json`、
`/private/tmp/save-state-runtime.png`。

## 判定

这是有约束力的负结果，不是 save-state runtime pass。它排除了“沿现有首战路线
自动保存”的低成本假设。save-state 保持 code 证据级别。

## 下一步重要入口

1. 静态追踪 `0x08068684` 的上游调用者，确定显式保存菜单/状态机入口；
2. 扩展 WASM 导航执行该菜单动作，同时保留本次 before/after SRAM 采集；
3. 或使用 mGBA debugger 在 `0x08068684` 设置断点，从有效保存动作记录 PC/LR、
   EWRAM 源和 SRAM 目标；
4. pass 条件：至少一条非擦除记录发生变化，第 20 字节 checksum 有效，且目标偏移
   与 bank 表项一致。

## 强制调用诊断补充

静态反向调用确认：

- `0x080689A4` 是整档保存包装器，按 mode 0 调用 groups 3–9；
- 它只有一个上游调用点：`0x08074F2C`；
- 对应整档加载包装器 `0x08068AF0` 只有一个调用点 `0x080752DA`。

`tools/build_save_state_runtime_probe.py` 在候选零区 `0x09E700` 写入诊断 stub，
将 12 个 `BL 0x0806D964` caller 重定向为：保留寄存器/原返回值、执行原成长函数、
调用 `0x080689A4`、把 marker/return 写到 `0x0203FFF0`，再恢复原返回值。

最终样本：

- diagnostic ROM SHA-256：
  `2eaceb1020b1063f72851adc0482adf18629b719a27135ffcb8d7ded319a592d`；
- result SHA-256：
  `022cdd50a18ff4a65820d40f4ed9b5e923145e4ba01eb0e0babd161dd506dc85`；
- scratch：`a500`，即 hook 确实命中、整档保存包装器返回 0；
- formation、模板、地图仍正常到达首战；
- 七条 SRAM 记录仍为擦除态。

解释：不能在任意已初始化战斗逻辑点裸调 `0x080689A4` 并期待成功。真实保存 UI
在 `0x08074F2C` 前执行额外状态/缓冲准备；后续动态验证必须复现该流程，不能把
强制调用失败误记为 SRAM 不可写或表身份错误。
