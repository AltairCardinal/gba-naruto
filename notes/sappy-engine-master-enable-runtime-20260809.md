# Sappy 音频初始化代码运行时闭环（2026-08-09）

## 结论

历史 `sappy-engine` slug 的真实对象是 ROM `0x09AE3C..0x09AEF3`
（CPU `0x0809AE3C..0x0809AEF3`）的 184-byte Thumb 音频初始化函数，不是
`0x08079668` 的消息分派器。旧 extractor 只保存 128 bytes，在
`0x0809AEBC` 的函数内截断；现已扩展到返回指令 `0x0809AEF2: bx r0`。

受控 ROM 复用 `tools/build_controlled_audio_runtime_probe.py` 的 clean-init +
sound 101 路线。baseline/candidate 只在 ROM `0x09AE76` 相差一个字节，把
`movs r0,#0x8F` 改为 `movs r0,#0x0F`；其后同一条 `strh` 写
`SOUNDCNT_X (0x04000084)`。

## 运行时证据

- 输入快照：两案共同恢复 `input-disclaimer.ss9`，SHA-256
  `02bc502ad31ba1cd781dba8a3f212dbf5d7b88e83132e4913e9f19b04afa2c36`；
  快照位于初始化前，`SOUNDCNT_X=0` 且 SoundInfo magic 尚未建立。
- 两案均在恢复后 frame 51 命中 initializer entry/return，frame 53 命中
  sound-ID 101 dispatcher 和首次 SoundMain return。
- 初始化返回时，baseline `SOUNDCNT_X=0x0080`，candidate `0x0000`；除该值外
  两案 audit 的控制流、cycle、寄存器采样和首次 SoundMain FIFO 块完全相同。
- 首次 SoundMain 后两案均为 `SOUNDCNT_X=0x008B`，说明后续路径重新打开
  master gate；因此本证据只证明目标指令的初始化时硬件效果，不声称持续静音。
- 首个 264-frame 双声道 FIFO 块为预期静音块，交错 PCM SHA-256
  `8889eb3cdd3d0ac94711b47ce78b430d8e23a7b31ecc994c56d0c3310c87674a`，
  与既有 sound 101 的 79/79 mGBA/离线差分首块一致。
- 两次正式 mGBA 峰值 owned-tree RSS 为 108.05/107.33 MiB，均由 heavy lock、
  512 MiB 上限、crash latch 和 success marker 保护，无降级、无崩溃。

正式证据为 `artifacts/sappy-engine-master-enable-ab-v1/`。`raw.tar` 不包含 ROM，
verifier 从 `rom/base.gba` 重建两案，复核唯一 ROM 差异、快照状态、断点链、
guard/工具哈希、FIFO 及硬件 gate，并支持从 raw archive 字节级重导出。

## 边界

闭环证明该 184-byte 函数真实执行，且 `0x0809AE76` immediate 控制初始化时的
GBA 音频 master gate。它不证明其余指令均可安全修改，不证明 candidate 会持续
静音，不提供录制 WAV 差异，也不替代实体 GBA 验证。
