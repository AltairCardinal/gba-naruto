# 场景 42 自然推进与 levels 前置条件（2026-07-18）

## 结论

- 从场景 41 战后世界地图自然执行“移动 → 演习场”，完成长剧情、编队、教程战斗和结果页；场景 42 胜利后 Naruto 保持 LV2，EXP **0→110**，训练点保持 1。
- 已固化世界地图 checkpoint `artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9`，SHA-256 `35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1`。base ROM 512 帧零输入重放 run `b228217df46280525146b7115c7e1815` 完成，task 2 resume 为 `0x08067D02`。
- 这是真实的主线推进和经验增长证据，但次级槽仍全部为 `FF`；`levels` 继续严格保持 `code_verified`。

## type 4 训练前置条件纠正

全参数确认观测器证明训练确认入口参数为 `r1=0x02022EF0`、`r2=0x02002880`、`r3=selected index`。默认 index 0 是普通训练 row；第一个 **type 4** row 位于 index 8，row pointer `0x020028A0`，8 bytes 为 `03 05 06 04 04 06 01 00`，即 levels ID 1、secondary slot 0。

场景 41 战后 Naruto 只有 LV2，而 index 8 的界面显示需要 LV8，并明确返回当前不可修炼；确认 hook 与 `0x080932CA` consumer 均未命中。因此旧设计中“有训练点即可自然消费 type 4”的假设不成立。必须继续自然升级，不能写内存强制激活，也不能提前做 record `+6` A/B。

## 场景 42 路线与战斗边界

- 世界地图默认“移动”进入演习场；剧情结束后在编队菜单向下两项选择“开始任务”。
- 首回合必须绕开 Naruto 右侧岩石，移动 `Up → Right → Right`；随后距离 3 的术可以命中敌人。
- 敌人贴身后，默认术固定距离 3，必须在术列表向下两项选择距离 1、范围 1 的近战项。
- 教程胜利弹窗出现时，敌人 unit record 仍保存 HP 2；本任务的胜利是脚本判据，不能错误要求 HP 必须为 0。
- 结果页自然写入 EXP 110；reward state SHA-256 为 `e8f950cfe5a69922839f5ee7b1a37901637c80285d1e1f6cb4891105a7a52feb`。

## 批量推进与资源边界

长对话和重复近战使用 build 内一次性 Lua 脚本，每次输入后或每回合结束保存 checkpoint，避免每句对话重启 mGBA。所有运行仍经共享资源守卫串行执行；最大 owned-tree RSS 为 **107.5625 MiB**，没有内存异常。

部分批量轮次在所有 checkpoint 写完后于 Lua `os.exit` 清理阶段触发 mGBA `SIGSEGV`。这不影响已在退出前写完并可离线解析的状态，但退出后的状态不作证据；正式 checkpoint 另用标准 runner 在 base ROM 下做零输入重放。

## 当前边界与下一步

场景 42 只把 EXP 推到 110，尚未达到 LV8，未证明 type 4 确认、`0x080932CA` 命中或 levels record `+6` 因果 A/B。下一步从新世界地图 checkpoint 继续自然主线；到 LV8 或首次自然激活次级槽时，再恢复 levels consumer 观测器。
