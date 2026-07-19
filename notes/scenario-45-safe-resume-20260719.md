# 场景 45 安全恢复记录（2026-07-19）

## 安全基线

- 恢复前 macOS 中已有 25 份 `mGBA-*.ips`；本轮所有固定 runner 完成后仍为 25，没有新增崩溃报告。
- 峰值 owned-tree RSS 约 51.9–52.7 MiB；每个最终 audit 均记录 `pgid_clean=true`、`mgba_listener_clean=true`。
- `tools/run_guarded.py` 已接入危险 Lua 扫描与 crash-report latch；临时脚本中的 `os.exit` 会在 mGBA 启动前失败关闭。
- 后续每次 mGBA runner 单独一个工具调用；返回后单独检查 audit、PGID、监听、崩溃报告与 latch，不在一个 shell 中串联多个模拟器运行。

## 已推进结果

输入基线：

- `build/scenario-45-round2-naruto-melee-20260719/pulse-11.ss9`
- SHA-256：`82bed2b973c1aa4a062b6176831ca13c384ed7907e2c097b8e2aa47b5434ff12`

安全重放与鸣人攻击：

1. `zero-80.ss9` 证明原快照零输入稳定。
2. A 确认近战后，卡卡西从 100/100 降至 87/100，鸣人保持 109/109；本次自然近战伤害为 13。
3. 完成朝向与默认“不使用防御”确认，切换到小樱。
4. 小樱本回合已无法移动/攻击，安全结束其行动并完成朝向/防御确认，切换到佐助。

佐助状态：

- `build/scenario-45-safe-resume-20260719/sasuke-tech-back.ss9`：佐助行动菜单，SHA-256 `0051cd623c72d24b1ac31997c7f23db8d3d6c9e81b1c5439dda63bcfc1fbd25a`。
- 火遁术参数：伤害 15×1、距离 2、范围 1、命中率 95%、查克拉消耗 2。
- 火遁未进入目标执行，原因是佐助与卡卡西当前距离约 3；已取消选择并返回行动菜单。
- `build/scenario-45-safe-resume-20260719/sasuke-move-open-short.ss9`：佐助移动网格，SHA-256 `ce14199070eb2ac84f42c3a318ba05fb0ec6b4c1d1e926c52fcacf57d80bd2b0`。

## 输入时序结论

- 菜单→子界面使用 8 帧 A 会跨状态重复消费；1 帧 A（frame 5→6）只打开移动网格。
- 行动菜单刚恢复时，frame 5→13 的方向脉冲可能落入输入锁；frame 40→48 可稳定改变菜单行。
- 移动网格中 1/8 帧方向输入只改变面对/指向，不能保证走格；不能把“状态哈希变化”误判为有效移动。
- 岩石右侧黄色格不可达；从当前网格应复用历史 `scenario-45-sasuke-advance-end-20260719` 的长按走格模式，先到青色目的格，再用 1 帧 A 打开确认。

## 下一步

1. 从 `sasuke-move-open-short.ss9` 进行一个变量的长按 Up 校准，目标是实际进入岩石上方青色格；失败即回到同一快照，不沿错误分支累积。
2. 靠近到火遁距离 2 后选择火遁，完成目标与命中结算。
3. 每次有效攻击后建立零输入稳定快照，记录卡卡西 HP；重复自然回合直到场景胜利并固化场景 45 持久证据。

## 安全整改后续推进（13:28–13:36）

- 首次真实运行被 Lua 门禁安全拒绝，原因是错误字符串中的普通单词 `load` 被当作动态加载调用；mGBA 未启动。策略现先剥离 Lua 字符串与注释再检查代码，并新增固定单输入 runner 的预检回归。
- 后续所有真实运行均为 `completed/0`，峰值 owned-tree RSS 为 51.9–52.4 MiB，PGID 与监听残留检查全通过；crash report 始终为 25，latch 未出现，持久 baseline 已建立。
- 移动网格的正确语义已确认：方向输入选择橙色目的格，A 才执行整段移动；不是按住方向直接走格。`Up` 选中原地，`Down → Right → Right` 是绕过岩石的本轮可达终点，第三次 Right 会越界切换到敌方单位查看。
- 已从第二次 Right 的目的格确认移动。新恢复点为 `build/scenario-45-safe-resume-20260719/sasuke-move-drr-confirm.ss9`，SHA-256 `6aa4fcad670ddf377699888374994888782f99c4ab09b392d4b3dec6e6cfb772`；佐助已移动到卡卡西近旁并返回行动菜单。
- 从该行动菜单执行 `Down → A` 会打开“结束行动？”确认框，并非忍术菜单；`sasuke-postmove-tech-open.ss9` 只作为错误分支证据。下一次应从 `sasuke-move-drr-confirm.ss9` 校准其他菜单方向，不从确认框继续。
