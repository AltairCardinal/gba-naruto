# AI 配置索引双来源预检（2026-09-30）

状态：只读有限窗口调查，promotion=0。模式为复用现有Thumb窗口解码器核对已知消费者
与上游writer；窗口内的线性反汇编会跨literal，不能替代CFG或producer分母。
本轮未启动mGBA、全ROM扫描或新语义工具；不把任意RAM输入解释为自然索引域。

## 输入与方法

- ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 使用canonical SHA `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
- 实验通过experiment_workspace init建立于
  `build/experiments/active/ai-config-preflight/consumer-domain-20260930-v1/`。
- 复用`tools/disasm_thumb.py`：三个固定窗`84274..85154`、`6A900..6AC00`、
  `6E200..6E400`内只搜索低字节CD、movs/adds immediate形态，再对三个命中各取0x80B。
  此搜索不穷尽其他寄存器、别名、STR/Memcpy或computed writer，也不证明形态即指令。
- `consumer-point-provenance.json`逐点保存既有claim、segment与ROM原字节；下面重要
  读写点位于instruction-only v2/v6 owner，不使用consumer_code_slice作为成员证据。
- 解码和目录快照是轻量有限读取，与正在运行的heavy coverage无共享写入；未绕过锁
  启动第二个heavy任务。decoder、窗原字节和来源哈希均保存在预检inventory。

可重放窗口示例：

```sh
python3 tools/disasm_thumb.py rom/base.gba 0x080842D2 --before 0x20 --size 0x80
python3 tools/disasm_thumb.py rom/base.gba 0x0806E246 --before 0x20 --size 0x80
python3 tools/disasm_thumb.py rom/base.gba 0x0806E2CA --before 0x20 --size 0x80
python3 tools/disasm_thumb.py rom/base.gba 0x0806E26C --before 0 --size 0x64
```

## 有正证据的局部操作

1. `842D2 ADD r0,#CD → 842D4 LDRB r1,[r0] → 842D6 MOV #A8 → 842D8 MUL →
   842DA PC-relative LDR → 842DC ADD`。消费的literal在`84344`，值`0853F348`。
   这确认索引字段与stride，不提供`<=7`上界。
2. 已知直接编队分支：`6E244 LDRB r1,[r5,#0E] → 6E246 ADD r0,#CD →
   6E248 STRB r1,[r0]`；单位池literal在`6E268`，值`020240C0`。
3. 另一分支：`6E2C0 LDRB r1,[r0] → MOV #AC → MUL → 加table base →
   6E2C8 LDRB r0,[r0,#2] → 6E2CA ADD r2,#CD → 6E2CC STRB r0,[r2]`。
   table-base literal在`6E2DC`，值`085411E4`；单位池literal在`6E2D8`。
   前段`6E26C..6E2C0`先做`(r1+6)&FF <=2`，再经RAM字节lookup产生ROM行索引。
   初次lookup有非零检查；writer用的是call后的再次lookup，callee与RAM别名不变量
   仍须证明，不能把callee前一次结果直接当callee后结果。

对应既有owner为v2 block `cfg-proven-roots-v2-thumb-0054-0842c8`、v6 blocks
`cfg-proven-roots-v6-thumb-0134-00-06e236`及`...0138-00-06e2a4`，literal属于已分类
consumed-literal claims。当前只是复用这些证据的点库存，未重跑完整v2/v6 verifier。

## 对后续规划的改变

旧AI候选记录只突出source record+0E复制。不能把它当完整writer分母；至少还要处理
固定ROM base5411E4、0xAC stride的`+2`读链，以及上游RAM lookup/call/生命周期。
5411E4位于大unknown簇`53F89C..541368`内部，因此“大簇完全没有消费者锚点”的
描述应限定为尚无完整全范围消费合同：该子范围现在有已知正向读取入口。
它不证明整个大簇、27行物理表、全部资源格式或AI索引已闭合。

另一个必须区分的分母：旧AI分析器的8×0xA8逻辑span精确结束于`53F888`，
而历史unknown候选只到`53F86C`。1,316B是后者的未知交集估算，不能称8×0xA8
完整表长度；邻接既有owner和逻辑尾必须分别验真，禁止包络认领。

下一步一次性冻结formation controller的完整入口、direct producer、两条writer path、
源记录域及call前后lookup不变量；无法证明完整writer域时keep_unknown。
这里没有把8行内容一致性、字段名称或单场自然样本替代生命周期证明。

## 固定内容反例与范围收紧

复用`tools/extract_positions.py`按已有48×3×12矩阵读取，首分支选择器FD/FE/FF各41条，
共123条，其raw `+0E`全部FF；第二分支FA/FB/FC各8条，共24条。这里只是固定矩阵内容
库存，不证明state group/variant生命周期，也不声称这些记录都会自然抵达scorer。
由此“所有writer产生0..7”的无条件命题不可作为合同；真正需要证明的是抵达正常
scorer路径时的状态域，以及FF单位是否被调用方或random-only前置分支排除。

对第二来源按任意u8 lookup试读固定字节时，index24在`542206`读到9，255个其他候选
同样不能凭字段宽度全部授权。`5411E4 + 24×AC = 542204`，且前24个`+2`字节为
`0,1,...,1`，这是后续边界研究提示，不是24行物理表证明。不得把第24项反例说成自然
越界：当前仍缺真实lookup值域及callee前后不变量。
派生数据独立保存在`notes/evidence/rom-ai-config-writer-preflight-derived-20260930-v1/`，
没有修改已completed实验或覆盖其原始窗口。

## 验收

- [ ] 重放三个窗口 → 找到842D4读取、6E248与6E2CC两个写入点及各自来源。
- [ ] 对照provenance → 重要点是既有instruction-only owner，literal值分别吻合。
- [ ] 核对边界 → 8×0xA8结束于53F888，候选unknown span不是整表；promotion仍为0。

## scorer入口与额外writer（后续独立预检）

新实验`ai-config-preflight/scorer-exclusion-20260930-v1`只读取三个有限窗口，复用
现有解码器和positions extractor；inventory连续两次逐字节一致，重要点均位于
既有v2/v6 instruction-only owner。永久收据为
`notes/evidence/rom-ai-scorer-exclusion-preflight-20260930-v1/`，promotion仍0。
其canonical来源为新落盘b568db6f…cf06d2，不覆盖前次旧基线窗口。

- scorer `8429C..842A6`读取unit+C0、与0E、比较2，不等进入842C8正常评分路径。
  这是既有utility analyzer的random-only门，未见本地CD==FF排除。
- core `6AAD4`写C0，其此前计算为source参数byte OR flagsword OR10；对123条
  FD/FE/FF矩阵内容，`(record[1]|u32(record[8:12])|10)&0E`全部0。
  这是call参数及初始化处的内容投影，不证明6A9EC等后续callee、状态变更或scorer
  实际入口保持该值；它仅否决“固定初始化就把这些记录全部设为random-only”的捷径。
- `6AB16..6AB1E`在core把CD字节OR FF写回，形成默认FF来源。
- `6AD68..6AD6E`从source+0E写本单位CD；`6AD74..6AD90`在C0&0E==6时又把该值
  写入由unit+CA关联的单位。两点均是v6 instruction-only owner，表明初始化、复制与
  关联单位路径必须纳入writer分母，不能再称“仅两条writer”。
- 6AC70包装器调用6AA64，formation6E232调用6AC70；6ACAC另一初始化入口也调用
  6AA64。当前没有穷尽全部入口、call前后寄存器/内存别名或自然执行producer。

下一验收里程碑先固定84274/851F8调用链的actor选择与阵营/控制状态域，同时冻结
6AA64/6ACAC/6E1B4的writer入口分母及状态变更；若只能提供任意RAM或局部可读
witness，继续keep_unknown。相关记录名称仍保持暂定，不由FF内容推导原作bug。

后续入口调查已完成独立局部预检，见`notes/rom-ai-entry-local-domains-20260930.md`：
主producer确有FF/0门、次producer筛CC而非CD，loop耗尽槽13及跨callee义务仍开放。
已有851F8全ROM固定target Thumb BL分母可按哈希复用，避免重复扫描；7项测试通过，
仍promotion=0，不由上述局部证据推导全scorer索引域。
