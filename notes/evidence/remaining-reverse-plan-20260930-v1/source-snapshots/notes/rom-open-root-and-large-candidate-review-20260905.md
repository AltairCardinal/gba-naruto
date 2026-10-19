# 尚未闭合的大范围与 callback 入口（2026-09-05）

本记录为现有证据的只读复核，不是新分类或producer穷尽证明，bytes_promoted=0。
ROM固定SHA：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。本次未重新执行全ROM扫描。

## 08F654 必须保留 producer frontier

`tools/verify_rom_scheduler_callback_lifecycle_gate.py` 将 `0x0808F654` 纳入待证明callback，
但其producer/slot/ABI没有闭合，已注册的8F73C与8EF2C不能替代它。
8F644 BL→8A0F0，8F648 POP {r1}，8F64A BX r1后没有fallthrough；
`[8F64C,8F654)`是020311D4、02026804两个literal word，不能线性解码越过它们
把8F654当成既有入口。

在“假设8F654是根”的局部解码中可见22条指令/48code bytes，范围
`[8F654,8F65E)`与`[8F664,8F68A)`；LDR8F65A消费`[8F660,8F664)`。
8F65C B→8F672；BL8F668→8F618与8F676→8F544只提供下游目标。
8F688 BX r0仍为indirect_pc_target，不能称为structured return。
已有story-selector包明确排除了unknown source8F676。假设根的局部闭包不是根证明。

早期窄ADR窗口`[8F000,8FA40)`没有找到指向`[8F640,8F660)`的地址形成，这只是
局部负结果，不是全局computed producer不存在。保持59EAE0 lifecycle gate的
keep_unknown、停止其writer/inheritance与抽象索引扩张要求。
复核窗口的raw hex与SHA位于本批run的`readonly-scout-recovery.json`，其window SHA
`5f8b336f1e7512fd7474231d047803256476ebd526696f8975e96cfac6d56fc6`；gate源码SHA `70d7d3618adf124fc43a3f08acf6b294d1bbbcd412b048ff96c0556dfcc92878`。

## 后续大范围方向仅列研究入口

Sol medium 从现有0902/0905 unknown-cluster记录只找到一个具有正向消费锚点、
预计超过1KiB的后续研究方向：AI配置表`[53F348,53F86C)`，旧估算unknown交集1316B。
`tools/analyze_battle_ai_utility_policy.py:27`固定基址与8×0xA8布局，126起有逐记录读取；
`notes/battle-ai-utility-policy-bindings-20260723.json:93`关联unit+CD。
现分析器的hash/内容断言不能替代实际消费者指令与索引上界。
`notes/rom-unknown-cluster-refresh-20260902.md:171`已记录consumer前没有<=7，writer
只从source record+0E复制到unit+CD。需先闭合完整source-record producer/index/lifecycle，
否则继续unknown。这不是已冻结packet，不计Tier-1收益，也不立即扩张生命周期假设。

其余大范围材料不足：4BE31..4C616虽grammar可解析但无producer/root且固定表跳过；
A1954..A2154不在固定glyph分母；53F89C..541368的14个疑似LZ77头均无效；
54136F..5421FC只有高零比例；5A4708..5A4CE8无base/parser锚点；8C5A8..8CBB4无
已分类direct producer，表观pointer位于data。不得为凑足候选数或100%进度而晋升。
