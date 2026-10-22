# 非伤害敌方效果命中门闭环（2026-07-26）

## 纠错结论

Butano 此前只让 damage family 消费动作成功率与 RNG。状态和 `effect 0x3F` 即使模板成功率
低于 100，也会无条件写入目标。这样会把金缚术的 85%、动作 23 的 70%、动作 24 的
75% 和动作 31 的 95% 都错误实现成必中。

当前共享 resolver 已把敌方非伤害效果接入与原 ROM 相同的“逐 hit 结果 → 至少一击有效
才分派 handler”门。未命中仍是一次合法动作：成本已消费、角色已行动，但目标状态、
reaction state 和属性不变。

## 原 ROM 静态证据

机读绑定仍由 `tools/analyze_battle_damage_hit_formula.py` 和
`notes/battle-damage-hit-bindings-20260723.json` 维护：

- `0x08076034` 的逐 hit 生成器先按事件成功率抽取 15-bit RNG；
- `0x08076E0A..0x08076E3C` 扫描当前 event 的 hit 结果，只有至少一项有效才设置队列局部
  effective 标志；
- `0x08076EEC..0x08076F24` 在跳转表分派前两次检查该标志；没有有效 hit 时直接跳过
  handler；
- effect `0x3F` 的跳转表项指向 `0x0807755C`，该 handler 只以目标槽和常量 `0x30`
  调用 `0x0806A8C0`；
- 因为 effective-hit 门位于 effect code 跳转表之前，它不仅约束 damage handler，也约束
  `0x0E/0x0F/0x21/0x3F` 等非伤害 handler。

对应 ROM 字节窗口由分析器逐字节验证；原始自然十字手里剑 checkpoint 当前不在工作树，
所以依赖它的动态重建测试按既有 durable-evidence 策略跳过，静态 ROM 门和持久 binding
仍可验证。

## 受影响的正式主动动作

| 动作 ID | effect | 模板成功率 | 当前行为 |
|---:|---:|---:|---|
| 23 | `0x0E` | 70% | miss 不写 `0x0E/0x3E` |
| 24 | `0x0F` | 75% | miss 不写状态或 reaction state |
| 31 | `0x21` | 95% | miss 不写防御降低 |
| 80（金缚术） | `0x3F` | 85% | miss 不写 reaction state `0x30` |

命中率继续使用已闭合的
`min(99, template_rate + trunc((source_agility-target_agility)/2))`，每个 hit 消费一次
`(rng_u15 × 100) >> 15`。范围效果对每个目标分别解析；任一目标的失败不会伪造其他目标
的状态。

## 实现边界

- 只对目标策略为 opponent 的 status / reaction-state family 应用该门；友方强化、治疗、
  召唤和资源动作不凭本次证据增加失败概率；
- handler 仍只在至少一个 hit 有效时执行一次，符合原 ROM “扫描 hit 结果后分派一次”
  的队列结构；
- action 80 的模板 duration 为 2，但 `0x0807755C` 本身不建立状态槽；当前只复现已证实
  的 reaction-state 写入，不把 duration 猜成禁行回合数；
- 专属 miss 动画、文本和声音未由本次领域修复闭合。

## TDD 与验证

`test_battle_effect_handlers` 先用固定 seed 1585 产生 85% 门外的随机值并失败于“金缚术仍
写入 0x30”；最小实现后：

- action 80 预览显示 85%，miss 产生 `generated_hits=1/effective_hits=0`，目标保持不变；
- action 23 预览显示 70%，miss 不建立 `0x0E` 或联动 `0x3E`；
- 既有命中、状态容量回滚、AI area、全动作和可见场景测试保持通过。

最终验证：

- 77/77 宿主 C++ 程序通过：
  `build/resource-guard/butano-nondamage-accuracy-full-host-20260726-15.json`；
- 分析器、内容生成、mGBA 脚本与文档共 74 项 Python 测试通过，原始自然 checkpoint
  缺失的一项按 durable-evidence policy 跳过；
- 固定 devkitARM Docker 构建成功：
  `build/resource-guard/butano-nondamage-accuracy-arm-build-20260726-16.json`；
- 静音 mGBA 路线在 frame 2791 完成 battle 41→43→9、角色动作、召唤、五敌行动与
  round 2，活动单位 9：
  `artifacts/butano-nondamage-accuracy-runtime-20260726-03/audit.json`；
- ROM/ELF SHA-256 分别为
  `51b952ae721464d8cb6dae6bfff61b63b22b0c343f9c1d4cce5f61e56d1624e3` /
  `45dfc74dc698c371830e58a7405d5623d775de1d7072c67a10fc04bff7f1ac78`；
- `rom/base.sav` SHA-256 保持
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。
