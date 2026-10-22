# 道具域统一编辑视图（忍具 / 奖励）— 2026-10-22

## 做了什么

按用户反馈（「光一个任务表就分了索引、标题、说明、提示表来呈现，过于细碎繁琐，
应当按统一的任务编辑来呈现，然后按索引表列出，将其他表的内容都作为字段呈现。
其他模块也要做同样思路的修改」），把道具域从「四张表各摆一行」改成两个统一视图：

- `rom-editor/js/modules/item.js`（新建）
  - `renderItem`：忍具视图。左边 = 道具/忍具记录表 `item_record` 的每一行；
    右边 = 名字（忍具名表）+ 它自己的 16 个未解字节 + 它在哪几关掉落。
  - `renderReward`：奖励视图。左边 = 奖励表 `reward_table` 的每一行；
    右边 = 金币 / 强化点 / 等级门槛 + 8 个掉落位（类别 + 物品），脚注写明归属。
- `rom-editor/js/modules/items.js`：域首页加 `groups`（忍具 / 奖励各一个入口），
  强化素材名表保持独立行；`kind === 'item' / 'reward'` 分发到新视图。
- `rom-editor/css/item.css`（新建）：`.item-block` / `.item-note` / `.item-numbers` 等。
- `rom-editor/js/routing.js`：`SUBVIEW_LABELS` 加 `item: '忍具'`、`reward: '奖励'`。
- `rom-editor/tools/verify_item_view.mjs`（新建）：自带 DOM 桩的无头验收脚本。

## 复核出来的关键事实（都从内容包取，没有写死在代码里）

- `item_record` 94 条 × 16 字节，`raw_only`，16 个字段全是 `hex`（未解字节）。
  **字段语义仍未证明**，所以列表上只显示名字与「未解字节」状态，不编字段名。
- `ninjutsu_names` 94 条，与 `item_record` 同一个 id 空间
  （`item_record.id_relation → ninjutsu_names`，反向用 `idspace.js::idSpace`）。
  名表 note 写明「0 = 占位，1..93 = 名称」。
- `reward_table` 112 条 × 24 字节：金币 / 强化点 / 等级门槛（3 个 u16）+ 8 个掉落位
  （类别 u8 + 物品 u8）+ 2 个保留字节。
- 掉落位的 `relation.categories` 给出类别 → 名字表的对应
  （0 忍具 / 1 强化素材 / 2 认识卡 / 3 技术），由 ROM 自带的 4 槽指针表 0x0859F5E0 证明。
- **掉落位的物品 id 写成 0 表示这一串掉落位到此结束**（内容包写在字段 desc 里：
  「该类别的名称表下标；0 = 列表结束」）。已核实：896 个槽位里 570 个物品 id 是 0，
  且每个奖励行里 0 之后全是 0。
  - 不认这条规则，占位忍具（id 0）会显示「掉了 568 次」—— 那是假的。
  - 认了这条规则，**真正被掉落的忍具只有 8 个**：
    id 1 / 17 / 18 / 31 / 37 / 40 / 67 / 73。
- 奖励 → 哪几关：`xref.js::missionIndexOwners(pack)` 给
  `Map<奖励下标, [{stage, sub}]>`。下标不是 `3×(关卡−1)`：
  下标 0 被第 0 / 1 / 47 关共用，**112 行里有 18 行被好几关共用**。
  子编号是 0 基的（`ownerLabel` 写「第 40 关子 0」）。

## 踩过的坑

1. **hash 往返会冲掉面板参数**。`app.js::openPanel` 先 `render()`（参数还在），
   随后 `hashchange` 事件触发 `parseHash()` 重建 `state.view`，而
   `#items/reward` 这种 SUBVIEW_LABELS 形式的 hash 记不下第几条 → 落点跳回默认那条。
   解决办法：模块级记住上一次看的条目（`lastItemId` / `lastRewardId`），
   `pickId` 的优先级是「面板参数 → 上一次看的 → 默认」。
2. **写回只用 pack.setValue / pack.setText**。16 个未解字节用**一个** hex 编辑区，
   提交时按字节拆开逐个 `setValue`（未变的字节 `setValue` 会早退，不产生 undo 条目）。
3. 页面文本里不能出现字面 `**`；说明文字用 `section-note` / `stat-hint` 这类
   prose 容器（`ui.js::el` 会自动去掉星号），但新写的文案一律不用星号。

## 验收

```
node rom-editor/tools/verify_item_view.mjs   # 9 组断言全过
node rom-editor/tools/verify_syntax.mjs       # 全过
node rom-editor/tools/verify_views.mjs        # 全过
node rom-editor/tools/verify_sources.mjs      # 全过
node rom-editor/tools/verify_labels.mjs       # 全过
python -m unittest discover -s tests           # 84 tests OK
```

## 待主代理配合

- `rom-editor/index.html` 加一行 `<link rel="stylesheet" href="css/item.css">`
  （index.html 不在本任务的可改范围里）。
