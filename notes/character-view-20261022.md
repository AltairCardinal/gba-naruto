# 角色域的统一编辑视图（2026-10-22）

日期：2026-10-22
范围：`rom-editor/js/modules/character.js`（新）、`rom-editor/css/character.css`（新）、
`rom-editor/js/modules/characters.js`（分发 + 一行 groups）、`rom-editor/js/routing.js`
（只加 `character` 一个标签）、`rom-editor/tools/verify_character_view.mjs`（新）。

## 1. 目标

用户反馈：「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
其他模块也要做同样思路的修改」

任务域已经这么做了（`rom-editor/js/modules/mission.js`）。角色域的域首页有 7 个入口：

| 入口 | 是什么 |
|---|---|
| 角色定义表 | 一个角色的属性 + 忍术槽 + 技能槽 + 道具槽 |
| 逐角色成长表 | 同一个角色的每级成长 |
| 角色特性表（技能） | 每个**技能**自己的参数 |
| 头像指针表 | 一个角色的 5 个表情 |
| 头像拼块表 | 头像由哪几块拼起来（所有角色共用） |
| 人物名表 | 名字本身 |
| 技能名表 | 名字本身 |

前五张是「一个角色」的侧面，后两张是「名字」。所以：前五张合成一个角色视图，
后两张在域首页保持独立行。

## 2. 走过的路与结论（都已复核）

### 2.1 一个角色 = 角色定义表的一条

- `character_template`（ROM 0x54241C，0xB4 字节 × 63）：第 0 条**整条全 0**（空槽），
  1..62 是 62 个角色；`id_relation → character_names`（63 条），所以名字与 id 同号。
- `per_character_stats`（ROM 0x545068，16 字节 × 63）：与角色**同号** ⇒ 成长。
- `portrait_table`（ROM 0x5A4DEC，40 字节 × 64）：1..62 与角色同号；第 0 条全 0；
  **第 63 条不是头像**（里面是 0x9A9A5992 这种图块数据，不是 ROM 指针）——
  导出时多带了一条，视图里照原样列，不作解释。
- `portrait_pieces`（ROM 0x4643C0，20 字节 × 6）：所有角色共用一份。

### 2.2 特性表不是「角色 id 空间」，是「技能 id 空间」——这一点与最初的设想不同

`character_perks`（ROM 0x5459C8，12 字节 × 45）的 `id_relation` 指向
**`training_names`**（技能名表，45 条），不是 `character_names`。
角色定义表里 `train_N_id` 的 relation 同样是 `training_names`。

也就是说：**角色的「特性」= 这个角色用到的那些技能的参数**。
按角色 id 直接取 `character_perks[角色 id]` 会显示另一个技能的参数（例：
鸣人（id 1）会显示技能 id 1「锻炼」的参数）——那不是鸣人的特性。

所以视图里「特性（技能）」这一段列的是：**这个角色的每个技能槽里的技能 id
→ 该技能在角色特性表里的那条记录**（效果类型 / 基础值 / 次要值 / 每级成长 /
附加属性）。每格照常能改，也照常能跳到 `character_perks` 的那条记录。

### 2.3 槽位与头

- 角色定义表的重复槽位：`jutsu`（15 × id/档位/解锁等级/填充）、`training`（24 × 同上）、
  `items`（9 × 只有 id）。数组名取自内容包的 `field.array`。
- 头 12 字节 = **不属于任何数组的字段**：`flag_00 / stat_a..stat_f / flag_07 /
  aux_stat / hp_base`。视图里「属性」一段给的就是这些字段（10 格，含两个恒定标志字节）。
- 头像指针表的重复槽位数组名是 `expr`（5 × 图像/调色板）。
- `perks` 的两个「未使用 +0xNN」与成长表的「未使用」在视图里不占版面
  （内容包里原样保留，写回照样定宽）；每槽那 1 字节「填充」列同理。

### 2.4 写回通路

全部走内容包已有的通路：`fields.fieldControl` → `pack.setValue`；
重复槽位走 `slots.renderArrayTable`（同一套 fieldControl）。**没有新增写回路径。**

## 3. 落地

- `rom-editor/js/modules/character.js`：左边 = 角色定义表的 63 条（一行 = 一个角色，
  名字来自 `id_relation`，摘要 = 体力 · 攻，已改标记数 = 四张侧面表 + 用到的技能参数）；
  右边 = 属性 / 成长 / 特性（技能）/ 忍术列表 / 技能列表 / 道具槽 / 头像 七段。
  用 `split.js` 的 `splitPane`（可拖动分栏，宽度记在 localStorage 的 `editor.character`）。
  顶部有跳转按钮：人物名表（改名字）/ 角色定义表 / 逐角色成长表 / 头像指针表。
- `rom-editor/js/modules/characters.js`：域首页加 `groups`（五张表合成一行），
  「人物名表」「技能名表」仍是独立行；推荐入口改成打开角色视图，
  另留一张次要卡片进通用表格视图。
- `rom-editor/js/routing.js`：只加 `character: '角色'` 一行 ⇒ `#characters/character` 可寻址。
- `rom-editor/css/character.css`：角色视图自己的几处样式（**还没有链进 index.html**）。

## 4. 自检

`node rom-editor/tools/verify_character_view.mjs`（新，自带 DOM 桩）四条断言全过：

1. 角色视图渲染成功，左边列表 63 行 = 角色定义表 63 条；
2. 详情里能看到属性（攻击力…体力）、成长、特性（技能）、忍术列表、技能列表、道具槽、头像；
3. 改一个字段后 `pack.changedCount()` 0 → 1，改回原值后 1 → 0；
4. 域首页「本域可编辑内容」里五张角色表合成 1 行，人物名表 / 技能名表仍各占 1 行。

另有门禁：`verify_syntax`（50 个文件）全过、`verify_sources` 全过、`verify_labels` 全过、
`python -m unittest discover -s tests` 84 项全过。

`verify_views.mjs` 目前有 1 项失败，**与本次改动无关**：素材域那张自己画的
`domain-tables` 表（`modules/assets.js`）没有 `dataset.covered`，
于是自检读到的「覆盖 0 张表」。角色域那条是通过的（覆盖 7 张表）。

## 5. 需要主代理配合

- `rom-editor/index.html` 加一行 `<link rel="stylesheet" href="css/character.css">`；
- `docs/sequel-roadmap.md` 里记一笔（本次没有动 `docs/`）。
