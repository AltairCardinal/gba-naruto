# Battle effect template consumer（2026-07-11）

> 2026-07-23 边界纠错：下文“32×16”是被截断的旧结论。表实际连续包含 87×16 字节，ID 0–86 与主动动作文本表和角色 primary 槽一一对应；生成器、bank 和校验器现均使用 87。其余关于 `0x0806D85C`、16 字节复制和等级增长的调用链仍有效。

## Corrected identity

File `0x545458` is not a u16 battle-scenario configuration table. It is a
87×16-byte active-action numeric template table consumed by Thumb
`0x0806D85C`. The actual map/scenario descriptor table remains at `0x53D910`.

The old u16 interpretation paired adjacent bytes and invented
`config_id/param/value/flag` fields. Those names are revoked.

## Code chain

Inputs to `0x0806D85C`:

- `r0`: effect/template ID;
- `r1`: level;
- `r2`: optional downstream target/context;
- `r3`: destination 16-byte runtime effect structure.

At `0x0806D860..0x0806D874`, the function computes
`0x08545458 + effect_id*0x10` and copies exactly 16 bytes to `r3`.
It then reads destination byte `+0x0C` and uses a seven-entry jump table:

| `+0x0C` type | level-growth destination |
|---:|---:|
| 1 | runtime byte `+4` |
| 2 | runtime byte `+5` |
| 3 | runtime byte `+6` |
| 4 | runtime byte `+7` |
| 5 | runtime byte `+8` |
| 6 | runtime byte `+9` |
| 7 | no growth adjustment |

For types 1–6, u16 `+0x0E` is multiplied by `(level-1)` and added to the
selected byte. Twelve callers were found between `0x0806FE36` and
`0x0809280A`; callers consistently supply an effect ID byte, a level byte and
a 16-byte destination embedded in UI/battle working structures.

## Durable changes

- `tools/extract_battle_effect_templates.py` performs lossless extraction of all 87 rows;
- `sequel/content/battle-config/bank.json` now preserves 14 bytes plus the
  proven `growth_target_type` and `per_level_growth` fields;
- `tools/verify_battle_config_records.py` validates the corrected byte layout;
- the bank evidence level is `code_verified`;
- legacy editor `battle_configs` import/write remains disabled because it
  describes map scenarios, not these effect templates.

## Runtime capture and controlled A/B

`tools/build_battle_effect_runtime_probe.py` redirects all twelve consumer
callers to a preserving stub and records the effective ID, level, type, growth
and output bytes `+4..+9` at EWRAM `0x0203FFD0`.

After extending the WASM route past formation preload and the Kakashi dialogue,
the live caller produced:

```text
effect_id=2, original_level=1, type=4, growth=1
output +4..+9 = 00 01 64 03 01 00
```

This exactly matches physical record 2 and proves a real caller. For a strict
field test, the diagnostic stub forced effective level 2 in both variants:

| Variant | ROM record 2 `+0x0E` | scratch | selected output |
|---|---:|---|---:|
| control | 1 | `02020400010000000001640401000000` | `+7=4` |
| changed | 2 | `02020400020000000001640501000000` | `+7=5` |

The only scratch differences are growth (`+4`) and its expected type-4 output
destination (`+11`, representing runtime `+7`).

Artifacts:

- control ROM SHA-256: `880322516572192893efe351e8429342a67f86fe4c36006146ea3214c0eb8511`;
- changed ROM SHA-256: `df1beedc1d2d5901472bbb7773f73853f161aa11b1b17846b87912d677926f7d`;
- control result SHA-256: `f3f23f116ceef16b9ba5c4bf6391dfe7b44e212cf8218708a6fe6e9384497adb`;
- changed result SHA-256: `f65eed995784359bb573b605ce2637587c42d2c19f789cd25a4ceb63b7f1785b`.

The bank is therefore `runtime_verified`. Remaining work concerns player-facing
names for the conservative bytes and safe editor serialization, not table
identity or the type/growth mechanism.
