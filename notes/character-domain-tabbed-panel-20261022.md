# 角色域右侧面板页签化 — 2026-10-22

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮 · 页签化）。
> 参考实现：`rom-editor/js/modules/battle-map.js`（战场地图那 5 个页签）。
> 通用机制：`rom-editor/js/tabs.js` 的 `TabPanel`。

## 做了什么

改了两个文件：

- `rom-editor/js/modules/character.js`
- `rom-editor/tools/verify_character_view.mjs`

角色视图（`#characters/character`）的右侧面板从「一串纵向追加」改成**页签**：

| 原来纵向堆叠的段落 | 现在的页签 | 每一页装什么 |
|---|---|---|
| `detail-head`（角色名）/ `detail-sub`（角色定义表 #N / 已改 N 处）/ 跳转条 | **留在页签外面** | 装在 `.detail-top` 容器里（不被 `clear` 波及） |
| `renderAttributes` | 属性 | 角色定义表头 12 字节 + 记录末尾未解字节 |
| `renderGrowth` | 成长 | 逐角色成长表同号那条 |
| `renderPerks` | 特性 | 本角色用到的每个技能的参数表 |
| `renderSlots('jutsu')` | 忍术槽 | 15 槽表 |
| `renderSlots('training')` | 技能槽 | 24 槽表 |
| `renderSlots('items')` | 道具槽 | 9 槽表 |
| `renderPortrait`（含 `renderPieces`） | 头像 | 表情槽 + 全角色共用的拼块表 |

页签 id 英文 / label 中文，`key: 'editor.character'`。
页签面板**只装一次**，换角色只 `refresh()` —— 页签选择与记住的页签都还在。

## 关键决定与踩过的坑

1. **`clear(host)` 会把页签面板一起清掉** ⇒ 页签面板挂在**不被 clear 的容器**里
   （`.detail-top` / `.detail-tabs` 两层）。
2. **角标要按字段细分，不能只按记录判**：
   属性 / 忍术槽 / 技能槽 / 道具槽 **都在角色定义表的同一条记录里**（`rom_offset` 相同）——
   纯 `rom_offset` 比对会让四个页签**同时亮**。
   所以在记录级判定之上再按字段细分（`originalValue` 读记录原始字节）。
3. **角标按字节判定**（改了又改回来不算改）；改回原值角标会灭。
4. **改完一格不重建页签内容**（输入框不丢焦点）—— 角标靠内容包的变更通知自动跟上。

## 复核出来的事实

- 角色定义表 63 条；逐角色成长表 63 条（与角色定义表同号）；
  角色特性表 45 条（**技能 id 空间**，不是角色 id 空间）；
  头像指针表 64 条；头像拼块表 6 条（**全体角色共用**）。
- 拼块表一改全体生效 ⇒ 它的角标按**记录数**计，与其它页签单位一致，
  但语义上它不属于「这个角色」。

## 验收

```
node rom-editor/tools/verify_syntax.mjs          # exit 0
node rom-editor/tools/verify_views.mjs           # exit 0
node rom-editor/tools/verify_character_view.mjs  # exit 0（含新增的第 6 组 24 条）
node rom-editor/tools/verify_labels.mjs          # exit 0
```

新增断言（`verify_character_view.mjs` 第 6 组）：页签条存在 · 标签恰为预期七个（顺序也比）·
页签正文只有一个 · 「角色定义表 #N」与跳转条留在页签外 · 默认停在属性页 ·
切到成长/特性后该页内容在 DOM 里 · 切走后上一页不在 DOM 里 · 切回来内容又回来 ·
改属性只有「属性」页亮角标（其余六页不亮）· 头部「已改 N 处」跟上 ·
改完一格**不重建页签内容**（输入框不丢焦点）· 改回原值角标与计数都回落。

## 没做的事 / 留给别人的

- 新引入两个无样式容器类 `.detail-top` / `.detail-tabs`（不得改 CSS）。
  视觉上与原来一致，但没有留给以后调样式的钩子。
- 只在无头桩 DOM 里验过，**没有在真实浏览器里目视确认**页签条样式与滚动表现。
