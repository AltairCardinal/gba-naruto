# 音频域 + 素材域：页签 → 卡片纵排（2026-10-22）

> 规格：`notes/specs/human-readable-cards-20261022.md`（第十轮，推翻第九轮的页签方案）
> 改动文件：
> - `rom-editor/js/modules/audio-workspace.js`
> - `rom-editor/js/modules/assets-wiring.js`
> - `rom-editor/js/modules/assets-memory.js`
> - `rom-editor/tools/verify_audio_workbench.mjs`（音频域的断言）
>
> **没改**：`rom-editor/js/cards.js`（通用机制由主代理写）、`rom-editor/styles.css`、
> `rom-editor/js/tabs.js`、`rom-editor/tools/verify_views.mjs`（素材域的断言由主代理改）。

起因是作者的原话：「不要用页签了，改成同一个滚动页面中纵向排列的的卡片」。
页签把其余类别**藏起来** —— 作者看到「成长」这一页时不知道还有几类东西没看。
这一轮**保留分类，去掉切换**：类别还是类别（一张卡片一张），但不互斥、不隐藏。

---

## 1. 原来是什么（第九轮的页签）

| 视图 | 页签数 | 页签标题 |
|---|---:|---|
| 音效工作台（`sound_id_table` 的详情面板） | 3 | 描述符 / 谁指向它 / 播放入口 |
| 乐曲描述符（`audio_song_*` 视图） | 3 | 描述符 / 谁指向它 / 播放入口 |
| 接线表（`#assets/wiring`） | 3 | 指向哪 / 换成哪一份 / 改动后果 |
| EWRAM 内存图（`#assets/memory`） | 2 | 内存分配 / 邻接关系 |

页签机制（`rom-editor/js/tabs.js` 的 `TabPanel`）的三条约定：懒渲染、
记住当前页签（`key` + localStorage）、角标（这一类改了几处）。

## 2. 现在是什么（卡片）

| 视图 | 卡片数 | 卡片头标题（依次） | 卡片头下的说明（`hint`） |
|---|---:|---|---|
| 音效工作台 | 3 | 描述符 / 谁指向它 / 播放入口 | 这个音效指向哪个 m4a 描述符… / 反向引用… / 播放通道与播放配置… |
| 乐曲描述符 | 3 | 描述符 / 谁指向它 / 播放入口 | 这个 m4a 描述符的字段… / 反向引用… / 函数指针表里与这些音效对应的播放 thunk… |
| 接线表 | 3 | 指向哪 / 换成哪一份 / 改动后果 | 这一格的指针值… / 从本表 / 另一张指针表复制… / 改这一格会动到谁… |
| EWRAM 内存图 | 2 | 内存分配 / 邻接关系 | 这一行的起始地址与分配大小… / 这一段与下一段挨不挨着… |

**所有卡片的内容同时在 DOM 里**（这是与页签最大的不同）。
「头部」（`detail-head` / `detail-sub`：哪一格、ROM 地址、原生读者、已改动）
仍在卡片堆**外面** —— 它回答「我现在看的是哪一条」，卡片回答「这一条有哪几面可看」。

角标从页签条挪到**卡片头**（`.card-badge`），口径没变：按字节判定
（改过又改回去不算改），走 `pack.changedStructureRecords` 的 `rom_offset` 集合。

## 3. 机械替换对照（`TabPanel` → `CardStack`）

| 原来 | 改成 |
|---|---|
| `import { TabPanel } from '../tabs.js';` | `import { CardStack } from '../cards.js';` |
| `new TabPanel([...], { key: '…', pack })` | `new CardStack([...], { pack })` —— **去掉 `key`**（卡片没有「当前页」） |
| `this.tabs` | `this.cards` |
| `this.tabs.element` | `this.cards.element` |
| `this.tabs.refresh()` | `this.cards.refresh()` |
| `this.tabs.setBadge(id, t)` | `this.cards.setBadge(id, t)` |
| `this.tabs.setTabs([...])` | `this.cards.setCards([...])` |
| `this.tabs.setActive('x')` | **删掉**（卡片全都同时可见，不需要切） |

方法名也跟着改（避免留下「Tab」字样）：
`tabSpecs()` → `cardSpecs()`、`tabContent()` → `cardContent()`、
`renderXxxTab()` → `renderXxxCard()`。

## 4. 做法与坑

- **`setActive` 只有一处**：接线表的「手动填地址」按钮原来先 `setActive('target')`
  再聚焦指针框（页签版本里指针框在别的页上，不切过去聚焦不到）。
  卡片版本里两张卡片**同时**在页面上，所以直接 `this.input.focus()` 就行 ——
  这一处是「切到另一个卡片然后聚焦那个卡片里的输入框」的正解。
- **焦点会丢（页签版本不会）**：`CardStack.updateBadges()` 在角标**出现 / 消失**时
  会 `this.render()` —— 整摞卡片重建，输入框也跟着重建，焦点就没了。
  （`TabPanel.updateBadges()` 只重画页签条，页签体不动，所以输入框不重建。）
  补了三处 focus 还原，保住原来「改一个数不用重新点一次框」的手感：
  - `assets-wiring.js` 的 `fieldCtx().onCommit`（指针框）
  - `assets-memory.js` 的 `commitSize()` / `commitAddress()`（大小框 / 地址框）
  还原时都写成 `if (input && input.focus) input.focus()` —— 无头 DOM 桩没有 `focus`。
- **接线表有两张卡片共用同一个角标**：`指向哪` 与 `换成哪一份` 的角标都是
  `pointerChanged()`（原规格就是这样：改的就是这一格指针）。
  所以改一格指针 → **两张卡片各亮一个角标 1**，`改动后果` 没有角标。
  这是原口径，不是新引入的。
- **`detail-tabs` 容器改名 `detail-cards`**：只是个没有 CSS 的容器
  （`styles.css` 里查不到 `detail-tabs`），但留着「tabs」字样会误导。
- **写回通路没变**：一律 `pack.setValue`，没有新开通路。
- **没选中记录时**：头部空着，提示放在**卡片内容**里（`cardContent()` 认得这个情况），
  卡片堆照旧在（结构不跳）。

## 5. 断言改了哪几条（口径没有放松）

`rom-editor/tools/verify_audio_workbench.mjs`：

| 节 | 原来断的 | 现在断的 |
|---|---|---|
| 3 | 反查块在详情里（先切到「谁指向它」再看） | 反查块在详情里 —— **在「谁指向它」那张卡片里**（不再需要切） |
| 9 | 右侧有页签条 / 标签是三个 / **页签内容区只有一个（懒渲染）** / 默认停在「描述符」/ 切过去后反查块在 / 切走后不在 | 右侧有**卡片堆** / 每张是 `.editor-card` / **卡片头标题是三个** / 每张都有内容区 / **三张卡片的内容同时在 DOM 里** / 「描述符」卡片里下拉与自定义地址都在 / 「谁指向它」卡片里有反查块 / 「播放入口」卡片里有播放通道与推定 |
| 10 | 角标：没改过没有 / 写回后「描述符」页签亮 1 / 改回去消失 | 同上，改成 `.card-badge`；**另加两条**：角标挂在「描述符」那张卡片上 / **别的卡片上没有角标** |
| 11 | 乐曲描述符有页签条 / 默认页是「描述符」/ 能切到「谁指向它」/ 能切到「播放入口」/ 标明了「推定」 | 乐曲描述符有**卡片堆** / 标题也是三个 / 「描述符」卡片有歌曲头与轨道表 / 「谁指向它」卡片有反查块 / 「播放入口」卡片标明了「推定」/ **三张卡片的内容同时在 DOM 里** |

原来断的三件事 —— **反查块、播放通道、描述符下拉的 81 个选项** —— 都还在，
只是改成在卡片里找；第 9 节还**多**断了一条「下拉里还是 81 个选项」，
第 10 节多断了「角标挂在哪张卡片上」。没有放宽任何一条。

素材域的断言在 `rom-editor/tools/verify_views.mjs` 第 18 节，
**由主代理改**（本轮没动那个文件）。它现在的 18 条失败全部是
「还在找 `tab-bar` / `tab-btn` / `tab-body` / `tab-badge`」的旧断言 ——
DOM 本身是对的（用卡片选择器逐条复核过：卡片堆、卡片标题、
输入框、反查块、角标全都在）。

## 6. 重要文件与地址范围

- `rom-editor/js/modules/audio-workspace.js` — 音效工作台（`AudioSoundTable`，
  结构表 `sound_id_table`，159 行 × 8 字节，ROM 0x465B70 起）与
  乐曲描述符（`renderSongDescriptor`，81 张 `audio_song_*`）。
- `rom-editor/js/modules/assets-wiring.js` — 接线表（`WiringView`），
  结构表 `data_pointer_table_a`（46 槽）/ `data_pointer_table_b`（90 槽）。
- `rom-editor/js/modules/assets-memory.js` — EWRAM 内存图（`MemoryView`），
  结构表 `wram_allocation`（10 行，ROM 0x53D848 起，8 字节/行；
  7 段不同的 EWRAM：0x02022E30 / 0x020240AC / 0x020240C0 / 0x02025884 /
  0x02026604 / 0x02026804 / 0x02026BC8）。
- `rom-editor/js/cards.js` — 通用卡片机制（`CardStack`），本轮**没有**改它。
- `rom-editor/js/modules/audio-workspace.js` 的改动随主代理的检查点提交
  `289282eb`（feat(editor): 通用卡片层落地）一起入库；
  `assets-wiring.js` / `assets-memory.js` / `verify_audio_workbench.mjs`
  留在工作区，随后单独入库。

## 7. 验收

```
node rom-editor\tools\verify_syntax.mjs         → exit 0
node rom-editor\tools\verify_audio_workbench.mjs → exit 0
node rom-editor\tools\verify_labels.mjs          → exit 0
node rom-editor\tools\verify_views.mjs           → exit 1（见下）
```

`verify_views.mjs` 当时是红的，共 46 条失败，分三处：

| 处 | 条数 | 归谁 |
|---|---:|---|
| 第 18 节「素材与资源」 | 18 | **本轮的改动** —— 那个文件里的断言还在找页签（`tab-bar` / `tab-body` / `tab-badge`），主代理正在改 |
| 战斗域（第 2 节等） | 15 | 战斗域的并行改造（`battle-map.js` 正在改成卡片） |
| 角色 / 任务域 | 13 | 角色域、任务域的并行改造 |

**另外**：主代理新写的 `rom-editor/tools/verify_cards.mjs`
（替代 `verify_tabs.mjs`）里，音频域（第 7 节）与素材域（第 8 节）**全部通过** ——
卡片堆、卡片标题、数量、内容同时在 DOM 里、角标各归各的，都对。
该门禁只剩一条失败：`js/tabs.js` 还没删（规格 §2.3 要求删）—— 那是主代理的文件。
