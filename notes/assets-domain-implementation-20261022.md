# 素材与资源域的交互重设计 —— 落地记录（2026-10-22）

> 规格：`notes/specs/assets-domain.md`（主代理定稿）。
> 本文只记**落地结果**与**需要别人配合的事**，设计不在这里重复。

## 落地了什么

| 文件 | 状态 | 负责 |
|---|---|---|
| `rom-editor/js/modules/assets.js` | 重写 | 域首页（结论横幅 / 三张任务卡 / 本域可编辑内容表 / 指针接线总表）+ 按 `panel.kind` 分发 |
| `rom-editor/js/modules/assets-wiring.js` | 新建 | 共享 helper（`targetSummary` / `pointerRefs` 缓存 / `hex32`）+ 接线表视图 + 79 条资源记录视图 + 指针接线总表 |
| `rom-editor/js/modules/assets-memory.js` | 新建 | EWRAM 内存条带 + 邻接/覆盖告警 |
| `rom-editor/css/assets.css` | 新建 | 本域样式（`index.html` 里已链好） |

三个子视图（`wiring` / `records` / `memory` / `overview`）与
`panel.kind === 'structure'` 的四张表（`data_pointer_table_a` / `_b` /
`tile_asset_records` / `wram_allocation`）**都走本域自己的视图** ——
从任何入口进去都是带目标摘要、邻接告警与范围校验的那一套。

## 写回

只走 `pack.setValue`：指针、起始地址、分配大小都经它写。
原始字节那一侧（`head` / `mid` / `raw_34`）仍按原字节保留，未改动就原样写回。

## 实测数字（全部从内容包算出来，代码里没有写死）

- 数据指针表 A 46 槽 / B 90 槽；A 全部非空，B 有 7 个空槽与 4 个不在 ROM 范围内的值。
- 图块记录 79 条 × 9 个指针槽 = 711 槽，其中 675 个非空，指向 295 个不同目标；
  **31 种图块组合 / 69 种脚本组合**（最大一组 10 条记录共用）。
- 指针接线总表 46 + 90 + 711 = **847 个指针槽**。
- WRAM 分配表 10 行 → **7 段**不同的 EWRAM（#0/#1/#3 同一块，#2/#4 同一块；
  段名只有 #0/#1/#3 战斗状态结构、#5 战斗控制标志、#7 战斗主数据有仓库依据，
  其余写「未命名」）。

## 覆盖告警怎么算的

段 = （起始地址 + 分配大小）相同的行合并；「下一段」= 地址严格更大的那一段
（同一地址的两段是叠着的，不是相邻）。
把大小改成 S 后，段尾 = 起始地址 + S；
`段尾 > 下一段起始` ⇒ 压到下一段前 `段尾 − 下一段起始` 字节。
例：#0 从 4732 改成 5000 ⇒ `⚠ 把大小改成 5000 字节会压到 #2（从 0x020240AC 开始）的前 268 字节。`

## 需要主代理配合的改动

1. **`rom-editor/js/routing.js` 要认识本域的子视图。**
   现在 `parseHash` / `hashFor` 只认 stage / graph / structure / text / script / raw-offset，
   所以本域**故意没有走 `ctx.openPanel`**（它会同步改写 hash，改写后的 hash 会在
   `hashchange` 里把面板重置掉，视图刚打开就被弹回首页），而是直接写
   `ctx.state.view.panel` + `ctx.render()`。代价是子视图**不可深链**、
   浏览器后退键回不去。建议 routing.js 加：
   `#assets/wiring` / `#assets/records` / `#assets/memory` / `#assets/overview`
   ↔ `{kind, id, params}`（本域按 `kind` 分发，`id` 只是面包屑上的中文标签）。
2. **内容包给 `wram_allocation` 补 `consumers`。**
   现在包里没有，WRAM 横幅里的「原生读者」那句只能省掉；
   规格 §3.4 写的 4 个读者地址（`0x0806869A` / `0x08068954` / `0x08068CC0` / `0x08068D98`）
   来自 `notes/battle-config-format.md`，应当由导出器写进内容包，而不是写进界面代码。
3. **本域劫持了这四张表的 `structure` 面板。**
   若还想让通用表格编辑器能打开它们，需要 routing 或 app 层给一个「绕过」的入口；
   目前本域的「本域可编辑内容」表里的「入口」按钮直接进本域视图。
4. `structure.verification` 的口径（「仓库里没有专用导入工具」≠「编辑器不写回」）
   是全域通用问题，仍归主代理（规格 §7.2）。

## 验证

```
node rom-editor\tools\verify_syntax.mjs      # 全部通过（37 个文件）
node rom-editor\tools\verify_views.mjs       # 全部通过
python -m unittest discover -s tests          # Ran 84 tests OK
python tools\export_content_pack.py --check   # OK
```

规格 §6 的 6 条验收标准另用一份临时无头脚本逐条跑过（复用
`verify_views.mjs` 的 DOM stub，跑完即删）：横幅含「改指针能换资源」与
「载荷本身动不了」且页面无 `**`；A#0 指针框显示 `0x0859F988`、改成
`0x0859FA18` 后 `recordBytes` 前 4 字节 = `18FA5908` 且已改计数 +1；
搜 `0x0859F988` 与搜 `140114312` 命中同一行；记录详情是 6 行 + 3 行两张表
（共 9 个指针控件，每行带目标摘要）；条带 7 段且 #0/#1/#3 合并、改 5000 给出
「会压到 #2（从 0x020240AC 开始）的前 268 字节」；越界指针与越界 EWRAM 地址
都当场 toast 拒绝且不写入。

## 调试方法备忘

- 载荷类型判定来自内容包 `derived.pointer_targets`（导出时判定，不载入 ROM 也能用）；
  查地址用 `pack.pointerTarget(address)`，键是 8 位补零的 `0xXXXXXXXX`。
- 「全包同址计数」用 `xref.backReferencesByPointer(pack, address)`，
  一次扫描要过 6000 多个指针格，所以本域按地址缓存（`clearPointerCache()` 在改动时清）。
- `editors.valueMatches(value, query)` 让搜索同时吃十六进制与十进制。
