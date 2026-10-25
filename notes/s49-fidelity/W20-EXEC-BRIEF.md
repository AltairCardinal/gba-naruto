# W20-EXEC —— wave 20 复开任务书（按 2026-10-25 14:5x 的回收结论重排）

> 本文件是**四路子代理的共同前置**。每路子代理**必须先读完本文件**，再读自己的那一节。
> 上游：`notes/s49-fidelity/W20-RECOVER-lanes.md`（回收报告，**最重要**）
> · `notes/s49-fidelity/WAVE20-TASKS.md`（原任务书，已被本文件 §2 修订）
> · `notes/s49-fidelity/W20-PARENT-wrapup.md` §8.3–8.6（收口巡检）
> 父代理：`mvs_4e730a9ded524558a303c115875a9707`

---

## 0. ⏰ 时间预算

* **本轮窗口 ≈ 2 小时**（额度 3.5 h 后重置，父代理要留出时间做接线 + 12 步流水线 + 报告）。
* ⇒ **每个子代理的任务书都写明了「先写笔记骨架、结论增量更新」**（截断风险，见 §5）。
* ⇒ **父代理在 T+75 min 会开始收口**：届时各路必须**已经有一份能用的笔记 + 一份可运行的改动**，
  哪怕没做完。**不要追求完美，要追求「有交付物」。**

---

## 1. 三棵树与只读约束

| 树 | 路径 | 你的权限 |
|---|---|---|
| **主仓（工具 + 笔记 + 报告）** | `D:\Github\gba-naruto` | ✅ 可写（笔记、工具、路线图） |
| **重制线（产品代码 + 资产）** | `D:\Shell\Github\gba-naruto-butano\butano-sequel` | ⛔ **不要直接改** —— 只在你自己的 lane 副本里改 |
| **逆向线** | `D:\Shell\Github\gba-naruto-reverse` | ⛔ **全程只读**（E4 路也一样） |

**你的 lane 副本**（已存在，已与共享树同步，**不要重建副本**）：

| 流 | 副本根 |
|---|---|
| E1 | `D:\Github\gba-naruto\build\w20-e1\butano-sequel` |
| E2 | `D:\Github\gba-naruto\build\w20-e2\butano-sequel` |
| E3 | `D:\Github\gba-naruto\build\w20-e3\butano-sequel` |
| E4 | `D:\Github\gba-naruto\build\w20-e4\butano-sequel` |

⚠️ **`third_party/` 是真实目录不是符号链接**（1,852 个 `graphics/` 资产与共享树逐一相同）。
⇒ **不要整棵重拷**（慢且会被安全策略拦），**只改源码目录**。

---

## 2. ⚠️ 最重要的前提更正（**别按旧任务书从零做**）

| 旧任务书的说法 | 实际 |
|---|---|
| 「E1 要从零修 Butano 调色板耗尽」 | ⭐ **E1 已经做完了，补丁在 `build/w20-verify/e1-palette-fix.patch`（+35 行，唯一改动文件 `battle_runtime_scene.cpp`）**，A/B 证据：修前 1 页 + 错误屏 → 修后 **48 页 + `final_phase=task_menu` + 无错误屏** |
| 「E2 要实现『击倒 ⇒ 轉發戰鬥分』」 | ⭐ **该逻辑 `battle_action_system.h:2327-2333` 早就有了**；真正缺的是**阵型种子数据**（`generated_battle_scenario_content.h` 的 scenario 14，5 个敌人的 `battle_experience` 字段**全是 0**） |
| 「E3 要从零找相机/布景映射」 | ⭐ **E3 已有进展**：步偏移 **best_offset = 4**（total 648,356 → **148,914 px**），3 对精确匹配（`step-14/15/17-A` ↔ `step-18/19/21-A`） |

---

## 3. 🔧 仪器纪律（**违反过两次的坑，别再踩**）

1. **改过探针源码 ⇒ 重建所有私建探针。**
   `framedump` 的真实签名在 `tools/mgba_probe/host_main.c`：
   `<count> <addr> <len> <keymask> <prefix>`。
   `build/mgba-probe-w4/` 里那份是 10-23 的旧二进制（`<prefix> [keymask]`）⇒ **不要用它**。
   重建自己的副本：`$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-<你的流>'; python tools/mgba_probe/build.py`
   ⚠️ **绝不覆盖共享的 `build/mgba-probe/mgba-probe.exe`**。
2. **本机构建非字节可复现** ⇒ **一切测量必须绑定自己那份 ROM 的 sha**。
3. **判定台读数必须同 ROM 比较**（不同 ROM 就不许比大小）。
4. **只有一台机器的 RAM**（32.5 GB 总 / 约 7 GB 空闲）⇒ **全机同一时刻只允许一路跑长录制**。
   ⇒ **长录制必须用全局锁**：
   ```powershell
   python tools/s49_w20/capture_lock.py --run --label <你的流> -- <你的命令>
   python tools/s49_w20/capture_lock.py --status
   ```
   拿不到锁就**换别的事做**（读代码、写笔记、跑短命令），别干等。
5. **共享 `probe.py` 每行一个读线程会死锁** ⇒ 长录制用 `tools/s49_battle_balance/w1_probe.py`。
6. **recorder 吃 7–8 GB 且泄漏** ⇒ 跑完查孤儿进程：
   `Get-Process -Name 'mgba-probe' -ErrorAction SilentlyContinue`
7. **无窗口无声门禁**：`python tools/mgba_probe/verify_headless_recording.py`
8. **改含中文的源文件一律用 `edit`/`write` 工具**，不要用 PowerShell `Set-Content`/`-replace`
   （PS 5.1 按 GBK 读入写回会毁 UTF-8）。
9. **新写文件一律 LF、无 BOM**；`core.autocrlf=false`。
10. **并发构建会互相覆盖同一 `.gba`** ⇒ 你只在**自己的副本**里构建，不要碰共享树的构建产物。
11. **安全策略**：同一条 bash 里 `Set-Location` 后再写入/复制会被拦；`Copy-Item` 也算写
    ⇒ **编辑类操作单独一条命令**（用 Python `shutil`/`Path.write_text`，路径写绝对路径），
    **构建/测试类操作单独一条命令**（先 `Set-Location` 再跑）。

---

## 4. 通用构建 / 验证命令

```powershell
# 构建（WSL，必须导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w20-<流>/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 单测（可传 lane 路径）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Github/gba-naruto/build/w20-<流>/butano-sequel
#   ⇒ 期望 pass=118 / fail=20（20 项预存债，逐名相同即零回归）

# 真实战斗（判据 bee_hp_dropped / from_real_battle / poke_commands=0）
python tools/s49_battle_balance/v1_battle.py --rom <你的ROM> --out build/<流>/run --boot --max-turns 400 --use-tools

# 结算链（真实链；要带全局锁）
python tools/s49_battle_balance/v1_battle.py --rom <你的ROM> --out build/<流>/chain --boot --max-turns 400 --use-tools
```

⚠️ `--use-tools` **只有 D4 修好后才能用**（现在已修好，可用）。

---

## 5. ⚠️ 截断风险（上一波 E1–E4 就是这么丢的）

**运行时可能在任何时刻截断你**（额度/上下文耗尽 ⇒ 状态仍显示 `succeeded`，但笔记没写、代码可能只写一半）。

⇒ **硬性要求**：

1. **你的第一件事就是创建笔记文件**（哪怕只有一个标题 + 一行占位）。
2. **结论增量更新**：每得到一个判定，立刻追加到笔记里，不要攒到最后。
3. **每写完一个可运行的改动，立刻编译一次**，别攒多个改动再编。
4. 笔记里必须有**假设台账**（一行一个假设：判定方法 / 结果 / 状态 = 未验·已证伪·已确认）。
5. **一次只改一处，跑一次，记一行**。**连续 3 次同样结果 ⇒ 停，换方法**。

---

## 6. 文件互斥表（**不许越界**）

| 流 | 独占文件 |
|---|---|
| **E1** | `game/src/battle_runtime_scene.cpp`、`game/include/konoha/battle_visual_resource_coordinator.h` |
| **E2** | `game/include/konoha/battle_action_system.h`、`game/include/konoha/battle_results.h`、`game/include/konoha/battle_scenario_content.h`、`tools/generate_butano_battle_scenario_content.py`、`game/include/konoha/generated_battle_scenario_content.h`、`game/tests/test_battle_experience_award.cpp` |
| **E3** | `game/include/konoha/battle_map_visual_projection.h`、`game/include/konoha/battle_map_content.h`、`game/include/konoha/battle_scene_presentation.h`、`game/include/konoha/battle_original_states.h` |
| **E4** | **不改任何产品文件**；新工具放 `tools/s49_w20e/`；逆向线**只读**；资产清理只在**自己的副本**里做并交清单 |

> ⚠️ 需要改别人的文件 ⇒ **不要改**，写「接线请求」（文件 + 行 + 改成什么 + 为什么）写进你的笔记，交给父代理转交。

---

## 7. 交付物清单（每路都要有）

1. **笔记**：`D:\Github\gba-naruto\notes\s49-fidelity\W20-<流>-<主题>.md`（**先建骨架，后补内容**）
2. **改动**：只在 lane 副本里（父代理负责接线回共享树）
3. **收据/产物**：放 `D:\Github\gba-naruto\build\w20-<流>\` 下（**不进 git**）
4. **一句话结论 + 数字 + 判定表**（写在笔记开头）

---

## 8. 三个口径不许混用（**报告里写错过**）

* **判定台读数**（arg-min 对齐残差）· **可证像素下界**（每拍内全部帧对取最小）· **内容锚可达数**（同一时刻的帧对）
  ⇒ **三个数不是同一个口径**，引用时必须写明是哪个。
* **poked 链 ≠ 真实链**：
  `build/w19-b/chain-final/chain.json` 的 `entry.method` = 「controller state poke」
  ⇒ 那张「48 页逐屏对照表」是 **poked** 的，**不能**写成「真实胜利链」。
* **rom 变了 ⇒ 残差不可比**（退出码 2 = `incomparable`，**不是通过**）。

---

## 9. 验收仪器

* **判定台**（唯一验收仪器）：`python tools/s49_fidelity_report.py --out build/<流>/report.json`
* **12 步流水线**（父代理跑）：`python tools/s49_package/run_pipeline.py --out build/s49-package-w20`
* **原版结算链真值**：`build/s49-victory-capture/w4/settlement-truth/`（9 张图，收据 `9a60a89b…`）
* **逐屏对照**：`python tools/s49_victory_align/align_settlement.py`（sha256 优先配对）

---

## 10. 父代理的收口约定

* **T+75 min**：父代理开始收口 ⇒ 各路笔记必须**已经可读**。
* 接线：父代理用 `tools/s49_wave18/integrate.py`（按 lane 清单拷回共享树 + 检出越界改动）。
* ⚠️ **接线后必须重跑 12 步流水线**（ROM 变了 ⇒ 棘轮会报 `incomparable` ⇒ 需要显式 `--accept-baseline`）。
* 父代理会把各路的「接线请求」统一转交，避免直接改别人的文件。
