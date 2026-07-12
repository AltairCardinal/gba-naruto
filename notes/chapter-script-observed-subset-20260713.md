# Alternate scenario 39 command 边界（2026-07-13）

## 结果

`tools/chapter_script_analyzer.py` 现可结构化解析 alternate scenario 39 的完整脚本
`0x08031281..0x0803142E`，得到与运行 trace 完全一致的 25 条 command：

| opcode | 次数 | 长度/边界证据 | 当前语义状态 |
|---:|---:|---|---|
| `1B` | 1 | 3 字节；handler `0x08097C9C` 读两个 operand | 已闭合 `AudioCue(cue_id, mode)`；mode 0/1/2 = play/play-and-wait/stop |
| `02` | 5 | 4 字节；handler `0x08097930` 读三个 operand | helper `0x080967E8`，参数名未闭合 |
| `08` | 8 | 2 字节；handler `0x080979E8` 读一个 operand | 已闭合 `SetSpeakerLabel(speaker_label_id)` |
| `01` | 8 | 变长；从 `r7+1` 交给 renderer `0x0806626C` | 内联文字/控制记录 |
| `04` | 2 | 4 字节；handler `0x08097958` 读三个 operand | helper `0x08096A04`，参数名未闭合 |
| `00` | 1 | 1 字节；`0x08097916` | 已闭合 End/return |

总长度为 `0x1AE` 字节，首 command 在 `0x08031281`，末 End 在
`0x0803142E`，解析后无剩余字节。

## `01` 为什么不能直接找首个零字节

renderer `0x0806626C` 明确把 `01` 视为两字节控制记录、把 `02` 视为三字节控制
记录；这些 operand 可以为零，但不终止字符串。高位字符按双字节前进，其他控制/ASCII
按单字节前进，只有位于 token 边界的 `00` 才是 terminator。analyzer 固化了该 walker，
避免 `bytes.find(0)` 在控制 operand 中提前截断。

## 安全边界

此 analyzer 仍是完整观测脚本的只读结构恢复；作者 codec 只开放消费链已经闭合的
`End(00)`、`SetSpeakerLabel(08)`、`SetBattle(1A)` 与 `AudioCue(1B)`。`02/04`
虽然长度已证明，参数含义仍未闭合；`01` 的 renderer token 边界虽然已闭合，但文字
编码及控制记录的创作约束尚不完整。因此这三类仍会被 codec 明确拒绝。

`1B` 的 handler `0x08097C9C` 把第一个 operand 作为 cue ID、第二个作为模式交给
`0x08097140`：模式 `0` 调用 `0x08061E6C` 播放后立即继续，模式 `1` 播放并轮询
`0x08061E98` 等待，模式 `2` 调用 `0x08061E88` 停止。scenario 39 的
`1B 04 00` 因而是 cue 4 的非阻塞播放。

`08` 的 handler `0x080979E8` 用单字节 operand 索引 12-byte 记录表
`0x085A57C4`，再通过 renderer `0x0806626C` 绘制选中的名字/标签并更新对话 UI；
辅助链 `0x08096E60` 同步 portrait/surface 上下文。scenario 39 的标签 ID 序列为
`[7,1,3,1,7,1,7,2]`，与画面上的说话人名标签切换一致。

后续仍应追踪 `0x080967E8` 与 `0x08096A04`，并在开放 `01` 编码前闭合文字编码和
全部 renderer 控制记录。生产写回还缺共享 allocator 与 pointer+payload 原子提交，
不能仅凭 codec 子集直接指向任意 ROM 字节。

重要范围：script `0x31281..0x3142E`；renderer `0x0806626C..0x08066734`；
speaker-label table `0x5A57C4`；audio helper `0x08097140`。
