# 残余 WRAM tilemap 首条自然 queue/flush 运行时闭环（2026-07-31）

## 结论

三条直接进入 status-3 GPU queue 的残余 WRAM tilemap 中，`0x0834928C` 已从
静态 ABI/资源归属升级为自然 base-ROM 运行时闭环：

- 从既有 `lz77-palette-runtime-v1` 人物图鉴自然初始化命中快照继续，输入为
  `[]`，不重复标题页导航；输入快照 SHA-256 为
  `ad2d215c2054e694d67fdd40e22c0aff99fe930466126a2823129ab34e33570c`。
- frame 0 命中 `0x0808AD3A`，寄存器固定源 `r0=0x0834928C`、目标 WRAM
  `r1=0x02002B48`；ROM LZ77 解压为 15×20 u16、600 bytes，SHA-256 为
  `4396144ffc41de6ee3d0da6383f825695bd37aefde1cb2100bd5672200d9140d`。
- frame 2 首次命中共享 consumer `0x0806365C`。queue slot 0 为 status 3，源
  `0x02002B48`、目标 `0x0600001E`、源行宽 15 halfword、行数 20。
- consumer 命中时目标 20 行的 SHA-256 是
  `bd50e12c55dda3ee443c1cb6d71c7bcf6351c4ec96f7bc8d6adec015d1192eea`，
  尚不等于源；紧接的 frame 3 边界，相同行拼接 SHA 与 ROM 解压 payload 完全相同，
  前后 600/600 bytes 均变化，16 个 queue slot 中原 status-3
  `(0x02002B48,0x0600001E,15,20)` 记录数已从 1 变为 0。这把静态 queue 合同、
  consumer 入口、记录退休和 post-consumer VRAM 结果绑定到同一次三帧运行。

输入快照的“自然”来源不是说明文字：verifier 固定并语义复核父
`lz77-palette-runtime-v1` 的 accepted manifest、evidence、profile-browser audit、
`Down,Down,A,A` 输入和 frame-54 命中，再确认父 manifest 中 `hit.ss9` 的哈希就是
本次输入。ABI/ownership 父成果也同时固定 accepted manifest 与 payload SHA；重签
父 evidence 后更新 manifest 仍会被固定 manifest 哈希拒绝。

正式成果位于 `artifacts/residual-wram-tilemap-runtime-v1/`。它保留 load-hit
和 final 两个 `.ss9`，后续可从已验证节点继续而无需重新导航；同时保留原始 audit、
guard、queue、flush 前后 VRAM 和最终截图。独立 verifier 不导入导出器，从基准 ROM
重做 LZ77、读取 ABI/ownership 父成果、解析 queue slot、抽取带 64-byte stride 的
VRAM 行，并拒绝重签后的目标地址、VRAM、额外文件或符号链接篡改。

## 资源安全

- mGBA：0.11-dev commit `c16c3ff55585e71bee83c95539c2ecde15d728c8`；binary
  SHA-256 `4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72`。
- 正式三帧运行经 `tools/run_guarded.py` 和统一 heavy lock；结果 `completed/0`、
  `success-marker`、非 degraded，无进程残留。另一个相同快照的 80 帧开发复核峰值
  owned-tree RSS `62.9453125 MiB`，结果相同，但不作为正式 payload 的替代。
- 未修改 `rom/base.gba` 或用户的 `rom/base.sav`；运行使用实验目录内的 ROM 副本。

## 当前边界

直接 queue tilemap 的运行时分母现为 1/3。`0x083F1C98`、`0x085B67E0` 仍需在
自然场景入口证明 load、slot 和 flush；裁切/变换的另外四条属于 7 条总分母，但不应
混入本 3 条直接 queue 子分母。本成果也不签发精确业务名称、修改 ROM 后的最终像素
A/B、完整跨帧演出时序，或“frame 2 入口至 frame 3 边界之间绝无其他 writer”的
排他因果结论。
