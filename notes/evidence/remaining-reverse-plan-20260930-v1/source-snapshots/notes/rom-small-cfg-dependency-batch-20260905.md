# 短 CFG dependency 批次候选（2026-09-05）

当前 canonical 仍为 6,203,707 classified / 87,749 unknown，coverage SHA
`1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
本批复用固定 direct producer、有限 Thumb worklist 与 code→literal align4 模式。
以下 Tier-1 收据不是 canonical 或 formal 接入证明。运行目录：`build/experiments/active/cfg-dependent-small-packets/wrapper-dispatcher-boundary-preflight-20260905/`。

| packet | Tier-1 状态 | 候选 bytes/claims | 稳定 report SHA256 |
| --- | --- | --- | --- |
| callback-gaps-luna | 15项测试，独立 raw source/gap，Sol无P0/P1 | 10/5 | 254399f91b973cc849c6ee32f3b538cd222eea05d99e43bb4b45a489f34cec1f |
| wrappers-luna | 15项测试，独立 producer/source/opaque boundary，Sol无P0/P1 | 54/5 | ce14455c65d9fde171cb02ad329993008a4bc36b3318b9fa969fbcf330af2f9c |
| event-gaps | 4项测试，独立 source/boundary，Sol无P0/P1 | 14/7 | e90171c91efb69e559b7b3ceddd9918a5ee61475ac30a760aba0aabe07073863 |
| dispatcher | 8项测试，独立全分母与owner，Sol无P0/P1 | 40/4 | 11c9979d3735c131266bfeca8b6aa384b63afe4026271724b5d4b5225f7a9c8e |

四个已验包共118候选字节/21claims，达到同类4包Tier-2门槛。canonical尚未改动；
必须以真实落盘coverage集成重建总量，不能用加减法代替验收。

## 三个 wrapper

code范围 `[0x7ADE8,0x7ADFE)`、`[0x7B89C,0x7B8B2)`、`[0x9C12C,0x9C12E)`，
literal `[0x7AE00,0x7AE04)`、`[0x7B8B4,0x7B8B8)`。
全ROM目标限定direct producer共15个；上游event 1742条、text-BG 1330条指令从raw
closure重建；2个opaque目标必须是已有artifact精确block start。
21条指令、5blocks、3个indirect_pc_target；structured_return=0。
两个2B洞和任何opaque callee字节均未混入54B。
收据 `wrappers-luna/tier1-receipt-v1.json` SHA
`644b60f374208a8481e587892763ff5b8da97dd870f60bcd7f699c4f3e3670a3`。

审计例外：Luna原tdd.log中有两次未守卫GREEN尝试，首次TypeError、第二次通过；
它们不是guard证据，已原样保留。随后实际8项guard GREEN及父级15项guard GREEN通过。
父级修复Thumb-1 BL测试编码和未知/保留opcode误接受；一次reserved-opcode fixture
本身target越界，修正后对不可变Luna原版重新记录有效RED，再对修复版GREEN。

## Event-handler gap

七个2B洞起点：7E1BE、7E4BA、7E63E、7E76A、7E836、7E956、7EC5E。
独立重建22code/18literal ranges、53LDR bindings、1742instructions：7正gap、
11零长度邻接、4排除hole；14B候选+160B排除=174B完整holes分母。
4个BX r0保留indirect frontier，3个B目标都在source code。每个literal word均有真实LDR。
3个code→code短洞和154B rejected-root tail保持unknown；不声明padding/NOP/free space。
首次GREEN因literal claim kind缺armv4t前缀失败；已修正并通过4/4，原日志保留。
稳定两次报告在14:17:35Z–14:17:37Z完成，非降级，峰值190.37109375MiB。
收据 `event-gaps/tier1-receipt-v1.json` SHA
`9f41d24565ea28c2db7788dbe449b8ce85c1f9837407b4d8dc260d3ae199f749`。

## 接入约束

目前使用已提交、固定hash的notes/evidence coverage archive。原callback和wrapper
实验helper在此批内按hash复用，迁移时必须形成新的规范路径/公开合同，不能把ignored
build路径带进committed artifact。source full lifecycle/whole verifiers未在这些小包重跑，
报告明确保留false。正式publisher必须先独立验候选，原子no-replace且保持成员inode身份；
异常时保存owned stage，不按可替换名字删除。Tier-2统一coverage/proof/formal。

账户14:15UTC附近读取used32%、可验证剩余68%；继续前和里程碑前仍须实时重查。
未使用reset、未push，主代理已收回唯一writer。

## Dispatcher Tier-1 闭合（14:52 UTC）

根7DCB8，唯一producer7E86E，3blocks/15instructions/8edges，20slot/256u8输入。
32code+8literal+80table=120语义字节，80B既有owner只保留provenance，40B新增候选。
每个120语义字节单独变异均失败关闭；8/8测试非降级，峰值240.375MiB。
两次报告一致，稳定guard峰值203.40625MiB。收据SHA
`8f74c5401b4642136bd658f43d8e9654217fa9e9e7e4ecd83c640e005401955c`。
原Luna完成报告的helper摘要漏一个十六进制字符，父级重新计算正确SHA为
`44aa4a516f32efeb421c4f326ef4d99c756a06f571b2e641603b6aabc4839b9c`，
失败日志与随后有效RED均保留。未改变scope或放宽输入。
账户本次里程碑前used33%，可验证余量67%。恢复记录为run内
`resume-state-after-four-tier1.json`，全部4份receipt固定；无running heavy。

## 永久路径迁移（15:04 UTC）

四包独立producer/verifier及共享有限decoder已迁入`tools/rom_small_cfg_*.py`；
新公开合同在`tools/data/rom-small-cfg-dependency-v1/`，原实验合同/源码/receipt不变。
新合同只增加正式发布的明确前置门并重绑定永久helper路径/身份，语义分母与scope未变。
`tools/rom_small_cfg_dependency_packets.py`只负责输入路径/安全I/O组合，没有发布接口。
永久路径集成3/3及完整回归45/45通过，后者15:03:48Z–15:04:45Z、非降级、
峰值359.31640625MiB。第一次完整回归因测试fixture残留实验模块名而失败，修正后
全通过；原失败日志保留。
运行恢复记录`resume-state-after-permanent-paths.json`固定24份源码/测试/合同。
正式artifact publisher、canonical coverage、proof spec和新formal均仍待本批接入。
新文件尚未提交；HEAD仍0302f468，无push/reset，也没有新running heavy。
