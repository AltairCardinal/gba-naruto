# 流 W3 —— 原版真值补齐：结算屏 + 黑场过渡

> 工具：`tools/s49_blackfade/`（新）、`tools/s49_victory_capture/`（M 流续做）
> 产物：`build/s49-blackfade/`、`build/s49-victory-capture/`
> 2026-10-24 · stream W3（wave 4）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**；重制线**零改动**。

---

## 0. 一句话结论

**任务 B（黑场）：判定 = 产品差，但 P 流的前提错了。**
原版 battle-14 的**开场演出**里有 **2 次黑场**，两次都是**渐变**（淡出 24 帧 → 全黑 18/24 帧 → 淡入 24 帧）；
重制侧在**同样的两个相位**也有黑场，但都是**硬切**（1 帧进、4 个 GBA 帧黑、1 帧出，**没有渐变**）
⇒ **缺的是淡入淡出渐变本身，这是玩家看得见的画面 ⇒ 产品差**。
（P 流的 P4「重制侧没有黑帧」被**证伪**：重制侧有 4 处黑场，P 的 walk 每 90 帧才采一帧，
黑场只有 4 个 GBA 帧，被采样漏掉了。）

**任务 A（结算屏）：**没打成（**不伪造任何帧**）—— 第 1 回合鸣人走完
「移動 → 十字手里剑 → 命中」并造成 **18 点真伤害**（蜜蜂 8 号 `25 → 7`）；
最远进度与三条卡点见 **§5**，结算屏清单见 **§7**。

---

## 1. 先修仪器：M 流的「每条命令前进一帧」是**错的**（W3-E1）

M 流的卡点诊断是「探针的每条命令都会让被模拟的游戏前进一帧 ⇒ 跨命令判定读到上一帧」。
本流用一条受控实验直接测了这件事（`tools/s49_victory_capture/exp_frame_advance.py`）：

| 步骤 | 命令 | 帧是否前进 |
|---|---|---|
| r1 | `frames 1 0` → `rawshot r1` | —（基准） |
| r2 | `rawshot r2`（与 r1 之间无命令） | **否**（r1 == r2） |
| r3 | `dump 0x02026A8C 1` → `rawshot r3` | **否**（r2 == r3） |
| r4 | `frames 1 0` → `rawshot r4` | **是**（r1 != r4） |
| r5 | `shot s1.png` → `rawshot r5` | **否**（r4 == r5） |

⇒ **只有 `frames` / `run` / `framedump` / `keyseq` 前进帧；`dump` / `shot` / `rawshot` 不前进。**
⇒ 「读寄存器 → 再截图」得到的是**同一帧**，画面**永远不会过期**。
⇒ M 流真正坏掉的是**菜单分类器**，不是时序（M15 判定：**已证伪**）。

**新仪器的帧对齐写法**（本流全部改用它）：
`frames 1 0` 前进一帧 → `rawshot` 落盘（核心的视频缓冲，240×160 RGBA，无损、比 mGBA 的 PNG writer 快）
→ 同一帧里再 `dump` 状态寄存器 ⇒ **画面与状态严格同帧**。

### 1.1 操作坑（本流踩到，别人也会踩）

1. **杀掉 Python 客户端不会杀掉探针子进程**：`mgba-probe.exe` 会变成孤儿并**继续 100% 吃 CPU**。
   本流结束时清掉了 5 个孤儿（约 6000 s CPU），机器才空出来。
   ⇒ 跑完/取消之后要 `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` 查一遍。
2. **驱动器退出码的含义**：`play_battle_v3.py` 打出胜利返回 **0**，没打赢返回 **1**（不是崩溃）。
   调试时只看退出码会把「没打赢」误判成「跑挂了」。
3. **逐帧日志要边跑边写**：驱动器把每条决策实时写进 `progress.jsonl`
   （`play.json` 只在跑完时写），否则卡死时什么都看不到。

---

## 2. 原版 battle-14 的战斗 UI 像素真值（本流实测）

`tools/s49_victory_capture/calibrate_menus.py` 把原版走到每一个界面状态并记录像素签名：

| 画面 | level | border 行(x=8) | 菜单暗像素 | 右信息板亮像素 | 底部对话框亮像素 | 错误框 | 确认框 | 青可达集 | 橙路径预览 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **行动菜单（5 项）** | 3 | **94** | 631 | 0 | 74 | 371 | 0 | 0 | 0 |
| **紧凑菜单（2 项，移动后）** | 3 | **42 / 46** | 304 | 0 | 0 | 138 | 0 | 0 | 76 |
| **忍术列表** | 4 | 8 | 953 | **5170** | 3476 | 5676 | 1211 | 0 | 0 |
| 移动阶段（可达集） | 3 | 0..2 | 0 | 0 | 0 | 0 | 0 | **5231..6665** | 0..1585 |
| 瞄准模式（射程预览） | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | **2171..10269** |
| 伤害预测（底部框） | 4 | 2 | 0 | 246 | **2207** | 0 | 0 | 0 | — |
| 「可以嗎?」确认框 | 4 | 2 | 0 | 246 | 2207 | **2145** | **2283** | 0 | — |
| 错误框（请把对方设置在范围） | 4 | 2 | 0 | 126 | 0 | 1358 | 68 | 0 | — |
| 单元选择相位（无菜单） | 3 | 2 | 0 | 0 | 0 | 0 | 0 | **0** | 0 |

**关键分辨器（都是本流新加的）**：

* **青可达集**（`r<=140, g>=230, b>=180`）：移动阶段 5231..6665 px，其它画面 **0**
  ⇒ 用来把「移动阶段」和「单元选择相位」分开（M 流的驱动器没有这个区分，
  所以它在单元选择相位里狂按 B 死循环）。
* **橙路径预览**（`r>=240, 120<=g<=175, b<=50`）：瞄准模式 2171..10269 px，其余 0..556
  ⇒ 用来认「瞄准模式」。
* **底部对话框区域必须避开 HUD 条**：原版的 HUD 状态条固定占 **y=135..152**，
  故事对话框从 **y=103** 开始 ⇒ 对话框区域取 **y=100..134** 才能与 HUD 分开。

---

## 3. 黑场真值表（任务 B）

### 3.1 采集方法

`tools/s49_blackfade/blackfade_capture.py` 用 **Lua 帧回调**（在模拟器进程内跑）
逐帧 `emu:screenshot`，所以每一帧都有**真实帧号**；随后
`tools/s49_blackfade/blackfade_report.py` 做亮度剖面并把黑场切成
**淡出 / 全黑 / 淡入** 三段。

### 3.2 原版（`rom/base.gba`，sha256 `1198ece7…`，从 battle-14 入口存档起，1881 帧）

| # | 黑场 | 帧号 | 淡出 | 全黑 | 淡入 | 总帧 | 不同帧数 | 相位 |
|---|---|---|---|---|---|---:|---:|---|
| 1 | `frame-01013.png … frame-01078.png` | 1013–1078 | **24**（1013–1036） | **18**（1037–1054） | **24**（1055–1078） | 66 | **25** | 「開始」标题 → **战前对白**（黑帧里有一颗**黄色四角星闪光**） |
| 2 | `frame-01653.png … frame-01724.png` | 1653–1724 | **24**（1653–1676） | **24**（1677–1700） | **24**（1701–1724） | 72 | **25** | 最后一句战前对白 → **「回合 1 玩家」** |

* 全黑帧 sha256（两侧、所有黑场都一样）：
  `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`
* 事件 1 前一帧 `frame-01012.png` sha256 `a1fac2a9ebd212edd1af126217763055302114869df10cabca636fc463cd8a1d`
  均值 (47.667, 53.681, 20.923)；后一帧 `frame-01079.png` sha256
  `331e0fb05c6646b908a9c6ad51eb7733a945a31a3460cdc3bcfbcd515f3afacd` 均值 (43.943, 50.461, 29.240)。
* 事件 2 前一帧 `frame-01652.png` sha256 `0e611d6eba7fa5927b05b96efefab391ca56b1347e232efed834e4b273a6309d`
  均值 (42.127, 46.915, 30.158)；后一帧 `frame-01725.png` sha256
  `82068f15c8b6a751db07bd4b5c36958c7556d6de482b7ad5b3c43c02dc95d975` 均值 (47.687, 53.696, 20.933)。

⇒ **是渐变，不是纯黑一帧**：66/72 帧里只有 25 张不同的图，
**12 级淡出 + 9/12 级全黑 + 12 级淡入**，每级**保持 2 个 GBA 帧**（原版把每帧画两遍）。

### 3.3 重制侧（`butano-sequel.gba`，sha256 `804dd793…`，上电起步，2402 帧）

| # | 黑场 | 帧号 | 淡出 | 全黑 | 淡入 | 总帧 | 不同帧数 | 相位 |
|---|---|---|---|---|---|---:|---:|---|
| 1 | `frame-00027.png … frame-00034.png` | 27–34 | **0** | 8 | **0** | 8 | **1** | 上电 → 标题（开机淡入） |
| 2 | `frame-00527.png … frame-00532.png` | 527–532 | **0** | 6 | **0** | 6 | **1** | 准备场景 → 战斗 |
| 3 | `frame-01479.png … frame-01486.png` | 1479–1486 | **0** | 8 | **0** | 8 | **1** | 敌方部署 → **战前对白**（= 原版事件 1 的相位） |
| 4 | `frame-01747.png … frame-01754.png` | 1747–1754 | **0** | 8 | **0** | 8 | **1** | 战前对白 → **「回合 1 玩家」**（= 原版事件 2 的相位） |

* 全黑帧 sha256 与原版**完全相同**：`47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`
* 事件 3 前一帧 `frame-01478.png` sha256 `d240243675549a61343bf86fd55eb9dcec3764b185e3a4a1a9ede0c5095acbac`
  均值 (129.993, 152.281, 43.452)；后一帧 `frame-01487.png` sha256
  `cda3d13cf39cbabd8ae3b8da4e9c8718dc5e72e9c7274fc56a1af7913166f959` 均值 (143.357, 151.079, 108.964)。
* 事件 4 前一帧 `frame-01478.png` 同族：前一帧 `frame-01746.png` sha256
  `8ca5f2c8af1065e6ed15a6fb2910cc252ef091d59c77959877bb1af961b28ac0` 均值 (130.625, 142.037, 98.434)；
  后一帧 `frame-01755.png` sha256 `4fad61d276a97f36ad8fe61fec5289da0afa00143ea347ec592c700819af018e`
  均值 (145.129, 167.185, 77.503)。

### 3.4 判定：**产品差**（不是「没走到」）

| 维度 | 原版 | 重制侧 | 差 |
|---|---|---|---|
| 黑场**相位** | 战前对白前 / 回合 1 前 | **同两个相位都有**（事件 3 / 4） | 无 |
| 黑场**有无** | 有 | **有** | 无 |
| **淡出渐变** | **24 帧（12 级）** | **0 帧（硬切）** | ⭐ **产品差** |
| **淡入渐变** | **24 帧（12 级）** | **0 帧（硬切）** | ⭐ **产品差** |
| 全黑持续 | 18 / 24 帧（9 / 12 个 GBA 帧） | 8 / 6 帧（4 / 3 个 GBA 帧） | 短 |
| 「開始」标题 | 有 | **没有** | ⭐ 产品差（同一相位的另一处缺） |

**证据链**：

1. 重制侧的 2402 帧是**逐帧**采集的（Lua 帧回调，一帧不漏），所以「没有渐变」是**测出来的**，不是采样漏掉。
2. 重制侧事件 3/4 的相位与原版事件 1/2 **逐一对应**（敌方部署→对白、对白→回合 1），
   所以 P 流说的「那次 walk 没走到该相位」**不成立**：它走到了。
3. P 流采不到黑帧的原因是**采样率**：P 每 90 帧采 1 帧，而重制侧的黑场只有 4 个 GBA 帧
   （重制侧同样把每帧画两遍），90 帧的步长必然错过 ⇒ **P4 判定被证伪**。
4. ⇒ 「黑场有没有」不是产品差；**「黑场是硬切而不是渐变」才是产品差**，
   而且它落在 W2 的三桶分类里属于 `black_transition` 桶。

---

## 4. 复跑命令（黑场真值表）

```powershell
# 0) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe，会 LNK1104）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w3'
python tools/mgba_probe/build.py

# 1) 原版开场演出：逐帧采集
python tools/s49_blackfade/blackfade_capture.py \
    --out build/s49-blackfade/original-entry-v2 \
    --state "D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints\scenario-49-battle-14-entry.ss9" \
    --keys "A*20" --settle 90 --capture all

# 2) 重制侧：从上电逐帧采集（ROM 快照已存 build/s49-blackfade/remake-snapshot.gba）
python tools/s49_blackfade/blackfade_capture.py \
    --out build/s49-blackfade/remake-entry \
    --rom build/s49-blackfade/remake-snapshot.gba --no-state \
    --keys "Down,Down,A,A*20" --zero-frames 240 --settle 90 --capture all

# 3) 真值表（一条命令，可复跑）
python tools/s49_blackfade/blackfade_report.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --out build/s49-blackfade/original-entry-v2/blackfade.json \
    --markdown build/s49-blackfade/original-entry-v2/blackfade.md
python tools/s49_blackfade/blackfade_report.py \
    --frames build/s49-blackfade/remake-entry/frames \
    --out build/s49-blackfade/remake-entry/blackfade.json \
    --markdown build/s49-blackfade/remake-entry/blackfade.md

# 4) 人读版真值表
python tools/s49_blackfade/show_blackfade.py \
    build/s49-blackfade/original-entry-v2/blackfade.json \
    build/s49-blackfade/remake-entry/blackfade.json

# 5) 联络表（看相位用）
python tools/s49_blackfade/contact_sheet.py \
    --frames build/s49-blackfade/original-entry-v2/frames --pattern "frame-*.png" \
    --columns 5 --out build/s49-blackfade/contact-original.png

# 6) 整局逐帧回放（证明战斗内没有黑场）+ 两次跑逐字节一致
python tools/s49_blackfade/verify_replay.py --out build/s49-blackfade/verify-replay
```

---

## 5. 任务 A：结算屏真值 —— **没打成**（交最远进度与卡点，不伪造）

### 5.1 一句话

**没有打到胜利，所以结算屏不存在，本流没有伪造任何帧。**
但驱动链路的**最后一环已经打通**：鸣人移动 → 術·忍具 → 十字手里剑 → 瞄准 → 开火 → 预测 → 「可以嗎?」 → **真伤害 18 点**（蜜蜂 8 号 `25 → 7`）。

### 5.2 走通的那一段（`build/s49-victory-capture/v3run24/play.json`）

```
acting      slot 1 (鸣人)  position [11, 6]  menu action5  bees 5
            bee_cells [[3,4,25,5] [4,8,25,6] [3,11,25,7] [6,6,25,8] [5,13,25,9]]
move-result moved=true  to [9, 6]  menu action2      ← 曼哈顿 3 的移动成立
aim         menu=aim  level=4  cursor [9, 6] → target [6, 6]  index=3
aim-cursor  cursor [6, 6]                              ← 游标走到蜜蜂身上
attacked    slot 8  hp 25 → 7  (18 伤害)              ← 真伤害
```

* 单元切换也通了：驱动器会用**格游标**走到「本回合还没行动过的我方单位」再按 A
  （鸣人 → 佐助 → 小樱 → **木叶丸**，木叶丸也是可操作的）。

### 5.3 卡在哪（三条，按阻断顺序）

| # | 现象 | 证据 | 性质 |
|---|---|---|---|
| **A-1** | **十字手里剑整场只能用一次**：用过之后条目从忍术列表里消失（第 2 回合的列表只剩 变身术/影分身术/忍者组合拳 3 项） | `build/s49-victory-capture/v3run17/debug/0007-jutsu-list-slot1.png`（截图）与 `jutsu-index-missing {slot:1,index:3}` | **原版规则真值**（不是 bug） |
| **A-2** | **佐助的火遁术开的是另一个目标界面**（等级 3 + 大信息板 + 自己的确认框），不是十字手里剑那种橙色射程预览；需要再按一次 A 才进真目标游标 | `build/s49-victory-capture/v3run17/debug/0010-aim-mode.png` | 驱动器还没吃透 |
| **A-3** | **某个「移动相位」画面用 B 出不来**（画面上有橙色路径预览，`hatch > 1000`），驱动器于是无限 `cancel-move` | `build/s49-blackfade/stuck-screen.png`（联络表） | 驱动器卡死点 |

⇒ **最远进度**：第 1 回合鸣人完整打了一套并造成 18 点真伤害；
第 2 回合起驱动器在「十字手里剑已消失 + 火遁术目标界面 + 出不去的移动相位」这三件事上打转。

### 5.4 顺带打出来的三条**原版真值**（可复用的）

1. **忍术列表按角色不同（本流实测，截图见 §7.2）**

   | 槽位 | 角色 | 查克拉 | 忍具 | 列表 | 有效攻击 |
   |---:|---|---:|---:|---|---|
   | 1 | 漩涡鸣人 | 138 | 5 | 变身术 / 影分身术 / 忍者组合拳 / **十字手里剑**（6×3、距离 3 直、90%） | 十字手里剑（**一次**） |
   | 2 | 宁智波佐助 | 104 | 4 | **火遁术**（15×1、距离 2 直、95%）/ 影分身术 / 忍者组合拳 | 火遁术（按查克拉，可多次） |
   | 3 | 春野樱 | 110 | 3 | 影分身术 / 分身术 / 忍者组合拳 | 只有体术 |
   | 4 | 木叶丸 | 40 | 4 | （本流未取到） | 木叶丸**可操作**，第 3 回合会死 |

2. ⭐ **蜜蜂每回合都会移动**（M 流的「蜂刺 远程、不位移」**被证伪**）：
   第 1 回合 `(3,4) (4,8) (3,11) (6,6) (5,13)` → 第 2 回合变成 `(5,5) (6,7) (4,9) (8,7) (6,11)`。
   ⇒ 战术含义：蜜蜂会自己走进我方射程，原版的战斗节奏是「敌人压上来」。

3. **战斗内（回合切换 / 单元选择 / 攻击）没有黑场**：
   把驱动器真实打过的对局按键日志逐帧回放（7139 帧，覆盖开场演出 + 4 次我方行动 + 敌方回合），
   扫描结果只有**开场演出里的那 2 处**黑场，帧号与 sha256 与 §3.2 完全一致
   （`build/s49-blackfade/battle-replay/blackfade.json`）。

---

## 6. 黑场相位真值表（索引 · 权威收据在 §3）

| 侧 | 采集帧数 | 黑场事件 | 相位 | 渐变 |
|---|---:|---:|---|---|
| 原版 | 1881（开场） | 2（帧 1013–1078 / 1653–1724） | ①「開始」→战前对白 ②战前对白→「回合 1」 | **24 帧淡出 + 18/24 帧全黑 + 24 帧淡入** |
| 原版 | 7139（整局回放） | **仍然只有 2** | 同上 | 同上 ⇒ **战斗内 0 处黑场** |
| 重制侧 | 2402（上电） | 4（帧 27–34 / 527–532 / 1479–1486 / 1747–1754） | ①上电→标题 ②准备→战斗 ③敌方部署→战前对白 ④战前对白→「回合 1」 | **0 帧淡出 + 6~8 帧全黑 + 0 帧淡入（硬切）** |

* 全黑帧 sha256（两侧、所有黑场都一样）：
  `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`
* 机读收据：`build/s49-blackfade/original-entry-v2/blackfade.json`、
  `build/s49-blackfade/remake-entry/blackfade.json`、
  `build/s49-blackfade/battle-replay/blackfade.json`
* 逐帧 sha256 列表见 **§3.2 / §3.3**（含每个事件的前一帧 / 后一帧 sha256 与均值）。

---

## 7. 结算屏真值清单

**空 —— 结算屏帧不存在**（原版 battle-14 没被打赢，§5）。
**本流没有伪造任何帧。**
采集仪器已就绪，状态机修好即可直接产出：
`play_battle_v3.py` 判定胜利后会用 `capture_endgame()` 逐帧抓 900 帧 PNG，
`endgame_report.py` 会把它们按内容分组（sha256 相同的连续帧算一场戏），
给出每场的首帧 sha256 与相邻两场的像素差分，并写出 JSON 收据。

### 7.1 复跑命令（结算屏链路 + 黑场真值表）

```powershell
# 0) 私有探针
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w3'
python tools/mgba_probe/build.py

# 1) 帧对齐实验（W3-E1：只有 frames 前进帧）
python tools/s49_victory_capture/exp_frame_advance.py --out build/s49-victory-capture/exp-frame-advance2

# 2) 菜单像素真值校准
python tools/s49_victory_capture/calibrate_menus.py --out build/s49-victory-capture/calibrate3

# 3) 战斗驱动器（当前：第 1 回合打出真伤害，未胜利）
python tools/s49_victory_capture/play_battle_v3.py --out build/s49-victory-capture/v3run --debug

# 4) 黑场真值表（一条命令，可复跑）
python tools/s49_blackfade/blackfade_report.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --out build/s49-blackfade/original-entry-v2/blackfade.json \
    --markdown build/s49-blackfade/original-entry-v2/blackfade.md

# 5) 逐帧回放一整局并重出真值表（一条命令）
python tools/s49_blackfade/verify_replay.py --out build/s49-blackfade/verify-replay
```

### 7.2 跑了哪些验证

| # | 命令 | 结果 |
|---|---|---|
| V1 | `python tools/s49_victory_capture/exp_frame_advance.py --out build/s49-victory-capture/exp-frame-advance2` | `rawshot_advances=False` `dump_advances=False` `two_read_rounds_advance=False` `frames_advance=True` ⇒ 只有 `frames` 前进帧 |
| V2 | `python tools/s49_blackfade/blackfade_capture.py --out build/s49-blackfade/original-entry-v2 --state … --keys "A*20" --settle 90 --capture all` | 1881 帧逐帧 PNG（帧号 1…1881） |
| V3 | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-blackfade/original-entry-v2/frames --out …/blackfade.json` | **2 个黑场事件**：66 帧 / 72 帧，各 25 张不同的图 ⇒ 渐变 |
| V4 | `python tools/s49_blackfade/blackfade_capture.py --out build/s49-blackfade/remake-entry --rom build/s49-blackfade/remake-snapshot.gba --no-state --keys "Down,Down,A,A*20" --zero-frames 240 --settle 90 --capture all` | 2402 帧逐帧 PNG（重制侧 ROM 快照 sha256 `804dd793…`） |
| V5 | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-blackfade/remake-entry/frames --out …/blackfade.json` | **4 个黑场事件**，全部 1 张不同的图（硬切） |
| V6 | `python tools/s49_blackfade/blackfade_capture.py --out build/s49-blackfade/battle-replay --state … --key-log build/s49-victory-capture/v3run24/play.json --capture all` | 7139 帧逐帧 PNG（整局回放） |
| V7 | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-blackfade/battle-replay/frames --out …/blackfade.json` | **仍然只有 2 个黑场事件**，帧号与 sha256 与 V3 完全一致 ⇒ 战斗内无黑场 |
| V8 | `python tools/s49_blackfade/verify_replay.py --out build/s49-blackfade/verify-replay` | 两次独立跑：**各 7141 个文件、0 个只在一侧、7139 个 PNG 全部逐字节一致**；真值表收据除 `frames_dir` 路径外完全相同 ⇒ `frames_identical=true`、`receipt_identical=true`、**`identical=true`（exit 0）** |
| V9 | `python tools/s49_victory_capture/calibrate_menus.py --out build/s49-victory-capture/calibrate3` | 9 个界面状态的像素签名（§2 的数据来源） |
| V10 | `python tools/s49_victory_capture/play_battle_v3.py --out build/s49-victory-capture/v3run24 --max-turns 14` | `turns=4 actions=4 hits=1 victory=false`；真伤害：蜜蜂 8 号 `25 → 7` |

### 7.3 证据文件（可复核）

| 文件 | 内容 |
|---|---|
| `build/s49-victory-capture/v3run17/debug/0007-jutsu-list-slot1.png` | 鸣人第 2 回合的忍术列表（十字手里剑已消失） |
| `build/s49-victory-capture/v3run17/debug/0010-aim-mode.png` | 佐助的火遁术目标界面（自己的确认框） |
| `build/s49-blackfade/stuck-screen.png` | A-3 的卡死画面（橙色路径预览 + B 不生效） |
| `build/s49-blackfade/contact-entry-original.png` | 原版开场演出联络表（25 张） |
| `build/s49-blackfade/remake-event3.png` / `remake-event4.png` | 重制侧两处黑场的前后帧 |
| `build/s49-blackfade/original-entry-v2/blackfade.json` | 原版黑场真值表（机读） |
| `build/s49-blackfade/remake-entry/blackfade.json` | 重制侧黑场真值表（机读） |
| `build/s49-blackfade/battle-replay/blackfade.json` | 整局回放的黑场真值表（证明战斗内无黑场） |
| `build/s49-blackfade/verify-replay/verify.json` | 两次独立跑逐字节一致的收据 |

---


## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W3-E1 | 探针的每条命令都会让被模拟的游戏前进一帧（M15） | `frames`/`rawshot`/`dump`/`shot` 四段受控序列，比对帧缓冲 sha256 | 只有 `frames` 前进；`rawshot`/`dump`/`shot` 都不前进 | **已证伪** |
| W3-E2 | 「读寄存器 + 截图」读到上一帧 | 同上 | 同一帧；画面永不过期 | **已证伪** |
| W3-H1 | 战斗 HUD 状态条与故事对话框在同一区域 ⇒ 对话框判不准 | 逐行统计底部亮像素 | HUD 占 y=135..152，故事框从 y=103 起 ⇒ 取 y=100..134 可分 | **已确认** |
| W3-H2 | 紧凑菜单与忍术列表混淆 ⇒ M 流丢了状态机 | 校准脚本测出两者签名 | 紧凑菜单 border=42/dark=304/panel=0；忍术列表 panel=5170 ⇒ 可分 | **已确认** |
| W3-H3 | 移动阶段可以用寄存器认出来 | 比较 level / cursor-active / 像素 | level 与 cursor-active 都认不出（都是 3/1）⇒ 改用**青可达集像素** 5231..6665 vs 0 | **已确认** |
| W3-H4 | 原版 battle-14 开场演出有黑场 | 逐帧亮度剖面（1881 帧） | **2 处**，且都是**渐变**（24 淡出 + 18/24 全黑 + 24 淡入） | **已确认** |
| W3-H5 | 黑场是纯黑一帧 | 同上 | 全黑 18/24 帧，且两侧各有 12 级渐变 ⇒ **渐变** | **已证伪** |
| W3-H6 | 黑场出现在回合切换 / 开场演出 / 胜利前 | 相位对齐（联络表） | 两处**都在开场演出**（战前对白前、回合 1 前） | **已确认**（战斗内未见，§6） |
| W3-H7 | 重制侧没有黑场（P4） | 当前 ROM 逐帧采集 2402 帧 | **4 处黑场**（事件 3/4 与原版同相位）⇒ P4 不成立 | **已证伪** |
| W3-H8 | 黑场是「产品差」 | 两侧逐帧对比 | 相位相同、有黑场，但**渐变为 0**（硬切）⇒ 产品差 | **已确认** |
| W3-H9 | 重制侧缺少「開始」标题 | 联络表（1381–1478 帧） | 原版有、重制侧没有 | **已确认** |
| W3-H10 | 战斗内（回合切换 / 单元选择 / 攻击 / 敌方回合）也有黑场 | 把真实对局的按键日志逐帧回放（7139 帧）做亮度剖面 | 只有开场演出那 2 处，战斗内**0 处** | **已证伪** |
| W3-H11 | 忍术列表对所有角色相同 | 读原版自己的忍术列表界面截图 | 鸣人 4 项 / 佐助 3 项（火遁术）/ 小樱 3 项 ⇒ **按角色不同** | **已确认** |
| W3-H12 | 十字手里剑可以反复使用（M 流的默认假设） | 第 2 回合读鸣人的忍术列表 | 条目**消失**（只剩 3 项）⇒ **整场一次** | **已证伪**（A-1） |
| W3-H13 | 蜜蜂的「蜂刺」远程且**不位移**（M 流结论） | 逐回合读单位池的实时坐标 | 第 1 回合 `(3,4)(4,8)(3,11)(6,6)(5,13)` → 第 2 回合 `(5,5)(6,7)(4,9)(8,7)(6,11)` ⇒ **每回合都会移动** | **已证伪** |
| W3-H14 | 木叶丸不可操作 | 驱动器的单元切换日志 | 切到槽位 4（木叶丸）并进入他的行动 ⇒ **可操作** | **已证伪** |
| W3-H15 | 帧对齐可以用「先读寄存器再截图」保证 | W3-E1 扩展实验（40 次读 + 2 次 rawshot） | 40 次读后帧缓冲 **sha256 不变** ⇒ 读操作确实不前进帧 | **已确认** |

---

## 9. 改动文件清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `tools/s49_blackfade/blackfade_scan.py` | 新增 | 逐帧亮度扫描（`frames 1 0` + `rawshot`） |
| `tools/s49_blackfade/blackfade_trace.py` | 新增 | 带按键序列的逐帧追踪 |
| `tools/s49_blackfade/blackfade_capture.py` | 新增 | Lua 帧回调采集器（一条命令产出逐帧 PNG） |
| `tools/s49_blackfade/capture_frames.lua` | 新增 | 采集器的 Lua 脚本（逐帧 `emu:screenshot`） |
| `tools/s49_blackfade/blackfade_report.py` | 新增 | **黑场真值表**（淡出/全黑/淡入三段切分 + sha256 收据） |
| `tools/s49_blackfade/contact_sheet.py` | 新增 | 联络表（看相位） |
| `tools/s49_blackfade/show_blackfade.py` | 新增 | 人读版真值表 |
| `tools/s49_victory_capture/battle_obs.py` | 新增 | **帧对齐观测器**（rawshot + 寄存器 + 像素签名） |
| `tools/s49_victory_capture/exp_frame_advance.py` | 新增 | W3-E1 实验（命令是否前进帧；扩展版测 40 次读） |
| `tools/s49_victory_capture/calibrate_menus.py` | 新增 | 菜单像素签名校准 |
| `tools/s49_victory_capture/measure_frames.py` | 新增 | 对任意 PNG 打像素签名 |
| `tools/s49_victory_capture/probe_jutsu_mode.py` | 新增 | 单个忍术的目标界面取证（逐帧截图） |
| `tools/s49_victory_capture/play_battle_v3.py` | 新增 | 本流的战斗驱动器（逐帧进度日志 `progress.jsonl`） |
| `tools/s49_victory_capture/verify_play_v3.py` | 新增 | 两次独立跑逐字节一致（复用 `verify_capture.compare`） |
| `tools/s49_blackfade/verify_replay.py` | 新增 | **两次独立跑逐字节一致**（逐帧回放口径，§7.1 第 5 条） |
| `notes/s49-fidelity/W3-original-truth.md` | 新增 | 本文件 |

**没有**改重制线任何文件、逆向线任何文件、`tools/s49_audio_probe/`、`tools/s49_rule_probe/`、
`tools/s49_overlay_align/`、`tools/s49_fidelity_report.py`。
