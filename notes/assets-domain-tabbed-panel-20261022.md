# 素材与资源域右侧面板页签化（2026-10-22）

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮，页签化的统一口径）
> 改动文件：`rom-editor/js/modules/assets-wiring.js`、
> `rom-editor/js/modules/assets-memory.js`、
> `rom-editor/tools/verify_views.mjs`（只加断言 + 给 DOM 桩补一个 `style.setProperty`）

本轮只动两个视图：**接线总表（`#assets/wiring`）** 与 **EWRAM 内存图（`#assets/memory`）**。
`#assets/records`（图块 / 精灵资源记录表）与 `#assets/overview`（指针接线总表区块）
不在本轮范围内，没有改。

## 1. 原来是什么

两个视图的右侧面板都是**一条纵向长面板**（`renderDetail()` 里一串 `appendChild`）：

### 接线总表（`WiringView`，`rom-editor/js/modules/assets-wiring.js`）

```
detail-head    数据指针表 A · #0   + [← 上一条][下一条 →][✕]
detail-sub     ROM 0x… · 第 1 / 46 条 · 原生读者 …
group 指向哪        指针输入框 + 目标摘要 + 原值 + [↺ 恢复原值][跳到原始字节]
group 改成          [从本表其它项复制…][从另一张指针表复制…][手动填地址]
group 这一项改动的后果   原来指向 0x… / 全包有 N 处指向这个地址 / 判定不到载荷
```

### EWRAM 内存图（`MemoryView`，`rom-editor/js/modules/assets-memory.js`）

```
detail-head    WRAM 分配表 · #0   + [← 上一条][下一条 →][✕]
detail-sub     ROM 0x… · 第 1 / 10 条 · 战斗状态结构 · [已改动]
group 内存分配      起始地址输入框 + 分配大小输入框 + 结束地址 + 原值 + [↺ 恢复原值]
group 这一段的邻接关系   下一段从哪开始 / 空隙多少 / ⚠ 压到下一段前 N 字节 / 是不是同一块
```

## 2. 现在是什么

**头部留在页签外面**（`detail-top` 宿主，只装 `detail-head` 与 `detail-sub`），
**内容进页签**（`TabPanel`）。

### 接线总表：三个页签，key `editor.assets.wiring`

| 页签 id | label | 这一页装什么 | 角标（这一类改了几处） |
|---|---|---|---|
| `target` | 指向哪 | 指针输入框 + 目标摘要 + 原值 + [↺ 恢复原值][跳到原始字节] | `pack.changedStructureRecords(指针表)` 的 `rom_offset` 集合里有没有当前这一条 |
| `replace` | 换成哪一份 | [从本表其它项复制…][从另一张指针表复制…][手动填地址] | 同上（改的就是这一格指针） |
| `impact` | 改动后果 | 原来指向哪 / 全包 N 处同址 / 判定不到载荷的警告 | 无（推出来的文字，不是存下来的） |

### EWRAM 内存图：两个页签，key `editor.assets.memory`

| 页签 id | label | 这一页装什么 | 角标（这一类改了几处） |
|---|---|---|---|
| `allocation` | 内存分配 | 起始地址 + 分配大小 + 结束地址 + 原值 + [↺ 恢复原值] | `pack.changedStructureRecords(wram_allocation)` 的 `rom_offset` 集合里有没有当前这一行 |
| `neighbors` | 邻接关系 | 下一段从哪开始 / 空隙多少 / ⚠ 压到下一段 / 是不是同一块 | 无（推出来的告警） |

两个 key 互不相干（`editor.tabs.` 前缀 + `localStorage` 记住上次停在哪一页）。
角标按**字节**判定（改过又改回去不算改），与通用表格编辑器同一套口径。

## 3. 做法与坑

- **`clear(host)` 的坑**：`renderDetail()` 开头原本 `clear(this.detailWrap)`，会把页签面板一起清掉。
  解法（规格推荐的做法）：`detailWrap` 里放两个**常驻**宿主 ——
  `detailTop`（每次重画头部，`clear` 只清它）与 `detailTabs`（只装 `tabs.element`）。
  页签面板**只建一次**，换一条记录 / 换一行只 `tabs.refresh()` ——
  于是**页签选择与 localStorage 记住的页签都还在**。
- **角标不用手写刷新**：`new TabPanel([...], { key, pack: this.pack })` 里把 `pack` 传进去，
  `tabs.js` 就订阅了内容包的变更通知（`pack.setValue` → `notifyChanged()` → `updateBadges()`），
  每次写回后角标自动跟上。**没有**在每个输入框的 onchange 里手调 `tabs.refresh()`。
- **懒渲染的副作用：跨页签的引用会过期**。
  指针输入框在「指向哪」那一页，结论框在「改动后果」那一页：
  改完值以后只 `refreshTargetLines()` 更新**当前页**的两行（不重建输入框，焦点不丢）；
  另一页的内容等切过去时**重建**，所以永远是新的。
  `assets-memory.js` 同理：`updateWarnings()` 拆成 `updateAllocationLines()`（当前页）
  与 `updateNeighborWarnings()`（另一页，切过去时重建）。
- **写回通路没变**：一律 `pack.setValue`，没有新开通路。
- **「手动填地址」按钮**：指针框在「指向哪」那一页，所以这个按钮先
  `this.tabs.setActive('target')` 再聚焦（否则聚焦一个已经不在 DOM 里的节点，白按）。
- **没选中记录时**：头部空着，提示放在页签内容里（`tabContent()` 认得这个情况），
  页签条照旧在（结构不跳）。

## 4. 顺手改掉 / 发现的（都记在这）

- **「跳到原始字节」跳的是旧地址**（接线总表）：按钮原来闭包捕获了渲染那一刻的 `value`，
  改完指针再点会跳到改之前的地址。现在改成点击时现读 `record.values[field.key]`。
- **EWRAM 的「原值」那行显示的是当前值，不是原值**（**未改，记下来备查**）：
  `updateAllocationLines()` 里 `originalAddr = record.values[ADDR_FIELD]`、
  `originalSize = record.values[SIZE_FIELD]` —— 这两个是**当前**值，
  真正的原值要用 `originalValue(this.table, record, field)`（文件里已经 import 了，
  `restore()` 就在用）。本轮只做页签化，没有动这一行的口径。
- **无头 DOM 桩缺 `style.setProperty`**：`splitPane()` 在 `wide: true` 时会写
  `--split-right` 这个 CSS 变量，`verify_views.mjs` 里的 `StubNode` 原来只有
  `style = {}` → 素材域两个视图根本渲染不出来（`container.style.setProperty is not a function`）。
  给桩补了 `setProperty` / `getPropertyValue` 两个空实现 —— 只是让桩能跑起来，
  没有放宽任何一条断言。

## 5. 重要文件与地址范围

- `rom-editor/js/modules/assets-wiring.js` — 接线总表（`WiringView`），
  结构表：`data_pointer_table_a`（46 槽，ROM 0x…）、`data_pointer_table_b`（90 槽）。
- `rom-editor/js/modules/assets-memory.js` — EWRAM 内存图（`MemoryView`），
  结构表：`wram_allocation`（10 行，ROM 0x53D848 起，8 字节/行；
  7 段不同的 EWRAM：0x02022E30 / 0x020240AC / 0x020240C0 / 0x02025884 / 0x02026604 / 0x02026804 / 0x02026BC8）。
- `rom-editor/js/tabs.js` — 通用页签机制（`TabPanel`），本轮**没有**改它。

## 6. 验收

`rom-editor/tools/verify_views.mjs` 新增第 18 节
「素材与资源：接线表与 EWRAM 内存图的右侧面板分页签」，共 29 条断言：

- 两个视图各自：页签条存在、页签数量与标签是预期的那几个、头部留在页签外面
  （`detail-head` 不在 `tab-body` 里）；
- 默认停在第一页（接线表有指针输入框 / 内存图有地址与大小两个输入框），
  别的页的内容不在；
- 切到某一页后那一页的内容在 DOM 里（复制下拉 / 「这一项改动的后果」/「下一段：…」），
  切走后不在，切回来又回来了；
- 改一格之后页签上出现角标 `1`（接线表与内存图各一条），并核对了写回内容包；
- 外加一条回归护栏：同一文件里的兄弟视图 `#assets/records`（资源记录表）本轮没改，但仍能渲染。

三个门禁：

```
node rom-editor\tools\verify_syntax.mjs    → exit 0
node rom-editor\tools\verify_views.mjs     → exit 0
node rom-editor\tools\verify_labels.mjs    → exit 0
```

（跑门禁时 `verify_syntax.mjs` 曾经是红的：`js/modules/jutsu.js` 是另一个子代理
（忍术域）当时正在写的文件，语法没过；本轮收尾时它已经修好，门禁恢复全绿。
`verify_audio_workbench.mjs` 与 `verify_tabs.mjs` 当时是红的：音频域的子代理
正在把音效工作台改成页签，探针还没跟上 —— 与素材域无关。）
