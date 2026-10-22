# MP2K player-slot 运行时差分（2026-07-13）

## 结论

本轮用 mGBA 0.10.1 的真实 `SoundMain` 输出闭合了 player slot 的三个动态边界：

1. 同一 slot 的新 cue 会硬替换旧 cue；替换当次旧 DirectSound channel 已全部清空，
   player 时钟从 1 重新开始，不存在旧 cue 的 release 尾音。
2. 不同 slot 的 cue 会在同一个 `SoundMain` 中并发推进，并共同使用一组
   10-channel DirectSound pool；实际 FIFO 等于两个隔离离线引擎之和。
3. 不同 slot 争用同一固定 CGB channel、priority 相同时，低地址 track owner
   `0x03006178` 稳定胜过 `0x030061C8`；68 次寄存器、status、player clock 时间线均与
   离线模型一致。

静态调用链和地址推导见 `notes/m4a-player-slot-control-flow-20260713.md`。本文件记录
对应的动态证据、诊断 ROM 边界和可复现命令。

## 同 slot 立即覆盖

受控初始化 stub 依次 dispatch sound 101、102；二者均属于 player slot 1。由于第二次
dispatch 发生在首次 `SoundMain` 之前，捕获结果应只等于 sound 102：

- 19/19 个双声道 FIFO chunk 逐字节一致；
- 捕获与离线合并 PCM SHA-256 均为
  `cc8cdd6ff4482c96b0ab92ef7d1d0bc67e572bf40591cf24e514741718ee0427`；
- 诊断 ROM SHA-256 为
  `5a1287af7908ad6f6abd0d706884d2cb5e43e65e07deae20d26aaf8f0d291ff2`；
- 紧凑证据为
  `artifacts/audio/mgba-same-player-101-102-differential.json`。

这证明同 slot 的两个 start 不会建立两条并行 player 链；最后一次 `MPlayStart` 决定
首次 SoundMain 看到的 descriptor。

## 活跃 cue 的延迟硬替换

`tools/build_delayed_audio_retrigger_probe.py` 在干净初始化后启动 sound 101，并把游戏
每帧调用点 `0x08061F76` 改到受检 stub。计入初始化流程中未改写的首次
`SoundMain 0x08061006` 后，第 8 次调用结束时 dispatch sound 102。

27 次捕获由“sound 101 的调用 0..7 + sound 102 的调用 0..18”精确组成：

- 27/27 FIFO chunk 逐字节一致；
- player slot 1 时钟在替换处由 8 重置为 1；
- 替换后的首个捕获点，旧 DirectSound pool 中没有任何 active status；
- 没有把 sound 101 的 release 尾音叠加到 sound 102；
- 双方合并 PCM SHA-256 均为
  `a69ec02e03c3adb8048abd849498715c01ddc08bf6df57e16dc3eb1dc44b0aba`；
- 诊断 ROM SHA-256 为
  `fd6909cb5ce4a18fda89e822000a9fb77e2253f5ddfec217988e64424f423bd6`；
- 紧凑证据为
  `artifacts/audio/mgba-active-retrigger-101-102-differential.json`。

因此 `MPlayStart -> TrackStop` 的硬停止行为已由运行时确认；它与 FINE 命令允许
DirectSound envelope 进入 release 的自然结束路径不同。

## linked player 并发

受控初始化同时启动 slot 1 的 sound 101 和 slot 2 的 sound 106。两者使用
zero-reverb 路径，因此离线期望可以按 signed FIFO plane 逐样本求和并执行 ROM 相同的
modulo-256 写回：

- 25/25 FIFO chunk 与隔离引擎之和逐字节一致；
- 两个 player clock 均按 `1..25` 推进；
- 全局 DirectSound pool 的 active owner 同时出现 `0x03006178` 和
  `0x030061C8`，证明不是每个 player 各有独立 channel pool；
- 合并 PCM SHA-256 均为
  `72de05b85271af0af784ef25160a401531387e82a5cedbb5d473dd78afd445d0`；
- 诊断 ROM SHA-256 为
  `f915bf5edafcabc0b510817476072db0b4a9eb898a573eb2f1246d1701a658e9`；
- 紧凑证据为
  `artifacts/audio/mgba-linked-player-101-106-differential.json`。

该用例动态确认多个 linked player 会在同一 SoundMain 中推进并消费全局 pool。具体
slot 0→1→2→3 的递归调用顺序仍由静态控制流证明；当前用例直接观察到 slot 1 与
slot 2 同轮推进，不把“两个时钟都递增”夸大成逐指令 hook 的完整顺序记录。

## 跨 player CGB 竞争

stock ROM 只有 sound 144 使用 CGB channel 4，无法用两个自然 cue 制造冲突。因此
`tools/build_cross_player_cgb_probe.py` 只用 sound 144 的 master-table row 覆盖
sound 143，并把 clone 的 player slot 改为 1；原 sound 144 保持 slot 2。descriptor、
voicegroup 和 track bytes 均未修改。初始化 stub 先启动 clone 143，再启动 144。

结果为：

- 68/68 组可读 `NR41/NR42/NR43/NR51` 与离线 CGB 模型一致；
- 68/68 个 channel-4 status 一致，Direct FIFO 全程静音；
- slot 1、slot 2 的 player clock 每轮均正确推进；
- channel active 时 owner 始终为 slot 1 track `0x03006178`，从未变成 slot 2 的
  `0x030061C8`；
- 11 次预期 NR44 trigger 写发生在 invocation
  `1,7,13,19,25,31,37,43,49,55,61`；
- 诊断 ROM SHA-256 为
  `b1e5b58730942c21c01831dd3095cd8ee76ab98439026c4ae364429d0753fd16`；
- 紧凑证据为
  `artifacts/audio/mgba-cross-player-cgb-143-144-differential.json`。

这次 capture 动态证明了一个方向：slot 1 先占用后，slot 2 的较高地址 owner 被拒绝；
`old_owner >= new_owner` 和“较低地址稳定胜出”的双方向结论仍由静态 allocator
控制流给出。由于 clone 是地址受检的诊断改写，本结论属于“该同时请求结果”的
runtime-verified 行为，不宣称 stock 内容自然存在两个 CGB cue，也不声称已分别捕获
slot2-first→slot1-steal 的第二时间顺序。

四个 compact artifact 还保存并强制验证诊断 ROM SHA-256、capture counter 序列、
PCM/state hash；CLI 参数与诊断 ROM 不一致时 `verification_passed=false`，不能再只靠
外部传入的 sound ID/slot 元数据升级证据。

## 可复现命令

原始 capture 不入库；以下命令从基准 ROM 重建诊断 ROM，并用
`tools/mgba-headless-snapshot.py --mode audio` 采集。运行器应为 `/usr/games/mgba`。

```bash
# 同 slot 立即覆盖
python3 tools/build_controlled_audio_runtime_probe.py \
  rom/base.gba /tmp/controlled-same-slot-101-102.gba \
  --sound-id 101 --sound-id 102
python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/controlled-same-slot-101-102.gba --mode audio \
  --sound-id 102 --invocations 19 --timeout 120 \
  --output /tmp/mgba-same-slot-101-102-capture19.json
python3 tools/compare_mgba_audio_capture.py \
  /tmp/mgba-same-slot-101-102-capture19.json \
  --dispatch-id 101 --dispatch-id 102 \
  --output artifacts/audio/mgba-same-player-101-102-differential.json

# 活跃 cue 延迟替换
python3 tools/build_delayed_audio_retrigger_probe.py \
  rom/base.gba /tmp/delayed-retrigger-101-102.gba \
  --first-sound-id 101 --replacement-sound-id 102 \
  --switch-after-invocations 8
python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/delayed-retrigger-101-102.gba --mode audio \
  --sound-id 102 --invocations 27 --timeout 120 \
  --output /tmp/mgba-delayed-retrigger-101-102-capture27.json
python3 tools/compare_mgba_retrigger_capture.py \
  /tmp/mgba-delayed-retrigger-101-102-capture27.json \
  --first-sound-id 101 --replacement-sound-id 102 \
  --switch-after-invocations 8 \
  --output artifacts/audio/mgba-active-retrigger-101-102-differential.json

# linked player DirectSound
python3 tools/build_controlled_audio_runtime_probe.py \
  rom/base.gba /tmp/controlled-linked-101-106.gba \
  --sound-id 101 --sound-id 106
python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/controlled-linked-101-106.gba --mode audio \
  --sound-id 106 --invocations 25 --timeout 120 \
  --output /tmp/mgba-linked-101-106-capture25.json
python3 tools/compare_mgba_linked_audio_capture.py \
  /tmp/mgba-linked-101-106-capture25.json \
  --sound-id 101 --sound-id 106 \
  --output artifacts/audio/mgba-linked-player-101-106-differential.json

# 跨 player 固定 CGB channel 竞争
python3 tools/build_cross_player_cgb_probe.py \
  rom/base.gba /tmp/cross-player-cgb-143-144.gba \
  --source-sound-id 144 --clone-sound-id 143 --clone-player-slot 1
python3 tools/mgba-headless-snapshot.py \
  --rom /tmp/cross-player-cgb-143-144.gba --mode audio \
  --sound-id 144 --invocations 68 --timeout 120 \
  --output /tmp/mgba-cross-player-cgb-143-144-capture68.json
python3 tools/compare_mgba_cross_player_cgb_capture.py \
  /tmp/mgba-cross-player-cgb-143-144-capture68.json \
  --source-sound-id 144 --clone-sound-id 143 --clone-player-slot 1 \
  --output artifacts/audio/mgba-cross-player-cgb-143-144-differential.json
```

## 仍未闭合的音频范围

- 80 个 sound ID 的有来源、玩家可理解语义名称；当前调用点审计只支持少量 A/B 级
  候选，不能把其余 72 个 `unknown` 猜成官方名称；
- 旧网页音频 CRUD 到真实 ROM 安全写回的产品边界；
- 若要单独证明 `MPlayStop` 与 FINE 的运行时差异，可增加显式 stop A/B capture；
  这不再阻塞已验证的同 slot `MPlayStart` 硬替换结论。
