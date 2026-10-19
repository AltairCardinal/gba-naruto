# Butano 角色与技能可观察战斗架构设计

## 问题与目标

当前通用场景已经通过 `battle_scene_controller` 驱动移动、命令、技能、目标、朝向、防御、
敌方行动和回合切换，但可见层只显示 `C#`、`A#` 和少量状态。它能证明控制流在运行，
却不能证明：

- 当前行动者是谁、等级和基础属性是什么；
- 不同角色从各自定义得到的技能列表是否不同；
- 菜单中的每个技能是否带有真实消耗、目标和可用性；
- 玩家选择的技能是否通过同一条领域链产生了不同结果。

因此这一阶段不再增加截图、关卡特判或场景内效果脚本，而是补齐“内容事实源 →
战斗目录 → 玩家动作流 → 场景快照 → Butano UI/遥测”的可观察架构，并以 battle row 9
中的漩涡鸣人、宇智波佐助和春野樱证明角色差异。

这仍是完整战斗系统 Goal 的一个里程碑，不表示全部角色美术、技能演出、47 场关卡和音频
已完成。

## 已有能力与复用判断

### 可直接复用

- `generated_battle_unit_content.h` 已有 63 个角色定义。每个定义包含攻击、防御、敏捷、
  移动力、忍具容量、查克拉容量、结印、最大 HP，以及 15 个主技能槽和 24 个副技能槽。
- `generated_battle_action_content.h` 已有 87 个主动技能和 94 个忍具动作定义。
- `battle_action_loadout` 按角色实例持久技能状态解析已习得技能；角色等级只把达到阈值的
  `0xFF` 槽解锁为状态 `0`，不会直接使技能可战斗。`battle_action_catalog` 把状态
  `1..254` 的角色技能与装备忍具合成固定容量目录；`battle_action_browser` 继续负责需求、
  消耗和效果处理器校验。
- `battle_player_action_flow` 已拥有动作浏览结果和选择索引；`battle_scene_controller`
  已是场景唯一命令入口；效果解析、目标、防御、反应和回合收尾继续走现有领域链。

### 需要抽取的公共能力

- 身份表目前只存在于 JSON 证据中。生成一个不依赖 Butano 的固定容量身份目录，使宿主
  测试、场景 UI 和后续关卡共同使用同一组 63 个角色名与 87 个主动技能名。
- `battle_player_action_flow_snapshot` 只公开当前动作 ID。把浏览器中最多 19 个动作的
  值语义视图复制到 snapshot，避免场景重新构建目录或读取 session。
- `battle_scene_unit_view` 补充等级及战斗基础属性，使 UI 不需要按角色 ID 回查生成表。

### 不能直接复用的部分

- 原 ROM 名称字节不是中文 Unicode 编码。同一字节码在中文释名中可能对应不同汉字，
  action 53 的三组原始字节也对应四字中文释名。因此原字形可作逆向证据，不能直接充当
  中文字体映射。
- 忍具内容目前只有 94 个数值模板，没有经过录像或文本证据核验的名称。UI 将明确显示
  `忍具 #ID`，不能编造名称；主动技能仍显示完整已核验中文名称。

## 方案比较

### 方案 A：继续在 renderer 中按角色 ID 拼接文字和选项

改动最少，但角色、技能和菜单仍是场景私有知识；宿主测试不能验证完整目录，后续关卡会
继续复制特判。不采用。

### 方案 B：新增内容投影层并扩展既有 snapshot

采用。生成身份目录和中文 sprite font；动作流把现有浏览器结果投影为固定容量值对象；
controller 把角色实例的等级与属性投影给场景。UI、遥测和测试都只消费 snapshot。它不
改变战斗规则，也不会建立第二套角色或技能系统。

### 方案 C：同时复刻原版角色立绘、技能菜单排版与逐技能演出

最终视觉还原需要这一步，但把字体、内容、领域投影、角色美术和 87 个技能演出捆绑在一起
会再次形成无法验证的截图式大改。先证明内容与行为架构，再分里程碑替换占位美术和演出。

## 数据与生成管线

新增确定性生成器，输入：

- `sequel/content/units/unit-identities.json`；
- `sequel/content/battle-config/action-identities.json`；
- 本机固定路径的 PingFang SC 字体；
- Butano common 16×16 ASCII font 资产。

输出：

- `generated_battle_identity_content.h`：63 个角色身份、87 个主动技能身份，包含 ID、
  UTF-8 名称和 `runtime_visual_exact` 置信标记；
- `battle_identity_font.bmp/json`：前 94 个 ASCII 字形与所有名称所需的唯一 UTF-8
  字形；
- `battle_identity_sprite_font.h`：UTF-8 map、ASCII 变宽表和汉字固定宽度表。

生成器严格检查 ID 连续、数量准确、名称非空、置信度枚举合法、所有名称字符都有生成字形、
输出确定性。`name_raw_hex` 保留在 JSON 证据中，不伪装为 Unicode 映射。若目标环境没有
指定字体，生成失败并报告缺失输入；已生成 BMP 仍可直接完成正常 ARM 构建。

## 领域投影

`battle_action_menu_view` 是不含指针的值对象，最多 19 条，包含：

- 来源类型、技能/忍具 ID、忍具槽位；
- 持久技能等级；
- cost 类型与数值；
- target 类型、effect code；
- `selection_error` 与 requirement reason。

`battle_player_action_flow_snapshot` 保存 `action_entries` 和 `action_count`。每次浏览器创建
或索引变化都同步完整目录；从目标选择退回动作选择时目录保持稳定，取消整名角色的行动或
新行动者开始时必须清空，防止跨角色陈旧数据。

`battle_scene_unit_view` 增加：

- `level`；
- `attack`、`defense`、`agility`、`movement`；
- 现有 HP、查克拉、位置、阵营、控制权、完成状态和召唤关系继续保留。

这些值都来自当前 `battle_unit_instance`，而不是场景按角色 ID 重算。

## 用户可见行为

1. battle row 9 初始选择鸣人时，底部显示“漩涡鸣人”、等级、HP/查克拉和基础属性摘要。
2. L/R 选择佐助或小樱时，同一 UI 立即显示对应身份和属性，不更换场景。
3. 进入技能命令后显示当前动作的真实名称、技能等级、菜单位置、消耗和不可用原因；上下键
   遍历该角色当前已习得的完整战斗技能列表。达到角色等级阈值但尚未投入修炼点的技能不会
   出现在战斗目录。
4. 鸣人等级 1 的目录为“瞬身术、忍者组合拳、影分身术”；佐助为“瞬身术、忍者组合拳、
   火遁术”；小樱为“分身术、瞬身术、忍者组合拳”。
5. mGBA 路线让鸣人执行瞬身术、让小樱执行分身术。前者改变合法落点，后者占用预留槽并
   把 active unit 数从 8 增至 9；两者都必须走动作选择、目标、朝向、防御和回合收尾。
6. 非法动作显示稳定错误，领域状态不提交；身份置信度不是 exact 时显示 `?` 标记。

## 场景与状态机边界

```text
generated unit/action data + character progression
          |
          v
slot states -> loadout -> level materialization
                         |
                         v
                 action catalog -> action browser
                               |
                               v
                    player action flow snapshot
                               |
                               v
scenario -> encounter runtime -> scene controller snapshot
                                      |
                              +-------+-------+
                              |               |
                           Butano UI       telemetry
```

- renderer 不读取 `unit_definitions`、不重建 loadout、不调用 resolver、不写 session。
- 身份目录只负责 ID → 名称/置信度，不决定技能可用性。
- 角色 progression 是技能状态唯一事实源；等级阈值、修炼扣点和战斗目录不能在场景层重算。
- snapshot 是领域状态的只读值投影，不持有 ROM 资产或 sprite。
- 中文字体是表现资产，不进入战斗规则。

## 错误、空状态与边界

- 无效角色/技能 ID 显示明确的数值占位符，不能越界访问身份表。
- 当前角色无技能时显示“无可用技能”，确认不会提交动作。
- 忍具名称证据缺失时显示 `忍具 #ID`；数值、消耗和效果仍来自 94 条真实定义。
- action menu 只有打开技能浏览器后才代表该行动者；新行动者开始必须清空旧目录。
- 16×16 中文字体会增加 ROM 占用和单字 OAM 尺寸，ARM 构建与 128 sprite 上限必须重新
  验证；若超限，先减少同时显示行数，不改为截图文本。
- 自动 mGBA 继续静音，只能签发内容、流程、图形和状态，不能签发声音听感。

## TDD 与验收

1. 生成器测试先因缺少输出失败，再验证 63/87 条身份、置信度、UTF-8 字形覆盖和确定性。
2. 宿主测试先要求 row 9 三名玩家拥有不同姓名、属性和完整动作条目，再扩展 snapshot。
3. source wiring 测试禁止 renderer 按角色 ID 建技能表、禁止数值 `C# / A#` 作为主要
   身份显示，并要求使用生成字体与身份目录。
4. 集成测试通过 controller 让鸣人瞬身、小樱分身，断言不同效果、预留槽生命周期和完整
   玩家/敌人/下一回合衔接。
5. ARM 构建检查 warning/error、ROM、IWRAM/EWRAM 和 OAM 预算。
6. 受守卫 mGBA 路线按 telemetry 状态驱动输入，分别捕获三名角色菜单、瞬身结果、分身
   结果、active 8→9、敌方阶段和 round 2；既有 row 41/43/9 路线继续回归。

## 实现结果与 ARM 约束

- 生成器输出 63 个角色身份、87 个主动技能身份和覆盖 238 个唯一非 ASCII 字符的
  16×16 sprite font；原 ROM 字节仅保留为来源证据，不被误当成全局 Unicode 码表。
- `battle_action_menu_view` 是不超过 12 字节的值对象，只包含动作 ID、等级、来源、消耗、
  目标、效果和稳定原因码；UI、遥测和测试都只消费 snapshot。
- 初版把完整 30 字节动作定义复制进 view，目标确认又按值复制 scene/player snapshot；
  mGBA 在 A 确认后进入 IWRAM 栈区。改为紧凑投影、snapshot const 引用和只捕获
  `ability_id` 后消除了该 IWRAM 栈溢出，未增加角色或 battle ID 特判。
- 当前 336 字节遥测在末尾追加 `selected_action_level`，保留所有既有字段偏移。符号地址
  只能用于对应 ELF，后续构建必须重新解析。
- 受守卫 row 9 路线于第 994 帧进入 round 2：鸣人动作 2 瞬移、小樱动作 1 生成角色 3
  的预留分身、活动单位 8→9，并浏览佐助 `[2,5,16]`。证据为
  `artifacts/butano-character-actions-b09-20260725-03/`。

2026-07-26 的后续修正把技能可用性从角色等级中分离：15+24 槽状态进入
`CharacterProgressionRecord → BattleUnitInstance → loadout/catalog → resolver`，
修炼点可令初始状态 0 的技能进入正式目录，同技能 LV1/LV3 的正式伤害结果不同。三场 ARM
路线同时证明场景切换会先提交 sprite tile 回收，防御收尾不会再在栈上复制完整 session。
证据见 `notes/battle-action-progression-20260726.md`。

同日后续接线修复了“等级只显示、不参与战斗”的数据断层。现在 loader 从同一份 progression
等级与 ROM 成长表生成七项角色属性，scene snapshot/HUD、resolver、状态 reducer 和 AI
直接消费实例值。LV2 与 LV9 的精确数值、敌方同角色实例和 ARM 回归见
`notes/battle-level-stat-runtime-20260726.md`。

该里程碑证明角色数据、已习得技能目录、等级成长和不同效果共用同一运行架构；仍不代表
玩家修炼页面、章节存档、63 名角色逐人美术、87 个技能逐项演出、全部关卡和音频听感已完成。
