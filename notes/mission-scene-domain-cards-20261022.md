# 任务域 / 场景域 / 字库域：右侧面板页签 → 卡片纵排（2026-10-22）

> 规格：`notes/specs/human-readable-cards-20261022.md`（第十轮的统一口径）
> 通用机制：`rom-editor/js/cards.js` 的 `CardStack`（主代理写的，本轮不碰）
> 改动文件：`rom-editor/js/modules/mission.js`、`rom-editor/js/modules/scene.js`、
> `rom-editor/tools/verify_scene_view.mjs`
>
> **上一轮那两份笔记里的「页签」说法已过时**：
> `notes/mission-domain-tabbed-panel-20261022.md`、`notes/scene-domain-tabbed-panel-20261022.md`
> 描述的是第九轮的页签版式；本文件描述的是第十轮的卡片版式（页签已被推翻）。

## 1. 起因

用户原话：「**不要用页签了，改成同一个滚动页面中纵向排列的的卡片**」。

页签的问题（第九轮自己也写进规格了）：作者看到「成长」这一页时**不知道还有几类东西没看**；
切页签会丢掉滚动位置，来回比对很烦。

⇒ 这一轮**保留分类，去掉切换**：类别还是分类（= 一张卡片），但不互斥、不隐藏。

## 2. 改了什么

| 域 | 原来（页签） | 现在（卡片，竖排） | 卡片 id |
|---|---|---|---|
| 任务 `#route/mission` | 5 页签 | **5 张**：基址 / 标题 / 说明 / 提示 / 奖励 | `base` / `titles` / `descriptions` / `hints` / `rewards` |
| 场景 `#story/scene` | 4 页签 | **4 张**：战前 / 战后 / 逻辑 / 事件 | `before` / `after` / `logic` / `events` |
| 字库 `#story/font` | 2 页签 | **2 张**：字形段 / 字宽 | `segments` / `widths` |

卡片规格的形状没变（`{ id, label, hint, badge, render }`）：
- `label` 现在是**卡片头的标题**（还是原来那几个字，作者不用重新认）；
- `hint` 还在 —— 它现在是卡片头下面那一行说明，给作者看这组东西是干嘛的；
- `badge` 还是「这一类改了几处」（按字节判定，与通用表格编辑器同一套口径）。

**头部仍在卡片外面**：`detail-head` / `detail-sub`（第几关、索引表第几条、基址 #N）
留在 `mission-detail-head` / `scene-detail-head` / `font-detail-head` 三个宿主里，
不属于任何一张卡片。

### 2.1 机械替换的对照表

| 原来 | 现在 |
|---|---|
| `import { TabPanel } from '../tabs.js'` | `import { CardStack } from '../cards.js'` |
| `new TabPanel([...], { key: '...', pack })` | `new CardStack([...], { pack })`（**去掉 `key`**：卡片没有「当前页」） |
| `this.tabs` | `this.cards` |
| `this.tabs.element` / `.refresh()` / `.setBadge(id, t)` | `this.cards.element` / `.refresh()` / `.setBadge(id, t)` |
| `this.tabs.setActive('x')` | **删掉**（卡片全都同时可见，没有「切过去」这回事） |

顺带把内部方法名从「页」改成「卡」（都在本域文件内部，外部没有引用）：
`missionTabs` → `missionCards`、`renderBaseTab` → `renderBaseCard`、
`renderTextTab` → `renderTextCard`、`renderRewardTab` → `renderRewardCard`、
`sceneTabs` → `sceneCards`、`renderRootTab` → `renderRootCard`、
`renderSegmentTab` → `renderSegmentCard`、`renderWidthTab` → `renderWidthCard`。

### 2.2 `setActive` 的两处用途

页签时代 `mission.js` 里有两处 `setActive`，都**不是**「切过去再聚焦输入框」：

```js
this.tabs.refresh();
this.tabs.setActive(this.tabs.active);   // refresh() 重建页签条后把高亮标回去
```

那是 `tabs.js` 的一个缺口（`refresh()` 不调 `syncBar()`，高亮会掉），
卡片机制里**没有高亮也没有「当前页」**，所以两处都直接删掉。
（`route.js` 里那个「切到卡片再聚焦标题输入框」的用法，由主代理改成直接 `input.focus()`。）

### 2.3 角标的重算

`mission.js` 原来靠 `refreshBadges()` 做「只重画页签条上的角标、不重建内容」，
现在改成：

```js
refreshBadges() {
  if (!this.cards) return;
  for (const card of this.cards.cards) this.cards.setBadge(card.id, null);
}
```

`setBadge(id, null)` 清掉角标覆盖，角标于是回到 `card.badge()` 按当前数据算出的真值。

## 3. 坑与取舍

- **`CardStack.updateBadges()` 会整摞重画**：
  角标「从无到有」或「从有到无」时它调 `render()`，**把全部卡片重建一遍** ——
  也就是说改一句任务标题，正文输入框会被换掉（如果作者是按回车提交，焦点会掉）。
  页签时代靠「只重画页签条」保住了焦点（见上一轮笔记 §3），卡片机制下保不住。
  这是 `cards.js`（主代理的文件）层面的取舍，**本轮没动**；内容重建后仍是当前数据，
  值不会错，只是焦点会掉。
- **`mission.js` 的说明文字里有过字面 `**`**：
  `section-note` 里原来写的是「左边按**任务索引表**列出」。编辑器不渲染 markdown，
  虽然 `ui.js` 的 `stripStars` 会替 `section-note` 这类容器兜底，
  但源码里不该留这种写法 —— 已改成「左边按任务索引表列出」。
- **写回通路没变**：文本仍走 `pack.setText`，字段仍走 `pack.setValue`，没有新开通路。

## 4. 断言怎么改的（`rom-editor/tools/verify_scene_view.mjs`）

辅助函数换掉：`switchTab` / `tabLabels` / `tabBadges` →
`cardList` / `cardTitles` / `cardByTitle` / `cardBadges`（按 `.editor-card` 与
`.editor-card-title` 找卡片，按 `.card-badge` 找角标）。

| 组 | 原来（页签口径） | 现在（卡片口径） |
|---|---|---|
| 2 | 页签条存在、五个/四个页签名、逐页切过去数指针 | 卡片堆存在、卡片名一致、**逐张卡片**数指针（每张恰好一个） |
| 3 | 切到「字宽」后字宽表在 DOM 里 | 「字宽」卡片里有字宽表（256 行，每行一个输入框） |
| 4 | 切到「字宽」再改字段 | 直接在「字宽」卡片里改字段（写回 +1、改回回落） |
| 7 | 切页签再数指针 / 切到「字宽」 | 换场景后四张卡片都在；「字形段」卡片里的字段仍可改 |
| 8 | 页签条 / 切走后不在 DOM 里 / 角标挂在改过的那一页 | 卡片堆 / **所有卡片的内容同时在 DOM 里** / 角标挂在改过的那**张**卡片上 |

**口径没有放松**，反而多了一条：

- 旧口径「四个指针、每页恰好一个、跳到哪张根表」→ 新口径「四个指针、**每张卡片**恰好一个、
  跳到哪张根表」，并且加了一条**卡片标题 → 根表名**的映射断言
  （战前→战前剧情、战后→战后剧情、逻辑→战场事件逻辑、事件→战场事件表）。
- 旧口径「切走后那一页的内容不在 DOM 里」在卡片语义下**反过来**了：
  卡片**不互斥**，要断的正是「所有卡片的内容**同时**在 DOM 里」。
  这一条是新加的，也是这一轮的核心诉求。
- 角标口径不变：改过的那张卡片上有角标、别的没有，改回原值后角标消失。

## 5. 验收

```
node rom-editor\tools\verify_syntax.mjs      → exit 0
node rom-editor\tools\verify_scene_view.mjs  → exit 0
node rom-editor\tools\verify_labels.mjs      → exit 0
node rom-editor\tools\verify_views.mjs       → exit 1（红点不在本域，见下）
node rom-editor\tools\verify_cards.mjs       → exit 1（唯一红点：js/tabs.js 还在，主代理要删）
```

- `verify_cards.mjs`（主代理新建的卡片门禁）里，**任务 / 场景 / 字库三个域全绿**：
  卡片堆、卡片名（基址·标题·说明·提示·奖励 / 战前·战后·逻辑·事件 / 字形段·字宽）、
  「所有卡片的内容同时在 DOM 里」、角标各归各的 —— 全过。
- `verify_views.mjs` 第 17 组（任务视图）**还是页签口径，红 12 条**，由主代理改；
  其余红点在战斗域与素材域（并行改造中，与本域无关）。
  **有一处要提醒主代理**：第 17 组里那两条「「标题」页里不混着「说明」页的文案」/
  「「说明」页里不混着「提示」页的文案」**现在是空过**（它们去找 `.tab-body` 里的输入框，
  卡片版没有 `.tab-body`，找到任何输入框，于是 `!some(...)` 恒真）——
  它们看着是绿的，其实已经不测任何东西了，必须改成「按卡片找」才作数。
  为了不空口说「本域没问题」，用一张**临时探针**（写在 gitignored 的 `build/` 下，
  跑完已删）按第 17 组的**同一口径**改成卡片口径跑了一遍任务域：
  卡片堆 / 五张卡片名 / 头部留在卡片外面 / 每张卡片装的是不是它该装的东西 /
  五张卡片内容同时在 DOM 里 / 改标题后只有「标题」那张卡片亮角标 /
  左边列表第 40 关的「已改」是 1 / 换关卡后头部跟着换且五张卡片还在 —— **18 条全过**。

## 6. 重要文件

- `rom-editor/js/modules/mission.js` —— 任务视图（5 张卡片）
- `rom-editor/js/modules/scene.js` —— 场景视图（4 张卡片）+ 字库视图（2 张卡片）
- `rom-editor/tools/verify_scene_view.mjs` —— 场景/字库域的卡片断言
- `rom-editor/js/cards.js` —— 通用机制 `CardStack`（主代理的，本轮只调用）
