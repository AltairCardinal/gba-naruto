# Motion/Effect 参数表玩家可见闭环（2026-08-09）

## 结论

历史目录 `sequel/content/palettes/bank.json` 并不是调色板，而是
`0x0853EE98` 的 15×10-byte motion/effect 参数表。现已用自然 Group 3
路径完成 record 0 `y_offset` 的 probe-free production-ROM A/B，bank 从
`code_verified` 升为 `runtime_verified`。

证据产物：`artifacts/motion-effect-parameter-pixel-ab-v1/`。

## 可复现路径

- 输入：`scenario-49-battle-14-tool67-expiry-ready.ss9`，零按键；快照内 C3
  延迟对象自然到期并创建 Group 3 / sequence 3。
- baseline：原始 ROM；candidate：仅把 ROM `0x53EE9C`（record 0
  `y_offset`）从 `0x0000` 改为 `0x0020`。
- consumer：sequence 3 tick `0x08080764` 按 index×10 读取表项，并调用
  `0x08080218` 创建子对象。
- 两次 mGBA 均经 heavy guard，峰值 owned-tree RSS 为 74.47 / 75.00 MiB，
  `pgid_clean=true`，没有崩溃、监听端口或进程残留。

## 差异归因

- renderer / submit：只差 task pool `0x1D8E` 与 shadow OAM `0x00`。
- ack：在上述两处之外，只增加 hardware OAM `0x00`。
- task slot 126 的 `+0x06`：`64→96`；OAM 0 Y：`80→112`，均严格为
  `+32`。
- active count/pointers、runtime offsets、submission、VRAM、PRAM、IO
  在 A/B 间完全相同。
- 从两份 ack savestate 独立重放 Mode 0，得到 286 个最终像素变化，包围盒
  `(54,88)–(72,107)`。阶段截图本身发生在同一帧提交前，因此 PNG 相同不是
  失败；最终可见性以 ack 状态的硬件 OAM + GPU 内存重放为准。

## 边界

该证据证明自然玩法中 record 0 `y_offset` 的读取、子对象坐标传播、OAM 提交
和最终像素影响。它不声称 15 条记录逐条运行，也不声称另外两个 consumer
路线均已观察，更不替代实体 GBA 验证。

## 模型与脚本分配

- `gpt-5.6-terra` 只读审计先筛选已有快照和最短路线；Codex 本体用 ROM、
  disassembly、运行时产物独立复核后选择自然 Group 3。
- build/run/export/verify 为数据合同驱动脚本；mGBA 固定两次，无盲重试。
- MiniMax-M2.7-highspeed sidecar 尝试在网络读取阶段超时，没有采用其输出，
  也没有因此暂停关键路径。
