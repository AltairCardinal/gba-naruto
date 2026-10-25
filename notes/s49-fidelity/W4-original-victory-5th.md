# 流 W4 —— 原版 S49 battle-14 胜利屏 + 结算屏真值（**第五次尝试，打成**）

> 工具：`tools/s49_victory_capture/`（本流独占）
> 产物：`build/s49-victory-capture/w4/`
> 2026-10-24 · stream W4（wave 8）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；重制线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**打成了。** 原版 ROM（`rom/base.gba`，sha256 `1198ece7…`）的 **S49 battle-14 被本流打赢**：
战斗结果字节 `0x02026807` 由 `0` 变为 `1`，**「勝利」屏、结算屏（经验值/战力/回合数）、
四人升级屏、忍具一览、战后对白、任务菜单地图** 全部逐帧录到，
**两次独立跑 32,596 帧 + 29,700 帧全部逐字节一致**（`identical: true`）。
**没有伪造任何帧。**

---

## 1. 这一轮为什么终于打通：方法换成了三层

前四轮（K → M → W3 → X3）死在同一件事上：**驱动器得靠像素猜「我现在在哪个画面」**，
猜错一次就丢状态机。这一轮把这件事从根上换掉了：

| 层 | 前四轮 | W4（第五次） |
|---|---|---|
| **战斗起点** | 从 battle-14 入口重打全场 | ⭐ **复用逆向线自己的存档点** `scenario-49-battle-14-turn4-two-kills.ss9`（同一个 base ROM，sha256 `e8b2a5ee…`）——它证明**这场仗在原版上能打赢**，所以问题从「能不能赢」变成「赢的时候屏幕上是什么」 |
| **状态读取** | 像素阈值 + 一个 1 字节的 level 寄存器 | ⭐ **把原版单位记录解出来了**（一次 4212 B 的 pool dump + 离线解析）：`+0x00` 角色 ID（**0 = 已被击倒**）、`+0x01` 忍具、**`+0x07` 当前查克拉**、`+0x0C` HP、**`+0x0E` 最大 HP**、`+0xC7/+0xC8` 实时坐标 |
| **胜利判定** | 看画面像不像胜利 | ⭐ **`0x02026807` = 战斗结果字节**（0 未结算 / 1 胜利 / 2 护送失败；逆向线 `analyze_battle_objective_transitions.py` 已证）——**读寄存器，不认像素** |
| **录制** | 跨命令读画面 | ⭐ **Lua 帧回调在模拟器进程内逐帧截图**，画面与状态严格同帧 |

⭐ **推论（本流最重要的一条）**：**HP 数组不是「是否存活」的判据。**
被打倒的敌人**保留最后一个 HP**（实测 slot 8 = 9、slot 9 = 25，角色 ID 都是 0），
而且 **HP 数组比攻击动画晚几百帧才更新**（实测命中后 240 帧才变）。
W3 用「HP > 0」判存活、被「数组滞后」骗过，两条都是错的。

---

## 2. 改动文件清单（全部是本流独占目录 / 本流新建）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_victory_capture\w4_play.py` | **新增** | **本流的战斗驱动器**（闭环，状态解码 + 像素只用来认消息框）+ 胜利后逐帧录制 |
| `D:\Github\gba-naruto\tools\s49_victory_capture\capture_victory_frames.lua` | **新增** | Lua 帧回调：在模拟器进程内逐帧截图（帧号 = 真实帧号） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\w4_capture.py` | **新增** | 帧精确采集驱动器（Lua + 收据 + 每帧 sha256 清单） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\w4_drive.py` | **新增** | **逐步路线驱动器**：每按一次键就采样一次状态 + 存一张 PNG（开环、可视化核对），本流用它反推了全部交互规则 |
| `D:\Github\gba-naruto\tools\s49_victory_capture\w4_verify.py` | **新增** | **两次独立跑逐字节一致**的验证器（帧级 sha256 比对 + 收据） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\w4_sheet.py` | **新增** | 联络表（把上千帧压成一页看） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\probe_checkpoint.py` | **新增** | 存档点检查器（加载 + 截图 + 状态采样） |
| `D:\Github\gba-naruto\tools\s49_victory_capture\screen_fingerprint.py` | **新增** | 屏幕指纹工具（用逆向线的**带标注存档点语料**离线找判别字段，见 §6 的失败记录） |
| `D:\Github\gba-naruto\notes\s49-fidelity\W4-original-victory-5th.md` | **新增** | 本文件 |
| `D:\Github\gba-naruto\build\s49-victory-capture\w4\**` | 临时产物 | 帧、收据、联络表、调试截图 |

**没有**改重制线任何文件、逆向线任何文件、其它流的任何工具
（`s49_pairing` / `s49_blackfade` / `s49_overlay_align` / `s49_fidelity_report*` /
`s49_save_boundary` / `s49_audio_l` / `s49_idle_*.py` / `s49_orig_map` / `s49_starfield` 一律未动）。

---

## 3. 跑了哪些验证

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `python tools/s49_victory_capture/w4_play.py --out build/s49-victory-capture/w4/victoryA --max-turns 24 --endgame-frames 1800` | **`{"turns": 7, "actions": 7, "hits": 5, "victory": true}`**；录到 **32,596 帧** |
| **V2** | 同上 → `victoryB`（完全独立的第二次跑） | 同上 stats；**32,596 帧** |
| **V3** | `python tools/s49_victory_capture/w4_verify.py --a .../victoryA --b .../victoryB --out .../verify-victoryAB.json` | `frames_a=32596 frames_b=32596 only_in_a=[] only_in_b=[] differing_count=0` ⇒ **`identical: true`** |
| **V4** | `python tools/s49_victory_capture/w4_play.py --out .../settlementA --endgame-frames 300 --record-victory-only --endgame-presses 30 --endgame-settle 240` | `victory: true`；录到 **29,700 帧**（胜利屏 → 结算屏 → 升级屏 → 忍具表 → 战后对白 → 任务菜单） |
| **V5** | 同上 → `settlementB` | 同上 stats；**29,700 帧** |
| **V6** | `python tools/s49_victory_capture/w4_verify.py --a .../settlementA --b .../settlementB --out .../verify-settlementAB.json` | `frames_a=29700 frames_b=29700 differing_count=0` ⇒ **`identical: true`** |
| **V7** | `python tools/s49_victory_capture/probe_checkpoint.py --state <turn4 ss9>` | turn4 存档点状态（§4.1） |
| **V8** | 一次 `framedump 1 0x02024294 4212` + 离线解析 | **单位记录全表**（§4.2），9 槽 × 0x1D4 B |
| **V9** | `python tools/s49_victory_capture/screen_fingerprint.py` | 14 个带标注存档点 × 256 KB EWRAM：260,600 个「组内恒定」偏移、24,207 个候选判别偏移、但**没有一个能直接当状态机用**（见 §6） |
| **V10** | `python tools/s49_victory_capture/w4_drive.py --keys "..."`（逐步路线） | 开环复现了鸣人「移動 → 十字手里剑 → 命中 → 25→8」的全过程 |
| **V11** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | **0 个孤儿进程** |
| **V12** | 新文件的 BOM/CRLF 扫描 | 6 个新文件全部 **bom=False, crlf_pairs=0**（纯 LF） |
| **V13** | `git status --porcelain` | 本流新文件**未提交**（工作区里是 `??` 未跟踪状态） |

⭐ **两次独立跑逐字节一致的结论**：**V3 与 V6 都是 `identical: true`**，
差异帧数 **0 / 32596** 与 **0 / 29700**。

---

## 4. 结算屏真值清单（本次拿到的真值）

### 4.1 战斗起点存档点（`scenario-49-battle-14-turn4-two-kills.ss9`，sha256 `e8b2a5ee…`）

| 槽 | 角色 | HP | 查克拉 | 角色 ID(+0x00) | 坐标 |
|---:|---|---:|---:|---:|---|
| 1 | 漩涡鸣人 | 99/138 | 5/5 | 1 | (9,6) |
| 2 | 宁智波佐助 | 104/104 | **0/4** | 2 | (7,10) |
| 3 | 春野樱 | 110/110 | 3/3 | 3 | (8,11) |
| 4 | 木叶丸（护送） | 28/40 | 2/2 | 30 | (12,3) |
| 5 | 蜜蜂 | 25/25 | 0 | 55 | (9,5) |
| 6 | 蜜蜂 | 25/25 | 0 | 55 | (8,5) |
| 7 | 蜜蜂 | 12/25 | 0 | 55 | (8,7) |
| 8 | 蜜蜂（**已倒**） | (9) | 0 | **0** | (10,6) |
| 9 | 蜜蜂（**已倒**） | (25) | 0 | **0** | (7,12) |

⇒ 存档点名字里的「two kills」是字面意义的：**slot 8 / slot 9 已经被击倒，但它们的 HP 还留着**。

### 4.2 原版单位记录布局（V8 实测，9 槽逐槽对齐）

| 偏移 | 语义 | 证据 |
|---|---|---|
| `+0x00` | **角色 ID；0 = 该槽已被击倒 / 清空** | 存活 4 人 + 3 蜂 = 7 个非 0；已倒的 slot 8/9 为 0 |
| `+0x01` | 忍具（工具）数 | 鸣人 5 / 佐助 4 / 小樱 5 / 木叶丸 3 / 蜂 5（W3 表格吻合） |
| `+0x07` | **当前查克拉** | 鸣人 5 / 佐助 **0** / 小樱 3 / 木叶丸 2（与 HUD 的 `5/5`、`0/4` 完全一致） |
| `+0x08` | 最大查克拉 | 鸣人 5 / 佐助 4 / 小樱 3 / 木叶丸 2 |
| `+0x0C` | **当前 HP** | 99 / 104 / 110 / 28 / 25 / 25 / 12（与 HUD 一致） |
| `+0x0E` | **最大 HP** | 138 / 104 / 110 / 40 / 25 / 25 / **25**（蜂 3 的 HP 是 12 但上限仍是 25 ⇒ 蜂 3 被打过 13 点） |
| `+0xC1` | 「在单位列表里」标志 | 敌方已倒的槽也带这个位 ⇒ **不能当存活判据** |
| `+0xC7/+0xC8` | **实时坐标** | 移动只改这两字节（W3 已证） |
| `+0xCC` | 阵营（0 我方 / 1 敌方） | — |
| `+0xCD` | 每单位行动状态 | 蜂全为 4（AI 配置行号），**不携带存活信息** |

### 4.3 本流打出来的战斗过程（`play.json` 摘要）

| 阶段 | 事实 |
|---|---|
| 鸣人 | 十字手里剑命中 (9,5) 的蜂：预测 **27 伤害 / 84% 命中**，实际 **25 → 8**（实伤 17）；十字手里剑**用过即从列表消失**（条目数 4 → 3，`menu_cursor` 顶到 2） |
| 佐助 | **查克拉 0**，火遁术不可用；「休息」**不回查克拉**（实测：休息后仍是 0）⇒ 本局只能靠体术 |
| 佐助/鸣人 | 忍者组合拳命中蜂：10 伤害、距离 1、消耗体力 0、成功率 98% |
| 小樱 | 移动被拒（「請在移動範圍內選擇」）：**游标过不了河**（battle-14 的 y=10 整行是河，(8,10) 不可走，(8,11)→(8,8) 只能绕经 (7,10)，而那里站着佐助） |
| 结果 | 7 回合 / 7 次行动 / 5 次命中 → `0x02026807` = **1** |

### 4.4 胜利/结算屏真值清单（PNG + sha256）

产物目录：`build/s49-victory-capture/w4/settlement-truth/`（机读收据 `settlement-truth.json`）。
**帧号是相对「胜利判定那一刻」的**（录制器在结果字节变 1 时启动），`frame-00001` = 「勝利」屏第一帧。

| 文件 | 内容 | sha256 |
|---|---|---|
| `01-victory.png` | **「勝利」屏**（大字胜 + 角色 + 石头） | `d60a1d35e45736dbad3a9d9e7f4fb633d55854dd5b7650c1162702793c3128ea` |
| `02-settlement-exp-power-turns.png` | **结算屏**：经验值 / 战力 / 回合数（166·166·125，300·350·200，胜/负） | `e34e116c7ed3a55e6fc470e9c9a18b6e803e2451818a173d3124d1d15c38d550` |
| `03-levelup-naruto.png` | 鸣人升级（「按鳴人的LV升到6級了」：体力 +14、攻击力 +1、防御力 +1、敏捷度 +1） | `a876f32dbe100a65d96e4769820f31ef1f2701583064e66c6b4bd7692a3d0078` |
| `04-levelup-konohamaru.png` | 木叶丸（护送）升级屏 | `ef0808aea763ff319445a9701b485b89b8646838e15dd33a921f60acf7b9dfaf` |
| `05-levelup-sasuke.png` | 佐助升级屏 | `c5a8440b451ef6a121a1b45f2fb0baf55ef56f7d2ceec811e6f3c8db8d8f3402` |
| `06-levelup-sakura.png` | 小樱升级屏 | `a0db87e9fd8ec358e713e7930ef716509b0cdfaa13f777e6ed546eaa404f7b3a` |
| `07-ninja-tool-list.png` | 忍具一览（十字手里剑 / 改变卷轴 / 兵粮丸 / 苦无 …） | `455acc43c9ace5531e6b4bc6fb3529e314b9cb523d63b48ecf39f5fc5974214c` |
| `08-postbattle-dialogue-1.png` | 战后对白第 1 页 | `2741dbc3fbf6e8389c93bdaa7b8ab32cfae8c9aca1b32b123569dd5efdb96e58` |
| `09-task-menu-map.png` | 战后回到「术之里」任务菜单（地图上 53 个红叉） | `cda07a18be60a1eab971df0d051b5a9efaa719e5c17889eec495c32a38d974a5` |

⭐ **结算链的顺序（本次实测）**：
`「勝利」屏 →（按 A）→ 结算屏（经验值/战力/回合数）→（按 A）→ 四人升级屏 →（按 A）→ 忍具一览 →（按 A）→ 战后对白 → 任务菜单`。
⭐ **「勝利」屏不会自己推进**：实测连录 **18,000 帧**（= 9,000 真实帧）都停在「勝利」上，
**必须按 A** 才进结算屏 —— 这是 W3/X3 没测到的最后一块。

---

## 5. 本流查清的「原版战斗 UI 规则」（前四轮没查清或查错的）

| # | 规则 | 证据 |
|---|---|---|
| W4-R1 | **被打倒的敌人保留最后一个 HP**；存活判据是 `unit+0x00 != 0` | 瞄准 (10,6)（slot 8）被游戏拒（「請把對方設置在範圍內」），而 slot 8 的 HP 数组还是 9 |
| W4-R2 | **HP 数组比攻击动画滞后**：命中后 240 帧才更新 | 命中帧 HUD 已显示 8/25，数组仍写 25 |
| W4-R3 | **行动菜单（5 项）不使用忍术列表的游标寄存器**；高亮在**多次打开之间保留** | 高亮在「移動」时 `0x0200A8BA` 仍读 1 ⇒ 计数式走位会走错项 |
| W4-R4 | **行动菜单条目用「Up × 条目数」定位**：按满一整圈必定落在第 1 项 | 包裹/不包裹都成立；本流驱动器据此稳定选中 移動/术·忍具/休息/行動結束 |
| W4-R5 | **游标过不了不可走格**（battle-14 的 y=10 是整行河）；越界时游戏答「請在移動範圍內選擇」 | 试图让小樱 (8,11)→(8,8) 被拒；(8,10) 值 = 1（river） |
| W4-R6 | **瞄准模式的游标只能沿弹道走** | 让它走到不在同排/同列的格 ⇒ `aim-unreachable` |
| W4-R7 | **忍术列表的说明框压在错误框区域**（列表本身 `error_light=5676`）⇒ 分类器必须**先认列表再认错误框** | 实测列表签名 `panel=4874 / dark=723 / err=5956`；W3 的分类顺序在这里会误判成错误框 |
| W4-R8 | **休息不回查克拉**（而且休息 = 本单位行动结束） | 佐助休息后查克拉仍为 0 |
| W4-R9 | 查克拉/体力/攻击力的**数值**与信息板一致：十字手里剑 距离 3 直 / 范围 1，火遁术 15×1 / 距离 2 直 / 消耗查克拉 2 / 95%，忍者组合拳 10×1 / 距离 1 / 消耗体力 0 / 98% | 直接读原版自己的信息板 |
| W4-R10 | **「勝利」屏等待 A 键** | 18,000 帧不变 |
| W4-R11 | **战斗结果字节** `0x02026807`：0 未结算 / 1 胜利 / 2 护送失败 | 逆向线 `tools/analyze_battle_objective_transitions.py`（已证）；本流用它判胜利 |
| W4-R12 | **原版单位记录布局**见 §4.2 | 一次 4212 B dump 离线解析 |

---

## 6. 卡在哪（以及为什么这一轮通了）

**这一轮真正的卡点不是「打不过」，而是「认不出画面 / 读不到状态」**。
四轮尝试的具体卡点与本轮的解法：

| 卡点 | 现象 | 本轮解法 |
|---|---|---|
| **非法落点** | 移动被拒（「請在移動範圍內選擇」），且**同一处连试 4 轮** | ⭐ 读出单位记录 + 用 M 的 147 格可走图做 **BFS 路径**；游标逐格复读；失败格记入 `blocked_cells` 不再重试 |
| **慢一帧** | W3 以为「每条命令前进一帧」 | W3 自己已证伪（W3-E1）。本轮**根本不用跨命令判画面**：Lua 帧回调同帧写 PNG |
| **目标界面分叉** | 佐助火遁术是另一个界面（等级 3 + 大信息板 + 自己的确认框），W3 卡死 | 本轮**根本不用火遁术**（佐助查克拉 0，休息也不回），全部走「忍者组合拳」 |
| **分不清「忍术列表」和「错误框」** | 列表说明框压在错误区域 ⇒ 列表被认成错误框，驱动器每次都以为失败了 | ⭐ 重新排序分类器：**先按 `panel>3000 && dark>=500` 认列表**，再认错误框；并补上「列表动画要等 40 帧再走游标」 |
| **行动菜单走错项** | 寄存器不跟随 ⇒ 一直选错条目 | ⭐ 「Up × 条目数」定位 + 结果校验（打开后核对目标画面） |
| **小樱走不到位** | 河挡路 + 佐助堵住唯一通路 | 记录成「该格不可达」，跳过该候选 |
| **胜利屏不推进** | 录了 18,000 帧还在「勝利」上 | ⭐ 胜利后**按 A**（30 次 × 240 帧）⇒ 结算屏/升级屏/忍具表/对白/任务菜单全部录到 |
| **（走了两条死路，已记账）** | ① 用逆向线的**带标注存档点语料**离线找「屏幕判别字段」：14 个画面 × 256 KB EWRAM，24,207 个候选偏移，**没有一个能当状态机用**（真状态是 ROM 里的 dispatcher，不在 EWRAM 里）；② 试过从 `postbattle-task-menu` 存档点倒推结算屏 —— 结算屏在它**之前**，回不去 | 两条路都写进台账（§7），不再走 |

⭐ **一句话**：
**「不要问『现在在哪个画面』，去问『原版自己怎么记这件事』」** ——
单位记录里有角色 ID / 查克拉 / HP / 坐标，战斗控制区里有结果字节；
有了它们，屏幕分类就只剩「三个消息框」这种小问题。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W4-H1 | 逆向线在同一 base ROM 上打赢过 battle-14 ⇒ 胜利屏在原版上可达 | 查 `D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints\`，找到 `scenario-49-battle-14-{entry,turn4-two-kills,postbattle-task-menu}.ss9` | 三个存档点都在，sha256 与逆向线笔记吻合 | **已确认** |
| W4-H2 | turn4 存档点里还剩几只蜂 | 离线解析单位记录 | **剩 3 只**（slot 5/6/7）；slot 8/9 角色 ID = 0 ⇒ 已倒，但 HP 仍留着 9 / 25 | **已确认** |
| W4-H3 | HP 数组 = 存活判据 | 瞄准 (10,6) 看游戏答不答 | 游戏答「請把對方設置在範圍內」⇒ 已倒 ⇒ **HP 数组不能判存活** | **已证伪** |
| W4-H4 | HP 数组实时更新 | 命中后连采 240 帧 | 命中帧 HUD 已 8/25，数组仍 25 ⇒ **滞后数百帧** | **已证伪** |
| W4-H5 | `0x02026807` 是战斗结果字节 | 读逆向线 `analyze_battle_objective_transitions.py` + 本流实战 | 0/1/2 = 未结算/胜利/护送失败；打赢时读到 1 | **已确认** |
| W4-H6 | 忍术列表与错误框可用像素分开 | 读列表自己的签名 | 列表 `err=5956`（说明框压在错误区）⇒ **必须先认列表** | **已证伪**（顺序错就崩） |
| W4-H7 | 行动菜单高亮可用 `0x0200A8BA` 定位 | 高亮在「移動」时读寄存器 | 读 1（≠ 0）⇒ **不可用** | **已证伪** |
| W4-H8 | 「Up × 条目数」能定位行动菜单第 1 项 | 包裹/不包裹两种情形都成立 | 稳定 | **已确认** |
| W4-H9 | 游标能直线穿过不可走格 | 让它从 (8,11) 走到 (8,8) | 河在 (8,10) ⇒ 卡住 ⇒ **必须绕路** | **已证伪** |
| W4-H10 | 休息能回查克拉 | 休息一次后读 `+0x07` | 仍是 0 | **已证伪** |
| W4-H11 | 查到「画面判别字段」就能替代像素分类 | 14 个带标注存档点 × 256 KB EWRAM 离线扫 | 24,207 个候选，**没有一个可用** ⇒ 真状态在 ROM dispatcher 里 | **已证伪**（这条路走不通） |
| W4-H12 | 从 postbattle 存档点能倒推结算屏 | 存档点语义 | 结算屏在它**之前** ⇒ 回不去 | **已证伪**（这条路走不通） |
| W4-H13 | 「勝利」屏自己会推进 | 连录 9,000 真实帧 | 全停在「勝利」⇒ **必须按 A** | **已证伪** |
| W4-H14 | 跨命令像素判定会慢一帧（W3 的老结论） | W3-E1 已证伪；本轮用 Lua 同帧回调 | 同帧 | **已确认**（沿用 W3 结论） |
| W4-H15 | 原版 battle-14 可以打到胜利结算屏 | 本流驱动器跑完整场仗 | **达成**：7 回合 / 5 次命中 / 结果字节 = 1，结算链全程录到 | **已确认** |

---

## 8. 复现命令清单

```powershell
# 0) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe，会 LNK1104）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w4'
python tools/mgba_probe/build.py

# 1) 打赢并全程逐帧录制（胜利屏 + 结算屏 + 升级屏 + 忍具表 + 对白 + 任务菜单）
python tools/s49_victory_capture/w4_play.py `
    --out build/s49-victory-capture/w4/settlementA `
    --max-turns 24 --endgame-frames 300 --record-victory-only `
    --endgame-presses 30 --endgame-settle 240

# 2) 第二次独立跑 + 逐字节一致
python tools/s49_victory_capture/w4_play.py `
    --out build/s49-victory-capture/w4/settlementB `
    --max-turns 24 --endgame-frames 300 --record-victory-only `
    --endgame-presses 30 --endgame-settle 240
python tools/s49_victory_capture/w4_verify.py `
    --a build/s49-victory-capture/w4/settlementA `
    --b build/s49-victory-capture/w4/settlementB `
    --out build/s49-victory-capture/w4/verify-settlementAB.json

# 3) 全程录（含战斗帧）的两次跑 + 逐字节一致
python tools/s49_victory_capture/w4_play.py --out build/s49-victory-capture/w4/victoryA --max-turns 24 --endgame-frames 1800
python tools/s49_victory_capture/w4_play.py --out build/s49-victory-capture/w4/victoryB --max-turns 24 --endgame-frames 1800
python tools/s49_victory_capture/w4_verify.py `
    --a build/s49-victory-capture/w4/victoryA --b build/s49-victory-capture/w4/victoryB `
    --out build/s49-victory-capture/w4/verify-victoryAB.json

# 4) 结算屏真值清单（PNG + sha256 收据）
python build/s49-victory-capture/w4/extract_truth.py

# 5) 联络表（看相位用）
python tools/s49_victory_capture/w4_sheet.py `
    --frames build/s49-victory-capture/w4/settlementA/frames `
    --out build/s49-victory-capture/w4/settlementA/sheet2.png --columns 7 --every 600 --count 49
```

---

## 9. 确认

* **新文件全部 LF、无 BOM**（6 个新文件扫描：`bom=False, crlf_pairs=0`）。
* **未提交 git**（本流文件在工作区里是未跟踪状态；`git status` 里其它 `M` 项是别的流的改动，本流没碰）。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用存档点与 ROM）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的工具**。
* **没有伪造任何帧**：所有 PNG 都来自探针内 Lua 帧回调的逐帧截图，两次独立跑逐字节一致。
* **孤儿进程检查通过**：`mgba-probe.exe` 残留 0 个。
* **路线图同步留给父代理**：`docs/sequel-roadmap.md` 当前已被别的流改动（工作区里是 `M`），
  本流**不碰**它（WAVE8-TASKS §5 规定由父代理串行接线与同步）。本流的进度记在本文件里。
