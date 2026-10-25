#!/usr/bin/env python3
"""The S49 packaging pipeline: source tree -> shippable package, one command.

    python tools/s49_package/run_pipeline.py

Twelve steps, each independently re-runnable (``--only N`` / ``--from N`` /
``--to N``), each with an explicit success criterion, and the first failing
step makes the pipeline exit non-zero.  Nothing is skipped silently: a step
that cannot run is a failure, not a pass.

    1  build            build the remake ROM (WSL, LIBBUTANOABS exported)
    2  unit-tests       the remake's unit tests, ratchet style against HEAD
    3  smoke            the ROM runs 4096 frames and shows the Chinese title
    4  headless         the recording chain is headless and silent
    5  judgment         the judgment bench: residual + attribution + buckets
    6  overlay          the overlay's per-cell family comparison
    7  idle-frames      the static frame gate
    8  outline-wave     the outline wave gate (200/200)
    9  blackfade        the black field truth table
    10 audio            the audio event level comparison
    11 save-boundary    the save / boundary receipt
    12 package          ROM + repro commands + receipt JSON

The pipeline is a **conductor**, not an instrument.  It only calls the
measurement tools that already exist; it never re-implements their logic and
it never touches the remake tree or the reverse-engineering tree.

The ratchet
-----------
Some measurements cannot be "zero" yet (the residual is still 1940 px, the
overlay families are not aligned, ...).  Those steps are gated against a
**pinned baseline** instead of an absolute threshold: the measurement may
only get better.  Steps whose criterion is absolute (the build, the smoke
test, the gates that are green today) are gated absolutely.

The judgment bench's baseline is the **accepted receipt of the last green
wave** (``build/s49-package/baseline-accepted/``).  It deliberately lives
*outside* every package directory: wave 14 measured a residual that grew by
+9,359 px and the ratchet did not catch it, because the baseline lived
inside the package directory and a run in a new package directory started
from the wave-4 reference report (168,357 px) instead of wave 13's
accepted receipt (100,210 px).  Only a receipt that is green all the way
(``ok: true`` and ``failed_step: null``) may become the baseline.

When the ROM changed between the baseline and this run, the two residual
numbers are not the same measurement.  The ratchet then reports
**incomparable** (the bench exits with code 2) -- never a silent pass.
A residual that got bigger is a failure in either case.

``--selftest-break STEP`` proves that a broken step really turns the pipeline
red; each step documents what exactly is broken.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

# os.path.abspath, not Path.resolve(): the repository is reached through
# a directory junction (D:\Github\gba-naruto -> D:\Shell\Github\gba-naruto)
# and resolving it would report the junction target instead of the path the
# user actually invoked.
HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
# The accepted ratchet baseline lives in the judgment bench's own package
# (``tools/s49_fidelity_report/``); it is used read/write by this flow only.
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report import accepted as accepted_module  # noqa: E402

DEFAULT_REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
DEFAULT_PACKAGE_DIR = REPO / "build" / "s49-package"
# The accepted ratchet baseline.  It is **outside** every package directory
# on purpose (wave 15 / W2): a run in a new package directory must still be
# compared with the last wave that was accepted, not with a historical
# reference report.
DEFAULT_ACCEPTED_BASELINE = REPO / "build" / "s49-package" / "baseline-accepted"
WSL_DISTRO = "Ubuntu-24.04"
PIPELINE_VERSION = "s49-package/1"

STEPS: tuple[tuple[int, str, str], ...] = (
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
STEP_NAMES = {name: number for number, name, _title in STEPS}

# --- the parallel-build collision policy -----------------------------------
# Several wave streams build the very same ``butano-sequel.gba`` at the same
# time.  Two ``objcopy`` processes writing the same output file collide and
# one of them fails with "Invalid argument".  That is a collision, not a
# broken tree: wait a minute and try again.
BUILD_MAX_ATTEMPTS = 5
BUILD_RETRY_WAIT_S = 60


def is_objcopy_collision(tail: str, log: pathlib.Path | None = None,
                         since: int = 0) -> bool:
    """True when *this* attempt looks like the parallel objcopy collision.

    ``since`` is the byte offset the attempt's log section starts at, so an
    earlier attempt's message can never make a later, different failure look
    like a collision.
    """
    text = tail or ""
    if log is not None and log.is_file():
        try:
            with open(log, "rb") as handle:
                handle.seek(since)
                text = handle.read().decode("utf-8", errors="replace")
        except OSError:
            pass
    return ("objcopy" in text and "Invalid argument" in text)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: pathlib.Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fresh(path: pathlib.Path) -> pathlib.Path:
    """Delete a step's output so a stale file can never pass as a fresh one."""
    if path.is_file():
        path.unlink()
    return path


def wsl_path(path: pathlib.Path) -> str:
    """``D:\\a\\b`` -> ``/mnt/d/a/b``."""
    text = str(path).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        return "/mnt/" + text[0].lower() + text[2:]
    return text


# The manifest describes what ships.  The intermediate captures under
# ``work/`` and the re-derivable HEAD snapshot are scratch, not parts of the
# package, so they are left out (they are listed in the receipt).  The
# self-test scratch directory is scratch too: it holds a deliberately broken
# copy of the test tree and a whole second package, and including it once
# inflated the manifest from 122 files to 714.
MANIFEST_EXCLUDED_PARTS = ("work", "head-snapshot", "selftest-scratch")


def _is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    """Is *path* inside *root*?  Both are compared in absolute form."""
    try:
        pathlib.Path(os.path.abspath(str(path))).relative_to(
            pathlib.Path(os.path.abspath(str(root))))
        return True
    except ValueError:
        return False


def write_manifest(package: pathlib.Path, exclude_roots=()) -> int:
    """Write ``package/manifest.json``; return the number of listed files."""
    manifest = []
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(package).as_posix()
        parts = relative.split("/")
        if path.name == "manifest.json" or path.name == "head.tar":
            continue
        if any(part in MANIFEST_EXCLUDED_PARTS for part in parts):
            continue
        if any(part.startswith("_") for part in parts):
            # underscore-prefixed files are scratch, not part of the package
            continue
        if any(_is_under(path, root) for root in exclude_roots):
            # the accepted ratchet baseline is state, not a shipped artifact
            continue
        manifest.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    write_json(package / "manifest.json", {
        "schema": "konoha.s49-package.manifest.v1",
        "generated_at": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "files": manifest,
    })
    return len(manifest)


def verify_manifest(package: pathlib.Path) -> list[str]:
    """Return the files whose sha256 on disk does not match the manifest.

    An empty list means the manifest really describes the package.  This is
    the check the packaging step's criterion asks for; it is deliberately a
    re-read of the disk rather than a trust of what was just written, because
    the receipt itself is rewritten after the step finished.
    """
    manifest_path = package / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"manifest.json is not valid JSON ({error})"]
    stale = []
    for entry in document.get("files", []):
        relative = entry.get("path")
        path = package / relative
        if not path.is_file():
            stale.append(f"{relative} (missing)")
            continue
        actual = sha256_file(path)
        if actual != entry.get("sha256"):
            stale.append(f"{relative} (sha256 {actual[:12]} != "
                         f"{str(entry.get('sha256'))[:12]})")
    return stale


class Context:
    """Everything a step needs: the paths, the receipt and the baseline."""

    def __init__(self, args):
        self.args = args
        self.remake_root = pathlib.Path(args.remake_root)
        self.game = self.remake_root / "butano-sequel" / "game"
        self.rom = self.remake_root / "butano-sequel" / "butano-sequel.gba"
        self.elf = self.remake_root / "butano-sequel" / "butano-sequel.elf"
        self.out = pathlib.Path(args.out)
        self.work = self.out / "work"
        self.evidence = self.out / "evidence"
        self.logs = self.out / "logs"
        self.baseline = self.out / "baseline"
        # The **accepted** ratchet baseline: the receipt of the last wave
        # that was green all the way.  It lives outside the package
        # directory so that a run in a new package directory is still
        # compared with the previous wave (wave 15 / W2).
        self.accepted_root = pathlib.Path(
            os.path.abspath(str(getattr(args, "accepted_baseline", None)
                                or DEFAULT_ACCEPTED_BASELINE)))
        self.accepted = accepted_module.AcceptedBaseline(self.accepted_root)
        # The ratchet verdict of this run ("pass" / "fail" /
        # "incomparable"), copied into the receipt.
        self.ratchet_verdict: dict = {}
        # The pinned ROM: the exact bytes every later step measures and the
        # package ships.  It lives under ``work/`` so it is scratch (and is
        # left out of the manifest); step 12 copies it into ``rom/``.
        # The path is **absolute**: the measurement tools hand the ROM to the
        # probe, which runs in its own working directory, so a relative path
        # cannot be opened ("ERR cannot open ...").
        self.pinned_rom = (pathlib.Path(os.path.abspath(str(self.out)))
                           / "work" / "pinned-rom" / "measured.gba")
        self.rom_pinned = False
        self.receipt: dict = {}
        self.baseline_state: dict = {}
        self.break_step = args.selftest_break
        # How many times the judgment bench reads itself.  A reading that is
        # not reproducible cannot be compared with a baseline reading, so the
        # bench is read three times and the three readings have to agree.
        self.judgment_repeat = max(1, int(getattr(args, "judgment_repeat", 3)))

    def prepare(self) -> None:
        for directory in (self.out, self.work, self.evidence, self.logs,
                          self.baseline):
            directory.mkdir(parents=True, exist_ok=True)
        path = self.baseline / "baseline.json"
        if path.is_file():
            try:
                self.baseline_state = json.loads(
                    path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.baseline_state = {}
        self.baseline_state.setdefault("schema", "konoha.s49-package.baseline.v1")
        self.baseline_state.setdefault("steps", {})

    def save_baseline(self) -> None:
        self.baseline_state["pinned_at"] = datetime.datetime.now(
        ).astimezone().isoformat(timespec="seconds")
        write_json(self.baseline / "baseline.json", self.baseline_state)

    def pinned(self, name: str) -> dict:
        return (self.baseline_state.get("steps") or {}).get(name, {})

    def pin(self, name: str, metrics: dict) -> None:
        self.baseline_state.setdefault("steps", {})[name] = {
            "metrics": metrics,
            "pinned_at": datetime.datetime.now().astimezone().isoformat(
                timespec="seconds"),
        }

    def log_path(self, number: int, name: str) -> pathlib.Path:
        return self.logs / f"step-{number:02d}-{name}.log"

    def pin_rom(self, expected_sha: str, attempts: int = 5,
                wait_s: int = 5) -> tuple[bool, str]:
        """Pin the built ROM so every later step measures **the same bytes**.

        Several streams build the very same ``butano-sequel.gba`` in
        parallel.  A rebuild between step 1 and step 12 silently swaps the
        ROM under the pipeline: the measurements then belong to one ROM and
        the package ships another.  That was observed in wave 12 (build step
        sha ``b6c2a05f…`` vs packaged sha ``196417ca…``).

        The fix is to copy the freshly built ROM into the package directory
        once, and to point every later step at that copy.  The copy is
        verified against the build step's sha256 (a parallel ``objcopy``
        writing the file at that instant can produce a truncated copy, so
        the copy is retried).

        Returns ``(ok, detail)``.
        """
        self.pinned_rom.parent.mkdir(parents=True, exist_ok=True)
        detail = ""
        for attempt in range(1, attempts + 1):
            try:
                shutil.copyfile(self.rom, self.pinned_rom)
            except OSError as error:
                detail = f"copy failed: {error}"
                time.sleep(wait_s)
                continue
            actual = sha256_file(self.pinned_rom)
            if actual == expected_sha:
                self.rom = self.pinned_rom
                self.rom_pinned = True
                return True, (f"pinned {self.pinned_rom} "
                              f"(sha256 {actual[:16]}…)")
            detail = (f"attempt {attempt}: the copy's sha256 {actual[:16]}… "
                      f"does not match the build's {expected_sha[:16]}… "
                      "(another stream is writing the same file)")
            time.sleep(wait_s)
        return False, detail


class StepRun:
    """The record of one step."""

    def __init__(self, number: int, name: str, title: str, criterion: str):
        self.number = number
        self.name = name
        self.title = title
        self.criterion = criterion
        self.ok = False
        self.exit_code = None
        self.duration_s = 0.0
        self.commands: list[str] = []
        self.artifacts: list[str] = []
        self.metrics: dict = {}
        self.notes: list[str] = []
        self.problems: list[str] = []

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "title": self.title,
            "criterion": self.criterion,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "duration_s": round(self.duration_s, 2),
            "commands": self.commands,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "notes": self.notes,
            "problems": self.problems,
        }


def run_command(command: list[str], log: pathlib.Path, cwd=None,
                env=None, timeout: int = 3600) -> tuple[int, str]:
    """Run a command, tee its output into ``log``; return (exit code, tail)."""
    log.parent.mkdir(parents=True, exist_ok=True)
    printable = " ".join(command)
    started = time.time()
    with open(log, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"\n$ {printable}\n")
        handle.flush()
        try:
            completed = subprocess.run(
                command, cwd=cwd, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout)
            code = completed.returncode
            output = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired as error:
            code = 124
            output = (error.stdout or "") if isinstance(error.stdout, str) else ""
            output += f"\nTIMEOUT after {timeout}s\n"
        handle.write(output)
        handle.write(f"\n[exit {code} in {time.time() - started:.1f}s]\n")
    tail = "\n".join(output.splitlines()[-40:])
    return code, tail


# --------------------------------------------------------------------------
# step 1 -- build
# --------------------------------------------------------------------------
# --- the settle window ----------------------------------------------------
# Z4's lesson: the pipeline was run **three times** and the first two were
# red, both times because another stream rebuilt the ROM while this one was
# building or pinning it (wave 14 run 2: the build produced 94ef708e… and
# the ROM on disk was already ec5b5273… when the pin ran, so the ROM could
# not be pinned).  The wait below removes that race: before the build
# starts, the ROM on disk has to sit still for ``--rom-settle-seconds``
# (150 s by default) and no recorder probe may be running.
PROBE_PROCESS_NAME = "mgba-probe.exe"


def probe_processes() -> list[str]:
    """The recorder probes that are running right now (empty on non-Windows).

    The recorder eats 7-8 GB and leaks; a probe that is running while the
    pipeline builds is both the reason the ROM moves and the reason the
    capture in step 5 gets killed.
    """
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {PROBE_PROCESS_NAME}", "/NH",
             "/FO", "CSV"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in (result.stdout or "").splitlines():
        if PROBE_PROCESS_NAME.lower() in line.lower():
            rows.append(line.strip())
    return rows


def wait_for_rom_stable(ctx: Context, run: StepRun, stable_s: int,
                        max_wait_s: int, poll_s: int = 5) -> dict:
    """Wait until the ROM on disk sits still and no probe is recording.

    Returns the measurements of the wait, so the receipt can show how long
    the pipeline waited and what it waited for.
    """
    started = time.time()
    signature = None
    unchanged_since = None
    probes: list[str] = []
    gave_up = False
    reason = ""
    while True:
        now = time.time()
        current = None
        if ctx.rom.is_file():
            stat = ctx.rom.stat()
            current = (stat.st_size, stat.st_mtime_ns)
        if current is None:
            reason = "the ROM does not exist yet => there is nothing to settle"
            break
        if current != signature:
            signature = current
            unchanged_since = now
        running = probe_processes()
        if running:
            probes.extend(running)
        stable_for = now - (unchanged_since or now)
        if not running and stable_for >= stable_s:
            reason = (f"the ROM has not changed for {stable_for:.0f}s and no "
                      f"{PROBE_PROCESS_NAME} is running")
            break
        if now - started >= max_wait_s:
            gave_up = True
            reason = (f"gave up after {max_wait_s}s (stable for "
                      f"{stable_for:.0f}s, {len(probes)} probe line(s) seen)")
            break
        time.sleep(poll_s)
    waited = time.time() - started
    metrics = {
        "waited_s": round(waited, 1),
        "stable_seconds_required": stable_s,
        "max_wait_seconds": max_wait_s,
        "gave_up": gave_up,
        "reason": reason,
        "probe_processes_seen": len(probes),
    }
    if ctx.rom.is_file():
        metrics["rom_sha256_before_build"] = sha256_file(ctx.rom)
        metrics["rom_mtime"] = datetime.datetime.fromtimestamp(
            ctx.rom.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    run.notes.append(f"settle window: waited {waited:.0f}s before building "
                     f"({reason})")
    return metrics


def step_build(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "构建之前先等「ROM 文件连续 150 s 不变 + 没有 mgba-probe.exe 在跑」"
        "（Z4 的教训：并行流同期重建 ROM 会让步骤 1/5 变红）；"
        "WSL 里的 make 成功（LIBBUTANOABS 已导出），且产出 "
        "butano-sequel.gba；ROM 的 sha256 与字节数写进收据")
    # --- the settle window comes first -----------------------------------
    # Another stream rebuilding the ROM between the build and the pin is
    # exactly what made wave 14 red twice.
    settle = wait_for_rom_stable(
        ctx, run,
        stable_s=max(0, int(getattr(ctx.args, "rom_settle_seconds", 150))),
        max_wait_s=max(0, int(getattr(ctx.args, "rom_settle_max_seconds",
                                      900))))
    run.metrics = {"settle_window": settle}
    script = (
        "cd {game} && source /opt/devkitpro/devkitarm.sh && "
        "export LIBBUTANOABS={butano_abs} && make -j4"
    ).format(game=wsl_path(ctx.remake_root / "butano-sequel"),
             butano_abs=wsl_path(ctx.remake_root / "third_party" / "butano"
                                 / "butano"))
    command = ["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc", script]
    run.commands.append(" ".join(command))
    if ctx.break_step == "build":
        # A real failure: build a directory that does not exist.
        command = ["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc",
                   "cd /mnt/d/__x4_selftest__missing__ && make -j4"]
        run.commands.append("SELFTEST " + " ".join(command))
        run.notes.append(
            "selftest: the build was pointed at a directory that does not "
            "exist, so make really fails")
    log = ctx.log_path(run.number, run.name)
    log.parent.mkdir(parents=True, exist_ok=True)
    offset = log.stat().st_size if log.is_file() else 0
    code, tail = run_command(command, log, timeout=3600)
    run.exit_code = code
    # The remake tree is built by several streams in parallel.  Two objcopy
    # processes writing the same .gba collide and one of them fails with
    # "Invalid argument"; that is a *collision*, not a broken tree.  Wait 60
    # seconds and retry, at most BUILD_MAX_ATTEMPTS times in total.  A failure
    # that is not an objcopy collision is a real failure and is not retried.
    attempts = 1
    while code != 0 and ctx.break_step != "build" and attempts < BUILD_MAX_ATTEMPTS:
        if not is_objcopy_collision(tail, log, offset):
            break
        attempts += 1
        run.notes.append(
            f"build attempt {attempts - 1} failed with exit code {code} "
            "(objcopy collision: another stream is writing the same .gba); "
            f"waiting {BUILD_RETRY_WAIT_S}s and retrying")
        time.sleep(BUILD_RETRY_WAIT_S)
        offset = log.stat().st_size if log.is_file() else 0
        code, tail = run_command(command, log, timeout=3600)
        run.exit_code = code
    if code != 0:
        run.problems.append(f"the WSL build failed with exit code {code}")
        return False
    if not ctx.rom.is_file():
        run.problems.append(f"the build produced no ROM at {ctx.rom}")
        return False
    built_sha = sha256_file(ctx.rom)
    run.metrics.update({
        "rom": str(ctx.rom),
        "rom_sha256": built_sha,
        "rom_bytes": ctx.rom.stat().st_size,
        "rom_mtime": datetime.datetime.fromtimestamp(
            ctx.rom.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
    })
    run.artifacts.append(str(ctx.rom))
    # Pin the bytes: from here on every step measures -- and the package
    # ships -- this exact copy, so a parallel rebuild cannot swap the ROM
    # under the pipeline half way through the run.
    pinned_ok, pinned_detail = ctx.pin_rom(built_sha)
    if not pinned_ok:
        run.problems.append(
            "could not pin the built ROM for the rest of the run: "
            + pinned_detail)
        return False
    run.metrics["pinned_rom"] = str(ctx.pinned_rom)
    run.metrics["pinned_rom_sha256"] = sha256_file(ctx.pinned_rom)
    run.notes.append(pinned_detail + " -- every later step measures this "
                     "copy and the package ships it")
    return True


# --------------------------------------------------------------------------
# step 2 -- unit tests, ratchet style
# --------------------------------------------------------------------------
def _unit_test_side(ctx: Context, run: StepRun, label: str, tests: pathlib.Path,
                    include: pathlib.Path, tsv: pathlib.Path) -> dict:
    script = HERE / "run_unit_tests.sh"
    command = ["wsl", "-d", WSL_DISTRO, "--", "bash",
               wsl_path(script), wsl_path(tests), wsl_path(include),
               wsl_path(tsv)]
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=3600)
    failures = []
    passes = []
    if tsv.is_file():
        for line in tsv.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            name = parts[0]
            (passes if parts[1] == "pass" else failures).append(name)
    else:
        run.problems.append(f"the {label} unit test run wrote no TSV")
    run.notes.append(f"{label}: exit {code}, {len(passes)} pass, "
                     f"{len(failures)} fail")
    return {"exit_code": code, "pass": len(passes), "fail": len(failures),
            "failing": sorted(failures), "passing": len(passes)}


def step_unit_tests(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "工作区的单测失败集合必须是 HEAD 基线失败集合的子集（HEAD 就有的 "
        "20 项红是预存债，不是回归）；比 HEAD 多出来的任何一项 ⇒ 变红；"
        "少掉的任何一项（被顺手修好了）⇒ 记为改进，不判红")

    baseline_root = ctx.baseline / "head-snapshot"
    # NOTE: ``git -C <repo> archive --output=<path>`` resolves the output path
    # against **git's own working directory** (the remake repository), not the
    # process working directory.  A relative path therefore lands in the wrong
    # tree and fails with "could not open ... for writing".  Use an absolute
    # path, and make sure the parent directory exists before the call.
    ctx.baseline.mkdir(parents=True, exist_ok=True)
    tar_path = (ctx.baseline / "head.tar").resolve()
    if ctx.break_step == "unit-tests":
        # A real regression: the test directory is copied aside and one extra
        # test is added that always fails.  The remake tree itself is never
        # touched.
        pass

    # --- the HEAD baseline snapshot (read-only on the remake repository) ---
    head = subprocess.run(
        ["git", "-C", str(ctx.remake_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    head_sha = head.stdout.strip()
    if head.returncode != 0 or not head_sha:
        run.problems.append("could not read the remake repository's HEAD")
        return False
    if baseline_root.exists():
        shutil.rmtree(baseline_root)
    baseline_root.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(ctx.remake_root), "archive", "--format=tar",
         "--output=" + str(tar_path), head_sha, "butano-sequel/game"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if archive.returncode != 0:
        run.problems.append(f"git archive failed: {archive.stderr.strip()}")
        return False
    extract = subprocess.run(
        ["tar", "-xf", str(tar_path), "-C", str(baseline_root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if extract.returncode != 0:
        run.problems.append(f"tar failed: {extract.stderr.strip()}")
        return False
    base_game = baseline_root / "butano-sequel" / "game"

    # --- the workspace side -------------------------------------------------
    tests = ctx.game / "tests"
    include = ctx.game / "include"
    if not tests.is_dir() or not include.is_dir():
        run.problems.append(f"the remake's test tree is missing: {tests}")
        return False

    workspace_tests = tests
    workspace_include = include
    if ctx.break_step == "unit-tests":
        workspace_tests = ctx.work / "selftest-tests"
        workspace_include = include
        if workspace_tests.exists():
            shutil.rmtree(workspace_tests)
        shutil.copytree(tests, workspace_tests)
        (workspace_tests / "test_x4_selftest_broken.cpp").write_text(
            "// Added by the pipeline's self test on purpose: it always fails.\n"
            "int main() { return 1; }\n", encoding="utf-8", newline="\n")
        run.notes.append(
            "selftest: a deliberately failing test was added to a *copy* of "
            "the test directory, so the ratchet sees a new failure")

    head_result = _unit_test_side(
        ctx, run, "HEAD", base_game / "tests", base_game / "include",
        ctx.baseline / "unit-tests-head.tsv")
    workspace_result = _unit_test_side(
        ctx, run, "workspace", workspace_tests, workspace_include,
        ctx.baseline / "unit-tests-workspace.tsv")

    head_fail = set(head_result["failing"])
    workspace_fail = set(workspace_result["failing"])
    new_failures = sorted(workspace_fail - head_fail)
    fixed = sorted(head_fail - workspace_fail)

    run.metrics = {
        "head_commit": head_sha,
        "head": {k: v for k, v in head_result.items() if k != "failing"},
        "workspace": {k: v for k, v in workspace_result.items()
                      if k != "failing"},
        "head_failing": sorted(head_fail),
        "workspace_failing": sorted(workspace_fail),
        "new_failures": new_failures,
        "fixed_since_head": fixed,
        "debt": "the failures that are already red in HEAD are pre-existing "
                "debt, not a regression of this wave",
    }
    run.artifacts.extend([
        str(ctx.baseline / "unit-tests-head.tsv"),
        str(ctx.baseline / "unit-tests-workspace.tsv"),
    ])
    if new_failures:
        run.problems.append(
            "new unit test failures compared with the HEAD baseline: "
            + ", ".join(new_failures))
    if fixed:
        run.notes.append(
            f"{len(fixed)} test(s) that were red in HEAD are green now "
            f"(improvement, not counted as a failure): " + ", ".join(fixed))
    return not run.problems


# --------------------------------------------------------------------------
# step 3 -- smoke
# --------------------------------------------------------------------------
def step_smoke(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "探针接受了每一条命令且没有崩溃标记；4096 帧之后模拟器仍在应答；"
        "中文标题画面渲染出来（不是空白开机屏，标题带有分开的墨迹连通块）；"
        "游戏对一次按键有反应")
    out_dir = ctx.evidence / "smoke"
    fresh(out_dir / "smoke.json")
    command = [sys.executable, str(HERE / "smoke_rom.py"),
               "--rom", str(ctx.rom), "--out", str(out_dir),
               "--frames", "4096"]
    reference = ctx.baseline / "title-reference.png"
    if reference.is_file():
        command += ["--reference", str(reference)]
    if ctx.break_step == "smoke":
        # A real failure: the ROM is truncated, so the emulator cannot boot.
        broken = ctx.work / "selftest-broken.gba"
        broken.write_bytes(ctx.rom.read_bytes()[:0x8000])
        command = [sys.executable, str(HERE / "smoke_rom.py"),
                   "--rom", str(broken), "--out", str(out_dir),
                   "--frames", "4096", "--probe-timeout", "30"]
        run.notes.append("selftest: the ROM was truncated to 32 KiB, so the "
                         "emulator really cannot boot")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=600)
    run.exit_code = code
    receipt = out_dir / "smoke.json"
    if receipt.is_file():
        document = json.loads(receipt.read_text(encoding="utf-8"))
        run.metrics = document.get("metrics", {})
        run.metrics["frames_run"] = document.get("frames_run")
        run.metrics["problems"] = document.get("problems")
        if not document.get("ok"):
            run.problems.extend(document.get("problems") or ["the smoke test failed"])
        run.artifacts.append(str(receipt))
    else:
        run.problems.append("the smoke test wrote no receipt")
    if code != 0 and not run.problems:
        run.problems.append(f"the smoke test failed with exit code {code}")
    # pin the reference title frame on the first successful run
    title = out_dir / "frame-title.png"
    if title.is_file() and not reference.is_file():
        reference.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(title, reference)
        run.notes.append(f"pinned the reference title frame: {reference}")
        run.artifacts.append(str(reference))
    return not run.problems


# --------------------------------------------------------------------------
# step 4 -- headless
# --------------------------------------------------------------------------
def step_headless(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "探针的导入表里没有窗口或音频后端（USER32/winmm/SDL/OpenAL…），"
        "实跑录制期间探针不拥有任何顶层窗口")
    command = [sys.executable,
               str(REPO / "tools" / "mgba_probe" / "verify_headless_recording.py")]
    if ctx.break_step == "headless":
        # A real failure: the same instrument is run against a *copy* of the
        # probe whose import table was corrupted, so it really finds a window
        # dependency.  The shared probe binary is never touched.
        sandbox = ctx.work / "selftest-headless"
        (sandbox / "tools" / "mgba_probe").mkdir(parents=True, exist_ok=True)
        (sandbox / "build" / "mgba-probe").mkdir(parents=True, exist_ok=True)
        (sandbox / "rom").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / "tools" / "mgba_probe" / "verify_headless_recording.py",
                        sandbox / "tools" / "mgba_probe" / "verify_headless_recording.py")
        shutil.copyfile(ctx.rom, sandbox / "rom" / "base.gba")
        data = bytearray((REPO / "build" / "mgba-probe" / "mgba-probe.exe")
                         .read_bytes())
        index = data.find(b"user32.dll")
        if index < 0:
            run.problems.append("the selftest could not find user32.dll in "
                                "the probe's import table")
            return False
        data[index:index + 10] = b"usxr32.dll"
        (sandbox / "build" / "mgba-probe" / "mgba-probe.exe").write_bytes(bytes(data))
        command = [sys.executable,
                   str(sandbox / "tools" / "mgba_probe" / "verify_headless_recording.py")]
        run.notes.append(
            "selftest: the instrument was run against a copy of the probe "
            "whose import table names a window library, so it really fires")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=600)
    run.exit_code = code
    if code != 0:
        run.problems.append(f"the headless gate failed with exit code {code}")
    return not run.problems


# --------------------------------------------------------------------------
# step 5 -- the judgment bench
# --------------------------------------------------------------------------
def step_judgment(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "判定台产出了报告，且残差 / 归因 / 三桶分类都在；"
        "残差没有比**上一波被接受的收据**（棘轮基线）变大；"
        "基线 ROM 与本次 ROM 不同时报「不可比」，不许静默 PASS；"
        "⭐ 同一个 ROM 连读 3 次，3 次读数逐项相同（读数不确定 ⇒ 棘轮会误报）")
    report_dir = ctx.work / "s49-report"
    report_path = fresh(report_dir / "report.json")
    command = [sys.executable, str(REPO / "tools" / "s49_fidelity_report.py"),
               "--out", str(report_path), "--work-dir", str(report_dir),
               "--quiet"]
    if ctx.rom_pinned:
        # Measure the **pinned** bytes, not whatever is on disk right now.
        command += ["--remake-rom", str(ctx.rom)]
    if ctx.judgment_repeat > 1:
        command += ["--repeat", str(ctx.judgment_repeat)]
    # --- the ratchet baseline: the last wave that was **accepted** ---------
    # The baseline lives outside every package directory on purpose (wave 15
    # / W2): wave 14's residual grew by +9,359 px and the ratchet missed it
    # because the baseline died with the package directory and the new run
    # started from the wave-4 reference report (168,357 px) instead of
    # wave 13's accepted receipt (100,210 px).
    baseline_report = ctx.accepted.report_path
    if not baseline_report.is_file():
        found = accepted_module.find_last_accepted_package(REPO / "build")
        if found:
            ok, detail = accepted_module.promote_package(
                pathlib.Path(found["package"]), ctx.accepted_root,
                note="adopted as the accepted baseline because no accepted "
                     "baseline existed yet")
            if ok:
                run.notes.append(
                    "the ratchet baseline was adopted from the last accepted "
                    f"receipt on disk: {detail}")
                run.notes.append(
                    "the ratchet baseline is the accepted receipt of the last "
                    "green wave (outside the package directory), not a "
                    "historical reference report")
            else:
                run.problems.append(
                    "could not adopt an accepted ratchet baseline: " + detail)
                return False
        else:
            # Nothing green anywhere on disk: fall back to the historical
            # wave-4 seed so a fresh checkout still has a baseline, and say
            # so loudly -- this is the state wave 14 was in.
            reference_report = ctx.baseline / "reference-report.json"
            for candidate in (
                    REPO / "build" / "s49-report" / "report-w1-after.json",
                    REPO / "build" / "s49-report" / "report-w2.json",
                    REPO / "build" / "s49-report" / "report-w4.json",
                    REPO / "build" / "s49-report" / "report-main.json"):
                if candidate.is_file():
                    shutil.copyfile(candidate, reference_report)
                    run.notes.append(
                        f"seeded the reference report from {candidate}")
                    break
            if reference_report.is_file():
                shutil.copyfile(reference_report, baseline_report)
                run.notes.append(
                    "NO accepted baseline was found on disk => the ratchet "
                    "falls back to the historical wave-4 reference report; "
                    "this is the state wave 14 was in and it is NOT the "
                    "previous wave")
            else:
                run.notes.append(
                    "no ratchet baseline at all: the judgment bench runs "
                    "without a gate this time")
    if baseline_report.is_file():
        command += ["--ratchet", str(baseline_report)]
    run.commands.append(" ".join(command))
    code, tail = run_command(command, ctx.log_path(run.number, run.name),
                             timeout=3600)
    run.exit_code = code
    if not report_path.is_file():
        run.problems.append("the judgment bench produced no report")
        return False
    document = json.loads(report_path.read_text(encoding="utf-8"))
    summary = document.get("summary") or {}
    determinism = (document.get("run") or {}).get("determinism") or {}
    run.metrics = {
        "content_sha256": document.get("content_sha256"),
        "field_residual": summary.get("field_residual"),
        "full_residual": summary.get("full_residual"),
        "overlay_residual": summary.get("overlay_residual"),
        "attribution": summary.get("attribution"),
        "pairing_diff_subclasses": summary.get("pairing_diff_subclasses"),
        "confidence": summary.get("confidence"),
        "pairing_quality": summary.get("pairing_quality"),
        "black_transition_frames": summary.get("black_transition_frames"),
        "static_frames": summary.get("static_frames"),
        "determinism": determinism,
    }
    for key in ("field_residual", "attribution", "pairing_diff_subclasses"):
        if not run.metrics.get(key):
            run.problems.append(f"the report has no {key}")
    # --- the reading has to be reproducible before it can be compared -------
    if ctx.judgment_repeat > 1:
        readings = determinism.get("runs") or []
        sums = [reading.get("field_residual_sum") for reading in readings]
        if len(readings) != ctx.judgment_repeat:
            run.problems.append(
                f"the judgment bench was read {len(readings)} time(s), "
                f"{ctx.judgment_repeat} were asked for")
        if determinism.get("rom_changed"):
            # The ROM was rebuilt while the bench was reading itself: the
            # readings are not comparable at all.  Say so instead of calling
            # the bench unstable.
            run.problems.append(
                "the ROM changed between the readings of the judgment bench "
                "⇒ the comparison is void, re-run the pipeline")
        elif not determinism.get("identical"):
            run.problems.append(
                "the judgment bench is NOT deterministic: "
                + "; ".join(determinism.get("differences") or []))
        else:
            run.notes.append(
                f"the judgment bench read itself {len(readings)} times on the "
                f"same ROM and got the same numbers every time "
                f"(residual sum {sums[0] if sums else '?'} px)")
    # --- the ratchet verdict ----------------------------------------------
    ratchet = document.get("ratchet") or {}
    status = ratchet.get("status") or ("pass" if ratchet.get("ok") else "fail")
    rom = ratchet.get("rom") or {}
    run.metrics["ratchet_status"] = status
    run.metrics["ratchet_comparable"] = ratchet.get("comparable")
    run.metrics["ratchet_baseline"] = ratchet.get("baseline")
    run.metrics["ratchet_note"] = ratchet.get("note")
    ctx.ratchet_verdict = {
        "status": status,
        "comparable": ratchet.get("comparable"),
        "baseline_report": ratchet.get("baseline"),
        "baseline_rom": rom.get("baseline") or {},
        "candidate_rom": rom.get("candidate") or {},
        "rom": rom,
        "note": ratchet.get("note"),
        "field_residual_sum": (summary.get("field_residual") or {}).get("sum"),
        "checks": [
            {"label": check.get("label"), "baseline": check.get("baseline"),
             "candidate": check.get("candidate"), "ok": check.get("ok")}
            for check in (ratchet.get("checks") or [])],
    }
    if rom:
        run.metrics["ratchet_rom"] = rom
    if status == "incomparable":
        # Not a failure -- but emphatically **not** a pass: the baseline and
        # this run were measured on different ROMs, so the two residual
        # numbers are not the same measurement.  The verdict has to be
        # visible in the receipt, not buried in a log.
        run.notes.append(
            "the ratchet verdict is INCOMPARABLE: the baseline ROM differs "
            "from this run's ROM => the residual numbers are not the same "
            "measurement => this is NOT a pass")
        run.notes.append(
            f"the ratchet baseline is {ratchet.get('baseline')} "
            f"(field residual sum {ctx.ratchet_verdict['field_residual_sum']} "
            f"px this run)")
    elif status == "fail":
        run.notes.append(
            "the ratchet verdict is FAIL: the residual got bigger than the "
            "accepted baseline")
    else:
        run.notes.append(
            "the ratchet verdict is PASS: the residual did not get bigger "
            "than the accepted baseline")
    run.artifacts.append(str(report_path))
    run.artifacts.append(str(report_path.with_suffix(".md")))
    if code == 2 and status == "incomparable":
        # Exit code 2 is the bench's "not comparable" verdict: the baseline
        # ROM differs from this run's ROM, so the residual numbers are not
        # the same measurement.  It is **not** a failure of the bench -- but
        # it is also not a pass, and the receipt says so.
        run.notes.append(
            "the judgment bench reported INCOMPARABLE (exit code 2): the "
            "baseline ROM differs from this run's ROM => the residual numbers "
            "are not comparable => NOT a pass")
    elif code != 0:
        detail = "; ".join(
            f"{check.get('label')}: {check.get('baseline')} -> "
            f"{check.get('candidate')}"
            for check in ratchet.get("checks", []) if not check.get("ok"))
        run.problems.append(
            "the judgment bench failed"
            + (f": the ratchet broke on {detail}" if detail else
               f" with exit code {code}"))
    if ctx.break_step == "judgment":
        # A real failure: the bench is gated against a deliberately regressed
        # report, so its own ratchet really turns red.
        regressed = ctx.work / "selftest-regressed.json"
        command = [sys.executable,
                   str(REPO / "tools" / "s49_fidelity_report" / "regressed.py"),
                   str(report_path), "--out", str(regressed)]
        run.commands.append("SELFTEST " + " ".join(command))
        run_command(command, ctx.log_path(run.number, run.name), timeout=600)
        check = [sys.executable,
                 str(REPO / "tools" / "s49_fidelity_report" / "ratchet_check.py"),
                 str(report_path), str(regressed)]
        run.commands.append("SELFTEST " + " ".join(check))
        code2, tail2 = run_command(check, ctx.log_path(run.number, run.name),
                                   timeout=600)
        run.exit_code = code2
        run.notes.append("selftest: the bench was gated against a "
                         "deliberately regressed report, so its ratchet fired")
        if code2 == 0:
            run.problems.append("the selftest did not turn the judgment "
                                "step red")
        else:
            run.problems.append("selftest: the judgment bench's own ratchet "
                                "rejected a regressed report (exit "
                                f"{code2}); see the log")
        return False
    # The accepted baseline is **not** re-pinned here: it is promoted at the
    # very end of the pipeline, and only from a run that is green all the
    # way (the receipt's ``ok``).  A run whose judgment step failed must
    # never become the thing the next wave is compared against.
    return not run.problems


# --------------------------------------------------------------------------
# step 6 -- the overlay's per-cell family comparison
# --------------------------------------------------------------------------
def _split_state(blob: bytes) -> tuple[bytes, bytes, bytes]:
    """The anchors cache stores io || pram || vram."""
    io = blob[:0x40]
    pram = blob[0x40:0x40 + 0x400]
    vram = blob[0x40 + 0x400:]
    return io, pram, vram


def step_overlay(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "逐格族名对拍跑通，且逐时刻的残差没有比钉住的基线变大（棘轮）；"
        "绝对数字写进报告")
    report_path = ctx.work / "s49-report" / "report.json"
    if not report_path.is_file():
        run.problems.append("the judgment bench report is missing; run "
                            "step 5 first")
        return False
    document = json.loads(report_path.read_text(encoding="utf-8"))
    frames = document.get("frames") or []
    best = None
    for row in frames:
        anchor = (row.get("anchor") or {}).get("remake") or {}
        overlay = anchor.get("overlay") or {}
        lit = overlay.get("lit_cells")
        if lit is None:
            continue
        if best is None or lit > best[0]:
            best = (lit, row.get("best_match"))
    if best is None:
        run.problems.append("the report has no remake overlay anchor")
        return False
    lit_cells, remake_frame = best
    run.notes.append(f"the overlay comparison uses the remake frame "
                     f"{remake_frame} (the one with the most lit cells: "
                     f"{lit_cells})")

    # ---- the candidate frames ------------------------------------------
    # Wave 10 / U4: the comparison is run over **every** remake anchor dump
    # (the instrument's own ``--vram-dir`` mode), not over the single frame
    # with the most lit cells.  Reason, measured: the original's walk shows
    # the overlay from its first step, the remake's walk only reaches the
    # overlay-displaying state at step 25 and later, so the 25 *paired*
    # frames contain **no** frame with an overlay at all.  Measuring one of
    # those is degenerate: the remake's side is empty, so the residual is the
    # original's 192 lit cells, whatever the product does.
    anchors = ctx.work / "s49-report" / "anchors" / "remake"
    if not anchors.is_dir():
        run.problems.append("the remake anchor dumps are missing; run "
                            "step 5 first")
        return False
    vram_dir = ctx.evidence / "overlay" / "vram"
    if vram_dir.exists():
        shutil.rmtree(vram_dir)
    vram_dir.mkdir(parents=True, exist_ok=True)
    dumps = sorted(anchors.glob("*.state.bin"))
    if not dumps:
        run.problems.append(f"no remake anchor dumps in {anchors}")
        return False
    for path in dumps:
        blob = path.read_bytes()
        # the anchors cache stores io || pram || vram
        (vram_dir / (path.stem + ".vram-0000.bin")).write_bytes(
            blob[0x40 + 0x400:])
    run.notes.append(f"the comparison covers all {len(dumps)} remake anchor "
                     f"dumps (the paired frames alone contain no frame with "
                     f"an overlay: the remake reaches the overlay state at "
                     f"step 25 and later)")

    out_json = fresh(ctx.evidence / "overlay" / "overlay-families.json")
    command = [sys.executable,
               str(REPO / "tools" / "s49_overlay_align" / "compare_overlay_families.py"),
               "--vram-dir", str(vram_dir), "--out", str(out_json)]
    if ctx.break_step == "overlay":
        # A real failure: the VRAM dump's overlay map is zeroed, so the tool
        # really cannot find the layer.
        broken = ctx.evidence / "overlay" / "vram-broken"
        broken.mkdir(parents=True, exist_ok=True)
        for path in sorted(vram_dir.glob("*.vram-0000.bin")):
            (broken / path.name).write_bytes(b"\x00" * len(path.read_bytes()))
        command[command.index("--vram-dir") + 1] = str(broken)
        run.notes.append("selftest: the VRAM dumps handed to the tool have an "
                         "empty overlay map, so the tool really refuses it")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=1800)
    run.exit_code = code
    if not out_json.is_file():
        run.problems.append("the overlay comparison produced no report")
        return False
    result = json.loads(out_json.read_text(encoding="utf-8"))
    moments = {}
    for name, row in (result.get("moments") or {}).items():
        residual = (row.get("original_only", 0) + row.get("remake_only", 0)
                    + row.get("family_mismatches", 0))
        moments[name] = {
            "offset": row.get("offset"),
            "both_lit": row.get("both_lit"),
            "original_only": row.get("original_only"),
            "remake_only": row.get("remake_only"),
            "family_mismatches": row.get("family_mismatches"),
            "residual": residual,
            "exact": row.get("exact"),
            "frame": row.get("frame"),
        }
    run.metrics = {"remake_frame": remake_frame, "lit_cells": lit_cells,
                   "candidate_dumps": len(dumps),
                   "anchor": result.get("anchor"),
                   "moments": moments}
    run.artifacts.append(str(out_json))

    # A measurement that saw **no** overlay at all is not a measurement: the
    # residual would be the original's lit cell count, whatever the product
    # does.  Wave 10 / U4 hit exactly that (the remake's overlay only appears
    # in the walk steps the paired frames never reach), so the step refuses
    # to call it a pass.
    measured = [name for name, row in moments.items()
                if (row.get("both_lit") or 0) > 0
                or (row.get("remake_only") or 0) > 0]
    if not measured:
        run.problems.append(
            "the overlay comparison measured nothing: no candidate frame of "
            f"the {len(dumps)} remake anchor dumps carries an overlay map "
            "(the residual would be the original's lit cells regardless of "
            "the product)")

    # ---- the two conventions on the very same dump (wave 10 / U4) -------
    # The report's section 3.1 quotes these numbers, so they have to be
    # produced by a tool that ships with the package.
    field_row = moments.get("field-frame-v1") or {}
    field_dump = field_row.get("frame")
    if field_dump:
        source = vram_dir / field_dump
        if source.is_file():
            conventions_json = ctx.evidence / "overlay" / "conventions.json"
            convention_command = [
                sys.executable,
                str(REPO / "tools" / "s49_overlay_align" / "compare_conventions.py"),
                "--vram", str(source), "--out", str(conventions_json)]
            run.commands.append(" ".join(convention_command))
            convention_code, _tail = run_command(
                convention_command, ctx.log_path(run.number, run.name),
                timeout=1800)
            run.exit_code = convention_code
            if conventions_json.is_file():
                run.artifacts.append(str(conventions_json))
            else:
                run.problems.append(
                    "the convention comparison produced no report")

    # ---- the independent review of wave 10 / U4's terrain criterion ------
    # ``find_overlay_map`` grew a terrain criterion in wave 10 (U4), which U4
    # itself reported as an overrun.  The review re-derives the answer on the
    # very same dumps this step uses, so the report's "overrun review" section
    # has numbers that trace back to this receipt.
    terrain_json = ctx.evidence / "overlay" / "terrain-review.json"
    terrain_command = [
        sys.executable,
        str(HERE / "verify_terrain_criterion.py"),
        "--vram-dir", str(vram_dir),
        "--out", str(terrain_json),
        "--label", f"wave-12/X4 review on {len(dumps)} remake anchor dumps"]
    run.commands.append(" ".join(terrain_command))
    terrain_code, _tail = run_command(
        terrain_command, ctx.log_path(run.number, run.name), timeout=3600)
    if terrain_json.is_file():
        run.artifacts.append(str(terrain_json))
        review = json.loads(terrain_json.read_text(encoding="utf-8"))
        q1 = review.get("q1_none_path_equals_pre_change") or {}
        q1b = review.get("q1_bench_reader_equals_pre_change") or {}
        q2 = review.get("q2_dumps_changed_by_the_criterion") or {}
        q3 = review.get("q3_shared_tool_table") or {}
        run.metrics["terrain_review"] = {
            "dumps": review.get("dump_count"),
            "none_path_mismatches": q1.get("mismatches"),
            "bench_reader_mismatches": q1b.get("mismatches"),
            "changed_by_criterion": q2.get("changed"),
            "unchanged_by_criterion": q2.get("unchanged"),
            "pre_change_categories": q2.get("pre_change_categories"),
            "frames_with_a_different_overlay_map": q3.get(
                "frames_with_a_different_overlay_map"),
            "moments_changed": [name for name, row in
                                (q3.get("moments") or {}).items()
                                if row.get("changed")],
            "changed_rows": [
                {"dump": row.get("dump"),
                 "pre_change": row.get("pre_change_hex"),
                 "with_terrain": row.get("with_terrain_hex")}
                for row in (q2.get("rows") or [])],
        }
        run.notes.append(
            "the terrain criterion review ran on the same "
            f"{review.get('dump_count')} dumps: the no-terrain path is "
            f"identical to the pre-change implementation on "
            f"{q1.get('mismatches')} dump(s), and the criterion changes "
            f"{q2.get('changed')} of them")
    else:
        run.problems.append(
            "the terrain criterion review produced no report (exit code "
            f"{terrain_code})")

    # ---- the per-cell property verdict ----------------------------------
    # The shared tool keeps only the aggregate counters for the best frame of
    # every moment; the 1:1 report has to give **every** remaining mismatch a
    # property verdict (product difference / stale tail of the original's
    # buffer / walk phase).  The classifier imports the shared instrument
    # read-only and keeps the per-cell rows, on the very same dumps.
    cells_json = fresh(ctx.evidence / "overlay" / "cell-classification.json")
    cells_command = [
        sys.executable,
        str(HERE / "classify_overlay_cells.py"),
        "--vram-dir", str(vram_dir),
        "--out", str(cells_json),
        "--label", f"wave-13/Y4 classification on {len(dumps)} remake anchor dumps"]
    run.commands.append(" ".join(cells_command))
    cells_code, _cells_tail = run_command(
        cells_command, ctx.log_path(run.number, run.name), timeout=1800)
    if cells_json.is_file():
        run.artifacts.append(str(cells_json))
        classification = json.loads(cells_json.read_text(encoding="utf-8"))
        cell_moments = {}
        for name, row in (classification.get("moments") or {}).items():
            cell_moments[name] = {
                "frame": row.get("frame"),
                "both_lit": row.get("both_lit"),
                "original_only": row.get("original_only"),
                "remake_only": row.get("remake_only"),
                "family_mismatches": row.get("family_mismatches"),
                "residual": row.get("residual"),
                "exact": row.get("exact"),
                "classes": row.get("classes"),
                "phase_set_original": row.get("phase_set_original"),
                "phase_set_best_frame": row.get("phase_set_best_frame"),
                "phase_shifted": row.get("phase_shifted"),
                "frames_matching_phase_set": row.get(
                    "frames_matching_phase_set"),
                "pairs": row.get("pairs"),
                "cells": row.get("cells"),
            }
        run.metrics["cell_classification"] = {
            "dump_count": classification.get("dump_count"),
            "shared_instrument_sha256": classification.get(
                "shared_instrument_sha256"),
            "class_rules": classification.get("class_rules"),
            "moments": cell_moments,
        }
        run.notes.append(
            "the per-cell property verdict ran on the same "
            f"{classification.get('dump_count')} dumps: every remaining "
            "mismatch is classified as product difference / stale tail of "
            "the original's buffer / walk phase")
    else:
        run.problems.append(
            "the per-cell property verdict produced no report (exit code "
            f"{cells_code})")

    pinned = ctx.pinned("overlay").get("metrics", {}).get("moments") or {}
    regressions = []
    for name, row in moments.items():
        before = pinned.get(name)
        if before is None:
            continue
        if row["residual"] > before.get("residual", 0):
            regressions.append(
                f"{name}: {before.get('residual')} -> {row['residual']}")
    if regressions:
        run.problems.append("the overlay residual got bigger: "
                            + "; ".join(regressions))
    if code != 0 and not run.problems:
        run.problems.append(f"the overlay comparison failed with exit code {code}")
    if not run.problems:
        ctx.pin("overlay", {"moments": moments})
    return not run.problems


# --------------------------------------------------------------------------
# step 7 -- the static frame gate
# --------------------------------------------------------------------------
def step_idle_frames(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "任何一侧都没有在波形平点之外重复同一帧")
    original = ctx.work / "s49-report" / "capture-original"
    remake = ctx.work / "s49-report" / "capture-remake"
    if not original.is_dir() or not remake.is_dir():
        run.problems.append("the judgment bench's captures are missing; run "
                            "step 5 first")
        return False
    out_json = fresh(ctx.evidence / "frame-repeat.json")
    command = [sys.executable, str(REPO / "tools" / "s49_idle_frame_repeat.py"),
               "--original", str(original), "--remake", str(remake),
               "--out", str(out_json)]
    if ctx.break_step == "idle-frames":
        # A real failure: one frame of the capture is replaced by a copy of
        # its predecessor.  The walk samples 47 GBA frames apart, so such a
        # pair can never sit on the outline wave's flat spot -- the gate
        # really has to reject it.
        broken = ctx.work / "selftest-frames"
        if broken.exists():
            shutil.rmtree(broken)
        shutil.copytree(original, broken)
        frames = sorted(broken.glob("step-*.png"))
        for index in range(1, len(frames)):
            if frames[index].stem == "step-05-A":
                shutil.copyfile(frames[index - 1], frames[index])
                break
        command[command.index("--original") + 1] = str(broken)
        run.notes.append("selftest: one capture frame was replaced by a copy "
                         "of its predecessor, so the gate really rejects the "
                         "repeat")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=1800)
    run.exit_code = code
    if out_json.is_file():
        document = json.loads(out_json.read_text(encoding="utf-8"))
        results = document.get("results") or {}
        run.metrics = {
            "rule": document.get("rule"),
            "sides": {
                side: {
                    "frames": info.get("frames"),
                    "consecutive_identical_pairs": info.get(
                        "consecutive_identical_pairs"),
                    "unexpected_pairs": info.get("unexpected_pairs"),
                    "distinct_outline_shades": info.get(
                        "distinct_outline_shades"),
                    "outline_wave_animates": info.get("outline_wave_animates"),
                }
                for side, info in results.items()
            },
        }
        run.artifacts.append(str(out_json))
    else:
        run.problems.append("the static frame gate produced no report")
    if code != 0:
        run.problems.append(f"the static frame gate failed with exit code {code}")
    return not run.problems


# --------------------------------------------------------------------------
# step 8 -- the outline wave gate
# --------------------------------------------------------------------------
def step_outline_wave(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "重制侧的待机描边波在 200 帧扫描的每一帧上都与原版一致"
        "（200/200，0 处不一致）")
    out_json = fresh(ctx.evidence / "outline-wave.json")
    command = [sys.executable, str(REPO / "tools" / "s49_idle_outline_wave.py"),
               "--out", str(out_json)]
    if ctx.break_step == "outline-wave":
        command += ["--pose", str(ctx.work / "selftest-no-pose.json")]
        run.notes.append("selftest: the pose identification was removed, so "
                         "the gate really refuses to judge")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=1800)
    run.exit_code = code
    if out_json.is_file():
        document = json.loads(out_json.read_text(encoding="utf-8"))
        run.metrics = {k: v for k, v in document.items() if k != "failures"}
        run.artifacts.append(str(out_json))
        if document.get("mismatched"):
            run.problems.append(
                f"{document['mismatched']} frame(s) disagree with the original")
        if document.get("matched") != document.get("frames"):
            run.problems.append(
                f"only {document.get('matched')}/{document.get('frames')} frames "
                "agree with the original")
    else:
        run.problems.append("the outline wave gate produced no report")
    if code != 0 and not run.problems:
        run.problems.append(f"the outline wave gate failed with exit code {code}")
    return not run.problems


# --------------------------------------------------------------------------
# step 9 -- the black field truth table
# --------------------------------------------------------------------------
def _blackfade_side(ctx: Context, run: StepRun, label: str,
                    frames_dir: pathlib.Path, out_json: pathlib.Path,
                    markdown: pathlib.Path) -> dict:
    command = [sys.executable,
               str(REPO / "tools" / "s49_blackfade" / "blackfade_report.py"),
               "--frames", str(frames_dir), "--out", str(out_json),
               "--markdown", str(markdown)]
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=1800)
    if not out_json.is_file():
        run.problems.append(f"the {label} black field report was not written")
        return {}
    document = json.loads(out_json.read_text(encoding="utf-8"))
    return {
        "exit_code": code,
        "frame_count": document.get("frame_count"),
        "event_count": document.get("event_count"),
        "events": [
            {
                "event": event.get("event"),
                "first_frame": event.get("first_frame"),
                "last_frame": event.get("last_frame"),
                "total_frames": event.get("total_frames"),
                "fade_out_frames": event.get("fade_out_frames"),
                "black_hold_frames": event.get("black_hold_frames"),
                "fade_in_frames": event.get("fade_in_frames"),
                "first_black_sha256": event.get("first_black_sha256"),
            }
            for event in document.get("events", [])
        ],
    }


def _capture_blackfade(ctx: Context, run: StepRun, label: str, rom: pathlib.Path,
                       state, keys: str, zero_frames: int,
                       frames: int) -> pathlib.Path:
    """Capture one side's black field frames with the current ROM."""
    out_dir = ctx.work / "s49-blackfade" / f"{label}-entry"
    command = [sys.executable, str(HERE / "capture_blackfade.py"),
               "--rom", str(rom), "--out", str(out_dir),
               "--keys", keys, "--zero-frames", str(zero_frames),
               "--frames", str(frames)]
    if state is not None:
        command += ["--state", str(state)]
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=900)
    receipt = out_dir / "capture.json"
    if code != 0 or not receipt.is_file():
        run.problems.append(
            f"the {label} black field capture failed (exit {code}); the "
            "upstream tool tools/s49_blackfade/blackfade_capture.py cannot be "
            "used because it reads an argument its own parser never defines")
        return out_dir
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if not document.get("frames_captured"):
        run.problems.append(
            f"the {label} black field capture produced no frame")
    run.notes.append(
        f"{label}: captured {document.get('frames_captured')} frames with the "
        f"ROM sha256 {(document.get('rom_sha256') or '')[:16]}...")
    return out_dir


def step_blackfade(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "两侧的黑场帧都用本次的 ROM 与钉住的存档重录了；"
        "原版侧每个事件都被切成淡出 / 全黑 / 淡入三段；"
        "重制侧的数字作为实测差距记进报告")
    original_rom = ctx.remake_root / "rom" / "base.gba"
    original_state = (ctx.remake_root / "artifacts" / "runtime-checkpoints"
                      / "scenario-49-battle-14-entry.ss9")
    original_dir = _capture_blackfade(ctx, run, "original", original_rom,
                                      original_state, "A*20", 0, 2030)
    remake_dir = _capture_blackfade(ctx, run, "remake", ctx.rom, None,
                                    "Down,Down,A*21", 240, 2552)
    original_frames = original_dir / "frames"
    remake_frames = remake_dir / "frames"
    if not original_frames.is_dir() or not remake_frames.is_dir():
        run.problems.append("the black field captures are missing")
        return False
    out_dir = ctx.evidence / "blackfade"
    fresh(out_dir / "blackfade-original.json")
    fresh(out_dir / "blackfade-remake.json")
    original = _blackfade_side(ctx, run, "original", original_frames,
                                out_dir / "blackfade-original.json",
                                out_dir / "blackfade-original.md")
    remake = _blackfade_side(ctx, run, "remake", remake_frames,
                             out_dir / "blackfade-remake.json",
                             out_dir / "blackfade-remake.md")
    if ctx.break_step == "blackfade":
        empty = ctx.work / "selftest-empty"
        empty.mkdir(parents=True, exist_ok=True)
        command = [sys.executable,
                   str(REPO / "tools" / "s49_blackfade" / "blackfade_report.py"),
                   "--frames", str(empty), "--out", str(out_dir / "broken.json")]
        run.commands.append("SELFTEST " + " ".join(command))
        code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                                  timeout=600)
        run.notes.append("selftest: the truth table was asked for an empty "
                         "frame directory, so the tool really fails")
        if code == 0:
            run.problems.append("the selftest did not turn the black field "
                                "step red")
        return False

    # the capture receipts are the provenance of the two frame sets
    provenance = {}
    for label, directory in (("original", original_dir),
                              ("remake", remake_dir)):
        receipt = directory / "capture.json"
        if receipt.is_file():
            document = json.loads(receipt.read_text(encoding="utf-8"))
            provenance[label] = {
                "rom_sha256": document.get("rom_sha256"),
                "state_sha256": document.get("state_sha256"),
                "frames_captured": document.get("frames_captured"),
                "keys": document.get("keys"),
            }
    run.metrics = {"original": original, "remake": remake,
                    "capture_provenance": provenance}
    run.artifacts.extend([
        str(out_dir / "blackfade-original.json"),
        str(out_dir / "blackfade-original.md"),
        str(out_dir / "blackfade-remake.json"),
        str(out_dir / "blackfade-remake.md"),
    ])
    if not original.get("events"):
        run.problems.append("the original side has no black field event")
    for event in original.get("events", []):
        if not event.get("fade_out_frames"):
            run.problems.append(
                f"original event {event.get('event')} has no fade-out frames: "
                "the truth table is not segmented")
        if not event.get("fade_in_frames"):
            run.problems.append(
                f"original event {event.get('event')} has no fade-in frames: "
                "the truth table is not segmented")
    return not run.problems


# --------------------------------------------------------------------------
# step 10 -- the audio event level comparison
# --------------------------------------------------------------------------
def step_audio(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "音频事件级对照产出了 19 个配对时刻，且两次独立跑的产物逐字节一致")
    out_dir = ctx.work / "s49-audio-l"
    fresh(out_dir / "event_diff.json")
    command = [sys.executable, str(REPO / "tools" / "s49_audio_l" / "run_all.py"),
               "--out", str(out_dir), "--repeat", "2",
               "--rom", str(ctx.rom), "--elf", str(ctx.elf)]
    if ctx.break_step == "audio":
        empty = ctx.work / "selftest-empty-audio"
        empty.mkdir(parents=True, exist_ok=True)
        command += ["--original", str(empty)]
        run.notes.append("selftest: the original side's evidence was pointed "
                         "at an empty directory, so the comparison really fails")
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=3600)
    run.exit_code = code
    event_diff = out_dir / "event_diff.json"
    if event_diff.is_file():
        document = json.loads(event_diff.read_text(encoding="utf-8"))
        rows = document.get("rows") or []
        run.metrics = {
            "rows": len(rows),
            "diff_counts": document.get("diff_counts"),
            "original_rom_sha256": document.get("original_rom_sha256"),
            "remake_rom_sha256": document.get("remake_rom_sha256"),
            "moments": [
                {"key": row.get("key"), "moment": row.get("moment"),
                 "diff": row.get("diff")}
                for row in rows
            ],
        }
        run.artifacts.append(str(event_diff))
        run.artifacts.append(str(out_dir / "event_diff.md"))
    else:
        run.problems.append("the audio event comparison produced no report")
    if code != 0:
        run.problems.append(f"the audio event comparison failed with exit "
                            f"code {code}")
    return not run.problems


# --------------------------------------------------------------------------
# step 11 -- the save / boundary receipt
# --------------------------------------------------------------------------
def step_save_boundary(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "存档 / 边界收据产出，且两次采集的 62 张镜像逐字节一致")
    receipts = REPO / "build" / "s49-save-boundary" / "receipts"
    # The receipt must be removed *before* the tool runs, so that a stale
    # one can never pass as a fresh one.
    run_all = fresh(receipts / "run_all.json")
    save_compare = receipts / "save_compare.json"
    command = [sys.executable,
               str(REPO / "tools" / "s49_save_boundary" / "run_all.py"),
               "--repeat", "2"]
    run.commands.append(" ".join(command))
    code, _tail = run_command(command, ctx.log_path(run.number, run.name),
                              timeout=3600)
    run.exit_code = code
    if not run_all.is_file():
        run.problems.append("the save / boundary receipt was not written")
        return False
    document = json.loads(run_all.read_text(encoding="utf-8"))
    identical = document.get("identical_across_runs")
    run.metrics = {
        "identical_across_runs": identical,
        "runs": document.get("runs"),
        "probe_sha256": document.get("probe_sha256"),
    }
    run.artifacts.append(str(run_all))
    if save_compare.is_file():
        compare = json.loads(save_compare.read_text(encoding="utf-8"))
        original = compare.get("original") or {}
        remake = compare.get("remake") or {}
        cross = compare.get("cross_format") or {}
        run.metrics["original"] = {
            "checkpoint_count": original.get("checkpoint_count"),
            "distinct_images": original.get("distinct_images"),
            "pre_post_differing_bytes": original.get("pre_post_differing_bytes"),
            "writes_during_battle": original.get("writes_during_battle"),
        }
        run.metrics["remake"] = {
            "checkpoint_count": remake.get("checkpoint_count"),
            "diff_erased_to_first_save": (remake.get("diff_erased_to_first_save")
                                          or {}).get("differing_bytes"),
            "diff_first_to_second_save": (remake.get("diff_first_to_second_save")
                                          or {}).get("differing_bytes"),
            "diff_second_save_to_last_battle_step": (
                remake.get("diff_second_save_to_last_battle_step") or {}
            ).get("differing_bytes"),
        }
        run.metrics["cross_format"] = {
            "differing_bytes": cross.get("differing_bytes"),
            "ranges": len(cross.get("ranges") or []),
        }
        run.artifacts.append(str(save_compare))
    if identical is not True:
        run.problems.append("the two save captures are not byte identical")
    if ctx.break_step == "save-boundary":
        # A real failure: the step's own acceptance criterion is fed a receipt
        # that says the two runs differ -- exactly the condition run_all.py
        # reports with exit code 3.
        broken = ctx.work / "selftest-run_all.json"
        broken_document = json.loads(run_all.read_text(encoding="utf-8"))
        broken_document["identical_across_runs"] = False
        write_json(broken, broken_document)
        run.notes.append("selftest: the receipt was handed the 'the two runs "
                         "differ' state, which is what run_all.py reports as "
                         "exit code 3")
        run.problems.append("selftest: the two save captures are not byte "
                            "identical")
    if code != 0 and not any("selftest" in problem for problem in run.problems):
        run.problems.append(f"the save / boundary run failed with exit code {code}")
    return not run.problems


# --------------------------------------------------------------------------
# step 12 -- the package
# --------------------------------------------------------------------------
def step_package(ctx: Context, run: StepRun) -> bool:
    run.criterion = (
        "包里放了 ROM、复现命令和收据，且包内每个文件的 sha256 都在清单里")
    package = ctx.out
    rom_dir = package / "rom"
    rom_dir.mkdir(parents=True, exist_ok=True)
    rom_copy = rom_dir / "butano-sequel.gba"
    shutil.copyfile(ctx.rom, rom_copy)
    run.artifacts.append(str(rom_copy))

    receipt_path = package / "receipt.json"
    write_json(receipt_path, ctx.receipt)
    run.artifacts.append(str(receipt_path))
    write_text(package / "receipt.md", render_receipt_markdown(ctx.receipt))
    run.artifacts.append(str(package / "receipt.md"))

    repro = package / "REPRODUCE.md"
    write_text(repro, render_reproduce(ctx))
    run.artifacts.append(str(repro))

    manifest_count = write_manifest(package, exclude_roots=(ctx.accepted_root,))
    run.artifacts.append(str(package / "manifest.json"))

    # The criterion says "every file's sha256 is in the manifest".  Prove it
    # instead of asserting it: re-read what is on disk and compare.
    stale = verify_manifest(package)
    if stale:
        run.problems.append(
            "the manifest does not match the package: " + ", ".join(stale))
    build_sha = None
    for step in ctx.receipt.get("steps", []):
        if step.get("name") == "build":
            build_sha = (step.get("metrics") or {}).get("rom_sha256")
    packaged_sha = sha256_file(rom_copy)
    run.metrics = {"packaged_files": manifest_count,
                   "rom_sha256": packaged_sha,
                   "rom_sha256_build_step": build_sha,
                   "package": str(package)}
    if ctx.rom_pinned:
        run.metrics["pinned_rom"] = str(ctx.pinned_rom)
        run.notes.append(
            "every measurement step and the package itself used the pinned "
            f"copy (sha256 {packaged_sha[:16]}...) => a parallel rebuild of "
            "the remake tree cannot swap the ROM under this run")
    if build_sha and build_sha != packaged_sha:
        # Several streams build the very same ROM.  If one of them rebuilt
        # the tree while this run was measuring it, the ROM on disk is not
        # the ROM the build step produced.  The package ships the ROM that
        # is on disk (the one the later measurement steps used), and the
        # build step's own sha stays in the receipt.
        run.notes.append(
            "the ROM was rebuilt by another stream after this run's build "
            f"step (build step sha {build_sha[:12]}..., packaged "
            f"{packaged_sha[:12]}...) => the package ships the ROM that was "
            "on disk at packaging time; both sha256 values are in the "
            "receipt")
    return True


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_receipt_markdown(receipt: dict) -> str:
    lines = [
        "# S49 出包流水线收据",
        "",
        f"- 生成时间：{receipt.get('generated_at')}",
        f"- 流水线版本：`{receipt.get('pipeline_version')}`",
        f"- 总结果：**{'PASS' if receipt.get('ok') else 'FAIL'}**",
        "",
        "| # | 步骤 | 判据 | 结果 | 耗时(s) |",
        "|---|---|---|---|---:|",
    ]
    for step in receipt.get("steps", []):
        lines.append(
            f"| {step['number']} | {step['title']} | {step['criterion']} | "
            f"{'PASS' if step['ok'] else 'FAIL'} | {step['duration_s']} |")
    lines.append("")
    verdict = receipt.get("ratchet") or {}
    if verdict:
        status = verdict.get("status")
        headline = {
            "pass": "通过（残差没有比被接受的基线变大）",
            "fail": "不通过（残差变大了）",
            "incomparable": "不可比（基线 ROM 与本次 ROM 不同 ⇒ "
                            "残差数字不是同一个测量 ⇒ 这不是通过）",
        }.get(status, status)
        lines.append("## 棘轮基线")
        lines.append("")
        lines.append(f"- 结论：**{headline}**")
        lines.append(f"- 基线收据：`{verdict.get('baseline_report')}`")
        lines.append(f"- 基线 ROM：{str((verdict.get('baseline_rom') or {}).get('remake'))[:16]}…"
                     f"　本次 ROM：{str((verdict.get('candidate_rom') or {}).get('remake'))[:16]}…")
        lines.append(f"- 本次战场区残差总和：{verdict.get('field_residual_sum')} px")
        if verdict.get("note"):
            lines.append(f"- 说明：{verdict.get('note')}")
        lines.append("")
    accepted = receipt.get("accepted_baseline") or {}
    if accepted:
        lines.append("## 被接受的基线（下一波的比较对象）")
        lines.append("")
        lines.append(f"- 位置：`{accepted.get('root')}`")
        lines.append(f"- 来源包：`{accepted.get('source_package')}`")
        lines.append(f"- 接受时间：{accepted.get('accepted_at')}")
        lines.append(f"- 战场区残差总和：{accepted.get('field_residual_sum')} px")
        lines.append("")
    promoted = receipt.get("accepted_baseline_promoted") or {}
    if promoted:
        lines.append(f"- 本次是否更新了被接受的基线："
                     f"**{'是' if promoted.get('ok') else '否'}**"
                     f"（{promoted.get('detail')}）")
        lines.append("")
    for note in receipt.get("notes", []):
        lines.append(f"> {note}")
        lines.append("")
    for step in receipt.get("steps", []):
        if not step["ok"]:
            lines.append(f"## 失败：{step['number']} {step['title']}")
            lines.append("")
            for problem in step.get("problems", []):
                lines.append(f"- {problem}")
            lines.append("")
    return "\n".join(lines) + "\n"


def render_reproduce(ctx: Context) -> str:
    return f"""# 复现命令

本机构建 **非字节可复现**（链接时间戳 / 路径进入产物），所以基线 savestate
**load 不了**本包里的 ROM。复现的办法是：**用本包里的 ROM 重录**。

## 0. 先建私有探针（不要覆盖共享的 `build/mgba-probe`）

```powershell
$env:KONOHA_PROBE_OUT='{ctx.out}\\mgba-probe-z4'
python tools/mgba_probe/build.py
```

> 共享的 `build/mgba-probe/mgba-probe.exe` 是别的流的仪器，**不要覆盖**
> （会 LNK1104）；它还是旧版（`framedump` 的参数顺序不同），只当最后兜底。

## 1. 重建 ROM（WSL，必须导出 LIBBUTANOABS）

```powershell
wsl -d {WSL_DISTRO} -- bash -lc "cd {wsl_path(ctx.remake_root / 'butano-sequel')} && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS={wsl_path(ctx.remake_root / 'third_party' / 'butano' / 'butano')} && make -j4"
```

## 2. 一条命令跑完整条流水线

```powershell
python tools/s49_package/run_pipeline.py
```

## 3. 单独重跑某一步

```powershell
python tools/s49_package/run_pipeline.py --only 5      # 判定台
python tools/s49_package/run_pipeline.py --from 9      # 从黑场真值开始
```

## 4. 本包里的 ROM

| 文件 | sha256 |
|---|---|
| `rom/butano-sequel.gba` | `{sha256_file(ctx.out / 'rom' / 'butano-sequel.gba')}` |

## 5. 收据

* `receipt.json` —— 12 步的完整收据（每个数字都能追到某一步的产物）
* `receipt.md` —— 人读的表格
* `manifest.json` —— 包内每个文件的 sha256
* `evidence/selftest-break.txt` —— 「故意破坏 ⇒ 流水线变红」的逐条证明

## 6. 故意破坏 ⇒ 流水线变红

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/s49_package/run_selftests.ps1
```

每一步都有一个 `--selftest-break <步骤>` 开关：它**弄坏该步骤的输入**
（截断的 ROM、空目录、故意失败的单测、变坏的报告……），于是该步骤自己的
判据必须亮红灯。退出码非 0 ⇒ 流水线注意到了；退出码 0 ⇒ **流水线自己有 bug**。
"""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
STEP_FUNCTIONS = {
    "build": step_build,
    "unit-tests": step_unit_tests,
    "smoke": step_smoke,
    "headless": step_headless,
    "judgment": step_judgment,
    "overlay": step_overlay,
    "idle-frames": step_idle_frames,
    "outline-wave": step_outline_wave,
    "blackfade": step_blackfade,
    "audio": step_audio,
    "save-boundary": step_save_boundary,
    "package": step_package,
}


def main() -> int:
    # The console on this machine is GBK: a character it cannot encode would
    # raise UnicodeEncodeError and turn a green step red for a trivial
    # reason.  Replacing instead of raising keeps the exit code honest.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_PACKAGE_DIR),
                        help="the package directory (default build/s49-package)")
    parser.add_argument("--remake-root", default=str(DEFAULT_REMAKE_ROOT),
                        help="the butano-sequel checkout")
    parser.add_argument("--only", type=int, default=None,
                        help="run a single step")
    parser.add_argument("--from", dest="from_step", type=int, default=None,
                        help="start at this step")
    parser.add_argument("--to", dest="to_step", type=int, default=None,
                        help="stop after this step")
    parser.add_argument("--selftest-break", default=None,
                        choices=sorted(STEP_FUNCTIONS),
                        help="deliberately break this step to prove that the "
                             "pipeline turns red")
    parser.add_argument("--fail-fast", action="store_true",
                        help="stop at the first failing step (by default every "
                             "step runs, so the receipt always covers all "
                             "twelve, and the pipeline still exits non-zero "
                             "when any step failed)")
    parser.add_argument("--judgment-repeat", type=int, default=3,
                        help="how many times step 5 reads the judgment bench; "
                             "the readings have to agree (default 3; 1 turns "
                             "the reproducibility check off)")
    parser.add_argument("--accepted-baseline", default=None,
                        help="where the accepted ratchet baseline lives "
                             "(default build/s49-package/baseline-accepted); "
                             "it is deliberately outside every package "
                             "directory")
    parser.add_argument("--accept-baseline", action="store_true",
                        help="do not run any step: promote the package in "
                             "--out to the accepted ratchet baseline.  The "
                             "package's receipt has to be green all the way "
                             "(ok: true, failed_step: null) -- a failed run "
                             "is refused")
    parser.add_argument("--rom-settle-seconds", type=int, default=150,
                        help="step 1 waits until the ROM on disk has not "
                             "changed for this many seconds before it builds "
                             "(default 150)")
    parser.add_argument("--rom-settle-max-seconds", type=int, default=900,
                        help="the longest step 1 waits for the ROM to settle "
                             "(default 900)")
    parser.add_argument("--list", action="store_true",
                        help="list the steps and exit")
    parser.add_argument("--verify-manifest", action="store_true",
                        help="do not run any step: rewrite the package's "
                             "manifest and verify it against the files on "
                             "disk (use after the self-tests added their "
                             "evidence, so the package stays self-consistent)")
    args = parser.parse_args()

    if args.verify_manifest:
        package = pathlib.Path(os.path.abspath(args.out))
        accepted_root = pathlib.Path(os.path.abspath(
            str(args.accepted_baseline or DEFAULT_ACCEPTED_BASELINE)))
        write_manifest(package, exclude_roots=(accepted_root,))
        stale = verify_manifest(package)
        listed = len(json.loads(
            (package / "manifest.json").read_text(encoding="utf-8")
        ).get("files", []))
        if stale:
            print("the manifest does not match the package: "
                  + ", ".join(stale))
            return 1
        print(f"the manifest matches the package ({listed} files)")
        return 0

    if args.accept_baseline:
        # Promote a package to the accepted ratchet baseline.  The package's
        # receipt has to be green all the way -- a failed run is refused,
        # because a failed run is exactly what the ratchet has to catch.
        accepted_root = pathlib.Path(os.path.abspath(
            str(args.accepted_baseline or DEFAULT_ACCEPTED_BASELINE)))
        package = pathlib.Path(os.path.abspath(args.out))
        ok, detail = accepted_module.promote_package(
            package, accepted_root,
            note="promoted explicitly with --accept-baseline")
        print(detail if ok else "ERR " + detail)
        if not ok:
            return 1
        store = accepted_module.AcceptedBaseline(accepted_root)
        print(f"accepted baseline: {store.report_path}")
        print(f"accepted receipt: {store.receipt_path}")
        return 0

    if args.list:
        for number, name, title in STEPS:
            print(f"{number:2d}  {name:14s}  {title}")
        return 0

    ctx = Context(args)
    ctx.prepare()

    selected = []
    for number, name, title in STEPS:
        if args.only is not None and number != args.only:
            continue
        if args.from_step is not None and number < args.from_step:
            continue
        if args.to_step is not None and number > args.to_step:
            continue
        selected.append((number, name, title))
    if not selected:
        print("ERR no step selected", file=sys.stderr)
        return 2

    receipt = {
        "schema": "konoha.s49-package.receipt.v1",
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "remake_root": str(ctx.remake_root),
        "package_dir": str(ctx.out),
        "selftest_break": ctx.break_step,
        "steps": [],
        "ok": True,
        "failed_step": None,
    }
    ctx.receipt = receipt

    failed = False
    for number, name, title in selected:
        run = StepRun(number, name, title, "see the step's own criterion")
        print(f"\n=== step {number}/{len(selected)}  {name}: {title}")
        started = time.time()
        try:
            ok = STEP_FUNCTIONS[name](ctx, run)
        except Exception as error:  # a crashed step is a failed step
            import traceback
            traceback.print_exc()
            run.problems.append(f"{type(error).__name__}: {error}")
            ok = False
        run.duration_s = time.time() - started
        run.ok = bool(ok) and not run.problems
        receipt["steps"].append(run.to_dict())
        print(f"--- step {number} {name}: {'PASS' if run.ok else 'FAIL'} "
              f"({run.duration_s:.1f}s)")
        for problem in run.problems:
            print(f"    ! {problem}")
        for note in run.notes:
            print(f"    . {note}")
        if not run.ok:
            receipt["ok"] = False
            if receipt["failed_step"] is None:
                receipt["failed_step"] = number
            failed = True
            if args.fail_fast:
                print("    (--fail-fast: stopping here)")
                break

    # --- the ratchet verdict goes into the receipt ------------------------
    # It is a **top level** field on purpose: "the pipeline is green" must
    # never hide the fact that the residual could not be compared with the
    # accepted baseline.
    receipt["ratchet"] = dict(ctx.ratchet_verdict)
    receipt["accepted_baseline"] = ctx.accepted.describe()
    receipt["notes"] = [
        "口径说明：判定台的战场区残差是 arg-min 对齐残差（不带时刻约束）；"
        "它不是任何「可证像素下界」的下界，两个口径不许混用。",
    ]
    ctx.save_baseline()
    write_json(ctx.out / "receipt.json", receipt)
    write_text(ctx.out / "receipt.md", render_receipt_markdown(receipt))
    # The receipt and the baseline are written *after* the packaging step, so
    # the manifest that step wrote is already out of date for those three
    # files.  Rewrite it here and verify it, so the package on disk really
    # matches its own manifest.
    write_manifest(ctx.out, exclude_roots=(ctx.accepted_root,))
    stale = verify_manifest(ctx.out)
    if stale:
        receipt["ok"] = False
        if receipt["failed_step"] is None:
            receipt["failed_step"] = 12
        failed = True
        print("    ! the manifest does not match the package: "
              + ", ".join(stale))
        write_json(ctx.out / "receipt.json", receipt)
        write_text(ctx.out / "receipt.md", render_receipt_markdown(receipt))
        write_manifest(ctx.out, exclude_roots=(ctx.accepted_root,))
    else:
        print("    . the manifest matches the package "
              f"({len(json.loads((ctx.out / 'manifest.json').read_text(encoding='utf-8')).get('files', []))} files)")

    # --- promote the accepted baseline ------------------------------------
    # Only a run that is green all the way may become the baseline the next
    # wave is compared with.  A failed run is refused, so a broken wave can
    # never become the reference that hides the next regression.
    promoted = None
    ran_judgment = any(step.get("name") == "judgment"
                        for step in receipt.get("steps", []))
    if receipt.get("ok") and not failed and ran_judgment:
        ok, detail = accepted_module.promote_package(
            ctx.out, ctx.accepted_root,
            note="promoted automatically: the pipeline was green all the way")
        promoted = {"ok": ok, "detail": detail}
        if ok:
            print(f"    . the accepted ratchet baseline was updated: {detail}")
        else:
            print(f"    ! the accepted ratchet baseline was NOT updated: "
                  f"{detail}")
    elif ran_judgment:
        print("    . the accepted ratchet baseline was NOT updated: this run "
              "is not green all the way, so it must not become the baseline")
    if promoted is not None:
        # The receipt has to say what happened to the baseline, and the
        # manifest has to be rewritten because the receipt changed.
        receipt["accepted_baseline_promoted"] = promoted
        receipt["accepted_baseline"] = ctx.accepted.describe()
        write_json(ctx.out / "receipt.json", receipt)
        write_text(ctx.out / "receipt.md", render_receipt_markdown(receipt))
        write_manifest(ctx.out, exclude_roots=(ctx.accepted_root,))
        stale = verify_manifest(ctx.out)
        if stale:
            receipt["ok"] = False
            if receipt["failed_step"] is None:
                receipt["failed_step"] = 12
            failed = True
            print("    ! the manifest does not match the package: "
                  + ", ".join(stale))
            write_json(ctx.out / "receipt.json", receipt)
            write_text(ctx.out / "receipt.md", render_receipt_markdown(receipt))
            write_manifest(ctx.out, exclude_roots=(ctx.accepted_root,))

    print("\n" + "=" * 70)
    verdict = receipt.get("ratchet") or {}
    status = verdict.get("status")
    if status == "incomparable":
        print(f"pipeline: {'PASS' if receipt['ok'] else 'FAIL'}"
              "  (⚠ 棘轮**不可比** —— 这不是棘轮通过)")
    else:
        print(f"pipeline: {'PASS' if receipt['ok'] else 'FAIL'}")
    if receipt["failed_step"]:
        print(f"first failing step: {receipt['failed_step']}")
    if status == "incomparable":
        print("⚠ RATCHET INCOMPARABLE: the baseline ROM "
              f"({str((verdict.get('baseline_rom') or {}).get('remake'))[:16]}…) "
              "differs from this run's ROM "
              f"({str((verdict.get('candidate_rom') or {}).get('remake'))[:16]}…) "
              "=> the residual numbers are NOT comparable => this is not a "
              "pass; the new baseline has to be accepted explicitly")
    elif status:
        print(f"ratchet: {status} (baseline "
              f"{verdict.get('baseline_report')})")
    print(f"receipt: {ctx.out / 'receipt.json'}")
    print(f"package: {ctx.out}")
    if promoted and promoted.get("ok"):
        print(f"accepted baseline: {ctx.accepted.report_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
