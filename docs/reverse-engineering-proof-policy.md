# 逆向工程 100% 证明规范

## 目的与权威入口

“100% 完成”只能由可重复、失败关闭的机器门禁得出，不能由 bank 数量、一次运行时
命中、静态导出成功或构建测试通过推导。权威入口是：

- `sequel/reverse-engineering-proof.json`：全局门禁、固定验收分母与基准 ROM 身份；
- `sequel/bank-proofs.json`：固定 32 个历史 bank 的文件哈希、覆盖分母、证据和限制；
- `sequel/rom-byte-coverage.json`：6 MiB ROM 的逐区间字节状态；
- `artifacts/character-battle-visuals-v1/manifest.json`：角色战斗视觉源区间；
- `artifacts/rom-m4a-byte-inventory-v1/manifest.json`：MP2K/m4a 音频字节清单；
- `artifacts/rom-mp2k-note-allocator-v1/manifest.json`：MP2K note allocator 的冻结闭包；
- `artifacts/rom-mp2k-dispatcher-v1/manifest.json`：MP2K dispatcher 的冻结闭包与表尾；
- `artifacts/rom-cgb-helper-bounded-cfg-v1/manifest.json`：CGB helper 的冻结
  bounded Thumb CFG 与指令实际消费 literal；
- `artifacts/rom-cgbsound-bounded-cfg-v1/manifest.json`：CgbSound 的冻结
  bounded Thumb CFG 与指令实际消费 literal；
- `artifacts/dialogue-font-v2/manifest.json`：双分支对话字库表与全部 2bpp 字形源；
- `artifacts/rom-boot-framebuffers-v1/manifest.json`：启动 Mode-3 framebuffer、ARM consumer 与 literal pool；
- `artifacts/rom-direct-cpuset-gpu-inventory-v1/manifest.json`：直接 CpuSet→PRAM 调色板源；
- `artifacts/rom-dialogue-text-inventory-v1/manifest.json`：305 行对话表及 1,220 个直接 NUL 目标；
- `artifacts/rom-dialogue-padding-inventory-v1/manifest.json`：1,219 段相邻对话目标间零填充；
- `artifacts/rom-chapter-script-inventory-v1/manifest.json`：四张解释器根表的完整静态控制流闭包、speaker-label 引用及精确字节并集；
- `artifacts/rom-renderer-text-inventory-v1/manifest.json`：11 张消费者绑定文本表的 625 个 parser-bounded target；
- `artifacts/rom-profile-text-inventory-v1/manifest.json`：固定角色资料表的 46 条 parser-bounded 记录与双零对齐填充；
- `artifacts/rom-fixed-consumer-text-inventory-v1/manifest.json`：11 张固定消费者文本表的 750 个槽（11 个显式空槽）与 735 条 parser-bounded 记录；
- `artifacts/rom-training-text-script-inventory-v1/manifest.json`：固定 45 槽训练表的 44 条解释器命令脚本；
- `artifacts/rom-value-range-text-inventory-v1/manifest.json`：固定 38 槽值域选择表、38 段选择范围及 renderer 文本闭包；
- `artifacts/rom-selector-text-bindings-v1/manifest.json`：固定 46 行来源域与三路配置域实际引用的文本前缀、配置列表和指针表；
- `artifacts/rom-selector-direct-source-records-v1/manifest.json`：固定 46×20 字节 selector direct 来源记录完整分母；
- `artifacts/rom-selector-code-windows-v1/manifest.json`：固定 10 段 selector 来源代码窗口及仅由 current-unknown 构成的提升分母；
- `artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json`：74 个目录资源映射到 70 段固定物理 BGR555 调色板的完整分母；
- `artifacts/rom-scene-visual-source-ranges-v1/manifest.json`：57 段场景视觉来源分母、29 段候选及只由 current-unknown 构成的提升分母；
- `artifacts/rom-cutscene-obj-source-ranges-v1/manifest.json`：四个固定 Cutscene OBJ 资源的 28 段 component、animation 与两类指针表来源分母；
- `artifacts/rom-positions-aux-dispatch-v1/manifest.json`：48 groups × 3 variants 的 144 张 16×4-byte auxiliary dispatch cell table；
- `artifacts/rom-battle-sound-selector-v1/manifest.json`：固定 256×u8 battle gameplay sound selector 与五条直接 pointer-literal 消费路径；
- `artifacts/rom-battle-condition-records-v1/manifest.json`：固定 47 battles × 3 variants 的 condition records、1,128 predicate slots 与 raw interpreter layout；
- `artifacts/rom-battle-message-text-inventory-v1/manifest.json`：固定 79 槽战斗消息表的 parser 文本与全部记录间零填充；
- `artifacts/rom-boot-interwork-v1/manifest.json`：固定 BL→BX pc→ARM B producer 与 `0x0800024C` ARM 根的静态闭包；
- `artifacts/rom-mplaymain-scheduler-v1/manifest.json`：固定 callback-slot/thunk 绑定的 MPlayMain bounded Thumb CFG 与 consumed literals；
- `artifacts/rom-soundmain-relocated-cfg-v1/manifest.json`：固定 CpuSet 搬运边界、IWRAM 映射与 SoundMain mixed ARM/Thumb source CFG；
- `artifacts/rom-cfg-inventory-v2/manifest.json` 与 `artifacts/rom-cfg-inventory-v3/manifest.json`：固定根 CFG 与一代索引跳转扩展；
- `artifacts/rom-cfg-proven-roots-v1/manifest.json` 至
  `artifacts/rom-cfg-proven-roots-v15/manifest.json`：固定直接 producer 或完整
  dispatcher 分母所证明的有限 CFG 根增量；
- `artifacts/rom-v17-v18-helper-cfg-v1/manifest.json`、
  `artifacts/rom-fixed-pair-tables-v1/manifest.json`、
  `artifacts/rom-prebattle-menu-controller-cfg-v1/manifest.json` 与
  `artifacts/rom-scene-source-closures-v1/manifest.json`：2026-09-05 四包 Tier-2
  里程碑的冻结 CFG、固定表与 scene source 分母；
- `artifacts/rom-scene-source-four-packet-precoverage-v1/manifest.json`：上述三个
  coverage-dependent packet 在接入前使用的 immutable canonical snapshot；
- `artifacts/rom-story-callback-dependency-closures-v1/manifest.json`：六条 accepted
  story callback BL 与三条递归 direct dependency 所绑定的 9-root Thumb CFG、实际
  consumed literals、opaque owners、structured returns 与保留 holes；
- `artifacts/rom-story-callback-dependency-closures-precoverage-v1/manifest.json`：上述
  Tier-1 packet 在接入前使用的 immutable canonical snapshot；
- `artifacts/sprite-definition-assets-v2/manifest.json`：43 项 sprite tile-base offset 表及其运行时资源链；
- `artifacts/battle-presentation-glyphs-v1/manifest.json`：战斗展示文本、glyph 表、绑定表与 palette；
- `artifacts/tile-assets-bg-v2/manifest.json`：79 个 BG descriptor 的 layer/palette 绑定；
- `artifacts/character-battle-visuals-v1/manifest.json`：角色战斗视觉 selector 及完整资源分母；
- `artifacts/bg-resource-canvases-v1/manifest.json`：BG canvas descriptor 表及 loader 消费链；
- `artifacts/overview-gradient-overlay-v1/manifest.json`、
  `artifacts/scene-visual-composites-v1/manifest.json`、
  `artifacts/residual-wram-visual-metadata-abi-v2/manifest.json`、
  `artifacts/rom-gpu-copy-queue-inventory-v1/manifest.json` 与
  `artifacts/portrait-palette-producers-v1/manifest.json`：已验收视觉/队列消费者切片；
- `artifacts/battle-effect-sprite-animations-v1/manifest.json`、
  `artifacts/battle-effect-sequence-bindings-v1/manifest.json`、
  `artifacts/story-scene-timelines-v1/manifest.json` 与
  `artifacts/battle-visual-runtime-timelines-v1/manifest.json`：消费者代码片段的规范边界；
- `tools/audit_reverse_engineering_proof.py`：严格完成审计器；
- `tools/audit_rom_byte_coverage.py`：ROM 字节清单重建与复核器。

当前规范只能证明可信工作副本中的可重复性和内部一致性。发布级真实性还必须由仓库外
的根摘要锚定：将证明规范的 SHA-256 发布在签名 tag 或独立 attestation 中，并在最终
审计时通过 `--trusted-spec-sha256` 传入。仓库内文件互相记录哈希，不能替代这个外部
信任锚；审计器及依赖也应由同一签名 commit 或可信 CI 固定。

## 分层审计策略

完整 coverage rebuild 与 formal proof 有显著固定成本，因此中间逆向成果按三级门禁
处理。该策略只减少重复执行，不改变失败关闭语义或最终完成条件。

1. **Packet 快速审计**：每个 packet 必须有先失败后通过的测试、独立 raw-input
   verifier、固定 ROM/上游 artifact/输出身份、完整分母与非声明项，并覆盖边界、顺序、
   重叠、current-unknown 投影和代表性单字节变异。通过后产物只能进入待接入队列；其
   coverage 数量和完成百分比仍是 projection，不是 canonical 事实。
2. **批量里程碑审计**：同一信任边界的 packet 合计净增达到 10 KiB、预计完成度提升
   达到 0.15 个百分点或累计 4 个时，统一完成 coverage
   TDD、一次 canonical rebuild、proof spec 更新、相关集成测试和一次非降级 formal
   proof。批内 packet 不得逐个重复全量 coverage/formal。
3. **最终审计**：只有 `unknown_bytes == 0` 或发布验收时，才重放全部 committed
   artifact verifier、完整 coverage、全部 formal
   contracts 与发布门禁。最终审计仍必须满足下节全部 100% 必要条件。

审计器或规范变化先由定向 TDD/集成测试失败关闭，formal 统一留到下一次批量里程碑或
发布验收，不为单个变化临时扩张审计频率。所有重任务精确使用
`build/experiments/heavy.lock`，不得 `--allow-degraded`，不得并行启动重复 formal。
Tier-2 必须从真实落盘 canonical 重建各 packet 的精确 claim/byte 分母、跨包无重叠、
保留 unknown gap 与 CFG aggregate；旧 canonical 加预计收益的算术外推只能作 Tier-1
projection，不能作为里程碑验收。coverage/formal 在满 CPU 时可超过 45 分钟无 stdout，
guarded idle 不得低于 120 分钟，wall timeout 按最近成功耗时另留余量。

coverage-dependent packet 不得把 mutable live canonical 当作永久 baseline。若合同依赖
接入前的 current-unknown 或 owner 状态，必须在 Tier-2 写 canonical 前发布 immutable
precoverage artifact，让 exporter、独立 verifier 与 proof evidence 共同绑定其 manifest、
压缩成员和解压后 raw JSON 身份；post-promotion 重放必须稳定。历史 one-shot builder 在
canonical 前进后按设计失败关闭，永久测试应重放 archive，不得改写历史 production
receipt 冒充新构建。

formal 的 ROM gate 已在进程内执行完整 `audit_rom_manifest`。当后续结构化合同精确对应
同一 `tools/audit_rom_byte_coverage.py --root .` 命令时，审计器复用该报告并重新执行全部
JSON pointer 断言，记录 `execution=reused-in-process`；不得再次 spawn 同一 coverage
CLI。复用条件还要求 proof spec 已哈希绑定同一脚本，命令或实现不同则必须独立执行。

## 部分 bank 证据的结构化迁移

迁移已有 runtime archive 时先复用其独立 verifier，再补 record/field IDs、固定
bank/evidence/input 哈希与具体覆盖单元。record_ids_covered 和 field_ids_covered 是
各维度投影；多字段情况下不能把二者笛卡尔积默认视为已覆盖，必须列 cells_covered。
分母来自完整冻结 bank schema，未覆盖单元保留，控制物化、自然入口和实体硬件分别声明。
verified=true 仅表示合同声明的证据通过，不等于 exhaustive=true。

首个 canary 为 [map-sprites 部分合同](../notes/rom-map-sprites-partial-bank-20261001.md)：
wrapper 直接调用旧 A/B verifier，覆盖 1/86 单元，现有全量审计器必须继续拒绝。
输入或实现漂移先失败关闭，以新版本和新收据恢复，不能改写旧 manifest。
新 proof_binding 先生成离线 proposal，定向 TDD/真实 CLI 集成通过后保留到里程碑；
接入时同步 live catalog、proof 引用与 formal，不能用离线提案宣称正式 blocker 已减少。

## “100%”的必要条件

只有以下条件同时满足时，`claim_status` 才能改为 `complete`：

1. 调用方提供的外部证明规范 SHA-256 与当前规范完全一致；所有 verifier 必须实际
   执行，不执行验证器的结构检查永远不能返回完成。
2. 基准 ROM 的仓库相对路径、大小和 SHA-256 完全一致；绝对路径、越界路径和符号
   链接均拒绝。
3. 固定 32-bank 集合完全相等，不能通过删除 bank 缩小分母。每个 bank 文件由
   `bank_sha256` 精确绑定，记录分母来自 `entries`，字段分母来自 `entry_format`。
4. ROM 每个字节都有可重复的语义分类，显式 `unknown` 为零。代码、literal pool、
   固定表、压缩/非压缩资源、文本、填充及别名都必须有有限分母和证据。
5. 每个有效 bank 按记录 ID 和字段 ID 穷尽覆盖，并具有哈希绑定原始证据与结构化
   JSON verifier 合同；任意脚本退出 0、仅写数量或自报字段名均不能通过。
6. 每个 `disproved` 候选必须有 ROM 内半开区间、候选字节 SHA-256、排除理由、负
   证据和独立结构化 verifier；空 `entries` 或文字结论本身不算证明。
7. 图像、音频、文本、地图、剧情和角色资源全部通过提取→编辑→编码→写回→重读
   round-trip。
8. 地图、关卡、剧情和角色编辑器全部通过 UI/数据库→ROM→启动→运行时读取测试。
9. 菜单和战斗逻辑修改有基准/候选行为断言；干净工作副本可用固定依赖重建全部提升
   产物和最终 ROM。
10. 受守卫的 mGBA 回归矩阵覆盖发布验收面，并在实体 GBA 上完成独立发布测试。

七个全局 gate 的 case ID 分母固化在审计器中。任何一项为 `partial`、`missing`、
`blocked_external`，覆盖集合不相等、仍有 `limitations`，或结构化验证结果不符合合同，
审计器都必须返回非零。

## 当前可证明的事实（更新至 2026-09-05）

- 字节状态清单覆盖 `6,291,456 / 6,291,456` 字节；这里的“覆盖”包含显式
  `unknown`，不代表语义破解完成。
- authoritative canonical 的保守精确定位并集为 `6,205,367` 字节
  （`98.63165219624838%`），显式 unknown 为 `86,089` 字节；当前为 16,913 claims /
  18,675 segments。下列按资源族展开的数字是累计证据说明，不再要求它们逐项相加等于
  authoritative 总数；总数只以 coverage auditor 的无重叠 union 为准：
  - 本批 fixed-index u8 tail 4 bytes、story-selector dependency CFG 80 bytes、task
    callback `0x078E38` closure 778 bytes 与 CFG proven-roots v21 116 bytes 已真实接入，
    合计 978 bytes / 21 claims；canonical/proof/持久收据集成9/9及formal106/106 contracts均通过。
    五个2-byte holes保留unknown；callback及V21间接frontier不声明structured return。
    原始收据在 `notes/evidence/rom-post-story-four-packet-tier2-20260905/`，不依赖被忽略
    的实验工作目录。A/B/C已提交且干净检出恢复、68项测试和身份重建验收通过；
  - 角色战斗视觉 1,299 个源区间：`2,023,076` 字节；覆盖 descriptor、组件、
    帧指针、时间线、动画指针、4bpp 图形与 BGR555 调色板；
  - MP2K/m4a 842 个语义区间：`887,018` 字节；覆盖空 sound-ID、song header、
    track stream、tone record 与 DirectSound wave；
  - DirectSound pitch lookup 的五个冻结 primary range：`344` 字节；包括 16-byte
    mixed Thumb/ARM high32 helper、92-byte closed Thumb consumer、8-byte consumed
    pointer literals、180-byte u8 scale descriptors 与 48-byte（12×u32）frequency
    table。两个 target-limited raw Thumb BL producer 仅作为 provenance，producer
    bytes/source membership、自然运行时可达、全局 caller/code/indirect 或
    computed/RAM consumer 分母、播放行为、编辑、写回、重定位及 allocatable space
    均不声明；
  - PSG frequency lookup 的五个冻结 primary range：`226` 字节；包括两段共
    `154` 字节的 bounded Thumb consumer code、三条共 `12` 字节的 consumed
    pointer literal，以及 `60` 字节的 channel-4 noise register descriptor table。
    两字节 `0x09B4C6..0x09B4C8` 对齐间隙不由本 PSG artifact 自身声明，而由后述
    artifact-bound alignment-gap 独立合同单独分类；固定 initializer 到逻辑
    `SoundInfo+0x30` 再经 `BX r3` 的入口链只作 provenance，不声明全局
    RAM/computed producer、writer、indirect caller、自然运行时可达、另两张目标表
    的业务语义、播放行为、编辑、写回、重定位或 allocatable space；
  - u8-indexed u8-triplet lookup 的两个冻结 primary range：`19` 字节；只包含
    `0x075C0C..0x075C10` 的四字节 consumed pointer literal 与
    `0x53DFB0..0x53DFBF` 的五条三字节 raw u8 记录。`272` 字节 consumer code
    保留既有 generic CFG owner，仅作 provenance；四段 literal pool 与右侧诊断
    区间继续 unknown，也不声明新闭合 CFG、return epilogue、自然运行时可达、业务
    字段语义、编辑、重定位或 allocatable space；
  - CGB helper 冻结 bounded-CFG artifact 提升 9 段、`180` 字节：`164` 字节
    bounded Thumb code 与 `16` 字节指令实际消费 literal。两段 intervening align4
    范围不由源 artifact 扩张声明，只由后述边界合同分类；自然运行时可达、完整
    caller/RAM-writer 分母、literal 业务语义、音频行为、编辑、写回、重定位与
    allocatable space 均不声明；
  - CgbSound 冻结 bounded-CFG artifact 提升 19 段、`1,084` 字节：`1,008`
    字节 bounded Thumb code 与 `76` 字节指令实际消费 literal。七段 intervening
    align4 范围同样只由边界合同分类；动态 callback/RAM 状态、自然运行时可达、
    helper/literal 业务语义、音频行为、编辑、写回、重定位与 allocatable space
    均不声明；
  - 四份已接受 artifact 边界上的十三段 4-byte 对齐间隙：前三段来自 task
    scheduler，第四段来自 PSG，其余两段来自 CGB helper、七段来自 CgbSound；每段
    均为两字节，共 `26` 字节、13 条 primary claim。独立 verifier 从固定 owner
    终点、下一结构起点和 raw ROM 重建十三段 `00 00`，并逐段验证
    `gap_end == align4(left_owner_end)`；其中 `0x061D7C` 右侧明确是已拥有的 Thumb
    函数而不是 literal。该窄合同不把这些字节称为 padding、NOP、reserved/free/
    allocatable space，也不声明全 ROM alignment-gap 穷尽、自然可达、compiler
    authorship、相邻 owner 新语义或编辑/写回/重定位安全；
  - 对话字库 30 个表/源区间：`144,416` 字节；覆盖 26 项 SJIS 表、2 项 byte 表、
    4,410 个 8×16 SJIS 字形与 192 个 8×8 byte 字形，并保留页间空洞；
  - 冻结 31-row SJIS lookup 的 rows 26..30：`40` 字节；仅把五个完整
    current-unknown、`<HBBI>=(0,0,0,0)` 的 empty lookup rows 绑定到真实 lookup
    loop 与 renderer parser，不声明 padding、reserved/free space、自然运行时、
    全消费者、完整 Unicode、编辑或重定位安全；
  - motion spawn→sequence descriptor 两字节 4-byte 对齐间隙：文件
    `[0x0053EF2E,0x0053EF30)` 的 `2` 个 current-unknown 字节；左侧固定
    15×10-byte motion-spawn table 以显式 terminator 结束，右侧固定 22×24-byte
    sequence-descriptor table 从 `0x0053EF30` 开始。该窄合同不声明 padding、
    reserved/free space、自然运行时可达、全局不可达、编辑/重定位安全、可安全分配、
    邻接字节或消费者完备性；
  - battle presentation binding→tile assets 两字节 4-byte 对齐间隙：文件
    `[0x005A320A,0x005A320C)` 的 `2` 个 current-unknown 字节；左侧是固定
    79×10-byte binding table 的精确 fixed-count boundary，并非 terminator，右侧是
    从 `0x005A320C` 开始的固定 79×68-byte tile-assets table。该窄合同不声明
    padding、reserved/free space、自然运行时可达、全局不可达、编辑/重定位安全、
    可安全分配、邻接字节、额外字段语义或消费者完备性；
  - runtime-state selector→handler pair 两字节 4-byte 对齐间隙：文件
    `[0x0053E696,0x0053E698)` 的 `2` 个 current-unknown 字节；左侧是冻结的
    256×1-byte selector table 精确 fixed-count boundary，右侧是从 `0x0053E698`
    开始的冻结 256×8-byte handler-pair table。该窄合同不声明 padding、
    reserved/free space、自然运行时可达、全局不可达、跨表数据流、编辑/重定位安全、
    可安全分配、邻接字节、额外字段语义或消费者完备性；
  - positions auxiliary dispatch cell tables：48 groups × 3 variants 的 144 张
    16×4-byte 表，共 2,304 cells / 9,216 bytes；byte 0 只声明 bounded dispatch
    selector，bytes 1..3 只声明 handler-dependent raw operands。独立 verifier
    重建完整 range denominator、ROM 字节与 handler read footprint；不声明自然可达、
    runtime group/variant bounds、统一业务语义、ABI、编辑/写回/重定位、next header、
    final gap 或 free space；
  - battle gameplay sound selector table：文件范围
    `[0x0053E496,0x0053E596)` 的 256×u8 完整物理表；独立 verifier 固定表范围、
    ROM bytes、base/index/data-load 指令、consumer window 及五条直接 little-endian
    pointer-literal 路径。不声明自然全索引/全路径可达、computed/RAM/indirect
    消费者穷尽、所有 selector consumers 穷尽、零/非零或 gameplay 值语义、左邻结构
    关系、右邻业务关系、完整播放例程、播放成功、全部音频穷尽、编辑/写回/重定位或
    free/allocatable space；
  - battle-condition records current-unknown fragments：完整物理表为 47 battles ×
    3 variants × `0x44` bytes，独立 verifier 重建 141 variants、1,128 predicate slots
    与 raw interpreter layout；coverage 只提升 84 个接入前 unknown fragment / 2,772
    bytes（41 个 raw variant prefix / 164 bytes，43 个 predicate fragment / 2,608
    bytes）。既有 fixed-table 与 positions-aux owner 不变，右侧 144-byte zero gap
    继续 unknown；不声明自然可达、全消费者、业务字段语义、handler 4/5 自然使用、
    编辑/写回/重定位或 free/allocatable space；
  - 启动链 14 个语义区间：`155,188` 字节；除两张 240×160 little-endian BGR555
    framebuffer、显示例程与内部填充外，还覆盖 reset vector、GBA header、可达
    bootstrap、IRQ callback 及其实际消费 literal；无可证明入边的
    `0x0000C4..0x0000C8` 继续为 unknown；
  - 直接 CpuSet→PRAM 的 3 个 BGR555 调色板源：`96` 字节；146 个直接 BL 的固定
    分母由独立验证器重建，只有这 3 个此前未绑定源计入新增覆盖；
  - 同一 direct CpuSet/CpuFastSet inventory 的完整 12-source 分母中，另将 6 个已有
    operation 绑定且完整 current-unknown 的 32-byte BGR555 source additive 晋升为
    `192` 字节；其余 6 个 source 保留既有 owner，不扩张父记录、自然可达、最终像素、
    编辑/重定位或可分配空间；
  - 消费者绑定的 305×20 对话表与 1,220 个直接 NUL 终止目标：`24,307` 字节；
    记录间填充不计入文本，原始游戏字形码也不冒充自然语言解码；
  - 上述 1,220 个目标的全部 1,219 段相邻间隙：`16,814` 字节；仅声明为
    对话记录间零填充，不声明文本语义、运行时可达或可安全分配空间；
  - 战斗展示文本、三张表及运行时调色板：`2,974` 字节；
  - 114 条候选裁决产生的 55 个此前未知规范区间：`6,304` 字节；其中候选 92
    已从错误的 36 槽子区间纠正为完整 38 槽文本指针表；
  - tile BG descriptor 绑定的 107 个规范 BGR555 palette 并集：`9,984` 字节；
  - BG canvas 的 14 项 descriptor 表（12 项非空）：`224` 字节；
  - 200 个非空解释器槽静态可达的 18,994 个节点合并为 92 段：`334,060`
    字节；另按 renderer 实际消费边界计入 49 个 speaker-label 的 `251` 字节；
  - 11 张消费者绑定文本表的 625 个唯一 renderer target：`22,588` 字节；重复指针不
    重复计数，记录间隙、自然玩法索引覆盖和 Unicode 解码均不声明；
  - 46 条角色资料文本：parser 消费 `6,798` 字节，另有 19 段、`38` 字节双零
    对齐填充；固定 46-slot 指针表、消费者和 renderer 桥接均由独立 verifier 重建，
    但自然运行时证据只绑定 ID 0，不声明其他 ID 的自然可达、字段语义或 Unicode 解码；
  - 11 张固定消费者文本指针表：750 个槽（11 个显式空槽）、735 个唯一 target，
    精确计入 `3,000` 个表字节和 `11,177` 个 parser 消费字节；除既有表外继续闭合
    active-action description 与 ninja-tool description 的非重叠后缀，并单独证明
    同表记录间零填充；混合
    `0x5A7FCC` UI 资源表因缺少文本前缀索引上界而排除；不声明记录间隙、运行时
    索引上界、自然玩法全槽可达、Unicode 解码或安全编辑边界；
  - 45 槽训练文本命令脚本表：ID 0 为空，ID 1..44 对应 44 条连续、解释器实际
    消费的记录，共 `2,505` 字节；表本身已由候选覆盖层分类，不重复认领；不声明
    每个 ID 的自然执行、Unicode 解码或安全写回；
  - 38 槽值域选择文本表：固定 `0x542204..0x54229C` 的 38 对连续 u16 包含范围，
    并按 renderer 的真实 NUL 终止路径闭合 38 条文本记录；coverage 新增 `152`
    字节范围表和 `862` 字节文本，152 字节指针表仍由候选裁决层唯一拥有；运行时
    输入上界、所有范围的自然可达、Unicode 解码和安全写回均不声明；
  - 46 行来源域 selector 文本：固定枚举器只证明 46 个来源记录映射到 46 个唯一
    物理槽，按 renderer 首个 NUL 精确计入 `324` 字节；完整来源记录表
    `0x0059F5F0..0x0059F988` 另由独立 verifier 固定为 46×20 字节并计入 `920`
    字节，但不为各记录 bytes 2..19 赋予字段语义；独立三路配置 selector 的
    3 个终止列表引用 38 个文本槽，按 copy parser 首个 NUL 计入 `316` 字节，并
    单独计入 `164` 字节配置列表与 `12` 字节指针表。实际引用槽的 NUL 后零后缀
    由后续独立 padding artifact 分类；17 个未引用槽、未证实的 63 槽分母、
    `0x0059F988` 及相邻 profile、自然可达、Unicode 解码和安全写回均保持未声明；
  - 10 段 selector 来源代码窗口：完整冻结范围共 `2,754` 字节，其中仅将当时仍为
    current-unknown 的 19 段、`1,252` 字节分类为 consumer code slice；已有 primary
    分类的 `1,502` 字节保持原 owner，不重复认领。该合同不声明全部窗口均为纯指令、
    自然运行时可达、全局 caller 穷尽、可编辑/可重定位或可安全分配空间；
  - 70 段菜单肖像物理调色板：74 个目录资源按 palette 指针/range 去重为 70 段
    128 字节 BGR555 数据，共 `8,960` 字节；311 个固定逻辑输出中 record 0 的 5 个
    零 pair 是 sentinel，唯一共享物理范围 `0x084098C4` 由 5 个资源共同引用。
    相同内容的不同物理范围不合并；不声明任意动态输入或自然玩法全覆盖、运行时像素
    等价、独立 alias 原位编辑、指针改写、重定位、图形字节、相邻间隙或可分配空间；
  - 52 段菜单肖像 LZ77→调色板短对齐间隙：独立 verifier 从 raw ROM 重新解析
    `896` 个 aligned-pointer-reachable type-0x10 流，并绑定 74 个菜单资源与 70 段
    物理调色板；仅分类 parser endpoint 到固定 palette start 之间满足
    `gap_end == align4(gap_start)` 的 52 段、`110` 个全零 current-unknown 字节。
    左右 primary owner、1/2/3-byte 尺寸分母、逐字节 mutation、源文件身份与
    canonical report 均失败关闭；不声明 padding 意图、运行时消费、通用 LZ77
    对齐规则、全部菜单间隙穷尽、编辑/重定位安全或 free/allocatable space；
  - 84 段 tile-BG LZ77→调色板短对齐间隙：独立 verifier 从 raw ROM 重新解析
    `896` 个 aligned-pointer-reachable type-0x10 流，并绑定 79 个 tile descriptor、
    236 个 palette entry、108 个 raw palette range 与 107 段合并后的物理 palette
    claim；仅分类 parser endpoint 到固定 palette source start 之间满足右边界
    align4 的 84 段、`165` 个全零 current-unknown 字节。逐字节 mutation、左右
    primary owner、范围/边界/packed-byte 分母与输入身份均失败关闭；两个含非零值的
    long gap 和七个 heterogeneous direct-CpuSet/reuse short gap 明确保留在合同外，
    且不声明 padding、reserved/free/allocatable space、自然可达、全局不可达、
    fixed-consumer 穷尽、最终像素等价、编辑或重定位安全；
  - 12 段 boot Thumb code→consumed-literal 对齐间隙：从哈希固定的 27 段
    target-limited Thumb code（1,226 字节）、22 段指令实际消费 literal（296 字节）
    与 77 条 literal binding 中，穷尽选出 code 终点到相邻 literal 起点满足
    `gap_end == align4(code_end)` 的正相邻项；仅分类 12 段各 2 字节、共 `24` 个
    全零 current-unknown 字节。独立 verifier 失败关闭地绑定 source artifact、
    terminal flow（6 branch、5 strict return、1 indirect）、range/boundary/packed
    分母；不把 gap 称为 instruction、padding、reserved/free/allocatable space，
    也不扩张历史 wide-envelope gap，不声明完整 boot runtime、自然执行、全局
    code/literal 分母、间接目标、编辑或重定位安全；
  - 29 段场景视觉来源范围：从 `scene-visual-packs-v1` 固定 9-record source table 的
    57 段、`88,756` 字节完整分母中冻结候选、
    `3,288` 字节；保留 pack 5 已由 LZ77 claim 拥有的 31 字节后，只将 29 段、
    `3,257` 个 current-unknown 字节晋升。新增范围包括 2 段共享 OBJ palette（64
    字节）、9 段 BG palette（2,304 字节）、9 段 definition record（697 字节）和
    9 段 animation record（192 字节）。不声明完整场景来源均自然可达、最终像素
    合成、LZ77 的新语义、间隙/填充可分配性、编辑/重定位安全或真机等价；
  - 28 段 Cutscene OBJ 来源范围：四个固定资源 ID 对应 10 段 component definition
    record（`240` 字节）、4 张 definition pointer table（`40` 字节）、10 段
    animation timeline（`80` 字节）与 4 张 animation pointer table（`40` 字节），
    共 `400` 个 current-unknown 字节。固定 parser stride、终止符与指针关系均由
    独立 verifier 重建；不声明未知 component 字段语义、自然运行时可达、最终场景
    合成、graphics/palette 扩张、编辑/重定位安全、相邻间隙或可分配空间；
  - Cutscene OBJ palette→definition 四处 4-byte 对齐间隙：四个固定资源 ID 各有
    一段 2-byte 范围，共 `8` 字节；独立 verifier 严格解析各 type-0x10 palette
    到精确 parser endpoint，并把该 endpoint、4-byte alignment equation 与 rooted
    slot-0 first definition record 的起点同时绑定。该窄合同不把这些字节称为 padding、
    reserved/free/allocatable space，也不声明自然运行时可达、全局不可达、完整
    Cutscene gap 分母、未知 definition 字段语义、最终像素等价、编辑/重定位安全、
    通用 LZ 对齐规则、相邻字节或 compiler authorship；
  - 79 槽战斗消息文本表：两个唯一 table literal 消费者均经固定 wrapper、bridge
    进入 renderer/parser，精确计入 79 条记录的 `1,411` 字节；并逐字节证明 79 段、
    `1,329` 字节记录间隙全零。316 字节指针表仍由 `data-table-b` 唯一拥有；运行时
    索引上界、ID 0 以外的自然执行、Unicode 解码、安全写回、零区可分配性及前置
    `0x5A14F4..0x5A1580` 的 140 字节均不声明；
  - 固定 interwork ARM 根闭包：`0x08061086` 的唯一 Thumb BL 经 `0x0809C56C`
    的 `BX pc` 切换为 ARM，再由 `0x0809C570` 唯一直接分支到 `0x0800024C`；
    独立 ARMv4T worklist 重建 92 条指令、8 个 block、10 条 edge、0 个 frontier，
    并绑定 9 个实际消费 literal。仅计入 368 字节根代码、36 字节 literal 与 10
    字节 producer，共 `414` 字节。另一个独立 additive coverage claim 只分类 spine
    跳过的文件 `[0x0009C56E,0x0009C570)` / GBA `[0x0809C56E,0x0809C570)`：
    `C0 46` / Thumb `MOV r8,r8` 两字节 veneer 对齐 NOP，同时保留原 artifact
    scope；不声明完整 reset-to-root 自然可达、全局不可达、相邻 sibling veneer、RAM
    目标、编辑/重定位安全、可分配空间或周边约 40 KiB 区域；
  - sprite-definition 的 43×u16 tile-base offset 表：`86` 字节；
  - 十三份资源 manifest 绑定且与更具体类别去重后的 71 个 consumer slice：`22,434`
    字节；这些片段可能含 literal pool，不冒充 instruction-only Thumb code；
  - 对齐 ROM 指针可达的 896 条 LZ77：`1,733,430` 字节；
  - 41 条无对齐直接指针的严格 type-0x10 流：`14,725` 个压缩字节；仅声明语法
    边界，不声明消费者、资源用途、图形语义或运行时可达；
  - 固定 263-root ARMv4T CFG 与既有 unknown 的交集：`74,962` 个 Thumb 指令字节；
    独立 raw-encoding worklist 重走 40,872 条入口并保留 366 个 frontier，不声明全局
    代码图、间接目标或自然运行时可达；
  - 在上述 v2 图哈希不变的前提下，29 个原始 Thumb 索引跳转表由 677 个允许 cell
    独立重建出 290 个目标；189 个目标引用既有入口，101 个新入口只执行一代直接
    CFG 扩展，新增 4,698 条指令、891 个 block、9,902 个指令字节。coverage 仅提升
    当时仍 unknown 的 `9,060` 个代码字节和 112 个允许表 cell 的 `448` 字节；328 个
    v2 间接 frontier 与新发现的 15 个间接 frontier 保持未解析，不认领两个稀疏表的
    奇数洞，也不声明全局代码图或运行时可达；
  - 三条固定 Thumb BL producer（`0x073688`、`0x07443C`、`0x074918`）在全 ROM
    目标限定扫描中精确指向 `0x081B70` 与 `0x0722A8`；以 v2/v3 指令入口作为
    opaque stop 独立重建的新增量包含 6,166 条指令、1,203 个 block 与 12,966 个
    指令字节。coverage 只提升其中仍 unknown 的 `12,946` 字节，并把三条 producer
    的 `12` 字节单列为 Thumb BL 指令；27 个间接目标与 1 个 decode failure 保持
    frontier，不声明全局 BL/代码分母或自然运行时可达；
  - 第二批五条固定 Thumb BL producer（`0x073690`、`0x07425A`、`0x07434E`、
    `0x074448`、`0x074F2C`）在全 ROM 目标限定扫描中精确指向 `0x0689A4`、
    `0x06B49C` 与 `0x0851F8`；以 v2/v3/首批 proven-roots 指令入口作为 opaque stop
    独立重建 4,809 条指令、835 个 block 与 9,876 个指令字节。coverage 将这些仍
    unknown 的字节全部提升，并把五条 producer 的 20 字节单列；27 个间接目标与
    1 个 unsupported instruction 保持 frontier，不声明全局 BL/代码分母或自然执行；
  - proven-roots v3–v7 继续在哈希冻结的既有 CFG 上，以固定直接 producer 或完整
    dispatcher 表分母闭合有限根；v7 接入后累计可达 Thumb 代码为 `141,680` 字节，
    未解析间接目标均保留为 frontier；
  - proven-roots v8 从已验真的 scene visual source closure 固定唯一 Thumb BL
    `0x0808BE5C→0x0808B99C`，独立重建 113 条指令、20 个 block、`246` 字节、
    10 条 baseline cross-edge 与 1 个间接 frontier。producer 与 source consumer
    已有更具体分类而不重复认领；接入后可达 Thumb 代码为 `141,926` 字节；
  - proven-roots v9 从冻结 battle-controller CFG 的完整 provenance 分母固定 11 条
    target-limited Thumb BL；其中 9 条是 controller artifact 的真实 source
    instruction，证明 8 个新 root。独立重建 299 条指令、62 个 block、`628` 字节、
    16 条 baseline cross-edge、7 个 opaque return，真正 frontier 为 0。coverage 只
    晋升 62 个完整 current-unknown block；`0x0736A4` 与 `0x07445C` 因不属于冻结
    controller CFG source instruction 而继续保持 unknown。接入后可达 Thumb 代码为
    `142,554` 字节；
  - proven-roots v10 从冻结 selector consumer source 闭包固定三条全 ROM 直接 BL：
    两条 target producer 指向 `0x0808B278`，一条 source producer 指向
    `0x0808B2C8`。独立 verifier 重建 source 264 条指令、35 个 block、580 字节、
    26 条 opaque external call edge、0 frontier，以及 target 36 条指令、7 个 block、
    72 字节、0 frontier；coverage 只晋升 target 的 7 个完整 current-unknown code
    claim 与两条 PC-relative LDR 实际消费的 8 个 literal 字节，共 9 claim / 80
    字节。producer 与 source 保留既有 owner；自然执行、全局代码/caller/间接目标
    分母、literal 可编辑性、相邻区域与重定位安全均不声明。接入后可达 Thumb 代码为
    `142,626` 字节；
  - proven-roots v11 对 `0x080633C0` 的全 ROM target-limited raw Thumb BL
    分母固定为 9 条：8 条由冻结的 tick callback source 闭包证明，`0x08080D7C`
    明确保持 `excluded_unproven_source`。独立 verifier 重建 8 个 source root、537
    条 source 指令、92 个 source block、1,130 个 source 字节和 28 条 opaque
    external edge；目标闭包为 30 条指令、6 个 block、62 字节、1 条进入既有
    baseline 的 opaque call、0 frontier。coverage 只晋升 `[0x0633C0,0x0633FE)`
    的 6 个完整 current-unknown block；第九个 raw match、source/producer、callee
    与相邻字节均不重认领，也不声明自然可达、全局 caller/代码/间接目标分母或编辑
    与重定位安全。接入后可达 Thumb 代码为 `142,688` 字节；
  - proven-roots v12 从冻结 battle-effect sprite animation source 闭包证明唯一
    `0x08061416 -> 0x08064478` Thumb BL producer，并由 immutable bundle 在不读取
    live coverage 的条件下重放已接受 artifact。目标只晋升四段闭合 Thumb code
    共 `372` 字节和四段指令实际消费 literal 共 `128` 字节，合计 8 claim / `500`
    字节；`[0x0644C2,0x0644C4)` 与 `[0x06450A,0x06450C)` 两个两字节孔洞继续
    unknown。source/producer 保留原 owner，也不声明自然运行时可达、全局 caller/
    code/间接或 computed target 分母、literal 业务语义、编辑、写回、重定位或可分配
    空间。接入后全局可达 Thumb code 汇总为 `144,550` 字节；
  - proven-roots v13 从同一冻结 source 闭包证明固定目标 `0x080651F8` 的全 ROM
    target-limited 直接 producer 分母只有 `0x080614D0` 一条 Thumb BL。独立
    immutable bundle 在动态加载 legacy verifier 前后，均由 wrapper 自身以
    `hashlib` 锚定运行时依赖；source worklist 为 237 条指令、40 个 block、508
    个指令字节、17 条 opaque external call、0 frontier，target worklist 为 153
    条指令、25 个 block、312 个代码字节、80 个实际消费 literal 字节。coverage
    只晋升 6 段、392 字节；`[0x0652DE,0x0652E0)` 与
    `[0x06536A,0x06536C)` 两个 2-byte hole 继续 unknown，`0x065368 bx r0`
    保持唯一 unresolved `indirect_pc_target` frontier，不能称为 structured return。
    source/producer、自然运行时可达、全局 caller/code/indirect/computed target
    分母、literal 业务语义、编辑、写回、重定位与可分配空间均不扩张声明。当时旧
    allowlist 输出的 Thumb 汇总为 `144,862` 字节；该数字现仅保留作历史审计快照；
  - proven-roots v14 从 V12/V13 accepted source nodes 固定五条 target-limited Thumb
    BL producer，证明 `0x0624C0` 与 `0x062510` 两个根。独立 preflight 与 immutable
    bundle 重建 60 instructions、10 blocks、120 code bytes、40 consumed literal bytes、
    4 promotion ranges、0 hole；`0x0624FE bx r0` 与 `0x062546 bx r0` 保持两个
    unresolved indirect-PC frontier。V14 只晋升连续 `[0x0624C0,0x062560)` 的 160
    current-unknown bytes，不声明自然运行时可达、全局 caller/producer/code 或
    indirect/computed/RAM target 分母、callee ABI/业务语义、literal 含义、相邻空间、
    编辑、写回或重定位；
  - proven-roots v15 从冻结的 producer/source 分母证明四个 Thumb 根
    `0x0611F4`、`0x0618FC`、`0x08B6F0` 与 `0x09A3E0`，独立 raw-control-flow
    verifier 和不读取 live coverage 的 immutable bundle 重建 197 条指令、31 个
    basic block、398 个 reachable instruction bytes 与 52 个 consumed literal bytes，
    共晋升 10 段、450 个 current-unknown bytes。`0x09C0F4` 因 literal/code overlap
    与未绑定 raw Thumb BL 命中被拒绝，三个 indirect-PC frontier、六段合计 386 字节
    的 hole 及 rejected range 全部继续 unknown；不声明自然执行、全局 caller/code/
    indirect/computed/RAM target 分母、callee 或 literal 业务语义、相邻空间、编辑、
    写回、重定位或 free-space 安全。综合、失败关闭的 CFG kind registry 同时修正了
    旧手写 allowlist 的漏计：当前为 956 ARM、148,778 Thumb 与 32 producer bytes，
    合计 149,766 promoted bytes、3,835 primary claims、33 code kinds，另有 2 个
    producer kinds；
    registry SHA-256 为
    `10ae3cc720e787630957b7c7bbbbae379ec5f3e542dbabeb871df861915a676b`。
    上述 `142,554`、`142,688`、`144,550` 与 `144,862` 均是旧不完整 allowlist 的历史
    输出，不再代表当前综合 CFG aggregate；
  - MPlayMain scheduler 冻结包提升两个互不重叠 primary range：
    `[0x09A42C,0x09A684)` 的 `600` 个 bounded Thumb instruction 字节，以及
    `[0x09A688,0x09A694)` 的 `12` 个 PC-relative-LDR consumed literal 字节，共
    `612` 字节。`[0x09A684,0x09A686)` 的两字节 `BX r3` veneer 保留既有 CFG
    owner，只作 opaque-stop provenance；`[0x09A686,0x09A688)` 两字节继续
    unknown。固定 ROM literal→RAM callback slot→consumer/thunk 链只证明静态结构
    绑定，不声明动态 callback target/RAM 值、callback 生命周期、自然运行时可达、
    全局 caller/code/indirect/computed producer 分母、调度业务语义、编辑、写回、
    重定位或 allocatable space；
  - SoundMain relocated-CFG 冻结包在 CpuSet 精确搬运合同下提升 `916` 个 mixed
    ARM/Thumb instruction 字节与 `8` 个 consumed literal 字节，共 6 个 primary
    claim / `924` 字节；四段 code 与两段 literal 合并为 5 个 union range。既有
    `[0x09A1AE,0x09A1B0)` return veneer 保留 boot-handoff owner，只作 provenance；
    source artifact 的历史合同将 `[0x099E1A,0x099E1C)`、
    `[0x099EC2,0x099EC4)` 与 `[0x099FA6,0x099FA8)` 三段两字节 alignment gap
    保持 deferred unknown；独立的 post-acceptance boundary verifier 现以 3 个
    additive claim 单独分类这 `6` 个 exact align4 字节。该后续合同不把它们称为
    instruction、NOP、padding、reserved/free/allocatable space，也不扩张右侧结构、
    自然运行时、全局不可达、compiler authorship、编辑、写回或重定位结论；源包仍不
    声明 computed/indirect producer、动态 IWRAM 状态或宽泛音频业务语义；
  - M4A initializer-chain 冻结包提升三段 target-limited Thumb 根中的 `390` 个
    bounded instruction 字节与 `128` 个指令实际消费的 literal 字节，共 6 个
    primary claim / `518` 字节。三个 direct Thumb BL producer 仅作为 raw
    provenance，不提升 producer 字节或外推 source-instruction membership；
    `0x061E28` producer 与 `[0x09B1E6,0x09B1E8)` return-to-pool 两字节间隙继续
    unknown。动态 RAM/callback 值、自然运行时可达、全局 caller/code/indirect/
    computed producer 分母、literal target 语义、音频行为、编辑、写回、重定位和
    allocatable space 均不声明；
  - MP2K note-allocator 冻结包提升 `550` 个 bounded Thumb instruction 字节、
    `8` 个指令实际消费的 literal 字节和一个 `4` 字节 initializer-consumed Thumb
    entry pointer，共 4 个 primary claim / `562` 字节。四段相邻范围共 `68` 字节
    继续 unknown；自然运行时可达、全局 caller/code/indirect/computed producer、
    RAM writer、literal target 业务语义、音频行为、编辑、写回、重定位及
    allocatable space 均不声明；
  - MP2K dispatcher 冻结包提升 `86` 个 bounded Thumb instruction 字节、固定
    table-tail 的 `12` 字节和 `4` 个指令实际消费的 literal 字节，共 4 个 primary
    claim / `102` 字节。五段既有 owner 共 `238` 字节只作 provenance，
    `[0x09BCE2,0x09BCE4)` 与 `[0x09BDFA,0x09BDFC)` 两段各两字节继续 unknown；
    自然运行时可达、全局 caller/code/indirect/computed producer、RAM writer、
    literal target 业务语义、音频行为、编辑、写回、重定位及 allocatable space
    均不声明；
  - 九份既有 artifact 经固定哈希、真实 JSON selector 与独立 verifier 复验后，只将
    baseline unknown 的交集提升为 37 个 claim、`3,919` 字节；包含四张规范 dispatch
    表、battle-effect/scene/world-map 表、受界 consumer slice 与 BGR555 palette；
    失败的 character OAM、staged GPU 的 RAM/raw resource、纯指令性和运行时可达均不声明；
  - battle-effect sprite 既有 artifact 的固定 source 分母新增 237 个互不重叠 claim、
    `11,120` 字节：178 段 component list（`9,452` 字节）、18 张 definition pointer
    table（`712` 字节）、23 段 animation timeline（`864` 字节）和 18 张 animation
    pointer table（`92` 字节）。每段必须完整落在 current unknown，并由同一独立
    verifier、ROM 原始字节、终止符和指针向量复验；不声明自然运行时可达、图形或
    调色板范围扩张、可编辑空间或写回安全；
  - 133 段引用槽 NUL 后结构零填充：共 `1,255` 字节，其中 46 个 direct selector
    槽 `550` 字节、38 个 configured selector 槽 `368` 字节、49 个脚本实际引用的
    speaker-label 槽 `337` 字节；每段均从消费者首个 NUL 后一字节起至固定槽末尾，
    并由独立 verifier 逐字节确认全零。未引用槽、NUL 与前缀、文本语义、自然运行时
    可达、编辑/写回安全及可安全分配空间均不声明；
  - 22 个非空 bank 的记录字节：`348,018` 字节；
  - 精确 `0xFF` 尾区：`132,116` 字节。
- 其余 `149,280` 字节（`2.372742%`）仍显式未知；当前共有 `15,940` 条 primary
  claim 和 `17,344` 个规范 segment。未知字节不能自动称为代码、资源、
  可用空间或“没有新结构”。
- 全 ROM 启发式指针表分母固定为 114 条；原始扫描清单保持不可变，独立裁决覆盖层
  当前由 ROM 与规范产物重建出 60 条 `accepted`、26 条 `alias_of`、28 条
  `rejected`，`open_candidate_count=0`。不能
  通过改写扫描清单、缩小分母或改 gate 状态绕过。
- 41 条不重叠、共 14,725 字节的严格 type-0x10 语法流没有对齐直接 ROM 指针；
  独立扫描与双 bundle 可重建并已按语法范围接入，但缺少 consumer，因此不称为图像、
  资源或运行时可达内容。
- 32 个固定 bank 均由证据目录和 bank 文件 SHA-256 绑定；10 个 `disproved` 候选现由
  同一独立负证据 verifier 分别重建规范表别名、错位切片、混合 font/handler 范围、
  角色视觉矩阵子视图或 m4a SongHeader `+4` 子字段，并绑定各自候选范围、ROM 字节、
  bank 与 evidence 哈希。因此严格 bank 门当前为 `10 / 32`，这十项仅否证历史候选
  作为独立物理 ROM bank；它们不声称穷尽排除同一规范字节的其他逻辑消费者，也不
  证明任何有效 bank 的运行时穷尽覆盖。
- 22 个 `runtime_verified` 仅表示至少一条运行时身份关联。当前直接证据声明为
  `23 / 2,954` 条记录；这是自报进度分子，不是按 record ID 重放的穷尽证明。
- 21 个 bank 配置了哈希绑定的离线 verifier，其中上述 10 个 `disproved` bank 具备
  新规范要求的结构化结果合同；22 个有效 bank 的严格全记录/字段完成度仍为
  `0 / 22`。
- 2026-09-05最新formal永久报告位于
  `notes/evidence/rom-evidence-selector-repair-20260905/formal-report.json`；report /
  guard SHA-256为`aa125c7e80ea4364522698c04557b3d6a819f77000c28c58871bc74cf13938bc` /
  `3e1722f8979fa68723acf3e5940cf7eacd5beaabde6d19c2c14bf277a6736c54`。
  106/106 structured contracts与ROM gate96/96通过、coverage errors=0。非降级，
  耗时40分58秒，峰值525.7109375MiB；唯一coverage报告为reused-in-process。
  123个selector修复不改变分类；两个project摘要错误已关闭。global incomplete/175blockers
  来自87,749unknown和既有bank/round-trip/发布/硬件门。
  64个历史root已由A/B固定身份迁移并提交；干净B暴露三份旧运行合同缺失，
  C已按`docs/rom-verifier-checkout-setup.md`补全输入；干净C的68项测试、64根160成员
  Git身份及282输入重建均通过。此次提交复验未重复执行完整formal，原始正式输入保持一致。后续列出的报告均为历史里程碑，不能覆盖此身份。
- 当前 proof spec 配置 96 个 ROM byte gate verifier，全部具备哈希绑定和结构化
  合同；MP2K dispatcher、MP2K note allocator、M4A initializer-chain、SoundMain
  relocated CFG 及其独立 alignment-gap、
  MPlayMain scheduler、PSG frequency lookup、DirectSound pitch lookup、任务调度器核心 R4、boot Thumb handoff、
  u8-indexed u16-pair lookup、u8-indexed u8-triplet lookup、
  CGB helper/CgbSound 双 artifact bundle、
  CFG proven-roots v11/v12/v13/v14/v15、battle-condition records、battle gameplay sound selector、
  positions auxiliary dispatch、Cutscene OBJ palette→definition alignment-gap 与
  artifact-bound alignment-gap、menu portrait LZ77→palette gap 与 tile-BG
  LZ77→palette gap 里程碑各有
  standalone verifier。boot-interwork NOP、SJIS empty
  lookup rows、motion-spawn/sequence-descriptor、
  battle-presentation/tile-assets 与 runtime-state/handler-table alignment gap 五个
  较早 additive claim 仍复用已有独立 verifier。本轮 tile-BG gap 受守卫正式审计实际执行
  94 个唯一结构化 contract（84 个 ROM byte 加 10 个 bank），全部
  `exit_code=0`、`contract_ok=true`。proof spec 另有 11 个只作哈希绑定
  证据的旧 bank verifier，因此当前 gate 配置总数为 95；配置引用与去重后的实际
  执行命令不能混为一谈：
  原有 LZ77、m4a、对话字库、启动 framebuffer、无直接指针语法库存及 114 条候选
  裁决均通过；新增的直接 CpuSet、对话文本、battle presentation、tile BG、story
  timeline、battle visual timeline、battle-effect sprite、sequence binding、角色
  战斗视觉、BG resource canvas、overview gradient、scene visual、residual WRAM
  metadata、GPU copy queue、portrait palette、章节脚本静态闭包、renderer 文本、
  角色资料文本、固定消费者文本、训练文本命令脚本、38 槽值域选择文本、selector 文本、79 槽战斗消息文本、固定 interwork ARM 根闭包、sprite-definition、固定 root
  CFG、一次性 CFG 扩展、proven-roots v1–v10 增量、对话记录间零填充与引用文本槽
  NUL 后结构零填充、selector direct 来源记录、selector 代码窗口、菜单肖像调色板与
  场景视觉来源范围、Cutscene OBJ 来源范围与 v9 controller-proven CFG 根合同也全部通过。
  positions auxiliary dispatch 的独立 range/cell/consumer、battle gameplay sound
  selector 的 table/consumer-path 与 battle-condition records 的 table/interpreter
  合同也通过；v10 的 source/target bounded worklist、两条实际消费 literal 与标准
  promotion receipt 合同同样通过。v11 的 source/target bounded worklist、九条 raw
  producer 分母、`0x080D7C` 排除状态与标准 promotion receipt 合同也通过；v12 的
  immutable bundle、500-byte code/literal promotion、两个 2-byte unknown hole 与
  不读取 live coverage 的历史 receipt 重放合同同样通过；v13 的 dependency-first
  immutable bundle、392-byte code/literal promotion、两个 2-byte unknown hole、
  唯一 unresolved `bx r0` frontier 与不读取 live coverage 的历史 receipt 重放合同
  同样通过；v14 的五条 accepted producer、双 root worklist、120-byte code、40-byte
  literal、两个 unresolved `bx r0` frontier、0 hole 与 dependency-first immutable
  bundle 合同同样通过；v15 的四个 accepted roots、一个 rejected root、398-byte
  code、52-byte literal、三个 unresolved indirect-PC frontier、386-byte preserved
  unknown holes 与 dependency-first immutable bundle 合同同样通过；52 段菜单肖像
  LZ77→palette gap 的 110-byte 分母、逐字节零值、左右 owner、align4 与非声明合同
  同样通过；84 段 tile-BG LZ77→palette gap 的 165-byte 分母、完整 896/79/236/
  108/107 来源分母、逐字节零值、左右 owner、align4、两个 long 与七个 heterogeneous
  排除项及非声明合同同样通过；lookup、
  boot handoff、scheduler R4、MP2K note allocator 与 MP2K dispatcher 的原始字节、
  范围分母、CFG/literal 投影和 promotion receipt 合同也全部通过。这些结论以本轮
  唯一受守卫 formal report 为准，不是从静态 spec 推定。
  当前 coverage 合同如实
  断言 `semantic_classification_complete=false`；单独加
  `--require-semantic-complete` 的最终语义门禁仍因未知字节按设计以退出码 2 失败。
- 七个 CFG consumed-literal packet（含第二批四包）接入后的最新正式报告
  位于
  `build/experiments/active/cfg-consumed-literals-batch2-formal/codex-r1-20260901/formal-report.json`
  （SHA-256 `8ec5119f4f21132721a0727bc4d6caf18a570076bce45093425334b573fe001d`，
  guard SHA-256 `7458b23dd71a825364bf27f5914bca326615ebb59ff4c94df82837b4b4c19ec3`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `f368bd1bb9b527b5f7311a33ff1435e3addb86a89db46e1fdce739232da74945`、
  `24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987`、
  `c3d6964cfbf497ef73a350cba2c0aaa393381f3fdc884362b7cecf911dc2d93e` 与
  `59ffdd85782c5127db1a545e49a5c0daa48e0033eb7c3b5196a4c492817b8c33`。
  102/102 个实际结构化 contract 全部通过，ROM byte gate 92/92、bank contract
  10/10、bad=0；审计耗时约 3,449 秒，守卫非降级、峰值 RSS
  673.7734375 MiB。报告正确保持 `complete=false`、`claim_status=incomplete`、
  177 个 blockers，只证明 6,142,176 / 149,280 / 15,940 / 17,344 的 coverage
  状态和已声明合同。
- menu portrait LZ77→palette gap 接入后的上一份历史正式报告位于
  `build/experiments/active/menu-portrait-lz77-palette-gap-proof-20260830/formal-r1-report.json`
  （report / guard SHA-256：
  `92b4b471b972bcc789848f78192f8c5162deeeb0ab0c1bce77e818694e88ba3a` /
  `e0985d49922e2473229c8c28c4182013e9497718977e07807a52885e76b2b66e`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `eaa8b7f2b37feaa9686d83c84f6fd16672e6b6ae3038e0ccf16ece96c4698eb2`、
  `c2798b35f4ac21f170c9a7575cbf10118aad98d58efbebf3d59ca9f599216133`、
  `86f33a51d09fc572818e5cc541563e670deb3a0d7f11a4015d7f640deb57a5e0` 与
  `59ffdd85782c5127db1a545e49a5c0daa48e0033eb7c3b5196a4c492817b8c33`；
  该历史报告为 93/93、ROM byte gate 83/83、bank contract 10/10、bad=0；对应
  6,127,495 / 163,961 / 14,624 / 16,693，耗时 3,385.228261 秒、非降级、峰值 RSS
  680.0625 MiB，不能覆盖当前 tile-BG milestone 身份。
- CFG proven-roots v15、隔离执行环境修复与 post-V15 coverage 接入后的上一份历史
  正式报告位于
  `build/experiments/active/cfg-proven-roots-v15-proof-20260830/formal-r2-report.json`
  （SHA-256 `3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63`，
  guard SHA-256 `b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`）。
  该历史报告为 92/92、ROM byte gate 82/82、bank contract 10/10、bad=0；对应
  6,127,385 / 164,071 / 14,572 / 16,693。V15 formal-r1 虽因
  `--allow-incomplete` 令守卫退出 0，但实际有
  coverage auditor 与 V15 bundle 两项 contract 失败；根因是 formal executor 注入
  `PYTHONPATH` 与 V15 `-I -S` 隔离合同冲突，已由失败测试、最小环境清理和本 r2
  取代，不能把 r1 当作验收报告。
- CFG proven-roots v14 与综合 CFG registry 接入后的上一份历史正式报告位于
  `build/experiments/active/cfg-proven-roots-v14-formal-20260830/formal-r2-report.json`
  （SHA-256 `f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786`，
  guard SHA-256 `3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `b78b8b2fd112cd07cc4b096443f3aff246b2df080be4c7acf54f0c677440ca02`、
  `2592ce481515af301ef5ce4078d3e9101793bf790f1bc90a6d33d5a06c207317`、
  `cfc6b59b2376308c3a63859585dacb0b0e8ecd06b5710dcdcaf9ab46bc2cb92f` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  91/91 个唯一结构化 contract 全部通过，ROM byte gate 81/81、bank contract
  10/10、bad=0；审计耗时 3,438.593624 秒，守卫非降级、峰值 RSS 660.1875 MiB。
  V14 formal-r1 使用旧不完整 aggregate，已被本 r2 取代。报告正确保持
  `complete=false`、`claim_status=incomplete`、175 个 blockers；它只证明当前
  6,126,935 / 164,521 / 14,562 / 16,677 的 coverage 状态和已声明合同，没有把
  两个 V14 `bx r0` frontier、其余 unknown 或其他六类未完成 gate
  扩张为已完成。
- CGB helper、CgbSound 与 13 段 artifact-bound gap 接入后的正式报告位于
  `build/experiments/active/cgb-bounded-proof-20260829/formal-r1-report.json`
  （SHA-256 `613cee1f8c72882aebe6ffaf617fc2fa1ea556ca9235f9f78607132dd189a567`，
  guard SHA-256 `7515d1e4c9a47f6508209a17747992e4219619075ada9f6a8766bb9045315e7a`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `9151c9c9e60cbb9885143356d15f441b2ee3c89d146c5f71cd6c50d14550d199`、
  `05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6`、
  `66befe8947606cae7f9aebd1822403536d1820ab6462debb71b24c0c3a5add78` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  88/88 个唯一结构化 contract 全部通过，ROM byte gate 78/78、bad=0；审计耗时
  2,976.038634 秒，守卫非降级、峰值 RSS 668.0078125 MiB。报告正确保持
  `complete=false`、`claim_status=incomplete`、175 个 blockers；它只证明当前
  6,125,883 / 165,573 / 14,544 / 16,654 的 coverage 状态和已声明合同，没有把
  未知字节或其他六类未完成 gate 扩张为已完成。
- SJIS empty lookup rows additive coverage 接入后的正式报告位于
  `build/experiments/active/sjis-empty-lookup-rows-coverage/codex-r1-20260821/formal-report.json`
  （SHA-256 `ff6087c3313dec3b71f16d96af9aa503844a44aa4ea1a2f286e21b98dc5c93bc`，
  guard SHA-256 `0260f58160f8f6f1ac108bf5254179fa6f443c4d6cfca43173fc9776211919ca`）；
  proof spec SHA-256 为 `ba3f4a3ecc51931478bdacc4f7124d68c3faeac4c2262f2f36be926088dc1f29`，
  coverage SHA-256 为 `3b562213df931df21e1bf237226c73279b883d427d02dccbf54e063bd18e3dd7`，
  coverage auditor SHA-256 为
  `a0109d2443858b09f9193f80a45dafa046e9661c863440b6ddcb42e651936f29`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`；
  68/68 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate 为 58/58，
  bad=0，守卫峰值 RSS 为 614.55078125 MiB。报告仍为 `complete=false`、175 个
  blocker，符合 `184,550` 字节仍未知、七个全局门均未关闭且 trust anchor 未由
  仓库外提供的事实。
- motion-spawn/sequence-descriptor alignment-gap 接入后的正式报告位于
  `build/experiments/active/motion-spawn-sequence-alignment-gap-coverage/codex-r1-20260822/formal-report.json`
  （SHA-256 `3844c1ff49a4a2da5142f517ee3066a15eccadf2b87e864407a7bc0e369bdd89`，
  guard SHA-256 `66ae9eead07daaed3ac9485d8b75a6ba29eae1e901e7c2d9c65c47c1aafd52a7`）；
  proof spec SHA-256 为 `57644273a2cf7e5f7f9bdfdad350cef0f21a99bb5137fcfa0900fc9d62b5b903`，
  coverage SHA-256 为 `7b108bf257cc99e9d4af7a47824b51e79f23e823fc0e1fe6d59fbd47500a8eab`，
  coverage auditor SHA-256 为
  `6fbf0059d76116a9d9bb5d1313223dcc942cadf29c5fcbd3682292fa632f53a6`；
  68/68 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate 为 58/58，
  bad=0，守卫峰值 RSS 为 584.328125 MiB。报告仍为 `complete=false`、175 个
  blocker，符合 `184,548` 字节仍未知、七个全局门均未关闭且 trust anchor 未由
  仓库外提供的事实；复用两套既有 verifier，因此 58/68 分母不变。
- battle-presentation/tile-assets alignment-gap 接入后的正式报告位于
  `build/experiments/active/battle-presentation-tile-assets-alignment-gap-coverage/codex-r1-20260822/formal-report.json`
  （SHA-256 `6839a623b83967b523f6aca76f5f420fcee326ef2fbbc11f19ca91a0a78a03c1`，
  guard SHA-256 `77a31c1b757eb5ab702fcbf62e466a3c91393ecdc027b72a2508ff98e45f34ea`）；
  proof spec SHA-256 为 `dc88f57780fde125b53b1ccffe29cdf1c3d0aecb880f0de30bb4f12f513c0782`，
  coverage SHA-256 为 `66f129450f31eb1ff9f4e931c219a463710b5caee21c0b1aa7f9c4ad3ffe70a6`，
  coverage auditor SHA-256 为
  `2c604c710fc058c7ad9e07653a38385726671ae5940eb54f9b204df1c4567fe4`；
  68/68 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate 为 58/58，
  bad=0，守卫峰值 RSS 为 593.7890625 MiB。报告仍为 `complete=false`、175 个
  blocker，符合 `184,546` 字节仍未知、七个全局门均未关闭且 trust anchor 未由
  仓库外提供的事实；复用两套既有 verifier，因此 58/68 分母不变。
- runtime-state/handler-table alignment-gap 接入后的正式报告位于
  `build/experiments/active/runtime-state-handler-table-alignment-gap-coverage/codex-r1-20260822/formal-report.json`
  （SHA-256 `63520dee7225e55e24dbcb71f5c724dea2cdadeba1a2f5e591edf353dd08a529`，
  guard SHA-256 `ce11dfd822638d1617a148e7856262c7e566efd20000514404930c1442d6eab9`）；
  proof spec SHA-256 为 `b8527d82fb35db5ad53e58fed96c873a95cf9b594c2ffdfba81c2d96434d81e4`，
  coverage SHA-256 为 `a061b3f9fa9551d34f4a3add7b2b062152cc2c2f50f439dd75c210c004e3e1de`，
  coverage auditor SHA-256 为
  `8dccae1f87c4137228551096c1de14878b1d96b7a733be9748598542a410f7c4`；
  68/68 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate 为 58/58，
  bad=0，守卫峰值 RSS 为 616.96484375 MiB。报告仍为 `complete=false`、175 个
  blocker，符合 `184,544` 字节仍未知、七个全局门均未关闭且 trust anchor 未由
  仓库外提供的事实；复用左右两套既有 verifier，因此 58/68 分母不变。
- Cutscene OBJ palette→definition 四处 alignment-gap 接入后的历史正式报告位于
  `build/experiments/active/cutscene-obj-palette-definition-alignment-gap-coverage/codex-r1-20260822/formal-report-retry1.json`
  （SHA-256 `6238a8f64de72cea9e0536d4a72f7b6825d0ea4dc1ac63b888d9516b9544f555`，
  guard SHA-256 `ef9da54d81f0f1fe12e30fabefc6615de1476b274a964b961e9b641458f95ced`）；
  proof spec SHA-256 为 `8b1093446d04cd68f83ef5cf2d978cb618540ca9bf0203ba57ee3487a9fd1ba7`，
  coverage SHA-256 为 `f77fbbf6271d04989c0e16ac36287cf6bcd4d2454d9549eb5fbed693a757c33f`，
  coverage auditor SHA-256 为
  `4908778b32fa5b2fc8473f88a8f3fa44f0541b5c9110d57260c3530ff38d65b4`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  proof spec 共配置 70 个 gate verifier，其中 59 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 69 个
  唯一结构化 contract（59 个 ROM byte 加 10 个 bank），69/69 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 为 59/59，bad=0。守卫耗时
  2530.974 秒、峰值 RSS 616.93359375 MiB。此前同命令的 2700 秒墙钟预算在仍正常
  执行 v9 verifier 时超时，guard SHA-256
  `b66c9b208b228460c8e51f7628bc0c5d430bd16610dcd6c6c1377146de879ce0`；它没有生成
  report，不是 verifier 失败。成功报告仍为 `complete=false`、175 个 blocker，符合
  `184,536` 字节仍未知、七个全局门均未关闭且 trust anchor 未由仓库外提供的事实。
  四段合计 8 字节只证明冻结的 palette stream endpoint 到 rooted definition record
  的精确对齐关系；不声明 padding、reserved/free/allocatable space、自然可达、完整
  Cutscene gap 分母、未知 definition 字段语义、最终像素、编辑或重定位安全。
- positions auxiliary dispatch 接入后的上一里程碑正式报告位于
  `build/experiments/active/positions-aux-proof/codex-r1-20260822/formal-report.json`
  （SHA-256 `e459ab6ae67b944141bbd18e148d1b135daaf557f706efda2f1c159933e76482`，
  guard SHA-256 `20eb2e4e731ba2b193c27b8aa391bc671c2a8d56c77bdcaac69a199af7e9d969`）；
  proof spec SHA-256 为 `384c13515ea65a93e1dea73add93503ea1c159f2126c82ab41ae7dc89395169b`，
  coverage SHA-256 为 `8bf64bbe0e9ca124f867cb7e97af9ee439a89e636450ae54af479985268be6ca`，
  coverage auditor SHA-256 为
  `08f92ffbd7fe5cacb51a15ba5d30436f1467f56cfe35a088596e96788bb98718`。
  proof spec 共配置 71 个 gate verifier，其中 60 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 70 个
  唯一结构化 contract（60 个 ROM byte 加 10 个 bank），70/70 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 60/60、bad=0。守卫峰值 RSS
  639.55859375 MiB。报告仍为 `complete=false`、175 个 blocker，符合 175,320
  字节仍未知、七个全局门均未关闭且 trust anchor 未由仓库外提供的事实。
- battle gameplay sound selector 接入后的上一轮正式报告位于
  `build/experiments/active/battle-sound-selector-proof/codex-r1-20260822/formal-report.json`
  （SHA-256 `6fc14885e20e4e63600d2f04130678cbe16f011d85ae2cb58f8968f36b3706c3`，
  guard SHA-256 `fad0d92819377e6b16cccd6cbbbe8967c7d4eb0ef15b482fdb6bf170be0b3140`）；
  proof spec SHA-256 为 `d235fb19024e62b7f6c7bf6e7c62935e6422e93f3940574c8730034fac8c7ca3`，
  coverage SHA-256 为 `6af3216caf853045b0590389a11abf161e4e489a183f308d940db9e64a67e9b7`，
  coverage auditor SHA-256 为
  `6a2da86067afbb413a355df4d70e4b13b039dd0c213fff47fce5bed4b66107b4`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  proof spec 共配置 72 个 gate verifier，其中 61 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 71 个
  唯一结构化 contract（61 个 ROM byte 加 10 个 bank），71/71 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 61/61、bad=0。审计耗时
  2536.636 秒，守卫峰值 RSS 648.578125 MiB。报告仍为 `complete=false`、175 个
  blocker。该报告对应的 classified/unknown/claim/segment 为
  6,116,392 / 175,064 / 14,310 / 16,402（97.2174% / 2.7826%）；七个全局门仍未关闭，
  trust anchor 也未由仓库外提供。
- battle-condition records 接入后的上一里程碑正式报告位于
  `build/experiments/active/battle-condition-proof/codex-r1-20260822/formal-report.json`
  （SHA-256 `15191084bcf75fa7908708f25d69cb436cd36f99b4815eeecc2926c64c4c8b41`，
  guard SHA-256 `3aeef7dc59c22f965b567641419b27d773cc61fbb30a0abba8f95c6d5caf135f`）；
  proof spec SHA-256 为 `a6032881de87c4faa045fbc5fb15b05043a1971da24a748114da70603f6074b3`，
  coverage SHA-256 为 `dd2a64883da6a5b561336a70d90ceb97a6ca7eb282b3bd09b0f3ec2d9ed0d156`，
  coverage auditor SHA-256 为
  `b81ea9a433d19fe9d64068f79f4ca692ab70764715f22ded46c64e2a6f508039`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  proof spec 共配置 73 个 gate verifier，其中 62 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 72 个
  唯一结构化 contract（62 个 ROM byte 加 10 个 bank），72/72 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 62/62、bad=0。审计耗时
  2,828.498 秒，守卫峰值 RSS 623.84375 MiB。报告仍为 `complete=false`、175 个
  blocker。该报告对应的 classified/unknown/claim/segment 为
  6,119,164 / 172,292 / 14,394 / 16,483（97.2615% / 2.7385%）；七个全局门仍未关闭，
  trust anchor 也未由仓库外提供。该报告已由 v10 coverage/proof 工作副本取代为历史
  基线。
- CFG proven-roots v10 接入后的上一里程碑正式报告位于
  `build/experiments/active/cfg-proven-roots-v10/codex-formal-r1-20260823/formal-report.json`
  （SHA-256 `0d761f8cdc7d21de305af6295d518981a0b6bafb242e5b4e433c83e5a4aeacda`，
  guard SHA-256 `915828bb3b01d54c7c7802ca482d6416df07ce2702e7531e0ee17186a7f94822`）；
  proof spec SHA-256 为 `75d5e48249a3ee200dd8b741faf2c304e390d74614a25c8a161746300d8017e1`，
  coverage SHA-256 为 `c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396`，
  coverage auditor SHA-256 为
  `e440b797a04d8186a854de5d174a46dbcb459e0a0abf515a0249ea4121a23c8f`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  proof spec 共配置 74 个 gate verifier，其中 63 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 73 个
  唯一结构化 contract（63 个 ROM byte 加 10 个 bank），73/73 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 63/63、bad=0。审计耗时
  2,592.267 秒，守卫非降级、峰值 RSS 615.17578125 MiB。报告仍为
  `complete=false`、`claim_status=incomplete`、175 个 blocker。该报告对应的
  classified/unknown/claim/segment 为 6,119,244 / 172,212 / 14,403 / 16,492
  （97.2628% / 2.7372%）；七个全局门仍未关闭，trust anchor 也未由仓库外提供。
- CFG proven-roots v11 接入后的历史正式报告位于
  `build/experiments/active/cfg-proven-roots-v11/codex-formal-r1-20260827/formal-report.json`
  （SHA-256 `9d243886ffed63f211066798f093e796c098d282a83862f11b93da0266478277`，
  guard SHA-256 `0c3f2995be3220231b53de9642ffbcf5d7eb7dc6eb8ce3e8debffc7a9ced60a2`）；
  proof spec SHA-256 为 `acb8bcbd3faf282c40ae2ef807c8f815c95c9aa29ca30a9adcbd892d3c56d1ba`，
  coverage SHA-256 为 `4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd`，
  coverage auditor SHA-256 为
  `e6d072de539ecabfec73857d8352435617dd38bf0a0359924e8db71dda8afac4`，
  formal auditor SHA-256 为
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  proof spec 共配置 75 个 gate verifier，其中 64 个 ROM byte verifier 具结构化
  contract，另 11 个旧 gate verifier 只作哈希绑定证据；正式报告实际执行 74 个
  唯一结构化 contract（64 个 ROM byte 加 10 个 bank），74/74 均
  `exit_code=0`、`contract_ok=true`，ROM byte gate 64/64、bad=0。审计耗时
  2,739.024 秒，守卫非降级、峰值 RSS 616.70703125 MiB。报告仍为
  `complete=false`、`claim_status=incomplete`、175 个 blocker。该报告对应的
  classified/unknown/claim/segment 为 6,119,306 / 172,150 / 14,409 / 16,498
  （97.2637% / 2.7363%）；七个全局门仍未关闭，trust anchor 也未由仓库外提供。
- 任务调度器核心 R4 接入后的上一里程碑正式报告位于
  `build/experiments/active/rom-task-scheduler-core-proof/codex-r1-20260827/formal-report.json`
  （SHA-256 `d975366d63c35c6a62f4e41d9199014828e689273d2d882f43188df519477c9e`，
  guard SHA-256 `e2ae0a75f524e70634b1a318d719e26c6591b4d789d995fb2bb839dd6d34ddc3`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `6fd1fc01e7e52d44510ba66f7d83c5ef64f2d07b27a30554047e87929db955e5`、
  `5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f`、
  `491de8204291f0e41cc4aadb23fbacc54e76cd2435cf52b4274f0fd9b3c32973` 与
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  正式报告实际执行 77 个唯一结构化 contract，77/77 均通过，ROM byte gate
  67/67、bad=0；审计耗时 2,891.251353 秒，守卫非降级、峰值 RSS 646.03125 MiB。
  报告保持 `complete=false`、`claim_status=incomplete`、175 个 blocker；该报告对应的
  classified/unknown/claim/segment 为 6,121,280 / 170,176 / 14,466 / 16,577
  （97.2951% / 2.7049%）的事实。artifact 以独立 raw-control-flow verifier 固定
  116 条 Thumb 指令、264 个指令字节、44 个 PC-relative literal 字节和 308 个
  promotion 字节；138 个已有 owner 字节只保留 provenance，三个两字节间隙继续
  unknown。动态 callback 目标与生命周期、自然可达性、全局 caller/code/indirect
  分母、业务语义、编辑、重定位及 allocatable space 均未声明。
- DirectSound pitch lookup 344-byte 接入后的上一阶段正式报告位于
  `build/experiments/active/rom-directsound-pitch-lookup/codex-r1-20260827/formal-report.json`
  （SHA-256 `9ff9072dc1e501bd6bef9f792f6a318640ea9b8594719effa514288595d4714e`，
  guard SHA-256 `eadf80d080f795495304028e9ee8f4074a1ff34e768571e7152b917b278fe133`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `cf242a73211f4cda07a70c6c3bc0f59d8f5a9c995334d9fecd6bf6b808df2c0a`、
  `922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6`、
  `eb98accbd486377e4d5cf00f2708f7fff75b1b22319ed4dc1d7c24b7abb582d2` 与
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  正式报告实际执行 78 个唯一结构化 contract，78/78 均通过，ROM byte gate
  68/68、bad=0；审计耗时 2,702.786 秒，守卫非降级、峰值 RSS 625.96875 MiB。
  报告保持 `complete=false`、`claim_status=incomplete`、175 个 blocker；该报告对应的
  classified/unknown/claim/segment 为 6,121,624 / 169,832 / 14,471 / 16,582
  （97.3006% / 2.6994%）的事实。artifact 只分类五个冻结范围：16-byte high32
  interwork helper、92-byte closed Thumb consumer、8-byte consumed literals、
  180-byte scale descriptors 与 48-byte frequency table；两个 raw BL producer 仅作
  provenance。自然运行时、全局 caller/code/indirect 或 computed/RAM consumer
  分母、播放行为、编辑、写回、重定位及 allocatable space 均未声明。
- PSG frequency lookup 226-byte 接入后的上一阶段正式报告位于
  `build/experiments/active/rom-psg-frequency-lookup/codex-parent-r1-20260827/formal-report.json`
  （SHA-256 `41f25e7c10aa32136f676145b2191a18245d2205ac888a300c8139890b06e670`，
  guard SHA-256 `dcb342bcfaa4b6ad5ddd523fda985e7cef5389427efaadc55f8cf3df0f94edaa`）；
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `394fe598af8061b578ab9898e1887fba01ad352fd9cb8f4fb18a2f9a8e7afe09`、
  `5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89`、
  `80d182d2fbfefbf68874bb1844e7c3b0e2d6be65f7a4be9d4d9d8e9718bc8d62` 与
  `39c811d770203d36ad9c0137fdd28ed3065e02c1cd405eefdf3fc22a15f2e6f2`。
  正式报告实际执行 79 个唯一结构化 contract，79/79 均通过，ROM byte gate
  69/69、bad=0；审计耗时 2,717.188 秒，守卫非降级、峰值 RSS
  626.12109375 MiB。报告保持 `complete=false`、`claim_status=incomplete`、175 个
  blocker；该报告对应的 classified/unknown/claim/segment 为
  6,121,850 / 169,606 / 14,476 / 16,589（97.3042% / 2.6958%）的事实。
  artifact 只分类五个冻结范围、共 226 bytes；两字节 consumer 对齐间隙和所有未闭合
  producer/业务/自然可达边界继续 unknown 或未声明。
- u8-triplet 19-byte 与 artifact-bound alignment-gap 8-byte 接入后的上一阶段正式报告位于
  `build/experiments/active/rom-artifact-bound-alignment-gaps-v1/codex-parent-r1-20260828/formal-81-after-bundles-report.json`
  （SHA-256 `7afcf333d39951dbe887fcea7f539bc4c70470d20ed986fd93439fefe9410d63`，
  guard SHA-256 `bff0680e5dbf6fefbaa7aad71b1b44105203d98f92e9d011138b3b713f64d10c`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `7110217ad8f33371afb80e0636ea88d665c699eb18c76295ace1e1f55accb735`、
  `17aa05ec2919606ac4728106daf08b3d06a033ccd3c723dc17fd7ad1bdec9ad0`、
  `4a12c51c9d67591f8e528ff8ef9a18d1951f63fea8c415966e49d85bfff7fe8a` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  正式报告实际执行 81 个唯一结构化 contract，81/81 均通过，ROM byte gate
  71/71、bad=0；审计耗时 2,710.326 秒，守卫非降级、峰值 RSS 591.15234375 MiB。
  报告保持 `complete=false`、`claim_status=incomplete`、175 个 blocker，符合
  classified/unknown/claim/segment 为 6,121,877 / 169,579 / 14,482 / 16,591
  （97.3046% / 2.6954%）的事实。四段 artifact-bound gap 独立 verifier/report
  SHA-256 为 `befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
  `344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`；只证明固定
  owner 边界间的 align4 字节，不声明 padding、NOP、reserved/free/allocatable
  space、自然可达、compiler authorship、编辑、写回或重定位安全。
- MPlayMain scheduler 612-byte 接入后的上一阶段正式报告位于
  `build/experiments/active/rom-mplaymain-scheduler-v1/codex-parent-r1-20260828/formal-82-report.json`
  （SHA-256 `34c390e98f367a2e885700fe95db32db9a2736ae8669cfe139524c576d2d9e1d`，
  guard SHA-256 `8ed618bc7b648046cb3c01f3ca3b009f31143b6b74a1bb99a6bf43711de2d906`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `748efea79aa849e0cece4331ada95d3cfb22e3934a8bde6c9b97226922ec5c7e`、
  `2b93df18a7815cb966dad707dfa2ad606049911ae1772a341b57cf2347b58e3b`、
  `ddfb21b28bdf65fff2b5c5de7fb1a891a7aefea0191ee3d31f24932326bfa8dc` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  正式报告实际执行 82 个唯一结构化 contract，82/82 均通过，ROM byte gate
  72/72、bad=0；审计耗时约 2,731.867 秒，守卫非降级、峰值 RSS
  611.7734375 MiB。报告保持 `complete=false`、`claim_status=incomplete`、175 个
  blocker，符合 classified/unknown/claim/segment 为
  6,122,489 / 168,967 / 14,484 / 16,593（97.3143% / 2.6857%）的事实。
  本包只分类 600-byte bounded Thumb code 与 12-byte consumed literals；2-byte
  preowned veneer 保留原 owner，紧邻 2-byte gap 继续 unknown。动态 callback/RAM
  值、callback 生命周期、自然可达、全局 caller/code/indirect/computed producer、
  调度业务语义、编辑、写回、重定位和 allocatable space 均未声明。
- SoundMain relocated-CFG 与三个独立 alignment gap 接入后的上一阶段正式报告位于
  `build/experiments/active/soundmain-relocated-alignment-gap-proof/codex-r1-20260828/formal-report.json`
  （SHA-256 `d2e265e4c7ddc3148eeaa877772246a4944b53f1bfc75c8c97fc99ca5826f8b1`，
  guard SHA-256 `edf30aa3feb13ba7500973c2ecad10a2f7f2c3bfb9c1f47d6f3d4d6d5c48c084`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `c8e18ab374b96962d4b1a65d44bd4a0de85dece8d71e6906f39e0143d9a84604`、
  `31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563`、
  `7cd79b584b8ae43706c97df4c3604d4fcf344288c95052bda7072e7e0ff9a3d4` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  正式报告实际执行 84 个唯一结构化 contract，84/84 均通过，ROM byte gate
  74/74、bad=0；审计耗时 2,866.934973 秒，守卫非降级、峰值 RSS
  597.23046875 MiB。报告保持 `complete=false`、`claim_status=incomplete`、175 个
  blocker，符合 classified/unknown/claim/segment 为
  6,123,419 / 168,037 / 14,493 / 16,600（97.3291% / 2.6709%）的事实。
  source artifact 只分类 916-byte mixed ARM/Thumb code 与 8-byte consumed literals；
  三个后续 2-byte claim 只证明固定 owner 边界与 align4 关系。2-byte preowned return
  veneer 保留原 owner；动态 IWRAM、自然可达、全局 caller/code/indirect/computed
  producer、音频行为、compiler authorship、编辑、写回、重定位和 allocatable space
  均未声明。
- M4A initializer-chain 接入后的历史正式报告位于
  `build/experiments/active/m4a-initializer-chain-proof/codex-formal-r1-20260828/formal-report.json`
  （SHA-256 `8f6761d5f19cb9142caf5338971c4b1712aebf32f6f9cb08d98196b3d4d84c3e`，
  guard SHA-256 `172d4a028aba3bfef2ca9ce9eeef9da8c07bbcf191e3fbe9424774a3a3e03628`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `fcbd2cfb0b930853e82ce171f05d5f16b7019601ac4152e8174b5b6733057977`、
  `ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27`、
  `ad9b9dff40eb06431acb0e9442a3df4432b026cd0318bfe7297f17e0a936f7a2` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  正式报告实际执行 85 个唯一结构化 contract，85/85 均通过，ROM byte gate
  75/75、bad=0；审计耗时 2,805.908073 秒，守卫非降级、峰值 RSS
  588.98828125 MiB。报告保持 `complete=false`、`claim_status=incomplete`、175 个
  blocker，符合 classified/unknown/claim/segment 为
  6,123,937 / 167,519 / 14,499 / 16,608（97.3374% / 2.6626%）的事实。
  六个 primary claim 只分类 390-byte bounded Thumb code 与 128-byte consumed
  literals；`0x061E28` raw producer 和 `[0x09B1E6,0x09B1E8)` gap 继续 unknown。
  动态 RAM/callback、自然可达、全局 producer、音频行为、编辑、重定位和可分配空间
  均未声明。
- MP2K note allocator 接入后的历史正式报告位于
  `build/experiments/active/mp2k-note-allocator-acceptance-20260829/proof-formal-report-r1.json`
  （report / guard SHA-256：
  `46b4b0c9b80b7ef2d8eaff9fb0572370c315d47baa05290d4fb2da327a95e7ce` /
  `7a69b38343c8a1b68392368cd0b130d6817b888fa3b3c90cf445a7d05e54adaa`）。
  86/86 唯一结构化 contract 通过，ROM byte gate 76/76、bad=0；classified /
  unknown / claim / segment 为 6,124,499 / 166,957 / 14,503 / 16,614。
- MP2K dispatcher 接入后的当前正式报告位于
  `build/experiments/active/mp2k-dispatcher-proof-20260829/formal-r1-report.json`
  （report / guard SHA-256：
  `3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0` /
  `b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`）。
  proof spec、coverage、coverage auditor 与 formal auditor SHA-256 分别为
  `823e1b23940044a60fda275772f04e0cef05bf88a5fdd8fe024f53aa17092efa`、
  `22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839`、
  `ea5f1ad59d783c2cd75c1c7eb380c0eacd1c7001532a145e39949ba22f47824f` 与
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`。
  87/87 唯一结构化 contract 通过，ROM byte gate 77/77、bad=0；审计耗时
  3,077.844030 秒，守卫非降级、峰值 RSS 638.47265625 MiB。报告保持
  `complete=false`、`claim_status=incomplete`、175 blockers，符合 classified /
  unknown / claim / segment 为 6,124,601 / 166,855 / 14,507 / 16,617 的事实。
  本包只净分类 102 bytes；完整 bounded CFG 的既有 owner 与两个 2-byte gap 均未被
  扩张声明。
- 当前没有仓库外根摘要 attestation，也没有实体 GBA 与烧录卡证据。

加固前曾执行 23 条“哈希绑定但未声明结构化输出合同”的旧 verifier，得到 21 通过、
2 失败（`menu-ui` 实现哈希漂移、battle-effect 写回实现不匹配）。该结果保留为历史
诊断，不能作为严格完成证明。

因此当前结论是：**逆向工程未达到 100%**。过去的“22/22 runtime identity”或
“32/32 bank closed”只能作为有限调查指标。

## 复核命令

复核当前字节清单和诚实进度：

```bash
python3 tools/audit_rom_byte_coverage.py --root .
python3 tools/audit_reverse_engineering_proof.py \
  --execute-verifiers --allow-incomplete
```

单独要求 ROM 语义完整时，当前命令应返回退出码 2：

```bash
python3 tools/audit_rom_byte_coverage.py \
  --root . --require-semantic-complete
```

最终发布验收必须由签名 tag 或独立 attestation 提供根摘要，并去掉
`--allow-incomplete`：

```bash
python3 tools/audit_reverse_engineering_proof.py \
  --execute-verifiers \
  --trusted-spec-sha256 <外部已发布的64位SHA-256>
```

只有最后一条命令返回 0，输出 `complete: true`、全部 gate 完成、每个结构化合同均
通过，且该根摘要能由独立渠道核对，才允许重新声明“100%”。

## 已知边界

- `state_inventory_complete=true` 只证明不存在未入账地址；
  `semantic_classification_complete=false` 才是当前语义状态。
- 指针可达 LZ77 分母不覆盖非压缩、过程式、未对齐或间接寻址资源。
- `find_similar_tables.py` 的 114 项只是启发式候选分母；当前已逐项可重放裁决为
  60 accepted、26 alias_of、28 rejected、open 0，但候选闭合不能替代全 ROM 语义覆盖。
- 审计输出中的 `trust_anchor.verified=true` 只表示调用方提供的摘要与当前 spec
  相等；审计器不认证摘要发布渠道。签名 tag/attestation 的签名与发布身份必须在
  调用审计器前由独立工具或可信 CI 验证，裸命令行参数本身不是外部真实性证明。
- 哈希证明完整性，不自动证明 verifier 的领域逻辑正确；结构化合同、独立实现、
  负向篡改测试、代码审查和外部根摘要共同构成信任链。
- mGBA 证据不能替代实体 GBA；受控 materialization 也不能冒充自然玩法入口。

## 历史 runtime 样本的离线可移植部分合同

原始捕获的绝对工作树／binary 路径属于历史 provenance；新的离线 verifier 可以在
固定合同中保留并核对它们，同时从当前仓库的 hash-bound archive、ROM、checkpoint
和原解析器重建证据。不得改写旧 manifest 或把旧 guard 的未记录共享锁视为已验证。
新输出必须明确是否执行当前 emulator、是否有零输入对照、实际 record×field 单元和
全部未覆盖分母。可移植验收应在禁止源工作树／历史 binary 读取及进程启动下重放；
结果一致仅证明离线复验可迁移，不证明重采集可重复、全 bank 自然可达或实机结果。
部分 proposal 仍须通过真实 CLI JSON contract，并由原 full-bank gate 保持拒绝。
参见 [data-table-b 1/79 迁移记录](../notes/rom-data-table-b-partial-bank-20261001.md)。

## 固定资源变异矩阵与 release resource gate 的边界

原始资源的内容/物理slot/逻辑reference分母应分别固定，不能把共享alias重复计为新资源。
容量证据身份漂移时，在新收据中用当前实现双重独立重建，再比较除implementation之外
的全部语义；旧收据继续保留并按原合同拒绝。实际写回验收应调用既有 importer/build
CLI，从同一immutable base逐项执行，独立重读所有target alias并比较完整ROM；容量
溢出必须在ROM/report发布前拒绝。无编辑DB的小fixture与完整release clean build分别声明。
固定low-bit等变异全分母通过只证明该变异矩阵，不能提升为任意容量、全部graphics
或其他audio/text/maps/levels/story/characters case。主进程的文件读取审计钩子也不能
宣称覆盖新启动的Python构建子进程。参见 [battle-effect固定矩阵](../notes/rom-battle-effect-fixed-roundtrip-20261001.md)。
