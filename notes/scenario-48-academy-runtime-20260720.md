# battle 13 后学院剧情与世界地图恢复点（2026-07-20）

## 路线与边界

- 从 `artifacts/runtime-checkpoints/scenario-47-battle-13-postbattle-world-map.ss9` 恢复，在
  “木叶之里”选择默认“移动”，地点列表选择“学院”，立即进入 Sakura 对白。
- “场景 48”仅是连续工作编号。本段是学院内的纯剧情，角色包括 Naruto、Sasuke、Sakura、
  第三代火影、Iruka、Kakashi、木叶丸与惠比寿；总计推进 99 页后自然返回世界地图，没有
  进入战斗或任务选择页。
- 本段没有经验结算，等级保持 Naruto LV5、Sasuke LV4、Sakura LV5。后续仍需自然推进主线，
  直到 Naruto 达到 LV8 或 secondary level 首次激活，再恢复 `levels` consumer 观测。

## 恢复点与资源状态

- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-48-post-academy-world-map.ss9`，
  SHA-256 `06096f67f9f93893c6b91a211af6b45e3ef751dd695360301adb3902a881a975`。
- 600 帧零输入恢复 run `fd9eaa9cab6023ec2e165242affedbe2` 成功，
  `zero_input_verified=true`、`pgid_clean=true`，峰值 owned-tree RSS 52.03125 MiB。
- 本段所有输入均经 heavy guard 串行执行，未出现 mGBA 残留或新增崩溃；后续直接从该快照
  选择“演习场”，不再重放学院长对白。
