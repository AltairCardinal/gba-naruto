# Legacy bank rebase: the three `0x5450xx` banks are windows into live tables

**Date:** 2026-10-20
**Scope:** `sequel/content/character-stats`, `sequel/content/character-stats-b`,
`sequel/content/levels` — the three legacy banks whose declared base the ROM
never names.  Bonus: `sequel/content/map-events`.
**Tool:** `tools/legacy_rebase.py` (new, this cycle).
**Evidence file:** `notes/evidence/consumer-evidence.json` (read-only, **not**
regenerated).

---

## 0. The trap this note is about

`notes/evidence/consumer-evidence.json` is the **audited subset** — 54 tables
the completion audit cares about.  The whole-ROM literal index has **18051**
distinct values, **1196** of which point into the ROM image.  Any "which live
literal is near this address?" question answered from the evidence file is
answered from a silently truncated candidate set, and live tables outside the
audit surface (`0x53EE98`, `0x545BE4`, `0x53E698`, …) simply do not appear in
it.

`tools/legacy_rebase.py` therefore builds the **full** index from the ROM
(`tools.consumer_locate.LiteralIndex`) and uses the evidence file for exactly
two things:

1. the `rom_sha256` digest anchor (the tool exits non-zero if it does not
   match the ROM it was handed), and
2. labelling neighbours that happen to sit inside the audited 54-table subset.

---

## 1. Method

### 1.1 Locating the readers

Every live literal in the ROM is found by scanning for pc-relative literal
loads — ARM `LDR Rn,[pc,#imm]`, Thumb-1 `LDR Rt,[pc,#imm]` and Thumb-2
`LDR.W Rt,[pc,#imm]` — and recording the 32-bit value each one reads
(`tools/consumer_locate.py`, `LiteralIndex`).  The pool address is derived
from the instruction encoding, so a reader and the value it loads are tied
together mechanically, not by hand.

### 1.2 Deriving the stride (and why the evidence file's stride is wrong)

`tools/consumer_locate.py` records a stride per reader, but it scans the
**whole function** for a `mov #imm` / `mul` pair.  When two tables are read by
the same function — the norm in this ROM — that pairs the immediate of one
load with the multiply of the other.  Both of the reported strides for our
three banks are wrong for exactly this reason:

| literal | evidence file says | actually is | why the machine got it wrong |
|---|---|---|---|
| `0x545068` | stride **180** | stride **16** | `movs r0,#0xb4` / `muls r1,r0,r1` at `0x0806D97E`/`0x0806D982` belong to the *other* literal load at `0x0806D984`, 2 instructions earlier |
| `0x5459C8` | stride **63** | stride **12** | `movs r0,#0x3f` at `0x0806D718` is the **bit-mask** `r3 & 0x3F`, and the `muls r0,r2,r0` at `0x0806D736` is `level * r4` |

`tools/legacy_rebase.py` re-derives the stride with a small symbolic pass
that runs **from the function start up to and past the reader**, tracking each
register as `const + Σ(atoms[a] · scale)`.  Because the pass is
dataflow-ordered, the immediate of one load can never be attributed to the
multiply of another.  The pending `scale` is what lets the idiom
`lsls #0x18` / `lsrs #0x14` be recognised as "multiply the index by 16"
instead of destroying the index.

Two further details the tool had to get right:

* **Literal pools sit inside functions** and decode as garbage code.  Left in
  the instruction stream they produce phantom `cmp`/`str` usages, so the pool
  words are removed before the analysis runs.  (Before that fix the tool
  reported `0x5450E8` as a "compare" — the `cmp r1,#0xbc` it had found was
  really the pool word at `0x0806D9A8`.)
* **The base pointer is copied** (`mov r8, r0`) and both branches of a
  function then write the same register, so the tool remembers the *carriers*
  of the base rather than only its current holder.

### 1.3 Two-dimensional tables

A table can be indexed in two dimensions at once, and a single "stride" would
hide half the picture.  The `battle_actors` table at `0x5461C4` is read at
`0x0806DF28` as

```
0806DF2C  ldrb r1, [r2, #2]       ; row
0806DF2E  ldr r0, [pc, #0x30]     ; 0x000008E4 = 2276
0806DF30  muls r0, r1, r0
0806DF32  ldrb r2, [r2, #1]       ; column
0806DF34  ldr r1, [pc, #0x2c]     ; 0x00001AAC = 6828
0806DF36  muls r1, r2, r1
0806DF38  adds r0, r0, r1
0806DF3A  adds r0, r0, r3         ; base + row*2276 + column*6828
```

The symbolic pass keeps every index coefficient, so the tool reports
`indexed-2d` with `6828+2276` instead of silently picking one of them.

### 1.4 Confirming a hypothesis

A hypothesis is only accepted when **all** of these hold:

1. the base is a **live literal** — some code loads it (a literal pool value);
2. a **reader** is identified with its function and its instruction;
3. the reader's stride and entry layout are **confirmed by the code** (the
   arithmetic that computes the address, and the field offsets it reads);
4. the **bank's bytes match the ROM byte-for-byte** at the proposed mapping;
5. the table's **extent** ends exactly on the next live literal.

---

## 2. The three banks

### 2.1 `character-stats` — declared base `0x54507A`, 20 × 16 → **CONFIRMED (with a corrected stride)**

**True structure:** per-character growth table, base **`0x545068`**, **63 entries × 16 bytes**.

**Reader:** `0x0806D98C` (Thumb), inside the function at `0x0806D964`.

```
0806D974  ldrb r2, [r6]           ; r2 = template[0x00] = the character index
0806D97E  movs r0, #0xb4          ; 180
0806D980  adds r1, r2, #0
0806D982  muls r1, r0, r1         ; r1 = 180 * index
0806D984  ldr r0, [pc, #0xc]      ; pool 0x0806D994 -> 0x0854241C  (character template)
0806D986  adds r1, r1, r0         ; sb = template + 180*index
0806D988  mov sb, r1
0806D98A  lsls r1, r2, #4         ; r1 = 16 * index
0806D98C  ldr r0, [pc, #8]        ; pool 0x0806D998 -> 0x08545068  <-- the live base
0806D98E  adds r1, r1, r0         ; r8 = 0x545068 + 16*index
0806D990  mov r8, r1
```

**The base is loaded at `0x0806D98C` and indexed with a ×16 stride, not ×180.**
The ×180 stride belongs to the *character template* table at `0x54241C`, read
by the **neighbouring** load at `0x0806D984`.  The briefing's premise — that
`0x545068` is the growth table *with stride 180* — is **refuted on the
stride**; the base it names is correct.

Four independent cross-checks inside the same function confirm the two
strides, because the compiler materialised two *other* table entries as
literal pools:

| pool | value | check |
|---|---|---|
| `0x0806D9AC` | `0x085450E8` | `0x545068 + 14 × 16 = 0x5450E8` ✔ |
| `0x0806DB3C` | `0x08545158` | `0x545068 + 15 × 16 = 0x545158` ✔ |
| `0x0806D9A8` | `0x085429BC` | `0x54241C + 8 × 180 = 0x5429BC` ✔ |
| `0x0806DB38` | `0x08542EA8` | `0x54241C + 48 × 180 = 0x542EA8` ✔ |

**Where the legacy base actually sits.** `0x54507A − 0x545068 = 0x12`, and
`0x12 = 1 × 16 + 2`: the legacy bank starts at **entry 1, byte offset 2** of
the real table.  Its field names are therefore shifted by two bytes, and its
last field (`max_value`) is really the **next** entry's `+0x00`:

| legacy field | legacy offset | real table field |
|---|---|---|
| `char_type` | +0 | `+0x02` of entry *n* |
| `hp` | +2 | `+0x04` of entry *n* |
| `attack` | +4 | `+0x06` of entry *n* |
| `defense` | +6 | `+0x08` of entry *n* |
| `padding1..3` | +8,+10,+12 | `+0x0A..+0x0E` of entry *n* |
| `max_value` | +14 | `+0x00` of entry *n+1* |

**True entry count.**  `0x545068 + 63 × 16 = 0x545458`, which is exactly the
`skill_table` base — a live literal with 8 readers.  And
`0x54241C + 63 × 180 = 0x545068`, so there are 63 character templates and
63 growth records, one per character.

**Falsifiable test.**

> Re-base the bank to `0x545068`, take 63 entries of 16 bytes, and check that
> every bank entry equals the ROM bytes at `0x545068 + 16 × (1 + i) + 2`
> (verified: **all 20 entries match byte-for-byte**), and that
> `0x545068 + 63 × 16 == 0x545458`.
> The hypothesis is **wrong** if the bank bytes instead match the ROM at
> `0x54507A + 16 × i` with *no* shift into a 16-byte table, or if the table
> does not end exactly on `0x545458`.

### 2.2 `character-stats-b` — declared base `0x545200`, 18 × 16 → **CONFIRMED (same table)**

**True structure:** the **same** per-character growth table as 2.1 — base
**`0x545068`**, **63 entries × 16 bytes**.  `character-stats-b` is not a second
table; it is a second *window* into the first.

**Reader:** the same `0x0806D98C`.

**Where the legacy base actually sits.** `0x545200 − 0x545068 = 0x198`, and
`0x198 = 25 × 16 + 8`: the legacy bank starts at **entry 25, byte offset 8** of
the same real table.  Because the window is shifted by 8 bytes instead of 2,
the field order is different — which is exactly what the bank recorded
("different field ordering from the primary character stat table"):

| legacy field | legacy offset | real table field |
|---|---|---|
| `hp` | +0 | `+0x08` of entry *n* |
| `padding1..3` | +2,+4,+6 | `+0x0A..+0x0E` of entry *n* |
| `max_value` | +8 | `+0x00` of entry *n+1* |
| `char_type` | +10 | `+0x02` of entry *n+1* |
| `attack` | +12 | `+0x04` of entry *n+1* |
| `defense` | +14 | `+0x06` of entry *n+1* |

**Entry count.** The bank's 18 entries × 16 = 288 bytes run from real entry
25 to real entry 42 (byte offset 8), i.e. into the part of the table that the
game never populates.  The bank's last entry therefore has
`max_value`/`char_type`/`attack`/`defense` all zero — those four fields are
really **entry 43**'s `+0x00/+0x02/+0x04/+0x06`, and entry 43
(`0x545318`) is zero-filled.  The true count of the structure is **63**.

**Falsifiable test.**

> Re-base to `0x545068` and check every bank entry equals the ROM bytes at
> `0x545068 + 16 × (25 + i) + 8` (verified: **all 18 entries match
> byte-for-byte**).
> The hypothesis is **wrong** if the bytes match a *different* 16-byte table
> (for instance one based at `0x545458`, the `skill_table`), or if no
> ×16-stride table contains `0x545200`.

### 2.3 `levels` — declared base `0x5459D4`, 47 × 12 → **CONFIRMED (and the bank overruns the table)**

**True structure:** the character perks table, base **`0x5459C8`**, **45 entries × 12 bytes**.

**Readers:** six native readers, all with a ×12 stride — `0x0806D6E6` and
`0x0806D786` (function `0x0806D6B8`), `0x0806DB14`, `0x0806DC4C` and
`0x0806DDD6` (function `0x0806D964`), `0x080932CA` (function `0x08093070`).

The stride is computed in the code itself, at **five** independent sites:

```
0806D6E0  lsls r0, r1, #1        ; r0 = id * 2
0806D6E2  adds r0, r0, r1        ; r0 = id * 3
0806D6E4  lsls r0, r0, #2        ; r0 = id * 12
0806D6E6  ldr r1, [pc, #0x20]    ; pool 0x0806D708 -> 0x085459C8
0806D6E8  adds r1, r0, r1        ; r1 = 0x5459C8 + id * 12
0806D6EA  ldrh r0, [r1, #6]      ; per-level gain
0806D6F2  ldrh r2, [r1, #2]      ; base value
0806D6FA  ldrb r0, [r1]          ; perk kind byte
```

**The "stride 63" is a mis-parse**, as explained in §1.2.

**Where the legacy base actually sits.** `0x5459D4 − 0x5459C8 = 0xC` =
exactly **one entry**: the legacy bank starts at **entry 1** of the perks
table, with **no byte skew**.  Its `entry_size` of 12 was already right.

**True entry count — and an overrun.**  `0x5459C8 + 45 × 12 = 0x545BE4`,
and `0x545BE4` is a **live literal with 7 readers** that index it with a
**×16** stride — `0x0806D91A`, `0x08078EF8`, `0x08078F08`, `0x0808FC28`,
`0x0808FF78`, `0x08095394`, `0x080953A4`.  It is therefore a **different
table**, not perks entry 45, and the perks table has exactly **45 entries**
(`0x5459C8 .. 0x545BE3`).

The address coincidence `0x545BE4 = 0x5459C8 + 45 × 12` is the trap here:
`0x545BE4` looks like "perks entry 45" but the code proves it is a 16-byte
table base.  The two readings are distinguishable because the 16-byte table's
entry 1 at `0x545BF4` does **not** satisfy the perk layout (its `+0x06`
halfword is `0x835A` = 33626, where a real perk gain is 1/5/30).

Consequence for the bank: it declares **47** entries, but only 44 of them
(`perks` entries 1..44) are inside the table.  Bank entries 44..46 read the
`0x545BE4` table instead.

**Perk entry layout** (from the code, not from the bank's field names):

| offset | width | meaning | evidence |
|---|---|---|---|
| +0 | u8 | perk kind / id | `ldrb r0,[r1]` then `cmp r0,#0xe` / `#0x10` / `subs r0,#0xd; cmp r0,#6` |
| +1 | u8 | unused | — |
| +2 | u16 | base value | `ldrh r2,[r1,#2]` |
| +4 | u16 | secondary value | `ldrh r1,[r1,#4]` (`0x0806DDF6`) |
| +6 | u16 | gain per level | `ldrh r0,[r1,#6]` |
| +8 | u16 | extra stat | `ldrh r0,[r1,#8]` |
| +10 | u16 | unused | — |

**Falsifiable test.**

> Re-base the bank to `0x5459C8` and check every entry equals the ROM bytes at
> `0x5459C8 + 12 × (1 + i)` (verified: **all 47 entries match byte-for-byte**),
> and check `0x5459C8 + 45 × 12 == 0x545BE4` where `0x545BE4` is read with a
> ×16 stride.
> The hypothesis is **wrong** if `0x545BE4` turns out to be read with a ×12
> stride (which would make the perks table 46+ entries), or if the bank bytes
> match a table with a different entry size.

### 2.4 Summary

| bank | declared base | declared count × size | **true base** | **true count × size** | reader | verdict |
|---|---|---|---|---|---|---|
| `character-stats` | `0x54507A` | 20 × 16 | **`0x545068`** | **63 × 16** | `0x0806D98C` | confirmed, stride 180 **refuted** → 16; window = entry 1 + 2 bytes |
| `character-stats-b` | `0x545200` | 18 × 16 | **`0x545068`** | **63 × 16** | `0x0806D98C` | confirmed; window = entry 25 + 8 bytes; same table as above |
| `levels` | `0x5459D4` | 47 × 12 | **`0x5459C8`** | **45 × 12** | `0x0806D6E6` (+5 more) | confirmed; window = entry 1, no skew; count must drop 47 → 45 |

All four live tables in this area are **contiguous**, which is the strongest
single argument for the boundaries:

```
0x54241C  character templates   63 x 0xB4 (180)   -> 0x545068
0x545068  per-character growth  63 x 16            -> 0x545458
0x545458  jutsu / skill records 87 x 16            -> 0x5459C8
0x5459C8  character perks       45 x 12            -> 0x545BE4
0x545BE4  (another 16-byte table, 7 readers)       -> ...
```

Every end address is a live literal that the ROM actually loads.

---

## 3. Bonus: `map-events` (declared base `0x53EB08`)

The parent asked whether `0x53EB08` is a window of the newly-found live table
at `0x53EE98` (3 readers, ×10 stride).  **It is not**, and the reason is
positional:

* `0x53EE98 > 0x53EB08` — the live table lies **0x390 *after*** the legacy
  base, so `0x53EB08` cannot be inside it.
* `tools/legacy_rebase.py --target 0x53EB08 --window 0x1000` confirms
  `0x53EE98` is the nearest live literal **above** it and independently
  re-derives its **×10** stride from the reader at `0x080806BA` (`adds r4,
  r0, r1`), matching the parent's manual verification.
* The nearest live literal **below** `0x53EB08` is `0x53E698` (2 readers,
  ×8 stride).  `0x53E698 + 8 × 142 = 0x53EB08` exactly — but the map-event
  array has a **×4** stride, so this is an alignment coincidence, not a
  window.
* `map-events` itself: 47 consecutive u32 ROM code pointers
  (`0x0807EAF9`, `0x0807F065`, …), byte-exact against the bank, terminated by
  a zero word at `0x53EBC4`.  `0x53EB08` has **no** literal reader and **no**
  raw occurrence anywhere in the ROM.

**Verdict: `map-events` is a separate structure that the literal index cannot
reach** — it is presumably reached by computed arithmetic from the map table.
The neighbouring ×8 table at `0x53E698` is indexed by a per-map byte
(`0x0807F934`: `ldrb r0,[r0]` then `lsls r0,r0,#3` then `adds r0,r0,r1`), and
its records are not pointers.

---

## 4. Reproduction

```powershell
# the three banks
python tools/legacy_rebase.py rom/base.gba --target 0x54507A --target 0x545200 --target 0x5459D4

# a wider sweep of every legacy bank base the audit knows
python tools/legacy_rebase.py rom/base.gba --all-legacy

# the bonus
python tools/legacy_rebase.py rom/base.gba --target 0x53EB08 --window 0x1000

# the raw readers (read-only; the evidence file is NOT regenerated)
python tools/consumer_locate.py rom/base.gba --target 0x546100 --suggest 4096
```

Failure modes, both non-zero:

```powershell
python tools/legacy_rebase.py rom/base.gba --evidence notes/evidence/missing.json   # exit 2
python tools/legacy_rebase.py build/naruto-sequel-dev.gba --target 0x54507A         # exit 3 (digest)
```

## 5. Open items

* `notes/evidence/consumer-evidence.json` still carries the **wrong strides**
  (180 for `0x545068`, 63 for `0x5459C8`).  It is read-only for this cycle and
  was **not** regenerated; the correction lives here and in
  `tools/legacy_rebase.py`.  Whoever regenerates it should fix
  `tools/consumer_locate.py`'s `_detect_element_stride` to scope its search to
  the reader's own dataflow instead of the whole function.
* The **bank files themselves were not modified** — `sequel/content/**/bank.json`
  is outside this task's ownership.  The corrections each bank needs are
  specified in §2 and can be applied by the owner of those files.
* The remaining ~20 unlocated legacy banks are not triaged here;
  `tools/legacy_rebase.py --all-legacy` is the mechanical way to do it.

---

## 6. 追加（2026-10-21，父会话）：`items` / `skills` 落地 + 五个「剧情表」改判

本文件的三项结论**已被父会话采纳并落进仓库**（bank.json、registry、
`tools/table_registry.py::CONFLICTS`、完成度审计）。同一天还落地了两组：

### 6.1 `items` / `skills`：真基址 `0x545BE4`（94 条 × 16 字节）

用 `tools/legacy_rebase.py --target 0x546100` 得到的候选里有一个之前没人
注意到的：

```
delta  literal     file off  rd  reader     function   usage    stride
+0xc4  0x085461C4  0x5461C4  26  0x0806DF28 0x0806DE18 indexed-2d 6828+2276
-0x51c  0x08545BE4  0x545BE4   7  0x0806D91A 0x0806D85C indexed      16
```

`0x545BE4` 有 **7 个原生读者**、步长 **16 字节**，而且
**`0x545BE4 + 94*16 = 0x5461C4`** —— 正好是战斗编成矩阵的起点。
旧基址 `0x546100 = 0x545BE4 + 81*16 + 12`，是这张表的**第 81 条 + 12 字节**
的错位窗口（与 registry 旧记录「同形记录延伸到 0x5461BF」一致）。

实测：94 条里 93 条非空。

**可证伪判据**：`0x0806D91A` 必须仍以 ×16 索引 `0x08545BE4`；
`0x545BE4 + 94*16` 必须仍等于 `0x5461C4`；两个 bank 的条目必须逐字节等于
ROM 在 `0x545BE4 + 16*i` 处的字节。

### 6.2 五个「剧情表」其实是**音频**（详见另一份笔记）

`story` / `story-b` / `story-c` / `story-d` / `story-e` 的基址各差 **4 字节**，
它们不是剧情表，而是 **m4a SongHeader**（sound id 1/2/8/11/14）。
完整证据在 `notes/evidence/story-table-family-20261020.md`，
提取器 `tools/audio_song_headers.py`，写回路径 `tools/import_audio_song.py`。

### 6.3 已落地的改动

| 文件 | 改动 |
|---|---|
| `sequel/content/character-stats{,-b}/bank.json` | 基址 → `0x545068`，63 条 × 16 字节，字段名改中性（旧的来自错位窗口） |
| `sequel/content/levels/bank.json` | 基址 → `0x5459C8`，45 条 × 12 字节（原声明 47 条越过表尾） |
| `sequel/content/items{,-b}/bank.json` | 基址 → `0x545BE4`，94 条 × 16 字节 |
| `sequel/content/story*/bank.json` | 基址 → 表头起点，身份改为 m4a SongHeader |
| `tools/table_registry.py` | 新增 `per_character_stats` / `character_perks` / `item_skill_records` / `audio_song_*`；`CONFLICTS` 新增 `0x545068` 与 `0x545BE4` 两条 |
| `tools/populate_bank_json.py` | `populate_items` / `populate_story*` 改为新几何 |
| `tools/completion_audit.py` | 这 8 个 bank 从「基址无效」升级为 L1（含可执行写回探针的 5 个音频表） |
