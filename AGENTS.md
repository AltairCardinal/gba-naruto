# Project Memory Rules

This repository is used as the persistent project memory for the ROM reverse-engineering and sequel-planning work.

Required rules:

1. All meaningful findings must be written into files inside this repository.
2. All effective development work must leave durable project artifacts in this repository.
3. Do not rely on chat history as the primary memory. If something matters later, record it in `notes/`, `docs/`, `tools/`, or another appropriate project file.
4. When a debugging method proves useful, document both the method and the result.
5. When a reverse-engineering conclusion changes, update the relevant note instead of leaving the old state only in conversation.
6. When roadmap progress changes, update `docs/sequel-roadmap.md` in the same work cycle.
7. **防循环守则**（2026-10-23 补；事故复盘见 `notes/evidence/session-loop-analysis-20261023.md`）：
   - **一次尝试必须能回答一个是/否问题。**「还是卡」不是结果，是噪音 ——
     换成能判定的观测（某处补丁开/关能不能跑、屏幕 diff 差在哪一行、某条断言过不过），
     或者换个方向。
   - **一次只改一处，跑一次，记一行。**结论落进**假设台账**
     （一行一个假设：判定方法 / 结果 / 状态 = 未验·已证伪·已确认），
     不要只写叙述性的「我试了 X 不行」—— 下一个会话读台账才能直接接着干。
   - **连续 3 次同样结果 ⇒ 停。**把「这条路走不通」写进台账，换方法，
     不要在同一处试第 4 次。
   - **陷住了就换方法/换会话，不要靠 Goal 续跑硬扛** ——
     续跑提示会逐字重复，只会把同一个状态再喂一遍。
   - 自检：`python tools/loop_guard.py <会话的 messages.jsonl>` ——
     命中就是「真的在打转」，不要继续往下想。

Preferred locations:

- `notes/`: investigation logs, intermediate findings, memory maps, experiment results
- `docs/`: stable plans, workflows, architecture, reverse-engineering strategy
- `tools/`: scripts, automation, reproducible probes

Minimum expectation for each successful step:

- record what was attempted
- record what was learned
- record what file or address range is now important

## Instrument discipline (added 2026-10-25, wave 18-19)

These four rules came out of wave 18-19 and are cheap to follow, expensive to
rediscover:

8. **改过探针源码的命令签名 ⇒ 重建所有私建探针。**
   The probe binaries under `build/mgba-probe*/` are *copies*, not build outputs:
   `tools/s49_save_boundary/` uses the private `build/mgba-probe-w4/mgba-probe.exe`
   and only rebuilds it when the file is **missing**, so a stale copy survives
   indefinitely. Symptom: the tool prints the probe's own usage line
   (`ERR framedump <count> <addr> <len> <prefix> [keymask]`) and the natural but
   wrong conclusion is "the tool passes the arguments in the wrong order".
   Check the probe's real signature in `tools/mgba_probe/host_main.c` and compare
   it with the binary's date before touching the tool.
9. **并行构建要各建各的副本。** Several streams build the very same
   `butano-sequel.gba`; concurrent builds overwrite each other's output and
   `objcopy` fails with `Invalid argument`. Each stream works in its own copy of
   the tree (source directories copied, read-only asset directories symlinked) and
   the parent merges the owned files afterwards (`tools/s49_wave18/integrate.py`,
   which also flags files a stream touched outside its ownership).
10. **子代理可能被截断 ⇒ 先写笔记骨架，再写代码。** Two streams in wave 18-19
    were cut off before producing their note, so their findings existed only in
    the conversation and had to be recovered from code comments. A stream's note
    must be written incrementally, not only at the end.
11. **判定台的读数必须绑定同一个 ROM。** The bench compares two *walks*
    (the original from a save state, the remake from boot), so the two sides
    differ by a constant step offset. Measure that offset
    (`tools/s49_wave18/align_capture_steps.py`) before treating a residual as a
    product difference, and never compare residuals across different ROMs.
12. **不要把「画面会变的帧」加进「有变化才重画」的判定。** Doing so halves
    the scene frame rate (the telemetry's `scene_frame` advances every 2
    frames instead of every frame), which shifts the whole timeline by ~45
    frames and breaks frames that were pixel-identical before. Measured cost in
    wave 21: the 25-frame bench residual went 148,914 → 186,279 px
    (**+37,365**). Every "extra frame that changes the picture" (a black-field
    fade level, a camera pan step) hits this trap. Keep such updates **outside**
    the "redraw only if changed" condition.
13. **仪器读出的「寄存器」要先证明它真的是那个寄存器。** The bench's `bg_hofs`
    used a 4-byte stride and actually read `VCOUNT`/`BG1CNT`/`BG3CNT`, so every
    conclusion drawn from it ("the camera is at a different position") was
    built on the wrong register, and the real scroll registers read back as a
    constant filler (open bus) on the headless debugger. GBA's IO map uses a
    **2-byte stride** (`BGxCNT` = `0x08 + 2x`, `BGxHOFS` = `0x10 + 4x`). When a
    register reading is used as evidence, verify it against the ROM's own
    register dump first, and expose a "is this actually readable" flag
    (see `probe.py::io_registers`).
14. **子代理被截断时，先去 lane 副本里翻。** In wave 20 all four streams were
    cut off before writing a note, but **their work was on disk**: a verified
    fix, a rule proof and a pixel decomposition all survived in the lane
    copies. After a wave, diff each lane against the shared tree
    (`tools/s49_wave18/integrate.py`) before concluding the wave produced
    nothing.
15. **判定台残差对「帧号位移/画面冻结」和「渲染」一样敏感。** Changing
    anything that moves frames (a black-field fade level, a camera pan, a
    scene switch) can freeze the walk's tail and make the residual explode
    even when the thing you changed got better. Measured in wave 23: the
    4bpp conversion removed 2 pure-black frames and saved 91 KiB of ROM, yet
    the 25-frame total went 54,959 → 82,831 px because the last 7 frames
    stopped advancing. **After any timing change, check both instruments**
    (`s49_fidelity_report` = arg-min, `align_capture_steps.py` = fixed
    offset) and confirm the frames that improved did not drag others off.

## Lane discipline (added 2026-10-26, wave 24-25)

16. **lane 的 `graphics/` 必须是真实目录，不能是指向共享树的符号链接。**
    A lane that symlinks `graphics/` back to the shared tree turns every asset
    patch into an edit of the *shared* tree. Measured in wave 24 / G3: three
    settlement assets were written into the shared tree before it was noticed
    (the damage was reverted byte-exactly, but it cost a rebuild). Build lanes
    with `tools/s49_w25/setup_lanes.py`, which copies `graphics/` for real.
    The same script copies `benchmark/`: the Makefile lists `benchmark/src` in
    `SOURCES`, and a lane without it cannot link `main.cpp` (wave 24 / G3 lost
    a build cycle to this).
17. **整文件覆盖式合并会丢工作 —— 多路改同一文件要用真三方合并。**
    `tools/s49_wave18/integrate.py` copies whole files, so two lanes that edited
    the same file cannot both be integrated. Wave 25 has three lanes editing
    `game/src/battle_runtime_scene.cpp`; use
    `tools/s49_w25/merge_lanes.py` (`git merge-file`, base = shared tree,
    ours = lane A, theirs = lane B). Per-lane ownership therefore has to be
    stated as *regions of a file*, not just file names.
18. **往 BG 层资产里抄像素前，先实测「屏幕 ↔ 资产」的偏移量。**
    Do not derive the offset from a comment. Wave 24 / G3 assumed GBA's hidden
    16-pixel border shifted the mapping to (+16, 0); a brute-force alignment
    over ±40 px showed the true mapping is **(0, 0)**. The patch simulated a
    0 px residual and actually only reached 163 px on hardware. Measure first
    (`for dy in -40..40, for dx in -40..40` → the hit rate separates cleanly).

