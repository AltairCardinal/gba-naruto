# 剧情与对白域右侧面板页签化（场景 / 字库）— 2026-10-22

> 规格：`notes/specs/tabbed-side-panels.md`（第九轮 · 页签化）。
> 参考实现：`rom-editor/js/modules/battle-map.js`（战场地图那 5 个页签）。
> 通用机制：`rom-editor/js/tabs.js` 的 `TabPanel`。

## 做了什么

改了两个文件：

- `rom-editor/js/modules/scene.js`
- `rom-editor/tools/verify_scene_view.mjs`

两个视图的右侧面板都从「一串纵向追加」改成**页签**（头部仍在页签外面）：

| 视图 | 原来纵向堆叠的段落 | 现在的页签 | 每一页装什么 |
|---|---|---|---|
| 场景 `#story/scene`（key `editor.story.scene`） | `detail-head`（场景 N）/ `detail-sub`（槽号 / N 张根表 / 已改 N 处）/ 四张 `.scene-ptr` 卡（战前 / 战后 / 逻辑 / 事件，每卡 = 标签 + 指针十六进制框 + 提示 + 跨表链接 +「看…的剧本 →」） | 战前 · 战后 · 逻辑 · 事件 | 每页恰好装一路的指针卡 |
| 字库 `#story/font`（key `editor.story.font`） | `detail-head`（第 N 段）/ `detail-sub`（起始码 / N 字 / 字形位置）/「这一段的字段」+ `font-seg-fields` /「字宽表」+ `font-lookup` 查表条 + 256 行字宽表 | 字形段 · 字宽 | 字形段页 = 该段字段；字宽页 = 查表条 + 256 行字宽表 |

页签 id 英文 / label 中文。

## 关键决定与踩过的坑

1. **`clear(host)` 会把页签面板一起清掉** ⇒ 页签面板挂在**不被 clear 的容器**里
   （`.scene-detail-head` / `.font-detail-head` 只装头部，页签元素只挂一次）。
   `renderDetail()` 只重建头部 + `tabs.refresh()`。
2. **`renderLookup()` 改成返回节点**（不再写 `this.lookupWrap`）——
   查表条随页签懒渲染。
3. **角标按字节判定**：
   - 场景域 = 该路**当前这一场**的指针改没改（`pack.changedStructureRecords(table)`
     的 `rom_offset` 集合）；
   - 字库 = 字形段看当前段记录，字宽看字宽表里改过的行数。
4. **四张根表是同一个场景的四个剧本入口** —— 分成四页而不是一页四张卡，
   是因为每张卡自己就是一整件事（指针 + 跨表链接 + 看剧本）。

## 复核出来的事实

- 场景根表四张：`story_before_root` / `story_after_root` / `story_logic_root` /
  `story_events_root`，各 55 条，**按场景（关卡）索引**。
- 字形段表 31 段；字宽表 256 行（按字符码索引）。

## 验收

```
node rom-editor/tools/verify_syntax.mjs       # exit 0
node rom-editor/tools/verify_views.mjs        # exit 0
node rom-editor/tools/verify_scene_view.mjs   # exit 0（含新增的第 8 组 25 条）
node rom-editor/tools/verify_labels.mjs       # exit 0
```

既有断言是**改写不是削弱**：原「详情里有 4 个指针」变成逐页断言（每页恰好 1 个 +
四页合起来 4 个 + 4 个都是十六进制框）；原「至少 1 条剧本链接」变成
**四页各一条且分别跳到 before / after / logic / events**（比原来更强）。

## 没做的事 / 留给别人的

- **没在真实浏览器里目视确认**（新增两个包裹 div 把头部从页签里挪出来；
  逐条查过 `styles.css` 与 `css/scene.css`，没有 `>` 子代选择器会被这层包裹破坏，
  但没法真机确认间距）。
- **页签条会随面板一起滚走**（与战斗地图域行为一致）。要吸顶必须改 CSS。
- 角标语义两处不完全对称：场景域角标限定在「当前这一场」的一条记录（0/1），
  字库的字宽角标是整张表改过的行数。
- 字库「内容包里没有字形段表」的空态从详情顶部挪进了「字形段」页签内；
  真实内容包有 31 段，该分支不会走到。
