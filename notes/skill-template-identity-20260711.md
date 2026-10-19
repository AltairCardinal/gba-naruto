# Skill template identity correction（2026-07-11）

The former `skills@0x546100` bank was a misbased 12-record tail slice. A range
pointer scan found six aligned literals targeting `0x08545BE4`, including the
literal at `0x0806D960` used by `0x0806D910`.

`0x0806D916` computes `skill_id<<4`, adds `0x08545BE4`, and copies record bytes
`+0..+9` into the caller's runtime skill structure. It initializes runtime
`+0x0A/+0x0C/+0x0E` separately. The physical region ends exactly at the proven
positions base:

```text
0x5461C4 - 0x545BE4 = 0x5E0 = 94 * 0x10
```

Therefore the corrected structure is 94×16-byte skill/technique templates at
file `0x545BE4..0x5461C3`. `tools/extract_skill_templates.py` performs lossless
extraction. Player-facing meanings for the ten copied bytes and six tail bytes
remain unproved, so legacy semantic editor import/write stays disabled.

The former `items` bank was byte-for-byte identical to the old skills slice and
has no independent consumer. It is now a `disproved` tombstone rather than a
second static-verified structure.
