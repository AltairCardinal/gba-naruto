# 全动作生产语义 sweep（2026-07-27）

## 目的

旧 `test_battle_all_actions_runtime.cpp` 已经能把 76 个角色模板主动动作、battle 8 自然
提供的动作 62，以及忍具 1–93 送入正式 preview/resolver，但只断言 `success`、生命周期、
`acted` 和忍具消费。这样的测试仍可能放过“命令成功、业务状态完全不变”的空实现。

本轮没有增加第二套测试 resolver，而是在同一生产入口后按
`effect_resolver_registry::handler_for()` 检查权威领域后果。

## 可达性复核

fail-closed 的 `tools/analyze_battle_action_reachability.py` 重新执行通过，87 个主动身份全部
有明确分类，`unclassified_action_ids=[]`：

- 27 个 `base_catalog`；
- 8 个 `base_level_unlock_then_training`；
- 2 个 `base_training`；
- 1 个 action 19 `scenario_unlock_then_training`；
- 39 个 `formation_catalog`，包括 battle 8 的 action 62；
- 5 个组合结果 10/11/13/17/18；
- 1 个 action 20 独立结印资源命令身份；
- 3 个全零、无 primary 引用的身份 39/40/52；
- 1 个 ID 0 哨兵。

因此早期“20 个 state 0 动作永久不可达”和“action 62 是内部测试动作”的结论均已被取代。

## 新增的逐 handler 后果门

每个非空、自然来源定义在 `success()` 之外还必须满足：

| handler | 必须观察到的领域后果 |
|---|---|
| damage | preview 伤害、有效命中、实际伤害与 damage step 均非零 |
| summon / variant / pair | `summoned` 且数量严格为 1/1/2 |
| move | 起点、终点不同且 `moved=true` |
| identity transform | 身份前后不同、写入链接身份 |
| heal percent | preview 与实际治疗均非零 |
| status | 至少一条实际状态写入 |
| linked cleanup | 至少一个真实链接单位被清理 |
| restore HP/chakra | 状态、治疗和查克拉三者均变化 |
| type 1 / type 2 object | 分配出非哨兵对象槽 |
| chakra restore/reduce | `chakra_delta` 非零 |
| reaction state | 状态写入且 reaction 确实变化 |
| no effect | 只允许 action 9；其生产语义由强制组合 flow 覆盖 |
| unimplemented | 立即失败 |

所有忍具还必须清除准确的 battle-local 工具槽。五个组合结果继续由正式组合事务测试检查，
不是伪造成五个独立菜单项。

## TDD 发现

首轮新断言在 action 80 失败：

```text
generated=3 / effective=3 / applied_status_count=3 /
reaction_state_changed=true
```

失败原因是测试错误要求 `applied_status_count == 1`。原动作是三段命中，每次有效命中都
计一次 status apply；status store 对同 code 执行 upsert，而 reaction byte 只从旧值改变
一次。因此正确契约是 `applied_status_count > 0` 且 reaction 改变。生产实现没有为迎合
错误断言而修改。

修正测试后，76 个角色模板动作、formation action 62 和 93 个忍具全部通过逐 handler
后果门。结合五个组合事务，覆盖全部 82 个非零主动动作定义和 93 个非空忍具定义。

## 验证

- reachability/progression Python：5/5；
- 聚焦 C++ semantic sweep：通过；
- 全部宿主 C++：94/94；
- guard：
  `build/resource-guard/butano-all-action-semantic-sweep-host-20260727-01.json`，
  exit 0，peak tree RSS 164.996 MiB；
- `git diff --check`：通过。

本轮只加强测试和持久证据，生产 ROM 没有改变，继续复用上一里程碑已经验证的 exact
devkitARM/mGBA 产物：

- ROM：
  `30719ed9750b832d6136967deeefad200101138d107fff186b1eb577c613aecd`
- ELF：
  `2a67a2367d09d8c6763efbe57a790a14e8986827fd1006f56bd5f061fffbc0d4`
- 静音 mGBA：
  `build/butano-passive-action-modifiers-runtime-20260727-01/`

## 边界

- 39/40/52 的 16 字节模板全零且没有 base/formation primary 引用；不能为了“87 个都能
  点击”而捏造效果。它们的非命令用途仍需调用点或自然录像证据。
- 本 sweep 证明数值/状态领域后果，不证明每个技能的专属逐帧表现、图标和音效。
- mGBA 证据明确静音，不能签发用户报告的音频撕裂修复。
- 完整战斗 Goal 仍 active。
