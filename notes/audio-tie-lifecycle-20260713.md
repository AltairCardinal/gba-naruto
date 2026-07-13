# MP2K TIE / EOT 生命周期闭合（2026-07-13）

## 修复前问题

`tools/render_m4a_midi.py` 会把 `TIE` 记录成 duration 为 `None` 的 note，但 MIDI
编码器只输出有 duration 的 note，因此所有延音在导出的 MIDI 中被静默丢弃。
`EOT` 虽有事件记录，却没有回填对应 TIE 的结束 tick。

## TDD 修复

`execute_track` 现在按 key 保存活跃 TIE；带 key 的 `EOT` 关闭指定音符，不带 key
的 `EOT` 使用当前 running-note key。闭合时把 `duration = eot_tick - tie_tick` 回填到
原 note，标准 MIDI 导出因此会生成对应 note-on / note-off。每个 track 另外暴露
`open_tie_keys`，manifest 汇总每首和全库的 tie 生命周期。

合成轨测试先复现了 duration 为 `None` 的失败，再验证显式/隐式 key 两种 EOT 都在
12 ticks 后闭合，并检查 MIDI 中确有 note-on/off。

## 全 ROM 结果与边界

80 个 sound ID / 217 条 track 重渲染结果：

- TIE 总数：90；
- 被 EOT 明确关闭：25；
- 单循环边界仍活跃：65，分布在 12 条 track；
- 原始总时间线事件为 17202，80/80 MIDI 均正常生成；后续显式状态与逐 tick
  MODT=0 pitch-LFO pass 添加 21328 条 pitch-state 元数据，当前结构化事件总数为
  38530；volume/pan pass 再添加 449 条 mix-state，当前为 38979，note/TIE 数量不变。

剩余 65 条不能武断地在 `GOTO` 单循环截断处释放；它们可能跨 loop 持续，或依赖
track/voice 停止语义。当前仍保留 duration `None` 和 `open_tie_keys`，不会伪造
note-off。后续 envelope/release 实现必须先决定这些跨循环 TIE 的生命周期。

验证：`python3 -m unittest tests.test_render_m4a_midi`；真实 corpus 断言固定为
`90 / 25 / 65`。
