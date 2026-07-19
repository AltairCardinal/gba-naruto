# 场景 46 后下一主线入口（2026-07-20）

## 当前边界

- 从 `artifacts/runtime-checkpoints/scenario-46-postbattle-world-map.ss9` 恢复后，世界地图标题为
  “木叶之里”。选择主菜单默认“移动”，再确认地点列表默认项，进入卡卡西在室内说明下一任务的
  对白。
- 当前只证明场景 46 后的下一段主线剧情已经可达；尚未看到任务编号、胜负条件或战斗地图，
  因此“场景 47”仅作为连续工作编号，不把它写成已确认 battle ID。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-intro-kakashi.ss9`，SHA-256
  `73d56ff495f80a583bd179d3f8def8bc34693c3e0e2e3241fb281885d89f0cf7`。80 帧零输入恢复 run
  `6317d082a3713058bce3652e8e4e15c9` 成功，峰值 owned-tree RSS 51.859375 MiB，
  `pgid_clean=true`。
- 后续从该对白快照继续，不重放场景 46 战斗与结算；自然完成任务并累计等级，直到 Naruto
  达到 LV8 或首次出现 secondary level 激活，再恢复 `levels` consumer 观测。

## 资源状态

- 本段 mGBA 全部经 heavy guard 串行执行，启动前后无 mGBA 残留。
- 建立快照时系统可用内存为 66%；此前整段场景 46 与入口运行期间 crash report 保持 25。
