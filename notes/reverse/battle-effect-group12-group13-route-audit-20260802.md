# Group 12/13 自然入口审计（2026-08-02）

## 结论（已由后续证据部分取代）

- Group 12 / action 32“雷切”：当前 battle 8 路线不可用。卡卡西虽为 Lv25，实际
  战斗单位的 15 个动作槽只有 `1,2,3,5,29,30,31`，没有 action 32。全仓 190 份
  tracked `.ss9` 也没有任何实际单位动作槽含 32、76 或 77。
- Group 13 / action 61“斩首大刀”：battle 8 的再不斩动作槽确实含 61，同时也含
  64。原首轮已有 action 64 运行时证据；本轮对第二、第三次敌方行动设置真实
  runtime-copy 观察点，两次仍选择 64，不能把资源变化推断成 action 61 入口。
- 当时只能确认 production 自然最终像素仍为 `6/18`。下文的 Group 13 否定结论已被
  写入后观察点和 battle 3 自然 action 61 证据取代；Group 12 结论仍有效。

## 为什么固定帧读取无效

动作上下文地址 `0x02027428 = 0x02026CB8+0x770` 会跨界面保留上一轮 action 64。
曾在回合确认选择仍为“否”时按 A，画面返回菜单而该字节仍为 64；这证明固定帧或
最终快照中的单字节不能证明本轮 AI 做过选择。

新增 `tools/mgba_battle_ai_action_observer.lua` 和
`tools/run_macos_mgba_battle_ai_action_observer.py`：只在原 ROM
`0x0807A222` 读取 `r4+0x770`，保存命中状态后退出。后续反汇编复核证明该地址位于
`0x0807A22A: strb r1,[r4+0x770]` 之前，因此这里读取的仍可能是上一轮旧值；它不是
“真实 runtime-copy”观察点。观察器已经改为写入后的 `0x0807A22C`。

## 运行结果

路线 ROM 由 scenario 39 的 battle ID 单字节改为 8，SHA-256 为
`6325192e28774efdb30014b87fe7a3e17f2c1bd1f7c34b2484815c156c081b4e`。

| 样本 | 输入状态 SHA-256 | 命中帧 | action | 峰值 RSS |
|---|---|---:|---:|---:|
| 第二次敌方行动 | `e4a85707f12e28302b534da54ae7df62beab506baf4ea64b0d207bf4db08862e` | 1607 | 64 | 65.37890625 MiB |
| 第三次敌方行动 | `725148ab22f82fb435c9fdfa8ef0324baee9dc977dc146c5072aeffe37b6d63b` | 447 | 64 | 65.59765625 MiB |

两次均验证 runtime pointer `0x02026CB8`、action address `0x02027428`、battle-control
pointer `0x0202680C`，guard 为 completed/non-degraded，且 PGID 和 mGBA listener 无
残留。第三回合确认快照及画面已持久化为：

- `artifacts/runtime-checkpoints/battle8-round3-ai-preconfirm.ss9`，SHA-256
  `725148ab22f82fb435c9fdfa8ef0324baee9dc977dc146c5072aeffe37b6d63b`；
- `artifacts/runtime-checkpoints/battle8-round3-ai-preconfirm.png`，SHA-256
  `cf8821dc8e7cc19d28a8fb4c4ed825314e95351fb3406c25f6ab03140c0152d9`。

该快照仅是调查恢复点：回合结束确认已选择“是”，再不斩 action 61 仍在实际动作
数组中。它不证明下一次会选 61，也不应进入 production 完成度分子。

## 下一步

1. 优先静态确认 battle 3 的低阶再不斩是否未携带 action 64；若成立，从兼容的战前
   快照建立 battle-3 确认点。
2. 若 battle 3 不可快速抵达，再扩展只读观察器，记录 `0x08084274` 返回的每个
   candidate action/score 和 `0x080855A8` 的 best 比较，确认 action 61 是否真实进入
   候选以及失败原因。
3. 只有捕获本轮 action 61 的 runtime-copy、对应 sequence 15/group 13 绑定和确认前
   可恢复状态后，才进入 production relocation 最终像素 A/B。

## 后续闭合（2026-08-02）

上述第 1、3 项已经完成。scenario 39 的 diagnostic battle ID 从 40 单字节改为 3，
路线 ROM SHA-256 为
`3569189c489ae1bc92c85d6afd7fc09a8ac97d102bad554323b897d28c911905`。
持久化确认快照为
`artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9`（SHA-256
`6524764b33c419077bfad8d13fff220a6d20e80b8b92c9da08c9b94d6cdcdf48`）。从该快照
只输入 `A:60:68`，写入后观察器在 frame 179 捕获 source/runtime action 均为 61，
并验证 runtime pointer `0x02026CB8`、action address `0x02027428` 与 battle-control
pointer `0x0202680C`。

父证据为 `artifacts/battle-effect-group13-natural-runtime-v1/evidence.json`；它明确
标记该路线是 diagnostic battle route，不冒充原剧情可达性。随后生产 relocation A/B
完成 group 13 单帧单像素因果链，独立 verifier 返回 `errors=[]`，成果位于
`artifacts/battle-effect-group13-pixel-ab-v1/`。完整结论见
`notes/battle-effect-group13-pixel-ab-20260802.md`。因此 Group 13 已进入 production
自然最终像素分子，聚合值为 `7/18`；Group 12 仍未闭合。
