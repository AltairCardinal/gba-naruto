# DirectSound 音量与声像链（2026-07-13）

## 地址与字段

- `TrkVolPitSet 0x0809B3E0..0x0809B492`：把 track 的 VOL、volX、PAN、panX
  与 MODT 合成为右/左增益缓存 `track+0x10/+0x11`。
- `ChnVolSetAsm 0x0809A6D8..0x0809A706`：把上述缓存与每个 channel 的
  note velocity、drum tone pan 合成为 pre-envelope 增益 `channel+2/+3`。
- `0x08099F74..0x08099F82`：再以实时 envelope scalar 缩放到 mixer 使用的
  `channel+0x0A/+0x0B`；该 envelope 状态机仍需单独闭合。

`VOL 0xBE` 在 `0x0809A340` 原样写 track `+0x12`；`PAN 0xBF` 在
`0x0809A354` 把 `raw-0x40` 写入 signed track `+0x14`。默认 volX 为 64、panX
为 0。MODT=1 把 signed `modM` 用作音量倍率，MODT=2 把它加到声像。

## 精确公式

```text
base = (VOL * volX) >> 5
if MODT == 1: base = (base * (modM + 128)) >> 7
pan = clamp(2 * signedPAN + panX + (modM if MODT == 2 else 0), -128, 127)
trackR = ((base * (pan + 128)) >> 8) & 0xff
trackL = ((base * (127 - pan)) >> 8) & 0xff

chanR = min(255, velocity * (tonePan + 128) * trackR >> 14)
chanL = min(255, velocity * (127 - tonePan) * trackL >> 14)
```

第一级最终是 `STRB`，极端合法组合会低 8 位回绕，不能擅自饱和。第二级才显式
钳为 255。drum child 的 `pan_sweep` bit7 置位时，`tonePan=(raw-0xC0)*2`；
普通 DirectSound tone 不使用这个字段作固定 pan。

## 全库覆盖与边界

`tools/render_m4a_midi.py` 现生成精确 `mix_state`，并在 note-on 快照 track
右/左缓存；`tools/map_m4a_instruments.py` 再传播到 channel pre-envelope 增益。

- 16169/16169 DirectSound note 均得到有效 channel 双声道系数，零无效；
- 右侧范围 0..139，左侧范围 0..146；
- 活跃 note 内共有 39 次有效 mix 更新，全部来自 VOL，零无效；
- 实际 217 条 track 中 MODT=0 次、LFODL=0 次，因此 MODT=1/2 只由合成边界向量
  锁定，不能宣称自然曲目覆盖；PAN 的 225 条命令都没有在本单循环语料的活跃
  DirectSound note 内发生。

结构化 timeline 当前为 38979 events：原有 38530 条加 449 条 `mix_state`。
结构 MIDI 仍不编码 ROM-exact mix-state，最终 envelope、mixer saturation 与 PCM
渲染未完成。
