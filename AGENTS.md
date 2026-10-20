# 项目协作规则

## 持久记忆

本仓库是 ROM 逆向与续作规划的长期记忆，重要信息不得只留在对话中。

- 有意义的发现和有效工作必须形成仓库内的持久产物。
- 调查记录、内存映射和实验结果放入 `notes/`；稳定方案和流程放入 `docs/`；可复现实验放入 `tools/`。
- 有效调试方法必须同时记录方法、结果及关键文件或地址范围。
- 逆向结论变化时更新原记录；路线图进度变化时同步更新 `docs/sequel-roadmap.md`。

## 分支与工作树边界

- Butano 实现使用 `/Users/altair/github/gba-naruto` 的
  `codex/butano-foundation-research`；逆向工程使用
  `/Users/altair/github/gba-naruto-reverse` 的 `codex/reverse-engineering`。
- 两边需要复用成果时通过已提交 commit 精确 cherry-pick；不得直接复制整个脏工作树。
- 跨分支共享文档由当前集成人单点修改，避免两边同时写入。

## Goal 直接执行

- 自动续跑或继续既有 `/goal` 开发前必须检查 Goal 状态；非 `active` 时不得继续该 Goal 的写操作。用户当前消息明确要求的独立操作仅按其授权范围执行。
- 后续任务不使用 Comet 编排；Goal 直接按仓库交接、路线图、测试和运行时证据规划与执行。
- 规划按可验收里程碑拆分，不做过细实验切片、重复审查或微步骤编排；相邻的低风险输入和验证应合并为一个闭环。
- 恢复任务时重新读取 Goal 状态、交接/路线图、目标证据文件和 Git 状态，以文件事实为准修正过期状态。
- 本地 commit 仅按 Goal 或用户授权执行；push 始终需要单独授权。
- 收到新用户指令后，继续写入前必须重新检查 Goal、存活代理和 Git 状态；重新确认前产生的写入或提交视为未审计结果。

## 分层审计与批量里程碑

- 逆向 packet 完成时只执行一级快速审计：有效 TDD RED/GREEN、独立 raw-input
  verifier、ROM/输入 artifact/输出 payload 身份哈希、范围/重叠/current-unknown
  投影和失败关闭变异测试。一级通过只表示 packet 可进入待接入队列，不得把收益估算
  写成 canonical coverage 或 formal 结论。
- 相邻且信任边界相同的低风险 packet 必须先批量积累。满足以下任一条件才触发二级
  里程碑审计：累计净增至少 10 KiB；预计完成度提升至少 0.15 个百分点；同类待接入
  packet 达到 4 个。二级审计统一执行
  coverage TDD、一次 canonical coverage rebuild、proof spec 同步、相关集成测试和一份
  非降级 formal proof，不得为批内每个 packet 重复执行全量审计。
- 不满足二级门槛时，packet 保持在唯一实验目录并记录 canonical 候选、验证 receipt、
  预计净增和非声明项；不得为了让整数百分比变化而放宽 owner、合并异构证据或提前写
  canonical coverage。审计器或规范变化先由定向 TDD/集成测试失败关闭，formal 统一留到
  下一次二级里程碑或发布验收，不为单个变化临时扩张审计频率。
- 三级最终审计只在 `unknown_bytes == 0` 或发布验收时执行：重放全部 committed
  artifact verifier、全量 coverage、全部 proof
  contracts 与发布门禁。分层策略只降低重复频率，不降低 100% 完成条件和最终证据强度。
- coverage rebuild 与 formal 均属于重任务，继续使用精确
  `build/experiments/heavy.lock`，禁止 `--allow-degraded`；同一里程碑只能保留一份拥有者
  明确的正式运行，失败重跑必须先记录首份日志与失败原因。
- 二级里程碑不得用“旧 canonical + 各 packet 预计收益”的算术外推冒充集成验收。
  必须至少有一条真实 canonical 集成测试，从落盘 coverage 重建每个 batch 的精确
  claim/byte 分母、跨包无重叠、保留 unknown gap 与 CFG aggregate，并绑定对应 guard
  receipt。一级测试可以复用哈希固定且连续重放稳定的旧 packet receipt，但不能替代
  上述二级集成测试。
- coverage/formal 可在正常满 CPU 时超过 45 分钟无 stdout；这类命令的 guarded
  `idle-timeout` 不得低于 120 分钟，wall timeout 另按最近一次成功耗时留出余量。
  不得仅因 30 分钟静默终止；若守卫误杀，必须保留首份 receipt 并把耗时计入浪费。
- dependency packet 不得在 replay 时把已经包含自身 claims 的 mutable canonical coverage
  当作构建基线再次校验，否则会形成自失效环。若不保留不可变 precoverage，payload 只能
  把旧 SHA 标为 `historical_coverage_reference`，并明确
  `observed_during_this_build=false` 与 projection gate deferred；独立 verifier 必须明示
  未检查 current-unknown，最终由 coverage auditor 在投影前逐 claim 验证 current-unknown
  并把 gate receipt 写入 accepted claims。历史引用不得伪装成 build receipt。
- coverage-dependent packet 一经正式接入，独立 verifier 必须仍可在 post-promotion
  canonical 上稳定重放。若 packet 合同依赖接入前 current-unknown/owner 状态，必须在
  Tier-2 写 canonical 前发布哈希固定的 immutable precoverage artifact，并让 exporter、
  verifier 与 proof evidence 共同绑定；禁止继续读取 mutable live ledger。历史 one-shot
  builder 在 canonical 前进后应失败关闭，永久测试改为重放 archive，不得通过改写历史
  manifest 的实现哈希伪造新生产 receipt。
- `consumer_code_slice` 且 `instruction_only_claimed=false` 的 primary owner 不能直接作为
  CFG producer 的指令 membership。raw bytes 即使恰好解码为 BL/B/Bcond，也必须从已验证
  入口独立重建到 source 的局部 CFG/path，并绑定 source instruction boundary、branch
  target、上游 artifact 身份与 target 的 opaque boundary owner；否则只算形态命中，
  promotion 为零。immutable payload 不得写入 live observed coverage SHA/state；live
  pre/post 状态只进入 verifier report 与 coverage auditor gate。
- packet verifier report 中凡依赖 current coverage 的字段必须区分稳定证据与瞬时状态。
  canonical claim 只绑定可在 post-promotion 重放中保持不变的 verifier report，或绑定已
  规范化排除瞬时字段的稳定摘要；不得把 `baseline`/`post-promotion` 等一次性状态写入
  claim identity。二级审计前必须连续重放两次相关 verifier 并比较报告哈希，稳定后才允许
  启动全量 coverage/formal；该检查属于一级快速审计，不应靠重复 full rebuild 发现。

## 并发与子代理

- 共享工作区同时最多一个 writer；reviewer、日志分析和资料研究代理默认只读。
- 外派任务必须独立、非关键路径阻塞、上下文精简且结果可验证；否则由 Codex 本体处理。
- 原生子代理使用 `fork_turns: none` 并在提示词中写明目标、允许路径、禁区、验证命令、停止条件和提交权限。提示词约束不是权限隔离，关键写入仍由父代理复核。
- 当前工具 schema 未提供的模型、权限、路径或预算能力，不得声称已经应用。外部模型只做只读 sidecar，输出均由 Codex 用本地证据复核。
- 子代理报告完成不等于任务完成；父代理必须核对 TDD 红绿证据、集成测试、改动范围和 review 结论后，才能勾选 Comet task。

### 已验收的模式化分工

- 固定后续CFG字面量消费者的批量筛选优先复用已有来源raw verifier和两套
  参数流/parser：冻结ROM、结构化mode/range block、instruction boundary、literal路径
  与immutable unknown分母。不同instruction schema须明确排除，不把解析缺失视为零
  消费者；后续CFG存在新root时追加delta，不改旧消费分母及历史源码哈希。共享handler
  入口不能证明opcode语法相同，RAM文本与inline文本必须分开；callee/context恢复未
  闭合时保持非声明项。预检候选不得代替TDD或受管final/promote发布。
  支撑为`notes/rom-later-cfg-renderer-consumers-preflight-20261001.md`及永久收据；
  v1/v3/v6来源3/3复验，36site与27record/1,656B双实现一致，六新opcode根仍排除。
  同信任边界旧语法delta可合并为单一受管packet，先校验39项冻结输入再使用来源缓存；
  interpreter/parser/SJIS范围身份不得随测试skip-ROM选项跳过。export只允许初始化且active
  的实验，accepted报告仅含稳定immutable投影，live unknown由adapter单独验真；临时路径
  不进入manifest身份，promote后不得改清单才能重放。支撑为
  `notes/rom-renderer-records-delta-tier1-20261001.md`：47site、29record、1,668B，
  10项完整回归和1项completed-run拒绝测试通过；一级包仍不得提前promote或写canonical。

- 固定少量消费者窗口的只读依赖预检优先复用现有窗口解码器、原字节哈希及
  instruction-only claim 点库存；线性反汇编跨 literal、immediate 形态命中和字段名
  均不得替代完整 CFG、writer/index/lifecycle 分母。找到替代 writer 时冻结其
  call 前后数据来源，不假定 opaque callee 保持 RAM lookup。只有窗口调查有新增
  可验证锚点时才扩展下一包；预检永不直接晋升 canonical。支撑证据为
  `notes/rom-ai-config-writer-preflight-20260930.md` 及其永久窗口/provenance收据，
  复用 `tools/disasm_thumb.py`，无需模型升级。
  固定局部条件分支的u8谓词可穷举为局部域并以不可变coverage archive绑定
  instruction-only owner；必须单列跨callee、循环耗尽与其他incoming模式，不能把
  局部谓词合成未经证明的scorer/live域。已有目标限定direct-BL分母优先按哈希引用，
  明示是否本次重放。支撑为`tools/analyze_rom_ai_entry_domains.py`、7项TDD/CLI集成
  及`notes/rom-ai-entry-local-domains-20260930.md`；该预检不产出晋升claims。
  已知少量函数目标的入口预检可复用Thumb BL/B scanner，再用独立raw verifier
  补查Bcond与ARM B/BL，并以每字节精确tagged/untagged word搜索复核；明确区分
  编码形态分母、已分类instruction owner与computed/RAM入口，零字样不能证明后者
  不存在。signed位移及AL/NV排除应有正负canary。支撑为
  `notes/rom-ai-producer-and-pool-alias-20260930.md`；9/9工具回归、独立分母与
  11项canary通过，ROM分类收益0。

- 固定 immediate 索引经唯一 table-base literal 与窄 load 消费少量标量字节时，可用
  可复现脚本冻结 target-limited direct caller 分母、四条 immediate window、base literal
  occurrence、literal-LDR consumer 与 current-unknown 物理范围。未被 fixed window 正向
  证明的 caller 只能标作 `excluded_non_fixed`，不得凭集合差声称其 index 为 dynamic；
  coverage provenance 必须逐 segment 覆盖完整 range，输出发布在建目录前拒绝 `..` 并
  原子 no-replace。`rom-fixed-index-u8-tail-v1` 验收 13 callers 中 4 fixed、9 excluded，
  只晋升 `[0x53E492,0x53E496)` 4 bytes / 1 claim。

- 固定窄状态 dispatcher 的完整 slot 表与多个 bounded Thumb roots 可组成一个 dependency
  packet：先由已分类 source owner 冻结全 ROM BL/B/Bcond producer 分母，再重建状态
  mask/上界/table/wrapper、各 root code/literal/hole/opaque-call 分母。`pop {r0}; bx r0`
  不能只因形态和 worklist terminal 就算 structured return；必须验证入口 LR 保存、SP
  delta、所有 SP-relative stores、SP alias 外传及 opaque callee 的内存副作用。若 SP 传入
  BIOS CpuFastSet，必须固定 SWI wrapper、source/destination/control，并证明 fill/copy 方向
  不写 saved-LR 槽。`rom-boot-state-dispatcher-cfg-v1` 验收 6 producers、5 roots、
  1,116 instructions、2,248 code + 188 literal + 96 dispatcher = 2,532 bytes、0 frontier；
  verifier producer scan 使用独立位级实现并以 Capstone 复核，synthetic B/Bcond mutation
  保护真实 ROM 未命中的 decoder 分支。

- 静态 task callback 即使能由唯一 ROM pointer、allocator `task+offset` 写入和 scheduler
  dispatcher 读取链绑定，也只能据此证明 callback 身份与 bounded code/literal closure；
  `pop {r0}; bx r0` 在任一 opaque callee 的 SP/内存副作用未闭合时必须保留
  `indirect_pc_target` frontier，禁止宣称 structured return。此类 packet 的 verifier 必须
  exact 重建完整 payload/manifest/claim/lifecycle/scope 合同，full-ROM direct scan 覆盖末尾
  2-byte halfword；candidate 必须先在 held staging inode 通过独立 verifier，再把同一
  inode 以最终名字原子 no-replace 发布并核对身份，随后才允许经 held dirfd 写 accepted
  receipt/manifest、再次独立验真并做最终 inode 检查；禁止在最后一次验证后再按可替换的
  staging 名称发布。`rom-task-callback-078e38-closure-v1` 据此验收 342
  instructions / 61 blocks / 718 code + 60 literal = 778 bytes，保留 1 frontier 与五个
  2-byte holes。

- 固定双层索引与 sentinel 终止的描述器组，必须从 caller group 域、allocator 字段与
  slot 初始化、一级组表、二级 record pointer table、renderer slot 递增条件、record
  stride 和 next-head stop 全链证明；仅凭连续 `N×stride` 形态或 pointer table 不足。
  exporter/verifier 都必须显式绑定两级 sentinel，且独立 verifier 要拒绝非 canonical
  artifact、额外文件、member/ancestor symlink，发布必须原子 no-replace。
  `rom-fixed-animation-descriptor-groups-v1` 验收 4 groups×3 records、12×`0x54`
  descriptors、每 descriptor 4×`0x14` entries + sentinel，共 1,136 bytes；11/11 packet、
  3/3 quick projection，最终 Sol medium 复核无 P0/P1。

- canonical CFG 内固定 PC-relative literal consumer 到已冻结 renderer/parser 的记录闭包，
  应由脚本从上游 block 分母重新枚举 consumer sites，并用 bounded CFG register-taint 证明
  literal 值最终进入 parser 参数寄存器；不能硬编码 site 清单或只凭附近存在 parser BL。
  逐 target 按 opcode/parser 合同失败关闭，未覆盖 handler 与动态索引保持 unknown。
  `rom-fixed-renderer-script-records-v1` 从 v2/v3 CFG 独立重建 41 sites，接受 36 sites /
  30 unique records / 1,124 bytes，排除五个 opcode 7/8 targets；Sol medium P1 复核后
  已补上游六文件身份、完整 site denominator 与寄存器数据流，最终无 P0/P1。
  handler 含解释器内部 BL 或切换 SP 的 interwork 调用时，必须分别记录内部 target、
  条件式 call continuation 与条件式 context resumption；不能把 BL fallthrough 或局部
  pointer add 当成完整消费证明。任务 record 域、SP/LR writer 与同上下文恢复未闭合时，
  保留 unknown。支持方法与反例见 `notes/rom-renderer-handler-context-preflight-20260930.md`。

- 固定 task callback 字段注册与间接 dispatcher 可作为局部 CFG 依赖闭包：必须同时
  冻结 callback pointer literal、caller stack arg、allocator 固定字段 store、task record
  schema、dispatcher 固定字段 load 与 BX wrapper，再在显式 bounds/strict returns 内闭合
  callback 后 direct-call DAG。依赖 artifact 的无关父 verifier 若失败，必须显式保留
  false 并只独立重放所需字段，不能冒充总体通过；不外推全程序自然可达、业务语义、
  相邻洞、编辑或 relocation。`rom-text-bg-task-closure-v1` 以独立 raw Thumb worklist
  验收 10 roots / 1,330 instructions / 2,782 full code bytes / 80 references / 65 literal
  words / 0 frontier；扣除 queued/canonical owners 后净投影 2,940 bytes。

- 固定 scheduler callback slot 的 initializer/store、dispatch load/BX、callback 本地状态
  分支与 downstream direct BL 可拆成有序 dependency packets：先冻结 slot 生命周期、
  pointer occurrence、callback CFG/literal/hole 分母，再只允许 callback 已分类 code claim
  内的精确 producer 解锁 target-local entry。每个 code packet 必须同时登记
  CFG code-kind registry 与 `mode=thumb`，并在昂贵 coverage 前运行“全部待接入 packet +
  `_cfg_code_aggregate`”定向预检；后续邻接 entry 不因包络相连而自动归入同一闭包。
  公开小包可先用 Luna max；若 literal、root producer 或 GREEN 纪律失真，立即收回本体或
  升级 Sol medium。`rom-story-state-callback-cfg-v1` / `rom-story-state-entry-c4cc-v1`
  验收 702 / 220 bytes，后续 1,548 bytes 保持 unknown。

- 固定 direct invocation 初始化持久 work struct、以窄 index 逐轮消费固定表时，可用
  可复现脚本冻结初始化支配关系、所有 index writes、自增、比较上界、唯一 state-reset
  edge、dispatcher backedge 与退出路径；只有证明完整序列从 0 到物理末行且末行后不再
  解引用，才可晋升完整 table/consumer records。computed/indirect root producers 未穷尽
  必须作为 limitation，不妨碍 target-limited direct invocation，但不得外推所有自然入口。
  `rom-alternate-dialogue-table-v1` 验收 index 0..19、20×20-byte table、80 NUL records
  与 80 parser-bound zero gaps，共 3,200 bytes；Sol medium 初筛/实现后由 Codex TDD
  修复 mutable coverage 与 artifact member 边界，再进入快速队列。

- 固定条件记录分母经公共仲裁读取 payload，并统一送入已冻结 renderer/parser 的记录
  闭包，优先用可复现脚本冻结完整物理 row/type/active/target 分母、公共 payload load 与
  parser 终止边界；单个 condition handler 不直接读取 payload 不构成否证，只要所有 active
  rows 最终都经同一公共仲裁消费。独立 verifier 必须从 raw ROM 重建 1:N target 去重、
  记录范围、字节哈希和未消费间隙；物理别名不得重复计 provenance，首个 terminator 后的
  gap/tail 不得晋升。`rom-battle-condition-result-text-v1` 验收 1,128 rows / 230 active /
  219 targets / 3,961 bytes；一级投影通过但按批量门槛延后 canonical/formal。

- 固定 consumer 通过 PC-relative root load、精确寄存器数据流与已知 parser call 绑定的
  parser closure，使用公开合同闭合的小型 packet：冻结 consumer slice/root/closure
  字节、node/edge/terminal 分母和零 frontier，Luna max 可作唯一 packet writer，Codex
  本体补独立 verifier、原子 NOREPLACE/故障注入复核并接入统一 dependency-packet
  coverage 投影。consumer slice 只作 evidence，只有 closure 可 promotion；不得外推
  自然可达、全 root 分母、命令业务语义、邻接字节、编辑/重定位或 free space。
  `rom-chapter-script-consumer-roots-v1` 验收 2 closures / 16,175 bytes，formal 复用
  coverage verifier 而不增加重复命令，106/106 contracts、ROM gate 96/96 通过。

- 逆向候选队列的文档提取、地址清单和重复性初筛可交给 MiniMax-M2.7-highspeed
  只读 sidecar，以减少本体上下文开销；不得让其写仓库、启动重任务或给出最终覆盖
  结论。本体必须用固定 ROM 的 target-limited producer 扫描、current-unknown 交集和
  CFG worklist 复核。2026-08-13 实测 sidecar 正确提取 `0x07305C` 的四条 producer，
  但把 `0x070DF8` 闭包估为 4–8 KiB，而本地独立 verifier 证明只有 110 字节；因此
  sidecar 的收益估算不得直接进入路线图、coverage 或 proof。
- 固定消费者记录、固定字库/视觉 source extent 或固定压缩流之间的短零间隙，优先使用
  可复现脚本和参数化 TDD：绑定 ROM 与上游分母身份，独立重建两侧边界，只接受同一
  消费者序列或严格 parser 终点到紧邻对齐起点的逐字节零范围，并逐段篡改失败关闭。
  2026-08-13 已验收 fixed-consumer 429 段/4,141 字节、dialogue font 19 段/
  2,848 字节和 LZ77 341 段/648 字节；跨表、非零、远间隙以及缺少 header/stride
  消费者语义的 fixed-table 间隙必须排除。MiniMax 只可做候选分组，过期 CFG 建议
  与收益估算必须由最新 coverage/artifact 本地复核后拒绝。
- 固定代码范围到其实际消费 literal range 之间的短 align4 边界，先用可复现脚本冻结
  全部 code/literal/binding 分母，再由独立 raw decoder 重解每个左侧 terminal flow；
  只有非 fallthrough、逐字节固定且 current-unknown 的完整正长度邻接集合可以晋升。
  公开合同闭合的小包可由 Luna max 实现，本体必须补 strict return、build-order、CFG
  code-like registry 与单字节变异测试。2026-08-31 boot Thumb 包以 27 code range、
  22 literal range、77 binding 闭合 12 段 / 24 bytes，95/95 formal contract 通过。
  该模式不证明包络内其他 gap、padding/NOP、自然可达、编辑/重定位或 free space。
  由于 coverage rebuild 与 formal 有约 20/55 分钟固定成本，净增低于 1,000 bytes 的
  同类短 gap 默认只并入批次里程碑，不得逐包触发完整 formal；除非它解除更大工作包的
  失败关闭 blocker，并在实验 progress 中说明原因。
- 冻结 accepted Thumb CFG 的 PC-relative LDR literal 批量投影，先从上游 block
  membership 与 raw ROM 独立解码完整 source→target 分母，再只晋升冻结 baseline 中
  完整 current-unknown 的 4-byte target words；不同 CFG 家族必须证明 target 零重叠。
  verifier 必须支持 baseline 与 post-promotion 两种 coverage 状态：baseline 绑定精确
  coverage SHA，post-promotion 则要求每个重建 target 由该 packet 的精确 primary class
  接管，不能因 canonical coverage 前进而永久失效。结构化输出同时提供
  `verified=true` 和领域 `contract_ok=true`，并由 coverage auditor 绑定 verifier 与
  verifier-test 哈希。2026-09-01 v2/v6/v1 批次验收 1,699/745/349 words，合计
  11,172 bytes / 946 claims；98/98 formal verifier 与 ROM gate 88/88 通过。该模式不
  证明 loaded value 业务含义、指针有效性、自然可达扩张、相邻字节、编辑、重定位或
  free/allocatable space。
- 固定 table-base 加有界窄索引所消费的完整物理表（含 strided dispatch cell 与
  single-byte selector），优先按“小型冻结公开合同”处理：必须固定完整物理
  entry/range denominator、base/index/data-load 指令链、各字段实际读取宽度、
  ROM/consumer window 哈希、current-unknown 交集和独立 verifier；多字段 cell 的
  selector 与 handler-dependent raw operand 必须分开，单字节输出也不能仅凭值分布
  推导零/非零、gameplay、播放成功或资源身份。两类表均不得外推自然全索引/全路径
  可达、computed/RAM/indirect 或所有 selector consumers 穷尽、左右邻接结构/业务
  关系、ABI、编辑/写回/重定位或 free-space。
  公开合同闭合时由 Luna max 单 writer 完成 TDD/exporter/verifier/artifact，本体复核并
  接入 coverage/proof/formal；发现 frozen instruction、字段读址或消费路径错误时必须
  停止并修订合同，不得让模型猜测绕过。
  若同一 packet 同时含 direct-BL consumer、interwork helper、PC-relative literal 与
  窄索引表，必须把 producer provenance 与可晋升 primary range 分开，并由独立 verifier
  精确绑定 coverage 的 pre/post 双状态；除新增 owner 外的 claims、segments、summary、
  limitations 与规范 JSON 也必须失败关闭，不能只核对总数或目标 claim。2026-08-27
  `rom-directsound-pitch-lookup-v1` 按此模式验收五段 344 bytes：16-byte helper、
  92-byte consumer、8-byte literals、180-byte u8 scale 与 48-byte u32 frequency；
  两个 raw BL producer 只作 provenance。Sol medium 只读审查发现并推动修复非目标
  coverage 漂移仍会被接受的 P1，本体完成 78/78 formal contract 验收。该模式不证明
  自然运行时、全局 caller/code/indirect 或 computed/RAM consumer、播放行为、编辑、
  写回、重定位或 free space。
- 固定 initializer 写入 RAM callback slot、固定 slot load 到 `BX` trampoline、再进入
  bounded Thumb consumer 与窄索引表的间接链，必须同时冻结 initializer CFG、slot
  provenance、目标受限 raw branch/pointer 分母、consumer CFG/literal、索引域与
  current-unknown promotion；producer/initializer 仅作 provenance 时不得顺带晋升。
  原始字节候选扫描若用正则 `.`，必须启用 DOTALL 或改为逐半字遍历，并用候选编码中
  含 `0x0A` 的正负位移变异测试防止分母漏项。历史 artifact verifier 若绑定旧 coverage
  receipt，后续 promotion 不得通过相互重签制造哈希环；应保留 immutable historical
  receipt，增加明确不验证 live coverage 的 bundle verifier，再由当前 full coverage
  auditor 验证所有权。2026-08-28 `rom-psg-frequency-lookup-v1` 按此模式验收 226
  bytes；69 个 ROM-byte contract 与 10 个 bank contract 共 79/79 正式通过，旧
  DirectSound receipt 由 bundle verifier 保持可复验。该模式不证明 RAM/computed
  producer、writer、indirect caller、自然可达、非目标表业务语义、播放、编辑、写回、
  重定位或 free space。
- 固定 ROM Thumb 函数指针经 RAM callback slot、间接 thunk 再进入 target-limited
  Thumb consumer 时，优先用可复现脚本分别冻结唯一 pointer literal、slot writer、
  consumer load/thunk、raw branch/pointer 分母、已有 owner opaque stop、完整 CFG/literal
  分母和 current-unknown 投影；不得把 RAM 动态值、callback 生命周期或间接目标解析
  混入静态结构合同。core exporter/verifier 先由本体按 TDD 实现并以独立 raw decoder
  复验；公开合同完全冻结后，Luna max 只适合实现 immutable bundle/helper 小包，Sol
  medium 只读审查错误包络、owner 边界和非声明项。本体负责 coverage、proof 与 formal。
  历史 verifier 若读取旧 live coverage，保留其 receipt 并由明确
  `live_coverage_verified=false` 的 bundle wrapper 注入历史视图，当前 owner 必须由 full
  auditor 独立重建。2026-08-28 `rom-mplaymain-scheduler-v1` 按此模式验收 600-byte
  bounded Thumb code 与 12-byte consumed literals；2-byte preowned `BX r3` veneer 只作
  provenance，紧邻 2-byte gap 继续 unknown。82/82 formal structured contracts 与 ROM
  byte gate 72/72 通过；报告/guard SHA-256 为
  `34c390e98f367a2e885700fe95db32db9a2736ae8669cfe139524c576d2d9e1d` /
  `8ed618bc7b648046cb3c01f3ca3b009f31143b6b74a1bb99a6bf43711de2d906`。
  证据见 `notes/rom-mplaymain-scheduler-20260828.md`。该模式不证明自然可达、动态
  callback/RAM 值、全局 caller/code/indirect/computed producer、调度业务语义、编辑、
  写回、重定位或 free space。
- 固定 CpuSet 搬运到 RAM 的 mixed-ISA 例程，必须把 ROM source、RAM runtime address、
  copy source/destination/count、全 ROM target-limited producer 分母、ARM/Thumb 模式
  切换、实际消费 literal、既有 owner opaque stop 与 current-unknown 投影分别冻结；
  不能把整个搬运窗称为代码。source artifact 内跳过的 align4 字节必须保留 unknown，
  待左右 owner、artifact/verifier/test 身份、对齐公式和 live coverage 全部固定后，才可
  由独立 boundary verifier 作为 additive claim 接入；即使字节为零，也不得称为 NOP、
  padding、reserved/free/allocatable space。2026-08-28
  `rom-soundmain-relocated-cfg-v1` 按此模式验收 916-byte mixed ARM/Thumb code、
  8-byte consumed literals 与 2-byte preowned return veneer provenance；后续独立合同
  又只分类三个 2-byte align4 gap。最终 coverage classified/unknown/claim/segment 为
  6,123,419 / 168,037 / 14,493 / 16,600；84/84 formal structured contracts 与 ROM
  byte gate 74/74 通过。该证据不证明动态 IWRAM 内容、自然可达、全局 computed/
  indirect producer、音频行为、compiler authorship、编辑、写回或重定位安全。
- 固定 `u8` 索引、固定 cell stride 且由多个 raw consumer 共同解释的逻辑 lookup
  overlay，应把“完整逻辑视图”和“可新增 primary 的 current-unknown 投影”分开：
  全 ROM 固定 table-base literal、直接 BL caller 与 enclosing-entry pointer literal
  分母，逐条冻结 index truncation/scale、字段加载、算术表达式和最终结果宽度；与既有
  owner 重叠的 cells 只保留 provenance，不撤销也不重分类原 owner。最终算术若有
  `LSLS/LSRS` 等窄化，公开公式必须显式写出 `u16(...)`，不能以无界整数公式替代。
  artifact promotion 必须先验证 candidate，再记录可搬迁的 repo-relative verifier
  reproduction command；candidate 预置 receipt、相对输出逃到进程 cwd、symlink 或
  non-empty 输出均失败关闭。2026-08-27 `rom-u8-indexed-u16-pair-lookup-v1` 已按此模式
  验收 256×4-byte 逻辑视图，其中 36 cells/144 current-unknown bytes 可新增，后 220
  cells/880 bytes 保留 `selector_direct_source_record` owner；Luna max 完成冻结 TDD 包，
  Sol medium 只读审查发现并推动修复结果截断、输出路径和 receipt command 三项 P1，
  本体复核 canonical artifact 与独立 verifier。该模式不证明自然全 256 索引、消费者
  穷尽、业务单位、独立物理 bank、编辑/写回/重定位或 free space。
- table index 由两个或更多持久 RAM 字段组合时，不能只闭合本地 consumer、直接 caller
  或 table-base/stride；必须把所有入口的首入/续入 callback 生命周期、字段 writer、
  clear/copy/inherit、脚本 root 与支配性范围检查一起纳入失败关闭分母。先用可复现 raw
  BL/literal/writer/script 扫描寻找静态反例；公开入口不变量闭合后才适合交给 Luna max
  冻结实现，存在 scheduler/indirect frontier 时由 Sol medium 只读追踪，本体复核。
  2026-08-27 `[0x59EAE0,0x59F560)` 的 `112×24` 候选因固定 scenario 50 可产生
  `(state+0x16,state+0x19)=(31,30)`、lookup 90、组合 index 120 而否证本地上界；
  自然 callback 可达性仍未证明，所以范围继续 unknown，也不得反向声称自然 OOB。
  同日可复现 lifecycle gate 又闭合了 8 个 `0x08061D7C` 直接注册点、11 个 slot
  wrapper、`BX r1` dispatch 与返回清理：`0x0808F73C`、`0x0808EF2C` 仅在
  “literal registration → dispatch → return cleanup”结构意义上闭合；
  `0x0808F654` 仍无 raw direct branch 或精确 Thumb pointer，computed/RAM/indirect
  producer 分母继续开放。因此 gate 必须输出 `bytes_promoted=0`、`keep_unknown`，并
  停止后续 writer/inheritance 与抽象索引任务；不得把两个结构闭合 callback 外推为
  整体生命周期闭合。证据见
  `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md` 与
  `tools/verify_rom_scheduler_callback_lifecycle_gate.py`。
- 两个异构固定结构之间的短 alignment gap 只有在两侧完整分母、精确 owner、规范
  artifact/verifier/test 身份、显式 terminator 或等价结构终点、对齐公式以及完整
  current-unknown 同时冻结时，才可作为独立 additive claim；完整 source range 与当前
  primary owner range 必须分开，不能仅凭全零或邻接关系推导 padding、reserved/free、
  自然可达/不可达、编辑/重定位或可分配性。执行方式为 Luna max 处理公开合同闭合的
  小型 helper/TDD 包，Sol medium 只读复核信任边界，本体完成接线、coverage、proof 与
  formal 验收。2026-08-22 该模式先验收 motion-spawn→sequence-descriptor
  `[0x53EF2E,0x53EF30)` 两字节，绑定 15×10-byte 终止表与 22×24-byte 后继表；
  随后验收 battle-presentation fixed-count binding→tile-assets
  `[0x5A320A,0x5A320C)` 两字节，绑定 79×10-byte 与 79×68-byte 完整表，两轮均有
  68/68 formal verifier 通过；同日又验收 runtime-state fixed-count selector→handler
  pair `[0x53E696,0x53E698)` 两字节，绑定 256×1-byte selector、三段既有 left owner
  （其中 LZ77 record 38 保持 primary）与 256×8-byte handler-pair 完整表，并明确不
  推导跨表 dataflow。三轮均由 Luna max 处理冻结小包、Sol medium 只读审查、本体
  完成最终证据链。证据分别位于
  `build/experiments/active/motion-spawn-sequence-alignment-gap-coverage/codex-r1-20260822/`
  与
  `build/experiments/active/battle-presentation-tile-assets-alignment-gap-coverage/codex-r1-20260822/`
  及
  `build/experiments/active/runtime-state-handler-table-alignment-gap-coverage/codex-r1-20260822/`。
  2026-08-28 同一模式又在 task-scheduler 与 PSG 两份已接受 artifact 的固定 owner
  边界上验收 `[0x061D62,0x061D64)`、`[0x061D7A,0x061D7C)`、
  `[0x061DEA,0x061DEC)`、`[0x09B4C6,0x09B4C8)` 四段，共 8 bytes、4 claims；
  verifier/report SHA-256 为
  `befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
  `344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`，
  81/81 formal structured contracts 与 ROM byte gate 71/71 通过。该证据仍只证明
  artifact-bound align4 字节，不扩张 padding、NOP、reserved/free/allocatable
  space、自然可达、compiler authorship、编辑、写回或重定位结论。
  2026-08-30 该模式扩展到固定 tile-BG LZ77 source→palette source 边界：脚本先
  重建 896 个 pointer-reachable 流、79 个 descriptor、236 个 palette entry 与
  107 段/9,984-byte 完整 palette 分母，再由 Luna max 实现冻结小包、本体用两项
  语义 RED/GREEN 修正 helper，最终验收 84 段/165 bytes；standalone verifier/report
  SHA-256 为
  `cd4f61cb1226989c235dd710be7e37b039a6548eec6e5448b23bff97fccbc80b` /
  `4122e5404dc32e9f1f0429b06e8446d4025b01fb566eeaf1110d92cab0b9a4dc`，
  14/14 测试覆盖全部 165 个逐字节 mutation，94/94 去重 formal contracts 通过。
  两段非零长 gap 与七段 direct-CpuSet/reuse 异构短 gap 被显式排除；结论仍只限
  artifact-bound align4 gap，不把零字节解释为通用 padding、free space 或可编辑区。
- 固定视觉 source table 的消费者/parser source extent 必须冻结完整 source 分母、
  candidate/current-unknown 交集及既有 primary overlap；palette 按固定长度，definition/
  animation 按 parser 实际终点闭合。与既有 LZ77 claim 重叠时保留原 owner，只晋升
  剩余 current-unknown，不得外推全部场景资源、自然可达、最终像素、编辑/重定位安全、
  相邻间隙或 free space。2026-08-20 scene visual 验收候选 29 段/3,288 字节，保留
  pack 5 既有 LZ77 31 字节，实际晋升 29 段/3,257 字节。
- 已有 artifact/dispatcher 中尚未晋升的完整 current-unknown 子范围，优先复用现有
  exporter/verifier 证据并在 coverage auditor 内重新冻结上游身份、完整分母、range
  顺序和 current owner；只有 whole-range unknown 才能 additive 晋升，partial overlap
  必须失败关闭，表单元不得计入可达代码。2026-08-21 parser-bound 零填充、v3 sparse
  dispatcher residual 与 v7 indexed dispatcher 分别验收 198/32/36 字节；Luna max
  只读检查冻结合同，Sol medium 只读审查信任边界，本体完成 TDD、写入与正式 proof。
  同日 direct CpuSet 完整 12-source 分母按 6 个 preowned/6 个 eligible 失败关闭分区，
  additive 晋升 6 段/192 字节；coverage/proof/formal 68/68 复验通过，证明该模式也适用
  于既有 artifact 中由独立 consumer operation 固定的短原始资源范围。boot interwork
  artifact 明确跳过的短范围也按同模式处理：必须同时冻结原 artifact scope、producer
  chain、前后 owner、精确编码与 current-unknown，另发 additive claim 而不改写原
  artifact；2026-08-21 验收 `[0x09C56E,0x09C570)` 的 `C0 46` / Thumb `MOV r8,r8`
  两字节 alignment NOP，且继续禁止自然可达、全局不可达、编辑/重定位或 free-space
  推论。
- 从已验真快照、manifest 和资源表批量推导候选参数时，优先让 `gpt-5.6-terra` 只读初筛；禁止其写仓库或启动 mGBA。本体必须用本地解析、画面重放和编码器逐项复算后才能采用。
- 同类候选超过一组时，先扩展数据驱动的 build/run/export/verify 脚本，再串行运行受资源守卫保护的 mGBA A/B；不得复制多套组专用流程。
- bank 玩家可见闭环先让 `gpt-5.6-terra` 只读盘点已有 consumer、快照和 runner，本体复核后优先复用自然快照；路线已证实时固定 baseline/candidate 两次运行，不先增加命中探针。阶段截图尚未显示刚提交的 OAM 时，应从 ack savestate 重放 Mode 0，不得据 PNG 同哈希误判无可见差异。
- 视觉 descriptor 闭环可让 `gpt-5.6-terra` 只读提出候选路线和 A/B 字段，本体负责断点验真并采用能完成归因的最小字段修改；候选建议范围大于必要范围时不得照单采用。已验证模板是“自然控制器快照 → 零输入 selector/initializer 命中 → 单指针两字节变化 → 固定两次 A/B → 六内存域与像素独立复核”。
- 通用 task 表已在自然快照中物化、但 task 已 inactive 且没有短自然重建路线时，先让 `gpt-5.6-terra` 只读枚举直接/间接 caller；本体完成零输入对照和最多一个有静态依据的重入候选后仍不命中，就停止导航试错。允许在明确标注 controlled 的实验中只恢复 active bit，并从 baseline/candidate ROM 表物化目标字段；必须同时命中真实下游 consumer、等待完整提交帧、核对六内存域与最终像素，且不得声称自然 loader 重入。
- 自然 savestate 已位于上游事件构造之后时，不得强求恢复后重命中已经过去的 producer；用 hash-bound checkpoint/静态链约束上游，再以 handler 入口和 `lr` 诊断真实 consumer，A/B 只签发本轮实际命中的下游边界。需要等待自然调度的 Lua 注册 callback/breakpoint 后应返回 mGBA 事件循环，不得用 `while ... frameAdvance()` 冒充自然运行；Terra 的候选字段仍须由本体先反汇编验证空值和调用约定。
- mGBA 启动异常可先让 `gpt-5.6-terra` 只读对比成功/失败 run 的 ROM、快照、工具哈希、guard 摘要和配置；禁止其启动模拟器或据缺少 audit 猜测 ROM 行为。本体复核后只做一次有新可观测信息的重试；stdout/stderr 未持久化时不得把 `idle-timeout` 归因为脚本或 ROM。
- 可执行代码 bank 闭环先让 `gpt-5.6-terra` 只读盘点已有调用链、受控 runner 和下游证据；本体必须重新反汇编确认完整函数边界，再用 TDD 修正 extractor。运行时优先从初始化前 hash-bound 快照恢复，以单条安全 immediate 的最小 A/B 同时约束入口/返回 PC、直接硬件状态和下游输出；瞬时寄存器差异不得扩张为持续静音、可听 WAV 或真机结论。
- 被动数据 bank 的自然 producer 难以到达时，先让 `gpt-5.6-terra` 只读盘点同类型真实 caller、上游快照和历史实验，本体必须检查输入快照中的目标状态与 observer 命中计数，拒绝“producer 已在快照前执行”的过期路线。可接受的 call-local 物化必须使用 caller 原本请求的类型、非零等级、单字段 ROM A/B，并在返回后证明 live slot 恢复；若最终画面相同，只能升级实际查询公式，不得声称自然解锁、玩家可见差异或真机行为。
- 多张等长指针表并存时，先让 `gpt-5.6-terra` 只读枚举各表 literal、consumer 和可复用确认前快照；本体必须用 observer 的实际表项地址和命中 ID 排除同数量邻表。命中后复用同一 hash-bound 快照，以同表合法 donor 做单指针 A/B；只签发实际命中的 ID 与可见差异，不把原始游戏编码流冒充自然语言解码或全表自然覆盖。
- 工具 schema 未列出的模型不得调用或声称已使用；当前原生 schema 已提供
  `gpt-5.6-luna`，只用于公开合同闭合的小型冻结包，且最终 TDD、证据链和验收仍由
  本体复核。能力可用性或 provider contract 变化后必须重新跑 compatibility gate。
- 固定直接分支 producer 证明的新 CFG 根若与既有分类部分重叠，coverage 必须按 block
  与 current-unknown 的交集切片，不能要求整 block unknown，也不能重复认领已分类
  字节。2026-08-13 proven-roots v6 验收 6 producer/5 root、12,564 指令、2,305
  blocks、27,224 reachable bytes、85 个 opaque frontier；其中仅 25,926 字节晋升，
  1,298 个既有分类字节保留原 claim。长链 coverage 写后复验在加入 sprite resolved
  window verifier 后实测超过 720 秒，proof verifier 与 guarded idle 上限至少使用
  900 秒。若闭包是完全线性的短 root，也必须从全部 raw 指令重建规范向量、完整枚举
  direct/dynamic control、opaque calls、literal、hole/frontier 与唯一 fallthrough，不能
  把冻结常量直接回填成独立复验结果；`rom-story-selector-dependency-cfg-v1` 据此验收
  37 instructions / 80 bytes / 3 opaque calls / 0 holes / 0 frontier。
- 固定 direct producer 位于同轮待晋升的上游 code claim 时，允许使用显式无环依赖
  DAG 与只读 validated overlay 原子投影，但不得伪造中间 canonical coverage。上游
  artifact、独立 verifier、code-claim owner、producer raw/full-ROM denominator 与
  下游 baseline opaque entry 必须分别哈希固定；全部节点通过后才允许一次性写 coverage，
  任一失败整批不写。2026-09-01 continuation→v19 验收 94+1,660=1,754 bytes，六个
  2-byte holes 保持 unknown；通用投影 helper 只做审计去重，不减少包级独立 verifier。
- 固定间接 dispatcher 的扩展优先复用同一 CFG 脚本模式：必须固定 terminal 前的
  index 数据流与有界分支、literal、完整有序表项以及冻结基线；表目标若已是基线入口
  必须 opaque stop，只以非基线目标启动增量 worklist。2026-08-13 proven-roots v7
  验收 2 dispatcher/45 表项/21 唯一目标，其中 13 个命中 v6 基线、8 个成为新 root，
  重建 155 指令、38 blocks、332 字节、17 cross-edge 并保留 1 个 opaque frontier。
  只读 sidecar 的 21 roots/32 blocks/0 frontier 草稿被本地 ROM 与基线复算否决。
- 固定 unsigned-index 间接 dispatcher 若代码与 literal owner 已有 accepted artifact，
  新包必须分别哈希绑定 owner blocks、literal words、完整有序 table、所有 roots 与右侧
  opaque baseline targets；worklist 只跟随包内 direct edge，进入既有有效入口时停止，
  零洞继续 unknown。2026-09-02 battle-distance dispatcher 按此模式闭合 7-slot table、
  555 instructions / 126 blocks / 1,110 code + 24 literal bytes，25 opaque exits、0
  frontier，净增 1,162 bytes；两个 2-byte 零洞不分类。独立 verifier 不导入 packet
  exporter，并自行 raw decode/worklist/block count；Luna max 只读冻结合同，Sol medium
  只读 P0/P1 复核，本体完成 TDD、artifact 与 quick projection。
- 固定 table-base 被 unsigned 上界支配、index 乘固定 stride 后由确定宽度 load 完整读取
  的小型物理表，优先复用可复现 exporter + 独立 raw-input verifier。必须冻结唯一或完整
  index writer 分母、比较/分支支配关系、base literal、所有字段 load、最高访问字节和紧邻
  非声明 gap；内容形态或物理行数不能替代 consumer bound。`rom-bounded-index-u16-pair-
  table-v1` 以 `CMP #7/BHI`、`index*4` 与两个 `LDRH` 闭合 8×4-byte 表，共 32 bytes；
  `[0x53F30E,0x53F310)` 继续 unknown。该模式只声明 bounded lookup bytes，不外推业务
  字段、自然入口、编辑/重定位或 free space。
- 固定消费者逻辑指针表与既有表物理重叠时，只把不重叠的连续 slot 后缀作为新的
  primary table range，完整逻辑 base/slot domain 仅保留为消费者 provenance；不得
  重复认领重叠前缀。2026-08-13 ninja-tool description 的 slots 0–5 与
  message-command 重叠，只有 slots 6–93（352 字节）进入新表 claim。
- 固定 initializer entry pointer、固定 writer/consumer/domain、target-limited raw
  producer 与 bounded Thumb CFG/literal closure 同时出现时，先由可复现脚本分别冻结
  pointer occurrence、writer instruction、consumer field/domain、branch/pointer 分母、
  CFG edge/frontier、实际消费 literal 和 current-unknown 投影；全局 RAM writer、
  computed/indirect producer 与自然运行时必须保持非声明。相邻 pool/gap 即使为零也只在
  有独立边界合同后分类。公开合同冻结后可由 Luna max 处理短小、隔离的映射或实现包，
  Sol medium 只读复核 owner 边界与非声明，本体负责 TDD、canonical artifact、coverage、
  proof 与 formal。2026-08-29 `rom-mp2k-note-allocator-v1` 按此模式验收 550-byte
  bounded Thumb code、8-byte consumed literals 与 4-byte initializer-consumed entry
  pointer，共 562 bytes；独立 worklist 为 269 instructions、66 blocks、0 frontier，
  consumer domain 为 0..48，四段邻区共 68 bytes 保持 unknown。86/86 formal structured
  contracts 与 ROM byte gate 76/76 通过；证据见
  `notes/rom-mp2k-note-allocator-20260829.md`。

- 固定历史 artifact 的提交格式迁移优先复用不可变 Git tree、可复现归档重建与独立
  identity verifier：必须保留旧 manifest 原字节，冻结全部根和成员的 path/mode/size/SHA，
  区分直接 proof verifier、aggregate claim verifier 和仅 gzip/raw baseline 三种证据。
  结构自洽的 candidate 不是提交授权；只有代码固定的完整现代包才可在独立的 A 提交后，
  授权 B 提交中的完整旧根批次。消费时 baseline/staged 包与授权模块、实际执行模块必须
  一致；无关现代目录仍走原门禁。重建CLI须在创建输出前核对完整非null snapshot pin及
  最终压缩字节身份。2026-09-05 的64根/160成员/282输入按32/21/11桥梁完成独立归档
  验真和逐字节重建；该模式新增语义字节为0，不冒充旧verifier重放或外部信任锚。
  合同与边界见 `docs/legacy-artifact-acceptance-contract-v1.md`。
- canonical claim 的证据selector校正优先复用原生成器、实际JSON payload与独立range
  比较；不能以虚拟selector兼容例外绕过缺失证据。冻结before/after后逐项证明仅selector
  变化，其他claim字段、范围、排序、summary与segments不变，再重新绑定proof工具/输入
  身份。永久测试应核对对应历史快照，不能用未来live canonical冒充旧收据。2026-09-05
  由此修正123个selector并保持87,749 unknown，106/96 formal合同通过；执行报告域的
  selector须单独建模，不能按解析Python源文件的失败判定JSON artifact错误。

- 固定历史verifier读取ignored实验合同而导致干净检出失败时，先保持原始合同及consumer
  字节身份，将最小输入集提交到tools/data并提供显式初始化；恢复必须早于任何依赖导入，
  全量预检后仅创建缺失目标，相同内容幂等、冲突失败、不清理未拥有文件。原consumer
  仍独立核对旧合同摘要；准备成功不能冒充ROM语义验真。2026-09-05三份CGB/MP2K合同
  共27,865B按此模式恢复，11项测试含consumer集成、FIFO、临时名碰撞及祖先symlink竞态；
  流程见docs/rom-verifier-checkout-setup.md。

### 任务模式登记表（脚本闭包补充）

| 任务模式 | 执行方式 | 适用边界 | 支撑证据 |
| --- | --- | --- | --- |
| 固定 CFG 指令来源的直接显示文本增量闭包 | 可复现 exporter + 独立 raw 参数 verifier + 双 parser，TDD与受管Tier-1；复用既有发布/投影 primitives | 固定site分母、已验真CFG instruction membership、有限直线r0路径、已知显示桥与immutable precoverage；不复用命令脚本语法，不外推全ROMcaller、自然运行、Unicode、编辑安全或NUL后suffix | tools/export_rom_display_text_delta.py、tools/verify_rom_display_text_delta.py、tests/test_rom_display_text_delta.py、notes/rom-display-text-delta-tier1-20261001.md；92site/85record/1,053B，18测试和稳定重建/独立live投影通过 |
| 冻结 runtime archive 样本的部分 record×field 合同迁移 | 可复现 typed wrapper，复用旧独立 verifier 或原解析器；旧 collector 绑定历史绝对路径时，仅以新 adapter 重建来源／evidence 身份；TDD + 现有 auditor 真实 CLI 集成，无子代理 | 原 archive、ROM、bank 和实现身份均固定；仅绑定实际单元及完整未覆盖分母；历史路径只作 provenance，缺失零输入／锁身份显式保留；不改旧 manifest，不升级 exhaustive/natural/hardware；可移植离线重放不能冒充新 emulator 运行 | map-sprites 的 19 输入／1/86 单元／19 测试；tools/verify_data_table_b_partial_bank.py、tests/test_data_table_b_partial_bank.py、notes/rom-data-table-b-partial-bank-20261001.md 的 22 输入／1/79 单元／23 测试，24 文件迁移在禁止源工作树与 Qt 读取及进程启动下结果相同；两者 CLI 合同通过、全量 bank gate 仍拒绝 |
| 固定有效 bank 旧 runtime verifier 分母重放与身份漂移定位 | 可复现离线 batch 脚本，同 heavy lock 顺序执行，逐项保留原命令/stdout/stderr及前后输入 SHA | 仅实际重放固定 catalog 的既有独立 verifier；verified=true与exit0共同检查，不新增 runtime/coverage，不改旧manifest或绝对binary参数；失效先定位身份而非放宽 gate | notes/rom-bank-runtime-replay-20261001.md 及对应 receipt；11命令实际执行、10通过，menu-ui renderer 单项 SHA漂移 四类typed partial 集中复验见 notes/rom-partial-bank-joint-matrix-20261001.md，141输入／4实际CLI／8假声明拒绝／4/811单元，永久artifact位置重放，全bank门仍拒绝 |
| 冻结资源身份证据恢复与固定 slot 全分母写回矩阵 | 复用原 exporter/importer/build CLI 与独立 codec/alias verifier；脚本优先、TDD及真实集成、同 heavy lock，无子代理 | 只适用于冻结ROM/catalog/bin/实现与确定性合法变异；新 receipt 双重重建且与旧语义比较，不刷新旧hash；六工具隔离fixture不带DB，每项从同一base独立构建，实际整ROM与物理/逻辑alias重读、溢出无输出必须验真；固定变异不外推任意编辑容量、其他资源族、runtime、UI、clean release或硬件，portable主进程读取钩子不外推到子构建进程 | tools/audit_battle_effect_fixed_roundtrip.py、tests/test_battle_effect_fixed_roundtrip.py、notes/rom-battle-effect-fixed-roundtrip-20261001.md；51输入／34content/35slots/36refs／35真CLI、23接受/11容量拒绝、22相关测试、53文件移植result精确一致；旧capacity仅测试身份漂移，新旧语义相同且独立双重重建；地图第二族见 tools/audit_map_resource_fixed_roundtrip.py、tools/fixed_resource_roundtrip.py、notes/rom-map-resource-fixed-roundtrip-20261002.md：184输入/166content/217slots/249refs、167真CLI、70接受/96容量拒绝（图像34全拒绝）、27测试、186文件永久精确重放；域边界独立检查及真实非法索引先于容量拒绝，三个旧测试纠正后仅测试身份漂移、双重容量恢复语义不变 |
| 冻结资源指针单字段 A/B 与可恢复快照自然路径合同 | 可复现 builder + 既有 codec/layout/region/PatchSafetyGate + 独立旧父重建/LZ77/runtime verifier，TDD 与受管发布；显式统一 heavy lock，不沿用 legacy helper 的默认锁 | 仅冻结父 ROM/完整 allocation ledger、已登记分区、固定 record/field 与零/单输入快照；输入和新输出版本分别绑定，重建隔离指针并比较六域和 renderer；错误锁旧捕获保留但必须 fresh 重跑；不升级成全 bank、任意导航或硬件证明 | tools/build_cutscene_obj_secondary_ptr_ab.py、tools/verify_cutscene_obj_secondary_ptr_ab.py、tools/export_cutscene_obj_secondary_ptr_ab.py、两组新 source/publication tests 与 notes/rom-cutscene-secondary-ptr-contract-20261001.md；45 输入、43 raw 成员、5 个正确锁捕获、1/16 单元、778 像素、31 相关测试、双重重建及真实 auditor CLI 通过；menu 指针扩展见 notes/rom-menu-gfx-pointer-ab-20261001.md，40输入/43 raw/1 of630/26测试，scratch前缀语义显式未解 |
| 冻结旧运行时 raw 样本的依赖漂移重发与语义不变证明 | 可复现旧 exporter + 独立 verifier 重算两次，显式统一 heavy lock，原始 source 保留；只在重算后形成新 receipt | 仅单项实现身份漂移、raw/ROM/catalog/其他实现身份固定且完整语义可重建的证据；不得只改哈希、不改旧 manifest，不把重发说成新 runtime、指针字段 A/B 或全 bank 合同 | notes/rom-menu-gfx-pointer-ab-20261001.md 与 notes/evidence/rom-menu-portrait-refresh-20261001-v1/；旧17成员不变，当前 renderer 全语义重算与双 verifier通过，payload完全相同，runtime_launch=false |
| 固定目标 BL 分母与混合动画池的 caller／flags／slot 批量局部审计 | 可复现脚本、参数化 TDD、原始 ARMv4T 指令有限状态探针与既有 source CFG 独立 verifier；显式统一 heavy lock，无子代理 | 仅固定原 ROM、canonical owner、实际 source 指令分区与局部参数；未知寄存器不猜常量、可能别名的 store 清除 stack facts、控制边界不跨越；人工有限状态矩阵不得外推完整 timer／高 flags／callback／外部 writer 或自然执行；descriptor 和 sequence 的两层 sentinel 分别证明 | notes/rom-animation-pool-lifecycle-20261001.md 及对应永久收据；113 形态、96 source 指令成员、47 双表调用（45 group0／2 group1）、9 source verifier、19 测试与 672 trace 复验；mask 0x8 位编号和 sequence suffix 消费已纠正；后续 notes/rom-animation-caller-predecessor-20261001.md 以64,926指令／918根重建47条，18测试与永久路径整图重放、25字段五callee边界；raw flags与被覆盖比较寄存器必须使predicate失效，保存metadata不足以证明值域；notes/rom-animation-callee-effects-20261001.md以38测试重建五callee原始保存区、永久路径重放及上游七目标，明确SP-alias STM不得豁免、第一层frontier不是完整callee链；后续同图应一次追完整生产／callee闭包及回边，避免逐代微包；notes/rom-animation-upstream-closure-20261001.md以48测试、17packet／3轮及一次整图重算推进至22缺口，普通MOV PC LR与BX PC模式边界分别处理，已枚举child不冒充已绑定GPR effects；notes/rom-animation-interprocedural-identities-20261001.md以63测试和永久路径重放将无环child递归验真接入，独立重建29 dispatch后仅绑定guard支配的十槽表，循环／深层source缺失／live输入漂移拒绝，BL不继承入口LR且caller memory不保留；23库根两轮发现后31双字段／16缺口，9C574复用既有协程恢复义务；notes/rom-animation-critical-writers-20261001.md以9测试与永久重放追加有限指针来源，v20净增1,369来源指令／八入口，地址按累计偏移与最终合流状态认定，RAM重载不猜pointee、未知store保留alias，candidate callback来源与canonical成员分开，freeze之前的table读取仍需有效域；完整生命周期开放、promotion=0；notes/rom-animation-object-lifecycle-20261001.md复用并抽取原raw执行器，以25tests／526人工状态／672旧trace差分和永久路径重放验证两个pool初始化、两allocator各128单free槽、全满128读分母与释放扫描链；返回哨兵不能重叠source，RAM／literal／callee边界失败关闭；saved byte恢复不能收窄为全局0/1，排序前stop不冒充return，BIOS与自然writer／alias仍开放 |
| 冻结覆盖声明与既有 CFG 的存储分母／物理别名联合调查 | 可复现脚本 + 参数化TDD，复用既有保守flow／raw CPU／来源verifier，显式统一heavy.lock，无子代理 | 仅固定ROM、完整instruction partition和哈希固定声明；新增声明不等于fresh语义验真，claim后半不得发明入口，IWRAM物理mirror／alignment与IO触发效果分别处理，未知地址／callee／ARM／IRQ／BIOS／DMA义务保留；人工全u8矩阵不证明自然索引域，条件零填充不证明天然二值counter | notes/rom-animation-writer-domain-20261001.md与49成员永久收据；16tests、88,472声明指令／9,730传输／8,785未知地址、512向量索引态、两fresh来源verifier及三输出精确重放；两BL跨claim分区修正，DMA止于03007B00，slot29别名与五直接caller0/2分别绑定，promotion=0；后续notes/rom-animation-save-source-20261001.md复用slot5注册／原CPU与三source/lifecycle verifier，以12tests／521raw轨迹及永久精确重放绑定8584C来源、256save/restore与128对象freeze／四task清理；decoder的越界direct frontier不得当普通终点，必须检查raw目标并保留opaque call；原0按saved空marker恢复为1，同上下文恢复及8F654 producer保持开放 |
| 冻结来源的 ARM/Thumb 迁移回调与协程／BIOS 有限夹具差分 | 可复现脚本 + 既有来源 verifier + 固定 mGBA 原生 ARM 内核（TDD、同 heavy lock、永久精确重放） | 来源字节、复制参数、provider ABI/依赖、人工寄存器/RAM/IO、PC 范围、停止点及步数均须冻结；先验快照恢复并绑定哈希。STM 记录实际调用，不重建未观察的逐 word bus 事件；不外推自然入口、未知 writer、完整上下文恒等或实机 BIOS/事件时序；持久 RAM 链的人工入口跳转、条件 head 路径与完整 body 必须分别声明 | `notes/rom-animation-irq-arm-native-20261001.md` 与 v2 收据（13 tests／10,270轨迹）；`notes/rom-animation-object-native-20261001.md`（16 tests／5,381轨迹／三来源复验／永久精确重放）；固定快照、70项provider与549输入；源范围缓存重构输出不变，封存执行位失败保留并恢复；`notes/rom-animation-full-renderer-20261001.md` 以5tests／3,684完整入口调用／7,368轨迹／611输入／三来源复验与永久精确重放证明人工单活动对象链，不外推自然多对象或pending重工作 |
| 冻结分区所有权与固定资源全集的批量重定位写回 | 脚本优先，复用原relocator/区域/layout/build安全门与既有raw codec，TDD及真实CLI、同heavy lock；共享recipe adapter，不另写allocator | 输入ROM/catalog/分区/owner/实现、合法固定批次及对齐u32指针分母冻结；每项从同一base和显式空fixture父ledger构建，实际整ROM/allocation+pointer ledger/旧槽/所有引用重读，域/容量/owner/冲突/缺layout拒绝不发布；不外推任意子集/排序/大小、既有release父ledger、未对齐/计算消费者、runtime/UI/clean release/硬件，读取hook不覆盖子进程 | tools/audit_map_resource_relocation_roundtrip.py、tools/resource_relocation_build_cli.py、tests/test_map_resource_relocation_roundtrip.py、notes/rom-map-resource-relocation-roundtrip-20261002.md；197输入/166content/217sources/249refs，四接受批（166保留/166变异/96溢出子集/1tile扩容）+五拒绝、16测试、199文件ROM单独供给精确重放；旧保留hash相同且图像34原槽拒绝不改 |
| 已晋升链包的重放基线失效（current-unknown 门 / 冻结区间键 / 「必须仍为 unknown」断言） | 可复现脚本优先：先用「按 build_manifest 生产链顺序逐个拿最终账本重放生产者」的重放探针定量根因，再用 AST 全量扫描枚举全部调用点与断言站点，最后逐类定向验证；只读子代理仅作全量扫描与复核，不改文件 | 仅适用于「生产者已晋升进活账本、测试拿最终账本重放」这一类失效；基线必须同时剔掉本包自身批次/claim_kind **与**生产链里排在其后的后继批次；**不得一刀切剔后继批次**（有的生产者明确要求后继批次在基线里）；**故意喂活账本以断言 fail-closed** 的站点不得改；活账本 61% 的 claim 没有 promotion_batch ⇒ 基线还须按 claim_kind/id 剔；**链时不变式**（本包跑在链上时看到的样子）与**账本时不变式**必须分开断言；冻结区间键要换成「段表 = 主 claim 表逐字节投影」的派生比对 | notes/auditor-module-failures-20261020.md §10–§14、notes/evidence/reverse-proof-update-20261020-v2/probe_full_ledger_replay_20261020.py 与 full-ledger-replay-20261020.json；90/90 生产者拿最终账本重放全部 raise（40 already-present / 33 not-current-unknown / 14 pre-X-baseline / 1 promotion-changed / 2 其他，617.3 s）；12 处失效逐个诊断（9 处已定向验证全绿，3 处在整模块重跑中验证）；2 个只读子代理 AST 全量扫描出 179 处重放点、其中 98 处潜在脆弱（当前不炸，属独立后续任务） |
| 固定多包的 claim 投影接入与 proof 同步（Tier-2 门槛例外晋升） | 可复现 exporter 接线 + 离线预演（先证无重叠与四元组，再写盘）+ 幂等 apply 同步器 + 受管 ledger rebuild / formal；重活一律经 run_guarded（wall 9000 / idle 7200） | 仅适用于「包已 accepted 且已由独立 verifier 逐字节重建、只需把 claim 投影接进活账本并同步 proof」；**接入前必须**用离线预演证明新 claim 与全部 primary claim 零重叠、字节数与 claim 数分母精确、投影后的四元组与预期一致；同步器必须**幂等**且**失败关闭**（活账本缺批次就拒绝写 spec）；**只有带 `/schema` 的 verifier 报告才能进 spec 的 verifiers**，否则 `_contract()` 拒收并新增 blocker ⇒ 其余包只进 evidence（哈希绑定），验证由审计器 in-process 调用；共用 primary_class 会在账本按 class 汇总时合并，必须在包级 limitation 里写明；例外晋升必须在 notes + AGENTS.md + roadmap 三处留痕（门槛数值、实测值、例外理由、不可回溯性） | notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md（只读侦察施工单）、notes/evidence/reverse-proof-update-20261020-v3/{preflight_three_promotions_20261020.py,apply.py}、notes/four-decisions-20261020.md §1；3 包 115 claims / 3,361 B，离线预演 0 重叠且四元组（unknown 82,728 / classified 6,208,728 / claims 17,028 / segments 18,882）精确命中；9 份冻结身份逐位吻合；2 个 renderer verifier 报告无 `/schema` ⇒ 只进 evidence 不进 verifiers |

## ROM 与资源安全

- mGBA、Chromium 和高开销静态任务必须经 `tools/run_guarded.py` 使用同一 heavy lock；只清理本次拥有的进程树。
- 启动前检查可用内存，运行中监控 owned-tree RSS；资源守卫拒绝、超时或内存异常时先保存证据并停止扩张实验。
- 冗长导航前及关键输入前后建立可复用快照，并先验证快照可恢复；后续实验优先从最近已验证快照继续。
- 读取历史 `.ss9` 前先核对状态格式版本；版本 `0xB` 使用本地 mGBA commit `c16c3ff55585e71bee83c95539c2ecde15d728c8`（binary SHA-256 `ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b`），不得把新版 mGBA 的加载超时误判为路线失败。
- 原生函数若在内部同步等待多个 VBlank，普通 Lua frame callback 可能直到函数返回才恢复；要捕获中间可见态，应在循环内稳定 CPU 地址计数目标 VBlank 后保存，不得用回调恢复时的晚帧冒充中间帧。
- 单次实验只改变一个输入，并保留零输入重放作对照；CPU 暂时为零不能单独证明进程挂死。

## 证据与验收

- 每次实验使用唯一 run ID，不覆盖原始产物；派生分析写入临时或新目录。
- 实验必须由 `tools/experiment_workspace.py init` 建立在
  `build/experiments/active/`；禁止直接向 `artifacts/` 生成候选文件。
- 只有带文件哈希和 verifier 成功证据的 `final/` 才能 `promote` 到
  `artifacts/`；新成果目录受 pre-commit 检查。
- 任务完成后显式 `complete`；维护任务只归档已完成实验，不触碰 active 实验。
- 结论必须关联输入、工具/ROM/快照哈希、关键地址和结果 manifest；失效结论标记为已取代，不删除历史证据。
- 完成前运行与改动匹配的格式、单元、集成和必要的运行时验证；无法执行的检查必须明确说明。
- `AGENTS.md` 只承担稳定行为约束；状态、权限、锁、预算和写入拦截必须由 Goal、Comet guard、hooks 或脚本实现，不得把文字规则当作硬隔离。
