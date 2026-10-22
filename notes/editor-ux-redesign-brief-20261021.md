# 编辑器交互重设计：任务书（2026-10-21 晚）

> 目标（用户原话）：**「当前版本非常不直观，检查每一项可编辑内容，为每一项编辑功能用
> 一个单独的子代理去重新设计用户的操作流，然后以此重新进行交互设计，最终将所有编辑
> 功能的交互流程都重新迭代一遍」**。
>
> 本文是所有子代理的**共同事实基准**。每个子代理负责其中一块「编辑功能」，
> 产出该块的操作流重设计规格；主代理负责汇总成统一设计系统并落地。

---

## 1. 交付物是什么

`rom-editor/` —— 一个**离线网页版 ROM 编辑器**（火影忍者 · 木叶战记，GBA 卡带）。
纯 HTML + 原生 ES Module，**没有构建步骤、没有后端、没有账号**。

它服务于两类人：

* **作者**：想改这个 ROM 里的剧情、数值、文本、战斗配置，并导出改过的 ROM；
* **复核者**：想知道「这个 ROM 的哪一处是什么、能不能改、改了会动哪几个字节」。

## 2. 编辑器的现状（务必先自己核对，不要照抄本文）

先跑这些命令自己看一遍：

```powershell
cd D:\Github\gba-naruto
python tools\editor_inventory.py            # 全部可编辑内容盘点（40 结构表 / 11 文本表）
python tools\editor_inventory.py --domain battle
node rom-editor\tools\serve.mjs 8765        # 起服务 → http://localhost:8765/rom-editor/
node rom-editor\tools\verify_views.mjs      # 无头视图自检（30 项，改 UI 时用它兜底）
```

关键文件：

| 文件 | 作用 |
|---|---|
| `rom-editor/js/app.js` | 外壳：侧边栏、路由（`#battle/stage/40/0`）、构建/导出/导入、状态栏 |
| `rom-editor/js/editors.js` | **通用结构编辑器 + 通用文本表编辑器**（所有表都由它渲染） |
| `rom-editor/js/modules/*.js` | 九个域视图（overview/story/items/characters/ninjutsu/battle/route/audio/assets/raw） |
| `rom-editor/js/modules/common.js` | 域首页的卡片网格、面板分发、`operandInput` |
| `rom-editor/js/pack.js` | 内容包模型：`setValue` / `setText` / 脏标记 |
| `rom-editor/js/rom.js` | ROM 构建器：结构写回、文本重定位、空闲区分配 |
| `rom-editor/js/ui.js` | DOM 工具（`el` / `toast` / `modal`） |
| `rom-editor/styles.css` | 全部样式 |
| `docs/rom-editor.md` | 面向使用者的说明（§3 六域、§6 文本长度策略、§7 已知边界） |

## 3. 当前的交互模型（今天长这样）

```
侧边栏（9 个模块）
  └─ 域首页：一段介绍文字 + 一堆「卡片」（每张表一张，卡片里塞了 label/条数/ROM 地址/说明/验证级别）
       └─ 通用编辑器：搜索框 + 「列设置」按钮 + 记录表格（最多 6 列，只读文本）
            └─ 点行 → 右侧详情面板：标题 + ROM 地址 + **全部字段的扁平表单**（标签 + 字节偏移 + 输入框 + 提示）
       文本表：搜索框 + 文本表格 → 点行 → 详情：文本域 + 字节计数 + 「恢复原文」
  「按关卡」视图（战斗 / 剧情路线）：关卡下拉 + 若干只读摘要表 + 少量可改输入框
  原始字节：分页十六进制 + 跳转/搜索 + 显式补丁
```

## 4. 已知的不直观之处（有证据，逐条核对过）

| # | 现象 | 证据 |
|---|---|---|
| A | **分组信息被丢掉**。内容包里每个字段都带 `group`（如 `character_template` 的 基础属性/头部/忍术列表/技能列表/道具槽），通用编辑器却把字段摊平成一张长表单 | `editors.js:157-160` 直接遍历 `structure.fields`，从不读 `field.group` |
| B | **单条记录 175 个输入框**。`character_template` 一条 180 字节的记录有 175 个已知字段（忍术 15×4 + 技能 24×4 + 道具 9 + 属性），详情面板是一条 175 行的长表单 | `python tools/editor_inventory.py` |
| C | **「原始字节」填字段和有意义的字段长得一模一样**。`item_record` 94 条记录**一个已知字段都没有**，全是 16 字节 `raw_XX`；用户只看到一个 hex 文本域 | `editors.js:238-245`（hex 走 textarea，和数字输入框同构） |
| D | **枚举值是裸数字**。阵营 0/1、道具类别 0–3、朝向 0–7、奖励层级 tier 都没有下拉或说明 | `export_content_pack.py` 里这些字段都是 `u8` |
| E | **指针是裸十六进制**。字段只显示 `0x08…`，不给「这个地址是什么」（哪张表/哪个字形段/哪段图块） | `editors.js:257-259` 只给出文件偏移 |
| F | **表格是只读的**，必须点行才知道能改；详情面板是右侧窄栏，要滚动 | `editors.js:105-125`（单元格纯文本） |
| G | **没有上一条/下一条、没有键盘操作、没有面包屑**；改完一条想看相邻记录只能再点一次 | `editors.js` 全文无键盘处理 |
| H | **域首页是一堵文字卡片墙**，看不出「我改过什么」「这张表最好从哪下手」 | `common.js:88-103` |
| I | **「按关卡」视图与通用编辑器是两套东西**：在关卡视图里改了值，表格视图里看不出改过，也跳不回去 | `battle.js` 的 `numCell` 只改 pack，不联动表格 |
| J | **脏状态只有一个数字徽章**（顶栏「已改动 N」），没有逐项标记、没有差异视图、没有撤销 | `app.js:markDirty` |
| K | **全 ROM 文本索引（16,915 条）是一张平表**，只能靠搜索找字符串；战斗目标说明文字这类「挂在别处的句子」用户根本想不到要去那里找 | `rom-editor/js/modules/story.js` |
| L | **构建报告是一个模态框**，构建完还得手动下载；没有「改了什么」的清单 | `app.js:showBuildReport` |

## 5. 你要产出什么

对你负责的那一块「编辑功能」，产出一份**可落地的操作流重设计规格**。不是感想，是规格。

必须包含：

1. **当前操作流**：用 3–6 步写出用户今天怎么干这件事（点哪里、看到什么）。
2. **摩擦点清单**：具体到 `文件:行` 或具体到内容包里的哪张表/哪个字段，并说明为什么这一步对用户是别扭的。至少 3 条，只写你这一块范围内的。
3. **重设计后的操作流**：分屏讲清楚
   - 屏幕布局：哪些区域、各自放什么；
   - 用户看到的**具体文案**（按钮叫什么、提示怎么写、空状态怎么写、错误怎么写）；
   - 用户的**点击序列**（从进入这块到改完一个值，每一步按哪里）；
   - 每一步的**反馈**（颜色/提示/焦点/撤销机会）；
   - 键盘操作（能加就加，写清楚键位）。
4. **控件类型映射**：对这一块涉及的字段种类，给出「字段类型 → 控件」的表（例如：阵营 → 下拉；指针 → 带说明的地址框 + 「跳到目标」；枚举 → 带标签的下拉；原始字节 → 折叠的 hex 区）。
5. **要改哪些文件**：逐个文件写「改成什么」，格式 `文件路径 — 改什么`。
6. **验收标准**：3–6 条**可被机器或人核对**的断言（例如「打开角色定义表时，详情面板第一屏只显示 基础属性 分组的 8 个字段，其余分组折叠」）。

## 6. 硬约束

- **不要修改任何文件**。你只产出设计规格，改动由主代理统一落地（避免多个代理互相打架）。
- 规格要能落地：不要提需要新框架/新构建步骤/后端的方案。
- 不要破坏仓库既定约定：
  - 写回模型：**复制原生条目 + 只改已知字段 + 未知字节原样保留**；
  - 文本写回走 **token 流**（控制码 0x01/0x02 必须保留，见 `notes/font-encoding.md:133-143`）；
  - 文本分两类：指针表驱动（可重定位、可变长）与绝对地址引用（只能等长改写，超长报错）。
- 界面语言是**中文**（面向中文作者），设计规格里的文案请直接写中文。
- 仓库换行符钉死 LF。

## 7. 输出格式

先给一段 5 行以内的摘要（这块功能今天怎么用、你要改成什么样），
然后按第 5 节的六个小节展开。最后附一段「我最不确定的一个点」——如果你需要主代理
拍板才能落地，把问题写在这里（一个就够）。

---

## 附：各编辑功能的划分（子代理分工）

| # | 编辑功能 | 负责范围 |
|---|---|---|
| 1 | **结构表通用编辑器** | `editors.js::StructureEditor`（40 张表共用）—— 分组、折叠、枚举、指针、导航、撤销 |
| 2 | **文本表通用编辑器** | `editors.js::TextTableEditor`（11 张表共用）—— 搜索、编辑、字节计数、等长/可重定位提示 |
| 3 | **域首页与全局导航** | `app.js` 侧边栏 + `common.js::renderDomainIndex` —— 入口、卡片、面包屑、全局进度 |
| 4 | **角色属性与技能** | `characters.js` + `character_template`(175 字段)/`per_character_stats`/`character_perks`/`portrait_*` |
| 5 | **忍术** | `ninjutsu.js` + `jutsu_record` + `jutsu_names` |
| 6 | **道具与奖励** | `items.js` + `item_record`（16 字节全未知）+ `reward_table` |
| 7 | **战斗 · 按关卡四件套** | `battle.js::renderStage` —— 战场布置/出生点/物件/战斗目标/战场事件 |
| 8 | **战斗 · 结构表集合** | `battle.js` 域首页 + `map_table`/`battle_actors`/`battle_rules`/`encounter`/`unit_*`/`level_blocks`/`object_descriptors`/`sprite_*`/`handler`/`pickup` |
| 9 | **剧情与对白** | `story.js` + 剧情脚本四根表 / 对白槽位 / 说话人名 / 文本索引 / 字体 / 底图 |
| 10 | **剧情路线** | `route.js` —— 路线边、任务文本、下一场景操作数 |
| 11 | **音频** | `audio.js` —— sound-ID / m4a SongHeader / 函数指针表 |
| 12 | **素材与资源** | `assets.js` —— 指针表 A/B / 资源记录表 / WRAM 分配表 |
| 13 | **原始字节** | `raw.js` —— 十六进制编辑、跳转/搜索、显式补丁 |
| 14 | **全局流程** | `app.js` —— 载入 ROM、构建 ROM、导出/导入内容包、状态与错误、脏标记与撤销 |

---

## 附二：主代理已经落地的内容包元数据（子代理设计时可直接用）

导出器 `tools/export_content_pack.py` 现在给字段/结构补了这些**机器可读**的语义，
界面应当直接用它们，不要再从散文里猜：

| 元数据 | 位置 | 含义 | 例子 |
|---|---|---|---|
| `field.group` | 字段 | 这条字段属于记录的哪一段 | `character_template` → 基础属性 / 头部 / 忍术列表 / 技能列表 / 道具槽 |
| `field.array` + `field.index` + `field.item` | 字段 | **重复槽位**：同一组里的第几项、这一项的哪一列 | `jutsu_7_id` → array=`jutsu`、index=7、item=`id` |
| `field.enum` | 字段 | 取值域 → 标签 | `g0_0_type` → `{1: 全灭敌方…, 2: 回合用尽（原生不读 a/b）, 3: 指定角色已离场…}` |
| `field.relation` | 字段 | 这个值是另一张表的 id | `jutsu_0_id` → `{table: jutsu_names, kind: text}`；`slot0_item` → `{kind: by_category, categories: {0: ninjutsu_names, …}}` |
| `structure.raw_only` | 结构 | 整张表**一个已知字段都没有** | `item_record`（94 条 × 16 字节全未解码） |
| `structure.id_relation` | 结构 | 记录下标本身就是一个 id | `character_perks` → `training_names` |

**重复槽位怎么用**：凡是一组字段的 `array` 相同、`index` 覆盖 0..N-1、每项有同样的
`item` 集合，它们就该渲染成**一张 N 行的表格**（每列一个 `item`），而不是 N×M 个
输入框。已确认为真的重复结构：

| 结构 | array | 行数 | 列（item） |
|---|---|---|---|
| `character_template` | `jutsu` | 15 | id / value / unlock / pad |
| `character_template` | `training` | 24 | id / value / unlock / pad |
| `character_template` | `items` | 9 | id |
| `reward_table` | `slots` | 8 | category / item_id |
| `battle_rules` | `rules` | 8 | type / a / b / c / text_ptr |
| `portrait_table` | （表达式 0..4） | 5 | gfx / palette |

渲染元数据层的代码在 `rom-editor/js/fields.js`（`groupFields` / `resolveRelation` /
`resolveByCategory` / `enumLabel` / `isRawOnly` / `describePointer` / `fieldControl`），
子代理的规格应当复用它，而不是各写一套控件。
