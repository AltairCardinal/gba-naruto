"""S49 packaging pipeline (stream X4).

One command that takes the remake tree from source to a shipped package:

    python tools/s49_package/run_pipeline.py

Every step is independently re-runnable (``--only <n>`` / ``--from <n>``),
every step has an explicit success criterion, and the pipeline exits non-zero
when any step failed.  Nothing is skipped silently: a step that cannot run is
a failure, not a pass.

The pipeline is a *conductor*, not an instrument.  It only ever calls the
existing measurement tools; it never re-implements their logic and never
edits the remake tree or the reverse-engineering tree.

Modules
-------
``run_pipeline.py``
    The conductor: the twelve steps, the receipt and the package.
``smoke_rom.py``
    Step 3: the ROM runs 4096 frames and the Chinese title screen renders.
``capture_blackfade.py``
    Step 9's capture: the read-only ``capture_frames.lua`` of the black field
    stream, driven with the same environment contract.  It exists because
    ``tools/s49_blackfade/blackfade_capture.py`` reads an argument its own
    parser never defines and therefore cannot be run.
``make_report.py``
    Fills the 1:1 fidelity report draft from the receipt.
``run_unit_tests.sh``
    Compiles and runs every unit test of a directory and writes a TSV whose
    names the ratchet gate compares against the HEAD baseline.
"""

__all__ = ["PIPELINE_VERSION", "STEPS"]

PIPELINE_VERSION = "s49-package/1"

STEPS = (
    (1, "build", "构建重制 ROM（WSL，必须导出 LIBBUTANOABS）"),
    (2, "unit-tests", "重制线单元测试【棘轮式：与 HEAD 基线对照】"),
    (3, "smoke", "ROM 4096 帧冒烟不崩 + 中文标题画面正常"),
    (4, "headless", "无窗口无声门禁"),
    (5, "judgment", "判定台：残差分解（配对差/产品差/一致）+ 三桶分类"),
    (6, "overlay", "覆盖层逐格族名对拍"),
    (7, "idle-frames", "静止帧门禁"),
    (8, "outline-wave", "描边波门禁（200/200）"),
    (9, "blackfade", "黑场真值"),
    (10, "audio", "音频事件级对照"),
    (11, "save-boundary", "存档/边界收据（--repeat 2）"),
    (12, "package", "打包：ROM + 复现命令 + 收据 JSON"),
)
