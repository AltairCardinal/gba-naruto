# 场景 46 前置剧情恢复点（2026-07-19）

## 当前结论

场景 45 世界地图后的下一主线已自然推进到任务委托人首次发言。稳定恢复点为
`artifacts/runtime-checkpoints/scenario-46-client-dialogue.ss9`，SHA-256 是
`5d50c5fc814471dacec0cb2f132e6fe0a15172373cb634aa225fde10bcf24ca6`。
标准 80 帧零输入复放 run `ac4fa41e596b7f88168348ef807353f9` 成功，峰值 owned-tree RSS
52.85546875 MiB，`pgid_clean=true`。本检查点仍是任务前置对白，不证明场景 46 已进入战斗。

## 自然路线

1. 从 `scenario-45-postbattle-world-map.ss9` 选择默认移动目的地，进入一乐拉面剧情。
2. 完成鸣人与伊鲁卡/手打对白并取得剧情奖励，返回木叶地图。
3. 再选择火影办公室，完成第七班、卡卡西与三代火影的任务分级说明和 D 级任务简报。
4. 当前画面已出现新委托人并进入其第二句对白；后续直接从正式 checkpoint 继续，不重放此前
   68 个单 A 边界。

## 超时与恢复

- 从 `dialogue-a67-zero.ss9` 用 300 帧单输入 runner 发送 A，两次都在约 20–23 秒触发
  `idle-timeout`；两次峰值 RSS 约 52.2 MiB，均由进程组守卫清理，无新 macOS mGBA
  崩溃报告、无 crash latch、无进程残留。
- 同一输入改为 80 帧捕获后成功，画面进入委托人下一句对白；再从该短帧状态做 80 帧零输入
  复放也成功。因此输入和游戏状态有效，失败边界是该场景在长捕获期间超过 15 秒没有 runner
  可观察进度，不应误报为 mGBA 崩溃。
- 后续在这段对白使用 80 帧检查点，并在跨场景后重新校准；不得简单取消 idle timeout。

## 下一步

从正式 checkpoint 继续委托人对白，遇到任务标题、编队或可操作地图时固化下一检查点；
减少截图展开，只在状态类型变化时检查画面，以控制 Codex 桌面渲染内存和上下文体积。

## 编队检查点续进（16:21–16:32）

- 从 `scenario-46-client-dialogue.ss9` 继续 68 个单 A 边界，完整推进达兹纳委托说明、
  第七班争执和出发剧情，最终进入“队伍・装备”编队界面。
- 该段统一使用 80 帧单输入检查点；`build/scenario-46-resume-20260719` 共 69 份含正式
  零输入复验的 audit，全部 `success=true`、`pgid_clean=true`，最高 owned-tree RSS
  52.4140625 MiB。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-46-lineup.ss9`，SHA-256
  `e91f1a72b59d6ee00e180818d9aa51679525c6fff13b9147f893fc97667c10a3`；80 帧零输入
  run `be4c7240ba89e8d936f997d55b0087b8` 成功，峰值 RSS 52.08203125 MiB。
- macOS mGBA crash report 仍为 25，未生成 crash latch，检查点结束后无 mGBA 进程残留。
- 下一轮直接从编队检查点选择“开始任务”并建立场景 46 可操作地图快照，不再重放本页记录的
  前置对白。

## 战斗起点检查点续进（16:36–16:45）

- 从编队页按 B 返回任务报告，依次选择“开始任务”并确认“是”，自然进入桥面战斗；这条路线
  没有使用内存写入、诊断 ROM 或自动输入脚本。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-46-battle-start.ss9`，SHA-256
  `eb5aa8b7887213a033b7b0e8886db2973fa76c7f360a373335aec7b719a8e3dd`。它由转场稳定状态再做
  80 帧零输入复放产生，run `8412352950a045e015b56636b31d6a0f` 成功，峰值 owned-tree RSS
  52.11328125 MiB，`pgid_clean=true`。
- 画面持续显示桥面上的三名角色和部署选择标记。离线 savestate 检查确认 task 2 resume 为
  `0x08073616`、battle ID 为 9、地图运行时尺寸为 `64×64 / 16×32`、结果 byte 仍为 0；
  后续单 A 实验确认这里仍是逐单位部署确认，不是玩家回合，因此不得把该画面冒充玩家控制。
- 后续直接从该检查点确认玩家行动菜单和本关胜负条件；每次只提交一个显式输入，并保留零输入
  对照，不再经过委托对白、编队和任务报告菜单。

## 玩家回合检查点续进（16:47–16:54）

- battle 9 的静态 formation variant 0 是 3 名玩家单位加 5 只猫。运行时从部署起点依次确认
  鸣人、佐助、小樱和五个敌方单位后出现“开始”，与该 8 条 active formation 记录一致。
- 战斗开始后的四个单 A 边界完成佐助与小樱的战前对白，随后鸣人画面出现“SELECT 详细”；
  再输入一个 A 后稳定打开鸣人的六项行动菜单，明确证明玩家控制已经接管。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-46-player-action-menu.ss9`，SHA-256
  `859ee3b54faa413d8e3f7a2cbbf428bb02b48a8174ba6337e0021d5cb006a8e1`。80 帧零输入复放
  run `cf2a64cbb1ab443a319dee0db5132427` 成功，峰值 owned-tree RSS 52.13671875 MiB，
  `pgid_clean=true`；task 2 resume 为 `0x08067D02`，battle ID 9、地图尺寸和未决结果 byte
  均保持不变。
- 该检查点证明可恢复的玩家行动菜单，但尚未证明 MOVEDONE、敌方阶段、胜利、EXP、升级或
  postbattle。后续应从这里选择移动或攻击，先定位本关胜负条件和最短自然通关路线。
