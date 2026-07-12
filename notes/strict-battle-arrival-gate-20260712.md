# Strict WASM battle-arrival gate (2026-07-12)

## Visual-gate correction

The original color classifier is withdrawn. It classified the genuine tail
battle-map screenshot as `other`, then classified the later character detail
panel as `battle-map`. Consequently the old “step 306 strict arrival” label is
a false positive and must not be used as proof.

The route did pass through a real battle map: the durable tail screenshot shows
the diamond map and chest before settle confirmations opened the character
panel. Offline pixel measurement over the game viewport gives
`darkRatio=0.200625` for the real map and `0.003125` for the panel.

The corrected classifier uses the diamond map's black corners (`darkRatio >
0.12`, low pale ratio) and separately identifies a full green UI panel
(`darkRatio < 0.05`, high green ratio). A new live run is required before using
the `strict-battle-arrival` reason again. ROM→WRAM A/B observations remain
valid, but their historical screen-state label is superseded by this section.

Two corrected-classifier reruns produced no false success. The first drifted to
the team/equipment page and ended on a character panel with zero battle/map
state. The second replaced the last A with START and stopped on the “special
chest” tutorial instruction page; it also ended without battle/map state. Both
were correctly rejected. The screen reveals the relevant menu order: team and
equipment, view map, start mission, save. START does not dismiss the tutorial;
the next deterministic navigator must select start mission and then confirm the
tutorial page with A before evaluating the black-corner map gate.

## Problem

The old probe returned success as soon as runtime coordinates uniquely matched
one formation. This was too weak: the game preloads unit templates, map sizes,
battle ID 40, and formation `(4,4)` while dialogue or transition graphics are
still visible. Therefore “unique formation” did not prove that navigation had
reached the playable battle map.

## Implementation

`play/_scripts/runtime-formation-probe-lib.js` now exposes
`evaluateBattleArrival()`. Success requires four independent conditions:

1. a unique formation candidate with no missing observed coordinates;
2. a non-zero `0x02026805` chapter/battle ID;
3. non-zero, derivation-consistent map dimensions at `0x0201BE28..2B`;
4. screenshot metrics classified as `battle-map` (green ratio above 0.18 and
   pale/text-panel ratio below 0.12).

The main probe captures screen metrics on every navigation and settle step.
All three former success exits now use the strict combined gate. Two regression
tests prove that preloaded memory during dialogue is rejected and that no one
factor can substitute for the others. Node probe tests are 23/23 passing.

## Live baseline result

The standard 30 Start / 250 A / menu-tail route was rerun against the baseline
ROM through the browser WASM emulator.

- At step 286, formation group 40 variant 0 was unique and complete, battle ID
  was 40, and map runtime was `[36,44,9,22]`, but screen state was `other`.
  The strict gate correctly rejected this preloaded state.
- During settle, several `prebattle-menu`/`other` samples were also rejected.
- At step 306 / settle poll 20, metrics were gray `0.0070833`, pale
  `0.1192057`, green `0.2652083`; screen state became `battle-map` and all four
  checks passed.
- Final result: `matched`, reason `strict-battle-arrival-after-settle`.
- Runtime position: slot 1, character 1, `(4,4)`; unique ROM formation group
  40 variant 0.

Local evidence artifacts:

- `/private/tmp/strict-arrival-baseline-result.json`, SHA-256
  `f6c053aaa2a980a2bff69d3c37c9a8de8a0c750925075f0eef49a8198ab1265b`;
- `/private/tmp/strict-arrival-baseline.png`, SHA-256
  `e45f971febb37fede2a2a9cfa580c22bad86ca25c492f723facffbf0bc12ef96`.

## Consequence for earlier evidence

Earlier unit/growth/map A/B results remain useful because they compare explicit
ROM mutations against their predicted runtime bytes; however, their historical
`unique-formation` result reason alone must not be cited as proof of visible
battle arrival. Future navigation, save, chapter, and resource experiments must
use the new strict result reason and inspect `final.arrival.checks`.
