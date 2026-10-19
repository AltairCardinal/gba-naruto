# Task 6 Step 5.2 persistence fix1 — close the defense-stability lineage gap

Fix the Important findings on commit `7016ce29f4aea14cde3effe2c78d5ea569912565` under strict TDD, without running mGBA or creating new runtime facts. Allowed edits are exactly:

1. `tests/test_scenario41_first_turn_technique_menu_persistence.py`;
2. `artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu-evidence.json`;
3. `notes/scenario-41-movedone-runtime-20260717.md`.

First add a test that requires a structured, ordered `state_chain` and fails RED because it is absent. The chain must begin at canonical parent checkpoint SHA `1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94`, end at canonical checkpoint SHA `039030d6b754f66a07582356402c9eaf99832badaf0821939af4dbdc8e83c6c1`, and assert every step output SHA exactly equals the next step input SHA. Required chain steps are:

- facing confirm A run `bcedf5f65522909b84edb3b160c59b90`: `1bc95c63…ffb94 -> 54cf5ecacd9cd89dd679b2b8926e6b6de2f27080da28331aae06c17abe414101`;
- defense Up run `13ec9c4842007d4ace77efc17b7c043a`: `54cf5eca…4101 -> a6f0806c8d2409f6b84300bd58c7bd76e59bd5ee649dffc345b80ba3b3d7017a`;
- defense-yes p1 zero run `10a2275055b9a604b006aed551c952be`: `a6f0806c…017a -> 695d14e7828251b6c908f8dc57a5f0e8951fc9cc877c22525479e2a687323fa3`;
- defense affirmative A run `a619e9ec5d24a0cbee0748e83ae4439b`: `695d14e7…3fa3 -> f26173ff9d03344cd2f1bb6715158e5764a1853eb8c808df811b852545a9a0f1`;
- technique p24 p1 zero run `e1db6602c1f66570145d730c90064ab4`: `f26173ff…0f1 -> 039030d6b754f66a07582356402c9eaf99832badaf0821939af4dbdc8e83c6c1`.

Each chain step must store input/output/audit/guard/done SHA-256 and input mode/timing; obtain exact artifact hashes only from the existing reviewed run roots/reports and independently re-hash those files. Explicit A/Up/A steps use native 5/13/8/capture128; zero bridge uses capture1 and no input/pre-script; final p1 uses capture24 and no input/pre-script. Separately retain and strengthen diagnostic/corroboration branches: defense cycle run `ca840f8e56bfd674a8695614fc490ca3`, defense p2 `95b2134e4abe6862a0227e7e68cbcc12`, technique cycle `42128f6224e172f1c17bd8b9d5ceca36`, technique p2 `9efd0047387a9520d06662c049b3bad6`, each with exact relevant state and artifact hashes. Do not misrepresent diagnostic cycle outputs as the canonical chain.

Update the note to describe the zero-input bridge explicitly. Run the focused test RED then GREEN, the same correct 39-test suite and ledger validator, inspect exact three-file diff, and commit one focused local fix. Do not edit checkpoint binary, ledger, evaluator/source/schema/plan/OpenSpec/progress/AGENTS/roadmap or any other file. Do not push. Report RED/GREEN, commit SHA and exact scope; stop for a completely fresh thorough review.
