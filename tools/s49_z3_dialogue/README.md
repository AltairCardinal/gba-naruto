# Z3's dialogue probes

The probes of the wave 7 **Z3** stream (dialogue box opening + line break
wait).  They read the original ROM and the original's savestates **read only**
and never write into the remake tree; the only file they write into the
remake tree is the measured mask table, and they write it from the original's
captured frames so that no number in the header is typed by hand.

The report with the findings is `notes/s49-fidelity/Z3-dialogue-box.md`.

## The two recorders

| tool | what it does |
|---|---|
| `lua/record_fine.lua` + `record_fine_original.py` | **One capture per GBA frame** of the original's dialogue window.  The semantic walk recorder (`tools/s49_pairing/`) samples every four frames, which is too coarse for the "confirm press to first glyph" delay; this one saves no savestate, so it is an order of magnitude faster. |
| `tools/s49_pairing/record.py` (read only) | The four frame walk the rest of the repository uses. |

```powershell
python tools/s49_z3_dialogue/record_fine_original.py `
    --out build/s49-z3/fine-original --from 1100 --to 1800
```

The capture index maps to the original's own frame number:
the base capture is the frame `zero_input_frames` (90), beat `b` presses the
confirm key on frame `90 + 94 * (b - 1)`, the inner captures are 4 frames
apart and the beat capture is 94 frames after the press.

## The measurements

| tool | what it answers |
|---|---|
| `measure_fine.py` | The dialogue events of the fine recording at one frame resolution: the first glyph of every line, the last glyph, the advance icon, the confirm press. |
| `measure_typewriter.py` | The same for the four frame walk (the coarse grid of the pairing instrument). |
| `scratch_frame_diff.py` | What changes between two captures: the portrait slide in and out, the text erase. |
| `scratch_reveal_residual.py` | The per frame residual of the dialogue box reveal on **both** sides (the number of pixels that differ from the settled capture). |
| `scratch_subset.py` | Proves the reveal is a **pure black overlay** over an already complete scene (every pixel that differs from the settled frame is non black in the settled frame). |
| `scratch_vram_diff.py` | Which VRAM blocks change during the reveal (the answer: only the object character data, the background tile maps are byte identical). |
| `scratch_mask.py`, `scratch_mask_band.py`, `scratch_mask_rects.py`, `scratch_mask_runs.py` | The geometry of the black mask that still covers the dialogue box. |
| `make_cut_table.py`, `make_mask_table.py` | Print the measured mask of the dialogue box interior. |
| `sync_mask_table.py` | **Rewrite the measured mask table inside the remake's `battle_presentation_content.h`** from the original's captured frames. |
| `scratch_script_dump.py`, `scratch_opcode_hist.py` | Dump the remake's generated battle presentation script and its opcode histogram (the answer: the whole data set has **one** `wait_frames` command, so the line break wait is not a script parameter). |
| `scratch_signatures.py` | The dialogue signature sequence of both sides (the content anchor's `bright_share`). |
| `scratch_zoom.py`, `scratch_stack.py`, `scratch_census.py`, `scratch_cream.py`, `scratch_geometry.py`, `scratch_icon_census.py`, `scratch_icon_locate.py` | Small image probes: magnified strips, colour censuses, the geometry of the dialogue box interior. |

Every probe takes the capture directory as its first argument and prints what
it measures; nothing of theirs is imported by the remake.
