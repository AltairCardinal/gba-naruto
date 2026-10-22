# 后续CFG中的renderer消费者与opcode2/6依赖

后续正式结果：见[受管合并包Tier-1](rom-renderer-records-delta-tier1-20261001.md)。本预检的accepted0为历史阶段；27条候选现已随原12B一起通过新包验收，尚未Tier-2。

状态：新的36site分母、27条旧语法record候选、1,656B未知交集已独立重放；
**Tier-1未接受、promotion=0**。上轮12B包静态验证通过，但其直接artifacts发布不符合本工作树final/promote规则，
发布门须补正；当前可接入Tier-2正式队列为0包。canonical
unknown87,631B、175项全局阻塞保持。不能把本预检或proposed contract当作accepted artifact。

## 模式与复用

本轮模式为“固定后续CFG字面量消费者的批量筛选与旧语法记录预检”，按脚本优先执行。
复用已有raw handler walker、v2/v3 CFG loader、两个独立参数流实现、training/renderer
两个parser，以及v1/v3/v6 raw-control-flow verifier；没有修改其源码或历史manifest。
不能只沿旧v2/v3的41site分母继续查找：后续已接受CFG包含之前不在该分母中的消费者。
筛选扩展来源，记录合同仍沿旧parser链维护，不新增解释器或放宽语法。

## opcode6与5共用入口，但不是inline文本

原始字节与独立解码确认：

- opcode2入口671DA读取`[script+1]`，671DE调用66D14，671E2/671E4局部推进2并保存
  `[sp+14]`，671E6调用公共dispatch68354。callee有自己的循环及外部调用，不能只凭ADD2
  宣称所有任务状态、返回和字节消费合同已闭合。
- 6721E..67222比较当前opcode是否5。opcode5使用script+2；另一分支6722A/6722C
  从literal67244绑定的RAM槽`0200A888`加载文本指针，不能按opcode5消费ROM后缀。
- 67484..6748A再次区分opcode5；5保存文本终点，另一分支674B8/674BA从`[sp+14]`
  加2并在674BC进入68352，由68352保存r5。此为条件恢复下的局部推进，不是全局resume证明。
- handler可达67460→9C574，保留既有任务切换依赖。不得把raw graph无frontier视为
  callee返回、文本来源域或共享任务恢复不变量已闭合。

针对公共dispatch BL，初始通用图把条件call-return继续到相邻handler或literal区，
从而产生边界frontier/缺少membership错误；原始失败保留。v3预检在已固定dispatch
**callsite之前**停止，不解码literal，也不宣称公共调用会正常返回到下一地址。
两个图分别5/288 instruction、5/302 edge；独立Capstone PC-target重走逐节点/边一致，
17个半字/5个BL原始见证另行验证。停止边界是本次检查边界，不是完整语义闭包。

## RAM文本槽的第三个来源

全ROM逐字节精确word出现仅3处：67244、79B6C、86E80；这不穷尽computed地址。
v2/v3 CFG的literal消费者只有6722A、79AD4、79B2A三个site，但79B6C被后两者共用。

- 79AD6、79B2C把`[r4]`取得的指针写入槽，随后调用解释器的42BD根。
  前者关联599B1C处stride40结构及特殊分组路径，后者关联599924处索引路径；
  索引域/所有记录字段和跨调用保留尚未闭合，不能据此接受整个1592B混合区。
- 86E80的literal由86D9E读取，86DA2把r8写入槽，86DA4/86DA6调用解释器根19B4。
  该源点具有已接受v6 CFG指令owner，v6 raw verifier本轮重新验证成功；不能因其不在
  v2/v3中便说它没有消费者。19B4从opcode6开始，仍不在旧parser合同内。

这条证据改变下一步方向：应纳入后续CFG的固定消费者，而不是反复扩张单一RAM局部窗口。

## 扩大筛选与独立重放

屏幕扫描绑定21个proven-roots v1..v21的payload/manifest身份。其中v1..v14具有受支持的
结构化mode/range block合同；v15..v21的不同instruction schema明确列入unsupported，
没有猜测字段或将其视为“零消费者”。消耗literal统计只针对受支持block分母。
首次schema/manifest读取失败均保留，最终v3脚本支持既有hash字符串/size+hash两种收据。

目标范围固定0..7554，root必须位于immutable coverage
b568db6f…cf06d2的unknown segment；每个block完整解码、site为指令边界。
筛选得到36个literal site，**全部**可重放参数流到67158，来源仅v1/v3/v6。

- 30site → 27unique完整record，独立training parser与renderer parser得到同一终止边界
  和opcode序列；range两两不重叠，每字节在固定unknown分母中，共1,656B。
- 六个site排除：1968/1AE3使用opcode7，19B4使用6，1AE7/1B4F/1BAA使用2。
  不自动推广新语法、不接受这些root与间隙。
- 三个来源raw-control-flow verifier全部verified=true；36site的第二套参数流重放一致，
  frozen path vector SHA为`6a7c0361e733db39af08e015d6433d9307dbf5153ab1eda95a8df90a076c07e6`。
  `contract-proposal.json`冻结候选、路径、来源和helper输入，accepted=false。

候选集中在BCD..BF5、159A..15B0、17B7..1C5F内若干独立record，以及4FA3..542E
内若干独立record；只接受未来正式合同逐record列出的边界，不能接受这些大区间包络。
例如17B7..1968的433B是两条inline文本命令所在完整record；1968之后的新opcode根仍排除。

## 下一完整动作与验收边界

先用新版本/受管包装补正12B包的final/promote流程，保持历史artifact、manifest与源码
哈希不变，不能改旧收据伪造发布证据。再以三个源CFG和immutable coverage作固定输入，
通过TDD建立批量旧语法record
artifact：重新枚举36site、校验paths及六项排除，独立重建27record，真实CLI、安全发布、
对抗manifest/终止符/参数/CFG漂移测试，并通过覆盖率adapter逐字节验证unknown交集。
**不能依赖会随晋升变化的current coverage来筛选root**，否则Tier-2后会破坏历史重放。
不改旧41site/1124B包和新12B包的源码身份，不用本预检代替TDD或正式producer/verifier。

本轮没有生产功能代码变化，因此不宣称新工具TDD完成；检查方式为3个真实CFG verifier、
两套consumer/parser、独立raw graph/见证和JSON/哈希/空白检查。无需新UI，仍是离线调查。
未运行mGBA、全量formal或canonical生成，因为没有新的runtime声明或Tier-2接入。
12B包与1,656B包均完成TDD及受管发布后，才形成2包/1,668B待Tier-2；未到4包/10KiB/0.15个百分点门槛
不重复全量审计。无提交或push；Goal active。

永久收据：`notes/evidence/rom-later-cfg-renderer-consumers-preflight-20261001-v1/`。
管理run：`build/experiments/active/renderer-opcode-contract/opcode2-6-20261001-v1/`。
ROM SHA1198ece7…59d05b；所有成功/失败原始尝试保留，最终结果以inspection-v3、later-cfg-v3、
independent、independent-graph、raw-witness-replay及proposal为准。

## 可执行验收

- [ ] 查看independent → source verifier3/3、36 consumers、27records、unknown_intersection1656。
- [ ] 查看excluded_sites → 六项unsupported，新opcode没有accepted claim。
- [ ] 查看raw-witness-replay → opcode6_inline_text=false，三个store锚点存在。
- [ ] 查看later-cfg-v3 → 七个unsupported block schema明确列出，不声称全CFG穷尽。
- [ ] 查看canonical → 仍87,631B未知，本预检promotion0，原12B包未受改动。
