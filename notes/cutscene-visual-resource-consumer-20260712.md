# `0x53DF70` visual-resource consumer correction (2026-07-12)

## Result

The catalog formerly named `cutscene-scripts` is not a 16-entry script table.
It contains two adjacent four-record, 8-byte visual-resource tables used by
resource IDs 0..3:

- `0x53DF70..0x53DF8F`: LZ77 graphics pointer + LZ77 palette pointer;
- `0x53DF90..0x53DFAF`: sprite-definition pointer + animation pointer.

The historical slug remains for migration compatibility, but the bank is now
`code_verified` with eight pointer-pair records. It must not be used as evidence
for story opcode or dialogue semantics.

## Consumer chain

`0x08072EDC` receives an 8-bit resource ID. At `0x08072F0C` it computes
`id << 3`, indexes literal base `0x0853DF70`, and sends the two pointers through
`0x0809C0E8` to `0x06016000` and `0x05000380`. All eight targets in the first
four pairs begin with GBA LZ77 header byte `0x10`.

The same routine passes literal base `0x0853DF90` to `0x080625A4`.
`0x08062668..0x08062674` indexes that base by `id << 3` and installs the two
pointers at sprite-task offsets `+0x1C/+0x20`.

Direct calls observed statically are:

- `0x08073100`: ID 1;
- `0x0807314A`: ID 2;
- `0x08073196`: ID 3;
- `0x0807363A`: ID 0.

## Boundary and maintenance rule

`0x53DFB0` is independently referenced from literal `0x08075C0C` and is not a
ninth pointer-pair record. `tools/populate_bank_json.py` now preserves the
8-byte pairing so regeneration cannot recreate the false 16-script model.
The editor mirror and real-ROM generator now use the corrected eight rows with
`primary_ptr/secondary_ptr`. The old 16-row `script_ptr` generator was removed
after a full isolated DB build reproduced its schema crash. The historical
cutscene slug remains compatibility-only and is not semantic script evidence.
