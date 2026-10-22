# 角色域 + 道具域：页签 → 卡片纵排（2026-10-22）

> 规格：`notes/specs/human-readable-cards-20261022.md`（第十轮，推翻第九轮的页签方案）
> 改动文件：
> - `rom-editor/js/modules/character.js`
> - `rom-editor/js/modules/item.js`
> - `rom-editor/tools/verify_character_view.mjs`（角色域的断言）
> - `rom-editor/tools/verify_item_view.mjs`（道具域的断言）
>
> **没改**：`rom-editor/js/cards.js`（通用机制由主代理写）、`rom-editor/js/tabs.js`、
> `rom-editor/styles.css`、`rom-editor/tools/verify_views.mjs`、`rom-editor/tools/verify_cards.mjs`。
> 别的域的模块文件与断言是并行子代理在改，本轮没碰。

起因是作者的原话：「不要用页签了，改成同一个滚动页面中纵向排列的的卡片」。
页签把其余类别**藏起来** —— 作者看到「成长」那一页时不知道还有几类东西没看。
这一轮**保留分类，去掉切换**：类别还是类别（一张卡片一张），但不互斥、不隐藏。

---

## 1. 原来是什么（第九轮的页签）

| 视图 | 页签数 | 页签标题 |
|---|---:|---|
| 角色（`#characters/character`） | 7 | 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像 |
| 忍具（`#items/item`） | 3 | 名字 / 记录字段 / 掉落位置 |
| 奖励（`#items/reward`） | 4 | 金币 / 强化点 / 等级门槛 / 掉落位 |

页签机制（`rom-editor/js/tabs.js` 的 `TabPanel`）的三条约定：懒渲染、
记住当前页签（`key` + localStorage）、角标（这一类改了几处）。

## 2. 现在是什么（卡片）

| 视图 | 卡片数 | 卡片头标题（依次） | 卡片头下的说明（`hint`） |
|---|---:|---|---|
| 角色 | 7 | 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像 | 角色定义表的头 12 字节… / 逐角色成长表里同号的那一条… / 这个角色用到的每个技能… / 角色定义表里的忍术槽… / 技能槽… / 忍具槽… / 头像指针表里同号的那一条 + 头像拼块表 |
| 忍具 | 3 | 名字 / 记录字段 / 掉落位置 | 忍具名表里的那一条文本 / 记录表那 16 个字节… / 奖励表里引用它的那些行… |
| 奖励 | 4 | 金币 / 强化点 / 等级门槛 / 掉落位 | 三个数字字段用内容包里的 `field.desc` / 8 个掉落位：类别 + 物品… |

**所有卡片的内容同时在 DOM 里**（这是与页签最大的不同）。
「头部」（角色名 / 来自哪张表 / 已改几处 / 跳转条；忍具名 / 记录表第 N 条 / 字节数）
仍在卡片堆**外面** —— 它回答「我现在看的是哪一条」，卡片回答「这一条有哪几面可看」。

角标从页签条挪到**卡片头**（`.card-badge`），口径没变：按字节判定
（改过又改回去不算改），角色域按字段再细分一次（属性 / 三个槽位共用同一条记录，
所以改一项属性只亮「属性」那张卡片）。

**卡片标题的命名**：规格 §5 给忍具域的第二张卡写的是「未解字节」，
但第九轮的实现是「记录字段」——2026-10-22 逐字节普查之后那 16 格都有了真名
（`notes/evidence/item-record-fields-20261022.md`），「未解字节」已经不成立。
规格 §2.3 又说「label 保持」，主代理的 `verify_cards.mjs` 两个名字都认
（`item: ['名字', ['记录字段', '未解字节'], '掉落位置']`）。本轮**保持「记录字段」**。

## 3. 机械替换对照（`TabPanel` → `CardStack`）

| 原来 | 改成 |
|---|---|
| `import { TabPanel } from '../tabs.js';` | `import { CardStack } from '../cards.js';` |
| `new TabPanel([...], { key: '…', pack })` | `new CardStack([...], { pack })` —— **去掉 `key`**（卡片没有「当前页」） |
| `this.tabs` | `this.cards` |
| `this.tabs.element` | `this.cards.element` |
| `this.tabs.refresh()` | `this.cards.refresh()` |
| `this.tabs.setBadge(id, t)` | `this.cards.setBadge(id, t)` |
| `this.tabs.setActive('x')` | **删掉**（卡片全都同时可见，不需要切） |

方法名也跟着改（避免留下「Tab」字样）：
`tabSpecs()` → `cardSpecs()`、`tabContent()` → `cardContent()`、
`refreshTabs()` → `refreshCards()`、`mountTabs()` / `unmountTabs()` →
`mountCards()` / `unmountCards()`。

两个域**都没有** `setActive` 的特殊情况：道具域的「手动填地址」按钮在素材域
（`assets-wiring.js`），不在这一轮的范围里。

## 4. 做法与坑

- **「刷新器」必须按卡片分桶**。页签版本里一次只建一页，所以 `tabContent()` 在每次
  重建前把 `this.refreshers` 清空是对的；卡片版本里**七张卡片一次全建**，
  照抄就会变成「每建一张卡片清一次」，最后只剩最后一张卡片的刷新器 ——
  改完一格，别的卡片的说明行与「已改」标记就不动了。
  改法：`this.refreshers` 从数组变成 `Map`（卡片 id → 刷新器列表），
  `cardContent(id, build)` 建这张卡片时先 `set(id, [])`，
  `addRefresher(fn)` 归到 `this.currentCard` 名下，
  `runRefreshers()` 把所有桶跑一遍。角色域、道具域两个视图各一份。
  （卡片堆内部因为角标出现/消失而自己重建时，各卡片重建各清各的桶，不会攒下旧回调。）
- **角标冒出来时整摞卡片会重建一次**（`CardStack.updateBadges()`）：
  角标节点是渲染时才有的，从「没有」变成「有几处」时机制会 `render()` 一次，
  输入框也跟着重建。角色域原来那条断言「改完一格不重建页签内容（输入框不丢焦点）」
  因此**保不住**（页签版本的 `updateBadges()` 只重画页签条，页签体不动）。
  本轮**没有**去改 `cards.js`（不是本轮的文件），改为把断言换成
  「改完一格，新值还在那张卡片里」+「改完一格，别的卡片内容没丢」，
  并在代码注释里写明「只有角标从『没有』变成『有几处』时卡片堆会自己重建一次」。
  角标一旦亮着，之后再改只改角标数字，不再重建。
  道具域不受影响：它原来每次提交都 `tabs.refresh()`，本来就是重建。
- **顺带修掉一个旧 bug**：忍具视图的 `fieldCtx().onCommit` 原来调 `this.refreshTabs()`，
  而 `refreshTabs()` **只在 `RewardView` 里定义**（`ItemView` 没有这个方法）——
  在忍具视图里改任意一个记录字段都会抛 `TypeError: this.refreshTabs is not a function`。
  卡片化时给 `ItemView` 补上了 `refreshCards()`，这条通路才通。
  （`verify_item_view.mjs` 第 13 节现在断的就是它。）
- **`detail-tabs` 容器改名 `detail-cards`**：只是个没有 CSS 的容器
  （`styles.css` 里查不到 `detail-tabs` / `detail-tab-area`），但留着「tabs」字样会误导。
- **写回通路没变**：一律 `pack.setValue` / `pack.setText`，没有新开通路。
- **没有选中记录时**：头部空着，提示留在**卡片内容**里，卡片堆照旧在（结构不跳）。
- 页面文本里没有字面 `**`（两个 `verify_*.mjs` 的第 8/9 节仍在断这条）。

## 5. 断言改了哪几条（口径没有放松）

`rom-editor/tools/verify_character_view.mjs`：

| 节 | 原来断的 | 现在断的 |
|---|---|---|
| 2 | 逐个**切**到七页，每页查关键词；槽位表 ≥ 5 张；控件 > 50；无 undefined/NaN；技能槽能跳到角色特性表 | 逐张**卡片**查关键词（`属性` / `成长` / `特性` / `忍术槽` / `技能槽` / `道具槽` / `头像` 七张都在）；槽位表 ≥ 5 张（实测 6）；控件 > 50（实测 364）；无 undefined/NaN；技能槽能跳到角色特性表 |
| 6a | 右侧有**页签条**；页签标签是预期的那七个 | 右侧有**卡片堆**（`.card-stack`）；**卡片头标题**是预期的那七个（依次） |
| 6b | 头部留在页签外面（`角色定义表 #1`、跳转条不在页签正文里） | 头部留在**卡片**外面（同样两条） |
| 6c | 切过去那一页在 DOM 里、**切走后不在**（互斥） | **七张卡片的内容同时在 DOM 里**（不再互斥）—— 逐张查关键词，并加一条「属性与成长两张卡片的内容都在」 |
| 6d | 角标只在改了的那一页亮；头部「已改 N 处」跟上；**改完一格不重建页签内容（输入框不丢焦点）**；改回去角标灭 | 角标只在改了的那**张卡片**亮（`.card-badge`，值 = '1'），**另外六张没有角标**；头部「已改 N 处」跟上；改完一格「攻击力」的新值还在那张卡片里 + 别的卡片内容没丢；改回去角标灭、头部回到「已改 0 处」 |

`rom-editor/tools/verify_item_view.mjs`：

| 节 | 原来断的 | 现在断的 |
|---|---|---|
| 1 | **切**到「记录字段」页后查：给的是字段名不是「未解字节」；三格标「保留」 | 在「**记录字段**」那张卡片里查同样两件事（不再需要切） |
| 3 | **切**到「掉落位」页后：8 个掉落位；类别与物品都是下拉（≥ 16 个） | 在「**掉落位**」那张卡片里查同样两件事 |
| 4 | 改金币 → 改动计数 +1 → 改回回落 | 同上（输入框改成在「金币」那张卡片里找，口径更准） |
| 6 | **切**到「掉落位置」页后：有「它在哪几关掉落」；默认忍具真被引用；能跳到奖励 | 在「**掉落位置**」那张卡片里查同样三件事 |
| 7 | **切**到「掉落位」页后：有跳到忍具的链接；点它能打开忍具视图 | 在「**掉落位**」那张卡片里查同样两件事 |
| 10 | 有页签条；标签是那三个/那四个；**内容区只有一个（懒渲染）**；切过去在、切走不在 | 有**卡片堆**；**卡片头标题**是那三个 / 那四个（依次）；**所有卡片的内容同时在 DOM 里**；加一条「金币与掉落位两张卡片的内容都在（不再互斥）」 |
| 11 | 页签角标：没改过没有 / 改金币后「金币」页亮 / 「强化点」「掉落位」不亮 | **卡片角标**（`.card-badge`）：没改过没有 / 改金币后「金币」**那张卡片**亮 / 「强化点」「掉落位」**那两张卡片**不亮 |
| 12 | 改掉落位的类别 → 物品下拉换成新类别那张名字表 | 同样一件事，改成在「掉落位」那张卡片里找下拉 |
| 13 | （原来没有） | **新加**：改忍具记录字段不报错（写回通路完整）+ 改动计数 +1 + 改完之后三张卡片的内容还在 DOM 里 |

原来断的「16 个掉落位 / 控件数量 / 跳转链接 / 8 个掉落位 / 类别下拉换候选」
一条都没少，只是改成在卡片里找；**多**断了「卡片堆在不在」「卡片头标题对不对」
「所有卡片同时在 DOM 里」「角标挂在哪张卡片上」「忍具记录字段的写回通路不报错」。

## 6. 重要文件与地址范围

- `rom-editor/js/modules/character.js` — 角色视图（`CharacterView`）。
  内容包里的表：`character_template`（角色定义表，头 12 字节 + 忍术/技能/道具槽）、
  `per_character_stats`（逐角色成长表）、`character_perks`（角色特性表）、
  `portrait_table`（头像指针表，5 个表情 × 图像/调色板）、`portrait_pieces`（头像拼块表）。
- `rom-editor/js/modules/item.js` — 道具域两个视图：`ItemView`（忍具 =
  `item_record` 记录表 16 字节 + 忍具名表）、`RewardView`（奖励 = `reward_table`，
  3 个定宽数字字段 + 8 个掉落位）。
- `rom-editor/js/cards.js` — 通用卡片机制（`CardStack`），本轮**没有**改它。
- `rom-editor/tools/verify_cards.mjs` — 主代理新写的门禁（替代 `verify_tabs.mjs`），
  角色域（第 4 节）与道具域（第 5 节）**全部通过**。

## 7. 验收

```
node rom-editor\tools\verify_syntax.mjs         → exit 0
node rom-editor\tools\verify_character_view.mjs → exit 0
node rom-editor\tools\verify_item_view.mjs      → exit 0
node rom-editor\tools\verify_labels.mjs          → exit 0
node rom-editor\tools\verify_cards.mjs           → exit 1（只剩一条：`js/tabs.js` 还没删 —— 主代理的文件）
node rom-editor\tools\verify_views.mjs           → exit 1（46 条失败，全部不在本轮的两个域）
```

`verify_views.mjs` 那 46 条失败分布在**战斗 / 忍术 / 任务 / 素材（接线表、EWRAM 内存图）**
四个并行改造的域 —— 断言还在找 `tab-bar` / `tab-body` / `tab-badge`。
角色域与道具域在这个门禁里的断言（域首页能渲染、本域表都列得出、不是纯卡片墙、
没有字面星号）**全部通过**。
