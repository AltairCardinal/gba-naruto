# 战斗特效硬编码 selector 生产者（2026-08-02）

## 结论

`0x0807FE2C` 的 67 个调用点由 66 个硬编码 sequence 调用和一个动态调用组成。
批量 CFG 分析把硬编码调用与 `0x0853E698` 的 256 组 primary/secondary handler
逐项关联，同时保留动态 action→sequence 表为独立关系。

Group 2 / sequence 2 的 11 个调用点中，8 个 handler 调用点关联到 13 个主动动作：

| Handler | Pair slot | 主动动作 |
|---|---|---|
| `0x0807E070` | primary | 1 分身术 |
| `0x0807E1C8` | primary | 7 影分身术、50 砂分身、63 水分身术、69/71/73 岩分身术 |
| `0x0807E340` | primary | 33 兽人分身 |
| `0x0807E4C4` | primary | 54 傀儡术 |
| `0x0807E648` | primary | 2 瞬身术 |
| `0x0807E774` | primary | 4 变化术 |
| `0x0807E8A8` | secondary | 22 解 |
| `0x0807EA00` | secondary | 62 雾隐术 |

这 13 个动作在动态 selector 表中的 sequence 都是 0；Group 2 是 handler 内额外
硬编码创建的演出，不得把 `dynamic_action_sequence_id=0` 改写成 action→sequence 2。
`0x0807BB90/0x0807BD70/0x0807C516` 属于未被 handler pair 直接引用的通用演出函数，
继续保持 unresolved。

## 证据与复现

- 生成器：`tools/analyze_battle_effect_hardcoded_selector_producers.py`
- 机读结果：`notes/battle-effect-hardcoded-selector-producers-20260802.json`
- 测试：`tests/test_analyze_battle_effect_hardcoded_selector_producers.py`

```bash
python3 tools/analyze_battle_effect_hardcoded_selector_producers.py \
  --root . \
  --output notes/battle-effect-hardcoded-selector-producers-20260802.json
python3 -m unittest \
  tests.test_analyze_battle_effect_hardcoded_selector_producers -v
```

分析器固定基准 ROM SHA-256，逐行核对 256×8 handler pair 与 ROM 原字节，拒绝非
Thumb 指针；逐个复核 67 个 selector 调用确实 BL 到 `0x0807FE2C`，再从每个 handler
根执行有界 Thumb CFG 可达性分析。输出完整固定四份输入文件哈希。

## 边界与下一步

该结果只证明“运行时 action index 可调度到一个包含 Group 2 固定创建路径的
handler”。它不证明自然输入一定经过 handler 内对应分支，也不证明修改 ROM 后最终
像素。下一步优先复用已验收 battle 15 回合 3 checkpoint，自然选择鸣人的动作 7
“影分身术”，先固化动作确认前检查点，再捕获 handler、selector 和 Group 2 task。
