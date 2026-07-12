# Skill template UI/runtime probe (2026-07-12)

## Corrected static chain

The real table is file `0x545BE4..0x5461C3`, 94×`0x10`. Initializer
`0x0806D910` computes `base + skill_id*16`, but the old bank description was
off by one: source `+0` is copied to runtime `+1`, source `+1` is skipped, and
source `+2..+9` copy to matching runtime offsets. Runtime `+0` is fixed to 5;
`+A/+C/+E` are cleared. Source `+A/+B` are not unused tails: separate code at
`0x0808FF7C/0x0808FF88` consumes them. The generator and bank now encode these
exact destinations while retaining legacy column names for DB compatibility.

Naruto's initial primary skill IDs are 2, 5 and 7. Skill 2 is file `0x545C04`,
raw `0100010206035a830200010300000000`.

## UI route and observed labels

From the reconstructed prebattle character submenu, a long Down moved to the
third item, one Up selected the second item, and A opened the skill list. The
detail panel visibly contains chakra cost, distance, range and success-rate
labels; this proves the player UI exists, but not which ROM byte supplies each
number.

Control result/screenshot SHA-256:

- `6d284c6f2d293b197d7adcdbd2c6bdfcc86fca4f615497cc47310d72daae1e1d`;
- `588dbe7acd0f4ce5baa8ace5c3a3bb625bc3f28ee78e56f737df88cd05547241`.

## Rejected shortcuts

`tools/build_skill_runtime_probe.py` hooks `0x0806D916` and records only skill
ID 2 initializations. Neither strict battle arrival nor opening the prebattle
skill list hit this initializer, so those routes cannot upgrade `skills` to
runtime evidence.

The same-state ROM A/B for skill 2 `+4: 6→7` did not change the right-side UI
numbers; pixel differences were confined to the animated list cursor. Further
single-byte `+0/+2/+5/+6` trials likewise changed no numeric region. The
checkpoint therefore contains data cached before the edited ROM byte is read,
and these are rejected UI A/B attempts rather than negative field semantics.

The browser bridge exposes `_readGbaByte` but not `_writeGbaByte`; a proposed
post-load memory patch failed explicitly with `mGBA writeGbaByte hook
unavailable`. That unsupported runner feature was removed instead of being
committed as a test-only success.

## Next acceptance gate

Keep `skills` at `code_verified`. The next valid route must either:

1. naturally trigger skill ID 2 through `0x0806D910`, then compare control
   source `0x545C08=6` with a changed-ROM value 7 at the captured runtime
   destination `+4`; or
2. hook the skill-detail reader itself, capture the selected skill ID/source
   pointer and the exact source offsets used for chakra cost/distance/range/
   success rate.

Only after a visible or behavioral A/B may fields such as power or hit rate be
named. The value-domain guess that source `+6` resembles accuracy remains a
hypothesis, not bank metadata.
