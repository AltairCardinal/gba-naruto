# ROM 字节级逆向进度（2026-09-05）

- Goal active：当前任务 `01a06ff8-6905-78c1-9c36-ad357340ec4d`；用户已确认继续至
  `unknown_bytes == 0`。2026-09-05运行输入修复前账户可验证余量73%，不高于 5% 时
  停止新逆向写入。原 Goal 的累计用量只作历史记录。
- canonical 已真实重建：6,203,707 classified / **87,749 unknown** / 16,891 claims /
  18,664 segments，即 **98.60526720682780%**。本批净增 978 bytes / 21 claims。
- coverage SHA-256：`1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6`。
- proof SHA-256：`c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb`。
- 本批四包：fixed-index u8 tail 4 bytes、story-selector dependency CFG 80 bytes、
  task callback `0x078E38` closure 778 bytes、CFG proven-roots v21 116 bytes。
  四包已接入 canonical，Tier-2唯一formal已完成：106/106 contracts、ROM gate96/96，
  coverage errors=0；队列归零。后续123个selector与两处project摘要修复后重新formal，
  106/96仍全通过，global blocker从177变为175。A/B历史格式迁移已提交；干净B运行输入缺口正在修复。
- V21 按 TDD 修复 candidate 误验收、成员替换竞态两个 P1，packet 15/15；独立 official
  verifier 连续两次 report 相同。真实 canonical/proof/永久收据集成 **9/9** 非降级通过。
- coverage guard：2026-09-05 06:01:04Z–06:32:46Z，完成、exit 0、非降级，峰值
  owned-tree RSS 452.63671875 MiB。修复后formal耗时40分58秒、非降级、峰值525.7109375MiB。
- 原始 RED/GREEN、coverage guard 和输出已复制到
  `notes/evidence/rom-post-story-four-packet-tier2-20260905/`，manifest 逐文件固定哈希。
  收据测试不再依赖 Git 忽略的 `build/`。A=`47d9a60e668a5c3fe6e1123524864d21a2c93545`，
  B=`80faaebd2d441e94afbe7f0c7921609659f4d0fe`，64历史根完整通过冻结Git对象门禁。
  干净B的auditor导入暴露三份历史运行合同遗漏；当前以已提交原字节恢复入口修复，未push。
- 最新修复formal永久收据在`notes/evidence/rom-evidence-selector-repair-20260905/`，报告
  SHA为`aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc`；
  原前态和失败证据保持不变。candidate-v4已通过验真/重建并在A提交，旧candidate-v3保持拒绝。
- 边界：五个 task callback 2-byte holes 保持 unknown；V21 跨 owner BL 完整解码，
  只新增 unknown 后半字节；两包的 BX frontier 与 structured_return_count=0 保留。
- 下一候选仅有只读证据：三短入口合计54 bytes、dispatcher约40 bytes、另一 callback
  入口58 bytes；缺少各自完整 producer/field/index 合同，均未计入覆盖。
- 恢复入口：`docs/reverse-engineering-handoff-current-20260905.md`；本批细节：
  `notes/rom-cfg-proven-roots-v21-20260905.md`。原暂停点与入队时的历史数字由本段取代，
  写入前文本保存在同一 run 的 `*.before-tier2-doc-update` 中。

## 2026-09-04 双固定 pair-table 包与 Tier-1 审计提速

- `rom-fixed-pair-tables-v1` 已正式提升：`[0x53E00A,0x53E014)` 为 5 个
  signed-u16，`[0x53E014,0x53E034)` 为 `index&7`、`index<<2`、双 `LDRH`
  消费的 8×4-byte records；净增 42 bytes / 2 claims。左右邻接 gap 继续 unknown。
- Luna max 只产生一次 RED 后约 9 分钟无实现/无 blocker，按执行纪律失败中止；Terra
  medium 完成初版，本体补齐 accepted receipt、精确 claims、输出路径 guard、内核原子
  no-replace、symlink 失败关闭与结构化 verifier。9/9 packet tests、py_compile、正式
  artifact verifier 均通过。
- 正式 R2 manifest / payload / verifier SHA-256：`70bab2c2...233d` /
  `dae6a761...98dc` / `66c33983...9ee`。pre-hardening staged 候选只保留历史，不得引用。
- 最终路径复核新增 `build/experiments/../...` traversal RED；resolved-relative gate
  GREEN 后 9/9 packet tests 再过，旧 R1 official 移入 superseded，payload hash 未变。
- 两个新 Tier-1 包累计 +1,296 bytes / 16 claims：6,195,412 classified / 96,044
  unknown / 98.47342173258463%。authoritative canonical 仍是 6,194,116 / 97,340；
  未达到 4 packets、10 KiB 或 0.15pp，未运行 full coverage/proof/formal。
- current-unknown gate 由每包全 ROM atomization 改为线性 primary interval gate；同组
  5 项测试耗时 215.686s → 55.812s（约 -74%），重叠 primary/非法 role、range、ID
  仍失败关闭。历史四包 quick tests 也改为先从 canonical 剔除自身 batch 后按入队顺序
  重放；12 项首次 11 pass/1 stale arithmetic assertion，修正后该项单独通过。
- 本轮余额复查 `usedPercent=6`，约剩 94%，高于 5% 停止线。Goal 继续 active。

## 四包 Tier-2 里程碑与审计简化

- 第四包 `rom-bounded-index-u16-pair-table-v1` 闭合 `[0x53F2EE,0x53F30E)`：consumer
  unsigned `CMP #7/BHI` 支配两个 `LDRH`，index 乘 4，完整 8×4-byte denominator；
  8 records / 32 bytes / 1 claim。右侧 `[0x53F30E,0x53F310)` 保持 unknown。
- exporter/verifier 分别以 raw Thumb 位域和 vendored Capstone 独立重建 43-node CFG、
  guard/literal/stride/双 `LDRH` 数据流与唯一 index writer；8/8 packet tests、standalone
  verifier 和 Sol P0/P1 review 通过。manifest / payload / verifier SHA-256 为
  `d909fed8...8d04` / `d95ab9f3...af2` / `077037c6...de7a`。
- 真正的四包合并测试不是把前三包收益加常数：`FourQueuedPacketTier2CanonicalTests`
  检查 canonical 内 45/2,532、1/1,136、14/1,162、1/32 四组 claim/bytes、跨包零重叠、
  右侧 gap unknown 和非降级 guard receipt；proof spec 另绑定八个 artifact evidence。
- coverage 首次运行因 `idle-timeout=1800s` 在 30:00 误杀，当时仍 100% CPU；canonical
  未写。R2 把 idle 提至 3,600s 后 38:37 完成，峰值 444.24609375 MiB。一次误判为
  “轻量”的 proof structural 重放在 83 秒确认仍会全量 rebuild 后主动终止。这两项均计入
  可避免浪费并保留 receipt。
- 正式 formal 只运行一次，48:36、峰值 532.828125 MiB、非降级；106/106 structured
  contracts 均 `exit_code=0`、`contract_ok=true`。今后无 stdout 的 coverage/formal
  idle 上限不得低于 120 分钟；一级单包不重复 full，四包或其他阈值到达时才统一执行。

## 第三个一级快速包：battle-distance dispatcher

- AI 配置表 `[0x53F348,0x53F86C)` 暂缓：`unit+0xCD` 来自记录字段复制，尚未闭合
  runtime config-ID 的 `0..7` writer/lifecycle 分母；8 行物理布局不能替代动态边界证明。
- 已改走 accepted dispatcher：`0x083B3C` 使用 unsigned `LDRB`，`CMP #6` / `BLS`
  精确闭合 7-slot `[0x083B5C,0x083B78)`；table roots 为 `0x083B78`、`0x083BAC`、
  `0x083C8A`、`0x083D20`、`0x083DAE`、`0x083E38`、`0x083F0E`。
- bounded closure 为 555 instructions / 126 blocks / 1,110 code bytes / 24 consumed
  literal bytes；25 条 exit 只进入 upstream accepted `0x083FEA` / `0x083FFA`，0
  frontier。`[0x083F52,0x083F54)` 与 `[0x083FBE,0x083FC0)` 共 4 bytes 保持 unknown。
- packet tests 7/7、Tier-1 quick projection 3/3、standalone verifier 均通过；Sol medium
  首轮除“生成 committed artifact”这一阶段性 P1 外无其他 P0/P1，该 P1 已通过正式
  原子发布与 official verifier 关闭；最终复核又发现新 code claim 未登记 CFG registry，
  已用 RED/GREEN 将其加入 `thumb_only`，避免 Tier-2 `build_manifest()` 失败。manifest /
  payload / verifier SHA-256 为
  `ce7844f6...5fa2` / `2b8efd1f...c718` / `8f6f3ce4...5716`。
- 本批三包累计 +4,830 bytes / 60 claims，投影为 6,194,084 classified / 97,372
  unknown / 98.45231374104819%。尚未达到
  10 KiB、0.15pp 或 4 packets，canonical 仍为 6,189,254 / 102,202；未运行 full
  coverage/proof/formal。

## 一级快速审计队列

本节下方保留各 packet 入队时的历史投影；四包现已全部接入，上方 canonical 为唯一
authoritative 状态，旧的“尚未改写 canonical”描述仅用于还原审计过程。

- `rom-boot-state-dispatcher-cfg-v1` 已作为新批次第一包通过一级快速审计。上游 accepted
  continuation claim 内唯一 `0x06109A BL -> 0x064670`，dispatcher 以
  `state[0x03005CBC] & 7`、减一及 unsigned `<=5` 冻结 6-slot table，再调用五个 roots。
  target closure 为 1,116 instructions / 2,248 code bytes / 188 consumed literals；
  dispatcher 96 bytes，合计 2,532 bytes / 45 claims，12 个 2-byte holes 保持 unknown。
- Luna max 复核发现 `0x063C84` 把 SP 交给 opaque `CpuFastSet`，原始 0-frontier 证明不足；
  已新增 SWI `0x0C` wrapper、fill-mode `0x01000050`、EWRAM destination、唯一 SP alias、
  所有 SP-relative stores 与 saved-LR `SP+0x30` 副合同。Sol medium 再发现 B/Bcond
  denominator 测试缺口；已补 synthetic B/Bcond extra-producer mutation，verifier 改为
  独立位级解码并用 vendored Capstone 二次确认。最终 Sol 复核无 P0/P1。
- packet tests 7/7、quick projection 3/3 通过；official verifier 连续两次 report SHA
  均为 `46240245...7002`。manifest / payload / verifier SHA-256 为
  `c3296d25...6004` / `ac14c13a...0465` / `5b373b90...a802`。预计 canonical
  6,191,786 classified / 99,670 unknown / 98.41578801472983%，即 +0.04024505615234375pp；
  当前仅 1 packet / 2,532 bytes，未达到二级门槛，故未运行 full coverage/formal。

- `rom-battle-condition-result-text-v1` 已通过一级快速审计：完整物理条件表为
  47×3×2×4 = 1,128 行，其中 230 个 active slots 经公共仲裁路径读取 payload `+4`，
  绑定 result renderer、parser 与 SJIS 查表；219 个唯一 NUL 终止记录共 3,961 bytes，
  219 claims，独立 verifier `verified=true`，packet tests 6/6、coverage projection tests
  3/3 通过。
- 该 packet 当前只进入待接入队列，**未改写 canonical**。基于 coverage
  `b71a91d1...ed52` 的失败关闭投影为 6,180,394 classified / 111,062 unknown，即
  98.23471705118814%，较 canonical 预计增加 0.0629583994547526 个百分点。
- 批量门槛累计为 3,961 bytes / 1 packet，尚未达到 10 KiB、0.15 个百分点或 4 packets，
  且不解除上游 blocker，因此 full coverage rebuild 与 formal proof 按分层审计规则延后。
  收据见 `build/experiments/active/battle-condition-result-text-20260902/codex-r1/quick-projection.json`。
- 明确保留 unknown：2,782 bytes inter-record gaps、`[0x9974,0x9980)`、6-byte
  `[0x9980,0x9986)` script 与 `[0x9986,0x9F2E)`；positions group47 只是物理别名，
  不能作为第二份独立 provenance。
- `rom-alternate-dialogue-table-v1` 作为第二个 packet 通过一级快速审计。直接调用
  `0x08F9F0 (r0=3,r1=0) -> 0x0914D8` 的 CpuSet 清零、index 自增、`CMP #19`、唯一
  state-zero backedge 与退出路径共同证明完整索引域 `0..19`。精确闭合 20×20-byte 表
  400 bytes、80 条 renderer text 1,214 bytes、80 段 parser-bound zero gap 1,586 bytes，
  合计 3,200 bytes / 161 claims；packet tests 7/7、coverage projection tests 3/3、独立
  verifier 均通过。
- 两包累计投影为 +7,161 bytes / 380 claims：6,183,594 classified / 107,862 unknown /
  98.28557968139648%，预计较 canonical 增加 0.11382102966308594 个百分点。仍未达到
  10 KiB、0.15 个百分点或 4 packets，故 canonical 与 formal 哈希继续保持本文件顶部
  数值。收据见
  `build/experiments/active/alternate-dialogue-table-20260902/sol-r1/parent-quick-projection.json`。
- `[0x45832C,0x458794)` 1,128 bytes 继续 unknown；computed/indirect `0x0914D8`
  producers 未穷尽，不外推所有自然入口、Unicode、编辑/写回/重定位或 free space。
- 第三包 `rom-story-state-callback-cfg-v1` 闭合固定 scheduler callback root
  `0x0808F73C`：678 code + 24 consumed literal = 702 bytes / 13 claims；四个 2-byte
  holes 保持 unknown。第四包 `rom-story-state-entry-c4cc-v1` 由 callback 内唯一
  `0x08FA26 BL -> 0x08C4CC` 解锁，闭合 184 code + 36 literal = 220 bytes / 2 claims；
  `[0x08C5A8,0x08CBB4)` 的 1,548 bytes 明确保留 unknown。
- 四包累计达到二级门槛并已原子接入 canonical：+8,083 bytes / 395 claims，正式
  coverage R6 耗时 32 分 12 秒、峰值 390.5234375 MiB；formal 耗时 42 分 41 秒、
  峰值 519.3046875 MiB、非降级，106/106 与 ROM gate 96/96 全部通过。
- 无效浪费：R1 因 30 分钟 idle timeout 误杀；R2/R4/R5 分别暴露日志缺失、CFG kind
  registry 未同步和 Thumb mode 未声明，均失败关闭且未改 canonical。后续里程碑必须先
  运行“四包合并 + CFG aggregate”定向预检，并为长静默任务设置不少于 120 分钟 idle。
- 新一轮第一包 `rom-text-bg-loop-continuation-v1`：当前已分类 source owner
  `[0x08B640,0x08B64E)` 解除旧 V15 blocker；全 ROM target-limited denominator 只有
  `0x08B644 BL -> 0x08ACC8`。精确晋升 `[0x08ACC8,0x08ACF2)` 42-byte Thumb code 与
  `[0x08AEB4,0x08AEC0)` 12-byte consumed literals，共 54 bytes / 2 claims、0 frontier。
  13/13 packet tests、4/4 quick projection tests与独立 verifier 通过；投影为
  6,184,570 classified / 106,886 unknown / 98.30109278361002%，canonical 仍保持顶部
  数值。本批 54 bytes / 1 packet / 0.000858pp，未达二级门槛。
- Sol P0/P1 review 发现 `consumer_code_slice` 明示非 instruction-only、mutable coverage
  自失效、opaque boundary 未绑定、非原子 NOREPLACE 与 symlink/mutation 测试缺口；已全部
  失败关闭修复。最终合同新增 `0x08B58C..0x08B60A -> 0x08B644` 的 55-instruction /
  130-byte source membership path、两处已验证自然 entry caller、`0x08ACF2` owner、
  immutable historical receipt、post-promotion replay、原子 no-replace + fsync。
- Luna max 只完成 RED 后超过 6 分钟无写入且无 blocker，本体接管 GREEN；这是模型
  执行纪律问题，不是环境阻塞。系统内存 free 71%。
- `[0x04BE31,0x04C616)` 的 2,021-byte chapter-shaped gap 保持 unknown：假设根可解析
  2,020 bytes，但全 ROM 无任何直接 pointer/root，左侧脚本已 terminal，scenario 54/55
  固定表明确跳过该区间。形态可解析不等于真实消费者读取。
- 第二包 `rom-boot-copy-sources-v1` 精确晋升 `[0x0004C8,0x000734)` 620 bytes / 1
  claim。唯一 `0x060FE0 BL -> 0x061624` 绑定 9 条 DMA3 descriptor 的完整本地
  consumer；其中 3 条命中候选。另由 V12 `0x06459E` 与 boot `0x0646DE` 两次
  CpuSet 覆盖尾部，五个 source range 的 union 恰为 620 bytes。artifact manifest /
  payload / verifier SHA-256 为 `040e009c...a464` / `aeecd2f0...f59b` /
  `57c336d3...189a`；14/14 packet tests、3/3 quick projection 与独立 verifier 通过。
- Sol 复核发现并已修复三项 P1：V12 目的地址由错误的 `0x03000200` 更正为 ROM
  literal `0x03005CE8`；verifier 现在独立解码 112 条 local CFG 指令并由 raw Thumb
  dataflow 重建全部 9 条 DMA descriptor；`rom`、`upstream_evidence` 与完整
  `promotion` 合同均逐字段失败关闭。两个待接入包累计投影为 6,185,190 classified /
  106,266 unknown / 98.31094741821289%，即 +674 bytes / +0.010712941487630207pp /
  2 packets，仍低于二级门槛，canonical 保持顶部数值。
- 第三包 `rom-text-bg-task-closure-v1` 以已排队 `0x08ACC8` continuation 和冻结
  `character-runtime-oam-task-bindings-v1` 的 `task+0x28` 字段为依赖，独立重放
  `0x08ADCE` callback literal、`0x08ADD0` stack arg、`0x062760` allocator store、
  `0x06294C` dispatch load 与 `0x09C114 BX r1` wrapper。十个 Thumb roots合计
  1,330 instructions / 2,782 full code bytes / 80 literal references / 65 unique words；
  扣除已排队及 canonical owner 后净晋升 2,692 code + 248 literal = 2,940 bytes /
  34 claims。9/9 packet tests、3/3 quick projection 与独立 raw-Thumb verifier 通过。
- 旧角色 OAM artifact 的整体验证器当前因 `parent OAM bindings are not independently
  verified` 返回 false；本包没有掩盖该状态，只哈希绑定 artifact/verifier，并独立重放
  所需 task-field/allocator/dispatcher ROM 链。三包累计投影为 6,188,130 classified /
  103,326 unknown / 98.3576774597168%，即 +3,614 bytes / +0.05744298299155pp /
  3 packets；canonical 仍保持顶部数值。

## 2026-09-02 固定动画描述器组一级审计

- `rom-fixed-animation-descriptor-groups-v1` 作为当前批次第二包通过。调用点
  `0x071EC0/0x071EC2` 装入 `0x12D964/0x12D9D4` 双表，前置比较把 `r2` 冻结为
  `0..3`；`0x0626B4` allocator 将 group/slot/bases 写入对象
  `+0x14/+0x16/+0x1C/+0x20` 并把 slot 初始化为 0。
- renderer 只在 next group entry 不是 `0xFFFF` 时递增 slot，故每组只消费 3 records；
  12-slot pointer table 恰指向 12×`0x54` descriptors。`0x0631F6..0x063208` 又以
  `0x14` stride 前进，在 next entry head 为 `-1` 时停止；每个 descriptor 为 4 entries
  + `0x0000FFFF` terminator。
- 净投影 `[0x12D574,0x12D9E4)` 1,136 bytes / 1 claim。11/11 packet tests、3/3
  quick projection、独立 verifier 与最终 Sol P0/P1 review 全部通过。manifest / payload /
  verifier SHA-256 为 `83e526c5...ff05` / `8afa72be...5e3b` / `9555d5bf...6e529`。
- 两包累计 +3,668 bytes / 46 claims，投影为 6,192,922 classified / 98,534 unknown /
  98.43384424845377%，较 canonical +0.058301289876302086pp；仍仅 2 packets、低于
  10 KiB/0.15pp/4-packet 门槛，故 canonical coverage/proof/formal 保持不变。

## 2026-09-05 pre-battle controller CFG 与审计简化

- `rom-prebattle-menu-controller-cfg-v1` 已正式发布。唯一 producer
  `0x08F894 BL -> 0x08F190` 绑定上游 story-state callback owner；六项 jump table
  解除 `0x08F392` frontier。raw closure 为 786 instructions / 1,752 bytes，净晋升
  1,564 code + 332 literals + 24 table = 1,920 bytes / 52 claims，保留 7 个间接 frontier。
- Sol reviewer 提出的 union 未派生、producer owner 回显两个 P1 已用 mutation
  RED/GREEN 关闭。packet suite 12/12、candidate/official 独立 verifier 均通过；正式
  manifest / payload / verifier SHA-256 为 `51824fc2...712d` /
  `ed05a078...ae13` / `f82f0778...908`。
- 上游完整 verifier 已从每个 mutation 的内层 `_producer()` 移到 exporter/verifier
  发布入口；内层仍绑定上游规范 JSON、accepted manifest、702-byte promotion、精确 owner
  claim 和当前 coverage owner。release-gate 定向测试由 14.3s 失败变为 4.2s 通过，完整
  12-test suite 为 68.8s；正式发布时仍真实运行上游 verifier。
- 新批三包累计 +3,216 bytes / 68 claims，Tier-1 overlay 为 6,197,332 classified /
  94,124 unknown / 98.50393931070963%，相对 canonical +0.051116943359375pp。
  authoritative 仍是 6,194,116 / 97,340；3 packets / 3,216 bytes 未达 Tier-2 门槛，
  不运行 full coverage/proof/formal。
- 下一优先包为 `[0x46401C,0x464534)` 的 1,029-byte 主 packet；98-byte alignment gaps
  必须另立 packet。余额复核 `usedPercent=10`，约剩 90%，Goal 继续 active。

## 2026-09-05 story dependency 与 CFG proven-roots v20

- `rom-story-callback-dependency-closures-v1` 已正式发布并完成 Tier-1：9 roots /
  762 instructions / 1,932 unknown bytes / 32 claims，保留六个 2-byte holes；immutable
  precoverage 避免 canonical 前进后自失效。
- `rom-cfg-proven-roots-v20` 随后发布。全 ROM target-limited 分母恰有两个 producer；
  只接受 instruction-only owner 中的 `0x06108E`，拒绝 `consumer_code_slice` 中的
  `0x061320`。闭包为 1,405 instructions / 249 blocks，净晋升 1,070 code + 80
  literal = 1,150 bytes / 18 claims，三个 BX frontier 保持 unresolved。
- v20 packet tests 9/9、Tier-1 projection 3/3、candidate/official 独立 verifier 均
  通过。两包累计 +3,082 bytes / 50 claims，投影为 6,201,429 classified / 90,027
  unknown / 98.56905937194824%。authoritative canonical 仍是 6,198,347 / 93,109；
  2 packets、3,082 bytes、+0.048987pp 未达 Tier-2 门槛，不运行 full proof/formal。
- Luna max writer/reviewer 两次出现长时间无产出且无真实 blocker，已停止并由 Sol
  medium 与父代理复核；该成本记为模型执行浪费。余额复核约剩 87%，Goal 继续 active。

## 2026-09-05 story-next dependency CFG

- `rom-story-next-dependency-cfg-v1` 已正式发布并完成 Tier-1。全 ROM target-limited
  producer 分母为两项，只接受 story owner 中的 `0x08F928`，拒绝 unknown owner 中的
  `0x08F61A`。闭包为 338 instructions / 96 blocks / 770 code bytes，21 个 consumed
  literal words / 84 bytes、43 条 opaque calls、3 个 unresolved BX frontiers。
- 精确净投影 854 bytes / 19 claims；五个 2-byte holes 保持 unknown。正式 manifest /
  payload / verifier SHA 为 `a5429f89...669` / `d12f4b28...e6b` /
  `ed5b3581...fa8`。packet suite 10/10、Tier-1 projection 3/3、candidate/official
  independent verifier 全部通过，guard 峰值 260.6 MiB，非降级。
- 新批三包累计 +3,936 bytes / 69 claims；线性 current-unknown 投影为 6,202,283
  classified / 89,173 unknown / 98.5826333363851%。authoritative canonical 仍为
  6,198,347 / 93,109；不运行 full coverage/proof/formal。余额复核约剩 86%，Goal
  继续 active。

## 2026-09-05 boot register-init dependency CFG 与四包 Tier-2

- `rom-boot-register-init-dependency-cfg-v1` 已正式发布。唯一 producer
  `0x06109E BL -> 0x06178C` 绑定 boot continuation 的 exact block；worklist 为
  154 instructions / 12 blocks / 318 code bytes，32 个唯一 consumed literal words /
  128 bytes，三条 opaque call 绑定 CFG inventory exact entry，三个 `BX r0` 保持
  unresolved。
- 净晋升 446 bytes / 8 claims；`[0x06181E,0x061820)` 继续 unknown，
  `[0x0620B4,0x0620CC)` 保留三个既有 boot-handoff owners。manifest / payload /
  verifier SHA 为 `367a72b1...a932` / `ec89abce...22bd` / `6710e77a...ff91`。
- TDD 经缺实现 RED、vector-schema RED 与三个 P1 RED 后，父代理复跑 packet 15/15；
  Tier-1 3/3、四包合并 13/13、candidate/official verifier 均非降级通过。
- story callback、v20、story-next、boot register-init 四包累计 4,382 bytes / 77 claims，
  达到 4-packet Tier-2 门槛。唯一 coverage rebuild 耗时 30 分 20 秒、峰值
  439.7265625 MiB，authoritative 更新为 6,202,729 classified / 88,727 unknown /
  16,870 claims / 18,641 segments，即 98.58972231547037%；coverage SHA 为
  `2cc07bc7...c01`。
- proof SHA 为 `3655c4a2...05ce`。唯一 non-degraded formal 耗时 40 分 46 秒、峰值
  534.92578125 MiB；report / guard SHA 为 `3971d9ea...ac3b` /
  `88d11d5f...26a`，106/106 contracts、coverage gate 96/96、errors=0。
  `complete=false` / 177 blockers 来自 88,727 unknown 与既有全局门。
- 简化审计本批无 coverage/formal 重跑浪费。Luna max 的约 5 分钟无实现等待记为模型
  执行浪费，Sol medium 与父代理接管后完成。余额复核约剩 85%，Goal 继续 active。

## 2026-09-05 fixed-index u8 tail 一级审计

- 新批第一包 `rom-fixed-index-u8-tail-v1` 由唯一 table-base literal/consumer 与四个
  immediate caller 证明 `[0x53E492,0x53E496)` 的 `2b 2c 36 3f`，只投影 4 bytes /
  1 claim。全 ROM 有 13 条 direct BL；除四条 fixed caller 外的九条只标作
  `excluded_non_fixed`，不声明 index provenance，也不外推完整 114-byte 表。
- Luna max 完成正确 RED 后约 5 分钟无产品实现且无 blocker，已停止；Sol medium 完成
  GREEN。父级只读 review 发现并通过 TDD 关闭三个 P1：非固定 caller 过度命名、owner
  只验起点、`..` 输出路径可先创建目录。加固后 packet suite 13/13、Tier-1 3/3、独立
  verifier `verified=true/contract_ok=true`；两次父级 guard 均非降级，峰值分别
  210.01953125 / 184.88671875 MiB。
- 随后先用 TDD 冻结共享 immutable precoverage；manifest / gzip SHA 为
  `95cb2fef...e65a` / `88365f67...a6b6`，小包已证明不再读取 live coverage。最终
  manifest / payload / verifier SHA-256 为 `4e8bbe70...fa88` /
  `25c49e18...2666` / `ab5ee9ab...a11f`。authoritative canonical 仍为
  6,202,729 classified / 88,727 unknown / 98.58972231547037%；一级队列为 1 packet /
  4 bytes，线性投影为 6,202,733 / 88,723 / 98.58978589375815%，未触发 Tier-2，故没有
  运行 full coverage/proof/formal。余额仍约 85%，Goal active。

## 2026-09-05 story-selector dependency CFG 一级审计

- 新批第二包 `rom-story-selector-dependency-cfg-v1` 由已接受 story callback owner 中的
  `0x08F8DE BL -> 0x08F544` 证明 `[0x08F544,0x08F594)` 的 80-byte Thumb root；
  同目标 `0x08F676` 因 source owner 仍为 unknown 被拒绝。全 ROM direct internal-entry
  分母恰为 2，raw worklist 为 37 instructions / 80 bytes / 3 opaque calls / 0 holes /
  0 frontier；literal 与末端 fallthrough 都保留既有 coarse owner，不重复晋升。
- Luna max 约 2 分钟未落 RED 后停止，Sol medium 完成初版。父级 reviewer 发现“向量与
  CFG 分母只回填常量”和“普通 rename 存在 TOCTOU”两个 P1；本体按 TDD 加固为独立
  raw worklist 与平台原子 no-replace。最终 packet 10/10、Tier-1 3/3、official verifier
  全部 non-degraded 通过；合并回归 32/32、峰值 341.57421875 MiB。manifest / payload / verifier SHA-256 为
  `c810e710...19ec` / `9909ace4...676` / `5bafd0fe...9d10`。
- authoritative canonical 仍为 6,202,729 classified / 88,727 unknown /
  98.58972231547037%。当前 Tier-1 队列为 2 packets / 84 bytes / 2 claims，线性投影为
  6,202,813 / 88,643 / 98.59105745951334%；未达 4 packets、10 KiB 或 0.15pp，故按
  简化审计规则不运行 full coverage/proof/formal。余额复核约剩 84%，Goal active。

## 2026-09-05 task callback 0x078E38 closure 一级审计

- 新批第三包 `rom-task-callback-078e38-closure-v1` 以唯一 ROM pointer occurrence
  `0x079378`、source `0x0792BE..0x0792CA`、allocator `task+0x28` 写入和 scheduler
  `task+0x28` 读取/`BX r1` dispatcher 链绑定 root `0x078E38`。全 ROM direct
  BL/B/Bcond 到 root/internal entries 的外部命中为 0，pointer 是唯一静态 producer。
- raw worklist 为 342 instructions / 61 blocks / 718 code bytes，15 个唯一 literal
  words / 60 bytes，17 opaque calls / 7 targets。五个 2-byte holes 保持 unknown；
  `0x079144: bx r0` 因 opaque callees 的 SP/内存副作用未闭合，保守保留 1 个
  `indirect_pc_target` frontier，明确不声明 structured return。
- Sol medium 完成 scout 与初版；父级 reviewer 发现 verifier 可漏字段/语义篡改、
  structured-return 超证据、路径 TOCTOU 和最终验证后 staging 名称可替换四个 P1。
  父代理新增 RED 后改为 exact payload/manifest 重建、candidate/accepted 双阶段独立
  验真、dirfd/O_NOFOLLOW/held-inode 绑定与原子 no-replace；并把 direct denominator
  修到覆盖 ROM 最后一个 halfword。
- 正式 manifest / payload / verifier SHA 为 `a9441633...7ca0` /
  `ac163dad...e1aa` / `46ad2406...6f14`。packet 13/13、Tier-1 3/3、三包合并
  22/22 均非降级通过；合并耗时 4 分 36 秒、峰值 360.3125 MiB；最终只读 P0/P1
  reviewer 无发现。
- 本包净晋升候选 778 bytes / 16 claims。当前队列三包累计 862 bytes / 18 claims，
  线性投影为 6,203,591 classified / 87,865 unknown / 98.60342343648275%；仍低于
  Tier-2 门槛，canonical 保持 6,202,729 / 88,727，不运行 full coverage/proof/formal。

## 2026-09-05 post-story四包 Tier-2 验收

四包真实净增978 bytes / 21 claims；canonical 6,203,707 / 87,749，真实集成9/9。
正式formal report / guard SHA：
`099580ad012729bbce697779cae732ef8678a0966c2669dad51cce0f58f79f00` /
`735b9505208758cd009c77d9a59d84f076d47181c9f2fb920d3bd4519f80d891`。
106/106 contracts、ROM gate96/96通过，coverage errors=0，唯一coverage结果在进程内复用。
全局complete=false / 177 blockers保留；不能把本批验收说成整体100%。
全部收据已固定到notes/evidence，接入队列为0。下一步先解决64个历史artifact根的提交
格式迁移，再按精确依赖闭包提交；不改旧manifest原字节，不绕过hook，不重复当前full审计。
