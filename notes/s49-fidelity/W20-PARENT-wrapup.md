# W20-PARENT —— S49「木叶丸 vs 野蜂」复刻：wave 18–19 收口成果与交接

> 2026-10-25 14:0x · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 覆盖波次：wave 18（U1–U5 + 父代理）+ wave 19（A–D + 父代理）
> 仪器：`tools/s49_fidelity_report/`（判定台，**唯一验收仪器**）·
> `tools/s49_wave18/`（接线器 + 步偏移对齐器，本波新增）·
> `tools/s49_w5/`、`tools/s49_w19b/`、`tools/s49_w19d/`（各流仪器）
> 任务书：`notes/s49-fidelity/WAVE18-TASKS.md`、`WAVE19-TASKS.md`、**`WAVE20-TASKS.md`（交接）**
> 1:1 报告：`docs/s49-fidelity-report-20261024.md`

---

## 0. 一句话成果

> ⭐⭐ **S49「木叶丸 vs 野蜂」的重制侧第一次能「真打赢仗」，并把結算链三屏做成逐像素零差。**
>
> | 里程碑 | wave 17 末 | wave 19 末 |
> |---|---|---|
> | **真实战斗** | ⛔ 蜂的 HP 从未下降过 | ✅ **5 只蜂各掉 25 HP（25→0）**、`escort_hp 40→40`、**`poke_commands: 0`**、`from_real_battle: true` |
> | **結算链**（对比原版真值） | 對白 26,819 / 菜單 37,694 / 人物 1,898 px | ⭐ **三屏全部 0 px**（合计 **−66,411 px**） |
> | **最坏栈深** | 26,888 B（可用 21,308 B ⇒ 溢出） | ✅ **14,944 B**（裕量 6,364 B） |
> | **判定台残差** | 109,569 px | **107,051 px**（判定台口径；⭐ **新基线已被接受**） |
> | **12 步出包流水线** | 11/12（第 11 步红） | ⭐ **12/12 全绿**（ok = true） |

---

## 1. ⭐ 两个硬阻塞的闭合（wave 18–19）

### 1.1 D4：攻击确认链把 IWRAM 用户栈撑爆

| 项 | 内容 |
|---|---|
| **根因** | `battle_session<MaxUnits> next = session;`（**8,052 B**）在**运行时**有 **3 处**（全仓 13 处，其余 10 处只被单元测试调用） |
| **第二条溢出链** | ⭐ **胜利路径是独立的**：`advance_empty_side`（16,880 B）+ `resolve_battlefield_object_event`（8,088 B）⇒ 链深 **33,536 B** ⇒ **只修确认链，战斗打完那一刻照样炸** |
| **嵌套陷阱** | ⭐ 外层持有会话副本时又调用内层拷贝 ⇒ **单个共享 EWRAM 缓冲会被内层覆盖** ⇒ 事务语义被破坏（症状 = 结算结果偶发错乱，**不崩**）⇒ 工作区必须**可嵌套** |
| **修法** | `battle_action_system.h`：**EWRAM 深度 2 的 LIFO 槽位池 + RAII 句柄**；`preview_area` 只拷 source 单体 468 B（新增 `collect_preview()`，**`collect()` 一字未改**）；`battle_turn_flow.h` 5 处；`battle_action_combinations.h` |
| **栈深实测** | `resolve_battlefield_object_event` 8,088 → **无独立帧**；`advance_empty_side` 16,880 → **120**；`combinations::resolve` 9,504 → **1,456**；`preview_area` 5,864 → **720** |
| **栈深怎么算的** | W1 自建 ELF 调用图分析器，**穷举 994,141 条路径（COMPLETE）** ⇒ 14,944 B |
| **自我推翻** | ⭐ **U1 的「21,304 B 链算术」是几条互斥路径的并集**，不是单条路径 ⇒ 已被实测推翻 |
| **自证** | 在 `IRQ_VectorTable[0]`（`0x03002880`）挂 **mGBA 写监视点**：改前按 A 那一瞬命中（`sp=0x03002818`，**比栈底低 940 B**）；改后**全程不命中**、`sp=0x03004D68`、向量表前后**逐字节相同** |

### 1.2 「開始」标题卡：不是缺确认框，是**卡片语义不对**

| | 原版 | 重制侧（wave 18 末） | 重制侧（wave 19 末） |
|---|---|---|---|
| 卡片是否看输入 | ⛔ **完全无视**（按/不按 A 的 300 帧**逐像素相同**） | ⛔ 按 A **冻住**；不按则 A↔B **无限循环** | ✅ **纯定时、无视输入、一次走完**（30/30 帧 sha256 逐字节相同） |
| 步偏移 | — | +4 → 第 10 步掉到 **+3** | ✅ **恒为 +4** |
| 姿态 B | — | walk 里没有 | ✅ **首次出现**（`step-10`：2,761 → **278 px**） |

* **根因**：`battle_opening_title.h` 的 `phase()` **取模**（`(_frame/23) % phase_count`）⇒ 永远转不完；
  且卡片**只在部署相位离开 `start_confirmation` 时消失** ⇒ **A 键被吃掉而相位没前进**。
* **原版的卡片时间线（实测，可当规格）**：升起 → 姿态 A **+98 帧** → 姿态 B → **+204 帧**卡片消失
  → **+266 帧**黑场淡出 → **+284 帧**全黑。
* **连带**：`lead_frames` 38 → 30 ⇒ `step-11` 残差 **30,418 → 1,212 px**。

---

## 2. ⭐ 像素账（两个口径，**不许混用**）

### 2.1 結算链逐屏（`tools/s49_victory_align/align_settlement.py`，sha256 配对）

| 屏 | wave 17 末 | wave 19 末 | 备注 |
|---|---:|---:|---|
| 勝利 | 0 | **0** | |
| **結算屏** | 2,582 | **684** | 人物 1,898 → **0**；**684 = 「戰鬥分」规则缺失**（见 §4.2） |
| 6 張升級屏 | 0/6 | **0/6** | D 路独立复核（6 张互不相同的真值帧，自算差 0） |
| **戰後對白** | 26,819 | ⭐ **0** | 定位错 `(0,0)` → `(8,48)` + 7 张對白页资产 |
| **任務菜單** | 37,694 | ⭐ **0** | 同上 + 2 张菜單层资产 |
| **合计** | **93,993** | **684** | **−93,309 px**（其中 −92,625 来自 4 屏归零） |

### 2.2 判定台（25 帧 walk，`tools/s49_fidelity_report/`）

| | 读数 |
|---|---:|
| wave 17 / 18 末 | 109,569 px（中位 1,372 / 峰值 27,325 / 全 0 帧 4/25） |
| **wave 19 末** | **107,051 px**（判定台口径；**这是 arg-min、无时刻约束**） |
| 归因 | identical 4 / product_diff 17 / pairing_diff 4 |

⚠️ **三个数不是同一个口径**（报告 §2 有警告）：
判定台读数（arg-min）· 可证像素下界（每拍内全部帧对取最小，25 拍求和）· 内容锚可达数（同一时刻的帧对）。

### 2.3 残差结构的两次认知升级

| 阶段 | 结论 |
|---|---|
| wave 17 | 109,569 px 里 82,571 px（75 %）是「4 帧配对错位」 |
| wave 18（父代理，新仪器 `tools/s49_wave18/align_capture_steps.py`） | ⭐ 逐帧扫偏移 ±1…±6 证明：**重制侧 35 帧里没有任何一帧能匹配那 4 个时刻** ⇒ **不是仪器选歪，是重制侧走不到** ⇒ 但**根因不是「打完仗」**，而是**标题卡吃掉了 A 键** |
| wave 19 末 | ⭐ 标题卡修好后**时刻对齐了**，但原版 `step-19/21/22` 仍各差 24k–28k px ⇒ **剩下的最大块（~73 k px）是战斗场景的相机/布景差异** |

---

## 3. 父代理本轮自办（6 项）

| # | 事项 | 结果 |
|---|---|---|
| 1 | ⭐ **棘轮红灯裁决** | wave 17 的 `test_battle_range_ui_phase_truth_table`（新增红）**归属 U2**：U2 把**活相位规则改错了**（原版目标选择帧**零青**，G-H15；结算帧的青+橙是「相位切换不清缓冲」的残迹、属渲染层）⇒ **回退规则** ⇒ **pass=118 / fail=20**，零新增红 |
| 2 | ⭐ **构建隔离** | 并发构建会互相覆盖同一 `.gba`，本机安全策略又拦递归拷贝 ⇒ 改成**只拷可变源码目录 + 只读大目录用符号链接** ⇒ 4 路各自独立构建（实测 `ROM fixed!`） |
| 3 | ⭐ **接线器** `tools/s49_wave18/integrate.py` | 按 lane 清单把独占文件拷回共享树 + **检出越界改动**（并带 `--ignore` 前缀白名单，避免「共享树已前移」造成的假阳性） |
| 4 | ⭐ **步偏移对齐器** `tools/s49_wave18/align_capture_steps.py` | sha256 精确匹配 + 逐偏移残差 + **最优偏移剖面** ⇒ 直接定位到「标题卡吃 A 键」 |
| 5 | ⭐ **探针签名修好（第 11 步仪器缺陷）** | `framedump` 的**参数顺序**在探针里是 `<count> <addr> <len> <keymask> <prefix>`，而 `build/mgba-probe-w4` 里那份**旧二进制**还是 `<prefix> [keymask]` ⇒ 存档/边界步骤**连续三波失败** ⇒ 重建探针（`KONOHA_PROBE_OUT`）并换掉私建那份 ⇒ **步骤 11 通过** |
| 6 | **路线图回填** | wave 17 收口 / wave 18 收口 / wave 19 开火 / wave 19 收口 / wave 20 排期，全部写进 `docs/sequel-roadmap.md` |

---

## 4. ⭐ 仍然开放的四项（**wave 20 的任务书已写好**）

> 任务书：`notes/s49-fidelity/WAVE20-TASKS.md`（四路分工 + 文件互斥表 + 判定问题 + 验收表）

### 4.1 ⭐⭐ Butano 调色板耗尽（**真实结算链的唯一阻塞**）

* 现象：真实战斗成功后，结算链**第 1 页（勝利屏）就死在 Butano 错误屏**
  ⇒ `BPP4 palette create failed. Colors count: 32 / no more available colors` ⇒ 相位冻结在 13 ⇒ **7 段一段都进不去**。
* A/B（同 ROM 同探针）：**poked 自检链 48 页全走完**；**不用忍具的败北真实链同样炸** ⇒ 与忍具/胜负无关。
* 已测事实：Butano 只剩 **1 个 8bpp/256 色调色板**（16 槽）⇒ 4bpp 无空槽；
  全工程唯一匹配的两张屏幕尺寸背景 = **勝利屏 `scenario_41_victory_bg`（8bpp/256）** 与 **`battle_duel_forest`（4bpp/32）**
  ⇒ **撞车**。
* 接线点（D 路给，待核实）：`battle_runtime_scene.cpp:1605-1624` / `5528-5545`。

### 4.2 ⭐ 「戰鬥分」发奖规则**根本不存在**（結算屏最后 684 px）

* `battle_results.h:369-395` 的 `battle_experience` = **Σ `unit->carried_experience`**；
  该字段全工程**只有两个写点**：① `battle_scenario_loader.h:465` 的**场景种子**（实测为 **0**）；
  ② `battle_action_system.h:2330-2332` 的**阵亡零和转移**。
* ⇒ **没有「击倒发奖」规则** ⇒ **真实战斗的战果也必然 0/0/0** ⇒ **产品缺口，不是 poke 链的假象**。
* 原版取值（原版 100/150/0 与 300/350/200；某场景 59/59/30）⇒ **公式未知**，需逆向线取证。
  ⇒ wave 20 的 **E4 路**负责取证，**E2 路**负责实现。

### 4.3 ⭐ 战斗段首帧的 ~73 k px（判定台剩余最大块）

* 原版 `step-19/21/22` 的 `bg_hofs` = `[160, 261, 268]`、重制侧 = `[160, 0, 131]`
  ⇒ **相机/布景不在同一个位置**（⚠️ 两侧地图不同 ⇒ 寄存器原值**不可直接比大小**，要先找语义映射）。
* wave 20 的 **E3 路**负责。

### 4.4 黑场 B2 / B3 / B4（玩家看得见）

| # | 事件 | 帧号 | 根因 | 可达性 |
|---|---|---|---|---|
| B2 | 准备→战斗 6 帧纯黑 | 527–532 | `battle_runtime_scene.cpp:8152` | ⛔ **被 64 KB BG 图块区卡死**（准备背景 32 KB + 部署地图 64 KB 无法共存 ⇒ **到 0 帧不可能**）⇒ 只能给最小可达值 + 硬证据 |
| B3 | 生长→对白 2 帧纯黑 | 1657–1658 | `:5066-5067` 的 `map.reset(); bn::core::update();` | ⇒ 挪进持黑段（顺带把事件 2 淡入 28 → 24） |
| B4 | 对白内部 8 帧纯黑 | 2123–2130 | `:6497-6514` + `battle_visual_resource_coordinator.h:119-131` | ⇒ 推迟到事件 2 淡出末几级 |

⇒ wave 20 的 **E1 路**（它拥有 `battle_runtime_scene.cpp`）。

---

## 4.5 ⭐ 最终出包判决（2026-10-25 14:10）

`
pipeline: PASS   ok = true
ROM: e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2
战场区残差总和: 107051 px（同一个 ROM 连读 3 次逐项相同）
accepted baseline: build/s49-package/baseline-accepted/report.json
                  accepted_at 2026-10-25T14:10:54+08:00
package: build/s49-package-w19b/   receipt: build/s49-package-w19b/receipt.json
`

⭐ **第 11 步（save-boundary）的仪器缺陷已修**：根因是**私建探针二进制过期**
（ramedump 在探针源码里的参数顺序是 <count> <addr> <len> <keymask> <prefix>，
而 uild/mgba-probe-w4/mgba-probe.exe 还是 10-23 的旧二进制 <prefix> [keymask]）
⇒ 重建探针（KONOHA_PROBE_OUT）并换掉私建那份 ⇒ 步骤 11 通过。

---

## 5. 复现（本波最终状态）

```powershell
# 1) 共享树构建（重制线）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 2) 判定台（唯一验收仪器）
python tools/s49_fidelity_report.py --out build/s49-report/report-main.json

# 3) 12 步出包流水线
python tools/s49_package/run_pipeline.py --out build/s49-package-w19b

# 4) 真实战斗（现在应当打赢）
python tools/s49_battle_balance/v1_battle.py --rom <ROM> --out build/w19-verify/run --boot --max-turns 400 --use-tools
#   ⇒ 判据：bee_hp_dropped=true、from_real_battle=true、poke_commands=0

# 5) 单测棘轮（HEAD 基线 vs 工作区）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel
#   ⇒ 期望：pass=118 / fail=20（20 项预存债，逐名相同即零回归）
```

⚠️ **本机构建非字节可复现**（同一份源码两个 sha）⇒ **一切测量必须绑定自己那份 ROM 的 sha**。
⚠️ 随包必须带 **ROM + 重录命令**（见报告 §12）。

---

## 6. 假设台账（本波新增）

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-18 | D4 = 8,052 B 会话栈拷贝撑爆 IWRAM 栈 | `.su` 重建 + ELF 调用图穷举 + 写监视点 | 成立（14,944 B ≤ 21,308） | **已确认** |
| P-19 | 胜利路径是第二条独立溢出链 | 链算术 6,136+2,432+16,880+8,088 | 成立（33,536 B） | **已确认** |
| P-20 | 单缓冲 EWRAM 工作区会被内层覆盖 | 调用图 + 生命周期分析 | 成立 ⇒ 必须可嵌套 | **已确认** |
| P-21 | 「はい」被打回是假象 | 写监视点 + 遥测 | **证伪**（是那一帧 ROM 死在栈溢出上） | **已证伪** |
| P-22 | U2 的「青不再被 move_phase 锁住」是对的 | 与 G-H15 的原版帧证据对拍 | **证伪**（活相位规则被改错） | **已证伪** |
| P-23 | 原版标题卡无视输入 | 300 帧按/不按 A 的逐像素对照 | 成立 | **已确认** |
| P-24 | 那 4 帧是「战后」的时刻 | 原版 `step-09/10` = 标题卡；4 帧步号在其后 | **证伪**（是战斗段第 1 回合） | **已证伪** |
| P-25 | 結算屏人物需要 8bpp 图集 | 色数分解 + 真值帧回收 | **证伪**（立绘自身 15/12/15 色 ⇒ 4bpp 够） | **已证伪** |
| P-26 | 真实链拿不到是因为「战斗打不完」 | D 路实测：真实链第 1 页就死在**调色板**错误屏 | 成立（但根因不同） | **已确认** |

---

## 7. 时间账

| | |
|---|---|
| 72 h 窗口 | 2026-10-23 23:13 → **2026-10-26 23:13** |
| wave 18 开火 | 2026-10-25 00:05（已用 24.9 h） |
| wave 19 开火 | 2026-10-25 00:55（已用 25.7 h） |
| wave 20 开火 | 2026-10-25 01:45（已用 26.5 h，**剩 45.5 h**） |
| wave 20 状态 | ⚠️ **四路在 01:48–01:51 被额度中断**（未产出代码）⇒ **任务书即交接**，可直接按 `WAVE20-TASKS.md` 重开 |

⇒ **本波（wave 18–19）共 9 路子代理全部交付**（wave 18：U1–U5；wave 19：A–D），
外加父代理自办 6 项（§3）。

---

## 8. 收口后的巡检（2026-10-25 14:2x，父代理自办）

> 收口后复核：把「产物是否还在盘上、结论是否还成立」当成一次独立审计。

| 检查 | 方法 | 结果 |
|---|---|---|
| 交付物还在盘上 | 直接 `Get-Item` 五个关键文件 | ✅ 收口笔记 14,764 B / 交接书 17,719 B / 1:1 报告 199,623 B / 收据 85,592 B / ROM 12,257,620 B |
| 共享树 ROM 仍等于已接受基线 | 重算 sha256 | ✅ `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2` = 收据里的 `accepted_baseline.rom.remake` ⇒ **基线仍然可比** |
| 12 步流水线 | 读 `build/s49-package-w19b/receipt.json` 的 12 个 step | ✅ 全部 `ok=true`；顶层 `ok=true`、`failed_step=null`；`accepted_baseline_promoted.ok=true`（accepted_at 2026-10-25T14:10:54+08:00） |
| 单测棘轮 | 收据步骤 2 的 metrics | ✅ HEAD `pass=101/fail=20` → 工作区 `pass=118/fail=20` ⇒ **20 项预存债逐名相同、零新增红** |
| 判定台残差 | 收据步骤 5 | `field_residual.sum = 107051`（min 0 / median 1323 / max 27325 / zero_frames 4 / frames 25）⇒ 与 §2.2 一致 |
| 孤儿进程 | `Get-Process mgba-probe` | ✅ **0 个**（无残留录制器）；机器物理余量 6,023 MiB / 32,561 MiB |
| wave 20 的半成品有没有污染共享树 | 全树找 `e2_dbg.cpp` / `test_battle_experience_award.cpp` / `blackfade-fix1` | ✅ **0 命中** ⇒ wave 20 的诊断产物只在 lane 副本里，共享树干净 |

### 8.1 三个开放阻塞在当前代码里**仍然成立**（只读复核，未改一行）

| 阻塞 | 复核方法 | 结论 |
|---|---|---|
| ⭐⭐ **Butano 调色板耗尽** | 读 `battle_runtime_scene.cpp`：`_add_victory_background()`（L1647）建 8bpp/256 色胜利屏背景；`_release_background_before_bpp_transition()`（L5661）只 `reset()` 掉 `_duel_hud_background` 与 `map`，**不释放胜利屏背景**；`_bind_duel_background()`（L5673）随后建 4bpp/32 色 `battle_duel_forest`（要 2 个连续槽） | **仍成立** ⇒ 16 槽 bank 被 8bpp/256 占满 ⇒ 后到的 4bpp 请求必然 `BN_ERROR` ⇒ 真实结算链第 1 页仍进不去 |
| ⭐ **「戰鬥分」发奖规则缺失** | 读 `battle_results.h:369-395`：`_battle_experience()` 只累加 `unit->carried_experience`（同角色转移）+ 被动 `battle_experience_passive_target` 奖励 | **仍成立** ⇒ 无「击倒发奖」写点 ⇒ 結算屏那 684 px 是产品缺口 |
| ⭐ **战斗段首帧 ~73 k px** | `bg_hofs` 原版 `[160,261,268]` vs 重制 `[160,0,131]`（见 §4.3） | **仍开放**（需要相机/布景的语义映射） |

### 8.2 ⚠️ 一个口径澄清（给 wave 20 复开的人）

`build/w19-b/chain-final/chain.json` 的 `entry.method` = **「controller state poke (phase + outcome)」**
⇒ **wave 19 B 那张「48 页全链」的对照表是在 *poked* 链上量的**（`build/w19-b/align-final.json` 的
`remake_dir` 就是这个目录）；
而**真实战斗链**在 wave 19 D 那份 ROM（`db676a63…`）上**只录到第 1 页就死在 Butano 错误屏**
（`build/w19-d/chain/real/`）。

⇒ **结论**：結算链的 4 屏 0 px 是**资产/渲染层**的结论（可信）；
但**「真实链能否走完 7 段」至今从未在任何一个 ROM 上被实测过** —— 因为调色板阻塞一直没解。
⇒ wave 20 的 **E1 必须先解调色板**，否则 D 路的「真实链逐屏差表」永远拿不到。

### 8.3 ⭐⭐ 收口后的复测：**已接受 ROM 上的真实战斗**（补上最后一个证据缺口）

> 巡检时发现：判定台/流水线都绑在已接受 ROM `e2182fff9…` 上，
> 但**没有任何一份真实战斗收据绑在这个 ROM 上**（`build/` 下 0 份收据含该 sha）
> —— 之前的真实战斗收据分别绑在 wave 18 的 `9127915b…` 与 wave 19 D 的 `db676a63…` 上。
> ⇒ **补测**（用流水线钉住的副本，不重建、不改产品代码）：

```
python tools/s49_battle_balance/v1_battle.py \
  --rom build/s49-package-w19b/work/pinned-rom/measured.gba \
  --exe build/mgba-probe-w19/mgba-probe.exe \
  --out build/w20-verify/accepted-run --boot --max-turns 400 --use-tools
```

| 判据 | 结果 |
|---|---|
| ROM sha256 | `e2182fff9a6ba987ae2d920418acbb98bc9d1e187312e9b787f982b89cee6ad2`（= **已接受基线的 ROM**） |
| `entry.poke` | `false`（**不是 poke**） |
| `entry.poke_commands` | **0**（`probe_commands` 13,449 条里 0 条 poke ⇒ 收据自证） |
| `errors` | **`[]`**（无 `rom-frozen`、无崩溃） |
| `outcome` | **1**（胜利） |
| `round` / `frames_run` | 13 / 60,518 |
| `bee_hp_start → bee_hp_end` | 5 只蜂 **25 → 0**（全灭） |
| `bee_hp_dropped` | **true** |
| `escort_alive` | **true**（木叶丸 40 HP 存活） |
| `from_real_battle` | **true** |
| 墙钟 | 31.4 s |

⇒ ⭐ **「重制侧能真打赢仗」这条里程碑，现在有了一份绑定在已接受 ROM 上的收据**（此前只有 wave 18/19 的中间 ROM 版本）。

### 8.4 ⭐⭐ 同时**复现了** Butano 调色板阻塞（在已接受 ROM 上）

同一跑的第二段（`settlement`）：

```
settlement pages: 1   final_phase: 13 (outcome)   poked: false   stuck_at: 6
```

第 1 页 `page-000-outcome.png` **不是勝利屏，而是 Butano 错误屏**：

```
ERROR in bn_palettes_bank.cpp.h
create_bpp_4:176
BPP4 palette create failed. Colors count: 32
There are no more available colors.
```

探针 stderr 里 Butano 自己的调色板状态（失败分支才打印）：

```
[mgba] palettes: 16
[mgba] bpp_8 - slot_index: 0 - slots_count: 16 - colors_count: 256 - usages: 1
```

⇒ **16 槽 bank 被一个 8bpp/256 色的调色板占满** ⇒ 后到的 4bpp/32 色请求必然失败
⇒ **真实结算链在已接受 ROM 上依然一段都进不去** ⇒ ⭐⭐ **阻塞 #1 在最终交付物上原样存在**。

⇒ 🎯 **这坐实了 wave 20 的优先级**：**E1 是硬前置** ——
E1 不修，E2（684 px 的「戰鬥分」）连一个可对照的真实結算屏都拿不到，
E3 的「真实链逐屏差表」同理。
⇒ 交付物里已经有的 `build/w20-verify/accepted-run/`（收据 + 错误屏截图 + stderr）
就是 **E1 修复前后的对照基线**（修好后同一命令重跑，错误屏必须消失且 `settlement pages ≥ 7`）。

### 8.6 ⭐⭐⭐ 收口巡检的**重大更正**：wave 20 的 E1 其实**已经做完了调色板修法**（被截断，没写笔记）

> 完整回收报告：`notes/s49-fidelity/W20-RECOVER-lanes.md`
> 补丁文件：`build/w20-verify/e1-palette-fix.patch`（2,532 B / +35 行 / 唯一改动文件 `battle_runtime_scene.cpp`）

按 AGENTS.md「lost ≠ 没干活」的纪律翻 lane 副本，查出：

| 项 | 结论 |
|---|---|
| **E1 的修法** | ⭐ **已存在且已验证**：进入全屏结算相位前**先释放决斗森林（4bpp/32 色）+ 决斗 HUD**，再让 8bpp/256 色的胜利屏背景进来 ⇒ 16 槽 bank 不再被两个屏幕尺寸的背景同时占 |
| **A/B 证据** | 同 lane 同探针：修前 `chain-base` = **1 页 + Butano 错误屏 + palette_status present**；修后 `chain-fix1` = **48 页 + `final_phase=task_menu` + 无错误屏** |
| **真实战斗** | `poke_commands=0`、`outcome=1`、蜂 25→0、`errors=[]`、**结算链 48 页**、7 段相位全走到 |
| **逐字节相同** | ⭐ 真实链里 **9 帧与原版真值 sha256 完全相同**（勝利/6 張升級/忍具一覽/戰後對白/任務菜單）⇒ **「真实链能走完 7 段」第一次被实测证明** |
| **⛔ 但有残差** | 結算屏（`page-001-result.png`）比无修法的已接受 ROM **差 35,006 px**：整块偏绿 ⇒ 画在**决斗森林的调色板**上而不是結算屏自己的底板 |
| **黑场** | B2/B3/B4 **一件都没做完**（基线表在 `W20-RECOVER-lanes.md` §4） |

⇒ ⚠️ **收口时说的「wave 20 四路颗粒无收」是低估** ——
E1 交付了核心修法 + 完整验证链，只是**没写笔记、没接线回共享树**。
⇒ 但 **不能直接照搬**：搬过去会带着 +35 k px 的結算屏回归
⇒ **验收必须是「三者同时成立」**：48 页 ∧ 結算屏 ≤ 684 px ∧ 无 Butano 错误屏。

⇒ 另有两处更正：
* **E2 不是「实现发奖规则」** —— 「击倒 ⇒ 戰鬥分转给攻击者」的逻辑
  `battle_action_system.h:2327-2333` **早就有了**；
  真正缺的是**阵型表里的种子数据**（`generated_battle_scenario_content.h` 的 scenario 14 种子字段全是 0）⇒ 归 E4 取证。
* **E3 有实质进展**：步偏移扫描出 **best_offset = 4**（total 648,356 → **148,914 px**），3 对精确匹配。

### 8.5 假设台账（本节新增）

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| P-27 | 已接受 ROM 上「真打赢仗」仍然成立（wave 18/19 的收据绑的是中间 ROM） | 用流水线钉住的 `e2182fff9…` 副本重跑 `v1_battle.py` | 成立（`outcome=1`、蜂 25→0、`poke_commands=0`、`errors=[]`） | **已确认** |
| P-28 | 调色板阻塞只存在于 wave 19 D 的中间 ROM | 同一次跑的第二段 | **证伪**：在 `e2182fff9…` 上**原样复现**（Butano 错误屏 + bank 只剩 1 个 8bpp/256） | **已证伪** |
| P-29 | 「結算链 4 屏 0 px」可以当成真实链的证据 | 查 `build/w19-b/chain-final/chain.json` 的 `entry.method` | **证伪**：那是 **poked** 链；真实链一段都没走到 | **已证伪** |
