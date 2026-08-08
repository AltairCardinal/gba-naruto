# 战斗特效受控 phase 覆盖扩展（2026-08-09）

## 结论

`artifacts/battle-effect-controlled-runtime-v1` 的原始归档已重新导出并由
`tools/verify_battle_effect_controlled_runtime.py` 独立验证。Group
6/7/8/9/10/12/13 均包含稳定目标 task 的 renderer、submit、ack 三阶段状态，
因此可计入“精确 phase 已验证”；聚合覆盖由 10/18 提升为 17/18。

这些组的入口是受控 sequence injection，不是自然玩法。聚合结果通过独立字段
`controlled_phase_extension_group_ids` 保存该边界，不改变 production pixel A/B
或 natural gameplay 的分子。当前唯一尚无正向三阶段事务的是 Group 15。

## 复核证据

- controlled runtime：13 个 case，10 个正向、3 个负向；正向组为
  4/6/7/8/9/10/12/13/16/17；25 个 OAM binding。
- Group 6 具体链：sequence 8，definition `0x08343700`，animation
  `0x0834375C`，目标 task 在 renderer/submit/ack 三阶段稳定为 slot 108。
- 聚合 verifier：phase 17/18、production pixel A/B 12/18、errors 0。

## 可复现命令

```bash
python3 tools/verify_battle_effect_controlled_runtime.py \
  artifacts/battle-effect-controlled-runtime-v1
python3 tools/verify_battle_effect_observed_frame_phases.py \
  --root . --artifact artifacts/battle-effect-observed-frame-phases-v1
```

## Group 6 自然入口对照

使用正确 mGBA 和 `scenario-50-battle-15-escort-12hp-player-turn.ss9` 进行 600 帧
零输入观测，`0x0807C93C` 命中 0 次；守卫正常完成，峰值 RSS 66.0 MiB。该结果只
排除这个快照上的零输入自然命中，不影响已验证的受控 phase，也不证明其他剧情
路线不可达。
