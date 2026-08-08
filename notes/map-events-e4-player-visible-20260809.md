# map-events E4 primary handler 玩家可见闭环（2026-08-09）

`0x0853E698` 是 256 组 primary/secondary Thumb handler。自然工具 67 链把
`C3` 延迟对象映射为 action `E4`；本轮闭合 E4 primary 字段的运行时与最终画面因果性。

## 实验

- 输入：`scenario-49-battle-14-tool67-expiry-ready.ss9`，零按键。输入中有唯一
  slot 3/state 1/action C3/remaining 0 对象且没有 active group-3 task。
- 基线：E4 primary `0x0807F209`；候选：只改为 ROM 内合法 Thumb no-op
  `0x0809C149`（`bx lr`），避免特殊 dispatch 对空指针直接 `bx r1`。
- ROM 实际只改变 `0x53EDB8..0x53EDBA` 三字节；secondary 保持 0。
- 两案均在 frame 66 以 `r0=0x0853EDB8` 命中 `0x0807FD36`，随后把各自
  handler 交给 `0x0809C114`。基线进入 `0x0807F208`，`lr=0x0807FD3F`，并在
  frame 67 创建/渲染 group-3 task 126；候选不进入原生 handler、没有 group-3 task。
- 两案在 dispatch 后等待相同 3 帧，于 frame 69 保存 state 和最终截图。

最终画面相差 37,436 像素，包围盒覆盖 `(0,0)..(239,159)`。六内存域差异计数为
IO 1、PRAM 62、VRAM 6,841、OAM 11、IWRAM 417、EWRAM 13；verifier 同时绑定
各域双案哈希和差分索引哈希。两次 mGBA 峰值为 56.21 MiB 与 56.19 MiB，guard
均 completed/0，无进程残留或崩溃锁。

## 纠偏与边界

初始候选“把 handler 置零”经反汇编被否决，因为 `0x0807FD28..3A` 特殊路径没有
空值检查。第一版 trace 又错误要求恢复后重命中 `0x08081D74`；三个有界诊断均在
120 帧停止且未崩溃。放开该错误 gate 后，直接 handler 断点的
`lr=0x0807FD3F` 定位了真实 consumer，最终只保留 baseline/candidate 两次正式运行。

恢复点已经位于 C3→E4 event 入队之后，所以本轮不声称重新命中 expiry builder；
上游由 hash-bound checkpoint、`battlefield-object-effect-chain` 静态链和既有自然
group-3 phase artifact 约束。本成果只证明 E4 primary 的代表性自然 dispatch，
不泛化到 secondary、其余 255 行、完整动画语义或实体 GBA。可复验证据位于
`artifacts/map-events-e4-handler-pixel-ab-v1/`。verifier 还绑定当前仓库 checkout
和受信 mGBA 的绝对路径/哈希，因此换机或移动 checkout 后需按证据路径恢复环境。
