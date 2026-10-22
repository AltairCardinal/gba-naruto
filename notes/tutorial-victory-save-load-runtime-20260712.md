# Tutorial victory and save/load runtime closure (2026-07-12)

## Outcome

The first tutorial was completed through the real UI and state machine. The
in-game Save command produced a valid 32-KiB SRAM image, and a cold ROM restart
recognized and restored it to the same Konoha overworld. This upgrades the
save-state descriptor bank from `code_verified` to `runtime_verified`.

## Natural victory route

The earlier map checkpoint was prebattle “view battlefield”. The actionable
route selects “start mission”, confirms Yes, advances the Start overlay and
Iruka dialogue, then performs:

1. round 1: Move Naruto `(4,4)→(4,7)`, end action, choose facing, decline a
   defensive technique;
2. finish the tutorial interruption and remaining round-1 action flow;
3. round 2: Move `(4,7)→(4,10)`, directly above chest `(4,11)`, and end action.

The game entered the star-shaped victory transition and returned to Konoha.
This matches the guide instruction to move one square from the chest and end
action.

During movement, unit `+0xC4/+0xC5` retains the committed turn-start coordinate
while `+0xC7/+0xC8` holds the current destination. At the turn boundary both
become the committed coordinate. This explains why the equality-filtered
formation probe temporarily loses a moving unit.

## Natural save and corrected record layout

Konoha menu Save → slot 1 → Yes wrote `/tmp/ui-save-complete.sav` (32,768
bytes). Disassembly of `0x08068684` and the file agree on each record:

`19-byte identity header + payload_length bytes + 1 checksum byte`

Record starts advance by `payload_length + 0x14`. Active records are:

- descriptor 0 at `0x0000`: header `Naruto-KONOHASENKI\0`, length 4732,
  observed/expected checksum `0xF7`;
- descriptor 2 at `0x2520`: the same header, length 20, observed/expected
  checksum `0xE3`.

Descriptors 1 and 3..9 are all-`FF` unused records, not corrupt records. The
corrected `tools/verify_save_state_records.py` reports the complete image PASS.
The former verifier started payload at the record base and therefore had a
19-byte offset error.

## Cold-load proof

`PROBE_SAVE_LOAD=/tmp/ui-save-complete.sav` installs the file and quick-reloads
the ROM before navigation. From the fresh title, Continue recognizes slot 1,
shows Konoha and play time `0:12:46`, reports load completion, and restores the
same Konoha overworld and Move / character / item / Save menu. Character
template slot 1, ID 1 is restored before a battle unit pool exists. This is a
cold game load, not savestate-only restoration.

`0x08068AF0` does not execute on this primary title-slot path. Its sole caller
at `0x080752D0` follows optional battle-state preparation, so the old title-load
acceptance condition was a caller-scope error.

## Durable tools and addresses

- runtime driver: `play/_scripts/runtime-formation-probe.js`;
- verifier: `tools/verify_save_state_records.py`;
- extractor: `tools/extract_save_descriptors.py`;
- optional-load observer: `tools/build_natural_load_runtime_probe.py`;
- descriptor table: ROM `0x53D848`;
- low-level handler: `0x08068684`;
- optional wrappers: `0x080689A4` / `0x08068AF0`.
