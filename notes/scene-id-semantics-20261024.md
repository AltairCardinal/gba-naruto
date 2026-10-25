# 场景号语义：游戏开局为什么被列成「第 54 场」（2026-10-24）

**用户反馈**：「在 HTML ROM 编辑器的对白查看器里，原本是游戏开局的剧情却被列到第 54 场，
检查一下为什么会这样并修复相关问题。」

**结论（一句话）**：**场景号不是「第几场」** —— 它是 ROM 里的**键**（剧情调度器的入参、
四张剧本根表的下标），数值大小**不代表剧情顺序**。游戏开局在 ROM 里的场景号是 **54**
（主线入口），而旧界面把槽号写成「第 N 场」，于是它看起来像最后一场，占位场景 55
还排在它前面。

---

## 1. 证据链：为什么开局是 54

### 1.1 场景号是什么

| 项 | 值 | 出处 |
|---|---|---|
| 场景号的来源 | `ldrb r0, [r4, #0x16]`（`0x0808F8DC`），`r4` = 剧情 flag 块 `0x020311D4` | `notes/evidence/l4-playthrough-20261021.md` §1.1 |
| 调度器 | `0x0808F544(scene)`：按 `state[0x18]` 选 `before_root[scene]` 或 `after_root[scene]` | 同上 §5.2 |
| 四张根表 | before `0x060C74` / after `0x060D54` / logic `0x060E34` / events `0x060EF0`（各 56/56/47/47 槽，**槽号 = 场景号**） | 同上 §1.1；`notes/completion-audit-20261020.md` |
| **键对不对** | L4 逐场留证 **55/55**：游戏实际用的脚本指针与 `before_root[scene]` **逐位相等** | 同上 §4.1 |

⇒ 场景号确实是根表下标，**不是**一个「顺序」。

### 1.2 开机走的就是 54

| 证据 | 内容 |
|---|---|
| mGBA 真机 | `START → A×4` 后画面上是伊鲁卡的对白「“是啊，是我这个班主任所承认的嘛！”」——与 `decode_story_script.py --scene 54` 的第 5 句**一字不差** |
| 断点采样 | 剧情调度器 `0x0808F544` 命中时 **r0 = 0x36 = 54**；VM 入口 `0x080977B8` 收到 **r0 = 0x08049E76** = `before_root[54]` |
| 画面比对 | `notes/evidence/story-scene-l3.png` 与编辑器渲出的场景 54 第 5 句逐像素相同（背景 3840/3840、立绘 6400/6400、名牌 384/384、正文 2304/2304 全等） |

（`notes/mgba-probe-runtime-20261020.md` §6.1–6.2、`notes/evidence/l2-runtime-evidence-20261021.md`）

### 1.3 场景 54 是什么：一个按剧情进度分支的**主线入口**

场景 54 的脚本开头是 **5 条 `0x15`（比较器条件跳转）**：

| 指令地址 | 比较器 | 值 | 目标 |
|---|---|---|---|
| `0x08049E76` | `==` | 270 | `0x0804B957` |
| `0x08049E7E` | `>=` | 229 | `0x0804B957` |
| `0x08049E86` | `>=` | 80 | `0x0804B5B5` |
| `0x08049E8E` | `>=` | 69 | `0x0804AFA7` |
| `0x08049E96` | `>=` | 27 | `0x0804A96A` |
| `0x08049E9E`（落空） | —— | —— | **开局的过场**（鸣人毕业 / 一乐拉面） |

比较的值是**剧情进度** `state[0x10]`（`0x020311E4`）。
⇒ 开机时进度为 0 ⇒ 全部不命中 ⇒ 落到开局的过场。
⇒ 场景 54 不只是「开局一场」，它是**主线入口 / 进度总线**。

### 1.4 场景号空间的全貌（本轮逐条解码得到）

| 场景号 | 类别 | 依据 |
|---|---|---|
| 0 | 空槽 | 四张根表的 0 号都没有指针 |
| **1..46** | **关卡场景** | 场景号 = 关卡号 = **战斗组号**（`notes/evidence/l4-playthrough-20261021.md` §5.1：编成矩阵 `组*0x1AAC + 子*0x8E4`） |
| 47 | 短对白 | 战前「走吧！ＭＡＰ０１的家伙。」/ 战后「成功啦～！」 |
| 48 / 49 | 占位 | 正文「无法进入此处」 |
| 50 | 主线分支总线 | 开头 13 条 `0x15`（进度 ==360/261/260、>=250/240/230/110/100/90/89/70/45/0）—— **绝大多数关卡剧情演完都汇到这一场** |
| 51 | 进度分支 | 开头 5 条 `0x15`（进度 >=225/172/169/159/150） |
| 52 | 章节场景 | 「这就是考场吗……」 |
| 53 | 章节过场 | `0x1E` 进战斗 + 「终于到了！！」 |
| **54** | **主线入口（游戏开局）** | 见 §1.2 / §1.3 |
| 55 | 占位 | 正文「此处无法进入。」 |

**游戏实际的场景转移**（`notes/evidence/l4-playthrough-20261021.md` §4.2）：
「绝大多数场景汇到 **50**，50 → **54** → 50 → **9**（章节收尾再续下一章）」——
所以 54 既在开局，也在主线的中途出现；它是一个**入口**，不是「第 54 关」。

---

## 2. 旧界面错在哪

| 位置 | 旧写法 | 问题 |
|---|---|---|
| `js/modules/dialogueview.js` | 场景下拉 `第 ${s} 场`；标题 `对白 · 第 ${scene} 场` | 把**槽号**说成**第几场** ⇒ 开局（54）排在列表末尾，占位（55）还在它前面 |
| `js/modules/scriptview.js` | 同上，且下拉**从 0 开始** | 还把四张根表都没指针的 **0 号空槽**列成了「第 0 场」 |
| `js/modules/route-graph.js` | `战前剧情（第 ${scene} 关）` / `第 ${scene} 关 · after 剧本` | 关卡只有 46 个，「第 50 关 / 第 54 关」**根本不存在** |
| `js/modules/route.js` | 下一场景 id 下拉 `${n} · 第 ${n} 关 · after 剧本` | 同上 |
| `js/xref.js` | `${root} 第 ${scene} 场` | 同上 |
| `js/modules/battle-sections.js` | 面包屑 `（第 ${scene} 场）` | 同上 |

**还有一个真 bug**：路线边里**确实有指向 50 / 51 的边**（内容包 `pack.scripts[].route` 里 63 条边，
目标是 0/1/2/5/24/31/40..45/50/51），而「目标」列点下去走的是
`ctx.openPanel('stage','stage',{stage})` —— **关卡工作台只有 1..46**。
点「场景 50」会落在一张**不存在的第 50 关**的页面上。

---

## 3. 改了什么

### 3.1 新增单一真源：`rom-editor/js/sceneid.js`

把「场景号是什么」收成一处，界面各处都从这里取说法：

| 导出 | 干什么 |
|---|---|
| `LEVEL_SCENE_MIN/MAX` | 1 / 46 —— 关卡场景的范围 |
| `ENTRY_SCENE` | 54 —— 主线入口（游戏开局） |
| `PLACEHOLDER_SCENE` | 55 —— 占位 |
| `sceneKind/sceneTag/sceneHint/sceneLabel/sceneName` | 这一场**是什么** |
| `sceneGroups()` | 下拉分组：主线入口 → 关卡场景 → 其他特殊场景（组内仍按场景号升序） |
| `sceneNumbers(structure)` | 一张根表里可用的场景号（从 1 开始，0 号是空槽） |
| `SCENE_ID_NOTE` | 界面上那句「场景号不是第几场」的说明 |

标签口径：

| 场景 | 标签 |
|---|---|
| 1..46 | `场景 12（第 12 关）` |
| 47 | `场景 47 · 短对白` |
| 48 / 49 / 55 | `场景 55 · 占位` |
| 50 | `场景 50 · 主线分支` |
| 51 | `场景 51 · 进度分支` |
| 52 | `场景 52 · 章节场景` |
| 53 | `场景 53 · 章节过场` |
| **54** | **`场景 54 · 主线入口（游戏开局）`** |

### 3.2 界面改动

| 文件 | 改动 |
|---|---|
| `js/modules/dialogueview.js` | 场景下拉改成分组（`<optgroup>`）并用新标签；标题 `对白 · 场景 54 · 主线入口（游戏开局）`；页面加一段「这一场是什么 + 场景号怎么读」；**不给场景号时默认落在主线入口（54）** |
| `js/modules/scriptview.js` | 同一套标签与分组；**不再列 0 号空槽**；默认也落在 54 |
| `js/modules/scene.js` | 场景列表与详情用 `sceneLabel()`；说明里加 `SCENE_ID_NOTE` |
| `js/modules/route-graph.js` | `scriptLabel/targetText` 用场景口径；**关卡之外的场景（>46）点「目标」跳剧情域的对白编辑器**，不再跳不存在的「第 N 关」 |
| `js/modules/route.js` | 「下一场景 id」下拉用场景口径（`场景 54 · 主线入口（游戏开局） · after 剧本`） |
| `js/xref.js` | 反查里的剧本名用场景口径 |
| `js/modules/battle-sections.js` | 面包屑用场景口径 |
| `js/routing.js` | 深链接默认场景从 1 改成 `ENTRY_SCENE`（`#story/dialogue/before` → 54；`hashFor` 同步） |
| `js/modules/story.js` | 域首页点明「打开时落在场景 54（主线入口）——那才是游戏开局的那一场」 |

### 3.3 顺带补上的健壮性

切剧本类型时**当前场景可能不在那张根表里**（例如从「战前剧情」切到「战场事件逻辑」，
而当前是场景 54 —— 那张根表只有 46 个槽）。旧代码这种情况下下拉会显示第一项（场景 1），
与页面正在显示的那一场对不上。现在 `sceneOptionGroups()` 会**补出当前场景那一项**。

---

## 4. 验收

`rom-editor/tools/verify_dialogue_view.mjs` 新增**第 11 组**（10 条断言）：
下拉里有 `场景 54 · 主线入口（游戏开局）` / 下拉分组且主线入口在最前 /
下拉里不再有「第 N 场」/ 关卡场景仍带关卡名 / 占位场景说得出自己是什么 /
页面解释了「场景号不是第几场」/ 页面点明游戏开局是场景 54 /
**不给场景号时默认落在主线入口** / 剧本查看器不再列 0 号空槽 / 剧本查看器默认也落在主线入口。

`rom-editor/tools/verify_route_workbench.mjs` 新增**第 9 组**（6 条断言）：
内容包里有指向 >46 的路线边 / 总览不把关卡之外的场景说成「第 N 关」 /
写得出「场景 50 · 主线分支」 / 「场景 50」可点 / **点它跳到剧情域的对白编辑器**。

两条门禁的旧断言按新口径更新（`第一行是「场景 1（第 1 关）」`、
`选项文案同时含场景号与关卡名` 的正则），并给 `verify_route_workbench.mjs` 的 ctx 补上 `onJump`。

其它门禁全过：`verify_syntax`（81 个文件）/ `verify_dialogue_view`（66 条）/
`verify_scene_view` / `verify_views` / `verify_cards` / `verify_route_workbench` /
`verify_battle_map` / `verify_battle_story_triggers`（82 条）/ `verify_pack` /
`verify_script_text` / `verify_variable_text` / `verify_script_relocation` /
`verify_font_map` / `verify_wording` / `verify_labels` / `verify_sources`；
`python -m unittest discover -s tests` **93 项通过**。

### 4.1 真浏览器复核（DOM 桩断不到的那一段）

无头门禁用的是 DOM 桩，断的是结构与文案；`<select><optgroup>` 在**真浏览器里**
长什么样、下拉框当前显示的是哪一项，桩断不了。

新增 **`rom-editor/tools/qa-scene-select.html`**（与 `qa-trigger-view.html` 同一路数）：

```powershell
node rom-editor\tools\serve.mjs 8000
# 打开 http://localhost:8000/rom-editor/tools/qa-scene-select.html
```

实测（2026-10-24，内置浏览器）：**8 项全过** ——

```
[PASS] 场景下拉分成组 — 主线入口（游戏从这里开始） / 关卡场景（第 1..46 关） / 其他特殊场景
[PASS] 主线入口组里就是场景 54 — 场景 54 · 主线入口（游戏开局）
[PASS] 下拉当前选中的是场景 54（不是第一项） — value = 54
[PASS] 下拉里没有「第 N 场」 — 没有
[PASS] 关卡场景仍带关卡名 — 场景 1（第 1 关）
[PASS] 标题写的是「场景 54 · 主线入口（游戏开局）」
[PASS] 切到没有这一槽的根表时，下拉仍选中场景 54 — value = 54
```

页面会把结果 POST 到 `/__report`（与 `selftest.html` 同一套），跑过什么留在
`build/selftest-report.jsonl`（`page: qa-scene-select`）。

> **取数上的两个坑**（都是这一轮踩到的，记下来）：
> ① **编辑器自己的取数路径是能通的**：`载入内置 ROM` 走
>    `content/base-rom/rom-loader.html` 那个**独立文档**取 `base-rom.bin.gz`（2.7 MB），
>    实测在嵌入式浏览器里**成功**（6,291,456 字节，2026-10-24）。
>    反而是「同一个文档里直接 fetch 6 MB 的 `rom/base.gba`」会卡住 ——
>    嵌入式浏览器对**单文档**的下载量有上限。
>    所以 QA 页默认**不取 ROM**（标签口径的断言不需要它），要整幅画面就加 `?rom=1`；
>    门禁页要 ROM 时走编辑器同款路径（`js/romsource.js::loadBundledRom`）。
> ② `serve.mjs` 每个请求都 `console.log` 一行 —— 用 `Start-Process` 起而不重定向
>    stdout 时，**日志管道写满会把 node 的 event loop 堵死**（服务器看着像死了）。
>    起服务器要重定向：`-RedirectStandardOutput build\serve.log`。

---

## 5. 复现命令

```powershell
# 场景 54 就是开局：第 5 句 = 伊鲁卡「是啊，是我这个班主任所承认的嘛！」
python tools\decode_story_script.py --scene 54

# 场景 54 的开头是 5 条按剧情进度分支的 0x15（进度 < 27 → 开局过场）
node tools\probe_scene_branches.mjs 54
node tools\probe_scene_branches.mjs 50      # 主线分支总线（13 条 0x15）

# 门禁
node rom-editor\tools\verify_dialogue_view.mjs
node rom-editor\tools\verify_route_workbench.mjs

# 真浏览器复核
node rom-editor\tools\serve.mjs 8000
# 打开 http://localhost:8000/rom-editor/tools/qa-scene-select.html
```

---

## 6. 遗留 / 没做

- **剧情顺序表**：界面能说清「场景号 ≠ 第几场」，但**没有一份权威的剧情先后表**
  （1..46 的关卡顺序已知，47..55 在主线里的确切位置只证明到 §1.4 的转移图）。
  所以下拉按**类别**分组，不按剧情顺序重排 —— 免得排出一个 ROM 里并不存在的顺序。
- **场景 50 / 51 的分支目标**（进度 → 具体分支）没有做成界面上的可读表；
  现在只在说明里给出「开头 N 条 `0x15`」这一层。
- 场景 47/48/49 的底图按 `0x0808F4D4` 的规则会读到越界的垃圾条目 —— **旧问题，本轮没碰**。
