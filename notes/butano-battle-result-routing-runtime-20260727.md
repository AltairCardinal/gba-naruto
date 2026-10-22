# Butano 战斗结果协议与战役事务边界（2026-07-27）

## 结论

本轮修复了一个会让通用战斗域重新退化成“选项跳场景”的生产旁路：

- 旧 `battle_runtime_scene_exit` 只有 `back/next_battle`；
- SELECT 可在战斗尚未结束时直接返回 `next_battle`；
- `run_battle_scene` 无论胜利、失败还是中途退出都会把场内 progression 和忍具消耗
  merge 回 campaign；
- `main.cpp` 忽略 battle 41 的返回值并无条件进入固定 43→9→11→32 夹具链。

现在可见场景只返回四种领域结果：

```text
aborted   START 撤退或场景装载失败
victory   controller complete + outcome win
defeat    controller complete + outcome loss
draw      controller complete + equal-slot result
```

SELECT 已完全移出生产战斗输入。只有 `victory` 允许：

1. 把场内角色成长与忍具消费提交回 campaign；
2. 保存 SRAM；
3. 进入后继战斗。

失败、平局和撤退使用保守回滚策略，不提交场内成长或消耗。原作是否在失败时保留某类消耗
尚无运行证据，因此不得在没有证据时扩大写入范围。

## TDD

红灯：

- `test_battle_runtime_result` 因结果协议头不存在而编译失败；
- Python wiring 测试同时抓到 `allow_next_battle`、SELECT gate、complete→back、
  无条件 campaign commit 和无条件夹具入口；
- 原动作训练测试证明动作 15/51/56 在 `0→1` 时返回 `not_trainable`。

绿灯：

- `battle_runtime_result.h` 固定 outcome→exit、commit 和 advance 真值表；
- complete 页 A 从 `battle_scene_snapshot::outcome` 生成结果，表现层不写胜负；
- `run_battle_scene` 只在 victory 事务中 commit；
- 主程序和后继夹具只消费 `battle_runtime_exit_advances_campaign`；
- 原 ROM 训练函数只按槽增加等级，并不检查数值成长字段；因此主技能训练不再把
  `upgrade_rule{0,0}` 当成不可训练。角色 2 槽 8/动作 15、角色 14 槽 5/动作 51、
  角色 16 槽 7/动作 56 均已通过 progression→unit→catalog 正式链。

## 验证

- 全量 game host C++：通过；
  `build/resource-guard/20260727-battle-result-routing-full-host.json`
- 结果 wiring：5/5 通过；
  `tests/test_butano_battle_result_routing_wiring.py`
- 固定 devkitARM 构建：通过；
  `build/resource-guard/20260727-battle-result-routing-arm-build.json`
- battle 41 四回合胜利、150 EXP、升级、动作 8 修炼和 verified SRAM：
  `artifacts/butano-battle-result-routing-20260727-01/audit.json`
- SELECT 运行时负证据：frame 144 前后均为 battle 41、phase 1、round 1，
  controller/player error 0：
  `artifacts/butano-battle-result-routing-select-20260727-01/audit.json`
- SELECT 探针 guard：
  `build/resource-guard/20260727-battle-result-routing-select-mgba.json`

最终产物：

- ROM SHA-256：
  `bc9fb4fccfd716e3225e7329a0b5c4017f45289dae00c21a7a33b252755eb7c7`
- ELF SHA-256：
  `b010e6ee83097a5f3f1eb7b3cd4a3fff3642f659f41c3f3605e3a822a98359f3`
- exact ELF telemetry：
  `konoha_battle_runtime_telemetry=0x0201FD54`，
  `konoha_battle_campaign_runtime_telemetry=0x02005C80`。

## 边界

这次闭合的是“单场战斗结果 → campaign 事务 → 后继入口”的所有权，证明关卡不能再由隐藏
SELECT 选项推进。当前 43→9→11→32 仍是开发夹具序列，不是完整章节脚本；完整 56 项章节
表的生产 orchestrator、失败后的原作 UI/重试策略、逐技能专属表现和当前禁用的 WAV SFX
仍未完成，完整战斗 Goal 保持进行中。
