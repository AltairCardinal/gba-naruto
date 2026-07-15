# Scenario 41 prebattle-menu acceptance on macOS Intel (2026-07-15)

## Attempt

Task 4.6 Step 3 reused the existing guarded strict replay directory
`build/macos-prebattle-frame80-step2-20260715/`. No ROM session was started and no
Down/A/controller input was sent. This avoids repeating the prologue and keeps the
already measured peak tree RSS of `51.94921875 MiB` as the only emulator allocation
for this acceptance.

The new offline gate `tools/accept_prebattle_candidate.py` authenticated the actual
bytes of the base and staged ROM, input and output states, screenshot, replay Lua,
build manifest, x86_64 mGBA 0.10.5 binary, and the upstream patch embedded in the
manifest. It also required the strict audit to say `success=true`,
`evidence_mode=zero-input`, `zero_input_verified=true`, `inputs=[]`, and
`pre_scripts=[]`, and required the guard summary to be non-degraded
`completed/0`.

## Result

All gates passed, so the tracked file
`artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9` (SHA-256
`b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078`)
is accepted as `scenario-41-prebattle-menu` in the checkpoint ledger. Durable compact
evidence is `artifacts/runtime-checkpoints/scenario-41-prebattle-menu-evidence.json`.

- strict run ID: `be8e11738e43f276b0c31798061e63fc`;
- frame-80 state SHA-256:
  `53ab750fe1c91d8ee2d47dee212aafcd3c3625059d349b2b3a2aa2eb59d23b65`;
- frame-80 PNG SHA-256:
  `6a4a715a35072b0a5d68b8a33de4076598fc67fb435e816516a9b211bb76e5f0`;
- candidate and output are RGB8 240×160 and share normalized RGB pixel SHA-256
  `bf0ffd7484bc0d4c8e2f94af623b265f8f462a891133a0bccf67f757c849d035`;
- task 2 SP/resume PC: `0x030011D8` / `0x08067D02`;
- `[0x0202680C]=0`;
- final read-only residue probe found no exact PGID `20050` row and no mGBA TCP
  listener. It did not kill or alter any process.

## Active-unwind method and important addresses

The inspector does not scan the stack for ROM-looking words. It reads only the three
known active slots and validates each raw return against the immutable base ROM with
`tools.thumb_branch.decode_thumb_bl`:

| Stack slot | Raw return | BL callsite | Decoded target |
|---|---|---|---|
| `0x03001220` | `0x080885C1` | `0x080885BC` | `0x08067158` |
| `0x03001240` | `0x08088F9F` | `0x08088F9A` | `0x080884DC` |
| `0x03001278` | `0x0808F92D` | `0x0808F928` | `0x08088F10` |

The negative boundary is independently static-checked: raw controller return
`0x0808F957` maps to callsite `0x0808F952`, whose BL target is `0x080732B4`. That raw
return is absent from the accepted task-2 unwind.

## Boundary

This result proves only that the reusable state remains on the same scenario 41
prebattle menu for 80 zero-input frames. It does not prove battle controller entry,
player control, MOVEDONE, victory, result storage, postbattle, EXP, or level growth.
Future input experiments must start as a separate reviewed task and preserve this
accepted snapshot as their reload point.

## Thorough-review hardening

The acceptance gate now treats the Step 2 caller-known values as immutable pins rather
than trusting a mutually consistent audit/sentinel rewrite. Audit, sentinel, guard,
candidate, output state/PNG, ROM/staged ROM, Lua, manifest, binary and patch all have
fixed SHA-256 values; repo inputs/outputs and external Step 1 manifest/binary also have
fixed paths. The guard is revalidated through the replay runner's existing POSIX
process-group contract, with an additional finite-positive peak RSS requirement and
exact audit equality.

Review fix round 2 closes the remaining patch-source gap: caller mode now requires the
tracked `tools/patches/mgba-0.10.5-qt-script-cli.patch` at its fixed repository path,
checks its fixed SHA-256, and compares its actual bytes directly with the manifest's
embedded base64 payload. Evidence records the tracked patch's relative and absolute
paths instead of leaving the patch represented only by a hash.

The PNG and savestate readers share one CRC/IEND/no-trailing chunk parser and bounded
`decompressobj` checks for EOF, unused data and unconsumed tails. Screen identity is now
based on normalized RGB bytes after reversing all standard PNG filters, not on encoded
pre-unfilter rows.

The compact evidence retains absolute `build/` and `.cache/` paths because it describes
one historical local raw run. The repository does not distribute those machine-local
raw outputs; it distributes the tracked candidate and compact JSON. Rebuilding the
compact evidence from raw bytes therefore requires the pinned local Step 1/2 files.
