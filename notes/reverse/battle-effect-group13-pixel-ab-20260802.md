# 战斗特效 Group 13 自然最终像素 A/B（2026-08-02）

## 结论

Group 13 已从静态资源、action 61 → sequence 15 → group 13 绑定，推进到修改 ROM 后
的自然动作选择、OBJ VRAM 和最终像素闭环。production 自然最终像素覆盖由 `6/18`
提升到 `7/18（38.89%）`。

本路线把 scenario 39 的 battle ID 从 40 单字节改为 3；它是可重复的 diagnostic
battle route，不代表原剧情自然可达。确认前快照为
`artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9`，SHA-256
`6524764b33c419077bfad8d13fff220a6d20e80b8b92c9da08c9b94d6cdcdf48`。
从该快照只输入一次 `A:60:68`，写入后观察器在 frame 179 捕获 source/runtime
action 均为 61。父证据位于
`artifacts/battle-effect-group13-natural-runtime-v1/evidence.json`。

## 生产修改与运行结果

两份 16 MiB ROM 均由生产 battle-effect relocation 构建。candidate 只把 group 13
解压 graphics offset `0x5D` 从 `0x32` 改为 `0x22`；资源绑定保持 action 61、
sequence 15、group 13、frame 0、component 1。

baseline/candidate 分别从同一确认前快照执行相同输入，在 frame 590 独立捕获：

- EWRAM、IO、PRAM、OAM 完整域无差异；
- IWRAM 只差 `0x03007F9C` 的返回地址
  `0x08061130/0x0806112C`，两者是同一 VBlank wait 边界，证据显式记录而未忽略；
- VRAM 只差 `0x0601245D: 0x32→0x22`；
- OAM entry 2、palette bank 5 和 renderer 均与 profile 一致；
- 最终 240×160 PNG 只在 `(96,63)` 改变一个像素，
  `(173,198,214)→(214,231,239)`；外部 PNG 与各自 `.ss9` 内嵌画面 RGB 指纹一致。

两次运行均由 heavy guard 管理，结果为 `completed/0`、非 degraded、PGID clean，峰值
owned-tree RSS 分别为 `69.58203125 MiB` 和 `69.5703125 MiB`。正式成果位于
`artifacts/battle-effect-group13-pixel-ab-v1/`，独立 verifier 返回
`{"errors": [], "verified": true}`。

## 证据边界

本成果签发 diagnostic battle 3 中 action 61 的自然 AI 选择，以及 Group 13 frame 0
的单字节、单 VRAM byte、单最终像素生产链。它不签发原剧情可达性、Group 13 全部帧、
完整 affine/blend/window/audio 时序、其余 10 个 Group 或实体 GBA 输出。

此前 `0x0807A222` 的观察位于 `strb r1,[r4+0x770]` 之前，可能读取上一轮旧值；其
“battle 8 连续选择 action 64，因此 Group 13 不可用”的结论已被本证据取代。新的
动作观察点固定为写入后的 `0x0807A22C`。
