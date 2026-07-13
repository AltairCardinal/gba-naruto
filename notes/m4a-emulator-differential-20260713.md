# m4a emulator differential（2026-07-13）

## 结论

本轮用独立 mGBA 0.10.1 运行时数据闭合了离线整曲引擎的两个硬件边界：

- DirectSound：sound ID 101 从干净 `m4aSoundInit` 后开始，79 次 `SoundMain`
  直至自然结束；79/79 个 264-frame 双声道 FIFO 块逐字节相同，合并原始 signed
  PCM SHA-256 在 ROM 与离线引擎两侧均为
  `d0f02e59c6595bcbaefa0f881e72add5cd2d74f16f5b23eb3dd40127e5648197`。
- CGB noise：sound ID 144 的 68 次 `SoundMain` 全时间线中，68/68 组可读
  `NR41/NR42/NR43/NR51` 与 68/68 个 channel-4 status 都和离线引擎一致；11 次
  retrigger 位于 invocation `1,7,13,19,25,31,37,43,49,55,61`。Direct FIFO 全程为零，
  离线引擎与 ROM 同时在 invocation 68 后自然结束。

这组证据动态覆盖 ID 101 已执行路径中的 player tick、ADSR、gain/pan、23-bit sample
phase、forward-linear interpolation、264-frame buffer、6-slot ring 和左右路 modulo-256
混合；也覆盖 ID 144 的三档 `NR42`、`NR43=0x14`、`NR51=0x88`、release stop 与固定
CGB channel-4 生命周期。它不代替同 player slot retrigger/stop、多个 linked player
并发或跨 player 的全局 CGB pool 竞争测试。

## 关键地址纠正

先前把 `0x03007520` 当成 `SoundInfo` 是错误的；运行时读取表明它是复制到 IWRAM 的
m4a 命令 jump table。`SoundMain 0x08099D8C` 的首条 literal load 实际读取全局指针
`0x03007FF0`，本 ROM 初始化后该指针为 `0x03006570`。

因此正确布局是：

| 对象 | 地址/范围 |
| --- | --- |
| `SoundInfo*` 全局 | `0x03007FF0` |
| 本次 `SoundInfo` | `0x03006570` |
| 12×0x40 DirectSound channel 前缀结束 | `SoundInfo+0x350` |
| right FIFO plane | `0x030068C0`，`6×264=0x630` bytes |
| left FIFO plane | `0x03006EF0`，`6×264=0x630` bytes |
| 4×0x40 CGB state | `0x030075B0..0x030076AF` |
| 4 个 player state | `0x030076B0..0x030077BF` |

受控启动的首轮 counter 为 0，随后为 `6,5,4,3,2,1` 循环；对应物理 chunk 正好是
`0,1,2,3,4,5` 循环。counter=0 的首块是 ID 101 的真实第一个静音块，不能像早期
探索脚本那样丢弃。把它丢弃会令所有离线调用错位一格。

## 可复现实验

运行器为 `/usr/games/mgba 0.10.1`。Qt 可执行文件没有把 CLI debugger 会话暴露到
stdin/stdout；`tools/mgba-headless-snapshot.py` 现在优先使用 SDL CLI 版本，并允许用
`MGBA_BIN` 显式覆盖。

为排除游戏在首个公开 sound-ID 调用前已有的 FIFO 状态，
`tools/build_controlled_audio_runtime_probe.py` 只把 `0x08061E28` 的
`m4aSoundInit` BL 改到 checked zero-filled stub `0x0809E800`。stub 先调用原始 init，
再立即调用 `0x0809AAC0(sound_id)`，然后返回原流程。除 4-byte hook 和 16-byte stub
外没有改 ROM。

```bash
python3 tools/build_controlled_audio_runtime_probe.py \
  rom/base.gba /tmp/controlled-sound101.gba --sound-id 101
# sha256 baf818df828b28948999dd3fb421038c6d896186b76f60f2ccc655ffbe51a60d

python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/controlled-sound101.gba --mode audio --sound-id 101 \
  --invocations 79 --timeout 180 \
  --output /tmp/mgba-sound101-capture79.json

python3 tools/compare_mgba_audio_capture.py \
  /tmp/mgba-sound101-capture79.json \
  --output artifacts/audio/mgba-sound101-full-differential.json
```

ID 144 使用相同流程：

```bash
python3 tools/build_controlled_audio_runtime_probe.py \
  rom/base.gba /tmp/controlled-sound144.gba --sound-id 144
# sha256 07c3c86aad681cb718f289fd5e3b132f31c1e5727f5e9f61a140569d6f2e24c0

python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/controlled-sound144.gba --mode audio --sound-id 144 \
  --invocations 68 --timeout 180 \
  --output /tmp/mgba-sound144-capture68.json

python3 tools/compare_mgba_cgb_capture.py \
  /tmp/mgba-sound144-capture68.json \
  --output artifacts/audio/mgba-sound144-cgb-differential.json
```

原始 capture 包含每次调用的 FIFO、channel、CGB 和 player bytes，约数百 KiB，可由上述
命令确定性重建，因此不入库；入库的 compact artifacts 保存每次调用的双方 SHA-256、
寄存器/status 比较与第一处 mismatch 字段。

## NR44 读回边界

`NR44` bit 7 是 trigger write；mGBA 对该位读回为 0。因此不能把 `x/4` 读到的
`NR44=0` 解释成 ROM 未触发 noise。对照采用两层证据：

1. 离线命令/allocator 时间线记录 11 次期望 `NR44=0x80` 写入 invocation；
2. 同一 invocation 上 mGBA 的 channel-4 status、`NR42/NR43/NR51` 同步切换并持续。

可读寄存器与 status 的 68/68 一致，加上最终 stop 的 `NR42=0x08`、status=0，闭合了
write-only trigger 的可观察边界。

## 剩余音频门槛

- 同一 player slot 新 cue 对旧 cue 的 retrigger/stop 行为；
- 多个 linked player 同时更新的递归顺序与全局 10+4 channel 竞争；
- 跨 player 的固定 CGB channel steal/retrigger；
- 80 个 sound ID 的有来源、玩家可理解 cue 名称；
- 旧网页音频 CRUD 与真实 ROM 安全写回的产品边界。
