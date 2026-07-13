# DirectSound ADSR / release / pseudo echo（2026-07-13）

## 精确状态机

SoundChannel 的 tone ADSR 在 note init `0x0809A88E..0x0809A892` 从 tone `+8..+B`
复制到 channel `+4..+7`。状态机位于 `0x08099EC8..0x08099F68`，每次
SoundMain mixer invocation 推进一次，不跟 MP2K wait tick 等价。

状态位：`0x80 new`、`0x40 release`、`0x10 loop sample`、`0x04 pseudo echo`，
低两位 `3 attack / 2 decay / 1 sustain`。`tools/m4a_envelope.py` 固化以下整数规则：

```text
attack: ev += A; ev>=255 时钳255并进入 decay
decay:  ev = ev*D>>8; ev<=S 时钳S并进入 sustain
release: ev = ev*R>>8; ev<=echoVolume 时进入 echo 或在零阈值立即停止
echo: 进入阈值的当前 tick 有输出；之后按 echoLength 倒计时，pre<=1 时停止
masterEnv = (masterVolume+1)*ev >> 4
mixR/L = preEnvelopeR/L * masterEnv >> 8
```

第一级 track/channel 双声道增益见 `notes/directsound-volume-pan-20260713.md`；最终
gain 地址是 `0x08099F6A..0x08099F82`。release-before-first-mix (`new|release`)
直接停止，不产生 attack click。attack 0 会永久停在静音 attack；decay/release 255
仍因 `>>8` 缓慢下降，不是恒定。

## Gate、EOT、FINE 与 TIE

- 普通 note 的 gateTime 每个 MP2K tempo tick 递减到 0 后置 release 位；gate 0
  不自动 release。
- `EOT 0xCE` 在 `0x0809A908..0x0809A946` 只释放首个匹配 key 的 active channel。
- `FINE` 在 `0x0809A1EC..0x0809A218` 让该 track 所有 active channel 进入 release，
  但不硬停止尾音。
- TrackStop 直接清 status，是无尾音硬停。
- TIE gateTime 为 0；GOTO 与分析器单循环边界没有隐式 release。

因此旧 `90 / 25 EOT / 65 open` 统计已纠正为：90 TIE、25 被 EOT 释放、19 在
FINE 释放、46 在单循环 GOTO 边界仍 open。只有这 46 条可能跨 loop 延续；渲染器
不会在分析边界伪造 EOT。

## 全库参数覆盖

16169/16169 DirectSound note 的 ADSR 均有效，只有 4 种 tuple：15006 条
`255/0/255/0`、837 条 `255/127/231/0`、171 条 `255/0/231/127`、155 条
`255/0/231/89`。全部 attack 都是 255；837 条 decay 非零，326 条 release 非零。

紧凑证据在 `artifacts/audio/envelope-evidence.json`。尚未完成的是把 MP2K tempo
时间线映射为 SoundMain buffer invocation、执行 sample loop/耗尽、混合并输出最终
PCM/WAV；因此不能把纯状态机 coverage 宣称为整曲波形忠实度。
