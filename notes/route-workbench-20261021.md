# 剧情路线域：一屏一关的「路线工作台」（2026-10-21）

> 依据：`notes/specs/route-workbench.md`（主代理定稿的规格）。
> 本文只讲**落地结果与实测事实**，设计说明在规格里。

## 落地了什么

`rom-editor/js/modules/route.js` 重写成「路线工作台」：一屏只做一关，三块内容。

| 块 | 内容 | 能改什么 |
|---|---|---|
| ① 路线走向 | 本关出边表 / 谁会跳到本关表 / 「下一场景 id」「相位标志」下拉 / 全游戏 63 条边的折叠一览 | 下一场景、相位标志（`pack.setScriptOperand`） |
| ② 任务文案 | 3 个子任务 × 标题 / 说明 / 提示，单行输入框 | 任务文本（`pack.setText`） |
| ③ 本关奖励 | 3 个子奖励：金币 / 强化点 / 等级门槛 + 8 个掉落位（`slots.js::renderArrayTable`） | 奖励字段与掉落位（`pack.setValue`） |

新增 `rom-editor/js/modules/route-graph.js`（`#route/graph` 整条路线总览 + 路线边的公共件）
与 `rom-editor/css/route.css`（本域样式，index.html 已引用）。
`common.js` 出了 `openInTable` / `openInModule` 两个公共件，`battle.js` 改用前者。

## 实测事实（内容包实测，不是推的）

- 路线边一共 **63 条**：`0x16` 48 条、`0x1A` 15 条。
  出边按 `pack.scripts[].scene === 关卡` 过滤，入边按 `edge.scene === 关卡` 过滤。
- `0x16` 的 48 条里 **47 条目标是 0**（1 条目标是 1）。仓库只证明了它会切到 after 表
  并把场景号写进 `state[0x1A]`，**没有**证明 0 等于「留在本关」——界面按这个口径写文案。
- `story_after_root` 的指针非空的是场景 **1..55**（槽 0 为空），所以「下一场景 id」
  的下拉就是 `0 · 场景 0` + 55 个 `N · 第 N 关 · after 剧本`。
- `mission_index`：第 40 关 = 103、41 = 104、42 = 105 …（**不是** 3×(关卡−1)）。
  于是槽 105 同时属于「第 40 关子 2 / 第 41 关子 1 / 第 42 关子 0」，
  这就是行脚注里「同时是第 41 关子 1」的来源（`xref.js::missionIndexOwners`）。
- 三张任务文本表各有**一个** 27 条的「同一段字节」共用组（`record.shared_with`），
  槽 103/104/105 **不在**里面。所以：
  - 第 40 关看不到「这段字被 N 处共用」；
  - 第 1 关（槽 1 落在共用组里）会看到「这段字被 27 处共用，改一处会一起变」。
  - 共用组与「跨关共用同一格」是两件事，界面分别用
    「这段字被 N 处共用」/「这格被 N 处共用（这几关共用同一格）」区分。

## 踩到的坑（都已在代码里处理）

1. `pack.setScriptOperand` **只写补丁表**：它既不更新 `operand.value`，也不进撤销栈。
   - 不更新 `operand.value` → 重画之后下拉还显示旧值。`route.js` 在写回后同步了
     `operand.value`。
   - 不进撤销栈 → 作者按 Ctrl+Z 撤不掉。`route.js` 自己补了一条撤销记录
     （`commitOperand`），撤销时既恢复操作数，也把补丁的 `after_hex` 恢复回去，
     否则 ROM 里还是新值、改动计数也不回落。
   - 更干净的做法是在 `pack.js` 里给 `setScriptOperand` 补 undo 记录 —— **待主代理处理**。
2. 键盘监听不能无条件 `stopPropagation`：app.js 的 Ctrl+Z 是挂在 `document` 上的
   冒泡监听，拦掉就撤销不了。`route.js` 只对**自己处理**的键（] [ → ← 1 2 3 g Esc）
   调 `stopPropagation`。
3. 无头自检的 DOM 桩没有 `focus()` / `removeEventListener()`，调用前都要判存在。

## 怎么验证的

```
node rom-editor/tools/verify_syntax.mjs        # 语法门禁
node rom-editor/tools/verify_views.mjs         # 旧断言不许坏
node rom-editor/tools/verify_route_workbench.mjs   # 新设计的 6 条验收（本次新增）
python -m unittest discover -s tests            # 84 项
```

`verify_route_workbench.mjs` 是本次新增的验收探针：对着规格 §6 逐条核对
（路线边按关卡过滤 / 下一场景是下拉 / 任务文案只改本槽 / 奖励与道具域同一份数据 /
跨关共用显式告知 / 键盘与撤销），另加域首页、整条路线总览与 1·2·3、Esc 的按键检查。
它自带一个极小的 DOM 桩，不依赖浏览器。

## 还缺的（要主代理配合）

- `pack.js::setScriptOperand` 补撤销记录 + 给补丁一个像样的 label（规格 §5 已列）。
- `fields.js` 的 `relationOptions` 在 `by_category` 下是按渲染当时的类别算的：
  改完类别物品下拉要重画。现在是 `route.js` 整体重画奖励区来兜底
  （`fieldCtx.onCommit` 里发现 `_category` 结尾就重画），
  通用编辑器那边还是老样子。
