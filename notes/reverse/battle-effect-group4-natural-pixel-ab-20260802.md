# Group 4 忍具确认自然像素 A/B（2026-08-02）

## 结论

Group 4 / sequence 4 已从原版忍具 1“十字手里剑”的最终确认页完成自然
renderer→submit→ack 与 production relocation 最终像素 A/B。它把 18 组战斗特效的
production 自然最终像素覆盖从 9/18 提升到 **10/18（55.56%）**。

正式成果：

- phase：`artifacts/battle-effect-frame-phase-group4-natural-v1/`；
- pixel A/B：`artifacts/battle-effect-group4-pixel-ab-v1/`；
- profile：
  `sequel/content/battle-effect-pixel-ab/group-04-tool1-projectile.json`；
- 聚合分母：`artifacts/battle-effect-observed-frame-phases-v1/`。

## 自然入口与时序

唯一输入状态为已接受的
`artifacts/runtime-checkpoints/scenario-50-cross-shuriken-confirmation.ss9`。该状态位于
忍具 1 / encoded action 129 的最终确认前，且没有活动 Group 4 task。两边只执行
`A:5:13`：

- Group 4 definition/animation 为 `0x08342910/0x08342934`；
- task slot 127 在 frame `94/94/95` 经过 renderer、submit、ack；
- pending 严格为 `0→1→0`，ack 后 hardware OAM 等于 renderer 生成的 shadow OAM；
- OAM entry 0 为 `0x003A/0x8051/0x4900`，OBJ tile base 256、palette bank 4；
- mGBA 截图回调比 OAM 提交晚一帧，因此最终像素证据固定在 frame 96，而不是把
  frame 95 的提交边界误作最终画面。

同一确认动作的动态 selector 还会选择 sequence 13 / Group 11；Group 4 来自该忍具
handler 的硬编码 sequence 4 路线。profile 和 phase provenance 将 trigger
sequence 13 与新增资源 sequence 4 分开记录，避免把两者误认为同一资源组。

## 修改隔离与最终像素

baseline/candidate 均使用当前桌面 mGBA profile，并从同一确认前快照执行同一个输入。
构建只重定向 Group 4 graphics 指针 `0x59913C` 到 sequel image partition；两侧 LZ77
编码长度均为 447 bytes，patch topology 相同。candidate 仅把解压图形 offset
`0x99` 从 `0x13` 改为 `0x14`，即低半字节 palette index `3→4`。

frame 96 的六域比较结果：

- EWRAM、IWRAM、IO、PRAM、OAM：零差异；
- VRAM：仅 `0x06012099` 为 `0x13→0x14`；
- 最终 240×160 RGB：仅 `(83,72)` 从 `[206,148,123]` 变为
  `[189,123,115]`；
- baseline/candidate 的离线 Mode-0 renderer 均逐像素等于各自 mGBA PNG。

因此证据同时闭合“确认输入→自然创建 Group 4 task→ROM 迁移资源进入 OBJ VRAM→
唯一最终像素”，不是直接注入 selector、task 或 VRAM 的 controlled 结果。

## 资源安全与证据维护

baseline/candidate guard 峰值 RSS 分别为 `70.03515625/70.09375 MiB`；两次均
`completed`、non-degraded，owned process group 与 mGBA listener 无残留。运行复用
确认前快照，没有重复长导航。

本轮还把 phase 聚合更新为 8/18、production pixel 聚合更新为 10/18。由于 phase
manifest 的实现哈希刷新会改变 natural-delayed profile 的父 manifest 哈希，
`tools/rebuild_battle_effect_pixel_ab_artifacts.py` 现可批量重基 Group 3/18 的纯
provenance JSON，同时证明 savestate、内存 dump、截图、图形二进制和最终像素均未改变。

## 未完成边界

剩余没有 production 自然最终像素闭环的组为
`{6,7,8,9,10,12,16,17}`。本成果不签发 Group 4 全部 frame/component、完整
affine/blend/audio 时序或实体 GBA/flashcart 等价。
