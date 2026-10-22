# Consumer stride derivation: the cross-load pairing bug

**Date:** 2026-10-21
**Tool:** `tools/consumer_locate.py` (fixed this cycle)
**Evidence file:** `notes/evidence/consumer-evidence.json` (regenerated; still the
**54-table audited subset**)
**Related:** `notes/evidence/legacy-rebase-nearby-20261020.md` §1.2 recorded the
bug (it was found by `tools/legacy_rebase.py`, which re-derived the stride with a
symbolic pass of its own).

---

## 0. Summary

| | before | after |
|---|---|---|
| `0x545068` `per_character_skills` | stride **180** | stride **16** |
| `0x5459C8` `character_perks` | stride **63** | stride **12** |
| evidence file SHA-256 | `5ffc647d247fc239ebc27382a4c05191bbeff1ce646d2ffe17856cabdbeb3b8c` | `95b94975a6e7256ca2a3e0577f6680e7174621f7992fe371764113b2e183f7da` |
| tables in the evidence file | **54** | **54** (same key set, none added, none dropped) |
| `rom_sha256` in the evidence file | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` | **unchanged** |
| consumer entries whose stride changed | — | **123** |
| tables whose *first* consumer stride changed | — | **21** |

---

## 1. The bug

`tools/consumer_locate.py` used to derive the element stride of a table with a
**function-wide pattern search**: it scanned every instruction of the enclosing
function for a `mov #imm` / `mul` pair (`_detect_element_stride`) and, failing
that, for an `add` whose source register happened to be the register the literal
load had written into (`_detect_stride`).

Both shapes break as soon as **one function reads two tables** — the norm in this
ROM — because the search is not scoped to the reader:

```
0806D974  ldrb     r2, [r6]          ; r2 = the character index
0806D97E  movs     r0, #0xb4         ; 180            <-- belongs to the TEMPLATE load
0806D980  adds     r1, r2, #0
0806D982  muls     r1, r0, r1        ; r1 = 180*index
0806D984  ldr      r0, [pc, #0xc]    ; 0x0854241C  (character template)  <-- reader A
0806D986  adds     r1, r1, r0        ; sb = template + 180*index
0806D988  mov      sb, r1
0806D98A  lsls     r1, r2, #4        ; r1 = 16*index
0806D98C  ldr      r0, [pc, #8]      ; 0x08545068  (per-character skills) <-- reader B
0806D98E  adds     r1, r1, r0        ; r8 = 0x545068 + 16*index
0806D990  mov      r8, r1
```

The `movs r0,#0xb4` + `muls r1,r0,r1` pair sits **two instructions before**
reader B, so reader B (`0x545068`) was reported with stride **180** — the stride
of the *other* table in the same function.  The same class of failure produced
stride **63** for `0x5459C8`, where `movs r0,#0x3f` at `0x0806D718` is the
**bit mask** `r3 & 0x3F` and not a stride at all.

Two further symptoms came from the same unscoped scan:

* the literal pool of a function decodes as garbage code, so a scan that walks
  forward into the pool reports phantom usages (e.g. `0x5450E8` was reported as a
  "compare" because the `cmp r1,#0xbc` it found was really the pool word at
  `0x0806D9A8`), and readers that sit **after** a pool were never analysed at
  all;
* the base pointer is routinely **copied** (`mov r8, r0`), so a scan that only
  looks at the load register loses the consumer.

---

## 2. Root cause

The stride was derived by a *function-wide* pattern search instead of by
following the **loaded base's own dataflow**, so an immediate that belonged to a
*different* load in the same function could be paired with this load's
arithmetic — and because a bit mask is also a `mov #imm`, the mask `0x3F` was
mistaken for a stride.

---

## 3. The fix

`tools/consumer_locate.py` now re-derives the stride with a small **symbolic
dataflow scoped to the reader** (the approach of `tools/legacy_rebase.py`,
ported in; `legacy_rebase.py` itself is untouched):

1. **Symbolic register values.**  Every register is tracked as
   `const + Σ(atoms[a] · scale)`.  The base pointer is seeded at the reader
   instruction; the pending power-of-two scale is what lets the idiom
   `lsls #0x18` / `lsrs #0x14` be recognised as "multiply the index by 16"
   instead of destroying the index.
2. **The immediate must meet the base.**  An immediate only becomes a stride
   when it is combined with the register that holds the base (or a copy of it).
   An immediate that is never combined with the base's register cannot
   contribute, and a mask (`ands r0, r3, #0x3f`) destroys the value it masks,
   so it can never be mistaken for a stride.
3. **Literal pools are filtered out of the instruction stream.**  The pool words
   are found from the pc-relative loads that read them and skipped; the scan
   re-syncs right after a pool, so a reader that sits after a pool is analysed
   like any other one (this is what makes the `0x0809AAC6` sound-table reader
   analysable at all).
4. **Base-pointer copies are tracked** (`carriers`), so `mov r8, r0` keeps the
   base alive.
5. **The address is the *sum* of both add operands**, and an add *chain*
   (`adds r0,r0,r1` then `adds r3,r3,r0`) refines the classification, so a
   two-dimensional access (`base + row*204 + column*68`) stays visible instead of
   being truncated to the first add.
6. **The Thumb-1 two-operand form** `adds Rd, #imm` no longer clobbers the base
   (it used to destroy the pointer in `0x0806A830`, which hid the ×144 stride of
   the sprite-action table).
7. **The derived slots are cross-checked.**  The constants that the function
   installs into the base-carrying register are attributed as `base + k*stride`;
   a wrong stride would leave them unattributed.

### 3.1 The evidence file is pinned to the audited subset

`--all` scans "the registry **plus** the built-in `AUDIT_TABLES` list".  The
registry grew during this session (60 entries, 9 of them outside the audited
subset: `audio_song_1/2/8/11/14`, `sprite_frame_descriptors`, `unit_delta_table`,
`battle_encounter_records`, `item_skill_records`), so `--all --evidence` would
have silently widened the evidence file from **54 to 63 tables**.  The evidence
file is *defined* as the audited subset (the completion audit's `codecite` /
`notatable` probes are derived from it), so `--all` now pins the evidence file
to `AUDIT_TABLES` and the registry still only affects the `--json` report.

---

## 4. Before / after stride table

The **first** consumer of every table, as the completion audit reports it
(`consumers[0].stride`):

| table | name | stride before | stride after | after: `usage_detail` |
|---|---|---:|---:|---|
| `0x0808136C` | mechanism_effects | None | **4** | `base + 4*idx` |
| `0x080815E4` | pickup_dispatch | 234 | **4** | `base + 4*idx` |
| `0x08348DAC` | mission_index | None | **1** | `base + 1*idx` |
| `0x08465B70` | sound_id_table | 76 | **8** | `base + 8*idx` |
| `0x0853D910` | map_table | None | **32** | `base + 32*idx` |
| `0x0853DF70` | legacy_cutscene_scripts | 1 | **8** | `base + 8*idx` |
| `0x0853F298` | legacy_units | None | **2** | `base + 2*idx` |
| `0x0854241C` | character_template | 188 | **180** | `base + 180*idx` |
| `0x08545068` | per_character_skills | 180 | **16** | `base + 16*idx` |
| `0x08545458` | skill_table | None | **16** | `base + 16*idx` |
| `0x085459C8` | character_perks | 63 | **12** | `base + 12*idx` |
| `0x085461C4` | battle_actors | None | **6828** | `base + 6828*idx + 2276*idx` |
| `0x08596CCC` | sprite_action_table | None | **144** | `base + 144*idx` |
| `0x0859903C` | background_table | 4 | **16** | `base + 16*idx` |
| `0x08599280` | character_names | None | **4** | `base + 4*idx` |
| `0x08599634` | ninjutsu_names | None | **4** | `base + 4*idx` |
| `0x0859AA5C` | mission_title_table | None | **4** | `base + 4*idx` |
| `0x0859D214` | mission_description_table | None | **4** | `base + 4*idx` |
| `0x0859E920` | mission_hint_table | None | **4** | `base + 4*idx` |
| `0x0859EAE0` | reward_table | None | **24** | `base + 24*idx` |
| `0x085A4DEC` | portrait_table | None | **40** | `base + 40*idx + 8*idx` |

The other 33 tables keep their first-consumer stride (`None`, or a value that
did not change).  The tables whose first consumer still reports **no** stride
are the ones whose first consumer is *not* an indexed access at all — a plain
dereference (`story_before_root`, `story_after_root`, `legacy_save_state`,
`material_names`), a fixed offset (`story_logic_root` `base + 4`,
`story_events_root` `base + 0`, `map_object_table` `base + 0`,
`font_segments` `base + 0` — a linear search whose loop counter the linear pass
cannot follow), or a store (`legacy_resource_pointers`).

### 4.1 The two mis-derivations, corrected

| table | reported stride | **true stride** | true reader |
|---|---:|---:|---|
| `0x545068` (`per_character_skills`) | 180 | **16** | `0x0806D98C` (fn `0x0806D964`) |
| `0x5459C8` (`character_perks`) | 63 | **12** | `0x0806D6E6` (fn `0x0806D6B8`) |

---

## 5. Falsifiable tests

Every test below is a **command that can fail**: if the tool regresses, the
command prints a different (or no) stride.  The second column of each pair is
the *independent* ROM-level evidence that would still hold if the tool were
wrong, so the two can be compared.

| # | command | expected output | independent ROM evidence |
|---|---|---|---|
| T1 | `python tools\consumer_locate.py rom\base.gba --target 0x545068` | `reader 0x0806D98C ... usage=indexed base + 16*idx stride=16` | `0806D98A lsls r1,r2,#4` + `0806D98E adds r1,r1,r0` ⇒ ×16; the same function's pool slots `0x085450E8 = base + 8*16` and `0x08545158 = base + 15*16` |
| T2 | `python tools\consumer_locate.py rom\base.gba --target 0x5459C8` | `reader 0x0806D6E6 ... stride=12` | `0806D6E0 lsls r0,r1,#1` + `0806D6E2 adds r0,r0,r1` + `0806D6E4 lsls r0,r0,#2` ⇒ (2+1)×4 = 12; `movs r0,#0x3f` at `0x0806D718` is the mask `r3 & 0x3F` |
| T3 | `python tools\consumer_locate.py rom\base.gba --target 0x54241C` | `reader 0x0806D984 ... stride=180` | `0806D97E movs r0,#0xb4` = 180; pool slots `0x085429BC = base + 8*180` and `0x08542EA8 = base + 15*180` |
| T4 | `python tools\consumer_locate.py rom\base.gba --target 0x545458` | `reader 0x0806D866 ... stride=16` | 16-byte ninjutsu record (`notes/character-template-format-20261020.md`) |
| T5 | `python tools\consumer_locate.py rom\base.gba --target 0x5461C4` | `reader 0x0806DF28 ... usage=indexed-2d base + 6828*idx + 2276*idx stride=6828` | `0x00001AAC` = 6828 (column) and `0x000008E4` = 2276 (row) are literal constants of the same function |
| T6 | `python tools\consumer_locate.py rom\base.gba --target 0x594758` | `reader 0x080751AA ... usage=indexed-2d base + 204*idx + 68*idx stride=204` | `080751B6 movs r1,#0xcc` = 204 |
| T7 | `python tools\consumer_locate.py rom\base.gba --target 0x465B70` | `reader 0x08061E3A ... stride=8` | 159 entries × 8 bytes (`notes/alias-conflicts-20261020.md` §4.3) |
| T8 | `python tools\consumer_locate.py rom\base.gba --target 0x596CCC` | `reader 0x0806A826 ... stride=144` | `0806A82A lsls r0,r1,#3` + `0806A82C adds r0,r0,r1` + `0806A82E lsls r0,r0,#4` ⇒ (8+1)×16 = 144 |

One-liner form (fails loudly when the stride is wrong):

```powershell
python tools\consumer_locate.py rom\base.gba --target 0x545068 | Select-String 'stride=16'
python tools\consumer_locate.py rom\base.gba --target 0x5459C8 | Select-String 'stride=12'
python tools\consumer_locate.py rom\base.gba --target 0x54241C | Select-String 'stride=180'
python tools\consumer_locate.py rom\base.gba --target 0x545458 | Select-String 'stride=16'
python tools\consumer_locate.py rom\base.gba --target 0x5461C4 | Select-String 'stride=6828'
python tools\consumer_locate.py rom\base.gba --target 0x594758 | Select-String 'stride=204'
python tools\consumer_locate.py rom\base.gba --target 0x465B70 | Select-String 'stride=8'
python tools\consumer_locate.py rom\base.gba --target 0x596CCC | Select-String 'stride=144'
```

### 5.1 The four derived literal slots of fn `0x0806D964`

The function loads two bases and four *derived* slots.  The tool attributes
each slot to the base it belongs to (the reader's own evidence lines):

| slot | attributed to | multiplier | ROM check |
|---|---|---:|---|
| `0x085450E8` | `0x08545068` | `8 × 16` | `0x085450E8 - 0x08545068 = 0x80` |
| `0x08545158` | `0x08545068` | `15 × 16` | `0x08545158 - 0x08545068 = 0xF0` |
| `0x085429BC` | `0x0854241C` | `8 × 180` | `0x085429BC - 0x0854241C = 0x5A0` |
| `0x08542EA8` | `0x0854241C` | `15 × 180` | `0x08542EA8 - 0x0854241C = 0xA8C` |

```powershell
# the CLI prints only the first three evidence lines, so the slot check reads
# the evidence file itself
Select-String -Path notes\evidence\consumer-evidence.json -Pattern 'slot 0x085450E8 = base \+ 8\*16'
Select-String -Path notes\evidence\consumer-evidence.json -Pattern 'slot 0x08545158 = base \+ 15\*16'
Select-String -Path notes\evidence\consumer-evidence.json -Pattern 'slot 0x085429BC = base \+ 8\*180'
Select-String -Path notes\evidence\consumer-evidence.json -Pattern 'slot 0x08542EA8 = base \+ 15\*180'
```

> **Correction to the briefing.**  The briefing gave the multipliers as
> `14×16` for `0x5450E8` and `48×180` for `0x542EA8`.  Those two products do
> not land on the stated addresses: `0x545068 + 14×16 = 0x08545148` (not
> `0x085450E8`) and `0x54241C + 48×180 = 0x085445DC` (not `0x08542EA8`).  The
> ROM says **8×16** and **15×180**; the two other multipliers of the briefing
> (`15×16` for `0x545158`, `8×180` for `0x5429BC`) are correct.  The tool
> derives all four from the ROM, so the note follows the ROM.

---

## 6. Reproduction commands

```powershell
# regenerate the evidence file (54 audited tables; deterministic)
python tools\consumer_locate.py rom\base.gba --all --evidence notes\evidence\consumer-evidence.json

# the eight audited strides
python tools\consumer_locate.py rom\base.gba --target 0x545068
python tools\consumer_locate.py rom\base.gba --target 0x5459C8
python tools\consumer_locate.py rom\base.gba --target 0x54241C
python tools\consumer_locate.py rom\base.gba --target 0x545458
python tools\consumer_locate.py rom\base.gba --target 0x5461C4
python tools\consumer_locate.py rom\base.gba --target 0x594758
python tools\consumer_locate.py rom\base.gba --target 0x465B70
python tools\consumer_locate.py rom\base.gba --target 0x596CCC

# the regression suite
python -m unittest discover -s tests -p 'test_*.py'      # 84 tests, OK
python tools\automated_test.py                           # 28/28
python tools\completion_audit.py --check                 # exit 0
python tools\alias_audit.py rom\base.gba                 # RESULT: OK
python tools\writeback_paths.py rom\base.gba             # all cases pass
```

---

## 7. What was *not* closed

* `notes/evidence/consumer-evidence.json` still stores **one** `stride` per
  consumer (the dominant coefficient).  A two-dimensional access keeps both
  coefficients in `usage_detail` (`base + 6828*idx + 2276*idx`), but the JSON
  schema was **not** extended with a `strides` array — that would change the
  file's schema, and the brief asked for the stride/classification fields only.
* The `font_segments` table (`0x53D644`) still has **no** stride on its first
  consumer: that reader is a linear search whose index is a loop counter, and a
  linear dataflow pass cannot see the back edge.  Its second consumer
  (`0x08065EE6`) is a fixed `base + 4` offset.  The table's real 8-byte stride
  is documented elsewhere, not derived here.
* `tools/legacy_rebase.py` was **not** modified (it is another agent's file).
  It keeps its own symbolic pass, so its output is independent of this fix.
