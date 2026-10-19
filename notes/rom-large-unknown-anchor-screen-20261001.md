# 17个大未知段的消费者锚点筛选

状态：可复现只读候选筛选，promotion=0。复用unknown cluster工具与固定CFG literal
预检模式；永久收据`notes/evidence/rom-large-unknown-anchor-screen-20261001-v1/`。
当前ROM SHA1198ece7…9d05b、coverage SHAb568db6f…cf06d2，完整值绑定输出inputs。

## 方法和分母

既有`tools/analyze_rom_unknown_clusters.py`重算完整连续coverage partition；17段至少
1KiB、合计42,880B。新研究脚本只扫描两类机械锚点：全ROM每4B对齐word指向该17段，
及canonical显式Thumb代码类别内每2B的PC-relative LDR形态，交叉解码原半字/Capstone。
LDR扫描域为171,916B/4,039个segment，精确class列表在输出；不包含全部CFG代码、
ARM、RAM、computed或未对齐来源，也未重新验证来源artifact及完整指令边界/参数流。
coarse consumer_code_slice不入域。计数是形态命中，**不是已证明消费者数**。

| ROM范围 | unknown B | 对齐word形态 | Thumb LDR形态 |
| --- | ---: | ---: | ---: |
| 00578C..007554 | 7,624 | 185 | 0 |
| 53F89C..541368 | 6,860 | 13 | 9 |
| 0042AB..00542E | 4,483 | 133 | 31 |
| 54136F..542204 | 3,733 | 0 | 0 |
| 59EAE0..59F560 | 2,688 | 4 | 9 |
| 0A1954..0A2154 | 2,048 | 8 | 0 |
| 04BE31..04C616 | 2,021 | 0 | 0 |
| 599924..599F5C | 1,592 | 3 | 3 |
| 000CEA..0012F0 | 1,542 | 108 | 0 |
| 5A4708..5A4CE8 | 1,504 | 0 | 0 |
| 009974..009F2E | 1,466 | 54 | 42 |
| 53F30E..53F86C | 1,374 | 3 | 3 |
| 001781..001CD0 | 1,359 | 40 | 22 |
| 5AE364..5AE800 | 1,180 | 21 | 7 |
| 12EE10..12F298 | 1,160 | 122 | 115 |
| 45832C..458794 | 1,128 | 143 | 116 |
| 53E034..53E492 | 1,118 | 14 | 13 |

## 会改变下一步顺序的锚点

1. **45832C..458794优先研究。** 6F90C/6F90E分别加载45854C/458558，再由6F914调用
   626B4；71044/71046加载458510/45851C，71060同样调用626B4。已有固定动画描述器组
   exporter/verifier绑定这个allocator，626B4..62766本轮原字节SHA匹配已有合同
   09cd85fb…6d804。可复用allocator字段、renderer step/advance研究方法，先冻结不同
   caller的group/slot和两种base值，逐个证明实际descriptor与sequence stop。不能直接
   套用旧12D574表的0x54 stride，也不能把两指针差12或143个word形态当整段结构证据。
   该簇原来没有完整消费合同，现在至少有多条固定入参路径，值得在352B文本delta之后
   优先做一次完整合同预检，再考虑高成本AI生命周期。
2. **12EE10..12F298第二顺位。** 6E1C2把12EE10送r1、r2=12，6E1C6调用9C3EC，提供
   最小固定12B复制候选，不能外推1,160B整段。6E374/6E382把后续targets送r2，分别调用
   85A40/85B8C；短窗口显示它们把r2存入RAM，没有直接读取ROM文本。因此还需追RAM
   consumer和生命周期，ASCII标签形态/大量LDR都不能代替parser边界。不要为12B单独
   开一次全量审计；与相同固定copy合同的候选批量处理。
3. **低文本/脚本段沿用既有解析器。** 42AB段31点、9974段42点、1781段22点可先与
   已接受及待接入renderer ranges去重，筛选固定参数流。578C及CEA的零LDR仅表示没有
   “直接PC-relative target”命中，185/108个对齐word可能来自表，不否认索引消费者。
4. **AI保持完整域要求。** 53F89C段9个LDR包括6E2B2→5411E4等既有锚点；不是一条
   初始化writer即可证明所有记录。59EAE0虽有9点仍保留既有拒绝/lifecycle门禁，不得
   因计数重扫又打开may-read扩张。
5. **三段零形态只作为搁置条件。** 54136F、04BE31、5A4708合7,258B在本次两种编码
   分母内零命中，优先等待新上游入口/动态访问锚点；不说明无computed/unaligned/RAM
   消费者，不是padding或free space证明。不能作为“没有被使用”的负证据。

## 验证和复用

两次anchors JSON逐字节一致，和既有cluster工具独立重算的17段/42,880B一致；guard
exit0且非降级。有限窗口raw hex/SHA和allocator历史身份保存于windows.json，线性
反汇编包含literal，不是CFG闭包。没有Tier-1、TDD生产功能、来源完整verifier、mGBA
或formal验收；不改ROM、coverage/proof，未提交。

从根目录复跑`PYTHONPATH=. python3 notes/evidence/rom-large-unknown-anchor-screen-20261001-v1/anchors.py`，
需要匹配冻结ROM/coverage，输出stdout JSON；新输出写新run，勿覆盖永久收据。
源码/输入身份变化时重新冻结研究，而不是改旧manifest。该研究模式仍为固定literal
低成本筛选，只有完整producer→consumer合同成立才进入TDD生产包。

- [ ] 查看anchors.json → class域、每条site/literal/target与表格计数吻合。
- [ ] 查看windows.json → 两对固定base进入626B4，但没有宣称描述器长度已知。
- [ ] 查看12EE10路径 → 12B copy与RAM存指针分开，整段仍unknown。
- [ ] 下一轮研究顺序 → 同类文本delta、固定动画描述器、RAM文本链，再评估AI完整生命周期。
