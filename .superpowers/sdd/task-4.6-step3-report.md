# Task 4.6 Step 3 implementation report

## Scope

Accepted the already tracked scenario 41 prebattle-menu candidate by reusing the
existing strict frame-80 replay. No emulator was launched, no ROM input was sent, and
no process was killed. The accepted boundary remains strictly before battle-controller
entry and player control.

## TDD RED → GREEN

### Inspector RED

Command:

```bash
python3 -m unittest tests.test_inspect_mgba_savestate -v
```

Observed RED: 8 tests ran, 4 failed for the intended missing behavior:

- `png_screen_fingerprint is not implemented` for valid and fail-closed PNG cases;
- `inspect_savestate` had no `rom_path` parameter for explicit BL-validated unwind.

After the minimal inspector implementation, the same command passed 8/8.

### Acceptance-builder RED

Command:

```bash
python3 -m unittest tests.test_accept_prebattle_candidate -v
```

Observed RED: 3 tests ran, 3 failed because `validate_strict_replay` and
`validate_runtime_residue` were not implemented. After minimal implementation, the
combined inspector/acceptance suite passed 11/11 at that checkpoint.

### Persisted ledger wiring RED

Command:

```bash
python3 -m unittest \
  tests.test_accept_prebattle_candidate.AcceptPrebattleCandidateTests.test_persisted_acceptance_evidence_and_ledger_share_the_strict_boundary \
  -v
```

Observed RED: the evidence existed but the ledger contained zero records named
`scenario-41-prebattle-menu`. After adding exactly one accepted record linked to the
durable evidence, the same test passed and the ledger validator reported
`accepted=4 candidate=0 rejected=1 errors=0`.

### Provenance-wiring hardening RED

The focused test
`test_rejects_wrong_capture_frame_and_guard_rom_wiring` first failed because a
capture-frame drift to 79 was not rejected. The gate now requires both frame fields to
be 80 and requires the exact four-argument guard command to end in the authenticated
staged ROM. The focused test then passed. The combined inspector/acceptance suite for
the initial implementation contained 13 tests.

## Acceptance result

- candidate SHA-256:
  `b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078`;
- candidate/frame80 normalized RGB pixel SHA-256:
  `bf0ffd7484bc0d4c8e2f94af623b265f8f462a891133a0bccf67f757c849d035`;
- task 2: SP `0x030011D8`, resume PC `0x08067D02`;
- explicit BL-validated raw unwind:
  `0x080885C1 → 0x08088F9F → 0x0808F92D`;
- controller raw return `0x0808F957` absent; its independent negative-boundary
  callsite `0x0808F952` still decodes to `0x080732B4`;
- `[0x0202680C]=0`;
- strict run `be8e11738e43f276b0c31798061e63fc` authenticated ROM, staged ROM,
  candidate/output state, PNG, Lua, manifest, x86_64 mGBA 0.10.5 binary, and embedded
  patch hashes from actual bytes;
- guard was non-degraded `completed/0`, peak tree RSS `51.94921875 MiB`;
- final read-only check found no exact PGID `20050` process and no mGBA TCP listener.

## User-visible boundary

The prebattle menu snapshot is now an accepted reusable reload point, eliminating the
need to replay the prologue for the next debugging segment. This step does not claim
controller entry, player control, MOVEDONE, victory, postbattle, EXP, or levels, and it
does not authorize or perform Down/A input.

## Thorough review fix round 1

The review identified three Important gaps and all were exercised through additional
RED → GREEN cycles:

1. Caller-known provenance: three focused tests first failed because the validator had
   no caller-pin API. The GREEN implementation fixes every Step 2 path/hash, requires a
   fixed and identical sentinel, and reuses the replay runner's manifest/guard
   validators. A fully self-consistent multi-file drift is still rejected.
2. Strict image/state decoding: the inspector RED had four expected failures for the
   missing normalized pixel field, filter-dependent identity, unvalidated `gbAs` CRC,
   and accepted filter 5. The GREEN implementation shares strict chunk/zlib parsing,
   reverses PNG filters 0..4 including Paeth, and hashes normalized RGB bytes.
3. Integration boundaries: the actual builder was run against local Step 2 raw files
   with only the read-only residue probe mocked. Focused REDs exposed the missing
   standalone state boundary and stale pre-unfilter method. GREEN tests now cover bad
   controller chain, WRAM flag, guard/pin failure, residue, every zero-input field,
   missing sentinel, path/provenance drift, and ledger lineage/scope.

Absolute `build/` and cache paths in the compact JSON are historical local provenance.
The repository distributes only the tracked candidate and compact evidence; raw
revalidation needs the pinned machine-local Step 1/2 files.

Final review-fix verification ran 130 related tests successfully with one documented
Windows-only skip. The acceptance CLI also generated a separate compact result at
`/tmp/scenario-41-prebattle-menu-evidence-fix1.json` without launching mGBA.

Review fix round 2 adds the final tracked-patch binding. Its RED proved that caller
mode ignored a replaced tracked patch and omitted it from actual evidence. GREEN now
pins the repository patch path/hash, requires byte identity with the manifest's
embedded payload, and records both repository-relative and absolute paths.
