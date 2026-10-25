# S49 逻辑状态一致性检查（stream C）

这一套脚本把「游戏逻辑状态与原版一致」这一条**逐条变成可判定的红绿**。

## 一条命令

```powershell
cd D:\Github\gba-naruto
$env:PYTHONIOENCODING='utf-8'
python tools\s49_logic_checks\record_evidence.py   # 先录证据
python tools\s49_logic_checks\run_all.py            # 再出红绿表
```

`run_all.py` 的退出码：

| 码 | 含义 |
|---|---|
| 0 | 全部绿 |
| 1 | 有红（未通过） |
| 2 | 缺输入（检查根本没跑起来） |
| 3 | 无红，但有灰（无法判定） |

优先级是显式的：缺输入 > 红 > 灰。

## 脚本

| 脚本 | 作用 |
|---|---|
| `record_evidence.py` | 用无头 mGBA 探针录下本机证据（原版长/短两段走位、重制走位、待机扫描、调色板探针、EWRAM 单位池、像素基准） |
| `check_original_equivalence.py` | 本机重录的原版 == macOS 录制的原版？（四个独立基准） |
| `check_battle_roster.py` | battle 14 名册：原版内存 ↔ 重制侧数据表，逐槽逐字段 |
| `check_rule_standby_state.py` | 状态栏 結束 / 待機 切换时机 |
| `check_rule_ai_facing.py` | AI 移动后的朝向 |
| `check_rule_move_grid.py` | 移动网格的染色规则（覆盖层） |
| `check_rule_idle_sequence.py` | 单位待机帧序与相位 |
| `check_rule_fbff.py` | 0xFBFF 损坏终止符的缺陷语义 |
| `run_all.py` | 跑全部，出一张红绿表 |
| `s49_logic_common.py` | 共用的路径、区域表、覆盖层统计、状态字分类 |

## 产物

* 收据：`build/s49-logic/receipts/*.json`（每条都有判定依据、原版值、重制值、差异）
* 录制：`build/s49-logic/{original-walk,original-walk-long,remake-walk,original-idle-sweep,roster-pool,field-frame,field-frame-step23,palette-probe}/`

## 与重制线五个测量器的关系

重制线的 `measure_s49_rule_*.py` 是**只读参照**：本目录没有改动重制线里的任何文件。
移植时改掉的地方（以及为什么）写在 `notes/s49-fidelity/C-logic-state.md` 的
「改了什么」一节里。核心的一条：重制线那五个测量器用**帧序号**定位画面
（`step-18-A.png` / `step-19-A.png`），而本机与 macOS 的走位不是同一条路径，
所以这里改成**按测量定位画面**。

## 依赖

* `build/mgba-probe/mgba-probe.exe`（无头 mGBA 探针）
* `recomp/bios/gba_bios.bin`（真实 BIOS，重制侧录像需要）
* 重制线 `D:\Shell\Github\gba-naruto-butano`（只读）
* 逆向线 `D:\Shell\Github\gba-naruto-reverse`（只读）
* Python 3.14 + Pillow
