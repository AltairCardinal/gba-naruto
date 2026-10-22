# Scenario 41 原作截图等价矩阵（2026-07-29）

## 目的与证据边界

本矩阵只跟踪“护送木叶丸逃离野蜂”这一关，不把其他关卡的共用能力算作完成。
原作权威集合固定为 34 个稳定边界：

- 战前菜单 6 张：
  `artifacts/scenario-41-prebattle-reference-v1/screens/`
- 战斗主流程 6 个 `.ss9` GPU 边界：
  `artifacts/scenario-41-reference-v1/`
- 战斗交互 8 个 `.ss9` GPU 边界：
  `artifacts/scenario-41-combat-reference-v1/`
- 战后扩展 14 个 `.ss9` GPU 边界：
  `artifacts/scenario-41-extended-reference-v1/`

GPU 边界以 manifest 的 `screen.rgb_pixels_sha256` 和
`artifacts/runtime-checkpoints/scenario-41-<boundary>.ss9` 为权威。
现有离线渲染器可像素精确重建其中 26/28 个边界；`level-up-1/2`
启用了 WIN0，当前派生 PNG 忽略窗口裁剪，因此这两项必须直接以 `.ss9`
内嵌屏幕或修正后的窗口渲染结果为准。

Butano 当前战斗交互签发基线为
`artifacts/butano-battle-ui-projection-20260729-37/`，
ROM SHA-256 为
`df122cf1be57703276a76cd7cfda43fc4b52d5ef48b7543555cb27d0b46e8774`。
守卫以 `done.json` 为成功标记正常退出，完整执行到 round 4、动作 5 和真实胜利条件，
控制器/玩家错误均为 0。该路线不继续结果与 campaign 保存；完整 campaign 保存证据仍
保留在 `20260729-09`，但其 ROM 已被当前交互基线取代，不能代表当前构建。音频在自动
截图中静音，因此这些产物都不签发音频等价。

状态定义：

- **等价**：同一用户状态、功能事务和视觉均已对照签发。
- **部分**：真实运行时状态已存在，但功能步骤、构图、资源、文字或时序仍有差异。
- **缺失**：没有同一 ROM 的可操作状态或截图证据。

当前没有任何一项达到“等价”；这能避免把“有截图”误报为“已复刻”。

## 34 个稳定边界

| # | 原作边界 | Butano 证据 | 状态 | 当前差异/下一验收条件 |
|---:|---|---|---|---|
| 1 | `menu-0` | `preparation-menu-0.png` | 部分 | 任务说明、胜败条件、菜单和游标已按状态动态绘制；仍缺黄色内沿/编织纹，底部失败条件的原作裁剪未复现。 |
| 2 | `menu-1` | `preparation-menu-1.png` | 部分 | 游标状态真实；结构差异同上。 |
| 3 | `menu-2` | `preparation-menu-2.png` | 部分 | 游标状态真实；结构差异同上。 |
| 4 | `menu-3` | `preparation-menu-3.png` | 部分 | 游标状态真实，储存走验证后的 SRAM 写入；结构差异同上。 |
| 5 | `confirmation-yes` | `preparation-confirmation-yes.png` | 部分 | 提示、是/否、游标和弹窗遮盖层级均由当前状态正确绘制；黄色内沿、编织纹与原作仍不同。 |
| 6 | `confirmation-no` | `preparation-confirmation-no.png` | 部分 | 选择状态与遮盖层级真实；框体纹理差异同上。 |
| 7 | `player-turn` | `move-ui.png` | 部分 | 可移动范围由 pathfinder 当前状态投影；移动区使用原作青色 12/16 混合，行动单位按完整 160px 视口居中并在地图边缘夹取。底栏已恢复原作 7px 编织上下沿、18px 内容区、橙色体力/绿色查克拉渐变和 40px 资源条；顶部英文操作提示、范围格内纹理与少量字形色值仍不同。 |
| 8 | `first-turn-technique-menu` | `actions.png` | 部分 | scenario 41 只暴露真实可用动作 5；名称、成本、威力、距离、范围、成功率和说明均来自当前动作定义。战斗信息使用独立小字形，不再沿用剧情 8×16 字形导致超框；整屏矩形和分隔线由 32×32 动态 BG 的 8 个逻辑 8bpp tile 组成。图标与编织纹细节仍未等价。 |
| 9 | `first-movedone-facing` | `facing.png` | 部分 | 技能、资源命令与行动结束均进入真实朝向阶段，方向键同步更新单位与头顶四向指示，A 才提交；底部状态栏已替换为原作同坐标的“请选择人物面对的方向”说明框，顶部英文调试提示已删除。编织纹和箭头资源仍未等价。 |
| 10 | `turn-1-complete` | `turn-1-complete.png` | 部分 | 第一回合敌方 settle 后，原 ROM selector 2 在第 2 回合玩家侧真实触发；头像、焦点、说话者姓名、编码正文和 A 推进均由脚本状态驱动。对白窗由 4 个无文字 60×63 切片组成，不再把文字压在地图上；边框编织纹与精确色值仍不同。 |
| 11 | `victory` | 无当前 ROM 截图 | 缺失 | Run35 遥测证明真实目标引擎到达 outcome，但未捕获胜利画面，不能用旧 ROM 的通用完成面板签发；仍需原作全屏“胜利”演出。 |
| 12 | `postbattle` | 无当前 ROM 截图 | 缺失 | 旧 ROM 曾证明 campaign 保存并进入 scenario 42，但当前基线未运行结果链，且用户可见出口不是原作木叶世界地图。 |
| 13 | `action-menu-0` | `action-menu-0.png` | 部分 | 移动前 5 项命令由真实 command access 生成，游标与单位层级可见；字形细节、边框纹理与原作不同。 |
| 14 | `action-menu-1` | `action-menu-1.png` | 部分 | 确认移动后真实收缩为“术·忍具/行动结束”两项；字形细节、边框纹理与原作不同。 |
| 15 | `target-select` | `target.png` | 部分 | 攻击范围来自当前动作射程，使用原作橙色覆盖；合法目标继续由 `target_legal()` 计算，并以更亮目标格和真实光标共同反馈。当前证据在光标到达活动敌人且遥测确认目标后采集，不再是刚进入阶段的初始光标。范围格内纹理与顶部提示仍不同。 |
| 16 | `attack-confirmation` | `attack-confirmation.png` | 部分 | 已恢复独立无副作用确认事务；框体可见范围精确为 x=80..159、y=24..87，文字坐标对齐，地图/HUD 仍不等价。 |
| 17 | `end-confirmation` | `end-confirmation.png` | 部分 | 行动结束先进入独立“可以吗？”是/否事务；确认前单位位置、行动完成标记和 player flow 均不提交，否/B 返回命令菜单。框体可见范围为原作 x=80..159、y=24..87，边框色纹仍不同。 |
| 18 | `defense-confirmation` | `defense-confirmation.png` | 部分 | 已恢复“使用防御・回避系的术・忍具吗？”动态是/否流程；默认“是”进入现有防御动作浏览器，“否”才结束单位回合，B 返回朝向。四个合法 64×64 OBJ 合成原作 x=64..175、y=24..103 的 112×80 框体，边框纹理仍未等价。 |
| 19 | `combat-dialogue` | 无同态截图 | 缺失 | 动作 5 演出已运行，战斗后的原作对白稳定态未签发。 |
| 20 | `combat-popup` | 无同态截图 | 缺失 | 当前没有原作同构的战斗后地图弹窗。 |
| 21 | `result` | 无当前 ROM 截图 | 缺失 | 旧 ROM 曾证明真实结算总经验 150，但 Run35 未进入结果链；原作角色、分项和构图尚未签发。 |
| 22 | `level-up-1` | 无当前 ROM 截图 | 缺失 | 旧 ROM 曾证明鸣人升级到 LV2，但 Run35 未进入升级页；原作参考必须按 WIN0 正确渲染。 |
| 23 | `level-up-2` | 无第二页 | 缺失 | 缺少原作第二成长页及完整属性变化。 |
| 24 | `postbattle-dialogue-1` | 无 | 缺失 | 缺少战后 presentation-script 入口。 |
| 25 | `postbattle-dialogue-2` | 无 | 缺失 | 同上。 |
| 26 | `postbattle-dialogue-3` | 无 | 缺失 | 同上。 |
| 27 | `postbattle-dialogue-4` | 无 | 缺失 | 同上。 |
| 28 | `postbattle-dialogue-5` | 无 | 缺失 | 同上。 |
| 29 | `postbattle-dialogue-6` | 无 | 缺失 | 同上。 |
| 30 | `postbattle-dialogue-7` | 无 | 缺失 | 同上。 |
| 31 | `postbattle-dialogue-8` | 无 | 缺失 | 同上。 |
| 32 | `postbattle-dialogue-9` | 无 | 缺失 | 同上。 |
| 33 | `postbattle-dialogue-10` | 无 | 缺失 | 同上。 |
| 34 | `postbattle-dialogue-11` | 无 | 缺失 | 同上；完成后还必须回到原作世界地图出口。 |

## 34 项之外但必须完成的动态流程

稳定截图集合没有覆盖全部动画/取消分支，以下仍是功能等价的必要条件：

- 鸣人、木叶丸亮相，“开始”标题、黑场、五页战前对白及手里剑转场。
- 玩家/敌方阶段横幅和敌方移动仍缺完整视觉等价；敌方发起决斗的共享构图规则已经固定为
  玩家在左朝右、敌人在右朝左。`20260729-37` 的确定性路线与既有 combat trace 证明 scenario 41
  当前确定性路线的敌方三轮只产生地图移动、combat stage 始终为 complete，因此没有
  可签发的敌方决斗截图；不得用玩家攻击截图替代。
- 移动中镜头、范围展开/收缩、各层 B 取消、非法输入反馈。
- 防御术/忍具列表的原作视觉、实际防御准备和资源消耗。
- 忍者组合拳 264 帧时间轴、战斗弹窗、胜利到结算的动态过渡。
- 结果数字累加、两页升级、11 页战后对白和世界地图转场。

任何一项只有 host 测试、领域状态或旧 ROM 截图时，都不能替代当前 ROM 的 mGBA
运行时签发。
