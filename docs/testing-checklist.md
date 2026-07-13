# Testing Checklist

## Authoritative Offline Smoke (2026-07-13)

- [x] `python3 tools/automated_test.py --json-output ...` passes 25/25
- [x] Actual output ROM SHA-1 and size match the build report
- [x] Native mGBA loads the tracked actionable battle checkpoint
- [x] Runtime snapshot is battle 41 on map 36×44 / grid 9×22
- [x] Runtime units remain Naruto `(4,10)` and Iruka `(4,4)`
- [x] Commands, exit codes, hashes and assertions are persisted under `artifacts/e2e/`
- [ ] Editor mutation → isolated build → download → runtime-visible change
- [ ] Cross-platform Chinese OCR comparison
- [ ] Long-path story → battle → save/load regression

Run `python3 tools/run_offline_e2e.py`. The unchecked sections below are the
historical broad checklist and must not be interpreted as completed by this smoke.

## Build Verification

- [ ] `python3 tools/build_mod.py` runs without errors
- [ ] Base ROM sha1 matches expected
- [ ] All patches apply without mismatch errors
- [ ] Output ROM generated at `build/naruto-sequel-dev.gba`
- [ ] Build report written to `build/naruto-sequel-build-report.json`

## Dialogue Patches

- [ ] `dialogue_proof_same_length` patch verified in output ROM
- [ ] `dialogue_group0_main` patch verified in output ROM
- [ ] `dialogue_group1_main` patch verified in output ROM
- [ ] `dialogue_group2_main` patch verified in output ROM
- [ ] `dialogue_group0_label1` patch verified in output ROM
- [ ] All patched text decodes correctly in cp932
- [ ] New text is readable in emulator at expected screen position

## Content Validation

- [ ] All dialogue text encodes in cp932 without errors
- [ ] All new text fits within `max_bytes` constraint (or uses redirect)
- [ ] No unintended bytes changed outside patch targets

## Build Pipeline

- [ ] `bytes` patch type works
- [ ] `dialogue` patch type works
- [ ] `pointer_redirect` patch type framework works
- [ ] `map` patch type framework works (when format discovered)
- [ ] `battle_config` patch type framework works (when format discovered)

## ROM Integrity

- [ ] Output ROM is same size as base ROM (no size change)
- [ ] Unpatched regions of ROM unchanged (spot check)
- [ ] Patch manifest has no duplicate IDs
- [ ] All enabled patches have matching bank entries

## Runtime Verification (mGBA)

- [ ] mGBA loads `build/naruto-sequel-dev.gba`
- [ ] Game boots past title screen
- [ ] New dialogue text appears at expected points
- [ ] No crashes during patched dialogue sequences
- [ ] Battle mode works (if battle patches applied)

## Content Completeness

- [ ] Episode-01 story skeleton has all 3 beats defined
- [ ] Episode-01 map spec has `patch_ready: true` when tilemap format found
- [ ] Episode-01 battle config has `patch_ready: true` when battle format found
- [ ] Unit definitions include all planned sequel characters
