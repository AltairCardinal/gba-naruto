# Butano Scenario 49 HUD and Sprite Fidelity Breakthrough

**Date**: 2026-10-18  
**Scope**: Scenario 49 (Battle 14 "护送木叶丸逃离野蜂") Turn 1 Operational Branches  
**Target ROM**: `butano-sequel/butano-sequel.gba` vs Base ROM `rom/base.gba`

---

## 1. Summary of Achievements

Through automated multi-branch frame comparison (`tools/butano/compare_all_s49_branches.py`), we identified, dissected, and resolved multiple systemic rendering and timing discrepancies between the original GBA ROM and Butano.

Key metrics before and after:
- **01_naruto_menu Peak Match**: 97.53% -> **99.84%** (Total screen diff down to **60 pixels**).
- **01_naruto_menu Avg Match**: 78.62% -> **97.56%** (+18.94% overall improvement).
- **01_menu_cancel_b Peak Match**: 97.58% -> **99.76%** (Avg: **97.74%**).
- **02_move_selection Peak Match**: 96.21% -> **99.76%** (Avg: **90.88%**).
- **04_confirm_move_11_7 Peak Match**: 96.02% -> **99.38%** (Avg: **90.77%**).
- **04_cancel_move_to_menu Peak Match**: 96.48% -> **99.36%** (Avg: **94.00%**).
- **05_action_end_facing_defense Peak Match**: 99.45% -> **99.64%** (Avg: **96.47%**).
- **09_in_place_chakra Peak Match**: 96.56% -> **99.76%** (Avg: **74.12%**).
- **10_in_place_rest Peak Match**: 96.61% -> **99.76%** (Avg: **87.71%**).
- **Bottom Status Panel (240x32, y=128..160)**: **100.00% Match (0 diff pixels)**.
- **Action Menu Box (48x88, x=8..56, y=16..104)**: **100.00% Match (0 diff pixels)**.

---

## 2. Root Cause Analysis & Fixes

### A. Bottom Status Panel Discrepancy (280 diff pixels -> 0)
- **Root Cause**:
  In the original GBA ROM, the bottom status panel (`y=128..159`) uses static 8x8 font tiles for `体`, `力` (Row 1, `y=136..143`) and `查`, `克`, `拉` (Row 2, `y=144..151`).
  In Butano, `battle_runtime_scene.cpp:3466-3485` mistakenly generated these labels using the 8x16 `battle_ui_sprite_font` at `y=64` (screen center 144) and `y=72` (screen center 152). Because each sprite had height 16:
  - Row 1 spanned scanlines 136..151.
  - Row 2 spanned scanlines 144..159, overlapping Row 1 and clobbering the yellow/dark bottom border at scanline 153.
  - This consumed 5 hardware sprite slots (2 for `体力`, 3 for `查克拉`).
- **Solution**:
  1. Extracted the exact 32x16 pixel region `x=136..167, y=136..151` directly from `artifacts/s49-branches/original/01_naruto_menu/frame-050.png`.
  2. Created `battle_ui_status_labels.bmp` and `battle_ui_status_labels.json` matching the 16-color palette of `battle_ui_status_panel.bmp` with transparency.
  3. Replaced dynamic font generator calls in `battle_runtime_scene.cpp` with a single 32x16 OBJ sprite placed at `(32, 64)` (and `(32, 48)` for expanded target status).
- **Result**: Exactly **0 diff pixels** across the entire 240x32 status panel strip.

### B. Rogue `scenario_41_select_label` Removal (358 diff pixels -> 0)
- **Root Cause**:
  `battle_runtime_scene.cpp:1237-1243` spawned a "SELECT" badge (`scenario_41_select_label`) at `(96, -64)` (screen `x=192..231, y=12..23`) whenever the status panel was visible.
  Investigation of original Scenario 49 frames proved that no select badge exists in this scenario during battle.
- **Solution**:
  Removed the sprite creation code from `battle_runtime_scene.cpp`.
- **Result**: Cluster 2 difference (358 pixels in the top-right corner) completely eliminated.

### C. Turn 1 Camera Panning Settle Delay (+18.94% Avg Match)
- **Root Cause**:
  `boot_butano_to_turn1.py` saved `turn1_start.ss9` on the very first frame `phase == 1` was reached. At that moment, Butano was initiating a 16-frame camera pan from Konohamaru to Naruto.
  In contrast, the original ROM checkpoint was taken when the camera was already stationary and centered on Naruto. Consequently, frames 1..17 had an artificial ~30% match due to camera movement.
- **Solution**:
  Added a 20-frame settle period in `boot_butano_to_turn1.py` after `phase == 1` before taking the screenshot and saving the savestate.
- **Result**: Frames 0..20 match improved to >96.5%, and branch average match rose from 78.62% to 97.56%.

### D. Completed Unit Grayscale Outline Color 15 (151 diff pixels -> 0)
- **Root Cause**:
  When an allied unit (Konohamaru) completed its turn, Butano's completed unit grayscaling loop in `battle_runtime_scene.cpp:6592` recalculated all colors `color_idx = 1..15` using luminosity formula `(r * 299 + g * 587 + b * 114) / 1000`.
  For outline color 15 (`0x0420` / `(0, 8, 8)` in 8-bit RGB), integer division truncated `701 / 1000` to `0`, setting color 15 to `(0, 0, 0)`.
  Inspection of original ROM VRAM via mGBA savestate chunk decoding revealed that the original game grayscales only indices 1..14, preserving color 15 (`0x0420`) as the outline.
- **Solution**:
  Changed loop in `battle_runtime_scene.cpp` to `for(int color_idx = 1; color_idx < 15; ++color_idx)`.
- **Result**: All 151 black outline differences on Konohamaru became 0 diff pixels. Best frame match jumped to **99.84%**.

---

## 3. Current Branch Summary (Post-Fix)

| Branch | Frames | Avg Match | Best Match | Worst Match | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `01_naruto_menu` | 64 | **97.56%** | **99.84%** | 85.99% | Menu box & HUD 100% pixel-perfect |
| `01_menu_cancel_b` | 50 | **97.74%** | **99.76%** | 87.57% | Seamless return to map |
| `02_move_selection` | 64 | **90.88%** | **99.76%** | 37.94% | Range overlay matching |
| `03_move_right_11_7`| 64 | **84.77%** | **91.74%** | 82.02% | Movement step interpolation |
| `04_confirm_move_11_7` | 80 | **90.77%** | **99.38%** | 82.36% | Arrive and re-open menu |
| `04_cancel_move_to_menu` | 50 | **94.00%** | **99.36%** | 82.36% | Move cancelled back to tile |
| `05_action_end_facing_defense` | 130 | **96.47%** | **99.64%** | 76.03% | Facing and defense stance |
| `06_jutsu_menu` | 60 | **93.18%** | **100.00%** | 9.16% | Jutsu selection list |
| `07_shadow_clone` | 140 | 53.22% | **100.00%** | 9.16% | Zero-target confirmation direct transition |
| `08_normal_attack` | 200 | 63.21% | **100.00%** | 9.51% | Duel combat scene |
| `09_in_place_chakra` | 140 | **74.12%** | **99.76%** | 35.26% | In-place chakra replenishment |
| `10_in_place_rest` | 150 | **87.71%** | **99.76%** | 73.06% | In-place rest |

---

## 4. Next Priorities
1. **Movement Path and Camera Interpolation in Branch 03 (`03_move_right_11_7`)**:
   Align the Naruto walking animation frame cadence and tile step timing.
2. **Combat Duel Timing in Branches 07 and 08**:
   Align cutscene transition triggers and animation frame counts so that mid-cutscene match rises from ~50% to >95%.
