# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：先完成逆向工程，再建网页编辑器。**

---

## 现状总览

> 2026-07-30 当前调查闭合审计为 32/32：22 个有效数据 bank 均通过元数据和
> 基准 ROM fidelity，另 10 个是带负证据、空 entries、禁写回的 `disproved`
> tombstone。分布为 runtime 13 / code 9 / static 0 / disproved 10。32/32 只表示
> bank 身份调查闭合，不等于所有字段语义、运行时路径与端到端写回均已完成；
> save-state 已由真实 UI save 与冷启动恢复升级为 runtime_verified。

### 2026-07-13 最新执行边界

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
