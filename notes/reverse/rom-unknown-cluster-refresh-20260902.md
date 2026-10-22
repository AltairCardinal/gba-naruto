# Unknown cluster refresh（2026-09-02）

## 初始输入与总量（历史快照）

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- coverage SHA-256：`e48c8f6d0df1d3469be2336caa71f628d82a51d4e637d6df42ebded412359c36`
- unknown：106,940 bytes / 1,651 ranges。
- 23 个范围长度至少 1,024 bytes，合计 66,907 bytes；这只是候选集中度，不是可晋升量。

## 最大候选族

| 范围或邻接族 | 字节 | 当前判断 |
| --- | ---: | --- |
| `[0x007F1D,0x009F2E)` | 8,209 | 位于 training text 与 chapter record 之间；需真实 parser/consumer 分母，不能按邻接晋升 |
| `[0x00578C,0x007554)` | 7,624 | value-range text 与 training script 之间；可能混合结构，需消费者解引用 |
| `[0x53F89C,0x541368)` | 6,860 | 14 个 LZ77-syntax 邻接子段；大量零字节不能证明 padding/free space |
| `[0x0003E0,0x001CD0)` | 6,384 | boot literal pool 与 text record 之间；启动路径未闭合，不得按包络晋升 |
| `[0x0042AB,0x00542E)` | 4,483 | 两种文本 owner 之间；需固定表或 renderer consumer |
| `[0x45832C,0x459414)` | 4,328 | palette 与 dialogue 之间；资源边界/消费者尚未绑定 |
| `[0x04BE31,0x04C616)` | 2,021 | 五段 chapter-record 邻接族中的最大段；优先检查是否存在尚未绑定的 chapter root |
| `[0x08C4CC,0x08CBB4)` | 1,768 | consumer slice 与 CFG code 之间；优先检查 direct producer/entry membership |
| `[0x08A700,0x08ACF2)` | 1,522 | consumer slice 之间；只在 producer/CFG 闭合后可晋升 |
| `[0x5A4708,0x5A4CE8)` | 1,504 | fixed table 与 scene source table 之间；需固定 stride/index/consumer 合同 |

## 已知拒绝项

- `[0x063ADC,0x064478)` 2,460 bytes：唯一上游 producer owner 仍 unknown。
- `[0x59EAE0,0x59F560)` 2,688 bytes：index=120 反例且 callback lifecycle 开放。
- `[0x0B9BB4,0x0B9E94)` 736-byte 全零：不满足 alignment/parser-bound padding 合同。

## 选择规则

下一 packet 优先满足：已有可哈希固定的 producer/consumer；范围净增至少 1 KiB，或能
解除更大依赖 blocker；独立 raw-input verifier 可复现；current-unknown 与无重叠由统一
coverage 投影失败关闭。邻接类别、熵、零/FF 计数只用于排序，不构成语义证据。

## 已补证但暂时拒绝的候选

- 表 `[0x599FF4,0x59A104)` 为 68 个物理 u32 槽（22 null、46 个唯一非空目标）；
  46 条目标记录连续覆盖 `[0x006BAA,0x007554)`。若分母闭合，预计可晋升
  272 + 2,474 = 2,746 bytes。
- consumer `0x0932A2..0x0932B0` 由 literal `0x0932C4 = 0x08599FF4` 取表基址，
  从 training row `+6` 读取 u8、乘 4 查表，并在 `0x0932AC` 调用 renderer bridge
  `0x067158`；现有 renderer/parser 与 SJIS 规则可复用。
- 补证后确认 `0..67` 不只是“尚未证明”，而是被固定 ROM 数据反驳。row producer
  `0x094530` 从 63 个角色定义构造 EWRAM 动态列表；primary ID 有 77 个不同值、最大
  86，角色 22..29、36..40、55 含 68..86。consumer 索引前没有上界比较，因此不能把
  `[0x599FF4,0x59A104)` 的物理右边界解释为完整 consumer slot denominator。
- 唯一自然 training entry `0x08E16E -> 0x093698` 的 character 3 primary ID 只含
  `{1,2,3,4,5,6,21,22}`，但 EWRAM `0x02002880` 的 writer/lifecycle 未穷尽，无法证明
  consumer 前最后 writer 必为该 invocation。必须先闭合完整 producer/lifecycle 分母，
  否则该 2,746-byte 候选保持拒绝。
- `[0x599924,0x599F5C)` 及其低 ROM 目标暂时否决：动态 RAM record count 与混合
  64-byte schema 未闭合，不能证明哪些指针实际送入 renderer。

## 本轮补充裁决

- 接受 `[0x007F1D,0x009F2E)` 内 219 个非重叠 renderer records，共 3,961 bytes。
  证据不是形态扫描：完整 1,128-row battle condition denominator 中 230 个 active rows
  的 payload `+4` 经公共仲裁送入已冻结 renderer/parser，219 个唯一目标均成功 NUL 终止。
  该 packet 已通过一级快速审计；canonical 暂不变化，待合并投影 unknown 为 111,062。
- 拒绝把同簇剩余 2,782-byte inter-record gaps 当作 padding：parser 在首个 NUL 停止，
  没有消费这些间隙的证据。`[0x9974,0x9980)`、`[0x9980,0x9986)` 的 6-byte script 与
  `[0x9986,0x9F2E)` 同样保持 unknown。
- 拒绝 `[0x0A1954,0x0A2154)` 2,048-byte font-shaped gap：固定 dialogue lookup 的 row 3
  在 `0x0A1954` 结束、row 4 从 `0x0A2154` 开始；4,410 个逻辑 glyph 均未命中 gap。
  虽然内容可机械分成 64×32-byte 2bpp records，但尚无消费者，形态不能构成语义 owner。
- 暂缓 low-script pointer pool `[0x53DF00,0x53DF70)`：27 个非空目标可解析为
  `[0x000CEA,0x0012F0)` 的 1,542-byte script union，但消费者的动态 u8 index 只有非零检查，
  无 `<=27` 上界；无法冻结完整 slot denominator。Luna max 小包尝试在限时内没有产物，
  Sol 只读复核确认这是合同真实缺口，不是通过多跑模型即可消除的问题。
- 暂缓 `[0x45832C,0x459414)` 中的 alternate-dialogue 候选。唯一 table-base literal
  `0x0918EC = 0x08459284` 绑定 `[0x459284,0x459414)` 的 20×20-byte records；80 个
  非零唯一指针均落在 `[0x458794,0x45927F)`，首 NUL records 合计 1,214 bytes，80 段
  inter-target/table-boundary zero gaps 合计 1,586 bytes，表本身 400 bytes。若能证明
  index `0..19`，预计可晋升 3,200 bytes，并保留 `[0x45832C,0x458794)` 1,128 bytes
  unknown。
- 当前不能晋升：`0x091944..0x09195C` 从 `[r7+1]` 或 helper 结果取得 halfword index，
  直接计算 `table_base + index*20`，没有 `<=19` 检查；u8 路径形式上允许 0..255，
  index 20 起会越过物理候选并进入 `0x459414` 主对话区。后续必须闭合 `[r7+1]` 与 helper
  返回值的 writer/lifecycle 分母，或找到支配该消费点的等价上界；在此之前形态、唯一
  literal、80 个有效目标和全零间隙都只用于排定优先级，promotion 仍为 0。

上述 alternate-dialogue 暂缓结论已被后续静态闭包取代。`r1=0` direct invocation 在
`0x0915AC` 先清零 work struct；`0x091BEC` 每轮自增 index，`0x091E52 CMP #19` 只在
`<=19` 时经唯一 state-zero write/backedge 重入，index 20 退出。因此 rows 0..19 的
完整 consumer denominator 已闭合，3,200 bytes 进入快速审计队列；computed/indirect
入口未穷尽只作为明确 limitation，不再阻塞这一 target-limited direct packet。

## 四包里程碑后的取代状态

- battle-condition result text、alternate dialogue、story-state callback CFG 与 C4CC
  target-local entry 已进入 canonical，共减少 unknown 8,083 bytes。
- 旧候选 `[0x08C4CC,0x08CBB4)` 已被部分取代：`[0x08C4CC,0x08C5A8)` 的 220 bytes
  已分类；`[0x08C5A8,0x08CBB4)` 仍有 1,548 bytes unknown，不得继续按包络外推。
- 当前最大单段依次为 `[0x578C,0x7554)` 7,624、`[0x53F89C,0x541368)` 6,860、
  `[0x03E0,0x1CD0)` 6,384、`[0x42AB,0x542E)` 4,483 bytes。下一轮只能基于
  coverage `e48c8f6d...9c36` 重新验证 producer/consumer owner。

## 新一轮静态裁决

- `[0x08A700,0x08ACF2)` 中仅 `0x08B644 BL -> 0x08ACC8` 具有当前已分类 source
  owner。由于该 owner 不是 instruction-only，最终证据不是 owner 标签本身，而是从
  residual-text-BG 两个固定 entry callers 到 `0x08B58C`，再沿冻结局部 path 经
  `0x08B608 B -> 0x08B644` 的独立 source membership。旧 V15 排除理由已被这条新证据
  取代；新 packet 精确晋升
  54 bytes，`0x08ACF2` 起已有 owner 作为 opaque stop。
- `[0x08C5A8,0x08CBB4)` 没有来自已分类代码的 direct branch producer；看似落入区间的
  pointer occurrences 位于 LZ77/音频数据中，不能作为 CFG root provenance。
- `[0x04BE31,0x04C616)` 即使可按 grammar 从假设根解析 2,020 bytes，也因全 ROM 无
  pointer/root、左侧 terminal、固定表明确跳过而保持 unknown。该负证据用于避免重复
  调查，不是“未使用/free space”证明。
- `[0x0003E0,0x001CD0)` 启动簇已由固定复制消费者部分闭合：五次 DMA3/CpuSet source
  range 的 union 精确为 `[0x0004C8,0x000734)`，净增 620 bytes。范围只声明
  `fixed_rom_copy_source_bytes`，不声明 ARM code、自然执行、业务语义、可编辑、可重定位
  或 free；簇内其余字节继续 unknown。
- `[0x00578C,0x007554)` 的 low-script 方向仍被动态 u8 index 的完整分母阻塞；本轮只读
  复核没有找到支配消费点的固定上界，不能以重复模型尝试替代缺失的 lifecycle 证据。
- `[0x53F89C,0x541368)` 的 14 个 `0x10` 形态头全部未通过 GBA LZ77 长度、token 与范围
  边界验证，0 个构成有效 stream。该结果是否证，不是 padding/free 证明，整段仍 unknown。
- `[0x5A4708,0x5A4CE8)` 的 1,504 bytes 可机械切成 79×19-byte NUL/zero-tail 行外加
  3 个零，但全 ROM 没有指向该范围的 direct pointer/base literal；左侧 79×0x44
  tile-assets consumer 恰好止于 `0x5A4708`，右侧 9×0x1C scene-source consumer 从
  `0x5A4CE8` 开始。重复文本形态不能替代真实 consumer，且候选行 28/42/59/78 无
  fixed-consumer 精确匹配，故晋升 0 bytes；只有找到真实 base/index/parser 链后可重开。
- `[0x08A700,0x08CBB4)` 的 text-BG task 子图已由新依赖闭包部分取代。callback pointer
  `0x08AF0C = 0x0808AA51` 经 task allocator `+0x28` 与 renderer indirect dispatch
  闭合十个 roots；扣除已有 owners 后 `rom-text-bg-task-closure-v1` 净晋升 2,940 bytes。
  未出现在精确 promotion ranges 内的 holes、外部 callees与相邻字节继续 unknown。
- `[0x0042AB,0x00542E)` 内发现 63×8-byte table `[0x599924,0x599B1C)` 与 44 条唯一
  renderer records `[0x42C6,0x4A38)` / 1,906 bytes，但 consumer 使用未检查的
  `unit[+0xBC] << 3`；runtime producer 域尚不能证明恒在 `0..62`，故本轮晋升 0。
  固定 ID 1/29/62 和静态 chapter corpus 不足以覆盖 `0x08086DFC` dynamic ID 及复制链。
- boot unknown 簇另筛出 30 条可由现有 parser 合同闭合的 records，共 1,124 bytes；
  它们由 canonical v2/v3 CFG 内 36 个 consumer sites 最终送入 `0x08067158`。五个
  opcode 7/8 targets 因 handler 无 bounded parser contract 排除。该候选将作为第四个
  快速 packet 实现；不能把 41-site canonical 分母外的 92 个形似 literal 或低脚本池
  dynamic index 外推为全 ROM consumer denominator。

## 四包接入后的 authoritative 状态

- 上述 fixed renderer 候选已实现并接入；最终由上游 CFG block 重建完整 41-site 分母，
  以 bounded register-taint 接受 36 sites、排除五个 opcode 7/8 targets，30 条 unique
  records 精确晋升 1,124 bytes。
- continuation、boot copy、text-BG task closure 与 fixed renderer 四包累计净增 4,738
  bytes / 67 claims。当前 coverage SHA-256 为
  `ff1b9a98fafbe7a14e569db229deddd201a5ec3bea64ced57eb2c0a86c3622b8`，canonical 为
  6,189,254 classified / 102,202 unknown / 98.37554295857748%。本文件开头的 range
  数量与候选排行属于旧 `e48c8f6d...9c36` 快照，继续选包前必须重新聚类，不能直接沿用。
- `[0x063ADC,0x064478)` 的旧“唯一上游 owner unknown”理由已部分被 continuation source
  解锁，但候选仍含五个 `BX r0` frontier；必须先冻结结构化返回/目标分母，不能因为旧
  blocker 消失就把整个包络自动晋升。

上述 dispatcher 候选已在后续一级快速审计中取代：五个 `BX r0` 均补齐结构化返回
合同，其中 `0x063C84` 的 SP alias 由固定 CpuFastSet SWI、fill-mode source-only 语义与
saved-LR 槽证明关闭。新 packet 连同 96-byte dispatcher 精确投影 2,532 bytes，12 个
2-byte holes仍保持 unknown；预计 unknown 99,670，但在下一批二级审计前 authoritative
coverage 仍是 `ff1b9a98...3622b8` / 102,202 unknown。

## 第二包：固定动画描述器组

- `[0x12D574,0x12D9E4)` 已由 `rom-fixed-animation-descriptor-groups-v1` 取代为
  1,136-byte current-unknown projection。物理布局为 12×`0x54` descriptors、12-slot
  pointer table、4×4-word group sequences 与 4-slot group pointer table。
- 证据链为 caller group `0..3` → allocator fields/slot=0 → group/record 双层索引 →
  group next-entry `0xFFFF` stop → descriptor `0x14` stride/next-head `-1` stop；不是按内容
  形态或邻接猜测。自然执行、所有 caller、renderer opaque 副作用、编辑与重定位不声明。
- 与 boot-state 包合并的一级投影为 6,192,922 classified / 98,534 unknown /
  98.43384424845377%。canonical 尚未重建，后续 current-unknown 判定必须在 canonical
  claims 后按 boot-state、fixed-animation 两包顺序叠加。
- 新候选：`[0x53F348,0x53F86C)` AI 配置表净增 1,316 bytes；
  `[0x083B5C,0x083FEA)` 7-slot dispatcher bounded packet 约 1,162 bytes。前者优先复用
  `tools/analyze_battle_ai_utility_policy.py`，但仍须核实动态 config ID 边界；若边界不闭合，
  切换后者。

## 第三包裁决

- AI 配置表边界未闭合：`unit+0xCD` 的直接消费者没有本地 `<=7`，现有 writer 只是从
  source record `+0x0E` 复制，完整 source-record producer/lifecycle 尚缺。该候选保持
  unknown，不以 8×`0xA8` 物理形态晋升。
- `[0x083B5C,0x083FEA)` dispatcher 候选已由
  `rom-battle-distance-dispatcher-cfg-v1` 部分取代。表 28 bytes、code 1,110 bytes、
  consumed literals 24 bytes进入快速投影；`[0x083F52,0x083F54)`、
  `[0x083FBE,0x083FC0)` 四字节继续 unknown。
- 三包叠加后 projected unknown 为 97,372；canonical 仍绑定
  `ff1b9a98...3622b8` / 102,202 unknown，后续候选必须在 canonical claims 上按三包顺序
  叠加做 current-unknown 检查。

## 2026-09-04 authoritative 取代状态

- 第四包 `rom-bounded-index-u16-pair-table-v1` 已精确闭合
  `[0x53F2EE,0x53F30E)` 32 bytes；`[0x53F30E,0x53F310)` 仍 unknown。四包已统一完成
  Tier-2 接入，authoritative coverage 改为 SHA-256
  `ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024`，
  6,194,116 classified / 97,340 unknown / 98.45282236735026%。上一节的三包投影和
  `ff1b9a98...3622b8` 只保留为历史过程，不得再用作 current-unknown 基线。
- 下一首选是 `rom-v17-v18-helper-cfg-v1`：11 roots、575 instructions、1,198 code +
  56 literal bytes，预计净增 1,254 bytes / 14 ranges、0 frontier。必须保留六个 2-byte
  holes、1 条 unknown root producer `0x090FF0 -> 0x090758` 及一条 M4A data 形态误报；
  合同只能声明 33 accepted + 1 rejected-unbound producer，不能宣称 inbound 穷尽接受。
- 低收益兜底 `[0x53E00A,0x53E034)` 为 42-byte 双表：前 10 bytes 由奇偶索引读取五个
  signed-u16，后 32 bytes 由 `&7`、`<<2` 和双 u16 load 读取 8×4-byte records。周边
  `[0x53DFBF,0x53E00A)` 与 `[0x53E034,0x53E496)` 动态索引边界未闭合，保持 unknown。

## V17/V18 helper Tier-1 取代状态

- 上述首选已由 `rom-v17-v18-helper-cfg-v1` 精确取代：1,198 code + 56 literals =
  1,254 bytes / 14 claims；六个 2-byte holes继续 unknown。33 个 accepted producers、
  1 个 unbound producer 与一条 M4A 数据误报均在正式合同中保留。
- 当前只是基于 authoritative `ae7c6933...90024` 的 Tier-1 overlay：6,195,370 classified /
  96,086 unknown / 98.47275416056314%。后续筛选必须把这 14 ranges 叠加后再检查
  current-unknown；不得把 96,086 冒充 canonical，也不得重复选择该闭包内字节。

## Fixed pair tables Tier-1 取代状态

- 低收益兜底已由 `rom-fixed-pair-tables-v1` 正式取代：
  `[0x53E00A,0x53E014)` 10 bytes 和 `[0x53E014,0x53E034)` 32 bytes 合计
  42 bytes / 2 claims；前者为五个 signed-u16，后者为 8×双-u16 records。
- consumer 证明只绑定冻结的奇偶 load、`&7`、`<<2`、双 `LDRH` 与九条已列入口；不
  声明完整自然执行、业务字段语义或 computed/indirect consumer 穷尽。左右 gap 仍 unknown。
- 与 V17/V18 helper 叠加后的 Tier-1 overlay 为 6,195,412 classified / 96,044 unknown /
  98.47342173258463%。authoritative canonical 仍是 `ae7c6933...90024` / 97,340 unknown。
