# 场景 43 自然推进与战斗生存证据（2026-07-18）

## 结论

从场景 42 的 accepted 世界地图快照自然进入下一任务，击倒三名 50 HP 敌人并完成全部战后剧情。结果页给出 155 经验，Naruto **LV2→LV3**，训练点变为 2；稳定模板为 level 3、EXP 0，24 个 secondary level byte 仍全部为 `FF`，所以 levels 继续保持 `code_verified`。

新的恢复点是 `artifacts/runtime-checkpoints/scenario-43-postbattle-next-task-prompt.ss9`，SHA-256 为 `55375b7736481505dc68cdfe774e1182d90ea77d31264d7be10c80279a978ce9`。immutable base ROM 的 512 帧零输入运行 `8c004d133c217788ab5d71326edb4fd2` 已验证该状态可恢复；task 2 resume 为 `0x08092FCE`，RGB hash 为 `d57e39a268fe602010467cb904bfb2076331003dcc75e97ae9d774febb5d66df`。

## 战斗机制

- 三名敌人的初始坐标为 `(2,11)`、`(4,10)`、`(6,11)`，HP 均为 50；Naruto 初始为 `(4,17)`、HP 94。
- 三名敌人分别在 unit record 仍保存 2、5、8 HP 时进入击倒状态，随后记录 character ID 清零。此任务同样不能把 HP 必须为 0 当作胜利门槛。
- **影分身**会创建第二条玩家阵营 Naruto unit record；召唤者被击倒后，分身仍可接管并继续行动。
- 行动菜单的**休息**一次恢复 **18 HP**。实测 6→24，随后承受敌方攻击变为 15；因此与相邻近身攻击交替，可形成稳定生存循环。
- 忍具攻击会消耗有限库存，耗尽后不能继续选择；后半程使用近身攻击与休息，不依赖修改内存或诊断 ROM。

## 资源与证据边界

所有 mGBA 运行都经过同一 heavy guard，正式零输入复验峰值 52.125 MiB；本轮批量导航最高峰值为 **107.64453125 MiB**，未发生内存异常。部分 Lua `os.exit` 清理仍可能在所有预定快照写完后触发 mGBA 崩溃；这些批量状态只作导航，最终 publication 由标准零输入 runner 独立验证。

levels 的第一个 type-4 row 仍要求 LV8。当前只到 LV3，且 secondary active count 仍为 0；下一主线从新 checkpoint 直接开始下一任务，继续自然升级，不回放场景 43。
