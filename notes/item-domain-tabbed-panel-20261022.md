# 道具域右侧面板页签化（忍具 / 奖励）— 2026-10-22

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮 · 页签化）。
> 参考实现：`rom-editor/js/modules/battle-map.js`（战场地图那 5 个页签）。
> 通用机制：`rom-editor/js/tabs.js` 的 `TabPanel`。

## 做了什么

只改了两个文件：

- `rom-editor/js/modules/item.js`
- `rom-editor/tools/verify_item_view.mjs`

两个视图的右侧面板都从「一串纵向追加」改成**页签**（头部仍在页签外面）：

| 视图 | 原来纵向堆叠的段落 | 现在的页签 | 每一页装什么 |
|---|---|---|---|
| 忍具 `#items/item`（key `editor.item`） | 名字（忍具名表）/ 这个忍具的记录（未解字节）/ 它在哪几关掉落 | 名字 · 未解字节 · 掉落位置 | 名字页 = 文本框 + 字节数预览 + 共用提示 + 跳到名表；未解字节页 = 16 字节 hex 编辑区 + 逐字节折叠表；掉落位置页 = 槽/第几关/类别/物品 id/跳转 表 + 「掉落关系改在奖励那一侧」脚注 |
| 奖励 `#items/reward`（key `editor.reward`） | 这一条给什么（金币/强化点/等级门槛并排）/ 掉落位（0 表示列表结束）/ 归属脚注 | 金币 · 强化点 · 等级门槛 · 掉落位 | 三个数字字段**各一页**（页签 id / 标签都从内容包的字段表取，不写死）；掉落位页 = 8 个掉落位表（类别 + 物品）+ 列表结束说明 + 「这一条掉的忍具」反向跳转 |

归属脚注（这一条是哪几关的奖励）留在**页签外面**（详情面板底部）—— 它说的是归属，
不是掉落位；放页签外可以一直看得见。

## 关键决定与踩过的坑

1. **`clear(host)` 会把页签面板一起清掉**。解决办法用规格里推荐的那条：
   `this.detailWrap` 里再分三个容器 —— `detailHead`（每次重画）、
   `detailTabs`（**常驻，clear 不到**）、`detailFoot`（每次重画）。
   `TabPanel` 实例挂在 `this.tabs` 上，只 new 一次；
   换忍具 / 换奖励时只调 `this.tabs.refresh()`，页签选择与 localStorage 记忆都还在。
2. **角标按字节判定**（改了又改回来不算改）：
   - 忍具「名字」页 = `textChanged(names, id)`（文本 vs `original_text`）；
   - 忍具「未解字节」页 = `recordChanged(pack, records, record)`（记录字节 vs 原版）；
   - 忍具「掉落位置」页 = `pack.changedStructureRecords(reward_table)` 的 `rom_offset`
     集合 ∩ 引用这个忍具的那些奖励行 → 有几条相关奖励行被改过；
   - 奖励的三个数字页 + 掉落位页 = **新增的 `fieldChanged()`**：
     拿 `pack.recordBytes()` 重编码后的字节和 `record.raw` 比，
     **只看这个字段占的那几个字节**（金币 = offset 0..1，掉落位每个槽各 1 字节）。
     这一条是页签粒度必须的：`changedStructureRecords` 只能判到整条记录。
3. **懒渲染会改既有断言的位置**。页签内容按需渲染 ⇒ 切走的那一页**不在 DOM 里**。
   既有断言里「详情里有 X」的几条改成「先切到那一页，再看 DOM」，
   断的还是同一件事（8 个掉落位、可改的下拉、跳转链接、归属脚注），
   断言条数与口径没有放松。
4. **奖励表的数字字段不是写死的**：`rewardNumberFields(rewards)` 从内容包取
   （金币 / 强化点 / 等级门槛三个 u16），页签 id 用字段 key（英文），
   标签用字段 label（中文）。内容包里两个保留字节（u8）本来就没渲染，不受影响。
5. **改完类别要把掉落位那一页整个重画**（物品下拉的候选换了）；
   其余字段改完只 `tabs.refresh()`（角标跟上）—— 与 `battle-map.js` 的做法一致。

## 复核出来的关键事实

- `item_record` 94 条 × 16 字节（16 个 `hex` 字段，语义仍未证明）；
  `reward_table` 112 条 × 24 字节（3 个 u16 + 8 个掉落位 ×2 字节 + 2 个保留字节）。
- 奖励行的 `rom_offset` = `0x59FFE0 + id × 24`（`0x59FFE0` = 5892832）。
  忍具记录 `rom_offset` = `0x545C14`（5528548）。
- `rewardRowsForItem()` 认「物品 id = 0 表示列表结束」，所以「掉落位置」页里
  不会出现占位忍具。

## 验收

```
node rom-editor/tools/verify_syntax.mjs     # exit 0（55 个文件全过）
node rom-editor/tools/verify_views.mjs      # exit 0
node rom-editor/tools/verify_item_view.mjs  # exit 0（含新增的第 10、11 组）
node rom-editor/tools/verify_labels.mjs     # exit 0
```

新增断言（`verify_item_view.mjs`）：

- 第 10 组：两个视图的右侧都有页签条；页签标签是预期的那几个；
  切到某一页后那一页的内容在 DOM 里、切走后不在；DOM 里永远只有一个内容区（懒渲染）。
- 第 11 组：角标 —— 没改过没有角标；改了金币只有「金币」那一页亮角标，
  没动过的「强化点」「掉落位」不亮。
- 第 12 组：改掉落位的类别 → 那一页里的物品下拉换成新类别那张名字表
  （实测 94 个忍具名 → 18 个强化素材名）—— 证明「改完类别要重画那一页」
  在页签里也成立。

## 没做的事 / 留给别人的

- 没有改任何 CSS：新增的 `detail-head-area` / `detail-tab-area` / `detail-foot-area`
  是三个普通 `div`（没有对应样式，靠 `.detail-head` / `.detail-sub` / `.tab-*`
  现有样式生效）。
- 没有改 `tabs.js` / `common.js` / `fields.js` / `pack.js`。
- `docs/sequel-roadmap.md` 本轮第九轮的汇总段由主代理统一写（本文件不碰共享文件）。
