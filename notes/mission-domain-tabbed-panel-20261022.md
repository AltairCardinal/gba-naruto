# 任务视图右侧面板页签化（2026-10-22）

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮，页签化的统一口径）
> 改动文件：`rom-editor/js/modules/mission.js`、`rom-editor/tools/verify_views.mjs`（只加断言）

## 1. 原来是什么

`#route/mission` 的右侧面板（`MissionView.renderDetail()`）是一条**纵向长面板**：

```
detail-head   第 N 关
detail-sub    索引表第 N 条 · 基址 #N
mission-index 本关的基址（索引表那一格）+ 脚注
mission-sub ×3
  ├── route-sub   子任务 1/2/3
  ├── mission-texts（3 个 mission-text-field：标题 / 说明 / 提示）
  ├── route-reward（金币 / 强化点 / 等级门槛）
  ├── route-reward-drops（掉落位 8 位）
  └── route-reward-foot（奖励表下标脚注）
```

改一句「说明」要先滚过基址与三张标题 —— 一屏看完头。

## 2. 现在是什么

**头部留在页签外面**（`mission-detail-head` 宿主，只装 `detail-head` 与 `detail-sub`），
**内容进五页签**（`TabPanel`，key `editor.mission`）：

| 页签 id | label | 这一页装什么 | 角标（这一类改了几处） |
|---|---|---|---|
| `base` | 基址 | 索引表里这一关的那一格（改它会换掉整关的任务与奖励） | `pack.changedStructureRecords(mission_index)` 的 `rom_offset` 集合 |
| `titles` | 标题 | 任务标题表：三个子任务的标题 | `pack.changedTextRecords(mission_titles)` 的 `id` 集合 |
| `descriptions` | 说明 | 任务说明表：三个子任务的说明 | `pack.changedTextRecords(mission_descriptions)` 的 `id` 集合 |
| `hints` | 提示 | 任务提示表：三个子任务的提示 | `pack.changedTextRecords(mission_hints)` 的 `id` 集合 |
| `rewards` | 奖励 | 本关的三份奖励：金币 / 强化点 / 等级门槛 + 8 个掉落位 | `pack.changedStructureRecords(reward_table)` 的 `rom_offset` 集合 |

判定口径与通用表格编辑器一致（**按字节比**，改过又改回去不算改）。
左边列表的「已改 N」现在由同一套判定算出（`stageChanged()` = 三个文本页签 + 奖励页签之和）。

## 3. 做法与坑

- **`clear(host)` 的坑**：`renderDetail()` 开头原本 `clear(this.detailWrap)`，会把页签面板一起清掉。
  解法（按规格推荐）：`detailWrap` 里放两个**常驻**宿主 ——
  `headHost`（每次重画头部）与 `tabs.element`（只建一次，换关卡只 `refresh()`）。
  于是**换关卡时页签选择与 localStorage 记住的页签都还在**。
- **写回通路没变**：文本仍走 `pack.setText`，字段仍走 `pack.setValue`，没有新开通路。
- **改完不重建内容**：文本改完只重画页签条上的角标（`setBadge(id, null)` → 角标按当前数据重算），
  不整页重建 —— 重建会把作者正在编辑的输入框换掉，焦点就没了。
  字段改动走 `fieldCtx().onCommit`：改基址 / 改道具类别才整页重画，其余只更新角标。
- **`isChanged()` 删掉了**：它自己算 `recordBytes` 比 `raw`，与
  `pack.changedStructureRecords()` 完全等价；现在统一走内容包那一份，少两套判定。

## 4. 顺手发现的 tabs.js 缺口（**不是本轮改的**）

`TabPanel.refresh()` 只做 `renderBody() + renderBar()`，**不调 `syncBar()`**；
而 `renderBar()` 把每个按钮重建成 `class="tab-btn"`（没有 `active`）。
于是**任何一次 refresh() 之后，当前页的高亮就没了**（`.tab-btn.active` 的样式丢失）。

受影响的不止本域：`battle-map.js` / `scene.js` / `item.js` / `character.js` 走的都是同一个 `TabPanel`。

本域的绕法（在 `mission.js` 里，没动 `tabs.js`）：

```js
this.tabs.refresh();
this.tabs.setActive(this.tabs.active);   // 同一个 id：不重建内容，只把高亮标回来
```

**建议在 `tabs.js` 里把 `syncBar()` 补进 `refresh()`**，那样各域都能省掉这个绕法。

## 5. 验收

`rom-editor/tools/verify_views.mjs` 新增第 17 节「剧情路线 · 任务视图：右侧面板分页签」，
共 22 条断言：页签条存在、五个页签标签、头部留在页签外面、切到某页该页内容在 DOM 里、
切走后不在、各页装的是不是它该装的东西、改完出现角标、换关卡后页签不被重建。

三个门禁：

```
node rom-editor\tools\verify_syntax.mjs    → exit 0
node rom-editor\tools\verify_views.mjs     → exit 0
node rom-editor\tools\verify_labels.mjs    → exit 0
```

（`verify_route_workbench.mjs` 当时是红的：另一个子代理正在把 `route.js` 的关卡工作台也改成页签，
奖励搬进了页签里，那份探针还没跟着改。与本域无关。）
