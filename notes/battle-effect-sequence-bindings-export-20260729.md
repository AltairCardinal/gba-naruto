# 战斗特效 sequence 映射全量导出（2026-07-29）

## 结论

原 ROM 已闭合两张相连的静态表：

- `0x0853E596`：256×1 字节 runtime-state → sequence selector，SHA-256
  `4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b`；
- `0x0853EF30..0x0853F140`：22×24 字节 sequence descriptor，SHA-256
  `04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f`。

selector 的前 87 项与 active action 0..86 按同一 action ID 静态连接；该切片
SHA-256 为
`373b8c02a0e768f15843be31a3f1282346986fd9bb52584be5649e3f01696b22`。
这不是从 action template 的 `display_animation_family` 或其他字段推导出来的：
action ID 同时索引 `0x08545458 + id*16` 的 template，并经 event `+0x0C` 复制到
runtime state `+0x770`，再索引 `0x0853E596 + id`。

selector 的 `0x80..0xDD` 还与 94 个 ninja tool ID 0..93 完整连接：动作构建器
以 bit 7 区分忍具，低 7 位索引 `0x08545BE4 + ninja_tool_id*16`，但写入 event
`+0x0C` 的仍是保留 bit 7 的原始 action byte；该值经 runtime state `+0x770`
索引 selector。因此 encoded action `0x80|ninja_tool_id` 与 selector 索引严格相同。
该 94 项切片 SHA-256 为
`7b329765f680d1638a5899bfa67b3501e8c32cda6399a83b38ef88b35c21cfb4`，
忍具模板表 SHA-256 为
`e586bbeeb364a14639e5062491c26c163905cb4c5501985bbafb5ed0ba3cd0fd`。

完整成果位于 `artifacts/battle-effect-sequence-bindings-v1/manifest.json`，包含：

- 256/256 runtime-state selector 条目；
- 87/87 active-action → sequence → descriptor 映射；
- 94/94 ninja-tool → encoded action → sequence → descriptor 映射；
- 22/22 descriptor 的四个 resource-group 槽和两个回调指针；
- 全 ROM 67 个 selector 直接调用点，其中 66 个是立即数 sequence，唯一动态调用
  `0x0807C602` 来自 sequence binder。

## Descriptor schema

| Offset | Type | 语义 |
|---:|---|---|
| `+0x00..+0x0C` | `u32[4]` | resource-group ID；0 表示结束/空槽 |
| `+0x10` | Thumb pointer | init-once callback；调度器调用后清零 |
| `+0x14` | Thumb pointer | tick callback；每次调度调用 |

当前 ID 0 全零；ID 1..21 都只使用第一个 resource-group 槽，后三槽全零。非零组号
均在 1..18，直接连接已导出的
`artifacts/battle-effect-resource-pairs-v1/group-XX-atlas.png`。所有非零回调都是
ROM 内 LSB=1 的 Thumb 指针。

| Sequence | Group | Init once | Tick | Active action IDs |
|---:|---:|---|---|---|
| 0 | 0 | `0` | `0` | 41 项，见 manifest |
| 1 | 1 | `0x08080555` | `0x0808055D` | — |
| 2 | 2 | `0x08080661` | `0x08080671` | — |
| 3 | 3 | `0x08080661` | `0x08080765` | — |
| 4 | 4 | `0x080808BD` | `0x080808C5` | — |
| 5 | 1 | `0x080808BD` | `0x080808C5` | — |
| 6 | 5 | `0x080808BD` | `0x080808C5` | 37 项，见 manifest |
| 7 | 18 | `0x080808BD` | `0x080808C5` | — |
| 8 | 6 | `0x080808BD` | `0x08080915` | — |
| 9 | 7 | `0x080808BD` | `0x08080915` | — |
| 10 | 8 | `0x080808BD` | `0x080809F5` | — |
| 11 | 9 | `0x080808BD` | `0x08080915` | — |
| 12 | 10 | `0x080808BD` | `0x080808C5` | — |
| 13 | 11 | `0x080808BD` | `0x080808C5` | — |
| 14 | 12 | `0x080808BD` | `0x080808C5` | 32 |
| 15 | 13 | `0x080808BD` | `0x080808C5` | 61, 76, 77 |
| 16 | 14 | `0x080808BD` | `0x08080915` | 16, 17, 18 |
| 17 | 15 | `0x080808BD` | `0x080808C5` | 64, 65 |
| 18 | 18 | `0x08080661` | `0x08080815` | — |
| 19 | 16 | `0x080808BD` | `0x080809F5` | — |
| 20 | 17 | `0x080808BD` | `0x080809F5` | — |
| 21 | 2 | `0x080808BD` | `0x08080965` | — |

## 边界证据

- selector `0x0807FE58..0x0807FE60` 计算 `sequence_id*24` 后加
  `0x0853EF30`；
- 最高立即数调用为 `0x0807ED2E movs r0,#0x15` →
  `0x0807ED30 bl 0x0807FE2C`；
- ID 21 恰好结束于 `0x0853F140`；
- `0x0853F140` 起是另一张指针表，首值 `0x0812F5B0`，由
  `0x08080B12` 通过独立 literal 引用；
- selector 本身没有 sequence/group 上界检查，导出器和 verifier 显式限制
  sequence `<22`、group `<=18`。

## 可复现性

```sh
python3 tools/export_battle_effect_sequence_bindings.py \
  --root . \
  --output-dir artifacts/battle-effect-sequence-bindings-v1
python3 tools/verify_battle_effect_sequence_bindings.py \
  --root . \
  --artifact-dir artifacts/battle-effect-sequence-bindings-v1
python3 -m unittest tests.test_export_battle_effect_sequence_bindings
```

独立 verifier 不导入 exporter 或其他 `tools.*`，自行扫描 Thumb BL、解析两张表并
重建完整 manifest。生产验证为 256/256 runtime-state、87/87 active-action、
94/94 ninja-tool、22/22 descriptor，`errors=[]`。最终导出耗时 1.67 秒，最大
RSS 24,096,768 字节，无 swap。

## 尚未闭合

本成果闭合完整 256 项 raw selector，并闭合两个已识别动作域（87 个 active action
和 94 个 ninja tool）→ sequence → 静态 resource group 和回调指针身份，同时证明
init-once/tick 的调度角色；剩余未识别 selector 值只保留原始映射，不额外赋予动作
语义。它不等于完整动画：

- tick callback 内部逐帧脚本格式仍待批量解析；
- OAM 组件、位置、翻转、优先级和 frame hold 尚未全量闭合；
- blend/palette transform 与音频绑定尚未全量闭合；
- sequence 0 只能确认是可接受的全零记录，不额外宣称其用户语义。
