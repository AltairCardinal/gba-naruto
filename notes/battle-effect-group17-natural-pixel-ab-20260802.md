# Group 17 自然忍具路线与 production 像素 A/B（2026-08-02）

## 结论

Group 17 / sequence 20 已由原版忍具 37 的自然选择链闭合到精确帧事务与修改 ROM
最终像素。该成果把聚合 phase 覆盖从 `9/18` 提升到 `10/18（55.56%）`，把
production 最终像素 A/B 从 `11/18` 提升到 `12/18（66.67%）`。

## 自然入口与恢复点

- 从 `scenario-49-post-training-task-menu.ss9` 装备忍具 37；持久模板
  `0x02022FA1` 与 battle 14 单位槽均为 37。
- 最终确认页保存为
  `artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation.ss9`，
  SHA-256 为 `af37457d4cd41e180e61338fed77d6322b4aecd21386917739f2e56599708a46`。
- 同一页仅输入 `A:5:13` 后，Group 17 唯一活动 task 位于 slot 125 / `0x03005904`；
  task flags 为 `0xC1003391`，definition/animation 为
  `0x083478B4/0x083478F0`。
- 提交后的可复用状态为
  `artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-group17-active.ss9`，
  SHA-256 为 `ac99cf9eba9582bad085226dd8683f33babafc3df83a0647e0deb05a9e76755f`。

静态 producer 与自然运行时相互独立地固定同一链：忍具 37 的编码动作是 `0xA5`，
动态 sequence 为 0；handler `0x0807ED20` 在 callsite `0x0807ED3A` 硬编码选择
sequence 20 / Group 17。graphics 指针项为 `0x005991A4`，相邻 palette 指针
`0x005991A8` 未被合并或改写。

## Phase 与像素证据

- phase artifact：`artifacts/battle-effect-frame-phase-group17-natural-v1/`。
- frame `132/132/133` 依次命中 renderer `0x08063328`、submit `0x08061126`、
  ack `0x080612AA`；pending 严格为 `0→1→0`，目标 task ordinal 均为 2。
- pixel artifact：`artifacts/battle-effect-group17-pixel-ab-v1/`。
- 两份 16 MiB ROM 只重定向 Group 17 graphics 指针；candidate 只把解压 graphics
  offset 22 的高半字节索引 `1→3`（字节 `0x14→0x34`），LZ77 大小均为 103 bytes。
- 六个运行时内存域中仅 OBJ-VRAM `0x06014E16` 一字节不同。该源 tile 同时被三个
  component 使用，其中一个水平翻转，因此最终画面恰有三处变化：
  `(165,92)`、`(194,95)`、`(173,97)`，均从 `[247,255,222]` 变为
  `[115,123,107]`。
- 独立 verifier 与聚合 verifier 均返回 `verified=true, errors=[]`。

## 资源与边界

自然建点、phase 和两次像素运行的 owned-tree 峰值 RSS 分别约为 66 MiB、
74.23 MiB 和 69.95 MiB；所有 guard 均完成且无 PGID/listener 残留，也没有 mGBA
崩溃。本成果只签发 Group 17 的一条自然入口、一个精确事务和一个最终像素因果对照；
不代表完整动画、blend、音频同步或实体 GBA 已全量验证。按用户要求，Group 17 收尾后
暂停完全逆向 Goal，不启动 Group 6/7/8/9/10/12。
