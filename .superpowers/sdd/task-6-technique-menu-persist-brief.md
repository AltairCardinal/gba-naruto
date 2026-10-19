# Task 6 Step 5.2 — persist stable first-turn technique menu

Use strict TDD to persist independently approved p1 `build/scenario-41-technique-menu-p24-1-20260717/output.ss9` SHA `039030d6b754f66a07582356402c9eaf99832badaf0821939af4dbdc8e83c6c1` as a reusable intermediate named `scenario-41-first-turn-technique-menu`. This is a persistence-only task: do not run mGBA or create any new runtime fact.

Allowed files are exactly:

1. new `tests/test_scenario41_first_turn_technique_menu_persistence.py`;
2. mechanical binary copy `artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu.ss9`;
3. new compact `artifacts/runtime-checkpoints/scenario-41-first-turn-technique-menu-evidence.json`;
4. append one accepted child record to `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`;
5. append a concise section to `notes/scenario-41-movedone-runtime-20260717.md`.

First write focused tests and run them RED for the correct missing artifact/record reason. Then add the minimum artifacts and run GREEN. The ledger child must have parent `scenario-41-first-movedone-facing`, inputs `["A","Up","A"]`, screen `first-turn-technique-menu`, stable_zero_input true, both MOVEDONE hooks in `before_hooks`, and `allowed_evidence=[]`. Bind the exact lineage runs: facing confirm `bcedf5f65522909b84edb3b160c59b90`, defense Up `13ec9c4842007d4ace77efc17b7c043a`, defense affirmative A `a619e9ec5d24a0cbee0748e83ae4439b`; bind cycle run `42128f6224e172f1c17bd8b9d5ceca36` with p24/[0,24,48], and serial p1/p2 runs `e1db6602c1f66570145d730c90064ab4` / `9efd0047387a9520d06662c049b3bad6` with strict candidate→p1→p2 hashes.

Evidence/tests must bind checkpoint hash, observer/base ROM and runner/tool provenance, normalized RGB `17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef`, task resume `0x08067D02`, menu/round all zero, scenario41/map 36×44 grid9×22, slot1/record `0x02024294`, character1/affiliation0/(4,10)/facing0/action `00ff0000`, complete-unit hash `e48385264808378faf58c5ddace890789a2d4b99c06018170a33253649ebeb19`, counter1, exact MOD1 and canonical-zero MOD2. State explicitly that this checkpoint is only a stable unsubmitted technique-menu boundary; it does not prove technique submission, fresh MOVEDONE, completed turn, victory, or postbattle.

After focused GREEN, run the relevant persistence/ledger/savestate tests and ledger validator, inspect exact diff, and create one focused local commit. Do not edit evaluator/source/schema/plan/OpenSpec tasks/progress/AGENTS.md/docs/sequel-roadmap.md or any other file. Do not push. Report true RED and GREEN commands/results, commit SHA and exact file list; stop for thorough parent/reviewer audit.
