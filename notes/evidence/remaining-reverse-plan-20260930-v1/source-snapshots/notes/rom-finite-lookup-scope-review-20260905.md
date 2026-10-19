# 动态窄索引候选的只读复核（2026-09-05）

结论：以下三项继续unknown，新增分类0字节。Sol medium只读初筛后，主代理对照既有
负证据与AGENTS组合RAM生命周期规则确认：局部字段宽度不是完整物理表或记录闭包。
本次未重新做全ROM扫描、mGBA实验或writer扩张，已有负证据不被形态匹配取代。

| 候选 | 确定读取 | 未闭合分母 |
| --- | --- | --- |
| `[0x599924,0x599B1C)` 63×8 | `0x079B0A..0x079B48`：unit+0xBC的LDRB、乘8、最多读取两个u32，null停止 | unit+0xBC无<=62守卫；动态创建/复制链和全部writer未穷尽 |
| `[0x599FF4,0x59A104)` 68×4 | `0x0932A2..0x0932AC`：row+6的LDRB、乘4、读取u32 | `0x094530` producer原样STRB primary ID，静态数据有68..86反例，不能认领68槽完整表 |
| `[0x53DF00,0x53DF70)` 28×4含slot0 null | `0x0712D0..0x071344`：RAM六字节行字段LDRB，仅检查非零，再乘4读取u32 | 无<=27守卫；RAM row writer/lifecycle未闭合；opcode7/8仍缺完整advance/终止合同 |

原始ROM SHA为`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
消费者/producer可从已接受CFG与consumed-literal artifact复验；完整旧反例见
`notes/rom-unknown-cluster-refresh-20260902.md`。
低脚本的五个排除目标`0x0BC9,0x0C2E,0x0C34,0x14B4,0x15FC`及parser边界见
`tools/export_rom_fixed_renderer_script_records.py`和
`tools/export_rom_training_text_script_inventory.py`。仅识别handler的byte参数load不能
授权记录终点或parser未接受的opcode。今后重开须补真正writer/domain或parser合同，
不能将任意注入RAM状态的may-read域改名为canonical primary范围。
