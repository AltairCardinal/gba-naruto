# Alternate scenario 39 command 边界（2026-07-13）

## 结果

`tools/chapter_script_analyzer.py` 现可结构化解析 alternate scenario 39 的完整脚本
`0x08031281..0x0803142E`，得到与运行 trace 完全一致的 25 条 command：

| opcode | 次数 | 长度/边界证据 | 当前语义状态 |
|---:|---:|---|---|
| `1B` | 1 | 3 字节；handler `0x08097C9C` 读两个 operand | 已闭合 `AudioCue(cue_id, mode)`；mode 0/1/2 = play/play-and-wait/stop |
| `02` | 5 | 4 字节；handler `0x08097930` 读三个 operand | 已闭合 `ShowPortrait(slot, portrait_id, expression_id)` |
| `08` | 8 | 2 字节；handler `0x080979E8` 读一个 operand | 已闭合 `SetSpeakerLabel(speaker_label_id)` |
| `01` | 8 | 变长；从 `r7+1` 交给 renderer `0x0806626C` | 已闭合 `RenderText(encoded_text)`；编码字节与汉化显示字形不等价 |
| `04` | 2 | 4 字节；handler `0x08097958` 读三个 operand | 已闭合 `UpdatePortrait(slot, portrait_id, expression_id)` |
| `00` | 1 | 1 字节；`0x08097916` | 已闭合 End/return |

总长度为 `0x1AE` 字节，首 command 在 `0x08031281`，末 End 在
`0x0803142E`，解析后无剩余字节。

## `01` 为什么不能直接找首个零字节

renderer `0x0806626C` 明确把 `01` 视为两字节控制记录、把 `02` 视为三字节控制
记录；这些 operand 可以为零，但不终止字符串。高位字符按双字节前进，其他控制/ASCII
按单字节前进，只有位于 token 边界的 `00` 才是 terminator。analyzer 固化了该 walker，
避免 `bytes.find(0)` 在控制 operand 中提前截断。

## 安全边界

analyzer 保留地址、raw bytes 等调查证据；作者 codec 只开放消费链已经闭合的
`End(00)`、`ShowPortrait(02)`、`UpdatePortrait(04)`、`SetSpeakerLabel(08)`、
`SetBattle(1A)`、`AudioCue(1B)` 与 `RenderText(01)`。整个 alternate scenario 39
现可由严格 codec 解码为 25 条语义 command，再逐字节编码回原始 `0x1AE` 字节。

`RenderText` 故意暴露 `encoded_text_hex` 而不是 Unicode 字符串。底层流是 cp932/SJIS
形状，但熊组汉化版替换了字形，同一个 cp932 code point 显示出的中文可能与 Unicode
字符不同。codec 复用 renderer `0x0806626C` 的 token walker：内部控制 `01` 占两字节、
`02` 占三字节、高位字符占两字节，其余占一字节；只允许 token 边界上的 `00` 终止。
这允许无损、安全地创作已编码内容，同时不作错误的“输入文字即所见文字”承诺。

`02` 的 handler `0x08097930` 将三字节 operand 原样交给 `0x080967E8`。第一个参数
索引仅有两个元素的 portrait slot 指针数组 `0x03005E50`；第二、三个参数最终进入
`0x08096138`，按 `0x085A4DEC + portrait_id*40 + expression_id*8` 选择图形/调色板
指针对（expression 5 使用 `0x085A4DE4` 特殊 pair）。该 helper 会在 slot 为空时创建
对象、设置转场状态并等待完成，因此命名为 `ShowPortrait`。

`04` 的 handler `0x08097958` 同样传递 slot/portrait/expression，但 helper
`0x08096A04` 直接通过 `0x08096238` 替换已存在 slot 的资源，再调用 `0x08096DD4`
同步另一侧 portrait surface，不创建 slot、不等待入场转场，因此命名为
`UpdatePortrait`。scenario 39 的 show 参数依次为
`(1,7,0),(0,1,1),(1,3,0),(1,7,0),(0,2,0)`，update 参数为
`(0,1,0),(0,1,1)`，与随后 speaker label 的人物切换相符。

codec 对两条 portrait 命令额外限制 `slot=0..1`、`portrait_id=0..62`、
`expression_id=0..5`；这对应真实数组/矩阵边界，避免任意 u8 导致越界读取。

`1B` 的 handler `0x08097C9C` 把第一个 operand 作为 cue ID、第二个作为模式交给
`0x08097140`：模式 `0` 调用 `0x08061E6C` 播放后立即继续，模式 `1` 播放并轮询
`0x08061E98` 等待，模式 `2` 调用 `0x08061E88` 停止。scenario 39 的
`1B 04 00` 因而是 cue 4 的非阻塞播放。

`08` 的 handler `0x080979E8` 用单字节 operand 索引 12-byte 记录表
`0x085A57C4`，再通过 renderer `0x0806626C` 绘制选中的名字/标签并更新对话 UI；
辅助链 `0x08096E60` 同步 portrait/surface 上下文。scenario 39 的标签 ID 序列为
`[7,1,3,1,7,1,7,2]`，与画面上的说话人名标签切换一致。

后续若要提供 Unicode 编辑入口，仍需闭合汉化字形的反向映射与全部 renderer 控制
记录的高层名称。生产写回还缺共享 allocator 与 pointer+payload 原子提交，
不能仅凭 codec 子集直接指向任意 ROM 字节。

重要范围：script `0x31281..0x3142E`；renderer `0x0806626C..0x08066734`；
portrait matrix `0x5A4DEC..0x5A57C3`；speaker-label table `0x5A57C4`；
audio helper `0x08097140`。
