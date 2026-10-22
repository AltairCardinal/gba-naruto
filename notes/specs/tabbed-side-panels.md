# 规格：右侧面板页签化（第九轮）

> 起因（用户原话）：
> 「战斗的编辑要将所有同一战斗的关联内容串联起来，以战斗地图的编辑为主界面，
> 右侧战场布置面板中用其他页签分类提供其他战斗相关配置的编辑，
> 例如胜利失败条件、相关剧情触发等等。**其他模块也一样，全部检查一遍**。」
>
> 规格：`notes/specs/battle-map-editor.md`（第八轮，地图本身）
> 本文只讲**页签化**这一件事的设计与落地口径。

## 0. 为什么要页签

一个域的相关配置往往有好几类。战斗里就有：战场布置 / 战场物件 / 角色出生点 /
胜负条件 / 剧情触发。角色里有：属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 头像。
把它们全堆在右侧面板里，右侧就变成一条**看不到头的长滚动** ——
作者要改「胜负条件」得先滚过「战场布置」和「战场物件」。

页签把同一件事的各个侧面按类分开：一次只看一类，改完一类切到下一类。

**统一的心智模型**：

```
┌──────────────────────────────┬───────────────────────┐
│  主界面（能看见东西的那个）    │  右侧：页签            │
│  地图 / 角色卡 / 任务 / 场景   │  [页签1][页签2][页签3] │
│                              │  ─────────────────    │
│                              │  当前页签的内容         │
└──────────────────────────────┴───────────────────────┘
```

## 1. 通用机制（已经做好，各域直接用）

`rom-editor/js/tabs.js` 导出 `TabPanel`：

```js
import { TabPanel } from '../tabs.js';

this.tabs = new TabPanel([
  {
    id: 'attributes',
    label: '属性',
    hint: '六项基础属性与体力',      // 悬停提示，可选
    badge: () => '2',                // 角标（「这一类改了几处」），可选
    render: () => this.renderAttributes(),
  },
  {
    id: 'growth',
    label: '成长',
    render: () => this.renderGrowth(),
  },
], { key: 'editor.character' });

host.appendChild(this.tabs.element);
```

### 契约

| 事项 | 规定 |
|---|---|
| **懒渲染** | 只有当前页签会调 `render()`。切走的那一页**不在 DOM 里**（别在 `render()` 里缓存节点） |
| **记住当前页签** | 按 `key` 记在 `localStorage`（前缀 `editor.tabs.`），下次进来还在这一页 |
| **角标** | `badge: () => 'N'`，返回 `null` / `undefined` / `''` 就不显示。**按字节判定**（改过又改回去不算改） |
| **刷新** | 改完数据后调 `this.tabs.refresh()` —— 它会重建当前页签的内容与角标 |
| **换页签** | `this.tabs.setActive('growth')` |
| **换视图** | 视图整体重建时（换关卡 / 换角色）**不要**重建 TabPanel，保留 `this.tabs`，只调 `refresh()`，这样页签选择与记住的页签都还在 |
| **页签 id** | 同一组里唯一，**用英文**（`attributes` / `growth` / `rules`），label 用中文 |
| **key** | 按域分开：`editor.<域>.<视图>`，例如 `editor.character` / `editor.reward` / `editor.story.scene` |

### 实现要点

1. 原来 `renderDetail()` 里是**一串** `host.appendChild(this.renderXxx())`。
   改成：**头部留在页签外面**（`detail-head` / `detail-sub` / 跳转条），
   **内容进页签**。

   ```js
   renderDetail() {
     const host = this.detailWrap;
     clear(host);
     host.appendChild(el('div', { class: 'detail-head' }, [...]));   // 留在外面
     host.appendChild(el('div', { class: 'detail-sub' }, [...]));    // 留在外面
     if (!this.tabs) {
       this.tabs = new TabPanel([...], { key: 'editor.character' });
       host.appendChild(this.tabs.element);
     } else {
       host.appendChild(this.tabs.element);
     }
     this.tabs.refresh();
   }
   ```

   ⚠️ `clear(host)` 会把 `this.tabs.element` 一起清掉，所以要**先 `clear` 再 append**，
   或者把 TabPanel 放在一个**不被 clear 的容器**里。推荐后者：
   `this.detailWrap` 只装一次页签面板，内容交给 `tabs.refresh()` 管。

2. 每个 `renderXxx()` 改成**返回一个节点**（而不是往 host 上 append）：

   ```js
   renderAttributes() {
     return el('div', { class: 'section' }, [ ... ]);
   }
   ```

3. 角标的计数要用**字节判定**，与通用表格编辑器同一套：
   - 结构表：`pack.changedStructureRecords(structure)` → 记录 `rom_offset` 集合
   - 文本表：`pack.changedTextRecords(table)` → 记录 `id` 集合
   - 剧情脚本操作数：`operandChanged(operand)`（`common.js` 已导出）

4. **不要**改这些：
   - 域首页（`renderDomainIndex` 的参数）—— 除非本域的「推荐入口」确实要跟着换
   - 通用表格编辑器（`editors.js`）、通用文本表编辑器
   - `common.js` 除非确实要加公共函数（加了要在自己的报告里写清楚）
   - 写回通路 —— 一律走 `pack.setValue` / `pack.setText` / `pack.setScriptOperand`

5. **页面文本里不许出现字面 `**`**（编辑器不渲染 markdown，星号会原样露出来）。
   说明性文字写在 `class` 含 `section-note` / `stat-hint` / `rule-note` / `field-hint` / `entry-card`
   的容器里，`ui.js` 会自动去掉星号；但**新写的标题类文本不要自己加星号**。

## 2. 各域要页签化什么

> 下表是**建议**，实际以代码里现在渲染了哪些段落为准 ——
> **把原来纵向堆叠的段落按类分到页签**，不要凭空加内容，也不要删内容。

| 域 | 视图 | 主界面 | 右侧页签（按现有内容归类） |
|---|---|---|---|
| 战斗 | 战场地图 `#battle/map/…` | **战场地图** | 战场布置 / 战场物件 / 角色出生点 / 胜负条件 / 剧情触发（**已做**） |
| 角色 | `#characters/character` | 角色卡 | 属性 / 成长 / 特性 / 忍术槽 / 技能槽 / 道具槽 / 头像 |
| 道具 | `#items/item` | 忍具表 | 名字 / 掉落位置 / 其它字段 |
| 道具 | `#items/reward` | 奖励表 | 金币 / 强化点 / 等级门槛 / 掉落位 |
| 剧情路线 | `#route/stage/…` | 路线工作台 | 任务文案 / 本关奖励 / 路线走向 / 剧本操作数 |
| 剧情与对白 | `#story/scene` | 场景表 | 战前 / 战后 / 逻辑 / 事件 四个剧本入口 |
| 剧情与对白 | `#story/font` | 字库 | 字形段 / 字宽 |
| 音频 | `#audio/…` | 音效工作台 | 描述符 / 谁指向它 / 播放入口 / ID 表 |
| 素材与资源 | `#assets/wiring` | 接线总表 | 接线 / 资源记录 / EWRAM 内存 |
| 剧情与对白 | 对白表（通用编辑器） | 对白表 | 字段 / 来源（`editors.js` 通用，两域共用） |
| 忍术 | `#ninjutsu/…` | 忍术表 | 记录参数 / 名字（表少，可以不拆） |

**原则**：页签是**分类**，不是**搬家**。同一类的东西放一页；页签数控制在 **2–7** 之间 ——
超过 7 个说明切得太碎，读者要来回翻；少于 2 个说明这一页没必要拆。

## 3. 验收

每个域改完至少要跑：

```powershell
node rom-editor\tools\verify_syntax.mjs        # 语法门禁
node rom-editor\tools\verify_views.mjs         # 无头视图自检
node rom-editor\tools\verify_labels.mjs        # 标签自检
```

**新增一条自己的断言**（在对应的 `verify_*.mjs` 里，或新开一个 `verify_tabs.mjs`）：
右侧面���**确实有页签条**，页签标签是预期的那些，**切到某一页后那一页的内容在 DOM 里**、
**切走后不在**。

改动不能降低既有门禁的通过率 —— 有失败要先修好再交。

## 4. 交付

每个域的改动要交：

1. 代码（**只动自己那一个模块文件**；需要动 `common.js` 的先在报告里说明）
2. 自己那个域的验收断言
3. 一段说明：**原来有哪些段落 → 现在分成哪几个页签 → 每一页装什么**
