# MP2K player-slot control flow（2026-07-13）

## 结论

本 ROM 的 4 个 player slot 只分别拥有 player/track 状态，不分别拥有声道池。
所有 player 的 note handler 都从同一个 `SoundInfo` 取得 10 个可用
DirectSound channel 和 4 个固定 CGB channel。因此跨 player 的分配、steal 和
priority/tie-break 是真实的全局竞争。

同一个 slot 启动新 cue 时，`MPlayStart 0x0809B1F4` 在装入新 track 指针之前，
对该 slot 的每个 track 调用 `TrackStop 0x0809A694`。旧 DirectSound channel 立即
清 `status`，旧 CGB channel 还会先调用硬件 stop handler；两者都清 owner/track
链，不经过 release envelope，也不保留尾音。随后只有新 descriptor 声明的 track
被设为 `0xC0` 并装入命令指针，多余的 slot track 保持停止。因此“同 slot 新 cue”
不是与旧 cue 叠加，也不是 FINE 式 release，而是硬替换。

四个 slot 初始化后，`SoundMain` 中实际的 player 更新顺序是：

```text
slot 0 -> slot 1 -> slot 2 -> slot 3 -> CgbSound -> DirectSound mix
```

链表的 head/入口实际上是最后注册的 slot 3；`MPlayMain 0x0809A42C` 先递归调用
保存在当前 player `+0x38/+0x3C` 的旧 callback/argument，再更新自己，所以执行顺序
反转回 0、1、2、3。这里不是四个独立的 `SoundMain`，所有到期 player tick 都在
同一次 CGB/DirectSound 更新之前完成。

## 固定内存布局与初始化链

`m4aSoundInit 0x0809AA3C` 读取 ROM `0x08465B40` 的 4×12-byte 配置表，按表序
0、1、2、3 调用 `MPlayOpen 0x0809B17C`：

| slot | player state | track array | 最大 track 数 | track 地址范围 |
| --- | --- | --- | ---: | --- |
| 0 | `0x030076B0` | `0x03005E58` | 10 | `0x03005E58..0x03006177`（每项 `0x50`） |
| 1 | `0x030076F0` | `0x03006178` | 1 | `0x03006178` |
| 2 | `0x03007730` | `0x030061C8` | 1 | `0x030061C8` |
| 3 | `0x03007780` | `0x03006218` | 7 | `0x03006218..0x03006447` |

表中每行 `+0x0A` 的控制值均为 0，初始化把其低 byte 写入 player `+0x0B`。
`MPlayStart` 的旧/new song priority 拒绝分支只在该字段非零时生效，因此本 ROM 的
正常 4-slot 初始化会无条件允许同 slot 新启动，不会因为旧 cue priority 更高而拒绝。

`MPlayOpen` 的链构造伪代码为：

```text
open(player, tracks, track_capacity):
    player.tracks = tracks                 # +0x2C
    player.track_capacity = min(capacity, 16)  # +0x08
    set every configured track.status byte to 0

    if SoundInfo.player_callback != NULL: # SoundInfo +0x20
        player.previous_callback = SoundInfo.player_callback  # +0x38
        player.previous_argument = SoundInfo.player_argument  # +0x3C
        SoundInfo.player_callback = NULL

    SoundInfo.player_argument = player    # SoundInfo +0x24
    SoundInfo.player_callback = 0x0809A42D
```

干净初始化时，最后得到：

```text
SoundInfo(+0x20/+0x24) = MPlayMain / slot3
slot3(+0x38/+0x3C)     = MPlayMain / slot2
slot2(+0x38/+0x3C)     = MPlayMain / slot1
slot1(+0x38/+0x3C)     = MPlayMain / slot0
slot0(+0x38)           = NULL
```

`SoundMain 0x08099D8C` 在 `0x08099DC0..0x08099DCC` 调用上述入口。
`MPlayMain 0x0809A43C..0x0809A448` 先调用 previous pair，故 slot 0 最先执行，
slot 3 最后执行。`SoundMain` 随后才在 `0x08099DCE` 调 CGB callback，再进入
DirectSound mixer。

## sound ID dispatcher 与同 slot 替换

`0x0809AAC0` 是无条件的 sound-number start dispatcher：

```text
row = *(0x08465B70 + (sound_id & 0xFFFF) * 8)
descriptor = row.ptr_at_0
player_index = row.u16_at_4
player = *(0x08465B40 + player_index * 12)
MPlayStart(player, descriptor)
```

本 ROM 有效 cue 的 slot/priority 分布是：

| slot | sound ID | SongHeader priority |
| --- | --- | ---: |
| 0 | 1..18 | 0 |
| 1 | 101..105、156..158 | 255 |
| 2 | 106..155 | 255 |
| 3 | 51..54 | 10 |

`MPlayStart 0x0809B236..0x0809B2C8` 的有效启动路径可缩写为：

```text
lock player
player.status = 0
player.song = descriptor
player.voicegroup = descriptor.voicegroup
player.priority = descriptor.priority
reset tempo/counter fields

for each configured player track:
    TrackStop(track)                       # 硬停旧 channel，清旧 owner 链
    if index < descriptor.track_count:
        track.status = 0xC0
        track.index = index
        track.command_ptr = descriptor.track_ptr[index]
    else:
        track.status = 0

if descriptor.reverb has bit 7:
    m4aSoundMode(descriptor.reverb)
unlock player
```

`TrackStop 0x0809A694..0x0809A6D0` 沿 `track+0x20` 的 channel 链遍历：active CGB
先通过 `SoundInfo+0x2C` 的 handler 关闭硬件，然后所有旧 channel 都清 status 和
owner，最后 track head 清零。这和 `FINE 0x0809A1EC` 的“置 release 后摘链、保留
尾音”不同。

另有显式停止路径：`MPlayStop 0x0809B2D8` 给 player 状态加停止位，并对其全部
track 调 `TrackStop`；`m4aSongNumStop 0x0809AB8C` 仅在 slot 当前 descriptor 与指定
sound ID 的 descriptor 相同时调用它；`m4aMPlayAllStop 0x0809ABF4` 则按配置表硬停
全部 4 个 slot。

## 全局 10+4 pool

全局指针 `0x03007FF0` 在运行时指向 `SoundInfo=0x03006570`。player state 里没有
Direct/CGB pool 指针；`ply_note 0x0809A708` 每次都重新取得全局 `SoundInfo`：

- DirectSound 候选从 `SoundInfo+0x50` 开始；虽然结构预留 12×`0x40`，本 ROM 的
  `m4aSoundMode` 把 `maxChans` 设为 10，allocator 只扫描前 10 个；
- 4 个 CGB state 来自唯一的 `SoundInfo+0x1C` 指针，初始化值为
  `0x030075B0`，tone `type & 7` 直接选固定 channel 1..4；
- channel 的 owner 是 track 指针（channel `+0x2C`），所以 owner 可来自任意
  player 的 track array。

因此 10+4 pool 在静态控制流上已经证明为全局，而不是“每 player 10+4”。不同
player 的 note 在同一个池里按 effective priority 和 owner track address 竞争。

## 跨 player 的 CGB tie-break

固定 CGB allocator 位于 `0x0809A7B6..0x0809A7F2`。在目标硬件 channel 非 free、
非 release 时：

```text
if old.priority < new.priority: replace
if old.priority > new.priority: reject
if old.priority == new.priority:
    replace iff old.owner_track >= new.owner_track
```

这里等号是有意的：同一个 track 可以重触发它占用的固定 CGB channel。跨 track
同 priority 时，地址更小的 owner 获得稳定优先权。例如 slot 1 的唯一 track
`0x03006178` 与 slot 2 的 `0x030061C8` 都以 priority 255 发声时：

- slot 1 已占用、slot 2 新请求：`0x03006178 >= 0x030061C8` 为假，slot 2 被拒绝；
- slot 2 已占用、slot 1 新请求：`0x030061C8 >= 0x03006178` 为真，slot 1 立即偷取。

因此同为 priority 255 时 slot 1 固定胜过 slot 2，结果不依赖“谁先到”；正常
SoundMain 顺序 0→1→2→3 只是令同时 note-on 时 slot 1 先占用、slot 2 随后被拒。
DirectSound pool 的同 priority owner 比较是严格 `oldTrack > newTrack`，所以跨
player 同样偏向低地址 track，但同一 track 在十槽全满时不能偷自己的旧 Direct
channel；这与 CGB 的 `>=` 不同。

本 ROM 自然执行的唯一 CGB terminal tone 是 sound 144（slot 2）的 channel-4
noise。其他 stock cue 没有 CGB note，因此 stock cue 组合本身不能自然覆盖“两个
player 同时争同一固定 CGB channel”。本轮已用地址受检的 master-row clone 诊断 ROM
动态制造 slot 1/slot 2 同优先级竞争，并确认 `0x03006178` 始终胜出；详见
`notes/m4a-player-slot-runtime-differential-20260713.md`。该结果验证 allocator 行为，
不宣称 stock 内容自然存在第二个 CGB cue。

## 可复现反汇编与表解析

使用仓库基准 ROM 和 Python Capstone；Thumb literal pool 是数据，必须按函数范围
分段，不能把 literal word 当指令继续解释：

```bash
python3 - <<'PY'
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

rom = Path("rom/base.gba").read_bytes()
base = 0x08000000
for start, end in (
    (0x09AA3C, 0x09AA90),  # m4aSoundInit
    (0x09AAC0, 0x09AAE4),  # sound ID dispatcher
    (0x09A42C, 0x09A680),  # MPlayMain
    (0x09A694, 0x09A6D2),  # TrackStop
    (0x09A708, 0x09A900),  # ply_note / allocators
    (0x09B17C, 0x09B1E6),  # MPlayOpen
    (0x09B1F4, 0x09B2D4),  # MPlayStart
    (0x09B2D8, 0x09B314),  # MPlayStop
):
    print(f"--- 0x{base + start:08X}")
    for insn in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(
        rom[start:end], base + start
    ):
        print(f"{insn.address:08X}: {insn.mnemonic:7} {insn.op_str}")
PY
```

配置表可以独立重建：

```bash
python3 - <<'PY'
from pathlib import Path
from struct import unpack_from

rom = Path("rom/base.gba").read_bytes()
for slot in range(4):
    off = 0x465B40 + slot * 12
    player, tracks = unpack_from("<II", rom, off)
    print(slot, hex(player), hex(tracks), rom[off + 8], rom[off + 10])
PY
```

预期四行依次是
`030076B0/03005E58/10/0`、`030076F0/03006178/1/0`、
`03007730/030061C8/1/0`、`03007780/03006218/7/0`。

## 动态验证状态

`notes/m4a-player-slot-runtime-differential-20260713.md` 已闭合：

1. 活跃 sound 101 在第 8 次 SoundMain 后被同 slot sound 102 硬替换，旧 pool 当次
   清空、player 时钟重置、27/27 FIFO chunk 与无尾音模型一致；
2. slot 1/sound 101 与 slot 2/sound 106 同时推进，25/25 FIFO 等于隔离引擎之和，
   全局 pool 同时观察到两个 track owner；
3. 地址受检的 sound-144 clone 在 slot 1 与原 slot 2 争 channel 4，68/68
   寄存器/status/clock 一致，active owner 始终为 `0x03006178`。

因此同 slot hard replacement、linked-player 并发/共享池和“slot1-first 时 slot2
被拒绝”的跨 player CGB 结果已可标为 runtime-verified。精确的 slot 0→1→2→3
逐调用顺序及反向 slot2-first→slot1-steal 仍以静态控制流为直接证据；动态用例证明
同轮推进和最终共享池结果，没有声称捕获四个 callback 的逐指令 hook或第二时间顺序。

可选的补充实验是显式 `MPlayStop` 与 FINE 的 A/B capture；它不再阻塞上述结论。
