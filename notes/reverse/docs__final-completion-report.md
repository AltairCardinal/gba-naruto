# 木叶战记 GBA 逆向工程完成性报告

**状态日期：** 2026-09-05
**基准 ROM SHA-256：**
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

## 结论

当前逆向工程 **未达到 100%**，不得作为“已完整逆向”验收。

过去的报告曾把静态提取、32 个历史 bank 名称、构建通过和一次运行时命中合并为
“100% complete”。该推导已经撤销：这些指标没有证明全 ROM 字节语义、全记录、
全字段、编辑器端到端、逻辑行为、模拟器回归及实体 GBA 发布兼容性。

当前权威条件见 `docs/reverse-engineering-proof-policy.md`，机器规范见
`sequel/reverse-engineering-proof.json`。严格审计器已经加固为失败关闭：固定 32-bank
分母、从 bank schema 派生记录/字段分母、校验候选与 bank 字节哈希、直接解析 ROM
coverage，并要求外部根摘要、结构化 verifier 合同及真实执行。

## 当前机器审计结果

| 项目 | 当前事实 | 完成要求 | 状态 |
|---|---:|---:|:---:|
| ROM 字节状态入账 | 6,291,456 / 6,291,456 | 全部入账 | 已入账 |
| ROM 字节语义分类 | 6,198,347 / 6,291,456（98.52007230122885%） | 6,291,456 / 6,291,456 | 未完成 |
| 显式未知字节 | 93,109（1.47992769877115%） | 0 | 未完成 |
| 固定 bank 文件/证明绑定 | 32 / 32 | 32 / 32 | 已绑定 |
| 严格 bank 证明完成 | 10 / 32 | 32 / 32 | 未完成 |
| 有效 bank 全记录/字段穷尽 | 0 / 22 | 22 / 22 | 未完成 |
| 有效 bank 直接证据声明记录 | 23 / 2,954 | 2,954 / 2,954 且逐 ID 可重放 | 未完成 |
| 配置哈希绑定旧 verifier 的 bank | 11 / 22 | 22 / 22 | 未完成 |
| 配置结构化 verifier 合同的 bank | 0 / 22 | 22 / 22 | 未完成 |
| 全局完成门禁 | 0 / 7 | 7 / 7 | 未完成 |
| 已执行结构化 verifier | 106 / 106；ROM byte gate 96 / 96；bank 10 / 10 | 全部通过且语义完整 | verifier 通过，语义未完成 |
| 仓库外根摘要 attestation | 0 / 1 | 1 / 1 | 未完成 |
| 实体 GBA 发布验证 | 0 / 1 | 1 / 1 | 外部阻塞 |

“字节状态入账 100%”包含显式 `unknown`，只证明不存在未列入清单的地址区间。
当前保守精确定位的 6,198,347 字节由互不冲突的失败关闭范围组成：

- 角色战斗视觉的 1,299 个源区间：2,023,076 字节；包含 descriptor、组件、帧指针、
  时间线、动画指针、4bpp 图形和 BGR555 调色板，并逐项与 ROM 及导出文件核对；
- MP2K/m4a 的 842 个语义区间：887,018 字节；包含空 sound-ID、song header、
  track stream、tone record 和 DirectSound wave；
- DirectSound pitch lookup 的五个冻结范围：344 字节；包含 16-byte mixed
  Thumb/ARM high32 helper、92-byte closed Thumb consumer、8-byte consumed
  literals、180-byte u8 scale descriptors 与 48-byte（12×u32）frequency table。
  两个 raw Thumb BL producer 仅作 provenance；不声明自然运行时、全局
  caller/code/indirect 或 computed/RAM consumer、播放行为、编辑、写回、重定位或
  allocatable space；
- PSG frequency lookup 的五个冻结范围：226 字节；包含两段共 154-byte 的 bounded
  Thumb consumer code、三条共 12-byte 的 consumed pointer literal 与 60-byte
  channel-4 noise register descriptor table。`0x09B4C6..0x09B4C8` 两字节不由
  PSG artifact 自身声明，而由后述 artifact-bound 独立合同分类；initializer/slot/
  trampoline 只作 provenance，不声明 RAM/computed
  producer、writer、indirect caller、自然可达、另两张表的业务语义、播放、编辑、
  写回、重定位或 allocatable space；
- u8-indexed u8-triplet lookup 的两个冻结范围：19 字节；只包含
  `[0x075C0C,0x075C10)` 的 consumed pointer literal 与 `[0x53DFB0,0x53DFBF)` 的
  五条三字节 raw record。272-byte consumer code 保留 generic CFG owner，四段
  literal pool 和右侧 65 bytes 保持 unknown；不声明业务字段语义、自然可达、编辑、
  重定位或 allocatable space；
- MPlayMain scheduler 的两个冻结 promotion range：612 字节；只包含
  `[0x09A42C,0x09A684)` 的 600-byte bounded Thumb code 与
  `[0x09A688,0x09A694)` 的 12-byte consumed literals。两字节
  `[0x09A684,0x09A686)` `BX r3` veneer 保留既有 owner，紧邻两字节继续 unknown；
  固定 function pointer→RAM callback slot→indirect thunk 只作静态结构绑定，不声明
  动态 callback/RAM 值、callback 生命周期、自然可达、全局 caller/code/indirect/
  computed producer、调度业务语义、编辑、写回、重定位或 allocatable space；
- SoundMain relocated mixed-ISA 的六个冻结 core promotion range：924 字节；只包含
  916-byte ARM/Thumb instruction bytes 与 8-byte consumed literals。CpuSet 实际搬运
  1,024 bytes，但未把整个 copy window 称为代码；既有 2-byte return veneer 保留原
  owner。随后独立 boundary verifier 只分类 `[0x099E1A,0x099E1C)`、
  `[0x099EC2,0x099EC4)`、`[0x099FA6,0x099FA8)` 三个 align4 gap，共 6 bytes。
  不声明动态 IWRAM、自然可达、全局 computed/indirect producer、音频行为、NOP/
  padding、reserved/free/allocatable space、compiler authorship、编辑、写回或重定位；
- M4A initializer-chain 的六个冻结 promotion range：518 字节；只包含三个
  target-limited root 的 390-byte bounded Thumb code 与 128-byte consumed literals。
  三个 direct Thumb BL producer 只作 raw provenance，其中 `0x061E28` 的 4 字节仍
  unknown；`[0x09B1E6,0x09B1E8)` return-to-pool gap 也保持 unknown。不声明 source
  instruction membership、动态 RAM/callback、自然可达、全局 caller/code/indirect/
  computed producer、literal target 语义、音频行为、编辑、写回、重定位或
  allocatable space；
- MP2K note allocator 的四个冻结 promotion range：562 字节；只包含 550-byte
  bounded Thumb code、8-byte consumed literals 与 4-byte initializer-consumed
  entry pointer。四段相邻范围合计 68 bytes 保持 unknown；不声明动态 RAM writer、
  自然可达、全局 caller/code/indirect/computed producer、音频行为、编辑、写回、
  重定位或 allocatable space；
- MP2K dispatcher 的四个冻结 promotion range：102 字节；只包含 86-byte bounded
  Thumb instruction、12-byte ordered table tail 与 4-byte consumed literal。完整
  bounded CFG 的 260 code bytes 中有 174 bytes 已有 owner，另有 64-byte table/8-byte
  literal projection；五段既有 owner 共 238 bytes 只作 provenance。两个 2-byte gap
  保持 unknown，历史 `candidate_027` 的 rejected 状态不变；不声明自然可达、全局
  caller/producer、音频行为、编辑、写回、重定位或 allocatable space；
- task-scheduler 与 PSG 已接受 artifact 边界上的四段 align4 gap：
  `[0x061D62,0x061D64)`、`[0x061D7A,0x061D7C)`、
  `[0x061DEA,0x061DEC)`、`[0x09B4C6,0x09B4C8)`，共 8 字节、4 条 claim。
  独立 verifier 固定左右 owner、raw ROM 与 `gap_end == align4(left_owner_end)`；不把
  它们称为 padding、NOP、reserved/free/allocatable space，也不声明自然可达、
  compiler authorship、编辑、写回或重定位安全；
- 对话字库的 30 个表/源区间：144,416 字节；包含 26 项 SJIS 表、2 项 byte 表、
  4,410 个 8×16 SJIS 字形和 192 个 8×8 byte 字形；页间空洞继续保留为 unknown；
- 冻结 31-row SJIS lookup 表尾的 rows 26..30：40 字节；五个
  `<HBBI>=(0,0,0,0)` empty row 由真实 lookup/parser 合同与完整表分母绑定，只声明
  这些行的结构语义，不声明 padding、reserved/free space、自然运行时、全消费者、
  完整 Unicode、编辑或重定位安全；
- motion-spawn/sequence-descriptor 两字节 4-byte alignment gap：文件
  `[0x0053EF2E,0x0053EF30)` 的 `2` 字节由完整 15×10-byte motion table、显式
  terminator、完整 22×24-byte sequence table、左右 owner 和两套既有独立 verifier
  绑定；不声明 padding、reserved/free space、自然运行时可达、全局不可达、编辑/
  重定位安全、可安全分配、邻接字节或消费者完备性；
- battle-presentation binding/tile-assets 两字节 4-byte alignment gap：文件
  `[0x005A320A,0x005A320C)` 的 `2` 字节由完整 79×10-byte binding table 的
  fixed-count boundary、完整 79×68-byte tile-assets table、左右 owner、末条/首条
  record 和两套 canonical 独立 verifier 绑定；不把左表终点冒充 terminator，也不声明
  padding、reserved/free space、自然运行时可达、全局不可达、编辑/重定位安全、
  可安全分配、邻接字节、额外字段语义或消费者完备性；
- runtime-state selector/handler-pair 两字节 4-byte alignment gap：文件
  `[0x0053E696,0x0053E698)` 的 `2` 字节由完整 256×1-byte selector table 的
  fixed-count boundary、三段左侧既有 owner（保留 LZ77 record 38 primary）、完整
  256×8-byte handler-pair table、精确左右 verifier report 与 ROM 原字节绑定；不声明
  padding、reserved/free space、自然运行时可达、全局不可达、跨表 dataflow、编辑/
  重定位安全、可安全分配、邻接字节、额外字段语义或消费者完备性；
- Cutscene OBJ palette→definition 四处两字节 4-byte alignment gap：文件
  `[0x0012DEFA,0x0012DEFC)`、`[0x0012E442,0x0012E444)`、
  `[0x0012E95E,0x0012E960)`、`[0x0012ED6E,0x0012ED70)` 的 8 个字节由两张
  固定根表、四条独立解析的 palette LZ stream endpoint、alignment equation、rooted
  first definition record、左右 owner 与 ROM 原字节绑定；既有 28-range / 400-byte
  Cutscene source artifact 不变。不声明 padding、reserved/free/allocatable space、
  自然运行时可达、完整 Cutscene gap 分母、未知 definition 字段语义、最终像素、
  编辑或重定位安全；
- positions auxiliary dispatch cell tables：48 groups × 3 variants 的 144 张
  16×4-byte 表，共 2,304 cells / 9,216 bytes；byte 0 只声明 bounded dispatch
  selector，bytes 1..3 只声明 handler-dependent raw operands。完整 current-unknown
  范围、ROM 字节和 handler 读取足迹均由独立 verifier 重建；不声明自然可达、统一
  字段业务语义、runtime group/variant bounds、ABI、编辑/写回/重定位、next header、
  final gap 或 free space；
- battle gameplay sound selector table：`[0x0053E496,0x0053E596)` 的 256×u8
  完整物理表及五条直接 little-endian pointer-literal 消费路径；表范围、ROM bytes、
  base/index/data-load 指令与 consumer window 均由独立 verifier 重建。不声明自然
  全索引/全路径可达、computed/RAM/indirect 消费者穷尽、所有 selector consumers
  穷尽、零/非零或 gameplay 值语义、左邻结构关系、右邻业务关系、完整播放例程、播放
  成功、全部音频穷尽、编辑/写回/重定位或 free/allocatable space；
- battle-condition records current-unknown fragments：完整 47 battles × 3 variants ×
  `0x44`-byte 物理表由独立 verifier 重建，但 coverage 只提升 84 个接入前 unknown
  fragment / 2,772 bytes（41 个 raw variant prefix / 164 bytes，43 个 predicate
  fragment / 2,608 bytes）。既有 fixed-table 与 positions-aux owner 不变，右侧
  144-byte zero gap 继续 unknown；不声明自然可达、全消费者、业务字段语义、handler
  4/5 自然使用、编辑/写回/重定位或 free/allocatable space；
- 启动链的 14 个区间：155,188 字节；包含两张 240×160 BGR555 framebuffer、
  两段显示例程、reset/header、可达 bootstrap、IRQ callback、实际消费 literal 与
  20 字节不可分配填充；`0x0000C4..0x0000C8` 因无可证明入边仍为 unknown；
- 直接 CpuSet→PRAM 的 3 个 BGR555 调色板源：96 字节；
- direct CpuSet/CpuFastSet 完整 12-source 分母中另有 6 个仍为 current-unknown 的
  32-byte BGR555 palette source，经已有独立 verifier 与真实 operation selector 绑定后
  additive 晋升 192 字节；另 6 个 source 保留既有 owner，且不把 32 字节 source 扩张
  为父记录、最终像素、自然可达、可编辑/重定位或 free space；
- 消费者绑定的 305×20 对话表与 1,220 个直接 NUL 目标：24,307 字节；另将全部
  1,219 段、16,814 字节相邻间隙严格分类为对话记录间零填充，但不声明文本语义、
  运行时可达或可安全分配空间；
- 战斗展示文本、三张表及运行时调色板的 83 个区间：2,974 字节；
- 全部 114 条启发式指针表候选的裁决范围中，55 个此前未知的规范区间：6,304
  字节；候选 92 已从错误的 36 槽子区间纠正为完整 38 槽文本指针表，裁决分布为
  60 accepted、26 alias_of、28 rejected，open 为 0；
- tile BG descriptor 绑定的 107 个规范 BGR555 palette 并集：9,984 字节；
- BG canvas 的 14 项 descriptor 表（其中 12 项非空）：224 字节；
- 四张解释器指针表中 200 个非空槽静态可达的 18,994 个节点，精确合并为 92 个
  `chapter_script_record` 区间：334,060 字节；另有 opcode `0x08/0x0E` 引用的
  49 个 speaker-label 仅按 renderer 实际消费到 NUL 的 251 字节计入；
- 11 张消费者绑定的 renderer 文本表共有 704 个槽、625 个唯一 target，按控制感知
  parser 精确计入 22,588 字节；不包含记录间隙，也不冒充 Unicode 解码；
- 固定角色资料表的 46 个指针槽对应 46 条 renderer 可消费记录，共 6,798 字节；
  记录之间 19 段、38 字节双零对齐填充独立分类。当前自然运行时只绑定 ID 0，
  不外推其他 ID 的自然可达、字段语义、Unicode 解码或安全编辑边界；
- 11 张固定消费者文本指针表共有 750 个槽（11 个显式空槽）、735 个唯一 renderer
  target；精确计入 3,000 个表字节和 11,177 个 parser 消费字节，另有 590 段、
  6,738 字节同表零间隙。混合 24 槽 UI
  资源表的文本前缀因无完整索引上界而排除；记录间隙、运行时索引上界、自然玩法
  全槽可达、Unicode 解码与安全编辑边界均不声明；
- 固定 45 槽训练文本命令脚本表中 ID 0 为空，ID 1..44 对应 44 条连续记录；解释器
  与嵌套 renderer grammar 精确界定 2,505 个脚本字节。自然执行每个 ID、Unicode
  解码和安全写回均不声明；
- 固定 38 槽值域选择文本表由 38 对连续 u16 包含范围驱动；coverage 精确计入
  152 字节范围表与 38 条 renderer 消费记录的 862 字节，152 字节指针表由候选
  裁决层唯一拥有。运行时输入上界、全范围自然可达、Unicode 解码和安全写回均不声明；
- 固定 46 行来源域只将其映射到的 46 个文本槽按 renderer 首个 NUL 计入 324
  字节；完整来源记录表 `0x0059F5F0..0x0059F988` 由另一独立 verifier 固定为
  46×20 字节并计入 920 字节，但不为 bytes 2..19 赋予字段语义。独立三路配置域的
  3 个终止列表引用 38 个文本槽，按 copy parser 首个 NUL 计入 316 字节，并计入
  164 字节配置列表和 12 字节指针表；17 个未引用槽、未证实的 63 槽物理分母、
  `0x0059F988` 与相邻 profile 继续保持未声明；
- 固定 10 个 selector consumer source window 共 2,754 字节；独立 artifact 只把其中
  仍属 current unknown 的 19 个不重叠区间、1,252 字节晋升为
  `consumer_code_slice`，其余 1,502 个已有 primary claim 字节保持原分类且不重复
  认领。bridge 与 mapper 窗口的 promotion 均为 0；不声明所有窗口字节都是指令、
  自然玩法可达全部路径、全局 caller 已穷尽，也不声明安全编辑、重定位、可分配空间
  或新字段语义；
- 菜单肖像目录的 74 个资源按 palette 指针/range 固定为 70 段物理 BGR555 数据，
  每段 128 字节，共 8,960 字节；311 个固定逻辑输出排除了 record 0 的 5 个零
  sentinel，唯一共享物理范围 `0x084098C4` 由 5 个资源引用。相同内容但地址不同的
  调色板仍各自保留；不声明动态输入域、全逻辑自然可达、运行时像素等价、独立 alias
  原位编辑、指针改写、重定位、图形字节、相邻间隙或可分配空间；
- 菜单肖像 LZ77 endpoint→palette 起点之间的 52 段、110 字节短零对齐间隙：
  独立 verifier 从固定 896 条 pointer-reachable LZ77、74 个菜单资源与 70 段物理
  palette 完整分母重建左右边界；长度分布为 16×1、14×2、22×3 字节，逐字节为零，
  右端满足 align4。coverage 只声明两侧 artifact-bound 的原始零对齐字节，不称为
  padding、reserved/free/allocatable space，也不声明自然可达、全局不可达、编辑或
  重定位安全；
- tile-BG LZ77 endpoint→palette source 起点之间的 84 段、165 字节短零对齐间隙：
  独立 verifier 从固定 896 条 pointer-reachable LZ77、79 个 tile descriptor、236 个
  palette entry、108 个 raw palette range 与 107 段合并 palette claim 的完整分母
  重建左右边界；长度分布为 31×1、25×2、28×3 字节，逐字节为零且右端 align4。
  两个含非零值的 long gap 与七个 heterogeneous direct-CpuSet/reuse short gap 明确
  排除；不声明 padding、reserved/free/allocatable space、自然可达、全局不可达、
  fixed-consumer 穷尽、最终像素等价、编辑或重定位安全；
- 场景视觉来源范围 verifier 从 `scene-visual-packs-v1` 固定 9-record source table 的
  57 段、88,756 字节完整分母重建 29 段、3,288
  字节候选；pack 5 的 31 字节继续由既有 LZ77 primary claim 拥有，仅将其余 29 段、
  3,257 个 current-unknown 字节晋升。新增 64 字节共享 OBJ palette、2,304 字节 BG
  palette、697 字节 definition record 与 192 字节 animation record；不声明全部来源
  自然可达、最终像素合成、LZ77 新语义、间隙/填充可分配、编辑/重定位或真机等价；
- Cutscene OBJ 来源范围 verifier 从两个固定四记录根表重建 4 个资源 ID、10 个 frame
  和 10 个 animation 的完整来源分母；coverage 只新增 28 段、400 个此前 unknown
  字节：10 段 component definition record（240 字节）、4 张 definition pointer
  table（40 字节）、10 段 animation timeline（80 字节）与 4 张 animation pointer
  table（40 字节）。固定 parser stride、终止符和指针关系均独立复验；不声明未知
  component 字段语义、自然运行时可达、最终场景合成、graphics/palette 扩张、编辑/
  重定位安全、相邻间隙或可分配空间；
- 固定 79 槽战斗消息指针表的两个唯一 literal 消费者均进入相同 renderer/parser；
  79 条记录精确计入 1,411 字节，79 段逐字节为零的记录间隙计入 1,329 字节。
  指针表继续由 `data-table-b` 拥有；不声明全 ID 自然执行、Unicode、安全写回、
  零区可分配性或前置 140 字节；
- 固定 BL→BX pc→ARM B interwork spine 将 `0x08061086` 唯一调用绑定到
  `0x0800024C` ARM 根；独立 ARMv4T worklist 闭合 92 条指令、8 个 block、10 条
  edge、0 个 frontier，并绑定 9 个 literal。该 artifact 新增 368+36+10=`414`
  字节；另一个 additive coverage claim 只分类 spine 跳过的文件
  `[0x0009C56E,0x0009C570)` / GBA `[0x0809C56E,0x0809C570)`：`C0 46` / Thumb
  `MOV r8,r8` 两字节 veneer alignment NOP，同时保留原 artifact scope。完整
  reset-to-root 自然可达、全局不可达、sibling、RAM 目标、编辑/重定位、可分配空间及
  周边区域均不声明；
- sprite-definition 的 43 项 tile-base offset 表：86 字节；不再误称角色 ID/属性表；
- 十三份既有资源 manifest 绑定的 71 个 consumer slice：22,434 字节；可能含 literal
  pool，故只声明为 `consumer_code_slice`，与候选 26 重叠的 128 字节保留其更具体分类；
- 896 条对齐 ROM 指针可达 LZ77：1,733,430 字节；
- 41 条互不重叠、无对齐直接指针的严格 type-`0x10` 流：14,725 字节；只声明
  `lz77_syntax_unbound`，不声明消费者身份、运行时可达、资源用途或图形语义；
- 固定 263-root ARMv4T CFG 与基线 unknown 的交集：74,962 个 Thumb 指令字节；
  独立 raw-encoding verifier 重走 40,872 条入口并保留 366 个 frontier，不声明全局
  函数入口、间接目标或自然运行时可达；
- 29 个固定 v2 Thumb 索引跳转 frontier 从 677 个允许 cell 重建 290 个目标，并以
  189 个既有入口引用和 101 个新入口执行一次性 CFG 扩展；新增闭包 4,698 条指令、
  891 个 block、9,902 个字节，coverage 仅提升其中仍 unknown 的 9,060 个代码字节
  与 112 个允许表 cell 的 448 字节。328 个基线及 15 个新间接 frontier 继续保留；
- 三条全 ROM 目标限定扫描唯一命中的 Thumb BL producer 证明两个新根
  `0x0722A8` 与 `0x081B70`；v2/v3 入口作为 opaque stop，独立闭包包含 6,166 条
  指令、1,203 个 block、12,966 个字节及 259 条回边。coverage 只提升仍 unknown
  的 12,946 个可达字节，并把三条 producer 的 12 字节单列；27 个间接目标与一个
  decode failure 仍保持 frontier，不声明全局代码图或自然运行时执行；
- 第二批五条目标限定 Thumb BL producer 证明 `0x0689A4`、`0x06B49C` 与
  `0x0851F8` 三个根；v2/v3/首批 proven-roots 入口作为 opaque stop，独立闭包包含
  4,809 条指令、835 个 block、9,876 个字节及 82 条 v2 cross-edge。coverage 提升
  全部 9,876 个仍 unknown 的闭包字节并单列五条 producer 的 20 字节；27 个间接
  目标与一个 unsupported instruction 保持 frontier，不声明全局代码图或自然执行；
- proven-roots v3 至 v7 继续用固定 producer 或完整 dispatcher 分母闭合有限根增量；
  v7 接入后累计 CFG promotion 为 141,680 个可达 Thumb 字节，所有未解析间接目标
  均保留为 frontier；
- proven-roots v8 从已验真的 scene visual source closure 固定唯一
  `0x0808BE5C→0x0808B99C` Thumb BL，独立重建 113 条指令、20 个 block、246 字节、
  10 条 baseline cross-edge 和 1 个间接 frontier。producer 与 source consumer
  已有分类而不重复认领；接入后 CFG 可达 Thumb 字节为 141,926；
- proven-roots v9 冻结 battle-controller CFG provenance 的完整 target-limited
  分母：11 条对齐 Thumb BL 中 9 条是 controller artifact 的真实 source
  instruction，证明 8 个 root；`0x0736A4`、`0x07445C` 两条合法 BL 只保留为
  excluded provenance。独立 verifier 重建 299 条指令、62 个 block、628 字节、
  16 条 baseline cross-edge、7 个 opaque return 与 0 个真正 frontier。coverage
  只晋升 62 个完整 current-unknown block；两条 excluded producer 继续 unknown，
  接入后 CFG 可达 Thumb 字节为 142,554；
- proven-roots v10 固定全 ROM 三条 target-limited Thumb BL producer 分母，独立重建
  source bounded worklist 264 instructions / 35 blocks / 580 bytes / 26 external call
  edges / 0 frontier，以及 `0x08B278` target worklist 36 instructions / 7 blocks /
  72 code bytes / 0 frontier；两条实际 PC-relative LDR 另消费 8 literal bytes。
  coverage 只晋升 7 个完整 current-unknown 代码 block 与 2 个完整 literal claim，
  共 80 字节；接入后 CFG 可达 Thumb 字节为 142,626。该合同不外推自然运行时可达、
  全局代码图、间接目标穷尽、函数 ABI、业务语义、编辑/重定位或 free space；
- proven-roots v11 从九条 raw target-limited Thumb BL 中固定八条已证 source
  producer，闭合 `0x080633C0` 的 62-byte target；第九条保持 excluded provenance。
  proven-roots v12 又从冻结 battle-effect source 闭包证明唯一
  `0x08061416 -> 0x08064478` producer，只晋升四段 372-byte Thumb code 与四段
  128-byte consumed literals，两个 2-byte hole 保持 unknown。v12 immutable bundle
  不读取 live coverage；两批均不声明自然运行时可达、全局 caller/code/indirect 或
  computed target 分母、业务语义、编辑、写回、重定位或 free space；
- proven-roots v13 证明固定目标 `0x080651F8` 的全 ROM target-limited 直接
  producer 分母只有 `0x080614D0` 一条 Thumb BL。target 只晋升三段 312-byte
  Thumb code 与三段 80-byte consumed literals；两个 2-byte hole 保持 unknown，
  `0x065368 bx r0` 保持唯一 unresolved indirect-PC frontier。immutable wrapper
  在动态加载 legacy verifier 前后均独立锚定运行时依赖；该合同不声明 structured
  return、自然运行时可达、全局 caller/code/indirect/computed target 分母、业务
  语义、编辑、写回、重定位或 free space；
- parser-bound additive coverage 复用独立 parser verifier，晋升 142 段、198 字节
  逐字节零填充；v3 sparse dispatcher 与 v7 indexed dispatcher 又分别晋升 8 个/
  32 字节和 9 个/36 字节完整表单元。三项都要求 whole-range current unknown，
  不声明运行时选择、target 可达、编辑/重定位或 free space；
- 九份既有 artifact 的独立 verifier、固定哈希与真实 JSON selector 共同绑定 37 个
  baseline-unknown claim、3,919 字节；其中表数据不冒充代码，consumer slice 不冒充
  instruction-only，staged GPU 只贡献代码窗口而不把 RAM 输出称为 ROM 原始资源；
- battle-effect sprite 既有 artifact 的固定 source 分母新增 237 个完整 claim、
  11,120 字节：178 段 component list（9,452 字节）、18 张 definition pointer table
  （712 字节）、23 段 animation timeline（864 字节）和 18 张 animation pointer table
  （92 字节）；每段完整落在接入前 unknown，未声明自然运行时可达、图形/调色板扩张、
  可编辑空间或写回安全；
- 引用文本槽 NUL 后结构零填充新增 133 个完整 claim、1,255 字节：46 个 direct
  selector 槽 550 字节、38 个 configured selector 槽 368 字节、49 个脚本实际引用
  speaker-label 槽 337 字节；不认领未引用槽、NUL/前缀、文本语义、自然可达、编辑/
  写回安全或可安全分配空间；
- 22 个非空 bank 的固定记录范围：348,018 字节；
- `0x5DFBEC..0x600000` 精确 `0xFF` 尾区：132,116 字节。

## 全局完成门禁

| 门禁 | 状态 | 当前边界 |
|---|---|---|
| 全 ROM 字节语义 | partial | 2.603467% 仍未知；固定 root、一次性扩展及 proven-roots v1–v15 仍不是全局 ARM/Thumb code map；114 条候选均已裁决（60 accepted、26 alias、28 rejected），开放 0 条 |
| 资源 round-trip | partial | 七类图像样本已绑定；未穷尽图像、音频、文本、地图、剧情、角色全部资源 |
| 编辑器 round-trip | partial | DB 镜像/补丁生成通过；无四类编辑器 UI→ROM→启动矩阵 |
| 逻辑修改 | partial | 离线补丁通过；无菜单/战斗全行为回归 |
| 干净重建 | partial | 常规 build suite 通过；无固定依赖 clean-clone 重建 |
| mGBA 回归 | partial | 存在受守卫样本；无完整发布矩阵 |
| 实体 GBA | blocked_external | 当前环境没有真机、烧录卡和硬件报告 |

当前 formal proof 配置 84 个哈希绑定且具结构化 JSON 合同的 ROM byte gate verifier；
2026-08-30 的 tile-BG LZ77→palette gap 里程碑受守卫正式审计共执行
94 个唯一结构化 contract，94/94 均为 `exit_code=0`、`contract_ok=true`。以下编号
保留已建立的关键类别索引；当前精确分母、
命令、脚本哈希与断言以 `sequel/reverse-engineering-proof.json` 为准：

最新报告位于
`build/experiments/active/tile-bg-lz77-palette-gap-preflight-20260830/proof-formal-r1/formal-report.json`
（SHA-256 `37ef4055b419cb520e3bbaf953ca81f3ae72fdc2613032235498ec298dc87832`），
guard SHA-256 为 `7d7fd44829fa1359c619182f2103b3856d359a63dc6f143113a10eb850592779`；
proof spec SHA-256 为 `b7423201e3f84280c5556d8d42b95de6c03c07fefcfc85f3d05bf71d5c614c57`，
coverage SHA-256 为 `1ddc10027b7642399bce8c1a07871ce3a141ca6f2b323c19a650469274cb2df4`，
coverage auditor SHA-256 为
`9075985f53c263619da34c24c9e0d15a1e2abec0c120a5094b0759397411b230`，
formal auditor SHA-256 为
`59ffdd85782c5127db1a545e49a5c0daa48e0033eb7c3b5196a4c492817b8c33`；
ROM byte gate 为 84/84、bank contract 10/10、bad=0，guard 峰值 RSS 为
692.83984375 MiB、非降级，耗时 3,263.08749 秒。proof spec 共配置 95 个 gate verifier
引用；formal executor 去重共享命令后实际执行 94 个唯一命令，因此不能把 95 个配置
引用写成 95 次执行。menu-gap 与 V15 formal 保留为历史里程碑，不能用其 coverage 或 proof
身份覆盖当前文件。
报告仍为 `complete=false`、`claim_status=incomplete`、177 个 blocker；这不是 100%
完成证明。

本轮 motion-spawn/sequence-descriptor alignment-gap 已闭合并由上述正式审计验收；
classified/unknown/claim/segment 分别为 6,106,908 / 184,548 / 14,159 / 16,257。
它只证明精确两字节的表间 4-byte 对齐语义，全局完成状态仍为 partial。

随后接入的 battle-presentation binding/tile-assets alignment-gap 已完成正式 coverage、
proof 与上述 formal 合同：classified/unknown/claim/segment 分别为
6,106,910 / 184,546 / 14,160 / 16,257，coverage/auditor/proof SHA-256 分别为
`66f129450f31eb1ff9f4e931c219a463710b5caee21c0b1aa7f9c4ad3ffe70a6`、
`2c604c710fc058c7ad9e07653a38385726671ae5940eb54f9b204df1c4567fe4`、
`dc88f57780fde125b53b1ccffe29cdf1c3d0aecb880f0de30bb4f12f513c0782`。
正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；全局完成状态仍为 partial。

此前接入的 runtime-state selector/handler-pair alignment-gap 也已完成正式 coverage、
proof 与 formal 合同：classified/unknown/claim/segment 分别为
6,106,912 / 184,544 / 14,161 / 16,257，coverage/auditor/proof SHA-256 分别为
`a061b3f9fa9551d34f4a3add7b2b062152cc2c2f50f439dd75c210c004e3e1de`、
`8dccae1f87c4137228551096c1de14878b1d96b7a733be9748598542a410f7c4`、
`b8527d82fb35db5ad53e58fed96c873a95cf9b594c2ffdfba81c2d96434d81e4`。
正式审计 68/68、ROM byte gate 58/58、bad=0、175 blockers；report/guard SHA-256
分别为 `63520dee7225e55e24dbcb71f5c724dea2cdadeba1a2f5e591edf353dd08a529` /
`ce11dfd822638d1617a148e7856262c7e566efd20000514404930c1442d6eab9`，完整 proof
测试 49/49 通过。全局完成状态仍为 partial。

上一轮接入的 Cutscene OBJ palette/definition 四处 alignment-gap 已完成独立 verifier、
coverage、proof 与 formal 合同：classified/unknown/claim/segment 分别为
6,106,920 / 184,536 / 14,165 / 16,257，coverage/auditor/proof SHA-256 分别为
`f77fbbf6271d04989c0e16ac36287cf6bcd4d2454d9549eb5fbed693a757c33f`、
`4908778b32fa5b2fc8473f88a8f3fa44f0541b5c9110d57260c3530ff38d65b4`、
`8b1093446d04cd68f83ef5cf2d978cb618540ca9bf0203ba57ee3487a9fd1ba7`。
正式审计 69/69 唯一结构化 contract 全部通过，ROM byte gate 59/59、bad=0、175
blockers；report/guard SHA-256 分别为
`6238a8f64de72cea9e0536d4a72f7b6825d0ea4dc1ac63b888d9516b9544f555` /
`ef9da54d81f0f1fe12e30fabefc6615de1476b274a964b961e9b641458f95ced`。全局完成状态仍为
partial。

此前接入的 positions auxiliary dispatch 已完成 artifact、coverage、proof 与 formal
合同：classified/unknown/claim/segment 分别为
6,116,136 / 175,320 / 14,309 / 16,401。144 张 16×4-byte 表只声明有限的 cell
dispatch/raw-operand 语义；不外推自然可达、统一业务字段、ABI、编辑/写回/重定位或
free space。正式审计 70/70、ROM byte gate 60/60、bad=0、175 blockers；全局完成
状态仍为 partial。

此前接入的 battle gameplay sound selector 已完成 artifact、coverage、proof 与 formal
合同：classified/unknown/claim/segment 分别为
6,116,392 / 175,064 / 14,310 / 16,402。`[0x0053E496,0x0053E596)` 的 256×u8
表只声明固定物理范围及五条直接 pointer-literal 消费路径，不外推自然全索引/全路径
可达、computed/RAM/indirect 消费者穷尽、所有 selector consumers 穷尽、值或 gameplay
语义、左邻结构关系、右邻业务关系、完整播放例程、播放成功、音频资源穷尽、编辑/
写回/重定位或 free space。正式审计 71/71、ROM byte gate
61/61、bad=0、175 blockers；全局完成状态仍为 partial。

随后接入的 battle-condition records 已完成 artifact、coverage、proof 与 formal
合同：完整物理表为 47 battles × 3 variants × `0x44` bytes、共 1,128 predicate
slots；coverage 只新增 84 个接入前 current-unknown fragment / 2,772 bytes，其中
41 个 raw variant prefix 共 164 bytes、43 个 predicate fragment 共 2,608 bytes。
既有 fixed-table 与 positions-aux primary owner 均保留，右侧
`[0x00596CCC,0x00596D5C)` 的 144-byte zero gap 继续 unknown。接入后
classified/unknown/claim/segment 为 6,119,164 / 172,292 / 14,394 / 16,483；不外推
自然 battle/variant 可达、全消费者穷尽、prefix/predicate 业务语义、handler 4/5
自然使用、编辑/写回/重定位或 free space。正式审计 72/72、ROM byte gate 62/62、
bad=0、175 blockers；全局完成状态仍为 partial。用户已要求在此里程碑后暂停，收到
明确恢复指令前不得继续新逆向写入。

随后接入的 CFG proven-roots v10 已完成标准受管 artifact promotion、coverage、proof
与 formal 合同：固定三条全 ROM target-limited Thumb BL producer 分母，独立重建
source `264/35/580/26/0` 与 target `36/7/72/0`，并绑定 8 literal bytes。coverage
只新增 7 个代码 block 与 2 个 literal claim，共 80 个接入前 current-unknown bytes；
classified/unknown/claim/segment 为 6,119,244 / 172,212 / 14,403 / 16,492。
正式审计 73/73、ROM byte gate 63/63、bad=0、175 blockers；全局完成状态仍为
partial。该暂停点已被用户 2026-08-27 的明确恢复指令取代，仅保留为历史收据。

随后 DirectSound pitch lookup 已用实际 344-byte 合同取代旧 318-byte/90-byte
候选估计，并完成 canonical artifact、coverage、proof 与 formal。五个范围为
16-byte high32 interwork helper、92-byte closed Thumb consumer、8-byte consumed
literals、180-byte scale descriptors 与 48-byte frequency table；两个 raw BL
producer 仅作 provenance。接入后 classified/unknown/claim/segment 为
6,121,624 / 169,832 / 14,471 / 16,582。正式审计 78/78、ROM byte gate 68/68、
bad=0、175 blockers；全局状态仍为 partial。下一优先候选为 PSG noise lookup 的
最多 220 个 current-unknown 字节，须先闭合 producer、CFG/literal 与完整索引域。

PSG frequency lookup 随后以实际 226-byte 合同完成 canonical artifact、coverage、
proof 与 formal。五个 promotion range 精确覆盖 154-byte bounded Thumb code、
12-byte consumed literals 与 60-byte noise descriptor table；两字节对齐间隙仍为
unknown。接入后 classified/unknown/claim/segment 为
6,121,850 / 169,606 / 14,476 / 16,589。正式审计 79/79、ROM byte gate 69/69、
bad=0、175 blockers；该段仅保留为历史收据。

u8-triplet 19-byte 与 artifact-bound gap 8-byte 随后都完成 canonical coverage、
proof 与 formal。该历史里程碑的 classified/unknown/claim/segment 为
6,121,877 / 169,579 / 14,482 / 16,591；正式审计 81/81、ROM byte gate 71/71、
bad=0、175 blockers，全局状态仍为 partial。artifact-bound verifier/report SHA-256
为 `befdf8545a0d2763514996935676a1a6384967174dcca119e0da62b71bd4da66` /
`344e3fe2660a48342b5f82bb9d7aeefc28c1f4fe0b99fc3f23bdb2a894f3f662`。

MPlayMain 随后按修正版 612-byte 合同完成 canonical artifact、coverage、proof 与
formal。该历史里程碑的 classified/unknown/claim/segment 为
6,122,489 / 168,967 / 14,484 / 16,593；正式审计 82/82、ROM byte gate 72/72、
bad=0、175 blockers，全局状态仍为 partial。

SoundMain relocated source 与三个独立 alignment gap、M4A initializer-chain、MP2K
note allocator 及 MP2K dispatcher 随后均完成；前述各段保留为历史基线。该阶段
classified/unknown/claim/segment 为 6,124,601 / 166,855 / 14,507 / 16,617；
正式审计 87/87、ROM byte gate 77/77、bad=0、175 blockers。report/guard SHA-256 为
`3321709fa8440c8857d895b1cb467a3959989be0cc639abfe439bdb91e43ddc0` /
`b6e177ccff24a0cb19ad6e500968c4905bae3a0758abd466a2174cfd4bf8d036`。
CGB helper、CgbSound 与 13 段独立 artifact-bound gap 随后净晋升 1,282 bytes，
历史里程碑为 6,125,883 / 165,573 / 14,544 / 16,654；正式审计 88/88、ROM byte
gate 78/78、bad=0、175 blockers。整个 1,960-byte CGB/PSG 包络仍不得当作单一连续
代码区，`0x061F14 -> 0x09BA68` 草案因 source membership 未闭合而保持 unknown。

历史 CFG proven-roots v12 immutable bundle 曾净晋升 500 bytes：372-byte Thumb
code 与 128-byte consumed literals；两个 2-byte hole 保持 unknown。V12 接入后
classified/unknown/claim/segment 为 6,126,383 / 165,073 / 14,552 / 16,665；
正式审计 89/89、ROM byte gate 79/79、bad=0、175 blockers。report/guard SHA-256 为
`961ace784373243954097418880fdbf52419385b2e34f62a136f7920b032306a` /
`53546d31216f134a9e22cddfb79fb2e01cd9642e494e4429eb0b2ebe4e6ab0eb`；报告仍为
`complete=false`，不得把本次合同全过扩张为全 ROM 100%。

CFG proven-roots v13 随后净晋升 392 bytes：312-byte Thumb code 与 80-byte
consumed literals；两个 2-byte hole 以及 `0x065368 bx r0` 间接目标保持未闭合。
V13 接入后 classified/unknown/claim/segment 为
6,126,775 / 164,681 / 14,558 / 16,673（97.3825% / 2.6175%）；正式审计
90/90、ROM byte gate 80/80、bad=0、175 blockers。report/guard SHA-256 为
`6bced154df1d4ca3940f597f64ef36bb5ebd8c3f9d995f62fce34ad92b8793c2` /
`23893d0b4996fac334cc4b93596e1e3a28ee5cc7302636c5abd5b8b34037d369`；报告仍为
`complete=false`，不能由局部合同全过推导全 ROM 100%。

CFG proven-roots v14 随后由五条 V12/V13 accepted producer 证明 `0x0624C0` 与
`0x062510` 两个根，净晋升 160 bytes：120-byte Thumb code 与 40-byte consumed
literals，共 60 instructions、10 blocks、4 ranges、0 hole；`0x0624FE bx r0` 与
`0x062546 bx r0` 保持两个 unresolved indirect-PC frontier。manifest / payload /
coverage SHA-256 分别为
`666772f43529a5578414c5b749e16ea8733a755a0a818e86cea81bd86d57091d`、
`d99c0cdc367637b62754b941926e22d09bef08f9a3e89817fbf42dafc0a7edff`、
`2592ce481515af301ef5ce4078d3e9101793bf790f1bc90a6d33d5a06c207317`。
V14 接入后 classified/unknown/claim/segment 为
6,126,935 / 164,521 / 14,562 / 16,677（97.385009% / 2.614991%）。综合 CFG registry
同时修正旧手写 allowlist 漏计，当时为 956 ARM、148,380 Thumb 与 32 producer
bytes，合计 149,368 promoted bytes、3,829 primary claims、32 code kinds；registry
SHA-256 为
`d57f6b22f597eb6cfcad6a746122870917fbc24b0e70a885a432a57c729a227f`。
formal-r2 为 91/91、ROM byte gate 81/81、bank contract 10/10、bad=0；report/guard
SHA-256 为
`f9c2a1014b62dc7449db7f35965a1d42db01eb4972e43c81d961688e0befa786` /
`3786c8d4e51c8070a021064433535429dc22efe5dcfb84ae4e156fe1039d7fa4`。
报告仍为 `complete=false`、175 blockers；formal-r1 的旧 aggregate 已被 r2 取代。
本包不声明自然运行时可达、全局 caller/producer/code 或 indirect/computed/RAM target
分母、callee ABI/业务语义、literal 含义、相邻 padding/free、编辑、写回或重定位。

CFG proven-roots v15 随后从固定 producer 分母接受 `0x0611F4`、`0x0618FC`、
`0x08B6F0`、`0x09A3E0` 四个根，并失败关闭地拒绝 `0x09C0F4`。四个根净晋升
450 bytes：398-byte Thumb code 与 52-byte consumed literals，共 197 instructions、
31 blocks、10 promotion claims；386-byte hole、3 个 indirect-PC frontier 与 2 条
external edge 保持未闭合。manifest / payload SHA-256 分别为
`7fb00210d8347df1935d6997afa66183d6cbaa4d7d26208f744256e09f11755f`、
`5786c04ae36d78957705175dfce38da190bb29682c640c6821bb44ec4c321cd2`。
V15 接入时 classified/unknown/claim/segment 为
6,127,385 / 164,071 / 14,572 / 16,693（97.392162% / 2.607838%）。综合 CFG registry
为 956 ARM、148,778 Thumb 与 32 producer bytes，合计 149,766 promoted bytes、
3,835 primary claims、33 code kinds；registry SHA-256 为
`10ae3cc720e787630957b7cbbbbae379ec5f3e542dbabeb871df861915a676b`。
修复隔离环境继承后，formal-r2 为 92/92、ROM byte gate 82/82、bank contract
10/10、bad=0；report/guard SHA-256 为
`3002d624f4a5354c4bf0f410aa7923c8377c33e96c263d6df6299ef67deefb63` /
`b10f03289ab3b941a3bb3d0dd30edc806816dc5a262224ec5137a28e94ada220`。
报告仍为 `complete=false`、177 blockers；四个已接受根的局部合同全过不能扩张为
自然运行时可达、全局 caller/producer/code、间接目标、ABI/业务语义、相邻 padding、
可编辑、可写回、可重定位或全 ROM 100%。

随后 menu portrait LZ77→palette gap 独立合同净晋升 52 段、110 字节，canonical
classified/unknown/claim/segment 更新为
6,127,495 / 163,961 / 14,624 / 16,693（97.393910% / 2.606090%）。正式 report /
guard SHA-256 为
`92b4b471b972bcc789848f78192f8c5162deeeb0ab0c1bce77e818694e88ba3a` /
`e0985d49922e2473229c8c28c4182013e9497718977e07807a52885e76b2b66e`；
93/93 个实际唯一命令、ROM byte gate 83/83、bank contract 10/10 全部通过，bad=0。
报告保持 `complete=false`、177 blockers；该局部闭环同样不是 100% 完成证明。

随后 tile-BG LZ77→palette gap 独立合同净晋升 84 段、165 字节，canonical
classified/unknown/claim/segment 更新为
6,127,660 / 163,796 / 14,708 / 16,693（97.396533% / 2.603467%）。正式 report /
guard SHA-256 为
`37ef4055b419cb520e3bbaf953ca81f3ae72fdc2613032235498ec298dc87832` /
`7d7fd44829fa1359c619182f2103b3856d359a63dc6f143113a10eb850592779`；
94/94 个实际唯一命令、ROM byte gate 84/84、bank contract 10/10 全部通过，bad=0。
报告保持 `complete=false`、177 blockers；两个非零 long gap 与七个 heterogeneous
short gap 仍在合同外，该局部闭环同样不是 100% 完成证明。

随后 boot Thumb code→consumed-literal alignment gap 独立合同净晋升 12 段、24 字节，
canonical classified/unknown/claim/segment 更新为
6,127,684 / 163,772 / 14,720 / 16,693（97.396914% / 2.603086%）。正式 report /
guard SHA-256 为
`b98828aa94f6704cca82bca876b9154f5e950fc1afcd2df535f7e833f98d00d8` /
`75afa7d5f183e08f4efb064d7fb0aadcfd4869694643871d7e096b2f8e3fcab0`；
95/95 个实际唯一命令、ROM byte gate 85/85、bank contract 10/10 全部通过，bad=0。
报告保持 `complete=false`、177 blockers；该收据只证明 12 个冻结边界，不外推 boot
包络、padding、自然可达或可编辑性。后续不再为几十字节单包重复完整 formal，而应先
批量聚类 unknown 并在里程碑合并审计。

1. 896 条对齐指针可达 LZ77 清单通过；
2. MP2K/m4a 的 842 个语义区间及 318 字节显式间隙通过独立解析；
3. 对话字库的 4,602 个逻辑字形、9,012 个物理半字块、4 份 atlas 与 3 个布局消费者通过独立重建；
4. 两张启动 framebuffer 及 reset→DMA3→Mode-3→原入口的 ARM 显示链通过独立指令级重建；
5. 41 条不重叠严格 type-0x10 流的语法、零对齐直接指针、重叠淘汰规则和双 bundle 通过；它们已按 `lz77_syntax_unbound` 接入覆盖，但因无 consumer，不升级为资源、图形或运行时可达声明；
6. 全 ROM 指针表启发式扫描的 114 条固定分母，以及 60 accepted、26 alias、28 rejected 的 114 条裁决通过；无开放项；
7. direct CpuSet/CpuFastSet 的 146 个调用点、完整 12-source 分母、6 个新增 32-byte
   palette source 与 6 个 preowned source 通过反向消费者和 additive coverage 验证；
8. 305 行对话表与 1,220 个直接 NUL 目标通过逐指针、逐字节独立验证；
9. battle presentation 的 79 条消息、三张表和 palette 范围通过窄验证器；
10. tile BG 的 79 个 descriptor、236 个完整 layer 与 108 个 atlas 通过；
11. 24 条 story scene timeline 通过；
12. battle presentation 的 79 条消息与 172 个 glyph 通过完整验证器；
13. 75 条 battle visual runtime timeline 通过；
14. battle-effect sprite 的 18 组、178 帧、437 个 component 与 23 个 animation 通过；
15. battle-effect 的 256/87/94 条绑定及 22 条 sequence 通过；
16. 角色战斗视觉的 558 个槽、250 项资源、2,004 帧、2,190 个 component、784 个
    animation 与 3,187 个 keyframe 通过；
17. BG resource canvas 的 12 / 12 个非空画布及其 descriptor/loader 消费链通过；
18. overview gradient 的 600 个精确 tilemap cell 及 generator/caller/controller 通过；
19. 9 份 scene visual composite 及其 controller/运动/加载消费者通过；
20. 7 份 residual WRAM tilemap source ABI 与 0 个遗留未决项通过；
21. GPU copy queue 的 14 个直接 caller 及队列消费者通过；
22. portrait palette opcode `0x17` 的 161 条记录及 transition/dim 消费链通过；
23. 章节脚本清单从四张固定根表独立重走 18,994 个节点，92 个合并区间共
    334,060 字节逐段与 ROM 及顺序 bundle 相等，解析失败为 0；
24. sprite-definition 的 43 项 tile-base offset、45 个 component、43 个 asset 与
    49 个 tile 通过完整运行链独立复验；
25. 11 张 renderer 文本表的 625 个唯一 target、22,588 字节及 speaker-label 的
    251 个 parser-consumed 字节均通过独立重建；
26. 固定 263-root CFG 以独立 ARMv4T raw-encoding oracle 重走 40,872 条指令入口，
    86,184 个指令字节、7,725 个 basic block 与 366 个 frontier 全部闭合复验；
27. 一次性 CFG 扩展从固定 29 个 v2 frontier 的原始指令与 677 个允许表 cell 重建
    290 个目标，独立闭包精确复验 101 个新入口、4,698 条指令、891 个 block、
    9,902 个字节与 16 个新 frontier；
28. 对话零填充 verifier 从固定 ROM 的 305×20 指针表独立重建 1,220 个 NUL 目标，
    证明全部 1,219 段相邻间隙共 16,814 字节均为零；
29. 角色资料文本 verifier 从固定 46-slot 指针表、真实消费者和 renderer 桥接独立
    重建 46 条记录、6,798 个消费字节及 19 段、38 字节双零对齐填充；
30. 固定消费者文本 verifier 从 11 张固定表的真实索引消费者与 renderer/parser 链
    独立重建 750 个槽（11 个显式空槽）、735 个唯一记录、3,000 个表字节和 11,177
    个消费字节，并排除缺少文本索引上界的混合 UI 资源表；
31. 训练文本 verifier 从固定 45 槽表、真实索引消费者、14 项 opcode dispatch 与
    嵌套 renderer grammar 独立重建 44 条记录、264 条命令和 2,505 个脚本字节；
32. 值域选择文本 verifier 从固定 38 槽指针表、38 对连续包含范围、真实消费者与
    renderer/parser 桥接独立重建 38 条记录、862 个文本字节和 152 个范围表字节；
33. selector 文本 verifier 从固定 46 行枚举器和独立三路配置 selector 重建 46 个
    direct 槽、38 个 configured 槽、640 个 parser 消费字节与 176 个配置结构字节，
    并拒绝把 NUL 后零后缀、17 个未引用槽或 63 槽观察区提升为已分类；
34. selector direct 来源记录 verifier 从 producer、46-row 向量、19 字节目标槽
    stride 计算链、6 个 renderer bridge 调用和 bridge→parser 调用独立重建
    `0x0059F5F0..0x0059F988` 的 46×20 字节记录分母；
35. 战斗消息文本 verifier 从 79 槽固定表、两个 table literal 消费者、wrapper、
    bridge 与 renderer/parser 独立重建 79 条记录的 1,411 字节，并证明全部 79 段
    记录间隙共 1,329 字节为零；
36. boot interwork verifier 从唯一 Thumb BL、`BX pc` 与 ARM B 重建 `0x0800024C`
    的 92 条 ARM 指令、8 个 block、10 条 edge、9 个 literal 与 414 字节精确声明；
    coverage auditor 另以相同冻结 producer chain 和 verifier 身份只分类被 spine 跳过的
    `C0 46` / Thumb `MOV r8,r8` 两字节 alignment NOP；
37. direct-call-proven CFG verifier 从三条固定 Thumb BL producer 重建两个新根，
    在 v2/v3 opaque stop 下精确复验 6,166 条指令、1,203 个 block、12,966 字节、
    28 个 frontier 与 259 条基线 cross-edge；
38. 第二批 direct-call-proven CFG verifier 从五条固定 Thumb BL producer 重建三个
    新根，在 v2/v3/首批 proven-roots opaque stop 下精确复验 4,809 条指令、835 个
    block、9,876 字节、28 个 frontier 与 82 条 v2 cross-edge；
39. ROM byte-state 清单可重复且全字节入账；当前状态合同如实断言
    `semantic_classification_complete=false` 并通过。单独要求
    `--require-semantic-complete` 时仍按设计返回退出码 2。
40. 第三、四批 direct-call-proven CFG 从 6 条固定 Thumb BL producer 重建
    `0x070DF8` 与 `0x07305C` 两个根，独立复验 538 条指令、126 个 block、
    1,154 个新增代码字节；v4 的 6 个间接 PC frontier 保持开放。该 v4 历史里程碑时
    ROM 语义覆盖为 6,020,083 / 6,291,456（95.6866%），unknown 271,373。
41. selector-code-window verifier 从固定 10 个完整 source window、两份上游 selector
    artifact、ROM 原始字节和 current-primary 投影独立重建 2,754 字节 source 分母；
    只提升 19 段、1,252 字节 current-unknown 交集，保留 1,502 字节既有 primary
    ownership，并验证 bridge/mapper promotion 均为 0、两个 bundle 与两个 range
    denominator 哈希固定。
42. menu-portrait palette verifier 从固定 63×5 表、record 0 的 5 个零 sentinel、
    special pair、selector 与 5 条 queue caller 独立重建 311 个逻辑输出；74 个目录
    资源按物理指针收敛为 70 段 128 字节 palette（共 8,960 字节），并固定唯一
    5-resource alias、54 个内容哈希、range denominator 与 packed bundle。
43. scene-visual source-range verifier 从固定 9-record source table 的 57 段、
    88,756 字节冻结分母重建
    29 段、3,288 字节候选；保留 pack 5 已有 LZ77 ownership 的 31 字节，仅晋升
    29 段、3,257 字节，并固定 2/9/9/9 类别分母、promotion denominator 与 bundle。
44. Cutscene OBJ source-range verifier 从两个固定四记录根表重建 4 个资源 ID、10 个
    frame 与 10 个 animation，固定 28 段、400 字节：component definition record
    10/240、definition pointer table 4/40、animation timeline 10/80、animation pointer
    table 4/40；manifest SHA-256 为
    `a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5`，verifier
    SHA-256 为 `a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446`。
45. proven-roots v9 verifier 从冻结 controller CFG、完整 11-producer 分母与所有冻结
    CFG baseline 独立重建 8 roots、299 条指令、62 个 block、628 字节、16 条
    baseline cross-edge、7 个 opaque return 和 0 个真正 frontier；9 条 producer
    绑定真实 controller source instruction，`0x0736A4`、`0x07445C` 两条 excluded
    producer 保持 unknown。manifest/payload/verifier SHA-256 分别为
    `1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b`、
    `fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b`、
    `b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935`。
46. parser-bound zero-padding verifier 独立绑定 142 个 parser-confirmed 范围与 198
    字节逐字节零值；coverage auditor 同时从冻结 v3/v7 dispatcher payload 重建
    8 个 masked residual cell（32 字节）和 9 个 indexed table cell（36 字节），
    对 partial overlap、分母漂移、symlink、payload 篡改与自引用失败关闭。

加固前 23 条旧式 verifier 的一次运行记录为 21 通过、2 失败：`menu-ui` 的实现哈希
漂移，以及 battle-effect 写回的 `implementation mismatch`。旧 verifier 缺少新规范
要求的结构化结果合同，这组数字只能用于定位旧证据，不计入严格完成证明。

## 2026-09-01 CFG consumed-literal 批次里程碑

v2、proven-roots v6 与 proven-roots v1 三个冻结 accepted Thumb CFG 的 PC-relative
LDR literal 分母已由独立 raw decoder 重建并接入 canonical coverage：分别为
1,699 / 745 / 349 个唯一 word，净增 6,796 / 2,980 / 1,396 字节；三组 target 零重叠，
合计 11,172 字节、946 条 merged-range claim。coverage / proof SHA-256 为
`66a5e95bd2927f9db13435f6862a052ad60634cfbd3a8b5dfad07459a4a12329` /
`85962384fda90272f4d89f6ca523b1055b3963725669f4c13c8772faa8a56f5d`。

正式验收位于
`build/experiments/active/cfg-consumed-literals-coverage/codex-r1-20260831/`：
formal-r2 report / guard SHA-256 为
`16c49cbb5cc95168b2e20b35b1a2f2fc6155638c5e27db59af1b88eb704143f7` /
`abf5dcffb1cc326364c860badb15f5a7c29cc16eedff6ec94d5e22147ef2ba9f`；
98/98 实际结构化 verifier、ROM byte gate 88/88 与 bank contract 10/10 全部通过，
守卫非降级、峰值 RSS 678.1328125 MiB。报告保持 `complete=false`、177 blockers，
因为 152,600 字节仍为 unknown，且 loaded-value 业务含义、自然可达扩张、编辑、重定位、
free-space 与最终发布门禁仍未证明。

### 2026-09-01 consumed-literal 第二批

第二批新增 CFG v3、proven-roots v2/v3/v4/v5/v7/v8/v9 合并包、battle-controller
CFG 与 v2 shadowed consumer slice，分别净增 1,220 / 1,256 / 536 / 308 bytes，
合计 3,320 bytes / 274 ranges，四包目标零重叠。canonical
classified/unknown/claim/segment 更新为 6,142,176 / 149,280 / 15,940 / 17,344。
coverage SHA-256 为
`24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987`；
formal report / guard SHA-256 为
`8ec5119f4f21132721a0727bc4d6caf18a570076bce45093425334b573fe001d` /
`7458b23dd71a825364bf27f5914bca326615ebb59ff4c94df82837b4b4c19ec3`。
102/102 个实际结构化 verifier 和 ROM gate 92/92 全部 contract-ok；报告继续
`complete=false` 是因为 149,280 字节仍 unknown 及既有最终门禁，而不是本批失败。

## 2026-09-05 四包 Tier-2 里程碑

`rom-v17-v18-helper-cfg-v1`、`rom-fixed-pair-tables-v1`、
`rom-prebattle-menu-controller-cfg-v1` 与 `rom-scene-source-closures-v1` 合计净增
4,231 bytes / 141 claims，已真实接入 canonical。scene packet 只接受 71 段
parser-bounded sources 655 bytes 与两个 OBJ closures 360 bytes；46 段 / 90 bytes
alignment gaps 独立排队，23 段 / 199 bytes residual 保持 unknown。

coverage / proof SHA-256 为
`b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82` /
`e50417ea10a2f485c3462812fe8aa74d518bb551fcac79f526ad75aad8c4a8e9`。最终受守卫 formal
位于 `build/experiments/active/scene-source-four-packet-formal-r2-20260905/`；106/106
contracts、ROM gate 96/96、coverage errors=0。报告仍为 `complete=false` / 177 blockers，
原因是 93,109 unknown 与既有 bank、round-trip、发布和实体硬件门，而不是本批失败。

审计已简化为固定三级：每包只做 TDD、独立 verifier 与线性 current-unknown projection；
只有累计 4 packets、10 KiB 或 0.15pp 任一门槛才做一次 Tier-2 canonical/proof/formal；
最终全量审计只在 `unknown_bytes==0` 或发布验收运行。

## 32 个 bank 的正确解释

- 22 个 `runtime_verified` 表示每个 bank 至少存在一条运行时身份关联，不表示全部
  记录或字段完成。
- 10 个 `disproved` 是历史误判、物理别名或子字段 tombstone。候选范围、字节、规范
  来源与独立结构化负证据 verifier 均已绑定，当前可严格关闭为 `10 / 32` bank；这里
  否证的是独立物理 ROM bank，并未声称穷尽排除规范字节的其他逻辑消费者。它们不计入
  22 个有效 bank 的记录/字段运行时覆盖。
- `sequel/bank-proofs.json` 为每个名称绑定 bank 文件、覆盖声明、证据与限制。
- `tools/audit_re_completion.py` 的 32/32 只证明旧 metadata 范围，不证明运行时语义
  或写回能力。

## 复核

```bash
python3 tools/audit_rom_byte_coverage.py --root .
python3 tools/audit_reverse_engineering_proof.py \
  --execute-verifiers --allow-incomplete
```

最终验收必须去掉 `--allow-incomplete`，并传入由签名 tag 或独立 attestation 发布的
证明规范 SHA-256：

```bash
python3 tools/audit_reverse_engineering_proof.py \
  --execute-verifiers \
  --trusted-spec-sha256 <外部已发布的64位SHA-256>
```

当前该命令按设计不能通过，因为 `claim_status=incomplete`、全部七个全局门禁均未闭合、
有效 bank 穷尽度为 0/22、缺少外部根摘要且实体 GBA 未验证。

## 历史报告处理

2026-06-28 版本中醒目的“100% complete”、绿色勾选、错误 offset 和“32 个结构全部
完成”表格已从当前文档移除。原始内容仍可通过 Git 历史追溯，但不得再作为当前技术
事实引用。
