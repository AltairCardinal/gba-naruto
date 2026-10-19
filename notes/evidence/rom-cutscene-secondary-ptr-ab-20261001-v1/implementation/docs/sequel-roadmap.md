# 木叶战记续作 Roadmap

> 2026-10-01 [cutscene secondary_ptr 输入与捕获](../notes/rom-cutscene-secondary-ptr-ab-20261001.md)：
> 隔离指针 A/B 与相关 8 测试通过，三零输入和两单输入 mGBA 捕获完成；观测 778 像素、
> 仅 PRAM 0x05000382 一字节改变。缺库已按同 commit 库核对/审计恢复，原失败证据保留。
> 独立语义 verifier 与正式发布待下一包；不增加正式 bank/canonical 覆盖。
> [旧 bank runtime 批量重放](../notes/rom-bank-runtime-replay-20261001.md)实际 10/11 通过，
> menu-ui renderer 身份漂移，需新收据；旧 formal 的 175 blockers 不是新全量运行结果。

> 2026-10-01 [map-sprites 部分 bank 合同](../notes/rom-map-sprites-partial-bank-20261001.md)通过：
> 19 固定输入、ID 1 / definition_ptr 的 1/86 单元，19 项测试及真实 auditor CLI 接线通过。
> proposal 保留离线，全量 bank gate 正确拒绝；正式矩阵和 canonical/proof 不变。
> 动画七对参数仍缺 flags/slot 生命周期，不认领整池；下一步 cutscene 两类种子与批量矩阵。

> 2026-10-01 [显示文本受管Tier-1](../notes/rom-display-text-delta-tier1-20261001.md)通过：
> 92site/85record/1,053B/85claims，最终56输入，18项测试（含真实CLI）与稳定双重重建通过。
> live unknown投影独立收据通过；新显示文本1包与旧命令脚本1包分开，库存总2,721B。
> 未达同类/净增门槛，不做Tier-2；canonical87,631B/175 blockers不变。下一步动画与bank。

> 2026-10-01用户取消3%研究门禁并授权推进至周剩20%；Goal active，恢复时周使用52%。
> [显示参数TDD实现](../notes/rom-display-text-parameter-flow-tdd-20261001.md)9/9通过，
> 92真实ROM路径/559指令出现的raw参数证明稳定重放；下一步完整显示合同与managed发布。
> 尚未新Tier-1或promotion，canonical/proof及旧脚本1包/1,668B保持，未提交。

> 2026-10-01 [显示文本局部路径成本](../notes/rom-renderer-flow-cost-20261001.md)：
> 92条路径各4～7指令，共559次出现；全部路径在自身instruction claim内，75/17走两桥。
> 下一包可用有限Thumb raw效果verifier，避免动态/通用符号执行；只是研究，尚未参数验收。

> 2026-10-01 [六来源语义重放](../notes/rom-renderer-source-replay-20261001.md)6/6通过，
> errors=[]且非降级；首轮采集误读guard的问题及修正原始产物保留。
> 下一步只需补新literal到显示桥接路径及文本合同；尚未Tier-1，canonical/proof/队列不变。

> 2026-10-01 [六来源核对/复用更正](../notes/rom-renderer-source-plan-20261001.md)：
> 92site全部指令类owner，六组CFG证据/manifest/verifier身份吻合；语义重放仍缺。
> 旧1,668B是67158命令脚本，新候选是直接显示文本，不能追加旧语法或合计同类包。
> 双parser与发布投影框架可复用；更正仅影响方案，canonical/proof/正式队列不变。

> 2026-10-01 [下一文本包验收设计](../notes/rom-renderer-batch-plan-20261001.md)：
> 92site/85record/1,053B研究集合，与既有包无交叠；完整来源raw验证仍缺。
> 规划单一同类包，禁止拆包凑里程碑；canonical、proof及正式队列不变。

> 2026-10-01 [12EE混合池收敛](../notes/rom-ram-protocol-tag-preflight-20261001.md)：
> 60条renderer候选578B，三池共1,053B假设；另25 RAM标签路径需stage/共享writer证明。
> 研究已收敛：先固定文本合同，再动画生命周期；同步bank/资源严格验收，复杂状态路线后置。
> 本轮仅研究，promotion=0；canonical、proof及1包/1,668B队列不变，未提交。

> 2026-10-01 [458混合池调用筛选](../notes/rom-animation-pool-caller-screen-20261001.md)：
> 116项局部筛选44固定group0/72排除，去重7对animation base；另11旧renderer root假设123B。
> 不能整段按animation分类；source/flags合同未闭合，promotion=0，canonical和队列不变。

> 2026-10-01 [动画双base预检](../notes/rom-animation-base-pairs-preflight-20261001.md)：
> 旧描述器合同CLI实际通过；两新样例首槽各2×0x14 entries并终止于FFFF。
> flags bit8改变slot advance，完整新caller/flags域仍缺；不沿用旧group分母，promotion=0。

> 2026-10-01 [17大段锚点筛选](../notes/rom-large-unknown-anchor-screen-20261001.md)双重重放通过：
> 45832C段固定base进入626B4 allocator可复用已知合同，12EE10段需区分固定copy与RAM文本链。
> 两路线优先于继续高成本生命周期碎片调查；所有形态保持候选，promotion=0、账本不变。

> 2026-10-01 [资源/发布门禁研究](../notes/rom-release-gate-work-plan-20261001.md)：
> 七组fixed-slot verifier实际6/7；battle-effect仅一项历史测试SHA漂移，保留旧产物，
> 后续以受管替代包恢复。六门19case仍为空，未运行build/UI/mGBA或formal，coverage/proof不变。

> 2026-10-01 [有效bank验收路线](../notes/rom-bank-proof-work-plan-20261001.md)：
> 22bank仍23/2,954，11已有命令但22均缺严格typed合同，6字段分母不符、3含机器路径。
> map-sprites entry1/213像素旧archive实际重放通过；建议先迁移样本合同再扩完整矩阵，
> 不扩大runtime/exhaustive声明；bank-proofs与canonical不变。

> 2026-10-01 [文本实际调用路径预检](../notes/rom-fixed-text-route-preflight-20261001.md)：
> 21site分六类，20条假设range共482B；先复用已有renderer桥接14site/352B，
> 90A20 wrapper需额外合同；66EFC仅22B暂缓。来源语义未复验，promotion=0，队列仍1包/1,668B。

> 2026-10-01 [剩余逆向推进方案](remaining-reverse-work-plan-20261001.md)：本轮只研究，
> unknown重算87,631B/1,763段，17个大段42,880B；有效bank声明仍23/2,954。
> 建议先完成后续CFG固定文本消费者合同，再做低脚本delta与AI/协程生命周期；
> 66EFC存在计数截断，不能按首NUL认领。筛选实际33点（旧摘要32点已纠正），
> 来源verifier未重跑，无新promotion；Tier-1队列仍1包/1,668B，正式账本不变。

> 2026-10-01 [受管renderer合并包Tier-1](../notes/rom-renderer-records-delta-tier1-20261001.md)通过：47site、29record、1,668B/29claims；10项完整回归+1项inactive-run检查通过，真实CLI及双重稳定重放/实际unknown投影通过。
> 原12B错误发布包保留历史，由同一raw-input合并包取代；当前正式待接入1包/1,668B，保存在唯一受管final，未promote。canonical87,631B、175 blockers保持，未提交。

> 2026-10-01 [后续CFG renderer消费者预检](../notes/rom-later-cfg-renderer-consumers-preflight-20261001.md)：v1/v3/v6三来源raw verifier通过，36site双参数流、27record双parser一致，共1,656B候选。opcode6使用RAM文本而非inline，六新opcode根仍排除。
> 候选尚未Tier-1；下一步TDD批量旧语法包。12B包静态通过但直接artifacts发布门需补正，正式可接入队列暂0包；canonical87,631B、175 blockers保持，未提交。

> 2026-10-01 [低地址脚本增量Tier-1](../notes/rom-low-script-delta-tier1-20261001.md)正式验收：六site分母、两条record、12B/2claims，8/8含真实CLI与coverage adapter集成测试通过。
> 待Tier-2累计1包/12B；canonical unknown仍87,631B，全局175 blockers保持，opcode2/6和7/8生命周期仍开放，未提交。

> 2026-10-01 [共享任务记录预检](../notes/rom-coroutine-record-lifecycle-preflight-20261001.md)已归档：固定8记录模板与slot0 marker，7C61C/coarse owner和全局恢复链仍开放，125B候选暂不晋升。
> 转向[低地址固定消费者](../notes/rom-low-script-fixed-consumers-preflight-20261001.md)：6 site、两套参数流/语法重放，得到12B旧语法候选，尚未Tier-1；canonical87,631B、Goal active，未提交。

> 2026-09-30 [renderer handler原始图与任务上下文依赖](../notes/rom-renderer-handler-context-preflight-20260930.md)已复现：7/8含早退与9C574→ARM026C的SP保存/恢复；16/16测试通过，缓存漏检已修复。完整续读合同仍开放，125B候选未晋升，unknown87,631B，Goal active。

> 2026-09-30 脚本五根预检完成：[推进形态与语法候选](../notes/rom-renderer-excluded-roots-preflight-20260930.md)，6/6含真实CLI测试通过；125B只是候选，完整7/8 handler合同未闭合，promotion=0。
> 上轮[extra pool复制与成对CD写入](../notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md)已稳定重放归档，生命周期仍开放；canonical unknown仍87,631B，Goal active。

> 2026-09-30 四包Tier-2验收完成：真实净增118B/21claims，unknown87,631B。
> coverage与formal均exit0、非降级；完整formal 107/107合同通过，ROM97/97，
> coverage errors=[]，global complete=false、175 blockers保持。新增永久formal收据
> 与3/3集成测试通过，见[本轮验收记录](../notes/rom-small-cfg-dependency-tier2-20260930.md)。
> 当前无running heavy，恢复读acceptance run的resume-state-after-formal.json，勿重跑已完成审计。
> [AI入口](../notes/rom-ai-entry-local-domains-20260930.md)7/7测试通过，
> [渲染脚本依赖](../notes/rom-ai-renderer-script-dependencies-20260930.md)复用两条preplanner
> 参数流与已分类脚本；postplanner两点尚缺指令owner，82B只是待查窗口，promotion=0。
> Goal active、最近余量55%，停止边界40%；未提交、未push。下文旧状态为历史基线。
> 后续[入口分母与单位池别名](../notes/rom-ai-producer-and-pool-alias-20260930.md)：
> 五目标整ROM raw scan仅9个BL，B/Bcond/ARM/精确指针均0，独立复验一致；
> slot13地址等于extra pool slot0，初始化不提供CD==0保证，须合并其复制/继承生命周期。
> 本轮仍promotion=0，静态字样分母不能关闭computed/RAM入口。



## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：先完成逆向工程，再建网页编辑器。**

> **严格证明门禁（当前更新至 2026-09-05）：** 过去的 32/32 bank 调查闭合和
> 22/22 runtime identity 不再视为“逆向 100%”。当前全 ROM 清单中
> 6,203,707 / 6,291,456 字节（98.60526720682780%）可保守精确定位，87,749 字节
> （1.39473279317220%）仍显式未知；当前为 16,891 条 claim、18,664 个 segment；综合
> bounded-CFG registry 计入 956 ARM、173,058 Thumb code bytes，共
> 174,046 promoted bytes / 4,059 primary claims / 54 code kinds；固定 114 条
> 指针表候选均已由独立证据裁决
> （60 accepted、26 alias_of、28 rejected，open 0）；22 个有效 bank 的直接证据声明覆盖 23/2,954 条
> 记录；10 个 `disproved` 独立物理 bank 候选已由结构化负证据 verifier 关闭，严格 bank 门为
> 10/32，22 个有效 bank 仍为 0/22 穷尽完成；实体 GBA 为 0/1。后续路线必须以
> `docs/reverse-engineering-proof-policy.md`、`sequel/bank-proofs.json` 和
> `sequel/reverse-engineering-proof.json` 的机器门禁为准，全部 gate 通过前不得
> 宣称 100%。

> 当前 Tier-2：fixed-index u8 tail、story-selector dependency、task callback `0x078E38`
> 与 CFG proven-roots v21 已真实接入，净增 978 bytes / 21 claims；9/9 真实 canonical、
> proof 与永久收据集成测试通过。coverage / proof SHA-256 为
> `1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6` /
> `c2862ea520a39432c94fa2634f2ae5650077738c9474aa96ca15d387a4857cbb`。
> 后续123个selector及两个project摘要修复不改变分类字节；新非降级formal已通过
> 106/106 contracts与ROM gate96/96，coverage errors=0。formal report SHA为
> `aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc`。
> 本次Tier-2结束时队列归零，global complete=false/175 blockers；64个历史root的
> A/B验收迁移及C运行合同修复已提交；干净C的68项测试、160成员Git身份和
> 282输入逐字节重建通过，当前committed-artifact验收闭合。详见 `docs/reverse-engineering-handoff-current-20260905.md`。

> 固定stride局部may-read实验1,145B/162ranges虽有26项测试和两次稳定报告，后续父级
> 复核确认组合RAM索引生命周期门未闭合，已拒绝canonical接入并移出队列；promotion=0。
> 不得以may-read标签替代08F654 producer/lifecycle证据，canonical数字不变。详见
> `notes/rom-strided-prefix-local-read-domain-20260905.md`。

---

## 历史调查与执行日志（非当前完成度）

> 2026-07-30 历史快照：当时调查闭合审计为 32/32；22 个有效数据 bank 均通过元数据和
> 基准 ROM fidelity，另 10 个是带负证据、空 entries、禁写回的 `disproved`
> tombstone。分布为 runtime 13 / code 9 / static 0 / disproved 10。32/32 只表示
> bank 身份调查闭合，不等于所有字段语义、运行时路径与端到端写回均已完成；
> save-state 已由真实 UI save 与冷启动恢复升级为 runtime_verified。

当前完成度只以页首严格证明门禁及 proof policy 为准。以下条目只描述专项证据和
当时状态，不可汇总为整体完成率。

### 历史执行日志（起始于 2026-07-13；后续条目按日期追加）

- 2026-08-11 否证 bank 合同化：新增一个只读共享 verifier，逐项从基准 ROM 与规范
  bank/artifact 重建 10 个历史误判候选；覆盖规范表别名、错位切片、混合 font 与
  handler 范围、角色视觉矩阵子视图及 m4a SongHeader 子字段。每项绑定候选范围、
  candidate/bank/evidence SHA 与结构化 JSON 合同，严格 bank 完成度由 0/32 提升为
  10/32；否证范围仅为独立物理 ROM bank，不声称穷尽排除同一字节的其他逻辑消费者；
  22 个有效 bank 和 7 个全局 gate 均未被扩大声明。

- 2026-08-09 事故恢复与目录安全：CFG seed 导出器的旧实现允许把仓库根目录当成
  artifact 递归替换，一条在真实工作树调用 `export(ROOT, ROOT)` 的错误测试触发
  工作树删除。Git 对象与分支未损坏；287 条成功补丁由会话日志恢复，全部生成型
  artifact 依赖重建，coverage 的 5,846,562 classified / 444,894 unknown 与事故前
  完全一致，formal proof 仍为 25/26 verifier 合同通过、`complete=false`。正式
  工作树已无损附着回 `codex/reverse-engineering`；原因、哈希与恢复边界见
  `notes/exporter-root-deletion-incident-20260809.md`。boot/CFG seed 已改为先验证
  所有权再原子替换；全仓另发现的 14 个 P0 与 9 个 P1 输出入口在统一迁移前禁用。

- 2026-08-09 CFG root seed 基线建立：从 18 张 inline dispatch 表、5 张规范
  dispatch 表及启动链导出 23 个来源、829 个原始槽、261 个唯一 Thumb handler，
  加 reset/IRQ 两个 ARM root 后共 263 个哈希绑定 seed；独立 verifier 重建全部
  分母。该 artifact 只声明“已枚举且已有消费者证明的 dispatch roots”，明确不
  声称全局函数入口、全局 dispatch 来源或已执行 CFG traversal，后续须以受界静态
  CFG 扫描扩展代码证据。

- 2026-08-09 未绑定 LZ77 覆盖接入：全 ROM 严格 type-`0x10` 扫描得到固定
  1,099 条语法候选；其中 41 条互不重叠、没有 4 字节对齐直接 ROM 指针且原覆盖
  全为 unknown 的流，以独立 verifier 和双 bundle 逐字节重建后，仅按
  `lz77_syntax_unbound` 接入 14,725 个 ROM 字节。该分类不声称消费者身份、运行时
  可达、资源用途或图形语义。语义分类更新为 5,861,287 / 6,291,456（93.1626%），
  unknown 降至 430,169（6.8374%）；coverage 15 项测试和 proof 28 项测试均通过。

- 2026-08-09 固定 root CFG 覆盖接入：从 263 个哈希绑定 root 受界遍历 40,872 条
  ARMv4T 指令、7,725 个 basic block 和 86,184 个指令字节；独立 verifier 以原始
  ARMv4T 位编码重走完整入口闭包，并显式记录 7 条 SVC→BIOS、357 条间接 PC 与 2 条
  不支持指令 frontier。仅将基线仍为 unknown 的 74,962 个 Thumb 指令字节提升为
  `armv4t_cfg_reachable_thumb_code`，不覆盖既有分类，也不声称全局代码图或运行时可达。
  当前分类为 5,936,249 / 6,291,456（94.3541%），unknown 为 355,207（5.6459%）；
  coverage 16 项、CFG 15 项、proof 28 项测试均通过。

- 2026-08-09 对话记录间零填充覆盖接入：从已验证的 305×20 对话表独立重建
  1,220 个严格递增、互不重叠的 NUL 目标，并穷尽其 1,219 个相邻间隙；全部间隙
  共 16,814 字节且逐字节为零。coverage 仅将原 baseline unknown 提升为
  `dialogue_inter_record_zero_padding`，明确不声明文本、运行时可达或安全可分配空间。
  当前分类为 5,953,063 / 6,291,456（94.6214%），unknown 为 338,393（5.3786%）；
  coverage 18 项与 padding 10 项测试均通过。

- 2026-08-09 已验证成果复用批次：对九份既有 artifact 逐一固定 manifest/payload/
  verifier 哈希并实际执行独立 verifier，再通过真实 JSON selector 校验每个来源记录的
  ROM range、size 与 SHA。只提升此前仍为 unknown 的交集，共 37 个 claim、3,919
  字节；失败的 character OAM 证据与 staged GPU 的 RAM/raw resource 明确排除。
  当前分类为 5,956,982 / 6,291,456（94.6837%），unknown 为 334,474（5.3163%）。

- 2026-08-11 Thumb 索引跳转一次性 CFG 扩展：保持 v2 的 263-root 图哈希与 357 条
  间接 frontier 分母不变，从固定 29 个 frontier 的原始 Thumb 模板、边界分支、literal
  和 677 个允许表 cell 独立重建 290 个目标。189 个目标引用既有 v2 指令入口，仅对
  101 个新入口执行一代 direct branch/call/fallthrough 闭包；新增 4,698 条指令、891 个
  block、9,902 个字节及 16 个 frontier，不递归处理新间接跳转。coverage 在九份成果
  复用之后只提升仍为 unknown 的 9,060 个代码字节与 112 个允许表 cell 的 448 字节，
  不认领两个稀疏表的 32 字节奇数洞。当前分类为 5,966,490 / 6,291,456（94.8348%），
  unknown 为 324,966（5.1652%）；v3 产物、独立 verifier、仓库 canonical artifact
  回归和完整 coverage 测试均在资源守卫下通过。

- 2026-08-11 角色资料文本闭包：从固定 `0x5A143C..0x5A14F4` 的 46 个严格递增
  指针重建 `0x59F988..0x5A143C` 的 46 条 renderer 可消费记录。独立 verifier
  同时绑定真实列表消费者、ID 选择器、资料 wrapper 与 renderer/parser 桥接；覆盖
  只提升 6,798 个文本字节及 19 段、38 字节双零对齐填充。自然运行时只证明 ID 0，
  不声明其他 ID 的自然可达、字段语义、Unicode 解码或安全编辑。语义分类更新为
  5,973,326 / 6,291,456（94.9435%），unknown 降至 318,130（5.0565%）。

- 2026-08-11 固定消费者文本闭包：从 5 张已由真实消费者索引并送入 renderer/parser
  的固定表独立重建 280 个槽和 276 个唯一 target；只提升 1,120 个指针表字节与
  2,756 个 parser 实际消费字节，不认领记录间隙、运行时索引上界或 Unicode 解码。
  覆盖率更新为 5,977,202 / 6,291,456（95.0051%），unknown 降至 314,254
  （4.9949%）；artifact、独立 verifier、覆盖率测试与形式 proof 均纳入门禁。

- 2026-08-11 训练文本命令脚本闭包：固定 `0x59A104..0x59A1B8` 的 45 槽表中
  ID 0 为空，ID 1..44 经真实索引消费者进入 `0x067158` 命令解释器；独立 verifier
  绑定 14 项 dispatch、实际使用的 `1,5,4,12,3,0` opcode 序列及嵌套 renderer
  grammar，精确界定 `0x007554..0x007F1D` 的 44 条连续记录、264 条命令和 2,505
  个字节。表的 180 字节已由候选覆盖层分类，故本批不重复认领。覆盖率更新为
  5,979,707 / 6,291,456（95.0449%），unknown 降至 311,749（4.9551%）；不声明
  每个 ID 的自然执行、Unicode 解码或安全写回。

- 2026-08-11 38 槽值域选择文本闭包与候选 92 纠错：真实消费者以
  `0x542204..0x54229C` 的 38 对连续 u16 包含范围选择
  `0x599F5C..0x599FF4` 的 38 槽指针，随后经 renderer/parser 消费
  `0x00542E..0x00578C` 的 38 条连续 NUL 记录。旧 36 槽候选只是完整表的严格
  子区间，现改为 `alias_of`；coverage 新增最后 2 槽的 8 字节、152 字节范围表和
  862 字节文本，共净减少 unknown 1,022 字节。CFG seed/v2/v3 因 verifier 哈希绑定
  完成级联重建，263 roots、40,872 条 v2 指令与 4,698 条 v3 扩展指令分母不变。
  当前分类为 5,980,729 / 6,291,456（95.0611%），unknown 为 310,727
  （4.9389%）；33 个结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-11 selector 文本保守闭包：固定枚举器只证明
  `0x59F5F0..0x59F988` 的 46 行来源域映射到 46 个唯一物理文本槽，因此只按
  renderer 首个 NUL 接入 324 字节，不把观察到的 63×19 区域当成完整分母。另从
  三路 selector、3 个 `0xFF` 终止配置列表及其 38 个唯一引用槽，按 copy parser
  首个 NUL 接入 316 字节文本，并接入 164 字节配置列表与 12 字节指针表。本批
  合计 86 个不重叠范围、816 字节；NUL 后 918 字节零后缀、17 个未引用槽和未证实
  的 63 槽分母保持 unknown。当前分类为 5,981,545 / 6,291,456（95.0741%），
  unknown 为 309,911（4.9259%）；34 个结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-11 79 槽战斗消息文本与零填充闭包：固定表
  `0x5A2034..0x5A2170` 的两个唯一 table literal 消费者均经 `0x08098290`
  wrapper、`0x08066758` bridge 进入 `0x0806626C` renderer/parser。独立 verifier
  从 79 个唯一递增 target 重建 79 条记录、1,411 个消费字节，并逐字节证明每条
  记录后到下一 target（末条到表首）的 79 段、1,329 字节均为零，连续闭合
  `0x5A1580..0x5A2034` 共 2,740 字节。指针表不重复认领；运行时自然证据只覆盖
  ID 0，前置 `0x5A14F4..0x5A1580` 的 140 字节继续 unknown。当前分类为
  5,984,285 / 6,291,456（95.1176%），unknown 为 307,171（4.8824%）；35 个
  结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-11 启动 interwork ARM 根闭包：全 ROM 原始分支分母确认
  `0x08061086` 是唯一直接 Thumb BL→`0x0809C56C`，后者以 `BX pc` 切换 ARM，
  `0x0809C570` 又是唯一直接 ARM B→`0x0800024C`。独立 verifier 在固定 ARMv4T
  decoder 下闭合 92 条指令、8 个 block、10 条 edge、0 个 frontier，并从 9 条
  PC-relative LDR 重建 36 字节 literal pool。coverage 仅接入 368 字节根代码、
  36 字节 literal 与 10 字节 producer，共 414 字节；跳过的 2 字节对齐、相邻
  sibling veneer、RAM 目标、完整 reset-to-root 运行时路径及周边约 40 KiB 均不声明。
  当前分类为 5,984,699 / 6,291,456（95.1242%），unknown 为 306,757
  （4.8758%）；36 个结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-11 固定消费者文本批量扩展：在既有 5 表 artifact 内新增完整的 unit-name
  63 槽、active-action-name 87 槽、message-command 100 槽与 passive-description
  45 槽表。message-command 的 `0x80..0xE3` producer 静态证明完整 100 槽，并保留
  command `0xDE` 的 null；独立 verifier 重新闭合累计 9 表、575 槽、570 条记录。
  本批新增 1,180 个表字节和 4,024 个 renderer/parser 消费字节；24 槽混合 UI
  资源表 `0x5A7FCC..0x5A802C` 因没有文本前缀索引上界而排除。当前分类为
  5,989,903 / 6,291,456（95.2069%），unknown 为 301,553（4.7931%）；结构化 ROM
  verifier 数仍为 36，既有 fixed-consumer 合同已扩展而未增加重复 verifier。

- 2026-08-11 direct-call-proven 两根 CFG 增量：全 ROM 的目标限定 Thumb BL 扫描
  精确固定 `0x073688→0x081B70` 与 `0x07443C/0x074918→0x0722A8` 三条 producer。
  新 artifact 将 v2/v3 指令入口作为 opaque stop，独立重建 6,166 条 Thumb 指令、
  1,203 个 block、12,966 个字节、28 个 frontier 与 259 条基线 cross-edge；任何
  跳入基线指令中部均失败关闭。coverage 只提升仍 unknown 的 12,946 个可达代码
  字节，并把三条 producer 的 12 字节单列为结构上已解码的 Thumb BL，不声称自然
  执行或全局代码图。当前分类为 6,002,861 / 6,291,456（95.4129%），unknown 为
  288,595（4.5871%）；37 个结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-12 direct-call-proven 三根 CFG 增量：全 ROM 的目标限定 Thumb BL 扫描
  精确固定五条 producer，分别指向 `0x0689A4`、`0x06B49C` 与 `0x0851F8`。新
  artifact 冻结 v2/v3/首批 proven-roots 三层 baseline，并将其入口作为 opaque
  stop；独立 verifier 重建 4,809 条 Thumb 指令、835 个 block、9,876 个字节、
  28 个 frontier 与 82 条 v2 cross-edge。coverage 提升全部 9,876 个仍 unknown
  的闭包字节并单列五条 producer 的 20 字节；27 个间接目标与一个 unsupported
  instruction 保持开放。该批接入后分类为 6,012,757 / 6,291,456（95.5702%），unknown
  为 278,699（4.4298%）；38 个结构化 ROM verifier 已纳入 proof 合同。

- 2026-08-09 严格覆盖审计更新：最后 3 条候选由唯一 table-base literal 和实际索引
  消费者闭合为规范表的严格子区间，累计 61 accepted、25 alias_of、28 rejected、
  open 0；同时接入 battle presentation、tile BG palettes 与六份 artifact 的
  consumer slices，并对候选 26 的 128 字节交叠去重。随后接入角色战斗视觉
  selector、BG canvas descriptor 表与 loader；本轮又从
  overview、scene visual、residual WRAM metadata、GPU copy queue 与 portrait
  palette 的既有验收产物接入 27 个有消费者代码 claim，共新增 5,958 字节。随后从
  四张解释器根表独立遍历 18,994 个节点，接入 92 个精确合并区间、334,060 字节；
  随后接入 49 个 speaker-label 的 251 个 renderer-consumed 字节、11 张文本表的
  625 个 target / 22,588 字节及 86 字节 sprite tile-base 表；随后严格接入启动区
  reset/header/bootstrap/IRQ 的 584 字节，并保留无入边的 `0xC4..0xC8` 为 unknown。
  接入未绑定 LZ77、固定 root CFG 与对话记录间零填充后，当时语义分类为
  5,953,063 / 6,291,456（94.6214%），unknown 为 338,393（5.3786%）。28 个结构化
  ROM verifier 中严格语义完整门仍按设计失败，其余 27 个合同已执行通过。

- 2026-08-09 严格候选裁决覆盖层建立：保留 114 条全 ROM 扫描清单作为不可缩减
  分母，验证器从 ROM 和规范产物独立重建 47 条 accepted、20 条 alias_of 与
  2 条 rejected。角色战斗帧指针表闭合候选 28–73；角色描述表及零终止行闭合
  85；章节、地图事件、战斗特效、文本和菜单表闭合 20 条严格子区间别名；88 与
  99 因跨越两个规范表边界而拒绝其聚合范围。开放项从 114 降至 45，未缩减原始
  分母。证据为 `sequel/similar-table-adjudications-v1.json` 与
  `tools/verify_similar_table_candidates.py`。

- 2026-08-09 第二批候选裁决以实际索引指令、literal、完整表边界与 ROM SHA 为
  证据，新增裁决 11、14、21、25、76、90、101、102；其中 #14 经机器码确认是
  指向 63 项表的 literal 加完整表，不误报为 64 项 dispatch。累计为 48 accepted、
  22 alias_of、7 rejected，开放项降至 37。另建立 41 条、14,725 压缩字节的严格
  type-0x10 无直接指针库存；因没有 consumer，不计入语义覆盖率。

- 2026-07-29 通用 Sprite 定义链已从“需运行时抓取像素”升级为完整静态资产：
  `0x08080A48` 把 ROM `0x0812F298/0x0812F584` 解压为 49 个 4bpp tile 和
  16 色 palette；43 个 ID、45 个 component 正好覆盖全部 tile 一次。v2 产物含
  43 张 ID PNG、总图集、无损二进制和 manifest，独立验证为 43/45/43/49、
  `errors=[]`；全程未启动 mGBA。证据见
  `notes/sprite-definition-runtime-chain-20260729.md`。
- 2026-07-29 通用 Sprite animation 0 已批量闭合：43 个 animation table 首指针
  全部回指 definition 内嵌的 `frame 0 / duration 1` 记录，下一条统一为 `-1/0`
  哨兵；自然加载链的 task flags `0x49` 选择停止而非循环。43 份 timeline JSON 和
  43 张 contact sheet 已进入 `sprite-definition-animations-v1`，独立 verifier
  从 ROM 重读记录并重建预览，43/43、`errors=[]`。这闭合规范 Sprite 的帧号、时长
  和终止策略，但不签发场景专用覆写或屏幕空间坐标。证据见
  `notes/sprite-definition-animations-export-20260729.md`。
- 2026-07-30 角色战斗视觉矩阵的唯一 component 尾标缺口已闭合。row 227
  （character 26、slot 2、frame 2）的 `0xFBFF` 在 renderer 中按 signed u16
  比较，不等于终止值 `-1`；同快照断点证明原 ROM 越过帧边界继续按 20 字节解释，
  仅把 `0x0825A8E5` 从 `FB` 改为 `FF` 后会在 `FFFF` 停止并产生唯一合法 OBJ。
  原始字节继续无损保留，导出器只对该已证明地址记录显式修复，角色战斗视觉现为
  2004/2004 个去重源空间帧完整，独立 verifier 为 `errors=[]`。这不签发屏幕坐标、
  相机、priority、blend 或 palette transform。证据见
  `notes/character-battle-visuals-export-20260729.md` 与
  `artifacts/character-fbff-runtime-v1/manifest.json`。
- 2026-07-30 角色源帧新增全 tracked checkpoint 的自然 OAM/VRAM 离线绑定。
  批量脚本严格解析 91/91 个 `.ss9`，扫描 1211 个活动 OAM，在 57 个 checkpoint
  中以尺寸和 OBJ VRAM 完整字节命中 222 个角色 component；133 个由最小 BGR555
  palette 差异唯一解析，89 个保留同分歧义。最优候选覆盖角色
  `[1,2,3,30,33,35,41,55]`、47 个 resource、146 个
  `(resource,frame)` 和全部 9 个 visual slot。11 个 palette 完全一致，194 个只改
  index 15，另 17 个记录 12/13 色差分；自然样本同时证明源 tile 128/160 等会被
  重定位到 runtime OBJ tile 0，不能把 attr2 当 ROM 源 offset。独立 verifier
  以既有 GPU decoder 交叉检查 1211 个 active OAM，再重建全部
  checkpoint/VRAM/PRAM 与源组件并通过手工 tile/palette golden 和 SHA 篡改测试。成果见
  `artifacts/character-runtime-oam-bindings-v1/` 与
  `notes/character-runtime-oam-bindings-20260730.md`。本批次仍不签发自然
  selector/task trace、camera writer、62×9 全槽或 BG/OBJ/window/blend 最终像素
  合成。
- 2026-07-30 继续把上述 222 个角色 OAM 与同 checkpoint 的单位池格坐标及
  BG0 scroll 批量关联。220 个观测存在同 character live unit，二维模型
  `origin_x ≡ grid_x*32-BG0HOFS+16 (mod512)`、
  `origin_y ≡ grid_y*16-BG0VOFS+8 (mod256)` 对其中 208 个给出唯一基础空间
  anchor；12 个只有唯一同角色单位但保留非零演出 offset，2 个没有 live-unit
  candidate。模型选择不是单样本猜测：X/Y 穷举的最优命中分别为 209/220 和
  208/220，次优只有 56/220 和 54/220。scenario 46 的五个 character 41 候选
  可由空间公式唯一落到 slot 8，scenario 50 的五个 character 35 OAM 也分别落到
  五个不同格坐标；上游 source ambiguity 和全部 `unit_ownership=null` 仍原样保留。
  独立 verifier、手工 raw-unit-pool/wrap golden、错误 24-pixel 单样本别名反例及
  semantic tamper 测试均通过。成果位于
  `artifacts/character-runtime-unit-oam-bindings-v1/`，说明见
  `notes/character-runtime-unit-oam-bindings-20260730.md`。constructor/selector
  writer、非零 offset 语义、camera 调度、动画状态到帧及最终 screen-space 合成仍
  未闭合，Goal 保持 active。
- 2026-07-30 角色自然 OAM 又与同 checkpoint 的 128×`0x3C` 全局 sprite task pool
  完成离线渲染身份绑定。91/91 个 checkpoint 均成功解析；59 个 OAM 同时满足
  资源三指针和 task origin，53 个进一步由 task 当前 animation/keyframe 唯一选中
  同一源 frame，并从 task origin、component geometry/flip、dynamic-copy tile
  base、palette 和 priority 精确重建完整 `attr0/attr1/attr2`。其余 6 个因当前
  frame 不一致降级为相关项，不误报为 identity。allocator/renderer 代码已证明
  pool、dispatcher、字段和推进契约；`0x030055F8` 已纠正为全局 slot 112，
  不是 pool 基址，53 条角色观测位于 slots 120–127。独立 verifier 重读 ROM、
  父 artifact、视觉 manifest 与
  91 个 `.ss9` 后得到 53 条相同结果。随后又按 dispatcher 的 flags/depth/sort-y
  comparator 重建 91/91 个活动 pointer list、共 741 个指针；53/53 条接受项均有
  唯一 dispatch ordinal，renderer 预测的 attr0/1/2 均命中 shadow OAM，且对应
  8-byte entry 与硬件 OAM 同索引逐字节一致。全 1 KiB shadow/hardware buffer
  只有 80/91 完全一致。IRQ bootstrap 已证明 entry 0 注册
  `0x080612BD`；VBlank callback 在 renderer 后通过 CpuFastSet 或 DMA3 把
  `0x0300027C` 的 1024 bytes 提交到 `0x07000000`，再清 pending flag。
  91 个 checkpoint 中 90 个保存于 pending wait loop，11/11 个完整缓冲差异
  全部落在该代码证明窗口，窗口外差异为 0；这闭合 copy route、VBlank 顺序和
  快照 phase classification，但不冒充逐指令运行时 trace 或精确历史帧身份。
  lineup 的 ordinal `1/2/3` 对应 OAM `12/13/14`，因此也不把 ordinal 冒充
  writer index。当前自然子集只闭合 dynamic-copy component 0；
  task→实际 OAM allocator index/writer、多 component 输出累加、unit ownership、
  camera、window/blend 与最终屏幕合成仍未完成。成果见
  `artifacts/character-runtime-oam-task-bindings-v1/` 与
  `notes/character-runtime-oam-task-bindings-20260730.md`。
- 2026-07-30 全部 91 个 tracked checkpoint 的运行时 BG 输入已批量离线解码。
  91/91 均为 display mode 0，归并为 89 个唯一状态；导出器重建 enabled BG0–BG3
  的 char/screen block、4/8bpp、四种 text-map 分块、scroll、tile flip、palette
  bank、priority 与 color-zero transparency，共生成 285 个逐层 PNG/调试预览。
  为避免把数百个小文件直接放入 Git，图像进入 3 MiB 的确定性 `layers.zip`，
  manifest 逐 member 哈希绑定。独立 verifier 自行解析 `.ss9` 并重建全部像素。
  91/91 样本 blend control 非零、5 个启用 WIN0，因此预览严格标记为
  pre-window/pre-blend/BG-only，不冒充 OBJ、window、brightness 或最终硬件帧。
  成果见 `artifacts/runtime-bg-composites-v1/` 与
  `notes/runtime-bg-composites-20260730.md`。后续独立来源目录把 91 个 checkpoint
  的 199 个启用图层观测归并为 196 个唯一状态图层，并与六类、345 个静态候选逐字节
  比对：28 个 graphics/tilemap/palette 三域精确命中、107 个部分命中、61 个保持
  未识别。精确项只签发 regular BG entry 1/9 和 world-map page 0，不把 alias 或
  单域命中冒充来源。成果见 `artifacts/runtime-layer-static-provenance-v1/` 与
  `notes/runtime-layer-static-provenance-20260730.md`；自然语言命名、
  camera/scroll writer、跨帧时序和未跟踪状态仍未闭合。
- 2026-07-30 上述 61 个 `unidentified_runtime_payload` 又按 tilemap cell
  完成字体组件来源审计。61 个 32×32 父图层共 62,464 个 cell，其中 2,827 个
  精确命中非空 `dialogue-font-v2` 展开内容，26 个只命中全零字体源并保持歧义，
  其余 59,611 个不属于已知字体内容。进一步按同列相邻、无 flip、同 palette bank、
  SJIS half 0→half 1 的严格契约闭合 1,050 个唯一源字形对，覆盖 58 个父层、
  226 个不同 SJIS 码；group 2/3 分别为 996/54 对。每层继续绑定原父记录
  `unidentified_runtime_payload` 身份，绝不把含字形的复合 UI/BG 整层改标为动态
  文字层。独立 verifier 从 ROM 重建 9,012 个字体 half、解析 `.ss9` 和 tilemap，
  并拒绝字形、palette group、上下顺序、runtime hash 与额外文件篡改。成果见
  `artifacts/runtime-font-tile-provenance-v1/` 与
  `notes/runtime-font-tile-provenance-20260730.md`。非字体 tile、具体 writer、
  Unicode 字符语义和未跟踪视觉状态仍未闭合，Goal 保持 active。
- 2026-07-30 非字体主分母又闭合一个静态初始化器资源包。
  `0x08065404..0x08065554` 从 literal pool 加载 BG gfx/palette
  `0x0809C614/0x0809C870` 和 OBJ gfx/palette
  `0x085B64E0/0x0809CBC4`；四项 LZ77/raw、64/48 tile 图集及 23 个 direct
  caller 已无损导出。59,611 个非字体 cell 中，5,225 个独特内容 cell 在 58
  个父层精确命中该 BG gfx，5,106 个满足 `+448` tile relocation；另有 48,815
  个全零和 4,673 个通用填充 cell 保持别名，898 个/39 种内容仍未命中。只有
  28 层的全部独特 cell 都满足固定偏移，palette 也只签发 source bank 0 →
  runtime bank 14 的逐字节相等；所有父层继续保持
  `unidentified_runtime_payload`。独立 verifier 自行重建 ROM、LZ77、atlas、
  61 个 `.ss9` 和父 provenance，结果 `errors=[]`。成果见
  `artifacts/initializer-resource-pack-v1/` 与
  `notes/initializer-resource-pack-export-20260730.md`。静态 loader 证据不冒充
  动态执行，OBJ 实例、剩余 39 种内容、writer、跨帧时序及未跟踪状态仍未闭合。
- 2026-07-30 `alternate-character-overview.ss9` BG0 的 10 种灰阶 tile 已从
  “静态包未命中”闭合为过程式生成来源。`0x0808D934` 按
  `floor(y*15/80)+1` 生成 tiles 257–266、灰阶 palette bank 13 和
  `0xD101..0xD10A` 的 30×20 tilemap；`0x0808DA90` 安装结果并写
  `BG0CNT=0x0002`。generator/caller/controller 代码哈希、活动 task 恢复点以及
  EWRAM/VRAM/PRAM 六个域都与固定 checkpoint 逐字节一致。新 artifact 还哈希绑定
  初始化器父记录并重新计算分母：闭合 300 cell / 10 种内容，使全局未知量从
  898/39 降到 598/29，overview BG0 自身从 717/17 降到 417/7；剩余内容和父层
  身份不被顺带升级。随后逐坐标证明余下 417/7 全在 32×32 screenblock 的
  30×20 可见域之外：右侧 padding 57、底部 padding 384、交集 24，可见域内
  未解释 cell 为 0。它们在来源历史口径继续保留，但不再作为玩家可见资源；
  该阶段留下的全局可见资源缺口为 181 cell / 22 种 battle BG3 内容。独立 verifier
  拒绝公式语义篡改与目录符号链接，结果
  `errors=[]`。成果见 `artifacts/overview-gradient-overlay-v1/` 与
  `notes/overview-gradient-overlay-export-20260730.md`。本轮复用已有 checkpoint，
  未启动 mGBA；`battle-status-bars-v1` 随后逐项闭合这 181/181 cell、22/22 种内容，
  因而当前已跟踪可见图像未知分母为 0/0。未跟踪状态和通用图像回写仍未闭合。
- 2026-07-30 Mode 0 最终 compositor 核心已接入普通 1D OBJ、BG/OBJ/backdrop
  priority、WIN0、alpha 与 darken。对 91 个 tracked checkpoint 的 1211 个
  active OAM 做包围盒预索引后，89 帧与 `.ss9` 内嵌 PNG 逐 RGB 字节完全一致。
  另两帧只差 OAM entry 0 的单个 8×16 cursor animation tile；serialized
  hardware/shadow OAM 分别为 `0x3F4/0x3FA`，PNG 精确对应 `0x3FA/0x3F8`，
  单字段替换后整帧 exact，因而被分类为 screenshot/state 异步相位而非 renderer
  缺口。mGBA commit `1d65391d` 的 packed-mColor darken 舍入也已源码绑定。
  当前自然 corpus 没有 2D OBJ、affine、semi-transparent、OBJ-window、
  brighten、WIN1 或 mosaic；其中 8bpp odd-index、2D stride、semi-transparent、
  OBJ-window、brighten、WIN0/WIN1 precedence 和 wrapped window 已补合成
  fixture，并据此修复 8bpp attr2 bit 0 未被忽略的问题。随后
  `runtime-screen-composites-v1` 把 91 个 checkpoint 的 IO/PRAM/VRAM、
  hardware/shadow OAM、rendered/screenshot RGB 全部逐项哈希绑定，91 张
  rendered PNG 归档为 1.7 MiB 确定性 ZIP。独立 verifier 不复用 exporter
  或 renderer，自行重建后得到 89 exact、2 个 cursor tile phase mismatch、
  未解释差异 0；篡改 hardware OAM 输入域的负例会被拒绝。随后 compositor
  又按 OAM matrix slot 的有符号 Q8.8 逆采样接入 affine OBJ：既有原作正常/
  阵营镜像 runtime savestate 的 OAM entry 2/5 均与 32×32 bound-object
  golden 逐像素 exact，synthetic double-size 也证明只扩输出边界。随后固定
  mGBA commit `1d65391d` 的三份 mosaic renderer 源码完整哈希，闭合 BG 在
  scroll 前的 screen anchor、普通 OBJ 的 screen anchor/edge clamp/flip，以及
  affine OBJ 的 output-raster anchor、leading partial accumulator 和
  double-size 组合；主 renderer 与独立 verifier 均通过 synthetic vectors。
  91 个自然 checkpoint 的 MOSAIC 仍全为 0，因此不把 source-model 合成覆盖
  冒充 ROM 自然使用或实体 GBA 验证；OBJ-window+mosaic 物理语义、scanline
  变化、所有游戏视觉状态与实体 GBA 输出仍待闭合。证据见
  `artifacts/runtime-screen-composites-v1/` 与
  `notes/runtime-mode0-screen-compositor-20260730.md`。
- 2026-07-23 用户否决了 Butano scenario 41 的截图/固定选项拼接实现：它不产生真实战斗规则，不能称为战斗架构或功能等价实现。纠错后，63 条单位、87 条主动动作、94 条忍具已经生成到 Butano 固定内容表，活动战斗阶段改为地图、独立单位/游标和领域快照 UI 的组件渲染，玩家与敌方多动作 AI 共用事务式 resolver；单关 2580 帧路线已通过。该闭环只解除“截图伪战斗”阻塞，不代表完整等价；45 条被动、剩余 handler、完整回合/AI/目标规则以及召唤、多角色、复合目标和护送样本仍必须继续实现和验收。证据审计见 `notes/battle-system-restoration-evidence-20260723.md`，实现/运行记录见 `notes/butano-battle-domain-rewrite-20260723.md`。
- 2026-07-23 主动动作显示身份已从诊断截图中剥离为受 ROM 名称字节约束的 87 项 overlay：78 项逐字确认，9 项明确待二次校字；主控制器 `0x080732B4..0x08075082` 的 36 个分派状态完成结构库存，已命名的 ROM 锚点只限阵营扫描、玩家选择、行动类别、MOVEDONE、胜负/结果和 postbattle。其余状态不得强行套入候选 Butano 状态图。机读证据为 `sequel/content/battle-config/action-identities.json` 和 `notes/battle-controller-states-20260723.json`。
- 2026-07-23 进一步把 18 个 `.ss9` 边界绑定到协作任务栈中的真实控制器帧：14 个 scenario 41 样本覆盖 `0x3110` 移动、`0x3000/0x4000` 菜单、`0x9200` 术菜单、`0x4100` 目标/确认、`0x9000/0x9100` 面向/防御、`0x8000` 结果与 `0x1220` 回合脚本；4 个 scenario 45/50 样本又证明敌方 `0x7000` 行动准备与玩家 `0x6000` 提交门共同汇入 `0x8000` 解析。分析要求有效 Thumb BL、外层 controller caller、checkpoint 哈希及阵营/当前单位字段。证据见 `notes/battle-controller-checkpoint-bindings-20260723.json`。旧 implementation plan 的“已实现”状态已撤销并标记为不得继续执行。
- 2026-07-23 多单位选择新增四次连续单输入 L 与一次受守卫 R 的哈希绑定：六个 checkpoint 始终位于 `0x2000`；L 的本场完整环绕为鸣人→猫→小樱→佐助→鸣人，R 为鸣人→佐助。每次只在两个有效单位的 `unit+0xC1` 间转移选择标记，当前行动单位指针保持空、战斗控制区零差异。它证明 roster 游标是确认前状态，并证明猫这类目标代理也能进入 roster。R 运行峰值 tree RSS 50.77734375 MiB，owned PGID/listener 清理通过。证据为 `notes/battle-unit-selection-bindings-20260723.json`。
- 2026-07-23 单位资格新增五次受守卫单输入对照：L/R 可从唯一未行动的小樱浏览到已行动佐助和护送目标，说明 roster 不预过滤命令资格；A 只让小樱从 `0x2000→0x3000` 并绑定 actor，佐助/护送目标的 A 均保持 `0x2000`，且单位池、战斗控制区、菜单块零差异。资格层因此位于确认边界，死亡/失能/召唤物与跨关卡差异仍待闭合。最大峰值 tree RSS 50.79296875 MiB，owned PGID/listener 全部清理通过。证据为 `notes/battle-unit-eligibility-bindings-20260723.json`。
- 2026-07-23 AI 规划器新增三段函数哈希与直接调用库存：`0x080851F8` 枚举候选，在 `0x080855A2` 调用格评分，并只在 `candidate_score > best_score` 时复制 20 字节候选；`0x08085160` 的局部评分已闭合面向 +50、地形 +200/+100 和 `(rng*50)>>15` 扰动；`0x08085610` 证明网格候选有边界/占用/标志过滤和严格择优。目标优先级、伤害效用、任务目标权重及未命名 helper 仍未闭合，不能把局部常量冒充完整 AI。证据为 `notes/battle-ai-planner-static-20260723.json`。
- 2026-07-23 63 个单位模板新增受 ROM 名称字节约束的显示身份 overlay：55 项逐字确认，8 项 `[22,23,24,25,26,44,53,56]` 明确待二次校字；生成目录已把每个单位的显示身份、基础数值、15 个主动槽、24 个被动槽与 87 主动动作/45 被动项关联。该结果闭合模板成员关系，但不把模板槽误报为任意剧情/等级下的自然菜单资格。证据为 `sequel/content/units/unit-identities.json` 和 `notes/battle-content-catalog-20260723.json`。
- 2026-07-23 事务边界新增四组原 ROM 哈希绑定证据：scenario 45/50 的三个 B 取消路径对完整单位池、忍具库存和战斗控制区均为零差异；scenario 50 瞬身术只在 `0x8000→0x9000` 时把当前查克拉 `1→0`、坐标 `(5,6)→(3,5)` 和行动标记 `0→16` 一起提交。候选 `ActionDraft` 因而有了运行时依据，但其他成本类型、AI 与失败分支仍未闭合。证据为 `notes/battle-action-transaction-bindings-20260723.json`。
- 2026-07-23 资源事务新增三组哈希绑定：battle 15 查克拉命令在 `0x3000→0x3210` 把 HP `134→119`、查克拉 `4→5`；battle 13 休息在 `0x3310→0x1220` 把 HP `24→41`、保持查克拉并把行动标记 `0→32`；同一场的十字手里剑在 `0x4100→0x9000` 清除行动单位首个战斗内装备槽 `unit+0xB1`，但不改 HP、查克拉或持久忍具库存区。它证明忍具 loadout/背包与本场可用槽位必须分层建模，但仍不构成通用恢复公式或完整装备槽布局。证据为 `notes/battle-resource-transaction-bindings-20260723.json`。
- 2026-07-23 效果解析新增普通命中/替身两条 `0x4100→0x8000→0x9000` 哈希链：普通分支目标 HP `46→46→32` 且不位移；替身分支佐助查克拉 `2→2→0`、目标 HP `110→110→110`、坐标 `(4,6)→(4,6)→(3,5)`，目标 `unit+0x154` 为 `0→22→0`。替身反应在确认态先暂存，成本、行动账本和位移到解析边界才原子提交；这证明预览不能直接扣血、替身必须是 resolver 反应分支。通用公式、多段、防御/反击、联携和状态优先级仍待闭合。证据为 `notes/battle-effect-resolution-bindings-20260723.json`。
- 2026-07-23 替身暂存新增 29 个 `0x8000→0x9000` 哈希绑定解析边界交叉矩阵：18 次普通伤害在解析入口均为目标 `unit+0x154=0`，随后扣 HP、不位移；11 次替身均为 `unit+0x154=22`，随后 HP 不变、位移并清零。该结果排除单一槽位/单次样本巧合，但仅覆盖 battle 15 的 character 35，不证明全局反应枚举、触发公式、落点或防御/反击/多段优先级。证据为 `notes/battle-reaction-matrix-bindings-20260723.json`。
- 2026-07-23 防御准备新增 `Up→A→A` 单输入链：从 `0x9100` 选择“是”进入 `0x9200` 共用动作列表；火遁术虽可浏览，但确认时显示“只能选择防御系・回避系的术・忍具”，仍在 `0x9200`。三步 actor/行动标记不变，单位池和战斗控制区零差异，只改菜单状态；说明类别资格在确认边界而非列表生成时验证。最大峰值 tree RSS 50.875 MiB，owned PGID/listener 清理通过。证据为 `notes/battle-defense-preparation-bindings-20260723.json`。
- 2026-07-23 防御类别负例补充 scenario 43 鸣人 `Down→A`：影分身术在防御动作浏览器可见，但确认后同样显示类别拒绝并保持 `0x9200`，单位池与战斗控制区零差异。不能按动作名称推断防御/回避类别。两次守卫峰值为 50.87109375/50.8046875 MiB，owned PGID/listener 清理通过；最终状态 SHA-256 为 `fb3c96d6eac89402275d1404b7a354323a6baa86d8f385d5dae6be084a75ca51`。
- 2026-07-23 成功防御新增写轮眼受控 A/B 链：只把佐助 action 15 等级 `0xFF→1`、当前查克拉 `1→5`，完整 EWRAM 审计确认无第三处前置修改。确认预览保持 `0x9200` 且单位池零差异；提交进入 `0x1220` 时查克拉 `5→3`、`unit+0xD4=0x10` 与 `unit+0xD5=15` 原子写入。相邻 character 35 进入 `0x8000` 攻击时 `+0xD4` 清零，出现写轮眼演出，佐助 HP 始终 134、坐标始终 `(5,6)`。该样本证明一次性回避反应，不证明反击、多段或其他防御动作优先级。证据为 `notes/battle-defense-reaction-bindings-20260723.json`。
- 2026-07-23 基础伤害/命中公式新增静态与自然样本绑定：`0x080754A8` 在演出前按攻击力、攻击属性、`100-5×isqrt(防御)` 与 150% 会心生成普通/会心、计防御/无视防御四候选；`0x08076034` 以模板成功率加敏捷差一半（向零截断、上限 99），对每个 hit 独立比较 `(rng×100)>>15`。自然十字手里剑 power 6、hit count 3 生成 `[9,13,11,16]` 四候选，HP `49→31` 唯一对应两次普通 9 点命中和一次 miss；界面 `6×3` 不是最终伤害。状态/地形修正仍待分支闭合。证据为 `notes/battle-damage-hit-bindings-20260723.json`。
- 2026-07-23 会心/无视防御新增静态与两个单字节受控运行时闭环：基础命中后依次查询被动类型 `0x0C` 与 `0x19`；会心率为 `min(100, passive_value+10)` 并写 flag 2，无视防御率为 `passive_value` 并 OR 4。100% 会心样本得到 `[2,2,2]`、HP `49→10`（`13×3`），100% 无视防御样本得到 `[5,5,5]`、HP `49→16`（`11×3`）；证明 RNG 顺序为命中→会心→无视防御且按条件消耗。证据为 `notes/battle-hit-modifier-bindings-20260723.json`。
- 2026-07-23 反应优先级新增原 ROM 预处理器与两类运行时闭环：`0x080763E0` 先查 blocker、再查 reaction，且只在非零 hit 上触发；写轮眼 `0x10` 替换首个有效 hit 并把事件截断到该 hit，自然十字手里剑基线以队列 hit count 3 逐 hit 判定并得到“两次普通命中、一次 miss”。火弹受控前置仅装备战斗内忍具 46，原版 UI 提交后写入 `unit+0xD4=0x19/+0xD5=0xAE`；敌人攻击队列携带该反应，结算保持佐助 HP `134→134`、把原攻击者 HP `17→3`，并清除反应元数据。静态递归调用与 HP 结果共同证明反击是 source/target 反转的嵌套共享解析，不是表现层反伤。其他反应家族与自然到期仍待闭合。证据为 `notes/battle-reaction-priority-bindings-20260723.json`。
- 2026-07-23 通用状态持续时间新增 side-end 静态/运行时闭环：控制器状态 `0x1100` 在切换阵营前调用 `0x0806C308`，遍历单位槽 1–12 的 16 个、步长 8 的状态槽；同一 checkpoint 的两字节受控对照证明持续时间 `1→0` 时完整移除状态，`2→1` 时保留状态，随后 side 才从 `0→1`。一次性 reaction 消费仍属于攻击 resolver，不与通用 tick 合并；状态专属周期效果、属性修正和 duration-zero 语义仍待闭合。证据为 `notes/battle-status-expiry-bindings-20260723.json`。
- 2026-07-23 状态存储新增三函数静态哈希绑定：每个单位的 `+0xD4..+0x154` 是 16×8 活动状态区，`+0x154..+0x1D4` 是 16×8 已移除状态事件区；自然到期把完整记录移入后者再清活动码，一次性反应消费只清活动码。查询按 code 低 6 位首匹配，普通 code 替换同类旧记录，特殊 `0x3F` 只在旧 duration 非零且短于新 duration 时替换。参数字段和 code-specific 玩法仍待消费者链闭合。证据为 `notes/battle-status-storage-bindings-20260723.json`。
- 2026-07-23 状态消费者新增全 ROM 直接引用库存：查询函数共有 96 个 BL 引用、写入函数 21 个；95 个立即数查询覆盖 25 个 code，现有 blocker/reaction 各 6 个，只覆盖 12 个。剩余 13 个 code 已按稳定 ID 列出，仍需逐调用数据流和运行样本闭合，不能把完整状态架构缩减成防御反应表。证据为 `notes/battle-status-consumer-bindings-20260723.json`。
- 2026-07-23 状态 `0x0E` 新增共享 resolver 静态闭环：解析器从主目标活动状态记录 `+4` 读取联动单位，以相同 source/action type/amount 和防递归参数 `[0,0,0,1]` 先递归结算，再回到主目标 HP 分支；这是有序传播而非重定向，不能实现成复制总伤害。其可见玩法名称和自然演出仍保持 unresolved；原始 13 个非 blocker/reaction code 中还剩 12 个 code-specific 行为待闭合。证据为 `notes/battle-status-linked-resolution-bindings-20260723.json`。
- 2026-07-23 状态 `0x0D` 新增 resolver queue 静态闭环：非反应 event 在解析前依次从 source/target 直接消费该状态且不产生 removed event；target 消费还清 `unit+0xC0` 的 raw bit `0x100`。六个已知 reaction event 跳过此门。状态显示名与 bit 业务名保持 unresolved；连同 `0x0E`，原始 13 个非 blocker/reaction code 已闭合两条操作链，剩余 11 个。证据为 `notes/battle-status-participant-consumption-bindings-20260723.json`。
- 2026-07-23 AI 状态策略新增整段评分器哈希闭环：15 个查询形成两组 target status-any 门、五组同族 event/status 门和两组 actor 分值惩罚；命中 target 门是跳过对应 event 的分值贡献，不是表现层取消，actor `0x12/0x12` 与 `0x0D/0x0D` 则减配置权重。该矩阵证明 AI 必须共享领域状态，但仍不等于完整目标、伤害、生存或任务优先级。证据为 `notes/battle-ai-status-policy-bindings-20260723.json`。
- 2026-07-23 AI 目标与效用新增目标索引函数、全评分器和 8×0xA8 配置表哈希闭环：单位槽 1–12 为同/异阵营各建立最低 HP 比例、最大 HP、攻击、防御、敏捷、移动和地图距离七槽，严格更小替换并保留首次扫描 tie；标准异阵营权重为 `[1700,800,800,1300,1000,800,3600]`，同阵营为 `[4200,2000,1000,1000,1000,800,0]`。damage family 先按目标聚合多段预计伤害，再组合 6000/900/3000/100 的伤害、成功率、覆盖和距离效用；配置尾部四个 typed rule 槽实际覆盖 kind 1–5，普通评分最终只加 0–9 RNG。目标优先级、标准伤害效用、关卡规则和 tie-break 已可实现；规则可见名与完整路径 helper 保持中性。证据为 `notes/battle-ai-utility-policy-bindings-20260723.json`。
- 2026-07-23 动作模板语义新增两套初始化器、目标资格、事件构建、资源门与 63 项 resolver 跳转表的哈希闭环：87 条主动动作和 94 条忍具均生成同一运行时描述，`+0/+1/+2/+3` 分别是成本、显示/动画、效果代码+flags、目标策略+flags；成本已区分查克拉、HP、无标量特殊动作和战斗内忍具槽，目标已区分自己/友军/敌军/占用单位/空格。所有非空模板都能按低 6 位解析到 `0x08076F44` handler，Butano 必须生成独立 Cost/Effect/Target/Range/Upgrade 策略并使用共享 registry，不得按截图或动作名写分支。证据为 `notes/battle-action-template-semantics-bindings-20260723.json`。
- 2026-07-23 Butano 领域重写首个闭环已落地：`generate_butano_battle_action_content.py` 生成 87 条主动动作与 94 条忍具的正交定义，`generate_butano_battle_unit_content.py` 生成 63 个角色的基础数值及 15/24 个动作槽。scenario 41 已删除固定 80 伤害，改从角色 1/30 与动作 5 的 ROM 表实例化；玩家和 AI 共用 `battle_action_resolver`，敌方接近后会真实造成 5 HP 伤害。新状态库实现每单位 16 个活动槽+16 个 removed-event 槽、低 6 位替换/移除、side-end tick 与写轮眼首有效 hit 截断。宿主 19 个 C++ 测试程序全部通过；这仍是领域基础，不代表完整 handler、AI utility、复合目标与多关卡表现已完成。
- 2026-07-23 状态 `0x13` 新增数值与生命周期闭环：effect type `0x14` 读取 source 活动状态记录 `+6` 低字节，加入模板 hit count 后写入 event `+0x12`；配对 handler 先共享解析，再以 mode 1 移除状态并产生 removed event。原 ROM 未检查 lookup `0xFF`，新内容生成必须把所需状态路径作为构建期不变量，不能复刻越界。显示名和其余消费者仍 unresolved。证据为 `notes/battle-status-hit-count-modifier-bindings-20260723.json`。
- 2026-07-23 状态 `0x13` 的生产和全部直接查询消费者已闭合：动作跳转表把 ID 43–49 绑定到第一至第五门、表莲华和里莲华；第一门要求状态缺失，后四门要求阶段严格为 1–4，表/里莲华分别要求阶段 `<=2` 与 `>2`。动作 43–47 的模板以 effect type `0x13`、potency `1–5` 进入 resolver，在 `0x0807758A` 以普通同 code 替换写入 record `+6`；资格与防御详情读取完整 u16，hit-count 消费低字节。它们必须共享一个 `EightGatesStage` 实例。原因码 9–20 的可见文案和状态显示名仍 unresolved，但操作链已闭合；原始 13 个非 blocker/reaction code 剩余 10 个。证据为 `notes/battle-status-stage-policy-bindings-20260723.json`。
- 2026-07-23 状态 `0x05` 已闭合为限时身份覆盖而非贴图替换：动作 4“变化术”只把 source character ID 覆盖为 target character ID，不复制 HP/资源/位置/状态等完整单位记录；状态 `+4` 保留 linked target slot，并参与 `0x0200` tile 类的阵营、自指和 cleanup-event 资格例外。cleanup event `0x0B` 与通用 duration 到期都会调用同一原始身份恢复 helper；自然到期明确经过 removed-event bank 和 `0x0806C5A6`。Butano 必须实现 `IdentityOverrideStatus` 的领域生命周期并覆盖两条恢复路径。该 code 操作链闭合后，原始 13 个非 blocker/reaction code remaining 9；证据为 `notes/battle-status-transformation-bindings-20260723.json`。
- 2026-07-23 属性状态族已闭合为从原始角色身份重建后的有序 modifier 管线：`0x0806D1EC` 按 16 个活动槽顺序，以 record `+6` u16 对攻击、防御、敏捷、移动和最大 HP 应用百分比/绝对增减及 99/9/999 上限；effect `0x26` 原子建立 `0x1E/0x20/0x22/0x1B` 并按最大 HP 正差值同步当前 HP。side-end 在 tick/removed-event 后统一重算，duration 0 保留。主动动作与忍具生产 ID 已逐模板绑定。至此原始 13 个非 blocker/reaction 直接查询 code 的核心操作链 remaining 0，但显示名、removed-event 演出和其他间接状态仍 unresolved。证据为 `notes/battle-status-attribute-modifier-bindings-20260723.json`。
- 2026-07-23 目标结果新增两组跨关卡哈希绑定：battle 44 在目标敌人已清除、小樱位于 `(4,3)` 且面向值为 2 时从 `0xE000→0xE010` 写入胜利 `0→1`；battle 15 在护送代理已清除、三名玩家仍存活时保持同一 `0x8000`，只把结果字节 `0x02026807` 从 `0→2`。这证明复合目标和结果抢占不能退化为清敌/玩家全灭。证据为 `notes/battle-objective-transition-bindings-20260723.json`。
- 2026-07-23 condition 解释器新增全函数、跳转表和 47×3 条 variant 的静态哈希绑定：记录区从 `0x08594758` 精确结束于下一张数据表 `0x08596CCC`，地址为 `base + battle_id×0xCC + variant×0x44`，每条保留四个有序胜利槽和四个有序失败槽。解释器支持 type 1–9，记录实际使用 1、2、3、6、7、8、9；全部已用 type 的运算已经闭合，包括单位/角色缺席、回合上限、战场对象槽失活、到限时 HP 总和/有效单位数/behavior 9 对象结算计数比较。32 槽对象表的分配/释放链与 behavior 9 结算后按单位阵营累加 `0x02026BC0 + side` 的写入链也已闭合。两组同时成立时比较首个命中槽位，较小索引抢占，同索引返回结果 5；调用者把结果 1/2/5 分别送入 presentation ID 1/2/3，结果 5 也结束战斗。对象 behavior 的可见玩法名称、presentation ID 3 可见身份、未用 handler 4/5 和运行时同满足 A/B 仍未闭合。证据为 `notes/battle-condition-interpreter-bindings-20260723.json`。
- 2026-07-22 在线战斗录屏复核已撤销 Butano scenario 41 的“完整 1:1”验收：原作在
  “开始任务？是”后依次显示双方亮相、“开始”标题、可见战前对白和手里剑转场，随后才
  进入单位选择；当前 ROM 跳过了整段入口。当前状态机也仍是固定单角色四回合黄金路线，
  尚未实现多单位行动状态、L/R 切换、完整行动菜单和真实敌方攻击/防御循环。纠正证据见
  `notes/butano-battle-flow-video-review-20260722.md`。
- 2026-07-22 已完成中文流程前 20 分钟 36,001 帧与日文原版全片 12,330 帧的逐帧清单、
  状态边界复核及 scenario 41–50 原 ROM 证据交叉验证。战斗系统后续采用“分层状态机 +
  事务式行动草案 + 数据驱动能力/目标 + 阻塞演出队列”的通用架构；scenario 41 仅作为首个
  验收切片，不再作为架构模板。本项仍处于设计审阅阶段，尚未据此改写 ROM。证据见
  `notes/butano-battle-video-frame-analysis-20260722.md`，设计见
  `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`。
- 2026-07-22 Butano scenario 41 的旧纵切片已从战前任务菜单贯通到战后世界地图：
  38 个稳定边界在真实 mGBA 中保持零像素差，264 帧组合拳为 264/264 normalized RGB
  一致。Maxmod 已按原版 player 状态接入战前 cue 5、战斗 cue 14、组合拳 cue 15、
  战后对白 cue 8、世界地图 cue 2，以及 UI、攻击、弹窗、胜利、结果和升级音效；五个
  路线采样点的主开关、DMA1/2、Timer0 均为 active。Goal 全量回归前墙钟记录为
  28,753 秒（7.9869 小时）。这些证据只对已经截取的画面、动画和音频边界有效，不再证明
  入口或通用战斗流程正确；本关也不代表通用部署、多技能、失败结算、存档和其他章节已完成。证据见
  `notes/butano-scenario-41-one-to-one-runtime-20260722.md`。

- scenario 41 任务准备菜单已确认：`A` 为队伍/装备，`Down,A` 为查看战场，
  `Down,Down,A` 为“开始任务？”，`Down,Down,Down,A` 为保存；
- 确认“开始任务？”后，battle ID 41、map 36×44、Naruto `(4,10)`、Iruka
  `(4,4)` 和白框画面连续六次采样保持稳定；但 2026-07-15 离线任务栈复核证明其保存时的活动链位于
  `0x0808F928 → 0x08088F10 → 0x0807509C → 0x0806F718` 的 pre-controller
  lineup/deployment，且不含 controller caller return；旧 strict arrival 对“该 state 证明 battle controller entry”产生了语义假阳性；
- 该边界尚未证明真实战斗入口、玩家接管、胜利、EXP 或升级：Naruto 仍为 level 1 / EXP 100，
  训练点 `+BA=0`、`A880=0`，因此 `levels` 继续保持 `code_verified`；
- 2026-07-15 五点 controller-path probe 已完成 builder/decoder 与 guarded A/B，但
  `actionable-move-grid.ss9` 的零输入 baseline 和显式 `B,Down,Down,A,A` final dump
  逐字节相同，`0x08073946` 与四个 `0x08073A04` 分支均无 fresh record。正对照未成立，
  因此没有运行 scenario 41 白框两轮，也没有提升玩家控制状态；
- 2026-07-15 macOS Intel 已复用严格 mGBA 0.10.5 frame-80 零输入结果验收战前菜单：
  candidate 与输出的 240×160 RGB8 normalized pixels 逐哈希相同，task 2 resume PC
  为 `0x08067D02`，三个显式栈槽经 base ROM Thumb BL 静态校验后得到活动 unwind
  `0x080885C1 → 0x08088F9F → 0x0808F92D`，`[0x0202680C]=0`，仍不含 controller
  return `0x0808F957`。strict audit/ROM/state/emulator/patch 全部通过哈希校验，guard
  为非降级 `completed/0`，最终 PGID 与 mGBA listener 均无残留；该 state 现已作为
  `scenario-41-prebattle-menu` accepted，可直接重载用于后续分段调试；
- 下一 P0 从 accepted prebattle menu 继续完成 lineup/deployment，并以 task 栈含
  `0x0808F957` 或 fresh entry observer 命中 `0x0808F952 → 0x080732B4` 证明真实
  controller entry；随后依次命中玩家单位选择 `0x08073940`、
  MOVEDONE `0x080722A8`、胜负谓词 `0x080777FC`、结果写入 `0x02026807` 和
  postbattle `0x08074EE6`，再对自然命中的 levels record `+6` 做单因素 A/B；
- 当前证据分布仍为 13 `runtime_verified` / 10 `code_verified` / 9 `disproved`；
  本次纠正的是 scenario 41 功能边界，不改变 bank 状态。
- 2026-07-16 成本/耗时审计确认，mGBA 证据链的实现后加固占本轮约 45% 有效
  token 和 50% 墙钟，根因与强制门禁记录在
  `docs/codex-mgba-cost-time-audit-20260716.md`。用户转向统计后，未被取消的写代理提交了
  `f252dbd` single-input runner；该提交尚未 review，未运行 ROM、未发送按键，也未提升
  controller 进度。后续只能先做一次限定 review，再从 accepted prebattle menu 执行单次
  Down，禁止继续扩展已批准的 evidence 框架。
- 2026-07-16 在限定 review 后，从 accepted prebattle menu 仅发送一次 Down，并以独立
  fresh 80-frame zero-input 重放固化 `scenario-41-prebattle-down.ss9`。四路 normalized RGB、
  task 2、显式 Thumb BL unwind、`[0x0202680C]`、guard 和资源门均稳定；该 rung 仍不证明
  controller entry/player control，也不单独授权 A。Step 4 仍须独立门禁，当前未发送 A。
- 2026-07-16 cycle diagnostic 选择最小 exact period `p=19` 后，从唯一 A candidate
  连续执行两段独立 fresh 19-frame zero-input replay。candidate/p/2p 的完整 RGB8 画面、
  task 2、三个显式 static-BL-valid unwind slots 与 `[0x0202680C]` 全部相同，已固化
  `scenario-41-pre-controller-after-a.ss9`。lineage 为 accepted Down → 唯一 A → zero
  settle 19，`allowed_evidence=[]`；活动 unwind 仍无 `0x0808F957`，所以这只证明稳定
  pre-controller 状态，不证明 controller entry 或 player control，后续仍须独立通过门槛。
- 2026-07-16 从该稳定 pre-controller state 分段执行 B → zero → B → zero；两个 B
  边界均稳定。后续唯一 Down 在 80-frame capture 与同 input state 的唯一 160-frame
  延长重试中，都没有改变 task 2、活动 stack、`[0x0202680C]` 或 normalized full-screen
  RGB，因此 selection/result 未被证明改变并触发停止门。未发送 final A，未运行 entry
  observer，未捕获 raw `0x0808F957`，没有 controller checkpoint；controller entry 与
  player control 继续为 `not-proven`，不进入下一阶段。
- 2026-07-17 上述 B/B/Down 分支已作为 superseded 历史保留：`0x08088628` 是
  message-box yield，Down 不会选择列表项。纠正后的分段输入 B → B → A → Down → Down →
  A → inner B → outer A → inner A 捕获 static-BL-valid raw `0x0808F957`；两次独立
  224-frame zero-input replay 保持 exact RGB、task-2 resume/SP/LR、三条 raw return 与
  A880/A882/2680C，p1 已固化为 `scenario-41-controller-entry.ss9`。controller entry
  现为 runtime-proven 且 stable；player control、first turn、MOVEDONE、victory 与
  postbattle 仍未证明。bank 验证数量和 13/10/9 分布不变。
- 2026-07-18 已从 accepted controller checkpoint 自然闭合玩家接管、第一回合
  secondary MOVEDONE、后续回合、技能击杀、`0x02026807=1` 胜利结果、升级页、战后
  对白和木叶世界地图。immutable base ROM 的决定性 A 与 observer 运行画面及 WRAM
  完全一致；`scenario-41-victory.ss9` 和 `scenario-41-postbattle.ss9` 均已在 base ROM
  下零输入重放并固化。完整边界见 `notes/scenario-41-completion-runtime-20260718.md`。
- `0x08074F2C` natural-save observer 在现有固定帧样本仍未命中，因此本轮不把瞬态
  `0xF400` 或自然保存写成已证明。下一 P0 不再重复战斗导航，直接从 accepted postbattle
  checkpoint 验证升级前后 levels record `+6` 的运行时消费；若最终审计仍要求保存命中，
  应使用“命中即落盘”observer，而不是继续增加固定帧切片。bank 分布暂仍为
  13 `runtime_verified` / 10 `code_verified` / 9 `disproved`。
- 2026-07-18 已从场景 41 战后 checkpoint 自然完成下一段演习场剧情与教程战斗；结果页
  令 Naruto 保持 LV2、EXP `0→110`、训练点保持 1。base ROM 零输入稳定 checkpoint
  `scenario-42-postbattle-world-map.ss9` 已固化，后续主线不再重放场景 42。
- levels probe 已捕获训练确认完整参数并定位第一个 type 4 row：index 8、levels ID 1、
  secondary slot 0。该 row 需要角色 LV8，当前 LV2 UI 明确拒绝，consumer `0x080932CA`
  未命中；因此 levels 保持 `code_verified`，下一步继续自然升级而非强制写入状态。
- 2026-07-18 已自然完成后续三敌人任务，结果页给出 155 EXP，Naruto `LV2→LV3`、训练点
  变为 2；`scenario-43-postbattle-next-task-prompt.ss9` 已经 base ROM 零输入复验。影分身可
  留下可控 unit，“休息”恢复 18 HP，可作为后续战斗的稳定生存循环。levels 仍未到 LV8，
  下一步从该 checkpoint 直接开始下一任务。
- 2026-07-18 已自然完成场景 `0x2C`：胜利条件是“击倒卡卡西 + 在铃铛宝箱上方 `(4,3)`
  朝下结束行动”，不是敌方清零或占据宝箱格。三人各得 125 EXP，Sasuke 升至 LV2；
  `scenario-44-postbattle-world-map.ss9` 已经 base ROM 零输入复验。下一步从该世界地图继续
  自然任务，直到 Naruto 达到 LV8 或首次出现 secondary level 激活。

Windows 前台 runtime 到此停止，后续转移到 macOS Intel。迁移、mGBA 0.10.5、Lua
8-frame 输入、candidate 零输入验收和进程守卫要求见
`docs/reverse-engineering-macos-intel-handoff-20260715.md`。

资源约束：全 ROM Capstone 对象扫描曾单进程膨胀到 3 GiB 以上并触发 OOM、swap
thrashing 和 I/O pressure；该路径现已替换为恒定内存 Thumb 编码扫描。静态重任务与
Chromium probe 必须统一经 `tools/run_guarded.py` 的共享 `heavy` 锁、内存准入、树级 RSS、
wall/idle timeout 和精确 owned-tree 清理；runtime 的实际入口是
`play/_scripts` 下的 `npm run probe:guarded`。禁止按进程名清理。当前 bank 分布仍为
13 runtime / 10 code / 9 disproved；资源安全实现不改变逆向证据等级。完整门槛、退出码和
命令见 `docs/reverse-engineering-handoff-20260711.md` 第 0.5 节。

### ✅ 已打通
以下勾选只表示对应子链路或历史子任务完成，不表示 P0、全 ROM 逆向或发布验收完成；
全局状态保持 `incomplete`，以 proof policy 为准。

- 对白 → ROM 写入闭环（dialogue patch pipeline）
- 5 段对话已验证写入 ROM
- 变长对白现已使用独占 `0x5F0000..0x5F7FFF` allocator，校验基准指针、FF
  空间、编码/NUL、对齐和容量；`group0.label2` 已从 6-byte slot 重定位到
  `0x5F0000`，构建 ROM 的 `0x461CF0` 指针和目标文本逐字节验证通过；该 ROM
  已在 WASM 路线 step 306 通过完整 strict battle arrival，变长重定位的构建→启动→
  文本流程→首战 no-crash E2E 已闭环
- 构建流水线支持 7 种 patch 类型（bytes/dialogue/pointer_redirect/map/battle_config/
  dialogue_var/chapter_script）
- mGBA headless 调试环境稳定（`tools/mgba-headless-snapshot.py`）
- mGBA PC/读取探针已加入：断点真实命中后可在同一上下文抓取 ROM 与 WRAM；
  复位 PC smoke test 已通过；maps width/height 与六类资源流均已由 WASM/mGBA
  同边界 A/B 闭合
- 网页 WASM 首战导航与编成探针已可复现：单位槽 1 坐标 `(4,4)` 唯一对应
  positions group 40 / variant 0 / record 0（ROM `0x588CA8`），positions 已完成
  runtime 验证
- WASM 探针现会记录 `0x02026804` 的 8 字节控制区、`0x02026805` 标识和
  `0x0201BE28..2B` map runtime；baseline 得到 `[36,44,9,22]`
- WASM 到达判据仍要求唯一完整编成、非零 battle ID、派生一致 map runtime 和
  真实地图截图，但旧颜色分类已纠正：旧 step 306 实际是角色详情面板假阳性；
  真正地图在 tail 阶段，菱形黑角 `darkRatio=0.200625`，面板仅 `0.003125`。
  分类器现用黑角比例区分，必须以新 live run 重新签发 strict-arrival 结果；详见
  `notes/strict-battle-arrival-gate-20260712.md`
- 纠正后两次重跑分别停在“队伍・装备”和“特别宝箱”教程说明页，均被正确拒绝且
  save hook 为 0；菜单已确认包含“开始任务”，START 不能关闭教程。静态追踪现已
  确认队伍页只是 normalized selector 2 的嵌套页；真实路径必须退回外层选 selector 4，
  经 `0x08086A54` 成功后由 `0x080871BE..C4` 建立 battle control，再以黑角与下一 A
  打开真实行动菜单的双门禁确认战场
- 独立 A/B 仅把 maps 第 40 行 `0x53DE10` 的 width 36→32，同路线得到
  `[32,44,8,22]`，因此 maps width/height 字段链已升级为 runtime；
  资源指针字段仍保持 code 验证。47 行已有持久 `rom_map_headers` 镜像和
  immutable-base、精确 offset、尺寸、ROM 对齐、LZ header/解压长度门禁的
  32-byte 安全写回
- units 旧结论已撤销：`0x0806E654` 实为读取单位 x/y，`0x53F298` 唯一消费者
  将其作为 u16 偏移查找；legacy units 回写已安全禁用，真实角色记录已迁移到
  `0x54241C`；loader-derived base destinations、两组槽数组和过滤 ID 区已命名，
  完整记录安全写回已建立；玩家界面属性名称仍待 UI correlation
- 真实角色定义表已定位并迁移到 units bank：`0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 可重复提取；formation character ID 经
  `0x02022E34` 模板池复制到 `0x1D4` 战斗槽；WASM 首战样本已证明
  template slot 1 → battle slot 1 的前 `0xBC` 字节复制，但 template payload 与
  ROM raw record `0x5424D0` 仅前 7 字节一致，raw record 字段转换仍待 PC/LR 或
  受控 A/B 证明；后续 `0x5424D1` byte `0x0e→0x0f` A/B 已证明 raw record byte `+1`
  进入 runtime template 和 battle slot，units 结构身份达到 runtime 证据；
  后续静态闭合 7 个 base value、15×4 主槽、24×4 次槽和 9 个候选 ID，
  `rom_character_definitions` 镜像支持带 immutable-base、精确 offset/length、
  sentinel/active flag 门禁的整条 `0xB4` 写回
- character-stats 旧两表结论已撤销：真实成长表为 `0x545068`，63×`0x10`，
  `0x0806D964` 按角色 ID 读取并以 `growth*(level-1)/100` 写入模板；受控首战
  两因素 A/B 已证明 record 1 `+4` 进入 template/battle slot `+2`。
  `0x54507A` 和 `0x545200` 都是错位切片，后者 legacy 回写已禁用
- `battle-config@0x545458` 的旧 u16 场景配置解释已撤销；2026-07-23 又撤销了把连续表截成 32 行的边界：真实结构是
  87×16-byte 主动动作数值模板，与动作文本及单位 primary 槽 ID 一一对应；`0x0806D85C` 按 action ID 复制记录，并用
  byte `+0x0C` 与 u16 `+0x0E` 应用等级成长；effect 2 的 level-2 A/B 已证明
  growth `1→2` 只令 type-4 输出 `+7:4→5`，升级 runtime；地图场景表仍是 `0x53D910`
- items 与 skills 的 `0x546100` 冲突已拆分：两者 entries 原本逐字节相同，且无
  独立 item consumer；items 已改为 disproved tombstone，legacy item 写回保持
  diagnostic-only；legacy `skills` 路径的真表已纠正为 `0x545BE4` 的 94×16-byte 忍具/强化道具模板，
  `0x0806D910` 按 ninja-tool ID 复制前 10 字节，旧 `0x546100` 是 record 81 起的尾部切片
- 五个旧 late-ROM `story*` 候选其实是 `0x465B70` 音频主表所指 song descriptor
  的 `+4` 切片；m4a SongHeader byte 0 是 track count，`+4` 是 voicegroup，
  `+8` 是 track sequence pointers。`story-c/d/e` 保持 tombstone；`story/story-b` 已迁移为真实章节表
  `0x60C74/0x60D54`，并有独立安全写回
- maps width/height 消费链已定位到 `0x0201BE28..2B`，并通过 width 36→32
  A/B 从 `[36,44,9,22]` 变为 `[32,44,8,22]`
- maps 资源字段静态语义已纠正：`+8` 是 BG palette（旧 extractor 错用 `+14`），
  `+0C/+10` 是主/可选 coarse layout，`+14` 是 metatile attributes，`+18` 是
  collision grid；47 行长度公式全部通过测试。row 41 的同边界 EWRAM/PRAM/VRAM
  比对已令六项全部通过，maps 升为 runtime_verified
- battle configs、units、chapters、skills、story beats、legacy audio、maps、levels、
  character_stats、battle_config_data、encounter_zones、items 等无 ROM 身份的
  legacy 危险回写已禁用，只输出 unmapped 诊断；lossless `rom_*` mirror 继续作为
  安全写回入口
- audio/palette/message 身份已拆分：`0x53F138` 的旧 palette 身份已撤销，
  `palettes` slug 实为 `0x53EE98` motion/effect 参数表；`0x599634` /
  `0x08079668` 是消息表/分发器。真实 sound-ID 主表为 `0x465B70`，域 0..158，
  80 个非空 descriptor；dispatcher `0x0809AAC0`、track initializer
  `0x0809B1F4`、FIFO/DMA initializer `0x0809AE3C` 已闭合。运行时 hook 命中
  230 次并证明 ID 118→`0x0853D06C`，audio 升级 runtime；真实指针可达提取器
  已导出 217 条 track blob、23 个 voicegroup、387 个 tone 和 79 个合法 WAV；
  track opcode/控制流已结构化解码并生成单循环 MIDI；player 级 mixer、同-slot
  硬替换和跨-player 共享池已有运行时差分，每个 cue 的可听名称仍待完成。
  sound-ID 主表已有持久
  `rom_audio_sound_ids` 镜像和 immutable-base、精确 offset、ROM 范围/对齐、
  descriptor track-count 门禁的 8-byte 安全写回
- save descriptor 第二字段已纠正为 payload length/累计 stride，而非独立 SRAM
  offset；group 3..9 累计起点为 `0x2548..0x55B0`。WASM 已改用 `getSave()`
  导出真实 32KiB `.sav`。裸 group 均返回1并改变七处，但 wrapper 在战斗初始化
  上下文仍返回0且记录校验不成立；自然 caller 已归属 postbattle controller
  `0x080732B4` 的 state `0xF400`。首战开始自然命中为0，强制 state/gate 会卡在
  更早的结果 UI 阶段，不能代替真实胜利转换；下一有效路线是自动完成首战或取得
  genuine post-victory state 后命中 `0x08074F2C`
- 首战已建立可恢复的 WASM slot-9 checkpoint 闭环：稳定真地图重载仍得到 battle
  ID 40、map `[36,44,9,22]`、唯一 slot 1 `(4,4)`；新增 EWRAM dump 证明光标是
  `0x02026A78/79`，与单位记录 `+0xC4/+0xC5` 不同。地图/面板门禁改以纹理
  `edgeRatio` 为主，稳定地图约 `0.3435`、角色面板约 `0.1263`。当前 A→单步 Down
  只令光标到 `(4,8)`，单位未移动、natural-save hook 仍为0，故不得升级 SRAM
  结论；下一步必须闭合教程的真实 unit-action 子状态后再验证保存与冷加载。详见
  `notes/first-battle-savestate-checkpoints-20260712.md`
- 上述 checkpoint 后续确认是战前“查看战场”，不是可行动战斗；此假阳性已撤销。
  正确选择“开始任务”后，首战以真实两回合 `(4,4)→(4,7)→(4,10)` 完成，
  在宝箱 `(4,11)` 相邻格行动结束并进入胜利转场。木叶界面 UI Save 写出 32KiB
  存档；descriptor 0/2 的 19-byte `Naruto-KONOHASENKI\0` header、payload 和
  NOT-sum checksum 均有效，未使用记录保持全 FF。冷启动 Continue 识别 slot 1
  并恢复相同木叶状态，因此 save-state bank 已升为 runtime_verified。旧 verifier
  把 payload/checksum 起点提前19字节，旧“冷加载必须命中 0x08068AF0”也混淆了
  optional battle restore caller，均已纠正。详见
  `notes/tutorial-victory-save-load-runtime-20260712.md`
- `0x60D54` 受控运行时探针已从无效的 `0x1A` 专用 hook 改为 selector + 通用
  dispatch 追踪。scenario 39 运行时选中 `0x08031281`，共执行 25 次 dispatch，
  最终在 `0x0803142E` 的 opcode `00` 正常返回；live bytes 与 ROM 一致。该脚本
  不产生 battle state 是已解码的预期行为，story-b 已升为 runtime_verified。
- 备用章节实验的 checkpoint 导出已修正：旧实现可能复制同槽旧文件，现保存前
  清理 `.ss9` 候选并要求唯一新文件，加载后也显式释放全部 GBA 键。新的
  `木叶里 / 对战` 任务选择 checkpoint 已通过独立零输入重放；下一段从该页 A
  进入卡卡西对白，继续追到 selector hook。
- 浏览器键盘映射修正后，`PROBE_TAIL_REPEAT` 可复现重复选择。后续通用 dispatch
  探针证明该分支本身就是备用章节对白消费链，而不是必须进入战斗才算成功；runner
  现在会在终止证据出现时立即固化，避免后续输入覆盖最后 cursor。
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ✅ 已定位 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，patch 生成可用 |
| 章节流程入口 | ✅ 两链已闭合 | `0x60C74/0x60D54` 两张 56 项脚本表；primary scenario 39→`0x31020`→三字节 `SetBattle(40,2)` 后接独立 `End`；alternate scenario 39→`0x31281`→25 次 dispatch→`0x3142E` opcode `00` 正常终止，均有 runtime 证据 |
| 资源提取（图片/音频） | ⚠️ 部分 | 47/47 地图画布、62×9 角色战斗视觉矩阵的 342 个有效槽/250 套唯一资源及 2004/2004 去重源空间帧、12/12 regular BG 场景画布、9 组角色场景视觉包、217 条音频 track blob、79 个 pointer-reachable WAV 和 80/80 整曲 PCM 已导出；screen compositor、屏幕空间角色合成、track opcode 和 cue 语义命名仍未全部完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（逆向工程 100% 完成后启动）
- 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
- 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
- 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

---

## 逆向工程路线图

### P0-Step 1｜稳定 mGBA 调试环境
**状态：✅ 已完成**

- `tools/mgba-headless-snapshot.py`：snapshot / watch / diff 三种模式可用
- `docs/next-action-plan.md`：方案 A 执行结果已记录
- 验证：watchpoint 命中 PC=0x08060FD2，cycle=182801696

---

### P0-Step 2｜定位 tilemap 布局数据（Phase 4 收尾）

**状态：✅ 已完成**

**现状：**
- Tile 描述表 `0x596D5C` 已完整分析（312行×16字节，每行含 tile data/attribute/layout/palette 4 个指针）
- tilemap 布局数据（2D 瓦片 ID 网格）已定位！

**发现：**
- 多个 tilemap 数据区位于 ROM: 0x14D000, 0x195000, 0x1CB000 等
- 格式：2字节/条目，32×32 网格 (1024条目，2048字节)
- 编码：低10位为 tile ID (0-311)， bits 10-15 为 flip/调色板属性

**方法：**
1. 用静态分析扫描 ROM 寻找 tile ID 有效范围内的 2D 网格模式
2. 通过对比验证找到多个有效的 tilemap 数据区

**交付物：**
- `notes/map-format.md`（完整版）✓
- `notes/map-addresses.md`（完整版）✓
- `tools/import_map.py`（完整 patch 生成逻辑）✓

---

### P0-Step 3｜定位战斗配置与角色定义

**状态：⚠️ 部分完成**（positions、maps 全资源、角色定义及成长表已有运行时闭环；units 已有结构字段和安全 lossless 写回，剩余玩家属性命名仍未完成）

**已确认 ROM 数据表：**
- ❌ 旧 `0x0853F298` 单位 ID 映射结论已撤销；唯一消费者把它作为 u16
  对象/渲染偏移查找，legacy 回写已禁用
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 已建立，`sequel/content/units/bank.json`
  已迁移；runtime 样本已把战斗槽 character ID 和模板槽闭合到 ID 1 / ROM
  `0x5424D0`；`0x5424D1` 单字节 A/B 已动态闭合 raw record byte `+1` 到模板字段；
  两组槽数组及过滤候选区已按 loader 命名，整条记录可受保护写回
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 16 字节
  - 条目格式：u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra
  - ptr1：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2：LZ77 压缩数据（解压后 384 字节，调色板/属性数据）
- ✅ 状态机函数指针表：`0x0853F1C0` / file `0x53F1C0`，u32[60]，指向 0x0812Fxxx
- ✅ WRAM 分配表：`0x0853D848` / file `0x53D848`

**已确认 WRAM 战斗数据地址：**
| WRAM 地址 | 大小 | 说明 |
|---|---|---|
| `0x0201BE28` | 4 字节 | map width/height 及 `>>2/>>1` 派生尺寸 |
| `0x02021E2C` | 网格相关 | 单位坐标查找表基址 |
| `0x020240C0` | `0x17C4` 总区间；`0x1D4*N` | 主战斗数据/单位数组物理基址（单位 stride 468 字节） |
| `0x02024294` | `0x1D4` | 第一个可分配/常用单位槽（slot 1） |
| `0x02022E34` | 24×`0xBC` | 角色模板池；模板 `+0` 为 character ID |
| `0x02022EF0` | `0xBC` | 角色模板池 slot 1；旧 character-stats WRAM 假设已撤销 |
| `0x02026804` | 8 字节 | 战斗控制标志 |

**交付物：**
- ✅ `notes/battle-config-format.md` — 完整版（ROM 表、WRAM 布局、LZ77 格式、代码引用）
- ✅ `notes/unit-skill-addresses.md` — 完整版（单位 ID 表、场景配置、状态机函数）
- ✅ `notes/unit-id-mapping-analysis.md` — 完整版
- ✅ `notes/battle-scenario-config.md` — 完整版（8 个场景条目解析）
- ✅ `tools/import_battle_config.py` — 可生成 ROM patches + WRAM cheat patches
- ✅ `tools/extract_positions.py` — 从 ROM `0x5461C4` 编成矩阵可复现提取 48×3×12 条记录；记录 `+2/+3` 已静态确认为初始 x/y
- ✅ positions ROM→WRAM 静态链路：`0x0806E41E/0x0806E71E → 0x0806AC70 → 0x0806AA64`；单位 stride 已纠正为 `0x1D4`
- ✅ positions 编辑/回写链：通用 ROM mirror 导入 `rom_positions` 1728 行并保留完整 `0xB8` 原始记录；构建器验证 index、ROM offset 与长度后写回真实矩阵
- ⚠️ 旧 `unit_positions` CRUD 仅是运行时编辑概念，没有一行一 ROM 地址证据，不计入真实回写完成度
- ✅ runtime WRAM dump 已通过网页 WASM 探针取得并与 ROM 编成记录唯一关联；CLI
  headless 仍无按键注入与 PC/LR 联合采集能力

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：✅ 主流程入口已完成；脚本 opcode 全语义仍属后续字段工作**

**2026-07-12 纠正：**
- `0x0808F544` 根据状态 `+0x18` 在 `0x60C74` / `0x60D54` 两张
  56-entry script pointer table 之间选择，并按 scenario ID 索引；
- WASM hook 捕获 primary scenario 39 → `0x08031020`，脚本游标
  `0x08031070` 的 `1A 28 02 | 00`（三字节 SetBattle + 一字节 End）将 battle ID 40 写入状态并最终到
  `0x02026805`；
- `story` bank 已迁移为 primary/runtime，`story-b` 为 alternate/runtime；
  旧 late-ROM `story*` 资源切片结论已撤销。

**已完成：**
- 静态分析：遍历 38 个 late-ROM 表候选，全部为视觉/资源描述表
- 代码引用分析：定位到 9 处对战斗配置表（0x0853D910, 0x0853F298）的引用
- 章节 ID 序列搜索：在 0xBD713, 0xC1717 等处发现 u16(1,2,3...) 模式，但未找到明确配置表

**Runtime 验证尝试：**
- 尝试 1：加载 savestate - 失败（所有 save 文件为 0xFF，未初始化）
- 尝试 2：设断点 0x080894DE - 未命中（游戏卡在 UI 循环 0x085CCDxx）
- 尝试 3：设断点 0x0806E654 - 未命中（无用户输入无法到达战斗）
- 尝试 4：frame advance + breakpoint - 停留在 video/UI 子系统，无法进入主游戏逻辑

**环境限制：**
- mgba-sdl 0.10.1 缺少 `--script` 参数支持
- CLI 调试器无法注入按键输入
- 无有效 savestate 文件

**交付物：**
- `notes/chapter-entry-points.md` - 运行时验证尝试记录 + 静态分析
- `notes/chapter-flow-format.md` - 格式分析（待 runtime 验证）

---

### P0-Step 5｜资源提取链路（图片/音频）

**状态：⚠️ 字节提取、整曲渲染及 player 运行时完成，cue 语义部分完成**

**现状：**
- 47/47 tileset atlas 已由真实 descriptor 指针导出
- m4a SongHeader 已纠正：`+4` voicegroup，`+8` track sequences
- 已导出 217 条 track blob、23 个 voicegroup、387 个 tone、79 个 WAV
- 217 条 track 已结构化解码为 18,090 条命令和 6,750 个 note/tie；1,287 个
  控制流目标全部落在已知 track 范围
- PATT/PEND/GOTO 已按单循环策略执行；80/80 sound ID 已生成标准 MIDI，
  217 条 track 共发出 17,202 个时间线事件
- 16,180/16,180 note 已解析 terminal tone：16,169 个 DirectSound note 覆盖
  79/79 waves，其中 5,340 个经 drum table；剩余 11 个明确为 0x0C PSG/noise
- TIE 生命周期已纠正为 90 条：25 条由 EOT 释放、19 条由 FINE 进入 release、
  46 条在单循环 GOTO 边界仍活跃；只保留后 46 条为 open tie，不伪造释放
- DirectSound nominal pitch-step 已按 `0x0809A998` 的 ROM 两表与 UMULL high32
  精确整数公式闭合；16169/16169 DirectSound note、79/79 waves 均产生正 step，
  23-bit mixer phase 与本 ROM 15768 Hz / divFreq 532 也已代码锁定
- KEYSH/BEND/BENDR/TUNE 与当前 MODT=0 LFO 状态已接入 16169 条 DirectSound
  note，971 条 noncenter，零无效 step
- MP2K triangle LFO/LFODL/MOD 的逐 tick pitch automation 已闭合；对活跃 note 共
  产生 30937 次有效 step 更新（BEND 323、LFO 30413、MOD 201），零无效；open TIE
  只追踪到单循环边界
- `TrkVolPitSet→ChnVolSetAsm` 的两级 volume/pan 整数链已闭合；16169/16169
  DirectSound note 均得到有效双声道系数，活跃 note 内 39 次 VOL 更新全部有效；
  MODT=1/2 由合成向量锁定，但实际 track 中 MODT/LFODL 均为 0 次。timeline 现为
  38979 events（21328 pitch-state、449 mix-state）
- DirectSound ADSR/release/pseudo-echo 与 master gain 状态机已按
  `0x08099EC8..0x08099F82` 代码锁定；16169/16169 note 共 4 种有效 tuple，零非法。
  状态按 SoundMain mixer invocation 而非 MP2K tick 推进
- 11/11 PSG note 已闭合至 CGB channel-4 寄存器向量、NR43 时钟和 15/7-bit
  LFSR；实际语料均为 sound ID 144、NR43=`0x14`，三档 NR42 向量已代码锁定
- DirectSound 16169/16169 note 的 forward-linear 插值、跨 sample/loop、非循环
  停止、reverb seed、signed-byte modulo-256（非饱和）累加和 stereo WAV 写入已锁定；
  8442 条非循环、7727 条循环语料全部走此路径
- MP2K tempo threshold=150、同一 SoundMain 内 0/1/多 tick、linked-player 递归顺序、
  每次 264-frame mix 与 6×264 DMA/reverb ring 已代码锁定；多 tick 间不得插入混音
- 持久 WAIT/GOTO/PATT/REPT command VM 已让 217/217 track 各运行 2048 ticks：累计
  39825 commands、163 次真实 GOTO，79 条 FINE 终止、138 条在时长边界继续运行
- 10 DirectSound pool + 4 fixed CGB 的 free/released/active 选择、priority/track-address
  tie-break、steal、newest-first track chain 与 same-key EOT 已代码锁定
- persistent TEMPO/PRIO/VOICE/VOL/PAN/pitch/LFO registers 已让全部 track 在 2048 ticks
  产生 17546 NoteRequest、21 EOT、79 FINE stop，复用现有 decoded commands/整数公式
- request→terminal tone→allocated channel 已闭合：全库 17546 请求全部到达解析/分配
  路径；真实 sound 1 DirectSound 与 sound 144 CGB noise 向量、drum-root pitch、
  mid-note pitch/mix dirty 传播、自然停止后的 track unlink 和首个 264-frame PCM hash
  均已测试。bounded allocator rejection 不能冒充真实 SoundMain 丢音统计
- player 级整曲 SoundMain 与 DirectSound+CGB 联合 PCM 已闭合：80/80 sound ID
  均生成非静音 WAV，62 个 one-shot 自然结束，18 个 loop song 的全部 138 条
  GOTO track 均跨过首次 GOTO；首次 GOTO 上 21 个 active TIE 保持跨边界
- 独立 mGBA 差分已闭合：sound 101 的 79/79 个 Direct FIFO 块逐字节一致，sound 144
  的 68/68 组可读 CGB register/channel-4 status 一致；两条路径均自然结束
- player-slot 差分已闭合：活跃同-slot sound 101→102 硬替换 27/27、slot 1/2
  linked-player DirectSound 共享池 25/25、跨-player 固定 CGB channel 竞争 68/68；
  equal-priority active owner 稳定为低地址 `0x03006178`
- 播放 wrapper 共 290 个 callsite：278 个立即数调用覆盖 38 个有效 ID，12 个动态
  来源；仅四个 A 级与四个 B 级语义候选有当前证据，72 个仍保持 `unknown`，尚无
  官方名称来源

**方法：**
1. 从 `0x596D5C` descriptor 链提取 tileset PNG（已完成）
2. 从 `0x465B70` sound-ID → SongHeader → voicegroup/track/wave（已完成）
3. 闭合同 player hard replacement、linked-player 并发和全局 CGB pool 竞争（已完成）
4. 动态对照显式 `MPlayStop` 与 FINE release，并为 80 个 cue 建立有来源语义名称（下一步）

**交付物：**
- `tools/extract_tileset.py`
- `tools/extract_audio_assets.py`
- `tools/build_controlled_audio_runtime_probe.py`
- `tools/compare_mgba_audio_capture.py`
- `tools/compare_mgba_cgb_capture.py`
- `tools/build_delayed_audio_retrigger_probe.py`
- `tools/compare_mgba_retrigger_capture.py`
- `tools/compare_mgba_linked_audio_capture.py`
- `tools/build_cross_player_cgb_probe.py`
- `tools/compare_mgba_cross_player_cgb_capture.py`
- `tools/extract_audio_cue_calls.py`
- `artifacts/audio/mgba-sound101-full-differential.json`
- `artifacts/audio/mgba-sound144-cgb-differential.json`
- `artifacts/audio/mgba-same-player-101-102-differential.json`
- `artifacts/audio/mgba-active-retrigger-101-102-differential.json`
- `artifacts/audio/mgba-linked-player-101-106-differential.json`
- `artifacts/audio/mgba-cross-player-cgb-143-144-differential.json`
- `notes/m4a-emulator-differential-20260713.md`
- `notes/m4a-player-slot-runtime-differential-20260713.md`
- `notes/audio-cue-semantics-20260713.md`
- `notes/resource-locations.md`

---

### P0-Step 6｜可变长对话（Phase 2 收尾）

**现状：**
- 同长替换可行，变长 redirect 需要已验证的空闲 ROM 区域

**方法：**
1. 用 mGBA 在游戏运行时检测 ROM 空闲区域（写入后读回为 0xFF 且不被读的地址）
2. 验证后实现 pointer_redirect 策略

**交付物：**
- 空闲 ROM 区域验证文档
- `import_dialogue_var.py`（变长 redirect patch 生成）

---

### P0-Step 7｜全面测试闭环

**现状：**
- `docs/testing-checklist.md` 已建立
- 离线无 OCR 子闭环已完成：`tools/run_offline_e2e.py` 执行正式 build checks，核对
  输出 SHA-1，并用原生 mGBA + tracked checkpoint 断言 battle 41、map 36×44、
  Naruto `(4,10)`、Iruka `(4,4)`；持久报告在
  `artifacts/e2e/offline-smoke-20260713/`
- 编辑器 DB 隔离正式构建已闭合：完整 mirror DB 中只改 map 40 width 36→32，正式
  build 后 reserved region 之前仅 `0x53DE10:0x24→0x20`；测试同时修复了旧
  cutscene 16×pointer generator 与 8×pair schema 不一致、以及未编辑 chapter mirror
  与 scenario 39 semantic relocation 冲突
- 私有 build-ID HTTP 所有权已闭合：owner 可查状态/下载，其他登录用户得到 403；
  “最新 build”改按创建插入顺序而非随机 UUID 字典序。公开 UUID ROM endpoint 保持
  显式 capability URL；浏览器下载现通过带 Bearer 的 fetch/blob 并显示下载中/错误；
  WebSocket 改为首帧 JWT+显式 build ID，拒绝跨用户订阅且不再泄露服务器 ROM 路径
- build-ID 子进程隔离已闭合：`DB_PATH` 贯穿 dialogue 与全部 generator，外部
  `BUILD_OUTPUT_DIR` 的 ROM/build report/automated report 三件套均被当前请求验证，
  全局 build 哈希不变；backend 支持注入 BUILD_CWD/PROJECT_ROOT，并在 trigger 时用
  SQLite backup 固化 build-ID 专属 DB snapshot
- 浏览器 UI/API 鉴权下载已闭合；玩家可见 OCR 与剧情→战斗→存档长程回归仍未完成

**方法：**
1. 在现有离线 runtime smoke 与 editor DB 隔离 build 上追加浏览器 API 与跨平台 OCR
2. 每完成一个格式的 patch 生成，都要跑一遍 checklist

**交付物：**
- `tools/run_offline_e2e.py`（当前无 OCR runtime smoke）
- `tests/test_editor_build_integration.py`（临时 DB 与临时 build ROOT）
- 后续跨平台 mGBA + OCR 验证
- 所有格式的验证报告

---

## 当前推荐顺序

### 2026-07-10 Positions 与构建安全更新

- positions 真实 ROM 来源已更正为 `0x5461C4` 编成矩阵，记录 `+2/+3`
  为初始 x/y；旧 `0x53D914` 结论已撤销。
- 新增可重复提取器 `tools/extract_positions.py`，共提取 `48×3×12=1728`
  条完整 `0xB8` 记录，并通过 `rom_positions` 无损回写。
- 单位物理数组基址是 WRAM `0x020240C0`，stride `0x1D4`；
  `0x02024294` 是 slot 1。
- 补丁冲突门禁发现旧 battle-config 模板会覆盖 `0x547934+`；
  已停止将未映射的 `scenario_id` 当 ROM 索引。
- 32/32 bank 已通过基准 ROM 字节一致性门禁；动态消费路径验证仍在进行。
- 新增只读 WASM 导航/WRAM 轮询探针 `play/_scripts/runtime-formation-probe.js`：
  可按 START → 新游戏 → 连续 A 计划导航，读取 `0x020240C0` 单位数组，并将
  `+0xC4/+0xC5` 坐标与 positions bank 匹配；已验证 core 就绪门禁与真实 WRAM
  读取。后续真实部署运行已进入首战，两次观察到 slot 1 `(4,4)` 并唯一匹配
  group 40 / variant 0 / record 0，因此 positions 已升级为 `runtime_verified`。
  当前导航已闭合 maps width/height A/B，并继续用于闭合真实角色定义的运行时证据。

### 2026-07-10 Bank 元数据审计基线

- 新增 `tools/audit_re_completion.py`，可重复检查 32 个 `sequel/content/*/bank.json` 的表偏移、格式字段、条目、验证标签和 Markdown 文档覆盖。
- 审计产物为 `notes/re-completion-audit.json` 与 `notes/re-completion-audit.md`。
- 首次审计结果为 23/32；随后已纠正错误偏移并从基准 ROM 重新提取。2026-07-30
  又确认 `resource-pointers@0x596F0C` 是角色战斗视觉矩阵 rows 27..31 的重复
  subview。审计现采用双轨规则：22 个有效 bank 必须有非空 entries 和 ROM
  fidelity；10 个 `disproved` tombstone 必须为空、记录负证据并禁写回。调查闭合为
  32/32，但这仍不代表动态语义或真实回写完成。
- 最新严格审计分布为 0 个 `static_verified`、9 个 `code_verified`、13 个
  `runtime_verified`、10 个 `disproved`；仍不能作为“100% 完成”的单独证据。

### 2026-07-11 Character growth 消费链修正

- 从精确地址零引用改为扫描 `0x545000..0x545458` 邻域，找到
  `0x0806D998 -> 0x08545068`，并反汇编闭合 `0x0806D964` 消费者。
- 真实表为 63×`0x10`，地址公式 `0x545068 + character_id*0x10`；ID 57/58
  分别复用 physical record 8/15。
- 七个 u16 成长字段写入模板 `+0x0E/+0x08/+0x02..+0x06`；首战 level 1
  会令正常增量为零，因此使用严格两因素插桩 A/B 避免伪阴性。
- character 1 record `+4` 从 100→200 后，template 与 battle slot 唯一变化为
  `+2: 15→16`，结构升级为 runtime_verified。
- 人物信息页与同边界 EWRAM 已把 template `+2/+3/+4/+5/+0A/+0C/+0E/+10`
  分别关联为攻击/防御/敏捷/移动/印/当前体力/体力上限/经验；growth 的体力、
  攻击、防御、敏捷、移动字段可同步命名。随后以 `0x08089AE0` 的标签行和数值读取
  行直接闭合 `template +8 = 查克拉容量`、`template +6 = 忍具数上限`，对应 growth
  `+2/+C`；两个运行值同为 5 不再构成歧义，也不再需要 UI A/B
- 章节最小语义创作链新增严格 codec；在 `End(00)` 与三字节
  `SetBattle(1A,id,mode)` 基础上，进一步沿 handler 闭合并开放
  `ShowPortrait(02,slot,portrait,expression)`、`UpdatePortrait(04,...)`、
  `SetSpeakerLabel(08,label_id)`、`AudioCue(1B,cue_id,mode)` 与
  `RenderText(01,encoded_text_hex)`。portrait 参数复用
  已闭合的 63×5 visual matrix 与 variant 5 特殊 pair，并限制真实 slot/记录边界。
  受控 primary
  scenario 39 探针选择 codec 输出
  `0x0809E800: 1A 28 02 | 00`，恰好 dispatch 两次并将章节/战斗状态 39→40。
  这证明 authoring bytes 的运行时因果，但生产 allocator、pointer+payload 原子回写和
  对话 opcode 子集仍未完成，短路线也未冒充 strict battle-map arrival
- alternate scenario 39 已由 control-aware text walker 完整拆成 25 条 command，边界与
  runtime 分布 `1B×1/02×5/08×8/01×8/04×2/00×1` 一致，末端精确落在
  `0x0803142E`。`1B` 已由 `0x08097C9C→0x08097140` 闭合为播放/等待/停止音频，
  `08` 已由 `0x080979E8` 与 12-byte 表 `0x085A57C4` 闭合为说话人标签选择；`02`
  按需创建 portrait slot 并等待转场，`04` 更新既有 slot，二者均通过
  `0x08096138` 选择 portrait/expression 资源。`01` 复用 `0x0806626C` 的控制感知
  token walker，并只承诺已编码字节的无损创作，不把汉化字形误当作 Unicode 同一。
  scenario 39 完整 25-command/`0x1AE` 字节现可 byte-exact codec 往返；analyzer 仍负责
  地址/raw 调查证据。生产 importer 已在独立 `0x5F8000..0x5FFFFF` 分区完成四字节
  对齐 allocator、immutable-base 指针校验与 payload+pointer 原子计划；真实构建将
  scenario 39 的 430 字节语义往返 payload 写到 `0x5F8000` 并重定向到 `0x085F8000`。
  旧 DB pointer-only 写回已禁用，避免绕过 codec。随后 runtime trace 捕获 selector
  实际选择 `0x085F8000`、25 次 dispatch，并在 `0x085F81AD` 的 `00` 正常终止，
  allocator→pointer→payload→interpreter 因果链已闭合
- skills initializer 字段链已纠正为 source `+0→runtime+1`、`+1` skip、`+2..+9`
  原位复制，`+A/+B` 另有 consumer。自然“术列表”控制器把 skill ID 1 与 `0x80`
  合并并命中 initializer；只改 row 1 `+4:6→7` 后，runtime `+4` 与可见攻击力
  `6×3→7×3` 同步改变，因此 skills 升级 runtime_verified
- skills 的非详情字段进一步闭合：`+0` 是战斗显示/动画族；`+A/+B` 构建前置技能到
  可联动候选的映射；`+C/+D` 是最多两个 ID 的资格白名单。它们均有明确消费者与
  错误反馈路径。自然详情另闭合 `+4` 攻击力、`+5` 距离、`+6` 成功率、packed
  `+7` 次数/直线和 `+8` 范围；`+2/+3/+9` 继续保持未知
- 战斗动作详情渲染器已锁定为 `0x080708BC`：action ID 高位清零时调用 effect
  initializer `0x0806D85C`，置位时才在 `0x08070906` 调 skills initializer
  `0x0806D910`。教程“忍者组合拳”是低位 effect 2，解释了旧 skills 探针零命中。
  旧强制 high-bit 诊断只作为负边界保留；现已由自然术列表 skill 1 的稳定可见 A/B
  取代，不能再用旧诊断的零可见差异否定新证据
- function-pointers 已从“11个看似有效 Thumb 指针”推进到真实 dispatcher 消费链：
  `0x08061D8C` 从 sentinel base `0x53D5F0` 按一基 ID 取表项并写入 task callback，
  11个 wrapper 均把对应 ID 传给 `0x08061C58`。自然标题人物图鉴路线两次命中
  ID 2 / entry `0x0853D5F8` / pointer `0x08061C99`；只把该四字节槽替换为相邻
  wrapper 3 后，同一输入提前分叉并留下未完成资料面板，因此升级 runtime_verified。
  variant 在再次 dispatch ID 2 前已分叉，其专用 scratch 为零，证据不把它误写成
  第二次 pointer hit
- `encounter-zones` 已证伪：其47行完整重复 maps，所谓 `zone_id` 实为已运行时
  追踪的 map `flags`/渲染配置字段；旧 bank 现为空且禁写。
- 历史 `cutscene-scripts@0x53DF70` 已修正为两个相邻的四记录视觉资源表：
  `0x08072EDC` 按 ID 0..3 解压 gfx/palette，并把第二组 pair 交给 sprite task，
  因此升级为 code_verified，但不再作为剧情脚本证据。`cutscene-obj-v1` 已导出
  4 张 atlas、10 张静态 frame 和 10 份动画 timeline；自然 loader 的 flags `0x08`、
  16 位 timer 与终止策略证明四条 animation 0 持续 1 次 renderer 更新，其余六条
  持续 65,536 次后停用。单 task 时序已闭合；调用者整体清理和最终屏幕合成仍未完成。
- 历史 `battle-encounters@0x542384` 已纠正为从真实 `0x54229C` 视觉资源表
  第14条 `+8` 处开始的错位切片；真实24条记录由剧情 opcode loader 消费，
  每条三条 LZ77 流，因此升级 code_verified，旧 editor 行禁写。
- 历史 `map-events@0x53EB08` 已纠正为完整 `0x53E698` 256×8-byte handler
  pair 表的 index 142 起始切片；消费者按 runtime state byte 同时选择 primary /
  secondary callback，因此升级 code_verified，旧47行 editor view 禁写。
- `battle-handlers@0x53E6D8` 又被证明是同一 handler-pair 表的 records 8..14
  重复视图，现为空、禁写的 disproved tombstone。
- `palettes` / `map-sprites` / `sprite-animations` 三个重叠目录已拆清：前两者
  分别修正为15条 motion/effect 参数与43条 sprite pair 并 code-verified；后者
  是 pair 24..42 的重复视图，已 tombstone。三个 legacy editor shape 均禁写。
- `fonts` 旧表跨入 handler pairs，已证伪；`levels` 修正为 `0x5459C8`
  45×12 effect/stat progression records。`resource-pointers` 曾修正为5×16嵌套
  descriptor，但 2026-07-30 进一步证明它是 `0x596D5C` 角色视觉矩阵
  rows 27..31 的别名，现已 tombstone；`levels` 保持 code_verified。
- levels 的真正 Continue 已复现：Naruto level 1、经验100/250、训练点`+BA=0`；
  自然 selector 证明“移动→对战→木叶丸对白”消费 primary scenario 41 脚本
  `0x08031A12..0x08031D5F`，44 次 dispatch 后 opcode 00 正常终止、无 SetBattle，
  随后 UI 是 story 后任务准备而非标题图鉴。`A→B→Down×2→A` 曾产生瞬时 battle41，
  但完整 settle 回到 battle/map=0 的队伍页，已作为控制器假阳性撤销；真正入口必须
  settle 后仍可操作。目标仍是 A880=3 / level2 / 分配前训练点1
- scenario 41 开始任务控制流已纠正：`0x08097C78` 是 opcode `0x1A` handler 的
  中间指令而非 SetBattle 函数入口；story-only script 已留下 battle ID，正常开战由
  selector 4 → `0x08086A54 return 1` → `0x080871BE..C4` 复制到 battle control，
  不要求新增 selector/opcode hit。下一运行探针按该三段链路签发，详见
  `notes/battle-start-control-flow-20260713.md`
- `data-table-a/b` 已从20条尾片恢复为46条人物资料文本和79条战斗消息文本；
  `tile-assets` 已恢复为79×0x44战斗视觉 descriptor，三者均 code-verified。
  2026-07-29 进一步纠正旧静态导出把 C 层统一当作 4bpp 的错误：消费者明确将
  A/B/D 作为 4bpp、C 作为 8bpp，并为 C 复制 128-byte/64-color palette；
  `tile-assets-bg-v2` 已重导 236 个逻辑图层和 108 个 atlas，独立验证
  79/79 descriptor、236/236 complete layer、108/108 atlas。24 条 story visual
  的 `config_id` 也已证明直接零基索引该表，BG3 overlay 与 linked B/C/D 分别绑定
  BG3/BG2/BG0/BG1；config 61 交换 C/D priority，D 仅 config 10/16/61/74 实际加载，
  config 16 初始启用。BG3 通用初始化的 `0x0300` 只是中间值，剧情路径在启用前于
  `0x08087CEA` 覆盖为 `0x030C`，闭合 charblock 3、screenblock 3 与 gfx
  `0x0600E800`/tile `0x140` 的地址一致性。后续时间线解释器进一步闭合 installer
  内部 16 tick + controller 90 tick 的 106 tick linked 状态、16 帧灰度变换、wall
  frame 144..383 的 overlay，以及 6 种实际 callback mode；24 份逐 tick JSON 与
  24 张关键帧 contact sheet 已进入 `story-scene-timelines-v1`，可供剧情编辑器离线
  预览。当前只签发确定性 text-BG 离线合成；shadow register 提交顺序、window 边缘和
  代表配置 mGBA golden frame 未闭合，因此不宣称 runtime pixel equivalence。证据见
  `notes/tile-assets-bg-export-20260729.md`、`notes/story-scene-layer-bindings-20260729.md`
  与 `notes/story-scene-timelines-export-20260729.md`。
  紧邻 `menu-ui` 之前的 `0x085A4CE8` 也已闭合为 9×`0x1C` 角色场景视觉包：
  9 张 8bpp 紧致背景、9 组 4bpp OBJ、18 张双 palette atlas 和 16 张 definition
  frame 已进入 `scene-visual-packs-v1`。进一步由 spawner `0xA0` flags、allocator
  活动位、16 位 timer 和 `0x20` 终止策略证明：16/16 animation 的零 duration
  会在 65,536 次 renderer 更新后回绕并循环同号 frame；116 个文件（含 16 份编辑器
  timeline JSON）由独立 verifier 复核。后续已从 controller 指令纠正并闭合
  两种mode的真实路由已纠正为8张main与1张exit稳定BG+OBJ合成：main task最后更新只到
  counter 31，稳定 Y 为 10/70；exit 从 `(240,128)` 到稳定 `(85,128)`，并非旧
  未提交实现假设的目标端点。BG0 priority 2、main OBJ priority 2、exit OBJ
  priority 3 的链也已闭合；exit OBJ 只透过 BG index 0 显示，取代旧无条件覆盖
  合成。OBJ frame、palette bank、animation时序、稳定viewport crop及403次
  背景scroll写入、521个独立task运动见证已闭合；state 3外部门禁、跨task调度、
  presentation overlay、mGBA像素等价和自然语言名称仍保持未完成。证据见
  `notes/scene-visual-pack-export-20260729.md` 与
  `notes/scene-visual-composites-export-20260730.md`。
  紧接的 `0x085A8014` 已闭合为 3×`gfx/map/palette` 世界地图背景表：
  三张 8bpp、512-tile、240×160 完整画布与三条 `0x10` 编码标签已进入
  `world-map-backgrounds-v1`。三个压缩 map 指针不同但解压内容完全一致，故只保留
  一份共享 tilemap；标签的 9 个唯一字形全部复用 `dialogue-font-v2`，不重复建立
  字体资产。独立 verifier 已复核 3/3 背景和 3/3 标签；文本 context 的最终 palette、
  屏幕坐标、选择光标及 BG 合成仍保持未完成。证据见
  `notes/world-map-background-export-20260729.md`。
  随后的 accepted scenario 42 世界地图快照 GPU capture 已闭合 page 0：
  BG0 精确匹配静态 gfx/palette/30×20 map，BG3 证明四个字形实际为 32×16 的
  8×16 纵向半块布局，位置 `(32,8)`、palette bank 14；唯一活动 OBJ 是
  `(184,8)` 的 16×8 选择光标。page 1/2 与选择切换时序仍未完成，证据见
  `notes/world-map-runtime-composition-20260729.md`。
  同期回查字体消费链，纠正 `dialogue-font-v2` 把 32-byte SJIS 源记录固有解释为
  16×8 水平字形的错误：源记录只定义两个有序 8×8 half-tile；已枚举的
  `0x0806626C`、`0x0808CE8C`、`0x0808CF08` 三个 tilemap consumer 全部按
  8×16 垂直排列；`0x0808942C` 只是 `0x08089310` 函数内部 cache path。
  两张 SJIS 组合图集已按 8×16 重生成，ROM 源字节与 4bpp 展开保持不变，独立 verifier 复核
  4602/4602 字形、9012/9012 half-tile。现有六个 accepted 世界地图快照的
  `available_count` 均为 1，不能用无效 LEFT/RIGHT 输入冒充 page 1/2 验证。
  `menu-ui` 随后由 `0x08096138` 纠正为63×5 visual variant matrix，加 special
  variant 5 pair；旧20项是records 61–62。record 7 / variant 0 的单因素 pair A/B
  又令同一步 `ShowPortrait(1,7,0)` 从卡卡西变为小樱，因此升级 runtime_verified。
  当前无 static bank。
- `data-table-a` 的 selected-pointer hook 已通过自然标题人物图鉴闭合。两边均在
  `0x0808B1A4` 命中一次 character 0 / entry
  `0x085A143C`；只替换该四字节指针为 entry 7 后，目标从 `0x0859F988` 变为
  `0x0859FDE8`，可见多行人物简介同步改变，因此升级 runtime_verified。旧 state
  `0x20` checkpoint 属于另一套三栏 UI，不再作为此 reader 的前置状态。
  后续复放确认原输入没有加载随附 save；该纠正不影响 reader A/B，但禁止把它当作
  存档进度或 levels 入口
- 已新增 base-ROM 可独立重放的真实 battle 41 actionable checkpoint：Naruto
  `(4,10)`、Iruka `(4,4)`、map 36×44，strict arrival 全过。基于该边界的三条
  专属探针当时进一步排除了入场期 `resource-pointers`、普通忍术下的组合关系 reader、
  以及无效目标提示属于 `data-table-b` 的假设；三项严格保持 code_verified，下一步
  从有效攻击/技能事件捕获真实运行 ID。后续别名纠正证明
  `resource-pointers` 无需再做独立运行时升级。详见
  `notes/remaining-runtime-bank-probes-20260713.md`。
- battle 41 的最小编成诊断又把伊鲁卡移到相邻 `(5,10)`：敌对时可被范围光标选中，
  但教程拒绝直接攻击；同阵营时提交移动直接进入教程对白，skill-relation 专属 scratch
  仍为零。该路线是剧情假阳性，不再作为组合技能入口继续扩展
- `character-stats-b@0x545200` 被证明是 record 25 `+8` 的错位别名，保留
  disproved tombstone；错误 bytes 写回已改为 diagnostic。
- 交付：`tools/extract_character_growth.py`、
  `tools/build_character_growth_probe.py`、验证器和回归测试；完整证据见
  `notes/character-growth-runtime-chain-20260711.md`。

### 2026-07-11 Save-state 首战 SRAM 负结果

- WASM 探针现会在导航前后读取七个已知 SRAM 记录并验证 19+1 checksum；
- 标题→新游戏→首战路线成功，但七条记录均保持 `FF×20`，证明该路线不自动保存；
- save-state 仍为 code 证据，下一步必须定位并执行显式保存菜单，或在
  `0x08068684` 捕获真实写处理器调用；
- 结果与哈希见 `notes/save-state-wasm-probe-20260711.md`。

### 2026-07-10 u32 指针表回写进展

- 新增带索引边界、48 Mbit ROM 地址范围、Thumb bit 和数据指针对齐检查的通用
  u32 指针表真实回写 helper，并补充 6 项单元测试。
- `map_events` 与 story B–E 当前可生成 88 个真实表补丁，不再写 audit 保留区。
- 安全检查发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行 DB 数据使用陈旧
  `_rom_offset`，现已拒绝回写；下一工作周期需从 `rom/base.gba` 重新导入并验证。
- `battle_encounters` 的旧混合值解释仍需纠正；`cutscene_scripts` 已确认是八个
  视觉资源 pointer pair，不是脚本表。详见
  `notes/cutscene-visual-resource-consumer-20260712.md`。
- 第二批当时把 data table A/B、function pointers、menu UI、resource pointers、
  sprite animations、tile assets 共 135 行转换为带严格校验的真实 ROM 回写。
  后续身份纠正已经撤销其中多个 legacy partial view；2026-07-30 又证明
  `resource-pointers@0x596F0C` 是角色视觉矩阵 rows 27..31 的别名，其生成器现为
  diagnostic-only，禁止独立写入。palette 因表冲突证据不足仍保持隔离。

```
P0-Step 1（mGBA调试） ✅
       ↓
P0-Step 2（tilemap） ✅
       ↓
P0-Step 3（战斗配置） ✅（ROM 表已定位，patch 生成可用）
P0-Step 4（章节流程）
P0-Step 5（资源提取）
P0-Step 6（变长对话）
P0-Step 7（测试闭环）
       ↓
100% 逆向覆盖
       ↓
网页编辑器开发
```

---

## 不该现在做的事

1. 不要现在开始写大量剧情 —— 格式还没定，内容随时可能废弃
2. 不要现在开始建网页编辑器 —— 等逆向覆盖到 80%+ 再动手
3. 不要把手工十六进制修改当正式开发流程 —— 一切要走 pipeline

---

## 网页编辑器架构（逆向完成后）

**技术方案：** FastAPI + Vue + SQLite

**服务器：** 14.103.49.74:443（Debian 12，2核/4GB）

**架构图：**
```
用户浏览器 (Vue)
    │ HTTPS
[FastAPI 服务]
    │
 ┌──┼──┐
 │     │
SQLite  ROM文件
(队列)  (本地)
 │
WebSocket
(协作编辑)
```

**功能模块（逆向完成后按序开发）：**

| 模块 | 说明 |
|------|------|
| 对话编辑器 | 文本表单，调用 import_dialogue.py |
| 地图编辑器 | Canvas 瓦片地图，调用 import_map.py |
| 角色编辑器 | 数值表单，调用 import_battle_config.py |
| 技能编辑器 | 效果链配置 |
| 道具编辑器 | 表格编辑 |
| 剧情编辑器 | 分支对话树 |
| 构建验证 | build_mod.py 输出可下载 patch ROM |

**优先级：** 对话 > 地图 > 角色 > 技能 > 道具 > 剧情

---

### 2026-07-21 Butano 功能等价重建预研

- 已在 `codex/butano-foundation-research` 分支将 Butano 21.7.1 固定为 submodule，提交为 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`；源码、离线 API 文档、示例和完整游戏样例均保存在 `third_party/butano/`。
- devkitARM Docker 工具链已按不可变 SHA-256 摘要锁定；最小木叶战记工程、官方 sprites 示例和 audio 示例均完成编译验证。
- 原 40/66/106 人周与 70–90 人周预算已取代，不再作为计划依据。当前估算以同一 Codex 模型实际完成的 B1–B6 六项任务为样本：总计 29.34 分钟，覆盖行动状态机、寻路、战斗效果、章节脚本、存档编解码与 Butano ROM 集成。
- 按 900 个逻辑单元与 160 个集成单元外推，全部基础系统功能等价重建为 80.9/121.3/191.2 Codex 连续墙钟小时；建议按 121.3–191.2 小时规划，并在首个真实纵切片后重校。该口径不计逆向补证、内容生产和旧存档兼容。
- 预研报告见 `docs/butano-konoha-systems-cost.md`，原始计时记录见 `notes/butano-agent-timing-benchmark-20260721.md`，本地使用手册见 `docs/butano-local-reference.md`。本阶段已实现可运行的五类基础微型纵切片及 ROM 内嵌自检，但尚未完成完整战棋、章节、AI、成长和内容系统。

### 2026-07-21 Butano scenario 41 战斗纵切片

- 选择运行证据最完整的 scenario 41“鸣人对伊鲁卡”作为首个功能等价关卡：9×22
  战棋格、初始坐标 `(4,10)` / `(4,4)`、移动暂存与取消、COMBO/WAIT 菜单、敌方
  确定性寻路、第 4 回合组合技胜利、结果页和重开均已进入 Butano 工程。
- 关卡领域核心与 Butano 显示层分离；新游戏测试覆盖初态、移动、取消、AI、非法目标
  不变性、自然胜利、结果/重开和页面文案，既有 benchmark 能力通过兼容头继续复用。
- 用户手册见 `docs/butano-scenario-41-battle.md`，构建及运行证据见
  `notes/butano-scenario-41-runtime-20260721.md`。资源守卫下的干净构建、17 次显式输入、
  胜利/结算/重开截图与最终 save-state 均已完成；移动范围原先逐格执行 198 次寻路导致
  输入丢失的问题也已修复并由同一冷启动路线复验。该单关卡纵切片当时被标记为验收完成，
  但这一结论已在 2026-07-22 在线录屏复核后撤销；入口演出和通用玩家/敌方行动循环补齐前，
  只能复用其局部资产、组合拳动画和已验证音频，不能作为完整功能等价关卡。

### 2026-07-22 Butano 通用战斗架构首个实现切片（2026-07-23 已否决）

- 当时新增了固定容量 `BattleSession`、行动资格、演出队列、能力/效果、目标表达式和确定性 AI 等类，并让 scenario 41 的固定路线调用它们；但这些类没有消费完整角色/动作数据，也没有生成原作完整回合，因此不能据此称为通用战斗架构已经实现。
- 入口现按“玩家亮相 → 敌方亮相 → 开始标题 → 30 帧自动黑场 → 可见对白等待 → 手里剑转场”推进；自动步骤不读取 A，L/R 已接入可行动单位轮换。确认开始后不再依赖黑屏中的额外 A。
- GBA 运行暴露了宿主测试未显示的性能问题：逐候选格重复 Dijkstra 会令敌方阶段长时间停帧。现改为单次可达代价场，受守卫 mGBA 在 frame 740 正确进入教程，并完成 2580 帧胜利/结果/战后路线。
- 当前 ROM SHA-256 为 `e04e218e9dbcede120f0b8544e44a47df68160258539d40eea303afd25fa44a6`；证据见 `notes/butano-battle-architecture-implementation-20260722.md`。
- 本节的旧“状态/规则架构已落地”结论已被 2026-07-23 用户验收推翻。入口和战斗主体使用截图/固定选项拼接，scenario 43–50 所需的多单位、召唤、护送、捕获、替身以及完整角色/技能内容均未实现；旧 ROM 只保留为反例和素材对照，不再作为新架构实现基线。
- 2026-07-23：纠正 Butano scenario 41 的截图拼接实现。活动战斗阶段已改为组件渲染，角色 1/30
  从生成内容实例化，玩家教程动作与敌方六动作 loadout 进入共享 resolver/AI；mGBA 完整 2580 帧
  路线通过。ROM SHA-256 `aefce90b11fcf9f41a7442ed73b36e69b3c5986be2a00a98cb8b6ecfd5c91b0d`。
  这只完成了领域基础与单关运行闭环，剩余 handler、多目标、完整 AI/condition 和跨关卡场景继续推进。
- 2026-07-29：全量闭合原 ROM 战斗特效静态资源表 `0x0859911C`。19 个 8 字节记录中
  group 0 为全零哨兵，group 1..18 均为有效 LZ77 graphics/palette 对；批处理共导出
  53,344 字节、1,667 个 4bpp tile 和 18 份 16 色 palette，形成 18 张索引色 atlas、
  解压二进制与哈希 manifest。独立 verifier 不复用 exporter，重新从基准 ROM 解压并
  核对表/consumer 代码、全部二进制、PNG 索引像素、RGB palette、透明色与文件集合，
  结果为 18/18、`errors=[]`。成果位于
  `artifacts/battle-effect-resource-pairs-v1/`，说明见
  `notes/battle-effect-resource-pairs-export-20260729.md`。本里程碑签发全部静态像素和
  palette 来源，不把 tile atlas 冒充最终动画；完整 sequence 映射、OAM 合成、逐帧
  hold、blend 和音频绑定仍未闭合，Goal 保持 active。
- 2026-07-29：闭合相邻的 regular BG 场景资源表
  `0x0859903C..0x0859911C`。14 个 16 字节 descriptor 中 ID 0/8 为全零哨兵，
  ID 1–7 是 battle-map 关联的 4bpp BG，ID 9–13 是特殊场景使用的 8bpp BG。
  批量导出 12/12 项的原始 LZ77、graphics、384-byte palette、32×10 u16
  tilemap、256×80 source strip，以及按 loader 填充规则重建的 256×160 可见画布；
  共 11 份唯一 graphics、12 份 palette、8 份 tilemap。独立 verifier 重解压并
  核对表/consumer 哈希、4bpp/8bpp tile、flip、palette、PNG pixels 与精确文件集合，
  结果为 12/12、`errors=[]`。成果位于 `artifacts/bg-resource-canvases-v1/`，
  说明见 `notes/bg-resource-canvases-export-20260729.md`。全部自然语言 scene 名称、
  滚动偏移及最终 BG/OBJ 合成仍未闭合，Goal 保持 active。
- 2026-07-29：将地图表 `0x0853D910` 的全部 47 个 primary 和 14 个非空
  alternate 布局展开为 61 张完整索引色画布及 GBA BG u16 tilemap，并导出
  graphics、palette、layout、metatile、collision 共 166 份按内容去重的编辑器源
  资源。独立 verifier 从基准 ROM 重解压并逐字节/像素检查全部 289 个文件，结果为
  47/47 maps、61/61 canvases、`errors=[]`；成果位于
  `artifacts/map-canvases-v1/`，说明见
  `notes/map-canvases-export-20260729.md`。本里程碑闭合完整静态地图画布，不把
  alternate 候选冒充运行时已选布局；其选择规则、滚动/分块和动态占用叠层仍待闭合，
  Goal 保持 active。
- 2026-07-29：闭合已识别战斗动作域的静态选择链。导出 `0x0853E596` 的 256 项
  runtime-state → sequence selector，其中前 87 项与 active action 0..86 精确连接；
  高位编码 `0x80..0xDD` 通过保留 bit 7 的 event/runtime action byte 与 94 个 ninja
  tool ID 0..93 精确连接；另导出
  `0x0853EF30..0x0853F140` 的 22 个 sequence descriptor、四个 resource-group 槽、
  init-once/tick 回调和全 ROM 67 个 selector 直接调用点。独立 verifier 结果为
  256/256 runtime-state、87/87 active-action、94/94 ninja-tool、22/22 descriptor、
  `errors=[]`；
  成果位于 `artifacts/battle-effect-sequence-bindings-v1/`，说明见
  `notes/battle-effect-sequence-bindings-export-20260729.md`。至此两个已识别动作域 →
  sequence → 已导出静态像素组的映射闭合；未识别 selector 值不赋予动作语义，
  当时未闭合的 callback child frame/OAM/hold 已由下一里程碑继续推进；最终动态合成、
  blend 和音频仍未全量闭合，Goal 保持 active。
- 2026-07-29：将18组战斗特效静态像素继续闭合为完整 child 动画：解析
  `0x085991B4` 的19项 definition/animation 指针对，导出178个 frame definition、
  437个 component、23条 animation、193个精确 hold keyframe和178张源空间帧；
  每组全部解压图块均被至少一个 component 覆盖。22个 sequence 的 callback spawn
  plan也已闭合，包括 sequence 2/3 的14-child扇出在 tick 111 结束、sequence 18
  强制 variant 0 并在 tick 76 结束。独立 verifier 返回18/178/437/23、
  `errors=[]`；成果位于 `artifacts/battle-effect-sprite-animations-v1/`，说明见
  `notes/battle-effect-sprite-animations-export-20260729.md`。现已继续闭合22/22
  sequence的child task原点模型：父对象静态偏移、对战侧水平镜像、角色Q8.8锚点跟随，
  以及sequence 1的RNG angle/speed与逐tick Q8.8状态转移均有ROM绑定公式。renderer
  又闭合最终renderer坐标到attr0/attr1的8/9-bit字段wrap、12种shape/size编码、普通
  battle-effect attr2的tile/palette/priority及guarded non-affine flip公式；继续以
  `0x08062C7C..0x08062D92`闭合四组IWRAM Q8.8偏移选择、两阶段Q8.8 scale/extent
  与四项可见性gate，并定位`0x03000054`偏移表的全零初始化、按槽重置和至少一组
  状态驱动动态更新。bit 22动态OBJ VRAM分支也已闭合source/destination/size、
  16槽enqueue、连续tile offset与attr2公式；当前22条sequence全部清bit 22而不可达。
  status-1消费者以同步CpuSet完成拷贝后清槽，且dispatcher先render、后flush的相对
  顺序也已闭合。affine writer继续闭合component独立angle offset、task angle、
  sin/cos、逆scale PA/PB/PC/PD、attr1 matrix index及group 2/3当前可达的
  `{±240,0,0,240}`矩阵；`0x08062AF2..0x08062B60`又闭合task angle对component
  中心的scale后旋转，并区分component angle只旋转自身像素。唯一绝对RNG轨迹、偏移表
  完整调度/逐帧值、动态队列外层硬件帧phase/容量失败仍待闭合。affine像素逆采样现
  已按mGBA `software-obj.c`闭合有符号Q8.8边界、double-size、透明和matrix镜像规则，
  并为group 2/3当前可达矩阵导出四张独立复核参考图；这些是源码模型而非真机golden。
  既有tool 49 trace现又闭合frame 152–179的28帧、44个正常侧affine OAM实例，
  runtime tile/palette与group 2 ROM资源逐字节一致，代表帧像素哈希也与source-model
  一致，并持久化可恢复快照与GPU域。随后从该快照零输入恢复，定位sprite slot 126
  的`0x03005940` render flags，以bit 15和frame-1 keyframe两项显式patch完成受守卫
  单帧镜像probe；runtime OAM为`0x0550/0x82A0/0x79D8`、matrix slot 1为
  `{-240,0,0,240}`，tile/palette不变，像素哈希与source-model镜像预览一致，且新的
  可恢复`.ss9`、截图、GPU域、audit/guard均进入同一artifact。至此正常侧与阵营水平
  镜像runtime OAM golden均闭合；物理GBA采集、完整OAM→viewport实例、parent释放
  0/1 tick边界、blend和音频仍未闭合，Goal保持active。
- 2026-07-29：纠正旧扫描候选 `0x085A2B08..0x085A2EE8`。消费者证明它并非
  62×16 四指针表，而是 79 项 message pointer 表和 172 项 LZ77 glyph pointer 表
  的错误拼接视图，且旧终点漏掉 glyph 169–171；相邻 `0x085A2EF4` 为 79×10
  message/glyph binding。批量导出 79 条原始 NUL 字节串、172 份 512-byte 4bpp
  graphics、172 张 32×32 索引图和完整总览，171 份唯一图形中 138 份被 binding
  引用。独立 verifier 从 ROM 重建表、LZ77、raster 和 PNG，结果为
  79/79 messages、172/172 glyphs、`errors=[]`；成果位于
  `artifacts/battle-presentation-glyphs-v1/`，说明见
  `notes/battle-presentation-glyphs-export-20260729.md`。同轮证明
  `0x085A4E14` 只是已导出 63×5 立绘矩阵的非零后缀，不再重复立项。消息字符映射和
  最终 screen-space 合成仍未闭合，Goal 保持 active。
- 2026-07-29：闭合战斗演出字形的运行时 palette 选择链。初始化函数
  `0x080983B8..0x0809860E` 固定把 `0x083E4AF0` 的 16 色 BGR555 palette 复制到
  OBJ palette bank 13（`0x050003A0`），显示 consumer 再从同一状态字段选择 bank 13。
  artifact 新增 172 张精确运行时配色 PNG、透明索引 0、运行时总览和原始 palette；
  独立 verifier 从 ROM 重建 palette、两套 PNG 及文件集合并通过篡改测试。消息字符
  映射和与 79×0x44 effect descriptor 的完整逐帧合成仍未闭合，Goal 保持 active。
- 2026-07-29：闭合 79 项 visual descriptor 与 79 条表现消息的同索引目录。
  `0x08098442..0x08098460` 将 1-based input ID 减一后以 `×0x44` 选择
  `0x085A320C` descriptor；`0x08099564..0x08099582` 从同一状态字节以 `×4`
  选择 `0x085A2B08` message。统一 artifact 逐项关联 236 个完整静态图层、284 个
  实际 glyph 槽和 10 个 `0xFF` 跳过槽，并生成 79 张 A/B/C/D＋消息字形编辑器预览。
  独立 verifier 返回 79/236/284/10、`errors=[]`；成果位于
  `artifacts/battle-visual-catalog-v1/`，说明见
  `notes/battle-visual-catalog-export-20260729.md`。预览是分区 contact sheet，
  不冒充逐 tick scroll/enable/blend、共享 VRAM 与最终 screen-space 合成，Goal
  保持 active。目录后续补入完整 17-word descriptor、packed definition、全部指针和
  运行时装载门：descriptor 0 的 D 已证明是 gfx 指针为零而不可安装的 dormant
  tilemap，不再作为待寻找资源；descriptor 4 的完整 D 则明确标记为 tick 50 的
  C-path 动态来源。编辑器模型因此已无损，但逐 tick 与 screen-space 仍待闭合。
- 2026-07-29：闭合 79 项战斗视觉的标准 consumer 离线运行时时间线。75 项可播放
  descriptor 各导出 106 个 linked tick，4 项全零 sentinel 明确不可播放；补齐
  callback mode 2/3 的横向震荡、D tilemap→C graphics 混合路径、mode 3 的 D 层
  正负 scroll，以及 descriptor 1/3 的 `0x0100` C-over-B alpha。标准 intro 同时
  闭合 17 帧 A 滚动、8 帧消息前置、6 帧槽节拍、60 帧保持和 OBJ 坐标/palette bank，
  并为每项生成 intro＋tick 16/32/50/81/106 的离线 contact sheet。独立 verifier
  返回 75 timelines、`errors=[]`；成果位于
  `artifacts/battle-visual-runtime-timelines-v1/`，说明见
  `notes/battle-visual-runtime-timelines-export-20260729.md`。shadow register
  提交顺序、window mask 边缘和代表性 mGBA golden frame 仍待闭合，因此不宣称运行时
  像素等价，Goal 保持 active。
- 2026-07-29：闭合 regular BG 的完整场景选择目录。批量遍历 primary/alternate
  110/110 个非空章节脚本槽、98 个唯一根和 14,199 个唯一 CFG 节点，精确处理两套
  text token 规则及 42 个双分支 opcode `0x06`，得到 6 个唯一 opcode `0x1E`
  背景选择记录且无解析失败；同时枚举 47/47 battle header、loader 的 4 个直接 caller
  和 selection wrapper 的 5 个 caller。成果不复制图片，而是把所有有效 ID 绑定到
  `artifacts/bg-resource-canvases-v1/` 的画布路径及 SHA-256。静态 ROM 实际观察到
  ID 1–7、9、10、12；ID 11/13 只标记为 wrapper 合法输入域可选择，不编造场景名称。
  wrapper 安全域已纠正为不连续的 `0..46 ∪ 50..54`；input 47–49 会越过 47 项
  header 表并得到无效 ID 96/36/214，loader 又无上界检查，目录将其作为明确风险保留。
  独立 verifier 从 ROM 重走 CFG、调用点、header 和上游画布，结果为
  47 headers / 6 opcode records、`errors=[]`。成果位于
  `artifacts/bg-scene-selection-v1/`，说明见
  `notes/bg-scene-selection-export-20260729.md`。自然语言场景命名仍未闭合；
  既有 checkpoint 的滚动与 mode-0 BG 单层像素已由
  `runtime-bg-composites-v1` 闭合；后续
  `runtime-screen-composites-v1` 又闭合 91 个已跟踪静态 GPU 状态的
  BG/OBJ/window/blend 合成，但不包含所有视觉状态、跨帧 scanline 行为或实体
  GBA 输出。其后的 `runtime-layer-static-provenance-v1` 又将这些 checkpoint
  的 196 个唯一启用 BG 图层与六类 345 个静态候选做 byte-level 目录：28 个三域
  精确来源、107 个部分候选、61 个未识别；独立 verifier 重建完整 payload 和
  promotion manifest，并拒绝 classification、source manifest hash 与额外文件
  篡改。该目录只闭合已观察图层的静态来源证据，不代表全游戏视觉状态、自然语言
  场景名或 camera/跨帧语义，Goal 保持 active。
- 2026-07-30：闭合已跟踪可见 BG 资源分母的最后缺口。`0x08068370` 从初始化器
  BG tiles 24–33 的两组五 tile 模板，按
  `floor(38*numerator/denominator)` 生成两种 style、39 个填充等级的完整战斗
  状态条；全 ROM 四个直接 caller、palette bank 13、工作区及 EWRAM→VRAM/tilemap
  transfer 路线均已静态绑定。30 个 checkpoint 的 60 条完整五 tile 序列全部唯一
  反推出 `(style,fill_level)`，并逐坐标覆盖父 artifact 剩余的
  181/181 cell、22/22 种内容，未命中为 0。成果位于
  `artifacts/battle-status-bars-v1/`，说明见
  `notes/battle-status-bars-export-20260730.md`；独立 verifier 自行重建
  78 条生成族并返回 `errors=[]`。这使当前已跟踪“玩家可见图像资源”未知分母为
  0/0，但不把未跟踪视觉状态、全部 caller 运行时绑定、跨帧最终合成或通用 ROM
  回写冒充完成，Goal 保持 active。
- 2026-07-30：建立全 ROM 的有限 LZ77 静态资源分母。逐字节严格解析得到
  1,099 条 type-`0x10` 语法记录，只保留源地址四字节对齐且至少有一个对齐 ROM
  u32 指针引用的 896 条；17 份哈希固定的既有 artifact JSON 按资源起点 schema
  白名单绑定 865 条，剩余 31 条现全部按 ROM 地址顺序无损打包并记录压缩/解压
  哈希、指针引用、literal-load 用户、直接 loader 和分类代码窗口。旧版任意地址
  字符串判据误吞的 `0x085B6000` 排他边界已纠正为独立图形记录。静态消费者把其中
  20 条送入 VRAM graphics、3 条送入 PRAM palette、7 条送入 WRAM visual
  metadata；另有 `0x08349368` 同时由 BG screenblock 目标和 32×20 u16 payload
  结构闭合为 text-BG tilemap，不再冒充 4bpp 图形。独立 verifier 从 ROM 重做扫描、
  解压、schema 绑定和 Thumb
  符号执行，并重建 bundle 全字节，得到 896/896、remaining 0、`errors=[]`。成果位于
  `artifacts/rom-pointer-lz77-inventory-v1/`，说明见
  `notes/rom-pointer-lz77-inventory-export-20260730.md`。这只闭合该限定静态分母；
  203 条无对齐指针的语法候选、未压缩图形/raw palette、运行时可达性、自然语言
  身份、通用写回和全部视觉状态仍不因本项升级，Goal 保持 active。
- 2026-07-30：上述 31 条新增 LZ77 中的 20 条 VRAM graphics 已全部生成
  source-order 4bpp tile atlas。静态 loader 在 32-byte 窗口内为 12 条绑定 raw
  palette、为 4 条绑定 LZ77 palette；另从全部 91 份已跟踪 `.ss9` 逐一验证完整
  payload、1D hardware OAM tile 交集和 attr2 palette bank，为 `0x0812C8B0` 与
  `0x0812D134` 唯一绑定 ROM `0x08457EA8`，形成 18/20 条源色候选和 33 张
  palette-bank candidate PNG；其余 2 条输出明确标记的灰阶 index-only PNG，
  不伪造自然颜色。12 个 raw palette
  段按 CpuSet/CpuFastSet 单位重建为 608-byte bundle，其中 `0x08405FF0` 的
  `r2=0x80` 路径按 256 bytes/8 bank 保留，`0x08463FFC` 的 CpuFastSet `r2=8`
  按 32 bytes 保留。独立 verifier 从 ROM 重做解压、copy 证据、atlas 和 PNG
  全字节；它还独立解析 `.ss9`、OAM 和 PRAM 并拒绝 palette-bank 篡改，得到
  20 records / 35 previews / `errors=[]`。成果位于
  `artifacts/rom-pointer-lz77-graphics-v1/`，说明见
  `notes/rom-pointer-lz77-graphics-preview-20260730.md`。最终 OAM 组合、两条未知
  palette、未压缩图形和通用写回仍未闭合，Goal 保持 active。
- 2026-07-30：未压缩图形主线已将 direct CpuSet/CpuFastSet 预审成果化为
  `rom-direct-cpuset-gpu-inventory-v1`。全 ROM 146 个直接 BL 均进入固定分母；
  32-byte fail-closed 常量参数窗口接纳 23 个固定 ROM→GPU 操作，当前全部为
  PRAM、15 个唯一源，其余 123 个保留为窗口内未证明项。既有 LZ77 graphics palette
  成果精确覆盖 20 个操作/12 个源；新增 `0x083F1E60`、`0x083F1F08`、
  `0x08406010` 三个 32-byte palette 源已按地址顺序无损打包为 96 bytes。
  `0x08405FF0` 的 256-byte copy 与严格 LZ77 源 `0x084060A8` 的交集被记录但
  不重复打包。独立 verifier 不导入导出器，自行重建 BL、参数、control、LZ77
  span、上游绑定、JSON 和 bundle，返回
  `146 direct / 23 accepted / 3 new / errors=[]`；语义篡改即使重算 manifest
  哈希也被拒绝。成果位于
  `artifacts/rom-direct-cpuset-gpu-inventory-v1/`，说明见
  `notes/rom-direct-cpuset-inventory-survey-20260730.md`。这里的 146 项是静态
  direct-BL 编码分母，123 项只是
  `not_proven_in_window`，不是已证明非 copy，也不声称运行时可达。该规则没有发现
  直接常量 ROM→VRAM tiles；下一步转向间接表、自定义 copy loop、DMA 和两段搬运，
  不把“直接 VRAM 命中为零”误报成未压缩图形已完成，Goal 保持 active。
- 2026-07-30：DMA 主线已将全 ROM 的 direct register-literal 预审成果化为
  `rom-direct-dma-gpu-inventory-v1`。全部 halfword 对齐位置中有 21 个
  Thumb-shaped PC-relative literal user 指向 `0x040000B0..0x040000DF`，
  DMA0/1/2/3 分布为 2/7/2/10。96-byte fail-closed 数据流同时支持 32 位
  `CNT_L+CNT_H` 写和分离的 16 位 count/`CNT_H` 写；后者先以合成测试暴露旧实现
  假阴性，再进入绿灯。当前规则没有固定 ROM→GPU 接纳项，21 项全部保留为
  `not_proven_in_window`。代表性已证明路径是 `0x0300027C→0x07000000` 的
  shadow-OAM 提交，以及 `0x08000104→0x0300007C` 的 ROM→IWRAM 初始化，均不是
  新图像源。独立 verifier 不导入导出器，重建 literal、word/split-halfword
  control 和逐项 JSON，返回 `21 users / 0 accepted / errors=[]`。成果位于
  `artifacts/rom-direct-dma-gpu-inventory-v1/`，说明见
  `notes/rom-direct-dma-inventory-survey-20260730.md`。该零结果不覆盖非 literal
  基址、跨函数/间接 wrapper、自定义 loop 或 ROM→RAM→GPU 两段搬运；下一主线转向
  分阶段 RAM slot 与已知 GPU consumer 的有限连接分母，Goal 保持 active。
- 2026-07-30：两段搬运主线已将此前散落的 hash-bound consumer 收敛为
  `rom-staged-gpu-copy-inventory-v1`。严格 allowlist 只含 3 个 family、5 个
  RAM slot 和 6 条 GPU copy route：shadow OAM 的两条等价提交、overview
  tiles/palette/tilemap 三条固定 copy，以及 battle status bar 的五 tile 动态
  BG VRAM copy。OAM 被固定为 renderer-generated metadata；overview 与 status
  bar 被固定为过程式生成，因此 accepted/new raw ROM source 均为 0，不创建空
  bundle。独立 verifier 不导入 exporter，从 ROM 和三份上游 accepted artifact
  重建代码哈希、地址、长度、分类、payload 与 manifest，并拒绝重签后的 RAM
  地址、分类、size 与 scope 篡改，返回
  `3 families / 5 slots / 6 routes / 0 raw / errors=[]`。成果位于
  `artifacts/rom-staged-gpu-copy-inventory-v1/`，说明见
  `notes/rom-staged-gpu-copy-inventory-20260730.md`。该有限分母不覆盖对话
  tilemap submit、通用异步 transfer queue、未知 ROM→RAM producer、custom
  loop 或全部两段搬运；下一主线转向 queue ABI 或固定地址 custom loop，Goal
  保持 active。
- 2026-07-30：共享 GPU copy queue 已从“未知 ABI”闭合为全 ROM 直接调用分母。
  `0x080635B8` 使用 IWRAM `0x03005BBC` 的 16×16-byte slot；status 1 保存
  source/destination/u16 size，consumer `0x0806365C` 以
  `CpuSet(...,size>>1)` 同步执行并释放 slot。status 3 的 stride/row 结构及本次
  consumer 逐行行为也已固定，但 bit 0 后续生命周期保持未完成。全 ROM Thumb BL
  解码得到且只得到 14 个直接 caller：5 个读取既有 `menu-ui` palette，1 个把
  同表 LZ77 graphics 解压并调整后从 RAM 提交，6 个使用已知 RAM 源，1 个固定
  RAM buffer 的 producer 未知，1 个 battle-effect task source 保持动态；
  新 ROM source 为 0。独立 verifier 不导入 exporter，重建 14 个 BL、queue/
  selector/caller 代码哈希、上游 bank 绑定、canonical JSON 与 manifest，并拒绝
  重签语义篡改。成果位于
  `artifacts/rom-gpu-copy-queue-inventory-v1/`，说明见
  `notes/rom-gpu-copy-queue-inventory-20260730.md`。这不覆盖间接 caller、其他
  queue、运行时可达性、对话 tilemap submit、全部未压缩图像或通用写回；下一图像
  主线应追踪 `0x08096536` 的 `0x02002880` producer，或把固定地址 custom loop
  的零候选调查成果化，Goal 保持 active。
- 2026-07-30：上述 `0x08096536` producer 已闭合。全量剧情 CFG 从 primary/
  alternate 的 110 个非空 slot、98 个唯一根遍历 14,199 个唯一节点，得到
  161 个唯一 opcode `0x17` 记录、193 次根引用；mode 0 为 48/161，其他
  mode 分母也全部建账且解析失败为 0。跳转表纠正了早期把第一个 entry 误称
  mode 1 的索引错误：`0x08096BD4` 实为 mode 0，它用 CpuSet fixed-source
  把 `0x02002882` 起的 63 色填为 `0x001F`，进入 state `0x40` 后在 tick 8
  通过 `0x08096536` 把 `0x02002880` 的 128 bytes 提交到动态 OBJ palette
  bank。受控快照只改脚本游标两个字节；零输入 240 帧为 0 写入，单次 A 输入
  命中完整 handler/fill/queue 链并记录 63 条连续 halfword 写，守卫峰值分别
  `105.01953125/84.015625 MiB`，无 mGBA 残留或 crash report。成果位于
  `artifacts/portrait-palette-producers-v1/`，说明见
  `notes/portrait-palette-producers-20260730.md`。这同时静态固定
  `0x08096D4C` 的 64 色 3/4 dim 公式，但不冒充 dim 运行时覆盖、
  `0x02002880` 全部生产者、所有肖像 palette 路径或通用回写已完成；下一图像
  主线转向剩余 scratch producer/custom loop，Goal 保持 active。
- 2026-07-30：LZ77 图形目录剩余两条 palette 缺口已完成自然入口精确断点复核。
  scenario 41 目标确认在 frame 114 命中 `0x08071BD0`，
  `0x0812D2F0 → 0x06016400` 的 1,344 bytes 完全一致；人物图鉴初始化在
  frame 54 命中 `0x0808B5EE`，`0x083496F8 → 0x06017580` 的 128 bytes
  完全一致。两次命中当刻及 frame 差不超过 240 的后续采样都没有
  hardware/shadow OAM 引用各自
  tile 800..841 / 940..943，故 bank 15/14 与唯一 ROM palette
  `0x08457EA8` / `0x083496B0` 仍只保留为候选，catalog 继续 fail closed 为
  `unresolved`。固定探针、可复用输入/命中快照和完整 GPU 域已成果化到
  `artifacts/lz77-palette-runtime-v1/`，独立 verifier 通过；两次受守卫运行峰值
  RSS 为 `58.9765625/58.21875 MiB`，无残留。详见
  `notes/unresolved-lz77-palette-survey-20260730.md`。后续不再重复这两条路线，
  只在发现新的 attr2/OAM 生成链时重开绑定调查，Goal 保持 active。
- 2026-07-30：闭合 `0x0808C214..0x0808C4CB` 两种直接调用 mode 的稳定
  scene-pack BG+OBJ 合成。后续路由审计纠正旧分母：mode 0只跑pack 0–3后退出，
  非零mode只跑pack 4–7并进入唯一pack 8 exit，因此是8张main与1张exit，9/9个
  源pack各进入唯一可达角色；旧5张不可达组合已删除。独立
  verifier 从 ROM 指令提取 task-index 运动分支、counter 31 停止边界、Q12 向零
  截断、mode初始pack/上界、退出分支、scroll、allocator参数及BG/OBJ priority，
  再重建全部9张240×160
  PNG。审查发现并由两轮红测固定了旧未提交实现的三项 P0：main 不能按 mode 把 Y
  写成 16/64，exit 不能写成 `(0,128)`，priority 3 的 exit OBJ 也不能无条件覆盖
  priority 2 的 BG；正确稳定坐标分别为 Y `10/70` 与 `(85,128)`，exit OBJ 只在
  BG index 0 处显示。成果位于
  `artifacts/scene-visual-composites-v1/`，说明见
  `notes/scene-visual-composites-export-20260730.md`。逐 tick 过渡、
  presentation overlay、运行时像素等价和自然语言身份仍未闭合，Goal 保持 active。
- 2026-07-30：菜单/剧情立绘从全量导出推进到受守卫原位回编。新增
  `menu_portrait` 构建类型，将80×80模式P PNG逆变换为六段1D OBJ流，确定性
  重压缩图形并写回128字节BGR555调色板；资源、catalog、基准ROM和原槽字节均以
  指针及SHA-256失败关闭，共享资源会显式列出全部逻辑别名。容量审计覆盖74/74
  唯一资源的原图重编码和74/74单像素修改，最小剩余槽空间均为4 bytes；311个
  逻辑立绘全部计入别名分母。独立 verifier 不导入 importer/exporter，自行实现
  LZ77编解码，从ROM和catalog重建全部记录，并拒绝重签后的容量篡改，返回
  `74 resources / errors=[]`。成果位于
  `artifacts/menu-portrait-writeback-v1/`，说明见
  `notes/menu-portrait-writeback-20260730.md`。任意PNG容量、资源迁移、指针改写、
  运行时像素等价和通用图像回编仍未完成，Goal保持active。
- 2026-07-30：角色场景控制器的阶段模型已按ROM真实顺序离线闭合。8条main背景
  轨道记录342次scroll写入，唯一exit记录61次，合计403次；main的初始scroll和
  首次4像素更新明确属于同一dispatch，全部背景记录均不在spawn前绘制OBJ。
  15条main task和1条exit task另记录521个“初态、有效位置更新、首个稳定回调”
  局部见证，不假设controller与task一一同帧，合计924张PNG进入固定元数据的单个
  约12MiB `frames.zip`。验证器不导入新导出器，从ROM重建跳转表基址、mode路由、
  spawn顺序、state 2/20计数、task插值、全部PNG及ZIP元数据；重签后篡改spawn
  语义或archive comment均被拒绝。测试/导出/验证均经heavy lock，峰值tree RSS
  约50.15/35.09/37.32MiB，`completed/0`、非降级。
  成果位于 `artifacts/scene-visual-transition-timelines-v1/`，说明见
  `notes/scene-visual-transition-timelines-20260730.md`。state 3外部门禁时长、
  跨task调度、VBlank/wall-frame、presentation overlay、window/blend/mosaic、
  运行时像素等价和自然语言身份仍未闭合，Goal保持active。
- 2026-07-30：全部战斗地图静态资源已从“只可导出”推进到受限原位回编。
  47个map header的249条非空引用按ROM起点形成217个物理LZ77槽，再按资源类型与
  解压内容去重为166份编辑资源；新`map_resource`构建类型会将一次内容修改同步
  写回全部物理别名，并在返回补丁前验证基准ROM、catalog、内容SHA、长度、格式和
  layout→metatile→tile/palette跨资源索引及所有槽容量。任一索引越界或槽溢出时
  整项失败，header指针保持不变。完整容量审计证明
  166/166内容、217/217物理槽可原样确定性重编码；固定低位变异有135/166内容、
  163/217槽可装回，剩余31内容/54槽明确进入容量失败边界。独立verifier从ROM和
  47个header重建`249→217→166`分母及LZ77编解码，并拒绝重签后的slot语义篡改。
  成果位于`artifacts/map-resource-writeback-v1/`，说明见
  `notes/map-resource-writeback-20260730.md`。超槽迁移、指针改写、完整画布PNG
  反编译和全地图运行时像素等价仍未完成，Goal保持active。
- 2026-07-31：18组战斗特效静态资源已从全量导出推进到受限原位回编。
  pair table的36条graphics/palette逻辑引用形成35个物理LZ77槽，并按资源类型与
  解压SHA去重为34份内容；group 2/3的共享graphics只写一个槽但保留两个逻辑别名，
  group 16/17的同内容palette默认同步两个物理槽，也可按两个不同物理指针显式
  拆分编辑，真正共用同一指针的逻辑别名不可分裂。新`battle_effect_resource`
  构建类型验证基准ROM、catalog、pair指针、内容、格式和全部别名容量，任一槽溢出
  即整项失败且36个指针保持不变。容量审计证明34/34内容、35/35槽可原样重编码；
  固定低位变异有31/34内容、32/35槽、33/36逻辑引用可装回，三条溢出graphics
  明确进入失败边界。独立verifier从ROM重建`36→35→34`并拒绝重签后的slot语义
  篡改。成果位于`artifacts/battle-effect-resource-writeback-v1/`，说明见
  `notes/battle-effect-resource-writeback-20260731.md`。迁移、指针改写、
  任意编辑容量及修改后OAM/affine/blend/时序/音频等价仍未完成，Goal保持active。
- 2026-07-31：角色战斗视觉的完整 palette 分母已从只读导出推进到安全原位回编。
  342个有效逻辑槽、250套descriptor资源收敛为48个互不重叠的32-byte物理
  BGR555槽和40份唯一内容；新`character_battle_palette`构建类型按物理指针与
  原始SHA标识编辑，同指针的全部resource/slot原子联动，内容相同但指针不同的槽
  保持独立。基准ROM、catalog、558项descriptor指针、resource ID、slot row和
  固定长度均失败关闭，48/48原始内容及48/48低位修改均可写回。独立verifier不
  导入实现，从ROM重建`48 physical→250 resource→342 slot`并拒绝重签后的别名
  篡改。成果位于`artifacts/character-battle-palette-writeback-v1/`，说明见
  `notes/character-battle-palette-writeback-20260731.md`。250套graphics、
  frame/component/animation结构、迁移/指针改写及修改后运行时像素等价仍未完成，
  Goal保持active。
- 2026-07-31：regular BG 的12个有效 descriptor 已从完整画布导出推进到受限
  原位回编。36条 graphics/palette/tilemap 逻辑引用对应36个互不重叠的物理
  LZ77槽，按类型和解压SHA去重为31份内容；新 `bg_resource` 构建类型默认同步
  同内容的全部物理槽，也允许按 catalog 约束的物理子集拆分编辑。写补丁前会以
  修改后全视图验证4bpp/8bpp tile完整性、384-byte palette、32×10 u16 tilemap、
  tile index、4bpp palette bank 和8bpp像素索引；任一槽溢出即整项失败且
  `0x0859903C` descriptor 指针保持不变。容量审计证明31/31内容、36/36槽可原样
  确定性重编码；固定低位变异有20/31内容、21/36槽可装回，11份内容/15个槽明确
  进入失败边界，最差超3 bytes。独立 verifier 不导入实现，从ROM和catalog重建
  `36 logical→36 physical→31 content` 并拒绝重签语义篡改。成果位于
  `artifacts/bg-resource-writeback-v1/`，说明见
  `notes/bg-resource-writeback-20260731.md`。canvas底部运行时填充的PNG逆编译、
  资源迁移/指针改写、任意编辑容量、完整运行时选择和最终BG/OBJ/window/blend
  像素等价仍未完成，Goal保持active。
- 2026-07-31：角色战斗视觉矩阵的250套 raw 4bpp graphics 已从无损导出推进到
  固定长度安全回编。250个资源对应250个唯一物理指针和250份唯一内容，总计
  60,430 tiles / 1,933,760 bytes；342个逻辑slot中的共享资源会完整披露全部
  alias。新 `character_battle_graphics` 构建类型从基准ROM和catalog重建
  2,004帧、2,190个component，逐资源验证
  `max(tile_end)==graphics.size/32`、graphics末端等于首个frame/component指针，
  并确认250个graphics彼此及与palette/component/frame table/timeline/animation
  table零交叉。任意同长度且32-byte对齐的raw像素可原位覆盖；descriptor和结构
  字节保持不变。独立verifier不导入实现，重建完整分母并拒绝重签语义篡改，成果
  位于`artifacts/character-battle-graphics-writeback-v1/`，说明见
  `notes/character-battle-graphics-writeback-20260731.md`。变长graphics、
  frame/component/animation编辑、迁移/指针改写、运行时slot选择及修改后最终
  像素等价仍未完成，Goal保持active。
- 2026-07-31：角色战斗视觉结构已从只读解析推进到同布局高层回编。新
  `character_battle_structure` 构建类型可修改现有component的tile、H/V flip、
  s16局部坐标和12种已验证OBJ尺寸，也可修改animation keyframe的frame引用与
  非零hold；每项只覆盖原20-byte/4-byte记录。构建前从ROM和catalog重建
  250资源、342逻辑slot、2,004帧、2,190 component、784 animation和3,187
  keyframe，并验证所有tile/frame边界、pointer table、region长度和terminator。
  2,003个`ffff0000`及唯一`0x0825A8E4=fffb0000` trailer均原样保留。独立审计
  证明2,190/2,190 component及3,187/3,187 keyframe可原样语义重编码且均有合法
  同长度真实变异；verifier不导入实现并拒绝重签篡改。成果位于
  `artifacts/character-battle-structure-writeback-v1/`，说明见
  `notes/character-battle-structure-writeback-20260731.md`。新增/删除结构项、
  pointer/region迁移、运行时slot选择、相机/priority/blend及最终像素时序等价仍
  未完成，Goal保持active。
- 2026-07-31：为解除角色视觉只能原位同长度修改的容量边界，正式建立统一
  16 MiB ROM布局与分区门禁。Nintendo AGB 32 MiB Game Pak ROM地址空间和
  mGBA源码上限先完成静态复核；受守卫运行又令CPU从`0x08600000`执行stub、读取
  `0x08600100` marker并返回原入口继续启动，首个扩展分区的取指/读数因果链成立。
  frame 60快照另经直接恢复并零输入运行30帧，ROM/EWRAM marker保持一致且恢复截图
  与原图逐RGB相同，因此后续扩容调试可从该已验证快照继续。
  新`character_battle_bundle`构建类型可原子迁移palette、变长graphics、
  frame/component、frame pointer table、animation timeline和animation pointer
  table，并同步重写全部descriptor别名。全量审计把250/250资源、342/342逻辑槽、
  2,004帧、2,190 component、784 animation、3,187 keyframe和60,430 tile迁入
  `0x600000..0x7FFFFF`，占2,020,612 bytes、余76,540 bytes。独立verifier重建
  整个16 MiB输出和3,815条精确引用；唯一额外数值位于被独立指针引用的严格LZ77
  压缩负载内，已作为coincidence建账，未知外部引用为0。证据位于
  `artifacts/rom-expansion-profile-v1/`、
  `artifacts/character-battle-bundle-relocation-v1/`和
  `notes/rom-expansion-character-bundle-relocation-20260731.md`。这闭合
  角色战斗视觉的变长结构、迁移和指针改写能力；修改后全部slot的自然运行选择、
  相机/priority/blend和最终像素时序等价仍未全量闭合，Goal保持active。
- 2026-07-31：`0x085A320C` tile-assets表已从全量静态导出推进到可变长迁移。
  75个非sentinel descriptor的236个完整图层及descriptor 0的1个partial D
  tilemap形成323个物理资源：107 graphics、108 tilemap、108 palette，并有709条
  descriptor逻辑指针引用；全ROM四字节对齐精确扫描的未知引用为0。新
  `tile_asset_resource`构建类型把资源分配到`0x800000..0x980000`，允许经catalog
  约束的别名子集显式分裂，并联合验证4bpp/8bpp tile、tilemap尺寸/索引、palette
  大小、8bpp色号及保留palette-bank位。全量preservation迁移占634,112 bytes，
  末端`0x89AE00`，在注册的`0x800000..0x980000`区域内剩余938,752 bytes；
  独立verifier重新解析ROM和完整
  `RomLayout`，重建323/709分母及16 MiB输出，并拒绝重签后的别名、实现哈希和
  分区篡改。成果位于`artifacts/tile-asset-resource-relocation-v1/`，说明见
  `notes/tile-asset-resource-relocation-20260731.md`。descriptor 0 partial D
  缺失的graphics/palette生产者、修改后自然路线选择及最终window/blend/时序像素
  等价仍未闭合，Goal保持active。
- 2026-07-31：47张战斗地图的六类静态资源已从受限原位回编推进到可变长迁移。
  166份去重内容、217个原物理LZ77槽和249条map-header逻辑指针经全ROM精确扫描，
  未知引用为0；新`map_resource_relocation`类型允许按catalog约束的header别名
  子集拆分，并在分配前重验全部layout→metatile→tile/palette索引及collision尺寸。
  为防止迁移器各自从同一父分区起点分配，新增图像资源区域注册表：tile-assets使用
  `0x800000..0x980000`，地图使用`0x980000..0xA80000`，菜单立绘使用
  `0xA80000..0xB00000`，regular BG使用`0xB00000..0xB40000`，未来图像当前保留
  `0xBC1C00..0xC00000`；其间`0xB40000..0xB50000`划给战斗特效，
  `0xB50000..0xB71000`划给剧情透明BG3图层，`0xB71000..0xB90000`划给
  世界地图背景，`0xB90000..0xBA0000`划给通用Sprite bundle，
  `0xBA0000..0xBB0000`划给Cutscene OBJ bundle；注册表
  强制无重叠、无空洞和对齐。地图全量迁移占
  385,086 bytes、末端`0x9DE03E`、区域余663,490 bytes。tile与地图全量组合在
  同一安全门应用489个分配和958个指针补丁，共1,447项无冲突。成果位于
  `artifacts/map-resource-relocation-v1/`，说明见
  `notes/map-resource-relocation-20260731.md`。修改后全地图像素、动态overlay、
  camera和碰撞玩法语义的运行时等价仍未闭合，Goal保持active。
- 2026-07-31：菜单／剧情立绘已从受限原位PNG回编推进到可变长成对迁移。
  311个可见立绘对应74种逻辑pair、70个物理graphics和70个物理palette；
  63×5矩阵与全局variant 5的622个指针字段经全ROM精确扫描，额外引用为0。
  新`menu_portrait_relocation`类型继续接受80×80 indexed PNG，可按catalog约束
  拆分pair别名，并把140个payload迁入注册的`0xA80000..0xB00000`区域。全量
  preservation占231,372 bytes、末端`0xAB87CC`、区域余292,916 bytes；独立
  verifier重建74/140/622分母及完整16 MiB输出。成果位于
  `artifacts/menu-portrait-relocation-v1/`，说明见
  `notes/menu-portrait-relocation-20260731.md`。任意尺寸、可变OBJ布局及修改后
  菜单调色/转场/最终像素等价仍未闭合，Goal保持active。
- 2026-07-31：regular BG的12个有效descriptor已从受限原位回编推进到可变长
  迁移。31份去重内容（11 graphics、12 palette、8 tilemap）、36个物理LZ77
  payload和36个descriptor指针字段经全ROM精确扫描，额外引用为0。新
  `bg_resource_relocation`类型允许按catalog约束拆分同内容descriptor别名，并在
  分配前重验12个场景的4bpp/8bpp tile几何、tilemap索引、palette bank和8bpp
  色号。全量preservation迁入`0xB00000..0xB40000`，存储87,037 bytes，占用跨度
  87,085 bytes，末端`0xB1542D`、区域余175,059 bytes；独立verifier重建
  31/36/36分母及完整16 MiB输出。成果位于
  `artifacts/bg-resource-relocation-v1/`，说明见
  `notes/bg-resource-relocation-20260731.md`。不同画布几何、底部运行时填充、
  修改后选择/滚动/OBJ/window/blend及最终像素等价仍未闭合，Goal保持active。
- 2026-07-31：18组战斗特效的静态graphics/palette已从受限原位回编推进到
  可变长迁移。36条pair-table逻辑引用形成35个物理LZ77 payload，并按类型与
  解压SHA去重为34份内容；全ROM四字节对齐精确扫描额外引用为0。新
  `battle_effect_resource_relocation`类型允许按catalog约束拆分指针别名，
  group 2/3的共享graphics可独立重定向，group 16/17的同内容不同物理palette
  也不会被错误合并为不可分指针。全量preservation迁入
  `0xB40000..0xB50000`，存储20,216 bytes、占用跨度20,260 bytes，末端
  `0xB44F24`、区域余45,276 bytes；独立verifier从ROM和旧独立审计器重建
  34/35/36分母、完整spec、全部精确引用和16 MiB输出。成果位于
  `artifacts/battle-effect-resource-relocation-v1/`，说明见
  `notes/battle-effect-resource-relocation-20260731.md`。不同图形几何、OAM、
  affine、帧时序、blend/window、音频耦合及修改后最终像素等价仍未闭合，
  Goal保持active。
- 2026-07-31：24条剧情透明BG3 descriptor已从静态导出推进到可变长迁移。
  24 graphics、24 tilemap和24个物理palette流形成72个LZ77载荷，按类型与解压
  SHA去重为49份内容；全ROM四字节对齐精确扫描额外引用为0。新
  `story_visual_resource_relocation`类型允许graphics在1–192个4bpp tile内变长，
  但要求同层32×32 tilemap精确覆盖从`0x140`开始的连续tile、palette固定32 bytes
  且全部entry使用bank 15。全量原样迁移写入`0xB50000..0xB71000`，存储
  56,551 bytes、末端`0xB5DD2D`、区域余78,547 bytes。共享palette的24个逻辑槽
  可按catalog子集显式拆分，区域总容量不足时整批失败。完整tile-assets与剧情层
  在同一安全门应用1,153个补丁无冲突，24个`config_id`继续索引原
  `0x085A320C` descriptor行。成果位于
  `artifacts/story-visual-resource-relocation-v1/`，说明见
  `notes/story-visual-resource-relocation-20260731.md`。修改后自然剧情路线的
  scroll/window/blend与最终像素等价仍未闭合，Goal保持active。
- 2026-07-31：三页世界地图背景已从全量静态导出推进到可变长迁移。三条
  `gfx/map/palette`记录形成9个物理载荷和9个descriptor指针；三个物理map的
  解压内容相同，按类型与SHA去重后为7份编辑内容。全ROM四字节对齐精确扫描的
  额外引用为0。新`world_map_background_relocation`类型允许按catalog约束拆分
  tilemap别名，graphics支持1–512个完整8bpp tile，并联合验证30×20 tilemap、
  160色palette、tile索引和像素色号。全量原样迁移写入注册的
  `0xB71000..0xB90000`，存储90,082 bytes、占用跨度90,084 bytes、末端
  `0xB86FE4`、区域余36,892 bytes；独立verifier自行编码LZ77、重建7/9/9分母
  及完整16 MiB输出。成果位于
  `artifacts/world-map-background-relocation-v1/`，说明见
  `notes/world-map-background-relocation-20260731.md`。地点标签编辑、解锁规则、
  page 1/2修改后的自然选择、光标/转场和最终合成像素等价仍未闭合，Goal保持active。
- 2026-07-31：43个固定通用Sprite ID已从静态像素/动画导出推进到bundle可变长
  迁移。43个definition、43个animation table、43个component list、43个
  animation-0 sequence及graphics/palette各一份，共174条精确源指针引用；
  全ROM四字节对齐扫描未知引用为0。12个自然加载调用的OBJ tile base只取
  `0x34E/0x39F`，故最高基址927在1024-tile OBJ空间内留下97 tile；迁移器允许
  graphics为1–97个完整4bpp tile、palette固定16色、每个固定ID含1–2个合法
  component，并在98 tile时失败关闭。全量保持迁入
  `0xB90000..0xBA0000`，形成45个allocation、88个外部pointer patch和43个
  tile-base patch，共176项安全写入。独立verifier不导入迁移器/导出器，自行重建
  43/45/174分母、LZ77、全部bundle内外指针和16 MiB输出。成果位于
  `artifacts/generic-sprite-bundle-relocation-v1/`，说明见
  `notes/generic-sprite-bundle-relocation-20260731.md`。新增ID、多动画/帧、
  场景专用覆盖和修改后最终屏幕像素/时序等价仍未闭合，Goal保持active。
- 2026-07-31：4个固定Cutscene OBJ ID已从全量静态导出推进到bundle可变长
  迁移。两张四记录表及内部10个component list、10条timeline形成36条精确源
  指针引用，未知引用为0；全ROM Thumb BL扫描只得到4个自然loader调用，ID集合
  严格为`0..3`，`0x53DFB0`保持独立。graphics固定解压到OBJ tile base
  `0x300`，因此迁移器允许每个ID使用1–256个完整4bpp tile、16色palette；
  loader硬编码的frame/animation槽数保持`[2,2,2,4]`，每帧支持1–2个合法
  component，每条animation支持非空变长keyframe timeline。完整保持迁入
  `0xBA0000..0xBB0000`，形成12个allocation和16个根pointer patch，共28项
  安全写入。独立verifier自行重建36条源引用、LZ77、全部内外指针和16 MiB输出；
  capability fixture独立覆盖256 tile、11 component和11 keyframe。成果位于
  `artifacts/cutscene-obj-bundle-relocation-v1/`，说明见
  `notes/cutscene-obj-bundle-relocation-20260731.md`。新增第五ID、改变固定
  frame/animation槽数、调用者场景清理及修改后最终屏幕像素/时序等价仍未闭合，
  Goal保持active。
- 2026-07-31：十个表驱动图像域之外的残余指针可达LZ77分母已推进到图形
  payload迁移。严格分母31条中，20条是4bpp图形、3条是LZ77 palette、7条是
  WRAM visual metadata、1条是32×20 text-BG tilemap；本里程碑只迁移20条真实
  图形，不混淆类型。20项形成36,640-byte解压数据和34个精确根指针，完整保持
  迁入`0xBB0000..0xBC0000`，形成20个allocation、34个pointer patch，共54项
  安全写入。每项可替换全部tile但保持原解压长度，压缩长度不再受旧槽限制；
  `0x0812D2F0`与`0x083496F8`的palette绑定继续保持未决。独立verifier不导入
  迁移器/导出器，自行重建20/34分母、LZ77、完整16 MiB输出及20项均修改首tile
  的capability fixture。成果位于
  `artifacts/residual-lz77-graphics-relocation-v1/`，说明见
  `notes/residual-lz77-graphics-relocation-20260731.md`。palette编辑、
  metadata/tilemap ABI、业务命名及修改后最终屏幕像素/时序等价仍未闭合，
  Goal保持active。
- 2026-07-31：所有已严格证明由ROM直接复制到PRAM的图像调色板已推进到可变存储
  迁移。18个逻辑源收敛为17个物理资源和29个全ROM精确根指针：3个LZ77调色板
  固定解压为96 bytes，14个raw BGR555物理资源合计672 bytes。迁移器把786 bytes
  存储写入`0xBC0000..0xBC0314`，形成17个allocation、29个pointer patch，
  共46项安全写入，注册区域`0xBC0000..0xBC0400`剩余236 bytes。
  `0x08406010`继续严格指向`0x08405FF0+0x20`；父资源尾部与剧情LZ77流重叠的
  72 bytes被锁定，任何修改均失败关闭。独立verifier不导入迁移器或导出器，
  自行重建inventory、catalog、别名、锁定区、完整16 MiB输出和17项均可编辑的
  capability fixture。成果位于
  `artifacts/direct-image-palette-relocation-v1/`，说明见
  `notes/direct-image-palette-relocation-20260731.md`。两条残余图形的palette
  身份、7条WRAM visual metadata及修改后最终屏幕像素/时序等价仍未闭合，
  Goal保持active。
- 2026-07-31：残余LZ77分母中唯一的text-BG tilemap已推进到可变存储迁移。
  `0x08349368`的178-byte LZ77流解压为32×20、640个little-endian u16 entry，
  唯一全ROM对齐根为`0x0808B464`；原内容只使用tile 0–5、palette bank 1、0个
  H flip和12个V flip。新`residual_text_bg_tilemap_relocation`允许在上述tile/
  palette边界内编辑全部640项及标准H/V flip，原样压缩178 bytes写入
  `0xBC0400..0xBC04B2`，形成1个allocation和1个pointer patch。注册区域
  `0xBC0400..0xBC0C00`按全literal最坏1444 bytes预留，最坏仍余604 bytes。
  独立verifier不导入生产迁移器/导出器，自行重建LZ77、代码/consumer合同、
  1/1分母、全局区域连续性、完整16 MiB输出和单entry capability fixture。
  成果位于`artifacts/residual-text-bg-tilemap-relocation-v1/`，说明见
  `notes/residual-text-bg-tilemap-relocation-20260731.md`。对应tile graphics/
  palette所有权、剩余12行screenblock、另一流复用`0x06001000`的运行时顺序、
  业务名称及最终屏幕像素/时序等价仍未闭合，Goal保持active。
- 2026-07-31：上述text-BG tilemap的资源归属已闭合。自然静态链
  `0x0808F844/0x0808FA04 → 0x0808B58C → 0x0808B640 → 0x0808B2C8`
  先把`0x08348F00`的68个4bpp tile加载到BG charbase 1、把raw
  `0x0834941C`加载到palette bank 1，再把`0x08349368`写入BG2 screenblock 2；
  `BG2CNT=0x0204`，tilemap使用的tiles 0–5完整落在graphics tiles 0–67内，
  并与同family overlay使用的tiles 6–67互补。独立ownership verifier从ROM重建
  两次LZ77、palette、BG位域和代码窗口，重新签名篡改VRAM目标仍会失败。
  text-BG迁移spec/importer/verifier现均固定ownership路径/SHA，正式迁移artifact
  已重新promotion。证据位于
  `artifacts/residual-text-bg-tilemap-resource-ownership-v1/`，说明见
  `notes/residual-text-bg-tilemap-resource-ownership-20260731.md`。现有91个
  tracked checkpoint仍没有已证明自然命中该链的样本；VRAM复用顺序、剩余12行、
  精确业务名称及最终像素/时序继续未闭合，Goal保持active。
- 2026-07-31：7条残余`WRAM_dynamic` visual metadata已从混合未知集合推进到
  有限ABI目录。其中`0x0834928C`、`0x083F1C98`、`0x085B67E0`均由局部
  `LZ77UnCompWram`后紧接status-3逐行GPU queue的代码链证明为15×20、24×12、
  23×3局部BG tilemap，共657个u16 entry/1,314 bytes；目标分别是screenblock 0
  的row 0/column 15，以及screenblock 31的row 0/column 8和row 17/column 7。
  独立verifier从ROM和固定inventory重建7条分母、三段route、共享queue consumer、
  完整bundle与manifest，重新签名后篡改destination或queue call均被拒绝。成果位于
  `artifacts/residual-wram-tilemap-abi-v1/`，说明见
  `notes/residual-wram-tilemap-abi-20260731.md`。其余4条WRAM payload、队列槽成功
  与自然flush、BG/palette/graphics所有权、可编辑迁移及最终像素/时序仍未完成，
  Goal保持active。
- 2026-07-31：上述3条已证明WRAM tilemap已作为单一批量域推进到可变存储迁移。
  三条source各只有一个全ROM对齐literal根且没有span内部别名；新
  `residual_wram_tilemap_relocation`类型保持15×20、24×12、23×3几何和各自
  palette/tile边界，允许编辑全部657个entry及H/V flip。注册表从未来区域切出
  `0xBC0C00..0xBC1400`，原样迁移存储821 bytes、含对齐占用826 bytes、末端
  `0xBC0F3A`、区域余1,222 bytes；全literal最坏含对齐为1,492 bytes，仍安全。
  独立verifier不导入生产迁移器/导出器，自行重建LZ77、三项allocation、三项根
  redirect、全局RomLayout/区域注册表、完整16 MiB输出和三项同时变异fixture。
  注册表哈希变化后12个既有图像迁移artifact已全部重建、独立验证，旧哈希剩余0。
  成果位于`artifacts/residual-wram-tilemap-relocation-v1/`，说明见
  `notes/residual-wram-tilemap-relocation-20260731.md`。剩余4条WRAM payload、
  computed-pointer consumer、自然queue flush、资源所有权及最终像素/时序仍未
  完成，Goal保持active。
- 2026-07-31：7条`WRAM_dynamic / visual_metadata`有限分母已全部闭合为
  tilemap源，原剩余4条不再保持未知。`0x083F2108`是40×10源，consumer逐行
  取前32项直写screenblock 2 row 4–13；`0x084634B8`、`0x0846356C`和
  `0x084635D8`均为12×12源，经坐标裁剪、entry加`0x02BC`后写入临时
  12×12缓冲并向`0x06000806`提交。综合
  `residual-wram-visual-metadata-abi-v2`从ROM和代码窗口独立重建7/7、
  1,489个u16/2,978 bytes，未决为0。后四条又作为单一批量域迁入新注册区域
  `0xBC1400..0xBC1C00`：4个allocation、4个唯一根redirect，存储597 bytes、
  含对齐占603 bytes、末端`0xBC165B`、区域余1,445 bytes；全literal最坏
  1,888 bytes仍可容纳。独立verifier不导入生产迁移器/导出器，自行重建LZ77、
  区域连续性、四个根和完整16 MiB输出。证据位于
  `artifacts/residual-wram-visual-metadata-abi-v2/`、
  `artifacts/residual-wram-derived-tilemap-relocation-v1/`，说明见
  `notes/residual-wram-derived-tilemap-relocation-20260731.md`。自然入口、
  queue槽/flush、graphics/palette所有权、业务名称及最终像素/时序仍未闭合，
  Goal保持active。
- 2026-07-31：上述7条残余WRAM tilemap的BG、graphics与palette归属已全部闭合。
  三条直接源分别绑定BG0/BG1、`0x08348F00/0x085B6880` graphics与palette
  bank 1/8/9；裁切源绑定BG2、共享`0x085B6880`与bank 10；三条变换源绑定
  BG1、`0x08463688`及bank 12/13，并严格证明
  `charbase1 + 0x02BC*32 = 0x06009780`。新ownership artifact从ROM、ABI、
  graphics/palette迁移规格和代码窗口独立重建7/7，未决0。两套tilemap迁移器、
  authoring spec和独立verifier现均固定ownership路径/SHA并交叉检查VRAM目标、
  源/有效tile范围、tile add和palette bank；3源与4源正式artifact经实验目录验证
  后重新promotion。证据位于
  `artifacts/residual-wram-tilemap-resource-ownership-v1/`，说明见
  `notes/residual-wram-tilemap-resource-ownership-20260731.md`。queue槽/自然
  flush、运行时可达性、精确业务名称及修改后最终像素/时序仍未闭合，Goal保持
  active。
- 2026-07-31：三条直接status-3 queue tilemap中的首条已完成自然运行时闭环。
  复用`lz77-palette-runtime-v1`中人物图鉴初始化自然命中快照，零输入续跑在frame 0
  命中`0x0808AD3A`，固定`0x0834928C→0x02002B48`；frame 2首次命中共享consumer
  `0x0806365C`，slot 0为status 3、目标`0x0600001E`、行宽15 halfword、20行。
  consumer当刻的目标行尚不等于源；紧接的frame 3边界，20行拼接的600 bytes与ROM
  LZ77解压payload逐字节一致、前后600/600 bytes变化，16个queue slot中该status-3
  记录数已从1变0。独立verifier重做LZ77、解析consumer前后slot并从两份96KiB
  VRAM dump抽取stride行；同时固定并语义复核产生输入快照的accepted父
  manifest/evidence/audit，以及ABI/ownership父manifest，拒绝重签父证据、目标/VRAM、
  额外文件和符号链接篡改。三帧正式运行经统一heavy lock，`completed/0`、无残留；
  相同快照的80帧开发复核峰值RSS为`62.9453125 MiB`。成果位于
  `artifacts/residual-wram-tilemap-runtime-v1/`，说明见
  `notes/residual-wram-tilemap-runtime-reachability-20260731.md`。直接queue子分母现为
  1/3；这闭合本记录的自然queue route，但不签发frame 2入口至frame 3边界间的
  排他writer因果。`0x083F1C98`、`0x085B67E0`及修改后最终像素A/B仍未闭合，
  Goal保持active。
- 2026-07-31：三条直接status-3 queue tilemap的自然运行时子分母已由1/3推进到
  **3/3**。从`residual-wram-tilemap-runtime-v1/final.ss9`只输入一次B，在frame 28
  命中`0x0808BAB0`并保存setup断点快照；其后5帧零输入续跑于frame 2同时命中
  `0x083F1C98→0x02002B78`和`0x085B67E0→0x02002DB8`的LZ77加载。frame 3首个
  consumer快照中，slot 0/1分别是目标`0x0600F810`的24×12记录和目标
  `0x0600FC4E`的23×3记录，均为status 3且精确出现一次；最终两项均转为status 2。
  按64-byte行距抽出的576/138 bytes分别与ROM解压payload逐字节一致，consumer前
  均不相等，变化字节数为473/134。新独立verifier自行实现LZ77，固定v1父成果、
  ABI/ownership、bridge与zero-input audit/done、guard、快照、queue及VRAM，并拒绝
  重签篡改。两次正式mGBA运行均经统一heavy lock，`completed/0`、非degraded，峰值
  RSS为111.28515625/107.046875 MiB。成果位于
  `artifacts/residual-wram-tilemap-runtime-v2/`，说明见
  `notes/residual-wram-tilemap-runtime-reachability-20260731.md`。本子分母已闭合，但
  修改ROM后的最终像素A/B、完整演出时序和排他writer因果仍未闭合，Goal保持active。
- 2026-07-31：四条派生WRAM tilemap中的CPU裁切源`0x083F2108`完成自然运行时
  闭环，子分母由0/4推进为**1/4**。复用已验收scene-panel setup快照零输入5帧，
  frame 3固定命中`0x0808BC2E`的`0x083F2108→0x02002880`加载，并紧接命中
  `0x0808B79C`，LR=`0x0808BC3B`。consumer入口的800-byte WRAM与ROM解压源逐字节
  一致，同刻`0x06001100`的640 bytes尚不等于源；最终精确等于该WRAM逐行保留前
  32项、丢弃右侧8项后的结果，640/640 bytes变化。独立verifier自行解压ROM、重建
  裁切、固定父runtime v2/ABI/ownership、audit/done/guard、WRAM及load/consumer
  寄存器，并拒绝重签篡改。正式mGBA运行经统一heavy lock，`completed/0`、非
  degraded，峰值RSS 106.78515625 MiB。成果位于
  `artifacts/residual-wram-crop-tilemap-runtime-v1/`，说明见
  `notes/residual-wram-derived-tilemap-relocation-20260731.md`。其余三条12×12坐标
  变换queue源、修改ROM像素A/B和排他writer因果仍未闭合，Goal保持active。
- 2026-08-01：派生WRAM tilemap中剩余三条12×12坐标变换源已在受控入口下完成
  运行时闭环，子分母由1/4推进为**4/4**（其中CPU裁切源1条为自然入口，变换源3条
  为受控入口）。三条source分别在`0x08090B5C/0x08090D56/0x08090DC4`加载，
  load完成后的`0x0200A640` staging均与各自ROM LZ77解压结果逐字节一致；变换后
  都以`0x0200A760 → 0x06000806`、12×12提交。独立事务固定严格cycle顺序，解析
  完整16槽queue得到slot 0/2/0的status `3→2`，并从96 KiB VRAM dump按64-byte
  行距重建目标区域：flush前与输出不同，flush后288 bytes逐字节一致，变化字节数
  为18/17/9。phase B还强制首条post早于第二条load，排除共享submit串证。
  正式mGBA运行经统一heavy lock，`completed/0`、非degraded，峰值RSS为
  116.7890625/116.734375 MiB。独立verifier不导入exporter，自行检查ROM解压、
  queue、`.ss9`内存、strided VRAM、ABI/ownership、父快照链及所有SHA；并从每条
  load-post快照的旧输出独立重建唯一3×3裁剪与`+0x02BC`更新，拒绝重签cycle、来源、
  变换输出、状态和VRAM篡改。成果位于`artifacts/residual-wram-transformed-tilemap-runtime-v1/`，
  说明见`notes/residual-wram-transformed-tilemap-runtime-20260801.md`。入口链含
  `0x020240BC: 0→1`补丁，故只签发controlled结论；自然入口、修改ROM像素A/B、
  完整演出时序与排他writer因果仍未闭合，Goal保持active。
- 2026-08-01：派生WRAM tilemap新增修改ROM最终像素A/B。生产迁移器把
  `0x084635D8`的`(8,8)`从`0xD80C`改为`0xD80B`，基线/候选均重定向到
  `0x08BC15AC`且解压源只差byte 208。复用同一accepted choice-state3快照和同一
  输入后，两边在frame 150/cycle `1198116187`命中相同load；staging的
  `0x0C→0x0B`经`+0x02BC`变换为`0xDAC8→0xDAC7`，queue flush后只改变VRAM
  `0x06000A16`对应entry。从各自queue-post快照零输入续跑一帧，mGBA截图恰好差
  **50像素**，坐标边界`[88,64,95,71]`且集合与独立ROM tile oracle完全一致。
  独立verifier从基准ROM与八项patch ledger重建两份16 MiB ROM，并重做LZ77、
  load/load-post寄存器与staging、BG1配置/scroll、charbase tile、PRAM、VRAM行及
  PNG检查；四对完整96 KiB VRAM证明load/load-post零差异、queue-post/下一帧
  仅offset `0x0A16`不同，重签patch ledger、staging、BG1 scroll或区外VRAM篡改
  均被拒绝。正式序列峰值
  RSS为122.8203125/123.79296875 MiB。成果位于
  `artifacts/residual-wram-tilemap-pixel-ab-v1/`，说明见
  `notes/residual-wram-tilemap-pixel-ab-20260801.md`。这解除该代表性派生源的
  “修改ROM最终像素A/B”缺口，但入口仍为controlled；完整时序、排他writer、其余
  WRAM tilemap逐项像素A/B及实体GBA输出仍未签发，Goal保持active。
- 2026-08-01：47张战斗地图的生产迁移能力新增首条自然loader到最终像素A/B。
  map 39–45共享同一primary layout；构建器只拆分map 41的header pointer
  `0x53DE3C`，另外六个alias保持原指针，并把coarse cell `(1,6)`从
  `0x00350022`交换为`0x00220035`。baseline/candidate均从loader前、map runtime
  全零的accepted `scenario-41-start-row.ss9`独立输入同一个A；frame 80都到达
  battle 41 / map 36×44。各自792-byte EWRAM layout精确等于`0x08980000`的迁移
  LZ77内容，完整EWRAM只差目标word的两个byte，完整VRAM只差由两个metatile展开的
  八个BG0 entry低byte，IO/PRAM/OAM完全相同。实际BG0 scroll `(24,104)`令目标
  cell的下半部位于屏幕`[8,0,39,7]`；独立ROM tile/palette oracle与两边可见
  32×8像素逐项相等，mGBA最终截图恰好只差该区域204像素。两次守卫运行峰值RSS为
  56.0546875/56.14453125 MiB，无进程或监听残留。独立verifier从基准ROM和两项
  patch ledger重建两份16 MiB ROM，并拒绝重签后的layout、alias和input audit
  篡改。成果位于`artifacts/map41-primary-layout-pixel-ab-v1/`，说明见
  `notes/map41-primary-layout-pixel-ab-20260801.md`。该代表性链已闭合；其他地图/
  资源类型、完整camera/overlay/碰撞玩法和实体GBA仍未全量签发，Goal保持active。
- 2026-08-01：同一map 41自然入口又批量闭合tile graphics、BG palette和metatile
  definitions三类修改ROM最终像素A/B。四份ROM共享三项allocation和三项map41
  header redirect的完全相同拓扑，均从同一preloader零状态快照独立输入A后到达
  battle 41。tiles候选只令VRAM `0x06006A20:34→35`并改变`(160,32)`一个像素；
  palette候选只令PRAM `0x0500004A:0D→0C`并改变119像素；metatile候选只令
  EWRAM `0x0201E05C:19→1A`和VRAM `0x06000418:19→1A`，改变56像素。三边
  IO/OAM及非目标完整内存域均相同，外部PNG与各自ss9内嵌画面逐RGB一致。独立
  verifier从基准ROM和六项ledger重建四份16 MiB ROM，重扫全部alias、验证三类
  payload、primary layout、五个完整内存域及从BG0状态重建的精确坐标/前后RGB；
  它将frame 80时共同被后续writer覆盖的1,080个graphics byte明确建账，不冒充
  整份12 KiB loader exact。四次guard均`completed/0`、非degraded，峰值RSS为
  55.9609375–56.0625 MiB。成果位于
  `artifacts/map41-visual-resource-matrix-v1/`，说明见
  `notes/map41-visual-resource-matrix-20260801.md`。map41四个主要视觉资源类型已有
  代表性自然像素链；其他地图、alternate layout、碰撞、camera/overlay和实体GBA
  仍未全量签发，Goal保持active。
- 2026-08-01：角色战斗视觉资源新增首条修改ROM自然最终像素A/B。生产bundle迁移器
  把resource 0（鸣人visual slot 0）的palette、18 KiB graphics、component、frame、
  timeline和animation table整体迁移到`0x08600000..0x08604B60`，两份16 MiB ROM
  拓扑相同且只在graphics `+0xD26`有`0x12→0x42`单字节差异。两边从同一accepted
  preloader快照独立输入A后到达battle 41；完整EWRAM/IO/PRAM/OAM相同，完整VRAM
  只差`0x06010126`。独立verifier从`DISPCNT=0x1940`、OAM entry 0、1D OBJ mapping、
  BG priority/透明度和OBJ palette重算局部`(13,17)`到屏幕`(117,25)`，最终PNG恰好
  只在该点由`(33,33,33)`变为`(255,0,0)`。它固定五个内存域及原始run身份，并拒绝
  重签后的bundle、savestate display、audit/guard、build和scope篡改。两次guard均
  `completed/0`、非degraded，峰值RSS为109.78125/109.01171875 MiB。成果位于
  `artifacts/character-battle-graphics-pixel-ab-v1/`，说明见
  `notes/character-battle-graphics-pixel-ab-20260801.md`。本证据只签发resource 0 /
  frame 3代表链，不外推至其余249个资源、342个逻辑槽、完整动作合成或实体GBA，
  Goal保持active。
- 2026-08-01：同一resource 0自然入口又批量闭合palette、component geometry和
  animation timeline三类修改ROM最终像素A/B。四份16 MiB ROM共享相同bundle与
  descriptor topology，只分别在`0x600002:84→85`、`0x60486C:F0→F1`、
  `0x604A64:03→04`有单byte差异。palette边完整内存只差PRAM
  `0x05000202`，268个最终像素统一由`(33,33,33)→(41,33,33)`；component边只差
  OAM entry 0 attr1 `0xC068→0xC069`，634个像素体现角色相对背景右移一像素；
  timeline边的task仍为animation 1/keyframe 0，但源帧3变为4，动态OBJ的1 KiB分别
  逐字节等于ROM tiles `96..127`和`128..159`，完整内存只在VRAM差394 bytes，最终
  改变616像素。独立verifier从基准ROM和四份bundle重建完整ROM，并固定task、五个
  内存域、OAM、最终像素、父快照、mGBA build/binary、audit和两层guard；重签后的
  bundle、PRAM/OAM/VRAM/task、截图、证据、父链、build/scope/verifier篡改均被负测
  拒绝。成果位于`artifacts/character-battle-visual-resource-matrix-v1/`，说明见
  `notes/character-battle-visual-resource-matrix-20260801.md`。当前只签发resource 0
  的三个代表字段，不外推至其余249个资源、完整动画推进、动作合成或实体GBA，Goal
  保持active。
- 2026-08-01：菜单／剧情立绘新增首条production relocation自然最终像素A/B。
  resource 0有36个逻辑别名，本轮只拆分row 1 / variant 0的pair `0x5A4E14`；两边
  graphics/palette共同迁移到`0x08A80000/0x08A80CEC`，candidate只把80×80画布
  `(40,40)`的index `52→14`，解压OBJ stream仅byte 5184不同。两份ROM从自然
  `scenario-41-postbattle-dialogue-9.ss9`独立输入一次A；其下一条脚本命令是
  `0x08031F6E: ShowPortrait(0,1,0)`，输入前目标graphics不在动态OBJ VRAM。
  frame 80的IO/PRAM/OAM完全相同，EWRAM只差`0x02003CC0`，VRAM只差
  `0x06011440`，两边完整6400-byte OBJ流和128-byte palette分别等于各自ROM资源；
  最终PNG只有屏幕`(56,48)`一个像素由`(239,189,165)→(99,74,57)`，Mode-0
  compositor也与两张mGBA PNG逐RGB exact。独立verifier自行重建六组件stream、
  BGR555、LZ77、两份16 MiB ROM、自然脚本边界、内存域、OAM、像素及运行来源，
  并拒绝重签后的语义与raw state篡改。两次guard均`completed/0`、非degraded，峰值
  RSS为55.96484375/56.1328125 MiB。成果位于
  `artifacts/menu-portrait-pixel-ab-v1/`，说明见
  `notes/menu-portrait-pixel-ab-20260801.md`。该链只签发row 1 / variant 0代表样本，
  不外推至其余310个逻辑立绘、全部转场或实体GBA，Goal保持active。
- 2026-08-01：世界地图page 0新增首条production relocation自然最终像素A/B。
  两份ROM均把graphics重定位到`0x08B71000`并只重写page 0 pointer；candidate只把
  32 KiB源的byte 15588、tile 243 local `(4,4)`、画布`(116,76)`从index
  `112→137`。两边从script cursor `0x08031FE7`、page 0资源尚未装入的自然对白
  checkpoint独立输入一次A；frame 80的EWRAM/IWRAM/IO/PRAM/OAM零差异，VRAM只在
  `0x06007CE4`有该byte差异，最终PNG也只在`(116,76)`由
  `(189,165,107)→(66,33,0)`。安全编码后捕获帧完整32 KiB graphics与各自loader
  源逐字节一致；旧证据的806-byte差异已在后续回归中确认为编码损坏。首轮tile 1
  候选实际扩散为13个VRAM byte/155个像素，已作为过程式模板
  假设拒绝。独立verifier重建LZ77、两份16 MiB ROM、page 1/2 descriptor、六个
  内存域、tilemap/palette、renderer、audit/guard及文件全集，并拒绝重签语义和raw
  state篡改。成果位于`artifacts/world-map-page0-pixel-ab-v1/`，说明见
  `notes/world-map-page0-pixel-ab-20260801.md`。page 1/2、切换/解锁、标签、光标和
  实体GBA仍未签发，Goal保持active。
- 2026-08-01：修复共享 GBA LZ77 编码器与 `LZ77UnCompVram` 不兼容的问题。旧编码
  允许distance 1重叠复制，字节级离线解压虽正确，但BIOS半字提交VRAM会读到尚未
  提交的低字节。TDD加入独立VRAM半字解码器和所有独立编码器的distance-1禁用测试；
  13份图像重定位成果及其依赖证据全部按安全编码重签并独立验证。固定槽位微改动的
  真实容量修正为菜单立绘37/74、地图70/166、战斗特效23/34、regular BG 10/31；
  其余编辑继续由已完成的可变长重定位链承载。菜单立绘和世界地图page 0均重新运行
  mGBA，后者旧有806-byte VRAM“共同覆盖”被证实为编码损坏，修复后完整32 KiB与源
  一致。新增Cutscene OBJ ID 1自然胜利加载最终像素A/B：完整VRAM只差
  `0x06016052`，最终只差屏幕`(60,52)`一个像素。三组正式运行峰值均约56 MiB，
  无mGBA崩溃、进程或监听残留。成果见
  `notes/vram-safe-lz77-runtime-20260801.md` 与
  `artifacts/cutscene-obj-id1-pixel-ab-v1/`；其他Cutscene ID/动画与其余资源的逐项
  自然像素链仍未全量闭合，Goal保持active。
- 2026-08-01：战斗特效新增首条production relocation自然最终像素A/B。scenario 41
  攻击确认页只输入一次A，自然action 5→sequence 6→group 5；两份16 MiB ROM都只把
  group 5 graphics迁移到`0x08B40000`，allocation、pointer redirect及1,165-byte
  安全LZ77大小完全相同。frame 150完整3,840-byte graphics与各自ROM解压内容逐字节
  相等，位于OBJ tile base 288；palette bank 5和OAM entry 1保持相同。candidate只将
  解压offset `0x200:02→04`，六个完整内存域仅VRAM `0x06012600`一字节不同，最终
  mGBA PNG也只在`(160,48)`由`(255,222,198)→(189,123,115)`。独立Mode-0
  compositor对两边逐RGB exact，verifier拒绝raw state和重签语义篡改。两次guard均
  `completed/0`、非degraded，峰值RSS为56.23828125/56.109375 MiB且无进程/listener
  残留。成果位于`artifacts/battle-effect-group5-pixel-ab-v1/`，说明见
  `notes/battle-effect-group5-pixel-ab-20260801.md`。当前只签发18组中的group 5和
  frame 1代表链，不外推其他组/帧、完整affine/blend/时序/音频或实体GBA；Goal保持
  active。
- 2026-08-01：战斗特效自然最终像素A/B由1组推进到**2/18组**。scenario 50中鸣人
  自然选择忍具1“十字手里剑”，对应encoded action 129→sequence 13→group 11；原
  十段导航已由通用多输入runner合并成一次guarded运行，并固化为最终确认A之前的
  `scenario-50-cross-shuriken-confirmation.ss9`；其审计与历史逐段运行记录了相同
  PNG SHA，但仓库不把两份外部PNG字节一致性作为独立可复算结论。两份
  16 MiB ROM共享`0x08B40000` relocation及488-byte安全LZ77拓扑，candidate只把
  graphics offset `0x16:21→22`。最终六个完整内存域仅VRAM
  `0x06012C16`一字节不同，mGBA PNG仅`(172,61)`由白色变为肤色；完整graphics、
  palette bank 6、OAM entry 0和独立Mode-0输出均精确匹配。两次A/B运行峰值RSS为
  56.09765625/55.85546875 MiB且无残留。成果位于
  `artifacts/battle-effect-group11-pixel-ab-v1/`，说明见
  `notes/battle-effect-group11-pixel-ab-20260801.md`。其余16组、其他帧、完整
  affine/blend/时序/音频及实体GBA仍未全量签发，Goal保持active。
- 2026-08-01：战斗特效自然最终像素A/B由2组推进到**3/18组**。scenario 47中佐助
  自然选择主动动作16“火遁·豪火球术”，对应encoded action 16→sequence 16→
  group 14；从已跟踪turn-5快照到最终确认页的9段正确输入链及零输入稳定性已固化为
  可恢复checkpoint，错误方向试探未进入成果。两份16 MiB ROM共享`0x08B40000`
  relocation及2,138-byte安全LZ77拓扑，candidate只把graphics offset
  `0x3A:33→23`。确认后frame 516的完整5,120-byte graphics与各自ROM源逐字节一致，
  OAM entry 1为`0x0030/0x80A0/0x5920`、OBJ tile base 288、palette bank 5；六个
  完整内存域仅VRAM `0x0601243A`一字节不同，mGBA PNG也仅屏幕`(173,54)`由
  `(255,165,49)→(255,239,107)`。两次正式guard峰值RSS为55.95703125/
  56.078125 MiB，非degraded且无PGID/listener残留。独立verifier从基准ROM重建
  两份ROM并返回`errors=[]`；成果位于`artifacts/battle-effect-group14-pixel-ab-v1/`，
  说明见`notes/battle-effect-group14-pixel-ab-20260801.md`。其余15组、其他帧、
  完整affine/blend/时序/音频及实体GBA仍未全量签发，Goal保持active。
- 2026-08-01：战斗特效自然最终像素A/B由3组推进到**4/18组**。复用scenario 41
  攻击确认checkpoint，只输入一次A；同一自然action 5路径中观察到直接selector
  sequence 6/group 5以及sequence 1/group 1的三个弹道尘土子任务。通用profile新增
  trigger sequence/group与资源sequence/group分离，避免把间接表现误写成直接绑定。
  两份16 MiB ROM共享`0x08B40000` relocation及735-byte安全LZ77拓扑，candidate
  只改解压offset `262:40→10`。frame 90完整1,024-byte graphics位于
  `0x06012000`，三个OAM均为frame 2；六个内存域仅VRAM `0x06012106`一字节不同，
  最终PNG在两个未遮挡实例`(44,73)/(37,77)`由`(148,140,90)`变为
  `(222,214,148)`；第三实例未进入最终像素差异，证据不推断具体原因。三个实例的
  OAM索引、attr0/1/2、frame、component与候选坐标均由profile及独立verifier约束。
  verifier另从`0x06012000`推出OBJ load tile基址256，再与component源tile 8相加，
  要求三个attr2低10位均为264，避免frame/component只停留在自述字段。
  checkpoint的`0x06016000`保留旧
  基线缓存，证据明确记录它并另证候选在输入前缺席、目标区重新装入各自ROM内容。
  两次guard峰值RSS为55.87109375/56.1484375 MiB且无PGID/listener残留；独立
  verifier返回`errors=[]`。group 1/11/14 manifest现分别记录历史生成实现哈希和
  当前复核实现哈希，不再覆盖raw证据的生成来源。成果位于
  `artifacts/battle-effect-group1-pixel-ab-v1/`，
  说明见`notes/battle-effect-group1-pixel-ab-20260801.md`。其余14组、其他帧、完整
  弹道RNG/affine/blend/时序/音频及实体GBA仍未全量签发，Goal保持active。
- 2026-08-01：现有持久状态的战斗特效身份已从逐组证据升级为全量离线目录。accepted
  `runtime-screen-composites-v1`仍诚实保留91个父checkpoint；Git后续新增的两份
  确认页作为`post-parent extensions`单列，当前93/93个tracked `.ss9`全部解析，
  1,254个active OAM中有3个在同一自然快照唯一绑定group 1 / frame 6 /
  component 0、OBJ load tile 768和完全一致的16色palette。四份accepted natural
  pixel A/B baseline与一份group 2 affine golden另列为5个supplemental state，9个
  OAM独立覆盖groups `[1,2,5,11,14]`，因此已有持久运行时资源身份覆盖为5/18
  （27.78%），但production自然像素A/B仍保持4/18（22.22%）。匹配必须先以
  `attr2 tile-component tile`推导load base，再要求完整group graphics逐字节一致，
  共享graphics及重复frame保持显式歧义。独立verifier不导入导出器，使用既有GPU
  decoder重建93+5状态和12条匹配，并拒绝frame身份篡改；10项定向测试最大RSS约
  25.5 MiB、swap 0，未启动mGBA。成果位于
  `artifacts/battle-effect-runtime-oam-bindings-v1/`，说明见
  `notes/battle-effect-runtime-oam-bindings-20260801.md`。task/selector排他writer、
  全帧/跨帧时序、RNG、blend/window/audio与实体GBA仍未闭合，Goal保持active。
- 2026-08-02：战斗特效生产修改 ROM 的自然最终像素 A/B 由4组推进到**5/18组**。
  battle 8 的原始 AI 自然选择 action 64，经 side 1、sequence 17 绑定group 15；
  从父artifact归档中成果化确认前checkpoint，只输入`A:60:68`并在frame 1549捕获。
  两份16 MiB ROM保持1,560-byte相同LZ77拓扑，candidate只改解压offset
  `0xA3:23→24`；六个完整内存域仅VRAM`0x060124A3`一字节不同。OAM entry 1
  `0x0030/0x9030/0x5920`的水平翻转把源像素`(14,8)`映射到屏幕`(65,56)`，最终
  PNG也仅该像素由`(82,140,255)→(0,82,255)`。独立verifier完整复验父自然artifact、
  checkpoint tar成员、当前桌面mGBA profile、ROM重建、OAM/VRAM/PRAM与Mode-0输出；
  两次guard峰值RSS为69.54296875/69.5390625 MiB且无PGID/listener残留。历史单输入
  runner保持原SHA，新runner独立承载当前工具链；group 1/11/14只重签当前验证实现
  哈希，raw与运行结论不变。成果位于`artifacts/battle-effect-group15-pixel-ab-v1/`，
  说明见`notes/battle-effect-group15-pixel-ab-20260802.md`。其余13组、group 15其他
  8帧、完整blend/window/音频及实体GBA仍未签发，Goal保持active。
- 2026-08-01：上述内容身份又与同一批快照的全局sprite task pool完成严格关联。
  战斗特效不能沿用角色的三指针资源身份：真实task `+0x24`可为零或动态tile/action
  地址，与静态group graphics不同；18组实际由唯一的`(+0x1C definition,+0x20
  animation)`指针对识别。批处理重建93+5个状态的128×`0x3C` task pool、active
  dispatcher、`0x03000054`运行时偏移、shadow/hardware OAM与提交相位；98/98个
  dispatcher逐项一致，12个活动特效task覆盖groups `[1,2,5,11,14]`。tracked
  scenario 50中的slots 113/114/115均选择group 1/frame 6；anchor、component
  `(-8,-8)`和Y offset 24精确重建OAM 17/18/19的完整attr0/1/2，三条均同时命中
  shadow与hardware。dispatch ordinals `12/13/14`与OAM indices `17/18/19`不同，
  因而未把调度顺序冒充writer index。82个状态全OAM缓冲一致，其余16个差异全部位于
  代码证明的pending wait窗口，未解释差异0。五份supplemental只保留frame-phase
  观察，不污染tracked自然分母。独立verifier重建全部字段并拒绝runtime-offset和
  group身份、parent promotion与source provenance篡改；13项测试最大RSS约30 MiB、
  swap 0，未启动mGBA。成果位于
  `artifacts/battle-effect-runtime-oam-task-bindings-v1/`，说明见
  `notes/battle-effect-runtime-oam-task-bindings-20260801.md`。affine、多component
  dynamic-copy、精确writer/allocator index、跨帧时序、未观察13组及实体GBA仍未闭合，
  Goal保持active。
- 2026-08-01：战斗特效 task/OAM 证据新增首条精确跨帧提交事务。直接复用已验收的
  group 11 active-task `frame106.ss9`，不重做十段导航且零输入运行；同一 slot 124
  task 在 renderer tail `0x08063328`、主循环 submit post `0x08061126` 与 ack post
  `0x080612AA` 依次命中；三份存档按mGBA Thumb breakpoint的`saved r15-2`
  独立恢复出相同地址，cycle严格递增，pending为`0→1→0`。renderer生成的
  shadow OAM 与旧 hardware OAM 不同，submit 后 hardware 仍未改变，ack 后完整
  1 KiB hardware OAM精确等于该shadow；task pool、group 11指针对、active
  dispatcher中slot 124唯一成员关系及九类稳定内存又由三份`.ss9`独立复算。同一
  dispatcher还有slots 125/127，故完整OAM变化不排他归因给slot 124。该结果纠正了
  把VBlank return `0x08061324`作为唯一
  renderer 后边界的旧假设。独立 verifier 不导入生产器，并将 byte-wise live MMIO
  `io.bin` 明确限制为哈希锁定但不与存档 I/O image 等同。正式 artifact 约716 KiB；
  guarded run 非degraded、success-marker完成且无PGID/listener残留，未重复启动模拟器。
  成果位于`artifacts/battle-effect-frame-phase-v1/`，说明见
  `notes/battle-effect-frame-phase-20260801.md`。该里程碑只签发group 11一个代表task
  的一次事务，不改变production自然像素A/B `4/18`分母；其余group、affine、
  multi-component、dynamic-copy、通用writer index与实体GBA仍未闭合，Goal保持active。
- 2026-08-01：战斗特效精确跨帧提交相位由单一group 11推进到当前全部已观察groups
  `[1,2,5,11,14]`，子分母`1/5→5/5`，全18组覆盖为`5/18`（27.78%）。新增批处理
  runner会先一次性验证四份profile/state/ROM hash，再串行调用单组guarded runner；
  group 1/2/5/14均零输入从既有accepted快照恢复，不重复长导航。五组都从`.ss9`
  独立恢复Thumb breakpoint地址，cycle严格递增、pending=`0→1→0`，renderer生成的
  shadow在submit时尚未进入hardware，ack后完整1 KiB精确相等；目标task在active
  dispatcher中唯一出现，ordinals分别为`12/0/2/0/2`。group 2首次覆盖affine事务，
  但仍是supplemental。四次新运行均`completed/0`、非degraded且无PGID/listener
  残留；group 5 baseline又经heavy guard确定性重建，峰值RSS 82.24609375 MiB。
  独立聚合verifier从18-group catalog、5-group task binding来源、batch spec和五份
  单组artifact重算，返回`phase_verified_groups=5/all_groups=18/errors=[]`，并单独锁定
  production修改ROM最终像素A/B仍为`4/18`，没有把phase覆盖冒充pixel覆盖。成果位于
  `artifacts/battle-effect-observed-frame-phases-v1/`及四个新增单组phase artifact，
  说明见`notes/battle-effect-observed-frame-phases-20260801.md`。未观察13组、全帧、
  排他task→OAM writer、dynamic-copy、blend/window、音频和实体GBA仍未闭合，Goal
  保持active。
  独立审查随后补齐来源链：运行profile保持原audit哈希不变，独立provenance catalog
  将其source evidence绑定到accepted父manifest/载荷，并验证state、ROM、group；聚合
  分母会实际运行task-binding独立verifier，并精确哈希锁定两个被导入verifier、
  savestate parser及对应测试；单组verifier重新校验audit/manifest/当前profile三方
  SHA一致。batch还拒绝绝对路径、`..`及符号链接逃逸。
- 2026-08-01：此前未观察的13组战斗特效已完成一次零输入受控入口批处理，但证据按
  目标task严格分为10个正事务与3个负结果。所有case都从同一accepted battle checkpoint
  恢复，scratch `0→1`，并捕获`binder-return→renderer→submit→ack`；只有groups
  `[4,6,7,8,9,10,12,13,16,17]`在后三相出现唯一稳定的definition/animation task，
  task派生OBJ VRAM graphics和OBJ palette又与静态resource pair逐字节一致。
  groups `[3,15,18]`四相均无目标task，也没有完整目标graphics/palette，因此保持负例，
  不把碎片字节命中冒充成功。正式artifact仍只有三个文件，其中约13 MiB的确定性
  `raw-batch.tar`完整归档729个来源成员（batch/profile/audit/guard/完成标记及四相全部
  审计输出）；独立verifier逐项重建PC、scratch、dispatcher顺序、task、资源和OAM提交，
  并将10个正例的25个可见component精确绑定到shadow/hardware OAM index。group 9保留
  post-frame-advance边界，group 10屏外component不伪造绑定；固定父SHA与完整依赖清单
  阻止替换catalog后自行重签。verifier拒绝正负、自然指标、member、guard/RSS、task、
  dispatcher和OAM绑定篡改。受控技术事务为`10/13`，与既有已观察组（含supplemental）取并集为
  `15/18`，但production自然像素A/B仍为`4/18`、既有observed phase仍为`5/18`、tracked
  checkpoint仍为93；group18/sequence18未覆盖。4个短run的RSS约0.17 MiB属于欠采样，
  不生成批次峰值/均值声明。成果位于`artifacts/battle-effect-controlled-runtime-v1/`，
  说明见`notes/battle-effect-controlled-runtime-20260801.md`。下一步为group3/18复现
  selector+object-spawn入口，并为group15补齐action/side上下文；Goal保持active。
- 2026-08-01：group 15 / sequence 17 的旧负例已拆成资源分配器与 side 两个相邻变量。
  父artifact经其独立verifier复核，且新verifier独立重建旧probe并从父归档四相
  `.ss9`复算：原no-reset/side-0 case的selector均为`0xFF`；复用自然sequence-18调用点的
  `0x0807FDCC(0x300,0x37F,12,14)`后，side 0/1 selector均为有效handle 0。在相同
  reset下，side 0仍无目标task，side 1则于renderer/submit/ack稳定产生slot 108，
  definition/animation为`0x0834711C/0x08347168`，3,584-byte graphics和32-byte
  palette逐字节吻合。两份probe ROM仅`0x0809E852`一个字节不同，因而可把task出现
  归因到side。该task anchor `(-98,62)`且唯一frame-0 component完全位于屏外，所以
  只升级受控selector/resource/task覆盖，不签发可见OAM、自然action 64/65入口或像素
  A/B。113个来源成员已归档到
  `artifacts/battle-effect-group15-allocator-side-runtime-v1/`。独立verifier还固定
  group15 graphics/palette、mGBA binary、toolchain profile/source commit、capture
  script及完整guard/runner依赖链，并通过资源替换后重签、runtime binary重签和父
  对照膨胀负测，返回`errors=[]`；说明见
  `notes/battle-effect-group15-allocator-side-runtime-20260801.md`。
  下一步从桃地再不斩自然action 64/65捕获`0x0807F0FC→0x0807F10C`；Goal保持active。
- 2026-08-02：原受控负例 group 3/18 已通过直接 selector→spawn 入口闭合为四个正
  事务。group 3旧探针误用`0x300..0x37F`的128-tile窗口，而其graphics为304 tiles，
  selector稳定返回`0xFF`；改用同子系统可复现的`0x100..0x39F / palette 4..14`
  受控容量窗口后，side 0/1均返回handle 0并形成slot 109。group 18的sequences 7/18
  则保留自然入口使用的`0x300..0x37F / 12..14`，两案均形成同一资源task。四案均闭合
  renderer→submit→ack、完整graphics及OAM提交；group 18 palette为32/32，group 3
  palette在观察边界为30/32且尾字覆盖被明确保留。至此18组均至少有一条自然或受控
  资源/task身份，技术子分母为`18/18`，但production自然最终像素A/B仍为`4/18`，不
  冒充完整玩法或图像完成。成果位于
  `artifacts/battle-effect-direct-spawn-runtime-v1/`，说明见
  `notes/battle-effect-direct-spawn-runtime-20260802.md`；group 3自然allocator上游、
  非镜像分支、palette尾字生命周期、自然入口、完整动画/像素及实体GBA仍未完成，
  Goal保持active。
- 2026-08-02：group 15 已从 allocator/side 受控对照推进到自然 action 64 运行时
  闭环。primary scenario 39 诊断 route 只把 `SetBattle(40,2)` 的 battle ID 字节改为
  8；复用已验证的结束回合确认快照，只输入一次 A 后，原 battle 8 AI 自然选择桃地
  再不斩 action 64。observer 唯一命中
  `0x0807A222→0x0807F064→0x0807F09E→0x0807F0FC→0x0807F10C→0x0807C5E8`，
  分类值为0，binder两端均为side 1/sequence 17；三份相位存档在派生地址
  `0x02027428`均读出action `0x40`。随后slot 124以definition/animation
  `0x0834711C/0x08347168`稳定存在于6个active task的ordinal 3；全局
  renderer/submit/ack pending=`0→1→0`且ack后完整shadow/hardware OAM相等，但不作
  排他task→OAM归因。48个原始成员压入单一确定性tar，独立verifier从基准ROM、
  observer、完成标记、最终state/PNG、`.ss9`、task pool和OAM重算后返回`errors=[]`；
  branch的route/state/script/guard/run ID绑定、完整guard传递依赖和tar读取前大小上限
  均已闭合。两次guard峰值RSS约66 MiB且都无PGID/listener残留。成果位于
  `artifacts/battle-effect-group15-natural-runtime-v1/`，说明见
  `notes/battle-effect-group15-natural-runtime-20260802.md`。这不签发action 65、
  原剧情可达性或修改后最终像素A/B；后续已复用同一确认页快照闭合group 15
  relocation单像素对照，当前production自然像素分母为`5/18`，Goal保持active。
- 2026-08-02：group 18 / sequence 7 已从受控直接入口的资源/task/OAM身份推进到
  production relocation最终单像素写回。baseline/candidate使用完全相同的直接
  selector→spawn探针、分配窗口和2,002-byte LZ77拓扑，candidate只把解压graphics
  offset `0xCA`由`0x44`改为`0x41`。六个完整内存域中仅VRAM
  `0x060160CA`一字节不同；OAM entry 17 `0x0021/0x8068/0xCB00`把源像素
  `(20,10)`映射到屏幕`(124,43)`；从两份mGBA ack存档离线重建的Mode-0图仅将该像素
  从`(181,181,181)`改为`(231,231,231)`。原始mGBA capture PNG两变体逐字节相同，
  明确不作为像素A/B证据。独立verifier重新运行父direct-spawn verifier、独立编码并
  重建两份16 MiB ROM，从六份三相存档复算PC/cycle、pending `0→1→0`、稳定task、
  资源与shadow/hardware OAM提交，再复核tar全集、六内存域与离线Mode-0像素，返回
  `verified=true, errors=[]`。成果位于
  `artifacts/battle-effect-group18-controlled-pixel-ab-v1/`，说明见
  `notes/battle-effect-group18-controlled-pixel-ab-20260802.md`。该路线明确为受控入口，
  所以production自然最终像素A/B保持`5/18`，技术资源/task身份保持`18/18`；candidate
  guard的0.171875 MiB样本因采样不足不参与统计。下一步优先闭合group 3自然allocator
  上游与exclusive pointer relocation；完整动画、音频、实体GBA仍未签发，Goal保持active。
- 2026-08-02：group 3 / sequence 3 / side 0 已从受控资源/task身份推进到production
  relocation最终单像素写回。group 2/3的graphics表项`0x59912C/0x599134`原本共同
  指向`0x08340AF8`；构建器只把group 3的`0x599134`拆分重定向到`0x08B40000`，
  group 2保持原指针。两份ROM共享5,294-byte安全LZ77和完全相同的直接入口探针，
  candidate只改graphics offset`0xCF:03→0E`。六个完整内存域仅VRAM
  `0x060120CF`一字节不同；OAM entry 22`0x0028/0x9078/0x4900`的水平翻转把源像素
  `(22,11)`映射到屏幕`(129,51)`，离线Mode-0只令该像素从`(247,115,0)`变为
  `(115,107,99)`。两份原始mGBA capture PNG逐字节相同，明确不作为像素A/B。
  runtime palette与ROM源仅前30 bytes一致、尾offset 30/31为`0100`对`6C2D`；所选
  索引3/14在匹配范围内，但artifact固定`full_source_palette_equal=false`。独立
  verifier重建共享alias、两份16 MiB ROM、三相task/OAM、六内存域与最终像素，并拒绝
  扩大group 2 redirect或完整palette声明。成果位于
  `artifacts/battle-effect-group03-controlled-pixel-ab-v1/`，说明见
  `notes/battle-effect-group3-controlled-pixel-ab-20260802.md`。该入口仍为受控，故
  production自然像素保持`5/18`、技术身份保持`18/18`；自然allocator上游、非镜像
  分支、palette尾字生命周期、完整动画/音频与实体GBA仍未签发，Goal保持active。
- 2026-08-02：group 3 的自然 allocator 上游已从未知生产者推进为原 ROM 静态端到端
  生产链。忍具67–72的effect code均为`0x18`，经`0x08077514`把encoded action
  `C3..C8`写入type-1战场对象`+4`；阵营结束控制器调用`0x08081B70`，对象到期时对该
  字段加`0x21`生成`E4..E9`，随后经`0x0807AB34→0x0807F414`进入`action > 0xE3`
  路径，执行`0x100..0x39F / palette 4..14` reset，并由六条相同表项分派至原生
  `0x0807F208`。分析器和独立verifier已锁定ROM、模板、代码片段、BL目标和handler表；
  篡改自然完成声明或handler映射会被拒绝。受守卫扫描`artifacts/`与`build/`共1,164份
  存档，全部解析成功但没有活动C3–C8对象或实际装备的忍具67–72；输入fail-closed
  修正后的复跑峰值RSS为20.16015625 MiB。因此没有盲目启动mGBA，production自然最终
  像素仍为`5/18`。成果见
  `notes/battlefield-object-effect-chain-20260802.md`；下一步定位67–72的原版取得/装备
  路径并捕获自然选择、对象到期和原生handler的同次运行时命中，Goal保持active。
- 2026-08-02：上述 savestate 种子扫描已纠正持久库存漏项。扫描器除活动对象和单位
  战斗槽外，现同时检查 `0x02023FD4` 的 `0x71` 字节忍具库存；对应 TDD 先因缺少
  `inventory_special_tools` 失败，最小实现后通过。受守卫重扫原 1,164 份存档全部解析
  成功，得到 248 个路径命中、224 个不同 state SHA。后续自然 UI 取证发现库存前两字节
  是总数/空位，工具 ID 需按偏移减 1，因此这些命中实际全部为忍具67数量1；旧“忍具68”
  结论已取代。活动目标对象
  和已装备目标忍具仍为0。已跟踪的
  `scenario-47-battle-13-postbattle-world-map.ss9` 即含该库存，SHA为
  `e80779dc048fd862d0a8fc1a47f77bcfe1ab06810859f38015c562679958b800`，因此不再需要
  重新调查取得路径。扫描峰值tree RSS 20.28515625 MiB，未启动mGBA。下一步从该快照
  进入装备UI并固化装备后checkpoint，再捕获C3对象、E4到期和原生group3 handler；
  production自然最终像素仍为`5/18`，Goal保持active。
- 2026-08-02：已从上述世界地图快照自然进入装备 UI，展开 18 件库存后向下 13 次选中
  可见“引爆牌”，最终 A 使鸣人持久模板首装备槽 `0x02022FA1` 从工具1变为工具67，库存
  数量保持1。确认后的状态被最新桌面mGBA重新加载并以四次B正常返回世界地图，持久装备
  复核仍为角色1/工具67；六段运行峰值不超过65.578125 MiB，全部success-marker、非
  degraded且无进程/listener残留。新恢复点
  `scenario-47-tool67-equipped-world-map.ss9` SHA为
  `ecea4dc669f4e7d8a72d6c6e28fe456ec335c3c113c8c1426ed5e7eba225e601`。下一步从它推进
  scenario48纯剧情与scenario49演习场，进入battle14验证持久槽复制为战斗槽，再自然提交
  工具67并等待C3对象到期为E4/group3；production自然最终像素仍为`5/18`。
- 2026-08-02：从已验收的忍具67世界地图恢复点，经显式受守卫输入自然推进 scenario 48
  学院剧情、scenario 49 演习场剧情及“开始任务”确认，进入实际 battle ID 14。新
  `scenario-49-battle-14-tool67-entry.ss9` SHA为
  `2c95de937efb785d537c45f39224bb3fdae319e410f6abbc3cbdfcc32fb2812c`；battle control
  为`00 0E 00 00 00 00 00 00`，鸣人持久模板和新建战斗单位的首忍具槽均为67，库存
  数量仍为1，活动延迟对象为0。最终确认运行峰值65.40625 MiB，非degraded且无进程或
  listener残留。该 checkpoint 免除后续重复剧情导航，并首次证明自然建战会复制目标
  忍具到战斗槽；尚未提交行动、创建C3对象或到期为E4，因此production自然像素仍为
  `5/18`，Goal保持active。
- 2026-08-02：从新battle 14入口恢复后，经单位展示/开场对白、取消默认移动、自然选择
  “引爆牌”、目标右移一格及确认“是”，首次生成真实延迟对象。新
  `scenario-49-battle-14-tool67-active-c3.ss9` SHA为
  `401256e00877169e98b3e6584488e732f9254b4426806ad2b6b3bdc770259939`；扫描得到唯一
  slot 3/state 1/action `C3`/remaining turns 2，战斗槽中的工具已消费而持久模板与库存
  保持67/数量1。最终运行峰值65.66015625 MiB，非degraded且无进程/listener残留。
  自然行动提交和C3对象创建已闭合；E4到期、group 3 handler及修改ROM自然最终像素仍未
  闭合，production自然像素保持`5/18`，Goal保持active。
- 2026-08-02：group 3 已从自然 C3 对象创建推进到原生 E4 到期与精确跨帧提交。
  从 `scenario-49-battle-14-tool67-active-c3.ss9` 正常完成三名玩家单位的面向/不防御
  与回合推进，固化唯一 slot 3/state 1/action C3/remaining 0 的
  `scenario-49-battle-14-tool67-expiry-ready.ss9`；随后生产 profile 零输入恢复，
  frame 67/67/68 在 `0x08063328/0x08061126/0x080612AA` 捕获 slot 126 的
  renderer→submit→ack，pending 严格为 `0→1→0`，ack 后完整 shadow/hardware OAM
  相等。新来源 verifier 同时约束自然提交、对象创建、C3/0 savestate、输入时无group 3
  task及独立通过的C3→E4静态链。guard峰值71.33203125 MiB，非degraded且无残留。
  成果位于`artifacts/battle-effect-frame-phase-group3-natural-v1/`，说明见
  `notes/battle-effect-group3-natural-expiry-phase-20260802.md`。精确phase覆盖由5/18
  提升到**6/18**；聚合artifact同时纠正production自然像素为既有**5/18**。本轮仍是
  基准ROM，下一步把exclusive relocation与该自然入口组合，Goal保持active。
- 2026-08-02：Group 3 已把上述自然到期相位与 production exclusive relocation
  组合为同输入最终像素 A/B。baseline/candidate 均从 tool 67 C3/remaining 0 快照
  零输入运行，在 frame `67/67/68` 命中同一 slot 126 renderer/submit/ack；两份
  16 MiB ROM 不含 controlled probe，只重定向 group 3 指针 `0x599134`，保留 group 2
  别名 `0x59912C`。六个运行时内存域仅 OBJ-VRAM `0x060124CF` 一字节不同，独立 Mode 0
  合成仅 `(70,91)` 一个像素从 `[247,115,0]` 变为 `[115,107,99]`，完整 source palette
  与 runtime PRAM 相等。独立 verifier 重新编码 LZ77、重建两份 ROM 哈希并验证三相
  savestate/dump，返回 `errors=[]`；guard 峰值 RSS 75.8515625/68.203125 MiB 且无进程
  残留。成果见 `artifacts/battle-effect-group03-natural-pixel-ab-v1/` 和
  `notes/battle-effect-group3-natural-pixel-ab-20260802.md`。聚合 phase 保持 **6/18**，
  production 自然最终像素由 **5/18 提升到 6/18**；其余 12 组及完整动画/混合/音频/
  实体 GBA 仍未闭合，Goal 保持 active。
- 2026-08-02：Group 12/13 路线审计先排除了旧伪证据：battle 8 的 Lv25 卡卡西实际
  动作数组没有 action 32“雷切”；`0x0807A222` 又位于动作 `strb` 之前，两次所谓
  action 64 观察只是旧值，不能证明本轮选择。观察器改到写入后的 `0x0807A22C` 后，
  diagnostic battle 3 从持久化确认页只输入一次 `A:60:68`，在 frame 179 同时捕获
  source/runtime action 61，并闭合 action 61 → sequence 15 → group 13。生产 A/B
  只改 group 13 解压图形 offset `0x5D:0x32→0x22`；两边从同一快照自然执行，除
  VBlank wait 返回边界 `0x03007F9C` 外，EWRAM/IO/PRAM/OAM 均相同，VRAM 只差
  `0x0601245D`，最终截图只在 `(96,63)` 发生
  `(173,198,214)→(214,231,239)`。独立 verifier 返回 `errors=[]`，两次运行峰值
  RSS 为 `69.58203125/69.5703125 MiB` 且无残留。成果位于
  `artifacts/battle-effect-group13-natural-runtime-v1/` 与
  `artifacts/battle-effect-group13-pixel-ab-v1/`；说明见
  `notes/battle-effect-group13-pixel-ab-20260802.md`。production 自然最终像素由
  **6/18 提升到 7/18（38.89%）**；Group 12、其余 10 组、完整动画/混合/音频及
  实体 GBA 仍未闭合，Goal 保持 active。
- 2026-08-02：Group 2 路线审计排除了另一条旧伪入口。历史
  `tool49-component-trace` 目录名不能证明 tool 49 到 Group 2 的数据流；静态表明确
  tool 49 / encoded `0xB1` 在 `0x0853E647` 选择 sequence 6，而 sequence 2 才绑定
  Group 2，且没有 runtime/action/tool binding，只有11个硬编码 immediate selector
  callsite。新增 current-desktop 严格零输入 runner 后，从 accepted supplemental
  `state-0154.ss9` 受守卫续跑600帧，稳定到面对方向提示：unit slot 1的首忍具由49变0，
  三个Group 2 task全部退出，无法原样重触发。运行峰值RSS `65.46484375 MiB`，guard
  completed/non-degraded且无进程/listener残留；current mGBA正常生成的32 KiB staged
  `.sav`已哈希记录并删除。runner还新增双payload回滚和最终commit marker，43项相关
  回归通过。完整快照与机器审计已按实验生命周期归档，说明见
  `notes/battle-effect-group2-route-stop-20260802.md`。该结果不改变production自然像素
  **7/18**；Group 2后续只能从11个硬编码caller的真实游戏上游重新建立自然链，不能
  复用tool49或supplemental state冒充，Goal保持active。
- 2026-08-02：Group 2 已从上述停止证据推进到 action 7“影分身术”的真实自然入口。
  静态生产者批处理把 handler `0x0807E1C8` / callsite `0x0807E1D0` 直接绑定到
  sequence 2 / Group 2，并明确区分通用动态表中的 action 7→sequence 0。两份
  production ROM 只拆分 primary pair `0x59912C`，保留 Group 3 alias `0x599134`；
  candidate 仅把 frame 2/component 0 图形 offset `688` 从 `0x32` 改为 `0x34`。
  两边从同一确认页快照只输入 `A:5:13`，frame 510 的六内存域只有 OBJ VRAM
  `0x060122B0` 一字节不同，最终截图也只有 `(64,82)` 从
  `(255,255,247)` 变为 `(255,255,197)`。离线 Mode-0 renderer 同时修正重叠
  semitransparent OBJ 应先选顶层 sprite、再与 BG/backdrop 混合的硬件语义；修正后
  baseline/candidate 均与 mGBA PNG 0 像素误差。独立 verifier 返回 `errors=[]`，
  guard 峰值为 `69.6171875/69.55078125 MiB` 且无残留。成果位于
  `artifacts/battle-effect-group2-pixel-ab-v1/`，说明见
  `notes/battle-effect-group2-pixel-ab-20260802.md`。production 自然最终像素由
  **7/18 提升到 8/18（44.44%）**；其余10组、完整动画/混合/音频及实体GBA仍未
  全量签发，Goal保持active。
- 2026-08-02：Group 18 / sequence 7 已从自然创建的忍具67 C3对象推进到type-1
  zero-event expiry与production relocation最终像素A/B。旧`expiry-ready`快照实际已
  含Group 18 task和基准ROM VRAM，恢复它不会重新读取candidate资源指针，故旧A/B被
  判为无因果资格。最终路线改从accepted `object-created`快照（slot 3、`(13,6)`、
  C3、remaining 2、Group 18 task为0）开始，baseline/candidate重放相同17输入，在
  frame `4519/4519/4520`捕获slot 114 renderer→submit→ack，pending为`0→1→0`。
  两份ROM仅重定向Group 18 graphics指针`0x5991AC`，candidate仅改解压offset
  `0xCA:44→41`；六个内存域仅OBJ-VRAM `0x060160CA`一字节不同，离线Mode-0仅
  `(196,68)`从`[181,181,181]`变为`[231,231,231]`。最终签发的两次guard峰值RSS为
  `79.5/80.11328125 MiB`且无残留。独立verifier返回`errors=[]`并拒绝重签输入
  序列篡改。成果位于`artifacts/battle-effect-frame-phase-group18-natural-sequence-v1/`
  与`artifacts/battle-effect-group18-natural-pixel-ab-v1/`，说明见
  `notes/battle-effect-group18-natural-pixel-ab-20260802.md`。production自然最终像素
  由**8/18提升到9/18（50%）**；其余9组、完整动画/混合/音频及实体GBA仍未全量
  签发，Goal保持active。
- 2026-08-02：Group 4 / sequence 4 已从忍具1最终确认页完成自然phase与production
  relocation最终像素A/B。同一`A:5:13`既触发动态sequence 13 / Group 11，也经忍具
  handler硬编码创建Group 4；profile明确分开trigger和resource sequence。Group 4
  slot 127在frame`94/94/95`经过renderer→submit→ack，pending为`0→1→0`；最终截图
  固定在回调晚一帧的frame 96。两份ROM只重定向graphics指针`0x59913C`，candidate
  仅改解压offset`0x99:13→14`；六域只有OBJ-VRAM`0x06012099`一字节不同，最终画面
  也只有`(83,72)`从`[206,148,123]`变为`[189,123,115]`。离线Mode-0与两份mGBA
  PNG均逐像素一致，guard峰值RSS为`70.03515625/70.09375 MiB`且无残留。成果位于
  `artifacts/battle-effect-frame-phase-group4-natural-v1/`与
  `artifacts/battle-effect-group4-pixel-ab-v1/`，说明见
  `notes/battle-effect-group4-natural-pixel-ab-20260802.md`。聚合phase现为**8/18**，
  production自然最终像素由**9/18提升到10/18（55.56%）**；剩余组为
  `{6,7,8,9,10,12,16,17}`，完整动画/混合/音频及实体GBA仍未全量签发，Goal保持
  active。
- 2026-08-02：Group 16 / sequence 19 已从战斗14忍具67“引爆牌”的最终确认页完成
  自然phase与production relocation最终像素A/B。忍具表动态sequence仍为0；编码动作
  `0xC3`经handler `0x0807EE50`在`0x0807EE6A`硬编码选择sequence 19，二者由profile
  与独立验证器明确区分。同一`A:5:13`令Group 16 slot 125在frame`135/135/136`
  经过renderer→submit→ack，pending为`0→1→0`。两份ROM只重定向graphics指针
  `0x59919C`，保留Group 16 palette及Group 17完整指针对；candidate仅把解压offset
  `2340`从`0x10`改为`0x20`，LZ77仍为781 bytes。六域只有OBJ-VRAM
  `0x06015724`一字节不同，最终画面也只有`(169,89)`从`[247,255,222]`变为
  `[181,189,165]`。guard峰值RSS为`69.82421875/70.0234375 MiB`且无残留。成果位于
  `artifacts/battle-effect-frame-phase-group16-natural-v1/`与
  `artifacts/battle-effect-group16-pixel-ab-v1/`，说明见
  `notes/battle-effect-group16-natural-pixel-ab-20260802.md`。聚合phase由**8/18提升到
  9/18（50%）**，production自然最终像素由**10/18提升到11/18（61.11%）**；剩余
  production像素组为`{6,7,8,9,10,12,17}`。完整动画/混合/音频及实体GBA仍未全量
  签发，Goal保持active。
- 2026-08-02：Group 17 / sequence 20 已从原版忍具37自然选择链完成phase与
  production relocation最终像素A/B。忍具表动态sequence为0；编码动作`0xA5`经
  handler `0x0807ED20`在`0x0807ED3A`硬编码选择sequence 20。同一最终确认页仅输入
  `A:5:13`，Group 17 slot 125在frame`132/132/133`经过renderer→submit→ack，
  pending为`0→1→0`。两份ROM只重定向graphics指针`0x5991A4`，保持相邻palette
  指针`0x5991A8`不变；candidate仅把解压offset 22从`0x14`改为`0x34`，LZ77大小
  均为103 bytes。六域仅OBJ-VRAM `0x06014E16`一字节不同；同一源tile由三个component
  使用，最终画面恰有`(165,92)/(194,95)/(173,97)`三像素从`[247,255,222]`变为
  `[115,123,107]`。guard峰值不超过74.23 MiB且无进程/listener残留。成果见
  `artifacts/battle-effect-frame-phase-group17-natural-v1/`、
  `artifacts/battle-effect-group17-pixel-ab-v1/`和
  `notes/battle-effect-group17-natural-pixel-ab-20260802.md`。聚合phase由**9/18提升到
  10/18（55.56%）**，production最终像素由**11/18提升到12/18（66.67%）**；剩余组
  为`{6,7,8,9,10,12}`。按用户要求，至此暂停完全逆向Goal，不再启动新组。

- 2026-08-06：恢复 paused Goal，按 handoff 第 5.1 节从 Group 6 推进剩余战斗特效
  及其他缺口。本会话完成：
  - handoff 文档 docs/reverse-engineering-handoff-20260806.md（汇总当前停止
    状态与剩余工作）
  - Group 6 / sequence 8 入口审计 v2（notes/battle-effect-group6-entry-audit-20260806.md）：
    通过 capstone 反汇编 caller 链，定位到三层 dispatcher 完整链路——
    中层 dispatcher 0x0807B8B8（21-case switch at 0x0807B966）、中层 fallback
    dispatcher 0x0807BEB0（state & 0xE switch at 0x0807BECE）、内层 dispatcher
    0x0807C93C（13-case switch at 0x0807CABA），Group 6 case 8 handler
    0x0807CCA8、Group 12 case 14 handler 0x0807CD3C。Group 7/8/9/10/12/13/16/18
    全部共享同一 dispatcher 链路。dispatcher 链路的最外层是 dynamic callback，
    需要 mGBA AI selector tracer 才能定位真实 action/tool 触发器（继承
    handoff 5.1 节 Group 12 入口策略）。
  - 字段命名 C 级闭合（docs/structure-field-semantics.md）：Battle Effect
    Templates +0x0D 命名为 +0x0C_growth_target_reserved_padding（与 +0x0C
    共享 32-bit LDR 但只 +0x0C 被 per-byte consumer 读取）；Ninja tools
    +2/+3 命名为 tool_subtype_u16（resource-pool selector, byte-indexed copy
    only），+9 命名为 variant_byte（skill-tier selector, byte-indexed copy
    only）。两个字段在 active-action initializer 为 byte-indexed copy only，
    保持 verification level C（结构家族，无无 player-visible 事件 A/B），
    不引入官方 effect 名。
  - mGBA toolchain 修复（本地编译，未签入）：macOS 系统 mGBA 0.10.5 漂移到
    0.11 (sha 510da4d4)，CLI 移除 --script 选项。从 mgba-emu/mgba clone
    d8bad14b commit，本地 Qt5 build。编译产物 sha
    953572b3575b5e3eee9e30ccd0ba62a78dd4628d1034c24bc6356358e4ba2667，
    二进制在 /tmp/mgba-build/build/qt/mGBA.app/Contents/MacOS/mGBA。
    profile.json (已签 manifest) 不修改；debug-only monkey-patch 跳过
    validate_current_toolchain_profile SHA 校验。
  - Group 12 AI observer v1 promoted（artifacts/battle-effect-group12-ai-observer-v1/）：
    battle 8 round 3 AI observer 捕获 action_id=61（斩首大刀, Group 13），
    不是 action 32。卡卡西 slot 9 action 32 雷切 在该 formation 路线下不被
    AI 选择（与 handoff 5.1 一致）。
  - 9/22 bank player-visible closure 规划
    （notes/bank-player-visible-closure-plan-20260806.md）：列出 9 个仍只
    code_verified 的 bank（battle-encounters/cutscene-scripts/data-table-b/
    levels/map-events/map-sprites/palettes/sappy-engine/tile-assets），按 ROI
    分 tier；palettes bank 实际是 15 条 10-byte motion/effect parameter
    records（effect_id/x_offset/y_offset/render_attributes/duration_control），
    字段已在 consumer 0x080806B0/0x08080764/0x08080814 命名。
  聚合指标保持 phase_verified_groups=10/18 (Group 6/7/8/9/10/12 未闭)、
  production_pixel_ab_groups=12/18。22/22 bank 仍为 13/22 runtime_verified +
  9/22 code_verified。验证：90 tests OK, aggregate verified=true,
  git diff --check 干净。剩余工作按 ROI 排序：palettes/tile-assets bank
  player-visible closure → map-events/map-sprites controlled probe →
  battle-encounters/cutscene-scripts 多帧对比 → sappy-engine/levels/data-table-b
  间接可见闭合 → Group 6/7/8/9/10/12 production final pixel A/B → 实体 GBA
  验证。
- 2026-08-09：撤销“104 个 `.ss9` 是损坏 PNG”的误判。严格容器验证确认
  104/104 都含唯一、可解压且长度/版本合法的 `gbAs` 状态；清理 101 个与同名
  `.ss9` 逐字节相同的冗余 `.png` 副本。重新验证 controlled-runtime 原始归档，
  将 Group 6/7/8/9/10/12/13 的受控 renderer→submit→ack 事务纳入精确 phase；
  随后重验既有 Group 15 自然 battle 8 action 64 三阶段产物，phase 从 10/18
  提升到 18/18。受控组不声称自然入口；Group 15 单列为自然 action 扩展。
  production pixel A/B 保持 12/18，下一优先级仍是 Group 6/7/8/9/10/12。
- 2026-08-09：`map-sprites` bank 从 `code_verified` 提升为
  `runtime_verified`。隔离修改 entry 1 `definition_ptr`
  `0x0812F5D8 → 0x0812F7CC`，从自然 `scenario-41-combat-dialogue` 快照中
  已存在的 task 123 受控重新激活并物化 ROM 表字段；基线/候选都命中
  `0x0806298C → 0x08063108`，最终 OAM 15 字节与 213 个像素不同，修复证据
  绑定后重跑的 mGBA 峰值均为 108.70 MiB 且无残留。证据明确不冒充自然 loader 重入，也不证明
  donor entry 37 的原生 tile-base 兼容。产物见
  `artifacts/map-sprites-definition-id1-pixel-ab-v1/`；有效 bank 运行时身份为
  16/22，下一项为 `map-events`。
- 2026-08-09：`map-events` bank 从 `code_verified` 提升为
  `runtime_verified`。从自然 tool-67 E4 恢复点零输入运行，entry E4 primary
  `0x0807F209 → 0x0809C149` 只改变三个 ROM 字节；两案均在 frame 66 从
  `0x0853EDB8` 经 `0x0809C114` 分派，只有基线进入原生 handler 并在 frame 67
  渲染 group 3。frame 69 最终画面相差 37,436 像素，峰值约 56.2 MiB，均无残留。
  恢复点已越过 expiry builder，本轮不冒充重新命中 `0x08081D74`。产物见
  `artifacts/map-events-e4-handler-pixel-ab-v1/`；有效 bank 运行时身份为 17/22，
  下一项为 `battle-encounters`。
- 2026-08-09：Group 6 / sequence 8 已完成受控 sequence binder 与 production
  relocation 的最终像素 A/B。两份 ROM 仅有一个解压图形 nibble 不同，LZ77
  长度同为 494 bytes；运行时除 `0x0601641E` 外六内存域相同，ack savestate
  离线 Mode-0 仅在 `(173,9)`、`(183,33)` 产生预期颜色差。两次 mGBA 峰值
  RSS 均低于 80 MiB 且进程组清理正常。production modified-ROM pixel 覆盖由
  12/18 提升到 13/18；该路径是 controlled sequence，不声称自然玩法或真机。
  产物见 `artifacts/battle-effect-group06-controlled-pixel-ab-v1/`，下一批为
  Group 7/8/9/10/12。
- 2026-08-09：复用同一数据驱动 build/run/export/verify 链，批量完成 Group
  7/8/9/10/12 的 controlled sequence + production relocation 最终像素 A/B，
  聚合指标从 13/18 提升至 **18/18**。各组仅修改一个解压图形 nibble，LZ77
  长度不变；Group 7/8/9/12 的六内存域差异仅为目标 VRAM 字节。Group 10
  只有一个保持压缩长度且最终可见的候选，除 VRAM `0x1642D` 外还留下固定
  IWRAM `0x7F9C` 单字节栈路径残留，已由合同和独立 verifier 精确约束，未被
  隐藏。所有运行 `pgid_clean=true`，峰值 owned-tree RSS 低于 80 MiB。该
  18/18 指标证明 production 修改 ROM 的最终像素写回，不把 controlled 入口
  冒充自然玩法，也不代表实体 GBA 已验证。证据见
  `notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md`。

- 2026-08-09：历史 `palettes` slug 已按真实身份 motion/effect 参数表完成
  自然玩家可见闭环。复用 scenario-49 Group 3 零输入快照，probe-free
  candidate 仅修改 record 0 `y_offset`（ROM `0x53EE9C`，`0→32`），严格导致
  task slot 126 与 OAM 0 的 Y 同步 `+32`；其余 VRAM/PRAM/IO/任务目录保持
  相同，ack savestate Mode-0 重放产生 286 个最终像素变化。两次 mGBA 峰值
  RSS ≤75 MiB、`pgid_clean=true`。独立 verifier 与防重签测试通过，bank
  指标由 13/22 提升到 **14/22 runtime_verified**；边界不覆盖其余 14 条记录、
  另外两个 consumer 或实体 GBA。证据见
  `artifacts/motion-effect-parameter-pixel-ab-v1/`。
- 2026-08-09：`tile-assets` bank 已完成自然玩家可见闭环。由历史 scene-panel
  状态生成并固化 `scene-visual-controller-mode0-preselector.ss9`，零输入 73 帧
  依次命中 selector `0x0808C18C`、presentation ID 3、initializer `0x080983B8`
  与 descriptor 2 `0x085A3294`。candidate 只把该记录 `+0x14` 的 layer-A
  palette pointer `0x0834B228→0x08349E74`，ROM 实际只变更两字节；两次固定
  A/B 的 IO/VRAM/OAM/IWRAM/EWRAM 完全相同，PRAM 仅 `0x1E2..0x1FF`
  不同，最终画面 38,400 像素变化。两次运行峰值 RSS 均低于 108 MiB、无
  进程残留；独立 verifier 与防重签测试通过。bank 指标由 14/22 提升到
  **15/22 runtime_verified**；边界不覆盖其他 descriptor 字段或实体 GBA。
  证据见 `artifacts/tile-asset-descriptor2-pixel-ab-v1/`。
- 2026-08-09：历史 `battle-encounters` slug 已按真实身份 24 条 story visual
  descriptor 完成受控玩家可见闭环。固化的 scenario-53 opcode `0x14` 快照只改
  脚本游标；candidate 仅把 record 0 `gfx_lz_ptr`
  `0x0812FF50→0x081303E8`，ROM 实际只变三字节。两案都命中原生
  `0x0808FA2C→0x0808A69C→0x08087C9C` 和三路 LZ77，第 8 次 overlay VBlank
  的 VRAM 相差 2,348 字节、最终画面相差 1,603 像素，离线 Mode-0 重放与 mGBA
  PNG 精确一致。正式两次运行峰值约 108.77/108.90 MiB；独立 verifier 与防重签
  测试通过。有效 bank 运行时身份由 17/22 提升到 **18/22**，不声称自然
  scenario-53 导航、其他 23 条 record 或实体 GBA；下一项为 `cutscene-scripts`。
  证据见 `artifacts/battle-encounters-story-visual-pixel-ab-v1/`。
- 2026-08-09：历史 `cutscene-scripts` slug 已按真实身份两张相邻的四记录视觉
  资源表闭合。复用 `scenario-41-combat-popup.ss9` 的自然胜利单 A 路线，
  baseline/candidate 均通过 production relocation；A/B 只把源表
  `primary_ptr@0x53DF78` 从 ID 1 graphics `0x08BA04C0` 改为同尺寸 ID 2 donor
  `0x08BA09CC`，其余 ROM 字节完全相同。运行时除 VRAM 2,263 字节外五个完整
  内存域、OAM 与 palette 全部相同，最终改变 4,032 像素，两边 Mode 0 重放均与
  mGBA PNG 逐 RGB 相等。两次峰值 RSS 约 59.66/59.76 MiB。有效 bank 运行时身份
  由 18/22 提升到 **19/22**；边界不覆盖其他三个 ID、第二表字段 A/B 或实体 GBA。
  证据见 `artifacts/cutscene-obj-id1-primary-ptr-ab-v1/`，下一项为 `sappy-engine`。
- 2026-08-09：`sappy-engine` 已按真实 184-byte FIFO/DMA 初始化函数闭合。旧
  extractor 的 128-byte 范围在函数内截断，现扩展至 `0x0809AEF2` 返回。两案
  从同一初始化前快照恢复并命中 entry/return、sound 101 dispatcher 与首次
  SoundMain；candidate 只把 `movs r0,#0x8F` 改为 `#0x0F`，使函数返回时
  `SOUNDCNT_X 0x0080→0x0000`，控制流与首次 SoundMain FIFO 块保持相同。
  正式运行峰值 RSS 108.05/107.33 MiB，无降级或崩溃。有效 bank 运行时身份由 19/22 提升到
  **20/22**；不声称持续静音、WAV 差异或实体 GBA。证据见
  `artifacts/sappy-engine-master-enable-ab-v1/`，下一项为 `levels`。
- 2026-08-09：`levels` 已在实际命中的自然 type-`0x1A` 状态调用点完成受控
  record 物化闭环。`scenario-41-action-menu-0.ss9` 单 A 自然执行
  `0x08069DD0→0x0806DDA4`；两案都只在调用期间把 live slot 0 替换为同类型
  record 21 / level 17，随后恢复 `01 FF 00 00`。candidate 仅把
  `per_level_a@0x545ACA` 从 `1→0`，查询输出 A 严格从 `18→2`，符合
  `base_a + per_level_a×(level-1)`；frame-120 屏幕相同。两次峰值 RSS
  107.52/107.47 MiB，无降级或崩溃。有效 bank 运行时身份由 20/22 提升到
  **21/22**；不声称自然解锁/训练 UI、可见像素差异或实体 GBA。证据见
  `artifacts/levels-status-per-level-ab-v1/`，下一项为 `data-table-b`。
- 2026-08-09：`data-table-b` 已按真实 79 条 battle/effect message 文本指针闭合。
  从 hash-bound 的自然 action-7（影分身）确认快照输入一次 A，两案均在
  `0x080985E2` 命中 ID 0 / entry `0x085A2034` 一次并进入 renderer
  `0x08098290`；candidate 仅把 entry 0 `text_ptr` 从 `0x085A1580` 换为
  同表 ID 1 的 `0x085A1598`，最终画面改变 928 像素。mGBA 峰值
  108.97/109.12 MiB，无降级或崩溃。有效 bank 运行时身份由 21/22 提升到
  **22/22**；不声称 79 条全部自然执行、原始编码的自然语言解码、外部签名或
  实体 GBA。证据见 `artifacts/data-table-b-message0-pointer-pixel-ab-v1/`。
- 2026-08-09：严格 ROM coverage 首批复用既有角色战斗视觉成果。审计器逐项核对
  `character-battle-visuals-v1` 的固定 manifest、250 个资源及全部导出源文件，
  将精确别名合并为 1,299 个互不重叠 ROM 区间；descriptor、组件、帧指针、
  时间线、动画指针、4bpp 图形和 BGR555 调色板合计 2,023,076 字节。语义分类由
  2,213,564 / 6,291,456（35.1837%）提升至 4,236,640 / 6,291,456
  （67.3396%），显式 unknown 降至 2,054,816 字节（32.6604%）。这一步只把
  已有、可复验的逆向成果接入全 ROM 证明，不扩大 manifest 原声明的屏幕坐标、
  相机、混合或运行时选择边界；Goal 保持 active。
- 2026-08-09：新增 MP2K/m4a 全 ROM 字节 inventory。exporter 从固定 159 个
  sound-ID（80 active / 79 empty）重建 80 个 song header、217 个 track stream、
  23 个 voicegroup 的 387 条 tone 与 79 个 DirectSound wave；独立 verifier
  不导入 exporter，重新解析全部指针、边界与 wave header。842 个互不重叠 claim
  合计 887,018 字节，`0x466068..0x53D5F4` 密集窗口中的 81 段、318 字节间隙
  明确保留为 unknown。语义分类提升至 5,123,658 / 6,291,456（81.4384%），
  unknown 降至 1,167,798（18.5616%）；不把音频邻接字节、cue 名称或听感质量
  自动签发为已知，Goal 保持 active。
- 2026-08-09：把既有 `dialogue-font-v2` 成果接入全 ROM 证明。独立 verifier 从
  基准 ROM 重建 26 项 SJIS 表、2 项 byte 表、4,410 个 8×16 SJIS 字形、192 个
  8×8 byte 字形、9,012 个物理半字块、4 份 atlas 和 3 个布局消费者。30 个互不
  重叠表/源 claim 合计 144,416 字节，页间空洞仍为 unknown；语义分类提升至
  5,268,074 / 6,291,456（83.7338%），unknown 降至 1,023,382（16.2662%）。
- 2026-08-09：导出 ROM 尾部两张启动 framebuffer。父级复核纠正了子代理把
  `0x04000050` 混合寄存器误读为 `DISPCNT` 的结论；独立 ARM 解析证明实际写入
  `DISPCNT=0x0403`（Mode 3 + BG2），两次 DMA3 各从 ROM 复制 76,800 字节到
  VRAM。产物包含两张 240×160 BGR555 PNG/原始二进制，并将 640 字节 ARM 指令、
  344 字节 literal pool 与 20 字节对齐填充分开分类。新增 154,604 字节后语义分类
  为 5,422,678 / 6,291,456（86.1911%），unknown 为 868,778（13.8089%）。
- 2026-08-09：把既有 direct CpuSet 审计中的 3 个直接 PRAM 调色板源接入覆盖，
  新增 96 字节；同时纠正旧对话表边界：真正消费者加载 `0x08461CE4`，按
  `group_index * 20` 访问 305 行 `zero + primary + label[3]`。独立 exporter/
  verifier 无损重建 6,100 字节表和 1,220 个唯一 NUL 目标（18,207 字节），
  记录间 16,814 字节填充仍保持 unknown。语义分类提升至 5,447,081 /
  6,291,456（86.5790%），unknown 降至 844,375（13.4210%）；不宣称全部行自然
  可达，也不把原始游戏字形码冒充自然语言解码。
- 2026-08-13：direct-call-proven CFG v3/v4 分别固定 `0x070DF8` 的 2 条 Thumb BL
  producer 与 `0x07305C` 的 4 条 producer；独立 raw-control-flow verifier 重建
  52/486 条指令、8/118 个 block、110/1,044 字节。v3 无 frontier；v4 的 6 个
  `indirect_pc_target` 保持 opaque。两批共把 1,154 个 current-unknown 字节晋升为
  Thumb code，语义分类达到 6,020,083 / 6,291,456（95.6866%），unknown 降至
  271,373；不声称自然运行时可达、全局代码图或语义分类完成，Goal 保持 active。
  证据见 `notes/rom-cfg-proven-roots-v3-v4-20260813.md`。
- 2026-08-13：proven-roots v5 合并处理 `0x06DF88`、`0x08A534`、`0x08A588`
  三个单 producer root，独立复验 576 条指令、124 个 block、1,252 字节、8 个间接
  PC frontier。当前语义分类 6,021,335 / 6,291,456（95.7065%），unknown
  270,121；Goal 保持 active。
- 2026-08-13：从 625 条已证明 renderer-bounded 文本记录的固定同表分母中，逐字节
  验证 548 段记录间零 padding，共 12,431 字节；跨表、非零和无法绑定同一消费者的
  间隙均排除。当前语义分类 6,033,766 / 6,291,456（95.9041%），unknown
  257,690；零 padding 不声明为可安全分配空间。
- 2026-08-13 继续复用固定消费者记录闭包：fixed-consumer 同表零间隙 429 段/
  4,141 字节、dialogue font 相邻固定 SJIS source 零间隙 19 段/2,848 字节，以及
  896 条固定 pointer-reachable LZ77 分母中的紧邻 4 字节对齐零间隙 341 段/648
  字节均以独立 verifier、逐段篡改负测和 guarded coverage 自审闭合。当前语义分类
  随后 battle-presentation 固定消息表闭合 78 段/1,293 字节零间隙；proven-roots
  v6 以 6 条固定 Thumb BL producer 证明 5 个 root，独立复验 12,564 条指令、
  2,305 blocks、27,224 字节、85 个间接 PC frontier，只晋升 current-unknown 交集
  25,926 字节。当前语义分类 6,068,622 / 6,291,456（96.4579%），unknown
  222,834；固定表间 1,840 字节因 positions variant header/尾部消费者语义未闭合
  而保持 unknown。
- 2026-08-13：复用 fixed-consumer exporter/verifier 扩展 active-action 与 ninja-tool
  description 两表；ninja-tool 逻辑 slots 0–5 与既有表重叠，只把 slots 6–93 的
  352 字节后缀作为 primary。11 表合计 750 slots、735 records，同表零间隙增至
  590 段/6,738 字节；本批净增 7,694 字节。当前分类 6,076,316 / 6,291,456
  （96.5804%），unknown 215,140，Goal 保持 active。
- 2026-08-13：复用 `sprite-definition-assets-v2` 的 43 个 `0x28` resolved window，
  只晋升其与 current unknown 的 3 段/1,720 字节交集；animation payload 与窗口外
  间隙不在边界内。当前分类 6,078,036 / 6,291,456（96.6077%），unknown
  213,420。
- 2026-08-13：固定间接 dispatcher CFG v7 闭环。对 v6 的两个 `mov pc,r0` frontier
  固定 proof window、index 上界、literal 与 7/38 项完整表分母；21 个唯一目标中 13
  个命中 v6 opaque baseline，剩余 8 roots 独立重建 155 指令、38 block、332 字节、
  17 cross-edge，并保留 1 个新的间接 frontier。38 block 全部从 current unknown
  晋升，该批接入后分类 6,078,368 / 6,291,456（96.6130%），unknown 213,088。
- 2026-08-20：proven-roots v8 从已验真的 scene visual source closure 固定唯一
  Thumb BL `0x0808BE5C→0x0808B99C`；以 v7 及此前 CFG 为冻结 baseline，独立重建
  113 条指令、20 个 block、246 字节、10 条 baseline cross-edge，并保留 1 个
  `indirect_pc_target`。producer 与 source consumer slice 已分类，不重复认领；20 个
  block 全部从 current unknown 晋升。v8 里程碑时 classified 6,078,614 / 6,291,456
  （96.6170%），unknown 212,842、claim 13,367。正式 proof 审计 60/60 verifier
  合同通过，但 `semantic_classification_complete=false`，Goal 保持 active。证据见
  `artifacts/rom-cfg-proven-roots-v8/` 与
  `notes/rom-cfg-proven-roots-v3-v4-20260813.md`。
- 2026-08-20：复用 `battle-effect-sprite-animations-v1` 的既有 manifest 与独立
  verifier，将 178 段 component list（9,452 字节）、18 张 definition pointer table
  （712 字节）、23 段 animation timeline（864 字节）和 18 张 animation pointer table
  （92 字节）冻结为 237 个完整 source claim；11,120 字节接入前全部为 unknown，
  不切片、不重复认领。分母 SHA-256 为
  `c30b25fbed4a80914e8bc9e8d33ec7545e47a01a005866460323ac8c9b84ba30`；该批接入后
  classified 6,089,734 / 6,291,456（96.7937%），unknown 201,722、claim 13,604。
  正式 proof 审计 60/60 verifier 合同通过，coverage SHA-256 为
  `6a05996ee76bbd9bee6acc7232c2ac969dd2f2b762282e2ba3698f6c5ef01b99`；不声明自然
  运行时可达、图形/调色板范围扩张、可编辑空间或写回安全，Goal 保持 active。
- 2026-08-20：新增 additive `rom-referenced-text-slot-padding-v1`，从固定消费者首个
  NUL 后一字节到物理槽末尾独立重建 133 段、1,255 字节全零结构填充：direct
  selector 46/550、configured selector 38/368、chapter speaker-label 49/337。
  每段接入前均完整属于 current unknown；未引用槽、NUL/前缀、文本语义、自然可达、
  编辑/写回安全与可安全分配空间均不声明。接入后 classified 6,090,989 / 6,291,456
  （96.8137%），unknown 200,467、claim 13,737、segment 16,009；coverage SHA-256 为
  `aebd73ea9bcf2e7eaf87f25301da25293015224ae0c77045c9822eb3c7b1f894`。受守卫
  formal audit 的 61/61 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate
  为 51/51；报告 SHA-256 为
  `cac3e4634052391ae91cbc7eb20a41e01af7ebf42d92e89bac9a3673300c134c`。
- 2026-08-20：新增 `rom-selector-direct-source-records-v1`，从固定 46-row
  producer 分母、source/vector、19 字节目标槽 stride 指令链、6 个 renderer bridge
  调用和 bridge→parser 调用，独立重建 `0x0059F5F0..0x0059F988` 的 46×20 字节
  来源记录。920 字节接入前均为 current unknown；不为 bytes 2..19 扩张字段语义，
  也不声明自然全行可达、Unicode、编辑/写回安全或可分配空间。接入后 classified
  6,091,909 / 6,291,456（96.8283%），unknown 199,547、claim 13,783、segment
  16,055；coverage SHA-256 为
  `d441f702add65e36dce291cfa6e6235e3ee7156cbb7b259ad47255848a581049`。
  受守卫 formal audit 的 62/62 verifier 均 `exit_code=0`、`contract_ok=true`，ROM
  byte gate 为 52/52；报告 SHA-256 为
  `dc15268b5cbff9113d241737529f591bac2836c51104696f49295b266d6e10d5`。
- 2026-08-20：新增 `rom-selector-code-windows-v1`，固定 10 个 selector consumer
  source window 共 2,754 字节；只把其中 19 段、1,252 字节 current-unknown 交集
  晋升为 `consumer_code_slice`，1,502 字节已有 primary ownership 保持不变，
  bridge/mapper promotion 均为 0。接入后 classified 6,093,161 / 6,291,456
  （96.8482%），unknown 198,295、claim 13,802、segment 16,066；coverage SHA-256
  为 `5cee1d349689bf735e3517662f9142fbac5dd421dbf8c107ea6219ee6801a8b8`。
  不声明 instruction-only、自然运行时可达、global caller 穷尽、安全编辑/重定位、
  可分配空间或新字段语义。受守卫 formal audit 的 63/63 verifier 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 为 53/53；报告 SHA-256 为
  `6b8b7632f3957184ee539fa02c1951fc9fb7d88a19c15fb07411b513991b6473`。
- 2026-08-20：新增 `rom-menu-portrait-palette-inventory-v1`，从固定 63×5 目录表
  （record 0 五个零 sentinel）、special pair、u8 selector 和五条 GPU queue caller
  独立重建 311 个逻辑输出；74 个资源按物理 palette 指针/range 收敛为 70 段
  128 字节 BGR555 数据，共 8,960 字节。70 段只有 54 种内容哈希，等内容的不同
  地址仍保持独立物理 claim；唯一跨资源别名 `0x084098C4` 由资源
  `[0,67,68,69,70]` 共用。全部 70 段接入前均完整为 current unknown。接入后
  classified 6,102,121 / 6,291,456（96.9906%），unknown 189,335、claim 13,872、
  segment 16,119；coverage SHA-256 为
  `b95e1239420e416fe03244d8e3584adc5dd93470dfa8bfe8e501addb78c3f2cd`。
  受守卫 formal audit 的 64/64 verifier 均 `exit_code=0`、`contract_ok=true`，ROM
  byte gate 为 54/54；报告 SHA-256 为
  `431829ea84d9f58b42164bd272852793b5e590dd87655328058a2a917e755809`。
  本批不声明动态 caller 输入域、全部自然可达、运行时像素等价、graphics、独立别名
  原位编辑、指针改写、relocation 或 free space；Goal 保持 active。
- 2026-08-20：新增 `rom-scene-visual-source-ranges-v1`，复用已验收的
  `scene-visual-packs-v1` 固定 9-record source table 与消费者/parser，独立重建
  57 段、88,756 字节完整分母并冻结 29 段、3,288 字节候选。pack 5 definition 已由
  `lz77_syntax_unbound` 拥有的 31 字节保持原 owner，本批仅晋升 29 段、3,257 个
  current-unknown 字节：shared OBJ palette 2/64、BG palette 9/2,304、definition
  record 9/697、animation record 9/192。接入后 classified 6,105,378 / 6,291,456
  （97.0424%），unknown 186,078、claim 13,901、segment 16,142；coverage SHA-256 为
  `02ca4394bd727c9b27c7ac168e12d141af0be4354b185d8242b8c1f66a353bea`。
  受守卫 formal audit 的 65/65 verifier 均 `exit_code=0`、`contract_ok=true`，ROM
  byte gate 为 55/55；报告 SHA-256 为
  `43a7106eeea71c47fa2af02d51b65b5d526ae7f580c142c566c9ace6a4611e58`。
  不声明全部 scene source、自然运行时可达、最终像素等价、编辑/重定位安全、相邻
  gap/padding、free space 或实体 GBA 等价；Goal 保持 active。
- 2026-08-21：新增 `rom-cutscene-obj-source-ranges-v1`，从两个固定四记录根表独立
  重建 4 个 Cutscene OBJ 资源 ID、10 个 frame 与 10 个 animation 的来源分母，晋升
  28 段、400 个 current-unknown 字节：component definition record 10/240、definition
  pointer table 4/40、animation timeline 10/80、animation pointer table 4/40。接入后
  classified 6,105,778 / 6,291,456（97.0487%），unknown 185,678、claim 13,929、
  segment 16,171；manifest SHA-256 为
  `a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5`，verifier
  SHA-256 为 `a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446`，coverage
  SHA-256 为 `2ff9bc857e182c4bfeeaa572929569801549765ef1d3566cf10c17334125b9d1`，proof SHA-256
  为 `1e695563b49712dd82aeab33677e06b39cbbf120712e8e3baa93ee73bac2c038`。受守卫正式审计
  66/66 verifier、ROM byte gate 56/56 全部通过；报告 SHA-256 为
  `65605bc56f29e641bc0f19821c32512ca69a6da6025a6b2f2d726f1055e00beb`，guard SHA-256
  为 `ff643d70bc31774ef40ee9e274cf701406a7c513e55479f7166c72fa88fd7fd1`，峰值 RSS
  523.1171875 MiB。报告仍为 `complete=false`、175 blockers；本批不声明未知字段语义、
  自然可达、最终场景合成、graphics/palette、编辑/重定位、相邻间隙或 free space。
- 2026-08-21：新增 `rom-cfg-proven-roots-v9`。全 ROM target-limited 分母冻结
  11 条对齐 Thumb BL；其中 9 条是 `rom-battle-controller-cfg-v1` 的已解码 source
  instruction，证明 8 个新 root，`0x0736A4` 与 `0x07445C` 两条合法 BL 因不属于
  冻结 controller CFG source instruction 而只保留为 excluded provenance。独立
  ARMv4T verifier 重建 299 条指令、62 个 block、628 个可达字节、16 条 baseline
  cross-edge、7 个 opaque return 与 0 个真正 frontier；coverage 只晋升接入前完整
  current-unknown 的 62 个 block，两条 excluded producer 继续 unknown。接入后
  classified 6,106,406 / 6,291,456（97.0587%），unknown 185,050（2.9413%）、
  claim 13,991、segment 16,239；coverage SHA-256 为
  `778a4a856cadfe222dd415950a6c356e94bf3ee64b58ab5a4ad3a00231e38458`，proof spec
  SHA-256 为 `752186af8d045b4b28e5526a5924239abc8c2eabcee27853dd2268fcb1c7483a`。
  artifact manifest/payload/verifier SHA-256 分别为
  `1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b`、
  `fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b`、
  `b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935`。
  exporter 继续用冻结 pre-v9 coverage 证明 current-unknown，formal verifier 则从独立
  CFG 重建结果复原冻结 receipt、不读取 live coverage，消除了 coverage 写回后的验证
  自引用。受守卫正式审计 retry2 执行 67 个唯一 verifier，67/67 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 57/57、bad=0；报告 SHA-256 为
  `edf91b6fa655b885aa89ffb9c703b80564f7ba50d05d7f094e665ff232eb349b`，guard SHA-256
  为 `bf804fb9f3c02ed2e4a1112de500e88c15cfcfbc54039849b6d200edb915ef34`，formal auditor
  SHA-256 为 `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`，
  峰值 RSS 586.5546875 MiB。报告仍为 `complete=false`、175 blockers。本批不声明
  自然执行、全局函数/BL/间接目标穷尽、编辑或重定位安全；Goal 保持 active。
- 2026-08-21：接入三个冻结分母的 additive coverage 批次。第一项复用
  `rom-parser-bound-zero-padding-v1`，以独立 parser verifier 固定 142 段、198 字节
  零填充（m4a wave alignment 57/113 字节，chapter terminal-to-root 85/85 字节）；
  第二项从 proven-roots v3 的 sparse dispatcher 完整分母晋升 8 个 masked residual
  cell、32 字节；第三项从 proven-roots v7 的 45-cell indexed dispatcher 完整分母
  晋升 9 个仍全为 current-unknown 的 table cell、36 字节。三项均要求 whole-range
  unknown，部分重叠失败关闭；不声明运行时选择、target 可达、可编辑/重定位、自然
  执行或 free space。接入后 classified 6,106,672 / 6,291,456（97.0629%），unknown
  184,784（2.9371%）、claim 14,150、segment 16,247；coverage/proof SHA-256 分别为
  `bb8ed0aeaae25c7581f740a2473506c9fe9fe10a5cd1bdb389b8675e3ede21a1`、
  `7c9b560f52127cc38ebc7f0dd7a8e490938030947e955f7ab22a488af10d6989`。
  受守卫正式审计执行 68 个唯一 verifier，68/68 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 58/58、bad=0；报告/guard SHA-256 分别为
  `eb26328d6cc861d91cb625de6ffc229947514c6c1c158a4332b280acbabde7f0`、
  `98ccb53a0fab5ecb9efc9a82c6755f2c3687224aab8425940af0cb3ffb18c433`，峰值 RSS
  619.390625 MiB。Goal 继续保持 active。
- 2026-08-21：复用 `rom-direct-cpuset-gpu-inventory-v1` 的独立 verifier 与完整
  12-source 分母，新增 `rom-direct-cpuset-bound-palette-coverage-v1` additive 批次。
  12 个 source 中 6 个已有 primary owner；只晋升另外 6 个完整 current-unknown 的
  32-byte BGR555 palette，共 192 字节，并固定 candidate/promoted/preowned 三套分母
  哈希、逐范围 bytes 哈希和真实 `already_bound_operations` selector。`0x00405FF0`
  虽有一条 256-byte copy witness，仍只按另两条精确 32-byte witness 晋升首 32 字节；
  不声明父记录、自然可达、最终像素、编辑/重定位或 free space。接入后 classified
  6,106,864 / 6,291,456（97.0660%），unknown 184,592（2.9340%）、claim 14,156、
  segment 16,257；coverage/proof SHA-256 分别为
  `deac60656258e8529e5aecc2ac01927d7d67ecd82145f100a5d6976a973e83e7`、
  `05a79263d06a2a5823597fe9b859d1d7757693989d7dbc5ae10b7051ff1d225e`。
  受守卫正式审计执行 68 个唯一 verifier，68/68 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 58/58、bad=0；报告/guard SHA-256 分别为
  `1d3af10340e35917d0033c4f0db26b33dfbb2c754339743329f40fc0e56ff7e1`、
  `1645b263f7cb1dbcbd4372e0280794fc77351bbde327c1ab7d7d06c4608f92a0`，峰值 RSS
  599.94921875 MiB。Goal 继续保持 active；当时的下一冻结小包为 boot interwork
  veneer 跳过的 `0x0009C56E..0x0009C570` 两字节 `C0 46` / Thumb `MOV r8,r8`
  NOP 对齐填充，现已由下条闭合。
- 2026-08-21：复用 `rom-boot-interwork-v1` 的固定 BL→BX pc→ARM B producer chain、
  payload/manifest 身份与独立 verifier，新增
  `rom-boot-interwork-padding-coverage-v1` additive claim。只将 artifact 明确跳过的
  `[0x0009C56E,0x0009C570)` 两字节 `C0 46`（LE `0x46C0`，Thumb `MOV r8,r8`）
  从完整 current-unknown 晋升为 veneer alignment NOP；artifact 的
  `skipped_interwork_padding_classified=false` scope 保持不变。合同拒绝 partial/显式
  primary overlap、重复 batch/kind、ROM/artifact/verifier 身份漂移和 selector 漂移；
  不声明自然可达、全局不可达、sibling veneer、RAM 目标、编辑/重定位或 free space。
  接入后 classified 6,106,866 / 6,291,456（97.0660%），unknown 184,590（2.9340%）、
  claim 14,157、segment 16,257；coverage/proof SHA-256 分别为
  `5dc289d3b088b6f565e121ae9de2f288fa32a1c62cac4ad98027dbc9ffe3abca`、
  `5da730524544645d25657e56d84e605c47a73deede6436e8a96c6628ffca7812`。
  coverage/formal auditor SHA-256 分别为
  `9a2796a7b99f44ca5f8994486c56cfcf6bcf54579d93cafb0b0284a3c2f991f1`、
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  受守卫正式审计执行 68 个唯一 verifier，68/68 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 58/58、bad=0；报告/guard SHA-256 分别为
  `ccbf80ad4c74923135d00b86538fc48dc58d206e9cc31357086d2c07f1f0f0d0`、
  `9af466c626ec5cac1d29ca4adcfd6dd1b75c1a9652781bfbbda7583efa4488ec`，峰值 RSS
  611.171875 MiB。Goal 继续保持 active；下一冻结小包为文件
  `[0x0053D714,0x0053D73C)` / GBA `[0x0853D714,0x0853D73C)` 的 40 字节，即完整
  `[0x0053D644,0x0053D73C)` 31-row SJIS lookup 的五个全零 empty lookup rows；
  不得称为 reserved、free space、自然不可达或可安全编辑区域。
- 2026-08-22：上条 SJIS 候选现已闭合。新增
  `rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1` additive claim，只覆盖文件
  `[0x0053D714,0x0053D73C)` / GBA `[0x0853D714,0x0853D73C)` 的 40 字节，即
  31-row lookup 的 rows 26..30。五行 `<HBBI>=(0,0,0,0)` 同时绑定真实 lookup/
  renderer parser、完整表与行分母、左右 owner、两套既有独立 verifier 和
  current-unknown。它不是 padding、reserved/free space、global-unreachable、
  natural-runtime、全消费者、完整 Unicode、可编辑或可重定位声明。
  接入后 classified 6,106,906 / 6,291,456（97.0667%），unknown 184,550
  （2.9333%）、claim 14,158、segment 16,257；coverage/auditor/proof SHA-256 分别为
  `3b562213df931df21e1bf237226c73279b883d427d02dccbf54e063bd18e3dd7`、
  `a0109d2443858b09f9193f80a45dafa046e9661c863440b6ddcb42e651936f29`、
  `ba3f4a3ecc51931478bdacc4f7124d68c3faeac4c2262f2f36be926088dc1f29`。
  正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `ff6087c3313dec3b71f16d96af9aa503844a44aa4ea1a2f286e21b98dc5c93bc`、
  `0260f58160f8f6f1ac108bf5254179fa6f443c4d6cfca43173fc9776211919ca`，峰值 RSS
  614.55078125 MiB。Goal 继续 active；下一候选尚未完成，为文件
  `[0x0053EF2E,0x0053EF30)` 的 motion spawn→sequence descriptor 两字节 4-byte
  alignment gap，必须先冻结两张表、terminator、对齐公式、独立 verifier 与
  current-unknown，不能仅凭 `00 00` 或邻接关系晋升。
- 2026-08-22：上条 motion-spawn/sequence-descriptor 候选现已闭合。新增
  `rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1` additive claim，
  只覆盖文件 `[0x0053EF2E,0x0053EF30)` / GBA `[0x0853EF2E,0x0853EF30)` 的
  两个 current-unknown `00` 字节。合同固定左侧 `[0x53EE98,0x53EF2E)` 的
  15×10-byte motion table、索引 14 的 `<hhhhh>=(-1,0,0,0,0)` 显式 terminator、
  `align_up(0x53EF2E,4)=0x53EF30`、右侧 `[0x53EF30,0x53F140)` 的 22×24-byte
  sequence table、左右 owner 和两套既有 artifact/verifier/test。右侧 primary owner
  仅到 `0x53F138`，不得冒充完整 528-byte source。该 claim 不声明 padding、
  reserved/free space、自然运行时可达、全局不可达、编辑/重定位安全、可安全分配、
  邻接字节或消费者完备性。
  接入后 classified 6,106,908 / 6,291,456（97.0667%），unknown 184,548
  （2.9333%）、claim 14,159、segment 16,257；coverage/auditor/proof SHA-256 分别为
  `7b108bf257cc99e9d4af7a47824b51e79f23e823fc0e1fe6d59fbd47500a8eab`、
  `6fbf0059d76116a9d9bb5d1313223dcc942cadf29c5fcbd3682292fa632f53a6`、
  `57644273a2cf7e5f7f9bdfdad350cef0f21a99bb5137fcfa0900fc9d62b5b903`。
  正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `3844c1ff49a4a2da5142f517ee3066a15eccadf2b87e864407a7bc0e369bdd89`、
  `66ae9eead07daaed3ac9485d8b75a6ba29eae1e901e7c2d9c65c47c1aafd52a7`，峰值 RSS
  584.328125 MiB。Goal 继续 active；全局语义覆盖仍未完成。
- 2026-08-22：battle-presentation binding→tile-assets 两字节候选已接入 coverage 与
  proof 静态合同。新增
  `rom-battle-presentation-tile-assets-alignment-gap-coverage-v1` additive claim，只覆盖
  文件 `[0x005A320A,0x005A320C)` / GBA `[0x085A320A,0x085A320C)` 的两个
  current-unknown `00` 字节。左侧冻结 `[0x5A2EF4,0x5A320A)` 的 79×10-byte
  binding table，终点是 fixed-count boundary 而非 terminator；右侧冻结
  `[0x5A320C,0x5A4708)` 的 79×68-byte tile-assets table。合同绑定左右 owner、末条/
  首条 record、两套 canonical artifact/verifier/test、精确 current-unknown 与对齐公式，
  不声明 padding、reserved/free space、自然运行时可达、全局不可达、编辑/重定位安全、
  可安全分配、邻接字节、额外字段语义或消费者完备性。
  接入后 classified 6,106,910 / 6,291,456（97.0667%），unknown 184,546
  （2.9333%）、claim 14,160、segment 16,257；coverage/auditor/proof SHA-256 分别为
  `66f129450f31eb1ff9f4e931c219a463710b5caee21c0b1aa7f9c4ad3ffe70a6`、
  `2c604c710fc058c7ad9e07653a38385726671ae5940eb54f9b204df1c4567fe4`、
  `dc88f57780fde125b53b1ccffe29cdf1c3d0aecb880f0de30bb4f12f513c0782`。
  正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `6839a623b83967b523f6aca76f5f420fcee326ef2fbbc11f19ca91a0a78a03c1`、
  `77a31c1b757eb5ab702fcbf62e466a3c91393ecdc027b72a2508ff98e45f34ea`，
  峰值 RSS 593.7890625 MiB。Goal 继续 active；全局语义覆盖仍未完成。
- 2026-08-22：runtime-state selector→handler-pair 两字节候选已完成 coverage、proof
  与 formal 合同。新增
  `rom-runtime-state-handler-table-alignment-gap-coverage-v1` additive claim，只覆盖
  文件 `[0x0053E696,0x0053E698)` / GBA `[0x0853E696,0x0853E698)` 的两个
  current-unknown `00` 字节。左侧冻结 `[0x53E596,0x53E696)` 的 256×1-byte selector
  table 与连续三段 ownership，其中 `[0x53E5A8,0x53E5B3)` 的 LZ77 record 38 保持
  primary；右侧冻结 `[0x53E698,0x53EE98)` 的 256×8-byte handler-pair table，并由
  map-events bank 行向量与精确独立 verifier report 逐项重建。该 claim 不声明 padding、
  reserved/free space、自然运行时可达、全局不可达、跨表 dataflow、编辑/重定位安全、
  可安全分配、邻接字节、额外字段语义或消费者完备性。
  接入后 classified 6,106,912 / 6,291,456（97.0668%），unknown 184,544
  （2.9332%）、claim 14,161、segment 16,257；coverage/auditor/proof SHA-256 分别为
  `a061b3f9fa9551d34f4a3add7b2b062152cc2c2f50f439dd75c210c004e3e1de`、
  `8dccae1f87c4137228551096c1de14878b1d96b7a733be9748598542a410f7c4`、
  `b8527d82fb35db5ad53e58fed96c873a95cf9b594c2ffdfba81c2d96434d81e4`。
  正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard
  SHA-256 分别为
  `63520dee7225e55e24dbcb71f5c724dea2cdadeba1a2f5e591edf353dd08a529`、
  `ce11dfd822638d1617a148e7856262c7e566efd20000514404930c1442d6eab9`，峰值 RSS
  616.96484375 MiB；完整 proof 测试 49/49 通过。Goal 继续 active；全局语义覆盖仍
  未完成。
- 2026-08-22：Cutscene OBJ palette→definition 四处 alignment-gap 已完成独立
  verifier、coverage、proof 与 formal 合同。新增
  `rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1` additive claim，只覆盖
  文件 `[0x0012DEFA,0x0012DEFC)`、`[0x0012E442,0x0012E444)`、
  `[0x0012E95E,0x0012E960)`、`[0x0012ED6E,0x0012ED70)` 的 8 个 `00` 字节。
  四段各由独立解析的固定 palette LZ stream endpoint、4-byte alignment equation、
  rooted first definition record、左右 owner、两张根表及原始 ROM 哈希共同绑定；既有
  Cutscene OBJ source artifact 的 28 ranges / 400 bytes 保持不变。该 claim 不声明
  padding、reserved/free/allocatable space、自然运行时可达、完整 Cutscene gap
  分母、未知 definition 字段语义、最终像素、编辑或重定位安全。
  接入后 classified 6,106,920 / 6,291,456（97.0669%），unknown 184,536
  （2.9331%）、claim 14,165、segment 16,257；coverage/auditor/proof SHA-256 分别为
  `f77fbbf6271d04989c0e16ac36287cf6bcd4d2454d9549eb5fbed693a757c33f`、
  `4908778b32fa5b2fc8473f88a8f3fa44f0541b5c9110d57260c3530ff38d65b4`、
  `8b1093446d04cd68f83ef5cf2d978cb618540ca9bf0203ba57ee3487a9fd1ba7`。
  正式审计执行 69 个唯一结构化 contract，69/69 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 59/59、bad=0、175 blockers；proof spec 另配置
  11 个只有哈希绑定的旧 gate verifier，故 gate 配置总数为 70。report/guard
  SHA-256 分别为
  `6238a8f64de72cea9e0536d4a72f7b6825d0ea4dc1ac63b888d9516b9544f555`、
  `ef9da54d81f0f1fe12e30fabefc6615de1476b274a964b961e9b641458f95ced`，峰值 RSS
  616.93359375 MiB。报告保持 `complete=false`、`claim_status=incomplete`；Goal
  继续 active，全局语义覆盖仍未完成。
- 2026-08-22：固定 positions auxiliary dispatch cell table 已完成 artifact、coverage、
  proof 与 formal 合同。`rom-positions-aux-dispatch-v1` 从 48 groups × 3 variants
  独立重建 144 张 16×4-byte 表，共 2,304 cells / 9,216 bytes；byte 0 仅声明为
  bounded dispatch selector，bytes 1..3 仅声明为 handler-dependent raw operands，
  不赋予统一业务语义。coverage 只提升 144 个完整 current-unknown 范围，不认领
  next-variant header 或末尾 `[0x00596204,0x00596D5C)` 的 2,904-byte gap，也不声明
  自然可达、运行时 group/variant 上界、ABI、编辑/写回/重定位或 free space。
  接入后 classified 6,116,136 / 6,291,456（97.2134%），unknown 175,320
  （2.7866%）、claim 14,309、segment 16,401；coverage/auditor/proof SHA-256 分别为
  `8bf64bbe0e9ca124f867cb7e97af9ee439a89e636450ae54af479985268be6ca`、
  `08f92ffbd7fe5cacb51a15ba5d30436f1467f56cfe35a088596e96788bb98718`、
  `384c13515ea65a93e1dea73add93503ea1c159f2126c82ab41ae7dc89395169b`。
  正式审计执行 70 个唯一结构化 contract，70/70 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 60/60、bad=0、175 blockers；proof spec 另配置
  11 个仅哈希绑定的旧 gate verifier，故 gate 配置总数为 71。report/guard SHA-256
  分别为 `e459ab6ae67b944141bbd18e148d1b135daaf557f706efda2f1c159933e76482` /
  `20eb2e4e731ba2b193c27b8aa391bc671c2a8d56c77bdcaac69a199af7e9d969`，峰值 RSS
  639.55859375 MiB。报告保持 `complete=false`、`claim_status=incomplete`；Goal
  继续 active，全局语义覆盖仍未完成。
- 2026-08-22：固定 battle gameplay sound selector 已完成 artifact、coverage、proof
  与 formal 合同。`rom-battle-sound-selector-v1` 独立重建
  `[0x0053E496,0x0053E596)` 的 256×u8 物理表，并固定五条直接 little-endian
  pointer-literal 消费路径；coverage 只将这 256 个完整 current-unknown 字节新增为
  `battle_gameplay_sound_selector_table`。合同不声明自然全索引/全路径可达、computed/
  RAM/indirect 消费者穷尽、所有 selector consumers 穷尽、零/非零或 gameplay 值语义、
  左邻结构关系、右邻业务关系、完整播放例程、播放成功、音频资源穷尽、编辑/写回/
  重定位或 free/allocatable space。
  接入后 classified 6,116,392 / 6,291,456（97.2174%），unknown 175,064
  （2.7826%）、claim 14,310、segment 16,402；coverage/auditor/proof SHA-256 分别为
  `6af3216caf853045b0590389a11abf161e4e489a183f308d940db9e64a67e9b7`、
  `6a2da86067afbb413a355df4d70e4b13b039dd0c213fff47fce5bed4b66107b4`、
  `d235fb19024e62b7f6c7bf6e7c62935e6422e93f3940574c8730034fac8c7ca3`。
  正式审计执行 71 个唯一结构化 contract，71/71 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 61/61、bad=0、175 blockers；proof spec 另配置
  11 个仅哈希绑定的旧 gate verifier，故 gate 配置总数为 72。report/guard SHA-256
  分别为 `6fc14885e20e4e63600d2f04130678cbe16f011d85ae2cb58f8968f36b3706c3` /
  `fad0d92819377e6b16cccd6cbbbe8967c7d4eb0ef15b482fdb6bf170be0b3140`，峰值 RSS
  648.578125 MiB。报告保持 `complete=false`、`claim_status=incomplete`；Goal
  继续 active，全局语义覆盖仍未完成。
- 2026-08-23：固定 battle-condition records 已完成 artifact、coverage、proof 与
  formal 合同。`rom-battle-condition-records-v1` 独立重建完整 47 battles × 3
  variants × `0x44`-byte 物理表、1,128 predicate slots 及 raw interpreter layout；
  coverage 只提升接入前 current-unknown 的 84 个 fragment，共 2,772 bytes：41 个
  variant-prefix fragment / 164 bytes 与 43 个 predicate fragment / 2,608 bytes。
  既有 fixed-table 和 positions-aux primary owner 保持不变，右侧
  `[0x00596CCC,0x00596D5C)` 的 144-byte zero gap 继续 unknown；不声明自然 battle/
  variant 可达、全消费者穷尽、prefix/predicate 业务语义、handler 4/5 自然使用、
  编辑/写回/重定位或 free/allocatable space。
  接入后 classified 6,119,164 / 6,291,456（97.2615%），unknown 172,292
  （2.7385%）、claim 14,394、segment 16,483；coverage/auditor/proof SHA-256 分别为
  `dd2a64883da6a5b561336a70d90ceb97a6ca7eb282b3bd09b0f3ec2d9ed0d156`、
  `b81ea9a433d19fe9d64068f79f4ca692ab70764715f22ded46c64e2a6f508039`、
  `a6032881de87c4faa045fbc5fb15b05043a1971da24a748114da70603f6074b3`。
  正式审计执行 72 个唯一结构化 contract，72/72 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 62/62、bad=0、175 blockers；proof spec 另配置
  11 个仅哈希绑定的旧 gate verifier，故 gate 配置总数为 73。report/guard SHA-256
  分别为 `15191084bcf75fa7908708f25d69cb436cd36f99b4815eeecc2926c64c4c8b41` /
  `3aeef7dc59c22f965b567641419b27d773cc61fbb30a0abba8f95c6d5caf135f`，耗时
  2,828.498 秒、峰值 RSS 623.84375 MiB。报告保持 `complete=false`、
  `claim_status=incomplete`；用户已要求在此里程碑暂停，Goal API 状态仍为 `active`，
  收到明确恢复指令前不得继续新逆向写入。
- 2026-08-23：CFG proven-roots v10 已完成标准受管 promotion、coverage、proof 与
  formal 合同。固定全 ROM 三条 target-limited Thumb BL producer 分母，独立重建
  source bounded worklist 264 instructions / 35 blocks / 580 bytes / 26 external call
  edges / 0 frontier，以及 `0x08B278` target worklist 36 instructions / 7 blocks /
  72 code bytes / 0 frontier；两条实际 PC-relative LDR 另消费 8 literal bytes。
  coverage 只晋升 7 个完整代码 block 和 2 个完整 literal claim，共 80 个接入前
  current-unknown bytes；不声明自然运行时可达、全局代码图、间接目标穷尽、函数 ABI、
  业务语义、编辑/重定位或 free space。canonical manifest/payload SHA-256 分别为
  `7bc6a70cb8409b44075df6e1031b9d80bdb19898605735dedd2a2acf9d495991` /
  `5edad0689b630e68c6ee304aac2f56e3d5c83e65ee7c2c7a7308e0fd980fd50e`。
  接入后 classified 6,119,244 / 6,291,456（97.2628%），unknown 172,212
  （2.7372%）、claim 14,403、segment 16,492；coverage/auditor/proof SHA-256 分别为
  `c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396`、
  `e440b797a04d8186a854de5d174a46dbcb459e0a0abf515a0249ea4121a23c8f`、
  `75d5e48249a3ee200dd8b741faf2c304e390d74614a25c8a161746300d8017e1`。
  正式审计执行 73 个唯一结构化 contract，73/73 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 63/63、bad=0、175 blockers；proof spec 另配置
  11 个仅哈希绑定的旧 gate verifier，故 gate 配置总数为 74。report/guard SHA-256
  分别为 `0d761f8cdc7d21de305af6295d518981a0b6bafb242e5b4e433c83e5a4aeacda` /
  `915828bb3b01d54c7c7802ca482d6416df07ce2702e7531e0ee17186a7f94822`，耗时
  2,592.267 秒、峰值 RSS 615.17578125 MiB、非降级。报告保持 `complete=false`、
  `claim_status=incomplete`；本手头里程碑已经收尾，现按用户要求停止开启新候选。
- 2026-08-27：CFG proven-roots v11 已完成标准受管 promotion、coverage、proof 与
  formal 合同。对 `0x080633C0` 的全 ROM target-limited raw Thumb BL 分母固定为
  9 条：8 条来自冻结的 tick callback source 闭包，第九条 `0x08080D7C` 明确保持
  `excluded_unproven_source`。独立 verifier 重建 8 个 source root、537 条 source
  instruction、92 个 source block、1,130 个 source 字节、28 条 opaque external
  edge 与 0 frontier；目标闭包为 30 条指令、6 个 block、62 字节、1 条进入既有
  baseline 的 opaque call 与 0 frontier。coverage 只晋升 `[0x0633C0,0x0633FE)`
  的 6 个完整 current-unknown block；第九个 raw match、source/producer、callee 与
  相邻 `[0x0633FE,0x06345E)` 均不重认领，也不声明自然可达、全局 caller/代码/
  间接目标分母、函数 ABI、业务语义、编辑或重定位安全。canonical manifest/payload/
  verifier SHA-256 分别为
  `3c0a4ae64b82a417e0577d28ea82b5f774ea3150d210ed4c117414938bc2b0d4` /
  `4d62230f3477abd29ac24790eb9fc98870c95f79e1da8df4e49783fbf6d18480` /
  `4dbcd849eba9b674ed9e3739e0ce8be278a4347b7c113a98d834ac2e4a82c563`。
  接入后 classified 6,119,306 / 6,291,456（97.2637%），unknown 172,150
  （2.7363%）、claim 14,409、segment 16,498；coverage/auditor/proof SHA-256 分别为
  `4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd`、
  `e6d072de539ecabfec73857d8352435617dd38bf0a0359924e8db71dda8afac4`、
  `acb8bcbd3faf282c40ae2ef807c8f815c95c9aa29ca30a9adcbd892d3c56d1ba`。
  正式审计执行 74 个唯一结构化 contract，74/74 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 64/64、bad=0、175 blockers；proof spec 另配置
  11 个仅哈希绑定的旧 gate verifier，故 gate 配置总数为 75。report/guard SHA-256
  分别为 `9d243886ffed63f211066798f093e796c098d282a83862f11b93da0266478277` /
  `0c3f2995be3220231b53de9642ffbcf5d7eb7dc6eb8ce3e8debffc7a9ced60a2`，耗时
  2,739.024 秒、峰值 RSS 616.70703125 MiB、非降级。报告保持 `complete=false`、
  `claim_status=incomplete`；Goal 继续 active，全局语义覆盖仍未完成。
- 2026-08-27：下一候选 `[0x0059EAE0,0x0059F5F0)` 的旧 `118×24` 假设已被
  负证据拒绝；`0x0859F560` 的三个独立 base consumer 把前段物理上限收紧为
  `[0x0059EAE0,0x0059F560)` / `112×24`，但固定 primary scenario 50 可产生
  `(state+0x16,state+0x19)=(31,30)`，ROM lookup 31 为 90，组合 index 120，否证
  “本地 consumer/caller 自动保证 `0..111`”的命题。scheduler callback 首入/续入
  生命周期仍未闭合，所以既不接入 2,688 字节，也不宣称自然玩法 OOB；unknown 保持
  172,150。可复核边界、raw 分母、固定脚本反例与恢复条件见
  `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md`。
- 2026-08-27：固定 u8-indexed u16-pair lookup 与 boot Thumb handoff CFG 已完成
  canonical artifact、coverage、proof 和 formal 合同。lookup artifact 只把逻辑
  256 cells / 1,024 bytes 中仍属 current unknown 的前缀
  `[0x0059F560,0x0059F5F0)` / 144 bytes 晋升为 1 个 primary claim；后续
  `[0x0059F5F0,0x0059F960)` / 880 bytes 继续由 44 个既有 selector-direct-source
  owner 持有，不重复分类。boot artifact 从固定 Thumb handoff roots 独立重建
  125 blocks、583 instructions、1,226 code bytes、296 literal bytes、14 returns 和
  2 indirect frontiers；coverage 只接入 27 个 code claim 与 22 个 literal claim，
  精确 union 为 25 ranges / 1,522 bytes，wide envelope 与 frontier 保持 unknown。
  两项合计净消除 1,666 unknown bytes；接入后 classified 6,120,972 / 6,291,456
  （97.29022979736328%），unknown 170,484（2.70977020263672%）、claim 14,459、
  segment 16,568。coverage/auditor/proof SHA-256 分别为
  `9ed94f7cab667383c136b6fdb11132d077329f8f6a67b74871ce32f4038b3529`、
  `b9bb12d1aeed440b2dae3fc2eed0a699d9e35f95519fb028001f9f426c9cae4e`、
  `ca2afde1b83177f1bf3e503a72c22729070915d7c262bd3b0b96e1c424c7334d`。
  正式审计执行 76 个唯一结构化 contract，76/76 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 66/66；report/guard SHA-256 分别为
  `bc598b5a1f13547e80c35b0b765c9cea0cf89bb4a344a1bd69e04c049cf01eb8` /
  `3330400830e5234b076e49f7a11b70c69c93b0b7457e3ea5acdbd8e550370c24`，耗时
  2,754.867994 秒、峰值 RSS 627.62109375 MiB、非降级。报告保持
  `complete=false`、`claim_status=incomplete`；Goal 继续 active。
  后续 Luna max compatibility gate 已拒绝把 `[0x00596CCC,0x00596D5C)` 的
  144 个全零字节称为 character-id 0 预偏行：现有证据没有 producer/caller 证明
  ID 0 属于合法域，因此该范围仍保持 unknown，不能仅凭全零晋升。
  同一门禁也拒绝 `[0x000000C4,0x000000C8)` 的 4-byte boot gap：固定 handoff chain
  只证明局部绕过，没有该地址的完整 target-limited inbound producer 分母；原始 word
  不能外推为 global-unreachable、NOP、padding 或 free space，故同样保持 unknown。
- 2026-08-27：`0x59EAE0` scheduler callback lifecycle gate 已完成并正式
  `REJECT / 0 bytes`。raw ROM 独立重建确认 `0x08061D7C` 恰有 8 个直接注册点，
  11 个 wrapper 经 `0x08061C58 → 0x0809C114/BX r1` dispatch，返回后由
  `0x08061E00` 清理；`0x0808F73C` 与 `0x0808EF2C` 仅在该结构意义上闭合。
  `0x0808F654` 仍无 raw direct branch 或精确 Thumb pointer，computed/RAM/indirect
  producer frontier 未闭合，所以 Task 2/3 停止、2,688 bytes 继续 unknown，coverage
  仍为 classified 6,120,972 / unknown 170,484。report SHA-256 为
  `1638ab9dab45800256fd921e950ef53600f6f592a05f39842b26bfbd7a983ec2`；
  定向测试 4/4 通过，Sol medium P0/P1 复核 ACCEPT。下一候选优先复用本 gate 已冻结的
  通用 task scheduler code/literal 精确窗口，先经 Luna max compatibility gate，不能
  把 hash-only window 直接晋升为 code。
- 2026-08-27：上述通用 task scheduler 精确窗口已作为独立 R4 工作包完成标准
  promotion、coverage、proof 与 formal 合同，不再是候选。canonical artifact 位于
  `artifacts/rom-task-scheduler-core-v1/`，manifest/payload/binary/verifier SHA-256
  分别为 `88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c`、
  `298dc0cf30765e0afe33487f92cce231bd76d4056719f825c1c9cef98d12a59d`、
  `2cdbf5ee8ee1f24e9d5590363f05cf177c21821209d8b735666b4844c829842f`、
  `90133f94b749dbd3d2d08404ac3be5a7a275f261076c82c8c01312271760d9f4`。
  独立 raw-control-flow verifier 重建 116 条 Thumb 指令、33 个 block、33 条内部
  edge、5 条外部 edge、4 个外部 target、1 个显式 frontier、12 个 return，并只晋升
  4 段 code / 264 bytes 与 3 段实际消费 literal / 44 bytes。138 个已有 owner 字节只作
  provenance，三个两字节间隙继续 unknown；动态 callback 目标/生命周期、自然可达、
  全局 caller/code/indirect 分母、业务语义、编辑、重定位及 allocatable space 不声明。
  接入后 classified 6,121,280 / 6,291,456（97.2951%），unknown 170,176
  （2.7049%）、claim 14,466、segment 16,577。coverage/auditor/proof SHA-256 分别为
  `5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f`、
  `491de8204291f0e41cc4aadb23fbacc54e76cd2435cf52b4274f0fd9b3c32973`、
  `6fd1fc01e7e52d44510ba66f7d83c5ef64f2d07b27a30554047e87929db955e5`。
  正式审计执行 77 个唯一结构化 contract，77/77 均 `exit_code=0`、
  `contract_ok=true`，ROM byte gate 67/67、bad=0；report/guard SHA-256 分别为
  `d975366d63c35c6a62f4e41d9199014828e689273d2d882f43188df519477c9e` /
  `e2ae0a75f524e70634b1a318d719e26c6591b4d789d995fb2bb839dd6d34ddc3`，耗时
  2,891.251353 秒、峰值 RSS 646.03125 MiB、非降级。报告正确保持
  `complete=false`、`claim_status=incomplete`、175 blockers。
- 2026-08-27：R4 后续候选按只读筛选的风险/收益顺序冻结为：DirectSound pitch
  lookup（最多 318 bytes：`[0x09A998,0x09A9F2)` 90-byte Thumb consumer、
  `[0x4645C4,0x464678)` 180-byte u8 scale、`[0x464678,0x4646A8)` 48-byte
  12×u32 frequency table）；PSG noise lookup（最多 220 bytes：
  `[0x09B494,0x09B534)` 160-byte consumer 与 `[0x46475C,0x464798)` 60-byte
  table）；MPlayMain scheduler（最多 414 bytes，`[0x09A42C,0x09A5CA)`）；
  SoundMain mixed-ISA relocated code source（最多 926 bytes，
  `[0x099E10,0x09A1AE)`）；最后才是 `[0x53DFB0,0x53E000)` 的 80-byte object。
  前两项复用“固定直接分支 producer + 确定性索引表”脚本模式：先闭合 target-limited
  producer、raw Thumb CFG/load bounds 与完整 key/fine/index 域，合同冻结后才允许 Luna
  max 小包；MPlayMain/SoundMain 必须先由 Sol/Codex 处理 callback/搬运边界。不得重开
  已 REJECT 的 `0x596CCC..0x596D5C`、`0xC4..0xC8` 或 scheduler lifecycle
  `[0x59EAE0,0x59F560)` 假设。
- 2026-08-27：上述 DirectSound pitch lookup 候选已由实际 344-byte 合同取代旧
  318-byte/90-byte 估计，并完成 canonical artifact、coverage、proof 与 formal
  验收。`artifacts/rom-directsound-pitch-lookup-v1/manifest.json` SHA-256 为
  `61f58bd4309d3b63389bdd09ddd62281dee6fe6ce91bcce0c351ce703012805d`；
  payload/binary SHA-256 分别为
  `ea54c37199704e58f4fcfb0c7dccf3227a23c6363692a4f238ebd807a8003d85` /
  `cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850`。
  五个 primary claim 精确覆盖 16-byte high32 interwork helper、92-byte closed Thumb
  consumer、8-byte consumed literals、180-byte scale descriptors 与 48-byte
  twelve-entry frequency table。两个 target-limited raw BL producer 仅作 provenance，
  producer bytes/source membership 不晋升；自然运行时、全局 caller/code/indirect
  或 computed/RAM consumer 分母、播放行为、编辑、写回、relocation 与 allocatable
  space 均未声明。接入后 classified 6,121,624 / 6,291,456（97.3006%），unknown
  169,832（2.6994%）、claim 14,471、segment 16,582；coverage SHA-256 为
  `922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6`。
  proof spec/report/guard SHA-256 分别为
  `cf242a73211f4cda07a70c6c3bc0f59d8f5a9c995334d9fecd6bf6b808df2c0a`、
  `9ff9072dc1e501bd6bef9f792f6a318640ea9b8594719effa514288595d4714e`、
  `eadf80d080f795495304028e9ee8f4074a1ff34e768571e7152b917b278fe133`；
  78/78 个唯一结构化 contract 全部通过，ROM byte gate 68/68、bad=0，正式报告
  正确保持 `complete=false`、`claim_status=incomplete`、175 blockers。
- 2026-08-27：下一优先包改为 PSG noise lookup 的最多 220 个 current-unknown
  字节：consumer `[0x09B494,0x09B534)` 160 bytes 与 table
  `[0x46475C,0x464798)` 60 bytes。已有 m4a PSG 消费者与运行时证据只能作为输入；
  仍须先由脚本闭合 target-limited producer 分母、raw Thumb CFG/literal 及完整
  key→index 0..59 域。合同冻结后才适合 Luna max 实现；任一 indirect/computed
  producer、frontier 或索引域缺口都必须保留 unknown。
- 2026-08-28：上述 PSG 候选已由实际 226-byte 合同取代，并完成 canonical
  artifact、coverage、proof 与 formal。`rom-psg-frequency-lookup-v1` 的五个
  promotion range 精确覆盖 154-byte bounded Thumb code、12-byte consumed
  literals 与 60-byte noise descriptor table；两字节对齐间隙保持 unknown。
  接入后 classified/unknown/claim/segment 为
  6,121,850 / 169,606 / 14,476 / 16,589（97.3042% / 2.6958%），coverage SHA-256
  为 `5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89`。
  正式 report/guard SHA-256 为
  `41f25e7c10aa32136f676145b2191a18245d2205ac888a300c8139890b06e670` /
  `dcb342bcfaa4b6ad5ddd523fda985e7cef5389427efaadc55f8cf3df0f94edaa`；
  79/79 唯一结构化 contract 通过，ROM byte gate 69/69、bad=0，报告正确保持
  `complete=false`、175 blockers。
- 2026-08-28：19-byte fixed-consumer u8 triplet lookup 已完成：只晋升
  `[0x075C0C,0x075C10)` 的唯一 pointer literal 与 `[0x53DFB0,0x53DFBF)` 的
  5×3-byte raw record；272-byte consumer code 保留 generic CFG owner，四段 literal
  pool 与右侧 65 bytes 保持 unknown。随后又以独立 artifact-bound verifier 闭合
  `[0x061D62,0x061D64)`、`[0x061D7A,0x061D7C)`、
  `[0x061DEA,0x061DEC)`、`[0x09B4C6,0x09B4C8)` 四段 align4 gap，共 8 bytes、
  4 claims；verifier/report SHA-256 为
  `befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
  `344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`。
  canonical coverage 保持 SHA-256
  `17aa05ec2919606ac4728106daf08b3d06a033ccd3c723dc17fd7ad1bdec9ad0`，统计为
  6,121,877 / 169,579 / 14,482 / 16,591。受守卫正式审计 81/81 contract 全部
  通过，ROM byte gate 71/71、bad=0；report/guard SHA-256 为
  `7afcf333d39951dbe887fcea7f539bc4c70470d20ed986fd93439fefe9410d63` /
  `bff0680e5dbf6fefbaa7aad71b1b44105203d98f92e9d011138b3b713f64d10c`。
  报告仍为 `complete=false`、175 blockers，不能据此宣称 100%。
- 2026-08-28：修正版 MPlayMain 已完成。旧 414-byte 包络因可达分支逃逸而作废；
  canonical artifact 只晋升 `[0x09A42C,0x09A684)` 的 600-byte bounded Thumb code
  与 `[0x09A688,0x09A694)` 的 12-byte consumed literals。两字节
  `[0x09A684,0x09A686)` 保留既有 `BX r3` owner，
  `[0x09A686,0x09A688)` 继续 unknown。独立 worklist 固定 289 instructions、
  81 blocks、117 internal edges、12 external edges、4 literal refs/3 words、1 frontier
  与 1 return；packed/range-vector SHA-256 分别为
  `8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955` /
  `a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d`。
  可复现 core 脚本由本体 TDD 实现，Sol medium 只读审查错误包络与 owner 边界，合同
  冻结后 Luna max 仅实现 immutable bundle wrapper；最终由本体接入 coverage/proof。
  canonical classified/unknown/claim/segment 为
  6,122,489 / 168,967 / 14,484 / 16,593（97.3143% / 2.6857%），coverage SHA-256
  `2b93df18a7815cb966dad707dfa2ad606049911ae1772a341b57cf2347b58e3b`。
  正式 report/guard SHA-256 为
  `34c390e98f367a2e885700fe95db32db9a2736ae8669cfe139524c576d2d9e1d` /
  `8ed618bc7b648046cb3c01f3ca3b009f31143b6b74a1bb99a6bf43711de2d906`；
  82/82 唯一结构化 contract 通过，ROM byte gate 72/72、bad=0，报告正确保持
  `complete=false`、175 blockers。证据见 `notes/rom-mplaymain-scheduler-20260828.md`。
- 2026-08-28：SoundMain relocated mixed-ISA source 已完成。`rom-soundmain-relocated-cfg-v1`
  只晋升 916-byte mixed ARM/Thumb code 与 8-byte consumed literals；既有 2-byte
  return veneer 保留原 owner。三个 2-byte align4 gap 由独立 boundary verifier 后续
  分类，累计净晋升 930 bytes。canonical classified/unknown/claim/segment 为
  6,123,419 / 168,037 / 14,493 / 16,600（97.3291% / 2.6709%）；coverage SHA-256
  `31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563`。
  正式 report/guard SHA-256 为
  `d2e265e4c7ddc3148eeaa877772246a4944b53f1bfc75c8c97fc99ca5826f8b1` /
  `edf30aa3feb13ba7500973c2ecad10a2f7f2c3bfb9c1f47d6f3d4d6d5c48c084`；
  84/84 唯一结构化 contract 通过，ROM byte gate 74/74、bad=0，报告正确保持
  `complete=false`、175 blockers。完整边界见
  `notes/rom-soundmain-relocated-cfg-20260828.md`。
- 2026-08-29：`rom-m4a-initializer-chain-v1` 已完成 canonical artifact、coverage、
  proof 与 formal。六个 promotion range 只包含 `m4aSoundInit`、PSG initializer、
  MPlayOpen 的 390-byte bounded Thumb code 与 128-byte consumed literals；三 root
  的 raw producer 分母分别为 `[0x061E28]`、`[0x09AA56]`、`[0x09AA76]`。第一个
  producer 4B 仍 unknown，只作 unpromoted provenance；`[0x09B1E6,0x09B1E8)` gap
  也保持 unknown。接入后 classified/unknown/claim/segment 为
  6,123,937 / 167,519 / 14,499 / 16,608（97.3374% / 2.6626%），coverage SHA-256
  `ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27`。
  正式 report/guard SHA-256 为
  `8f6761d5f19cb9142caf5338971c4b1712aebf32f6f9cb08d98196b3d4d84c3e` /
  `172d4a028aba3bfef2ca9ce9eeef9da8c07bbcf191e3fbe9424774a3a3e03628`；
  85/85 唯一结构化 contract 通过，ROM byte gate 75/75、bad=0，报告正确保持
  `complete=false`、175 blockers。下一首选是四段合计 562-byte 的 MP2K note
  allocator/channel-gain closure；必须先由本体冻结 producer、CFG、literal 与单一
  entry-pointer writer/consumer/domain 分母，冻结后才适合 Luna max 短包。再后才是需本体
  拆分的 `[0x09B53C,0x09BCE4)` 1,960-byte CGB/PSG callback 包络。
- 2026-08-29：`rom-mp2k-note-allocator-v1` 已完成 canonical artifact、coverage、proof
  与 formal。只晋升 `[0x09A6D8,0x09A708)`、`[0x09A708,0x09A8FE)`、
  `[0x09A900,0x09A908)`、`[0x09AF24,0x09AF28)` 四段，共 550-byte bounded Thumb
  code、8-byte consumed literals 与 4-byte initializer-consumed entry pointer；
  `[0x09A6D2,0x09A6D8)`、`[0x09A8FE,0x09A900)`、
  `[0x09AEF4,0x09AF24)`、`[0x09AF28,0x09AF34)` 合计 68 bytes 保持 unknown。
  独立 worklist 为 269 instructions、66 blocks、99 internal edges、5 external edges、
  2 returns、0 frontier，consumer command 域固定为 0..48。接入后
  classified/unknown/claim/segment 为 6,124,499 / 166,957 / 14,503 / 16,614
  （97.3463% / 2.6537%），coverage SHA-256 为
  `3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735`。
  canonical manifest / payload / binary SHA-256 分别为
  `a2f61cb3596c8e48294ba07c710a2681bbe8ca8173c6d9288beccd5dd3e1cf8a`、
  `a4ccf706d2c8db658b6fa402d13155c73d15e84c197f9da4e8975759a14b0fa6`、
  `3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c`。
  formal report/guard SHA-256 为
  `46b4b0c9b80b7ef2d8eaff9fb0572370c315d47baa05290d4fb2da327a95e7ce` /
  `7a69b38343c8a1b68392368cd0b130d6817b888fa3b3c90cf445a7d05e54adaa`；
  86/86 实际结构化 contract 全通过，ROM byte gate 76/76、bad=0，报告正确保持
  `complete=false`、175 blockers。下一包改为 102-byte MP2K 18-entry dispatcher
  additive delta；不得修改历史 candidate-027 的 rejected 状态，也不得把两个 2-byte
  gap 或整个 1,960-byte CGB/PSG 包络一并晋升。证据见
  `notes/rom-mp2k-note-allocator-20260829.md`。
- 2026-08-29：`rom-mp2k-dispatcher-v1` 已完成 canonical artifact、coverage、proof
  与 formal。四个 primary claim 只净晋升 `[0x09BCB4,0x09BCE2)` 的 46-byte root
  code、`[0x09BD24,0x09BD30)` 的 12-byte table tail、
  `[0x09BDC4,0x09BDEC)` 的 40-byte handler code 与
  `[0x09BDFC,0x09BE00)` 的 4-byte consumed literal，共 102 bytes。五段既有 owner
  共 238 bytes 只作 provenance；两个 2-byte gap 保持 unknown，历史
  `candidate_027` 的 rejected 状态未改写。完整 bounded CFG 固定为 129 instructions、
  260 code bytes、36 blocks、65 internal edges、1 external edge、1 return、0 frontier
  与 18 条 dispatch edge。接入后 classified/unknown/claim/segment 为
  6,124,601 / 166,855 / 14,507 / 16,617（97.3479% / 2.6521%），coverage
  SHA-256 为
  `22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839`。
  正式 report/guard SHA-256 为
  `3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0` /
  `b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`；
  87/87 唯一结构化 contract 全通过，ROM byte gate 77/77、bad=0，报告正确保持
  `complete=false`、175 blockers。下一批合并冻结 `[0x09B53C,0x09B5F4)` 的两个
  CGB helper 与 `[0x09B5F4,0x09BA3E)` 的 `CgbSound` bounded closure；共享同一
  immutable precoverage，再统一接入 coverage/proof，禁止扩张到整个 1,960-byte
  包络。证据见 `notes/rom-mp2k-dispatcher-20260829.md`。
- 2026-08-29：CGB helper、CgbSound 与统一 artifact-bound gap 接入已完成。
  `rom-cgb-helper-bounded-cfg-v1` 只晋升 164-byte bounded Thumb code 与 16-byte
  consumed literals；`rom-cgbsound-bounded-cfg-v1` 只晋升 1,008-byte bounded
  Thumb code 与 76-byte consumed literals；13 段独立边界 gap 共 26 bytes。
  本批净增 1,282 bytes、37 claims、37 segments，canonical
  classified/unknown/claim/segment 为
  6,125,883 / 165,573 / 14,544 / 16,654（97.3683% / 2.6317%），coverage
  SHA-256 为
  `05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6`。
  双 artifact 的 manifest/payload SHA-256 分别为
  `8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1` /
  `dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960`
  与 `4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e` /
  `362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d`。
  formal report/guard SHA-256 为
  `613cee1f8c72882aebe6ffaf617fc2fa1ea556ca9235f9f78607132dd189a567` /
  `7515d1e4c9a47f6508209a17747992e4219619075ada9f6a8766bb9045315e7a`；
  88/88 个唯一结构化 contract 全通过，ROM byte gate 78/78、bad=0，报告正确保持
  `complete=false`、175 blockers。余下 630-byte 连续包络不得整体分类。虽只读扫描
  在 `0x061F14` 找到唯一可解码为指向 `0x09BA68` 的 raw Thumb `BL`，其 source
  自身仍位于 unknown，尚无已证明 CFG/table/callback membership，因而不能据此把
  100-byte target 与 4-byte literal 晋升为 code/root。该草案已在 GREEN 前停止；
  104 bytes 与其余 526 bytes 均继续 unknown，只有先闭合 source membership 才可重开。
- 2026-08-29：CFG proven-roots v12 immutable bundle、coverage、proof 与 formal 已完成。
  唯一已证明 producer 为 `0x08061416 -> 0x08064478`；目标只晋升四段闭合 Thumb
  code 共 372 bytes 与四段指令实际消费 literal 共 128 bytes，合计 8 claims / 500
  bytes。`[0x0644C2,0x0644C4)` 与 `[0x06450A,0x06450C)` 两个 2-byte hole 继续
  unknown，source/producer 保留既有 owner。canonical classified/unknown/claim/
  segment 为 6,126,383 / 165,073 / 14,552 / 16,665（97.3762% / 2.6238%），
  coverage SHA-256 为
  `96fba5e10bbef80eb0326e7dd85d07babdcffb63674a0fecd046c8b9edc427eb`。
  formal report/guard SHA-256 为
  `961ace784373243954097418880fdbf52419385b2e34f62a136f7920b032306a` /
  `53546d31216f134a9e22cddfb79fb2e01cd9642e494e4429eb0b2ebe4e6ab0eb`；
  89/89 个唯一结构化 contract 全通过，ROM byte gate 79/79、bad=0，报告正确保持
  `complete=false`、175 blockers。该包不声明自然运行时可达、全局 caller/code/
  indirect/computed target 分母、literal 业务语义、编辑、写回、重定位或可分配空间。
- 2026-08-30：CFG proven-roots v13 immutable bundle、coverage、proof 与 formal 已完成。
  固定目标 `0x080651F8` 的全 ROM target-limited 直接 producer 分母只有
  `0x080614D0` 一条已证 source Thumb BL；目标只晋升三段闭合 Thumb code 共
  312 bytes 与三段指令实际消费 literal 共 80 bytes，合计 6 claims / 392 bytes。
  `[0x0652DE,0x0652E0)` 与 `[0x06536A,0x06536C)` 两个 2-byte hole 继续
  unknown；`0x065368 bx r0` 保持唯一 unresolved indirect-PC frontier，不能称为
  structured return。immutable wrapper 在动态加载 legacy verifier 前后都独立锚定
  运行时依赖。canonical classified/unknown/claim/segment 为
  6,126,775 / 164,681 / 14,558 / 16,673（97.3825% / 2.6175%），coverage
  SHA-256 为
  `e8787f8e200e84b2966c6f6b8c70ea164a0f90d81348d88e5daa614ea3cb8004`。
  formal report/guard SHA-256 为
  `6bced154df1d4ca3940f597f64ef36bb5ebd8c3f9d995f62fce34ad92b8793c2` /
  `23893d0b4996fac334cc4b93596e1e3a28ee5cc7302636c5abd5b8b34037d369`；
  90/90 个唯一结构化 contract 全通过，ROM byte gate 80/80、bad=0，报告正确保持
  `complete=false`、175 blockers。该条是冻结的 V13 历史快照；其旧 CFG 汇总字段已
  被后续综合 registry 取代，不得当作当前全局 aggregate。
- 2026-08-30：CFG proven-roots v14 immutable bundle、canonical coverage、综合 CFG
  registry 修正、proof 与 formal-r2 已完成。五条 V12/V13 accepted producer 证明
  `0x0624C0` 与 `0x062510` 两个根；只晋升 120-byte Thumb code 与 40-byte consumed
  literals，共 4 ranges / 160 bytes、60 instructions、10 blocks、0 hole。
  `0x0624FE bx r0` 与 `0x062546 bx r0` 保持两个 unresolved indirect-PC frontier。
  manifest / payload / coverage SHA-256 分别为
  `666772f43529a5578414c5b749e16ea8733a755a0a818e86cea81bd86d57091d`、
  `d99c0cdc367637b62754b941926e22d09bef08f9a3e89817fbf42dafc0a7edff`、
  `2592ce481515af301ef5ce4078d3e9101793bf790f1bc90a6d33d5a06c207317`。
  canonical classified/unknown/claim/segment 为
  6,126,935 / 164,521 / 14,562 / 16,677（97.385009% / 2.614991%）。综合 registry
  将 V14 当时的 bounded-CFG 汇总修正为 ARM 956、Thumb 148,380、producer 32、promoted
  149,368 bytes、3,829 claims、32 code kinds，registry SHA-256 为
  `d57f6b22f597eb6cfcad6a746122870917fbc24b0e70a885a432a57c729a227f`。
  formal-r2 report / guard SHA-256 为
  `f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786` /
  `3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`；
  91/91 contract、ROM byte gate 81/81、bank contract 10/10 全部通过，报告仍正确为
  `complete=false`、175 blockers。formal-r1 的旧 aggregate 已被 r2 取代。
  后续 V15 只对五个 source-bound roots 做 root-isolated preflight；864-byte
  root-forward unknown ceiling 不是 promotion 估计，`0x08B644→0x08ACC8` 因缺少
  accepted source membership 已排除。该后续工作已由下一条完成记录取代。
- 2026-08-30：CFG proven-roots v15 已完成独立 preflight、TDD、canonical artifact、
  dependency-first immutable bundle、coverage、proof 与 formal-r2。接受
  `0x0611F4`、`0x0618FC`、`0x08B6F0`、`0x09A3E0` 四根，拒绝 `0x09C0F4`；
  只晋升 398-byte Thumb code 与 52-byte consumed literals，共 10 semantic ranges /
  7 union ranges / 450 bytes、197 instructions、31 blocks。三个 indirect-PC frontier、
  六段合计 386-byte holes 与 rejected range 继续 unknown。manifest / payload /
  coverage SHA-256 分别为
  `7fb00210d8347df1935d6997afa66183d6cbaa4d7d26208f744256e09f11755f`、
  `5786c04ae36d78957705175dfce38da190bb29682c640c6821bb44ec4c321cd2`、
  `c76ac479b6798b856ff839b9f9388f537f912247481ee06ff53ad52c504624c9`。
  canonical classified/unknown/claim/segment 为
  6,127,385 / 164,071 / 14,572 / 16,693（97.392162% / 2.607838%）；综合 CFG
  registry 为 ARM 956、Thumb 148,778、producer 32、promoted 149,766 bytes、
  3,835 claims、33 code kinds，registry SHA-256 为
  `10ae3cc720e787630957b7c7bbbbae379ec5f3e542dbabeb871df861915a676b`。
  formal-r2 report / guard SHA-256 为
  `3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63` /
  `b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`；
  92/92 contract、ROM byte gate 82/82、bank contract 10/10、bad=0，报告仍正确为
  `complete=false`、177 blockers。formal-r1 的两项环境合同失败已由隔离 env TDD
  修复和 r2 取代。该条保持为 V15 历史收据；后续 menu-gap 结果见下一条。
- 2026-08-30：menu portrait LZ77 endpoint→palette 起点的短零对齐间隙已完成
  preflight、Luna max 小包 TDD、父代理变异验收、canonical coverage、proof 与 formal。
  独立 verifier 从 896 条 pointer-reachable LZ77、74 个菜单资源和 70 段物理 palette
  分母重建 52 段 / 110 bytes，长度分布 16×1、14×2、22×3；每段逐字节为零、紧邻
  两侧 owner 且右端 align4。range / boundary / packed SHA-256 分别为
  `e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7` /
  `13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb` /
  `f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5`。
  canonical classified/unknown/claim/segment 为
  6,127,495 / 163,961 / 14,624 / 16,693（97.393910% / 2.606090%）；coverage /
  proof SHA-256 为
  `c2798b35f4ac21f170c9a7575cbf10118aad98d58efbebf3d59ca9f599216133` /
  `eaa8b7f2b37feaa9686d83c84f6fd16672e6b6ae3038e0ccf16ece96c4698eb2`。
  formal report / guard SHA-256 为
  `92b4b471b972bcc789848f78192f8c5162deeeb0ab0c1bce77e818694e88ba3a` /
  `e0985d49922e2473229c8c28c4182013e9497718977e07807a52885e76b2b66e`；
  93/93 个去重后的实际命令、ROM byte gate 83/83、bank contract 10/10 全部通过，
  bad=0，耗时 3,385.228261 秒，峰值 RSS 680.0625 MiB、非降级。报告保持
  `complete=false`、177 blockers。
- 2026-08-30：tile-BG LZ77 endpoint→palette source 的短零对齐间隙已完成
  script-first preflight、Luna max 小包 TDD、父代理两项语义补强、165-byte mutation、
  canonical coverage、proof 与 formal。独立 verifier 从 896 条 pointer-reachable
  LZ77、79×68 descriptor、236 个 palette entry、108 个 raw range / 107 个 merged
  claim 重建 84 段 / 165 bytes，长度分布 31×1、25×2、28×3。range / boundary /
  packed SHA-256 分别为
  `684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2` /
  `b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448` /
  `2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d`。
  canonical classified/unknown/claim/segment 为
  6,127,660 / 163,796 / 14,708 / 16,693（97.396533% / 2.603467%）；coverage /
  proof SHA-256 为
  `1ddc10027b7642399bce8c1a07871ce3a141ca6f2b323c19a650469274cb2df4` /
  `b7423201e3f84280c5556d8d42b95de6c03c07fefcfc85f3d05bf71d5c614c57`。
  formal report / guard SHA-256 为
  `37ef4055b419cb520e3bbaf953ca81f3ae72fdc2613032235498ec298dc87832` /
  `7d7fd44829fa1359c619182f2103b3856d359a63dc6f143113a10eb850592779`；
  94/94 个实际唯一命令、ROM byte gate 84/84、bank contract 10/10 全部通过，
  bad=0，耗时 3,263.08749 秒，峰值 RSS 692.83984375 MiB、非降级。报告保持
  `complete=false`、177 blockers；两个非零 long gap 与七个 heterogeneous short gap
  均正确留在合同外。
- 2026-08-31：boot Thumb code→consumed-literal 的 12 段 / 24-byte 冻结对齐边界包
  已完成。独立 verifier 从 `rom-boot-thumb-handoff-cfg-v1` 的完整 27 code range / 22
  literal range / 77 binding 分母投影全部正长度邻接，并从 raw ROM 重解 6 个直接跳转、
  5 个严格返回和 1 个间接 terminal；12 段均为 2-byte `0000` align4 boundary。
  canonical classified/unknown/claim/segment 为
  6,127,684 / 163,772 / 14,720 / 16,693（97.396914% / 2.603086%）；coverage /
  proof SHA-256 为
  `7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a` /
  `6ff897133f1d89d62d214ed23434baad1d04c9df0468db639a6eaebc9e33afe2`。
  formal report / guard SHA-256 为
  `b98828aa94f6704cca82bca876b9154f5e950fc1afcd2df535f7e833f98d00d8` /
  `75afa7d5f183e08f4efb064d7fb0aadcfd4869694643871d7e096b2f8e3fcab0`；
  95/95 实际唯一命令、ROM byte gate 85/85、bank 10/10 全部通过，非降级。
  不改写源 artifact 历史 scope，也不声明全 ROM boot gap、padding、free/allocatable、
  自然可达、编辑或重定位安全。由于最近三个 gap 包合计仅净增 299 bytes，后续改为
  批量聚类 unknown，优先冻结预期净增至少 1,000 bytes 的语义族；几十字节 gap 只并入
  里程碑批次，不再单独触发完整 formal。
- 2026-09-01：首个同信任边界批次里程碑闭合 v2 / proven-roots v6 / proven-roots v1
  的 consumed literal words，分别净增 6,796 / 2,980 / 1,396 bytes，合计 11,172 bytes、
  946 claims 且目标零重叠。canonical classified/unknown/claim/segment 为
  6,138,856 / 152,600 / 15,666 / 17,182（97.574488% / 2.425512%）；coverage / proof
  SHA-256 为
  `66a5e95bd2927f9db13435f6862a052ad60634cfbd3a8b5dfad07459a4a12329` /
  `85962384fda90272f4d89f6ca523b1055b3963725669f4c13c8772faa8a56f5d`。
  formal-r2 的 report / guard SHA-256 为
  `16c49cbb5cc95168b2e20b35b1a2f2fc6155638c5e27db59af1b88eb704143f7` /
  `abf5dcffb1cc326364c860badb15f5a7c29cc16eedff6ec94d5e22147ef2ba9f`；
  98/98 实际 verifier、ROM gate 88/88、bank 10/10 全部通过，非降级。loaded value
  业务含义、自然可达扩张、相邻字节、编辑、重定位和 free/allocatable space 均未声明。
- 2026-09-01：第二个 consumed-literal 批次接入 CFG v3、proven-roots
  v2/v3/v4/v5/v7/v8/v9 合并包、battle-controller CFG 与 v2 shadowed consumer
  slice，净增 3,320 bytes / 274 ranges，四包零重叠。canonical
  classified/unknown/claim/segment 为 6,142,176 / 149,280 / 15,940 / 17,344
  （97.627258% / 2.372742%）；coverage SHA-256 为
  `24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987`。
  非降级 formal report / guard SHA-256 为
  `8ec5119f4f21132721a0727bc4d6caf18a570076bce45093425334b573fe001d` /
  `7458b23dd71a825364bf27f5914bca326615ebb59ff4c94df82837b4b4c19ec3`；
  102/102 实际结构化 verifier、ROM gate 92/92、bank 10/10 全部通过。
- 2026-09-01：四个 accepted consumer-code-slice packet 作为同一批次接入：profile
  selector 164 bytes / 2 ranges、chapter selector 64 bytes / 1 range、generic sprite
  loader tail 36 bytes / 1 range、battle status-bar caller 1,856 bytes / 1 range，合计
  净增 2,120 bytes / 5 claims。canonical classified/unknown/claim/segment 更新为
  6,144,296 / 147,160 / 15,945 / 17,349（97.660955% / 2.339045%）；coverage /
  proof SHA-256 为
  `064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa` /
  `bd634d12c3e3c94c69236648d8d3961898256176cc45f17525862c756b138dd9`。
  本批同时修复后续合法 packet 会触发旧 consumed-literal verifier 历史全局汇总误报，
  并让 formal 复用已经执行的同进程 coverage report，消除同一 coverage 的第二次完整
  重建。去重后 formal report / guard SHA-256 为
  `369c84311c2a753c93b4d7b9868f7752f8d8a9780021264737002b4a7269c80c` /
  `af1a7354baf64a6942a6f37a32015b553e91cdc7675714e3dfcbd5ee47fa4ef9`；
  106/106 实际结构化合同通过，ROM gate 96/96，coverage 合同有且仅有一次
  `reused-in-process`，非降级，耗时 1,965.474851 秒、峰值 RSS 496.792969 MiB。
- 2026-09-01：`rom-event-handler-cfg-v1` 已通过一级快速审计并进入下一批队列，尚未改写
  canonical coverage。固定 512-slot producer 表得到 247 个匹配槽 / 19 个唯一 roots；
  接受 18 roots，拒绝越过冻结边界的 `0x07F064`。独立 raw verifier 复验 1,742
  instructions、3,910 code bytes、152 literal bytes，promotion union 为 4,062 bytes，
  174 bytes holes 保持 unknown。当前正式进度仍为 97.660955%；仅 projection 为
  6,148,358 classified / 143,098 unknown。达到批量门槛前不单独 rebuild/formal。
- 2026-09-01：同批第二个 `rom-sprite-component-source-v1` 已通过一级快速审计，固定
  consumer chain 精确闭合 `[0x12C904,0x12D134)` 的 2,096 bytes：96 个 component
  records、12 个 definition slots、12 个 timeline keyframes、4 个 animation slots；
  consumer code 与相邻 3 bytes 均未晋升。两包累计 projection 为 +6,158 bytes，预计
  6,150,454 classified / 141,002 unknown / 97.758834%；canonical 仍保持 97.660955%。
- 2026-09-01：撤回 positions group47 renderer text `1,022 / 1,710 bytes` 候选。
  独立反汇编确认 `0x06E810` dispatcher 只把 3×16 个 4-byte cells 当作 selector 与
  参数，handlers 只读当前 cell 并调用 `0x081024` battlefield object allocator；8 个
  pointer-shaped cells 的 selector byte 均大于 7，全部 default skip，没有解引用或
  renderer consumer edge。机械 parser 仅得到 8 段 / 146 bytes，旧 1,022 估算是
  `146×7` 的错误乘法；66-byte 零间隙也没有消费顺序证明。该候选不计 coverage，相关
  字节继续 unknown，只有找到真实解引用至 renderer 的冻结链后才允许重开。
- 2026-09-01：同批第三、第四包完成一级快速审计。`rom-cfg-proven-roots-v16` 由 19 个
  已分类 direct Thumb BL producers 证明 15 roots；2 个 unknown-owner 形态命中失败关闭
  排除。父代理 TDD 修复 `0x09C106` SoftReset `svc #0` 的终止语义，避免把随后
  `[0x09C108,0x09C110)` 两个 literal words 错算成代码；最终 369 instructions / 70
  blocks / 778 code bytes。其 consumed-literals 包再独立重解 51 个唯一 word / 204 bytes。
  四包现已统一接入 canonical，净增 +7,140 bytes / 116 claims；authoritative
  classified/unknown/claim/segment 为 6,151,436 / 140,020 / 16,061 / 17,483，
  即 97.77444203694662%。coverage / proof SHA-256 为
  `4e8ab6b090825901ab7b055326e64a6a16343ec95ac33cfe5e0dbe7721eb2440` /
  `9b78c91a30b1150c82b9e213b08087afcaeb8237a3d3365ec5b57c409ae481d7`。
  mutable 历史 coverage 基线已压缩固化并由一个统一 verifier 重放四个原 verifier；
  formal 不再重复单列该 verifier。非降级 formal report / guard SHA-256 为
  `8e6dbd0bb776672ac7927f865fc43b97638091f034b583eb94bd28d5e167104f` /
  `8e09c74bf4212cf735673d9196dfb16530eafcb11eca244c1aeea27da241b81f`，
  106/106 实际结构化合同、ROM gate 96/96 全部 contract-ok；140,020 unknown 与其他
  发布 gate 仍使 proof 正确保持 incomplete。
- 2026-09-01：从 140,020 unknown 重聚类后，合并 `rom-cfg-proven-roots-v17` 包由两个
  已分类 direct Thumb BL 证明 `0x0914D8` root，并在 `[0x091676,0x091FE0)` 精确分类
  2,092 reachable code + 308 closure-wide consumed literal = 2,400 bytes / 26 claims；
  五个 2-byte gap 保持 unknown。canonical classified/unknown/claim/segment 更新为
  6,153,836 / 137,620 / 16,087 / 17,513，即 97.81258900960286%；coverage SHA-256 为
  `23eb0ceaf4d38b8cadb74e05ddf8686de454d5e73c433da26073075d1fa71e78`。
  2,688-byte 112×24 表外观因 index=120 反例与 lifecycle 开放拒绝；736-byte 全零 gap
  因不满足 alignment/parser-bound 合同拒绝。后续继续优先选择能冻结 producer/consumer
  分母且净增至少 1 KiB 的集群，不用全零或表外观填充进度。proof SHA-256 为
  `2110942b50ea9e33592b0f1ce339092fbc1e041c647e343c4e298f69231f80c4`；非降级 formal
  report / guard SHA-256 为
  `9a66f8b2fc5e7840b4226ad306dbd10c68dc4243c5e40cab7927ed84c15eaf3f` /
  `7be0f457a6da35600c868972df77dac384a1bae4d7500e0e2e36f5a691e5ed8d`，
  106/106 contracts、ROM gate 96/96 全部 contract-ok，coverage 仅一次进程内复用；
  137,620 unknown 与其他发布 gate 使 proof 正确保持 incomplete。
- 2026-09-01：`rom-cfg-proven-roots-v18` 以两个 roots 和四条已分类 direct Thumb
  producers，在 `[0x09106C,0x09163E)` 精确新增 1,386 code + 96 consumed literal =
  1,482 bytes / 17 claims；四个 2-byte gaps 与目标外子树继续 unknown。canonical
  classified/unknown/claim/segment 更新为 6,155,318 / 136,138 / 16,104 / 17,533，
  即 97.836144765218%；coverage / proof SHA-256 为
  `984eb8ed8ef72691e1b580b00465d24e1762bb5c0604c35fe76db40153fc42e0` /
  `af16a0e8df448032e2f16a2e984e4df94b1b914bb0444ae9e225a2e0491c9f80`。
  2,460-byte `[0x063ADC,0x064478)` 候选因唯一上游 producer 仍为 unknown 而零晋升。
  非降级 formal report / guard SHA-256 为
  `fc3d2ce85af12f5d26e2703811edd8bf56070c35b7ffac7efa24a4fde1105290` /
  `9f31c62b289e9d127256db543ff264f37f1082be3452d13f0dc410ed55853f69`；
  106/106 contracts、ROM gate 96/96 全部通过，proof 因 136,138 unknown 与其他发布
  gate 正确保持 incomplete。
- 2026-09-01：完成 boot interwork continuation 与 `rom-cfg-proven-roots-v19` 的显式
  依赖 DAG。先证明 `0x06108A` 静态 continuation 的 94 bytes，再以其中唯一
  `0x061092 BL -> 0x065728` 为 producer，分类目标本地 1,600 code + 60 literal；
  总净增 1,754 bytes，六个 2-byte 洞保持 unknown。coverage 审计改为一个通用
  dependency-packet 投影 helper 并一次性原子写入，未减少独立 verifier。
- canonical classified/unknown/claim/segment 更新为 6,157,072 / 134,384 / 16,124 /
  17,557，即 97.86402384440103%；coverage / proof SHA-256 为
  `b51f322d...74008` / `57b62f81...0b45`。formal report/guard
  `f31c5546...fc95` / `73b3d913...89c2` 非降级通过，106/106 contracts、ROM gate
  96/96；proof 仅因 134,384 unknown 与既有发布 gate 保持 incomplete。
- 2026-09-02：接入 `rom-chapter-script-unbound-tail-v1`。固定 slots 45/46 的 8-byte
  pointer vector 与两个无 frontier parser closure 合计净增 3,186 bytes / 3 claims；
  两个 1-byte 边界洞继续 unknown。canonical classified/unknown/claim/segment 更新为
  6,160,258 / 131,198 / 16,127 / 17,559，即 97.9146639506022%；coverage / proof
  SHA-256 为 `3b13c811...9daf` / `fdaef96c...68df`。审计依赖改为 historical reference
  与 auditor current-unknown projection gate 分责，消除 mutable coverage 自失效环；
  formal report/guard `1f3a392b...ef75` / `52e34d3e...a2b6` 非降级通过，106/106
  contracts 全部 contract-ok，proof 因 131,198 unknown 与既有发布 gate保持 incomplete。
- 2026-09-02：接入 `rom-chapter-script-consumer-roots-v1`。两个固定 consumer 通过
  PC-relative LDR、寄存器搬运和同一 parser BL 分别绑定 `0x05CD41` / `0x05D593`，
  两个无 frontier closure 精确净增 16,175 bytes / 2 claims；consumer slices 仅作证据，
  两侧 1-byte / 4-byte 边界继续 unknown。canonical classified/unknown/claim/segment
  更新为 6,176,433 / 115,023 / 16,129 / 17,562，即 98.171758651733%；coverage /
  proof SHA-256 为 `b71a91d...ed52` / `8d6ec4cf...0c96`。coverage 复用声明式
  dependency-packet 投影，formal 不新增重复 verifier；formal report/guard
  `b7ff8d64...a289` / `12b01904...fe9` 非降级通过，106/106 contracts、ROM gate
  96/96 全部 contract-ok。下一步以新 canonical 重聚类 115,023 unknown，继续优先
  冻结预期净增至少 1 KiB 或可解除上游 owner blocker 的 producer/consumer 家族。
- 2026-09-02：`rom-battle-condition-result-text-v1` 通过一级快速审计并进入下一批队列。
  完整 1,128 行物理条件表中的 230 个 active slots，经公共仲裁读取 payload `+4` 并送入
  result renderer/parser；219 个唯一记录精确闭合 3,961 bytes / 219 claims。canonical
  仍为 6,176,433 classified / 115,023 unknown / 98.171758651733%；待合并投影为
  6,180,394 / 111,062 / 98.23471705118814%。由于本批仅 3,961 bytes / 1 packet / +0.063
  个百分点，未达到二级审计门槛，暂不重复运行全量 coverage/formal。2,782-byte 记录间隙、
  `[0x9974,0x9F2E)` 尾部及 positions group47 物理别名均不晋升。
- 2026-09-02：第二个快速 packet `rom-alternate-dialogue-table-v1` 闭合 3,200 bytes /
  161 claims。固定 direct invocation 以 CpuSet 清零 index，逐轮自增，并由
  `0x091E52 CMP #19`、唯一 state-zero write 与 dispatcher backedge 精确消费 rows
  `0..19`，index 20 直接退出；20×20-byte table、80 条 NUL text 与 80 段固定零间隙
  分别为 400 / 1,214 / 1,586 bytes。两包累计投影达到 6,183,594 classified /
  107,862 unknown / 98.28557968139648%，但 +7,161 bytes / +0.113821pp / 2 packets
  仍未达到二级审计门槛，canonical 暂不改写。`[0x45832C,0x458794)` 与 computed/
  indirect root producers 保持开放。
- 2026-09-02：四包快速审计队列达到 `4 packets` 门槛并统一合并。新增
  battle-condition result text 3,961 bytes、alternate dialogue 3,200 bytes、story-state
  callback CFG 702 bytes、callback downstream entry C4CC 220 bytes，共 8,083 bytes /
  395 claims。canonical 更新为 6,184,516 classified / 106,940 unknown / 16,524
  claims / 18,175 segments，即 98.30023447672525%；coverage/proof SHA-256 为
  `e48c8f6d...9c36` / `7efbccde...83e0`。非降级 formal report/guard SHA-256 为
  `6960c095...9cc5` / `b056eddf...8b69`，106/106 contracts、ROM gate 96/96 全部
  contract-ok。`[0x08C5A8,0x08CBB4)` 1,548 bytes 及 callback 四个 2-byte holes 保持
  unknown；下一轮必须基于新 coverage 重聚类，不得复用 `b71a91d1...ed52`。
- 2026-09-02：按新的分层审计规则完成下一批第一包
  `rom-text-bg-loop-continuation-v1`。当前已分类 source owner 证明唯一
  `0x08B644 BL -> 0x08ACC8`，精确闭合 42-byte Thumb code + 12-byte consumed
  literals = 54 bytes / 2 claims；投影为 6,184,570 classified / 106,886 unknown /
  98.30109278361002%。由于仅 1 包、54 bytes、0.000858pp，canonical coverage/proof/
  formal 暂不重建，继续等待批量门槛。`0x08ACF2` 后续与所有自然运行时、业务语义、
  padding/free/edit/relocation 均不外推。
- 2026-09-02：第二个一级快速 packet `rom-boot-copy-sources-v1` 闭合启动复制源
  `[0x0004C8,0x000734)` 620 bytes / 1 claim。唯一 direct producer、完整 9 条 DMA3
  descriptor、两次 CpuSet source/destination/control 均由 raw ROM 独立重建；V12
  destination 已由错误的 `0x03000200` 更正为 `0x03005CE8`。14/14 packet tests、3/3
  quick projection 与独立 verifier 通过。两包累计投影为 +674 bytes：6,185,190
  classified / 106,266 unknown / 98.31094741821289%；尚未达到二级门槛，canonical
  coverage/proof/formal 保持不变。
- 2026-09-02：第三个一级快速 packet `rom-text-bg-task-closure-v1` 通过 callback
  registration→task `+0x28` store→dispatcher `BX r1` 与 direct-call DAG，闭合十个
  Thumb roots。完整重解 1,330 instructions / 2,782 code bytes / 260 consumed-literal
  bytes；扣除 queued 与 canonical owner 后净增 2,940 bytes / 34 claims。9/9 packet
  tests、3/3 quick projection 与独立 raw verifier 通过。三包累计为 +3,614 bytes，
  projected classified/unknown = 6,188,130 / 103,326，即 98.3576774597168%；等待第四包
  后统一里程碑审计，canonical 暂不变化。
- 2026-09-02：第四包 `rom-fixed-renderer-script-records-v1` 从 canonical v2/v3 CFG
  完整重建 41 个 PC-relative literal consumers，并以 bounded register-taint 证明其中
  36 sites 把值送入固定 renderer/parser；五个 opcode 7/8 targets 失败关闭排除，30 条
  unique records 精确晋升 1,124 bytes / 30 claims。Sol medium P1 复核提出的上游身份、
  site denominator 与 r0 数据流缺口均已修复，最终无 P0/P1。
- 2026-09-02：本批四包统一接入后 authoritative canonical 为 6,189,254 classified /
  102,202 unknown / 16,591 claims / 18,261 segments，即 98.37554295857748%；相对上一
  canonical 净增 4,738 bytes / 67 claims / 0.07530848185223pp。coverage / proof
  SHA-256 为 `ff1b9a98...3622b8` / `d615ac45...bc2df`；最终非降级 formal-r2
  `3dcfb9d2...dc86` 达到 106/106 contracts，coverage verified、零 errors。首次 formal
  暴露 verifier report 瞬时 `coverage_state` 自失效，已通过稳定重放与一次合并重建修复；
  后续把连续报告哈希检查前移到一级审计，避免重复全量工作。
- 2026-09-02：新批次第一包 `rom-boot-state-dispatcher-cfg-v1` 通过一级快速审计。
  continuation owner 内唯一 producer 解锁 96-byte 6-slot dispatcher 与五个 bounded roots；
  精确净投影 2,532 bytes / 45 claims，12 个 2-byte holes 保持 unknown。Luna max 发现
  CpuFastSet 的 SP alias 风险后补齐 source-only/fill-mode 内存副作用合同；Sol medium
  发现 B/Bcond denominator 测试缺口后补 synthetic mutation 与独立 verifier decoder，
  最终无 P0/P1。预计为 6,191,786 classified / 99,670 unknown /
  98.41578801472983%，但未达到批量门槛，authoritative canonical 仍保持上一条数值。
- 2026-09-02：第二包 `rom-fixed-animation-descriptor-groups-v1` 通过一级快速审计。
  固定 caller group 域、allocator slot=0、4-group sequence、12-record pointer table、
  renderer `0x14` stride 与两级 `0xFFFF` stop 共同闭合 `[0x12D574,0x12D9E4)`
  1,136 bytes。11/11 packet tests、3/3 quick projection及最终 Sol 无 P0/P1。两包累计
  投影为 6,192,922 classified / 98,534 unknown / 98.43384424845377%，仍未达到批量
  门槛，因此 canonical coverage/proof/formal 未改写。
- 2026-09-02：第三包 `rom-battle-distance-dispatcher-cfg-v1` 通过一级快速审计。
  accepted owner 中的 unsigned `LDRB/CMP #6/BLS` 固定 7-slot table；七个 roots 独立
  重建为 555 instructions / 126 blocks / 1,110 code + 24 literal bytes，25 条边只进入
  accepted baseline、0 frontier。两个 2-byte 零洞保持 unknown，净增 1,162 bytes /
  14 claims。三包累计投影 6,194,084 classified / 97,372 unknown；继续等待第四包后
  统一执行二级 coverage/proof/formal，authoritative 哈希暂不改变。
- 2026-09-04：第四包 `rom-bounded-index-u16-pair-table-v1` 以 unsigned
  `CMP #7/BHI`、`index*4` 与两个 `LDRH` 闭合 `[0x53F2EE,0x53F30E)` 的 8×4-byte
  表，净增 32 bytes / 1 claim；右侧 2-byte gap 保持 unknown。四包达到门槛后通过真实
  canonical 集成测试统一接入，最终为 6,194,116 classified / 97,340 unknown /
  16,652 claims / 18,332 segments，即 98.45282236735026%。coverage / proof SHA-256
  为 `ae7c6933...90024` / `75408993...034f`；非降级 formal 106/106 contracts、ROM gate
  96/96、bad=0。首次 coverage 因 30 分钟静默被 idle guard 误杀，后续规则改为静默重任务
  idle 至少 120 分钟，并禁止用旧 canonical 加常数的算术外推冒充 Tier-2 集成验收。
- 2026-09-05：新批第三包 `rom-prebattle-menu-controller-cfg-v1` 冻结唯一 direct
  producer、`0..5` selector、六项 jump table、递归 current-unknown callee closure 与
  accepted opaque-call owner。净投影 1,920 bytes / 52 claims；本批三包累计 3,216 bytes /
  68 claims，overlay 为 6,197,332 classified / 94,124 unknown / 98.50393931070963%。
  这是入队时的历史投影；随后第四包完成，下面的新条目取代本条的“authoritative 未变”
  状态。
- 2026-09-05：第四包 `rom-scene-source-closures-v1` 在
  `[0x46401C,0x464534)` 内只晋升 71 段 parser-bounded text/fixed source 655 bytes 与
  2 个 OBJ closures 360 bytes，共 1,015 bytes / 73 claims。46 段 / 90 bytes alignment
  gaps 独立排队，23 段 / 199 bytes residual 和两个无 owner roots 保持 unknown；早期
  1,029-byte 草案因包含 12 bytes unknown-only roots 与 2 bytes parser overrun 被拒绝。
- 2026-09-05：v17/v18 helper、fixed pair、prebattle controller、scene source 四包合计
  4,231 bytes / 141 claims，已通过真实 Tier-2 接入。authoritative canonical 为
  6,198,347 classified / 93,109 unknown / 16,793 claims / 18,552 segments，即
  98.52007230122885%；CFG aggregate 为 956 ARM / 168,334 Thumb /
  169,322 promoted / 4,005 primary claims / 47 code kinds。coverage / proof SHA-256 为
  `b14d1778...96b82` / `e50417ea...a8e9`。
- 2026-09-05：三个 coverage-dependent packet 改为绑定 immutable precoverage
  `rom-scene-source-four-packet-precoverage-v1`，避免 canonical 接入后 verifier
  自失效。最终 formal 位于
  `build/experiments/active/scene-source-four-packet-formal-r2-20260905/`，report / guard
  SHA-256 为 `b2afd536...88da` / `f09deffd...30d`；106/106 contracts、ROM gate 96/96、
  coverage errors=0。`complete=false` / 177 blockers 来自 93,109 unknown 与既有全局门，
  不是本批回归。后续只在 4 packets、10 KiB 或 0.15pp 任一门槛触发 Tier-2；最终全量
  审计只在 `unknown_bytes==0` 或 release 运行。
- 2026-09-05：下一批的 story callback dependency 与 CFG proven-roots v20 已完成
  两个 Tier-1 packet。前者 1,932 bytes / 32 claims；后者由唯一 accepted direct
  producer 证明 root `0x062924`，净增 1,150 bytes / 18 claims。两包累计投影
  6,201,429 classified / 90,027 unknown / 98.56905937194824%；未达 4 packets、
  10 KiB 或 0.15pp，故 canonical/proof/formal 不重建。三个 BX 间接目标与
  `0x061320` 的 shape-only producer 保持未证明边界。
- 2026-09-05：第三个 Tier-1 packet `rom-story-next-dependency-cfg-v1` 已发布。唯一
  accepted producer `0x08F928 BL -> 0x088F10` 位于已排队 story code owner；同目标的
  `0x08F61A` 因仍在 unknown owner 只保留为 rejected shape match。raw closure 为
  338 instructions / 96 blocks / 770 code + 84 consumed-literal bytes，三个 BX 保持
  unresolved，五个 2-byte holes 保持 unknown；净增 854 bytes / 19 claims。
- packet 10/10、Tier-1 projection 3/3、candidate/official 独立 verifier 均通过；正式
  manifest / payload / verifier SHA 为 `a5429f89...669` / `d12f4b28...e6b` /
  `ed5b3581...fa8`。三包累计 +3,936 bytes / 69 claims，投影 6,202,283 classified /
  89,173 unknown / 98.5826333363851%。仍只有 3 packets，按简化审计策略不改
  canonical/proof/formal；下一包完成即达到 4-packet Tier-2 门槛。
- 2026-09-05：第四包 `rom-boot-register-init-dependency-cfg-v1` 由 boot continuation
  exact producer block `0x06109E` 解锁 root `0x06178C`，闭合 154 instructions /
  318 code + 128 consumed-literal bytes，共 446 bytes / 8 claims。三个 `BX r0` 保持
  unresolved；2-byte hole 保持 unknown；相邻 24 bytes 继续归属三个既有
  boot-handoff owners。packet 15/15、Tier-1 3/3、四包合并 13/13 与独立 verifier
  全部通过。
- 2026-09-05：本批四包累计 4,382 bytes / 77 claims，达到简化审计的 4-packet
  Tier-2 门槛后一次性接入。authoritative canonical 为 6,202,729 classified /
  88,727 unknown / 16,870 claims / 18,641 segments，即 98.58972231547037%；CFG
  aggregate 为 956 ARM / 172,148 Thumb / 173,136 promoted / 4,048 primary claims /
  51 kinds。coverage / proof SHA 为 `2cc07bc7...c01` / `3655c4a2...05ce`。
- 唯一 coverage rebuild / formal 分别耗时 30 分 20 秒 / 40 分 46 秒，峰值
  439.7265625 / 534.92578125 MiB，均非降级且无重跑；formal report / guard SHA 为
  `3971d9ea...ac3b` / `88d11d5f...26a`，106/106 contracts、coverage gate 96/96、
  errors=0。`complete=false` / 177 blockers 仍来自 unknown 与既有全局门；下一批从
  新 canonical 重新聚类，继续优先选择至少 1 KiB 或可解除上游 blocker 的冻结包。
- 2026-09-05：新批第一包 `rom-fixed-index-u8-tail-v1` 以四个 fixed immediate caller、
  唯一 `0x0853E424` literal/consumer 和 13-call denominator 闭合
  `[0x53E492,0x53E496)` 4 bytes；其余九条 caller 仅记 `excluded_non_fixed`。Sol review
  的三项 P1 已经 TDD 修复；另冻结 `rom-post-story-dependency-precoverage-v1`，确保
  post-promotion 稳定重放。precoverage + packet 16/16、Tier-1 3/3、独立 verifier 通过。canonical
  仍为 6,202,729 / 88,727；队列投影为 6,202,733 / 88,723（98.58978589375815%），
  只有 1 packet / 4 bytes，按简化策略不运行 full coverage/proof/formal。
- 2026-09-05：第二包 `rom-story-selector-dependency-cfg-v1` 由 accepted story callback
  producer `0x08F8DE` 解锁 `[0x08F544,0x08F594)`；另一个 shape match `0x08F676`
  因 source unknown 失败关闭拒绝。独立 raw worklist 重建 37 instructions / 80 bytes /
  3 opaque calls / 0 holes / 0 frontier，preowned literal 与 fallthrough 不重复认领。
- 父级 P0/P1 review 找到向量/CFG 分母回填常量与普通 rename TOCTOU 两项 P1，均经
  RED/GREEN 修复；packet 10/10、Tier-1 3/3、official verifier 通过。两包累计 84 bytes /
  2 claims，投影为 6,202,813 classified / 88,643 unknown / 98.59105745951334%。未达
  Tier-2 门槛，canonical/proof/formal 保持不变。
- 2026-09-05：第三包 `rom-task-callback-078e38-closure-v1` 由唯一静态 callback
  pointer `0x08078E39`、allocator `task+0x28` 写入和 scheduler dispatcher 读取链绑定。
  raw closure 为 342 instructions / 61 blocks / 718 code + 60 literal bytes；五个
  2-byte holes 继续 unknown。17 个 opaque callees 的栈/内存副作用未闭合，因此末端
  `0x079144: bx r0` 明确保留 1 个 indirect frontier，不宣称 structured return。
- 父级 review 的 payload/manifest 宽松校验、structured-return 超证据、路径 TOCTOU 与
  最终验证后 staging 名称可替换四个 P1 已通过 RED/GREEN 修复；发布流程现在对
  candidate/accepted 各做一次独立验真，并以 dirfd/O_NOFOLLOW/held-inode/原子
  no-replace 固定最终身份。packet 13/13、Tier-1 3/3、三包合并 22/22 均非降级通过，
  最终只读 P0/P1 reviewer 无发现。
- 三包累计净投影 862 bytes / 18 claims：6,203,591 classified / 87,865 unknown /
  98.60342343648275%。仍只有 3 packets 且低于 10 KiB/0.15pp，因此按简化审计规则不改
  canonical/proof/formal；下一份有效 packet 将触发 4-packet Tier-2。

- 2026-09-05：post-story四包实际接入978 bytes/21claims；canonical为6,203,707
  classified/87,749 unknown/16,891claims/18,664segments，98.60526720682780%。
  V21两个发布P1按TDD关闭，packet15/15；真实canonical/proof/持久收据集成9/9。
  非降级formal106/106、ROM gate96/96、errors0；global incomplete/177blockers保留。
  原始RED/GREEN和formal收据固化到notes/evidence；门禁修复本地提交e4b626462。
  精确提交预检发现64个历史artifact根使用旧schema/收据/库存，迁移未完成，不绕过hook。
