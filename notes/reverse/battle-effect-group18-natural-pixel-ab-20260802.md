# Group 18 自然到期 production 像素 A/B（2026-08-02）

## 结论

Group 18 / sequence 7 已从原 ROM 自然创建的忍具 67 战场对象，闭合到修改 ROM 的
production relocation 最终单像素 A/B。该路线不含 selector/spawn 探针：baseline 与
candidate 都从同一个 type-1 C3 对象、剩余两回合的验收快照开始，重放完全相同的 17
个显式输入，直至原生 zero-event expiry 路径创建 Group 18 task。

production 自然最终像素覆盖由 8/18 提升到 **9/18（50%）**。

## 因果修正

旧尝试从 `expiry-ready.ss9` 开始。该状态已存在 Group 18 task，且 VRAM 已由基准 ROM
加载；savestate 恢复会覆盖 candidate ROM 启动时的 VRAM，因此候选资源指针不会被重新
读取。该路径只能观察既有 task，不能证明修改资源被生产代码消费。

最终路径改用：

- `object-created.ss9`：SHA-256
  `603616525d7cd55bef9460ff5e7bc25dc7defbd9fe4cdfc29b281c3864a2785b`；
- 唯一 slot 3 / state 1 / `(13,6)` / action `C3` / remaining turns 2；
- 此时活动 Group 18 task 数为 0；
- checkpoint 由
  `artifacts/battle-effect-group18-natural-checkpoint-v1/` 的独立 verifier 验收。

固定输入序列为：

```text
A:18:20, Up:378:380, A:450:452, B:878:880,
A:1238:1240, A:1838:1840, Up:1910:1912, A:1982:1984,
A:2054:2056, A:2438:2440, A:2540:2542, A:2938:2940,
Up:3010:3012, A:3082:3084, A:3154:3156, A:3320:3322,
A:3440:3442
```

frame 4519/4519/4520 捕获 renderer→submit→ack；pending 严格为 `0→1→0`，task
slot 114 的 definition/animation 为 `0x0834819C/0x083481DC`。父相位成果位于
`artifacts/battle-effect-frame-phase-group18-natural-sequence-v1/`。

## 修改与运行时结果

- 只重定向 Group 18 graphics pair 指针 `0x5991AC` 到 `0x08B40000`；
- baseline/candidate 使用相同 2,002-byte LZ77 拓扑；
- candidate 只把解压 graphics offset `0xCA` 从 `0x44` 改为 `0x41`；
- OAM entry 6 为 `0x003A/0x80B0/0xCB00`，OBJ tile base 768、palette 12；
- 六个完整内存域中 EWRAM/IWRAM/IO/PRAM/OAM 完全相同；
- VRAM 仅 `0x060160CA` 一字节不同；
- 离线 Mode-0 合成仅屏幕 `(196,68)` 一个像素从
  `[181,181,181]` 变为 `[231,231,231]`；
- baseline/candidate 最终签发运行的峰值 tree RSS 分别为
  79.5/80.11328125 MiB，均为
  completed、非 degraded、无 PGID/listener 残留。

最终成果位于 `artifacts/battle-effect-group18-natural-pixel-ab-v1/`。独立 verifier
不导入 builder/exporter，会从 raw tar 重建 LZ77、两份 16 MiB ROM、三相 task/OAM、
输入序列、六内存域和最终像素，并拒绝重签后的输入序列或覆盖率篡改。

## 边界

本成果只签发 Group 18 的一条自然 zero-event expiry 路线、一个 frame/component/pixel
修改。它不签发 sequence 18 的所有自然生产者、完整动画、blend/window/audio、全部
战场对象分支或实体 GBA/flashcart。原始 mGBA capture PNG 在断点时机可能相同，最终
像素结论来自 ack savestate 的独立 Mode-0 重建。
