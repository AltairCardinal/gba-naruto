# Battle reaction family runtime closure — 2026-07-25

## Result

The previously unknown incoming-reaction families are now operationally
closed without assigning unsupported names:

| code | observed incoming-hit policy | range gate |
| --- | --- | --- |
| `0x04` | consume token, cancel the first effective hit and truncate the remaining hits; no movement | Manhattan distance exactly 1 |
| `0x09` | consume token, resolve reverse damage against the attacker, cancel the incoming hit and truncate remaining hits | Manhattan distance no greater than status byte `+3` |
| `0x0A` | consume token, resolve reverse damage against the attacker, then continue the original incoming damage | Manhattan distance no greater than status byte `+3` |
| `0x16` | substitution cancellation/movement only when adjacent | Manhattan distance exactly 1 |
| `0x19` | reverse damage and incoming cancellation only when adjacent | Manhattan distance exactly 1 |

The machine-readable run identities, state hashes, screenshot hashes, patch
bytes, ROM hash, and emulator hash are in
`notes/battle-reaction-family-runtime-20260725.json`.

## Method

The input state was the verified scenario 41 attack-confirmation checkpoint.
Only the defender's eight-byte reaction status record changed between runs.
Each run applied one A press, saved a new state, and then continued from that
exact output state. The original `rom/base.sav` was moved out of mGBA's lookup
path for each isolated run and restored with the same SHA-256 afterward.

The runtime observations were cross-checked against:

- preprocessor `0x080763E0`, including priority and `status+3` range gates;
- shared resolver `0x08076A30`;
- `0x04/0x16` branch `0x08076C44`;
- `0x09` branch `0x08076BA8`;
- `0x0A` branch `0x08076B1E`;
- `0x19` branch `0x08076BCC`.

## Butano architecture consequence

These codes are not separate scenario events. They are one-shot status tokens
selected by the single ROM-ordered incoming-reaction arbiter inside
`battle_action_resolver`. Reverse damage for `0x09`, `0x0A`, and `0x19` uses
one counter handler. The handler returns an explicit flow decision:

- no trigger;
- reverse effect followed by incoming damage;
- cancel all remaining incoming hits.

Presentation receives a `reaction_resolution_event`; it never changes HP,
coordinates, status tokens, or turn state.

## Boundary

This closes the operational damage/continuation semantics and distance gates.
It does not claim a Chinese display name for `0x09`, nor exact audiovisual
timings for any reaction. Those remain presentation/content research rather
than rule-engine behavior.
