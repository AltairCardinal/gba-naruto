#!/usr/bin/env python3
"""Measure where the reverse-engineering pipeline is bottlenecked locally.

The reverse ledger is advanced by three very different classes of work:

* cheap static analysis (exporter/verifier/audit scripts),
* guarded heavy work (mGBA captures, formal proof replay),
* and parallel read-only reconnaissance.

They do not scale the same way, so "the pipeline is slow" is not actionable
until each class is measured separately.  This tool produces that measurement:

1. every declared stage is executed behind ``tools/run_guarded.py`` and the
   guard receipt (wall clock, peak tree RSS, exit code, rejection reason) is
   kept verbatim;
2. host samples (free disk, available physical memory, load average, CPU
   count) are captured around every stage;
3. a lock-contention probe starts two guarded runs against the same project
   lock to show whether heavy work queues or fails;
4. a CPU scaling probe starts N CPU-bound workers without any project lock to
   show how much read-only parallelism the host actually delivers.

Nothing here changes repository state beyond the output directory.  The tool
records measurements; it never promotes a claim.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCHEMA = "reverse-throughput-measurement-v1"

try:
    from tools.project_resource_guard import available_physical_memory_mib
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from project_resource_guard import available_physical_memory_mib


# --------------------------------------------------------------------------
# host sampling
# --------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sample_host(root: Path) -> dict[str, Any]:
    """Capture one host resource sample for ``root``'s filesystem."""
    usage = shutil.disk_usage(root)
    memory = available_physical_memory_mib()
    return {
        "at": _now(),
        "disk_total_gib": round(usage.total / 2**30, 2),
        "disk_available_gib": round(usage.free / 2**30, 2),
        "memory_available_mib": round(float(memory.available_physical_mib), 1),
        "memory_backend": getattr(memory, "source", "unknown"),
        "load_average_1m": round(os.getloadavg()[0], 2),
        "cpu_count": os.cpu_count(),
    }


# --------------------------------------------------------------------------
# guarded stage execution
# --------------------------------------------------------------------------


def _guard_command(
    python: str,
    command: Sequence[str],
    summary: Path,
    lock_file: Path,
    cwd: Path,
    wall_timeout_s: float,
    max_tree_rss_mib: int,
    idle_timeout_s: float,
) -> list[str]:
    return [
        python,
        str(PROJECT_ROOT / "tools" / "run_guarded.py"),
        "--summary",
        str(summary),
        "--lock-file",
        str(lock_file),
        "--cwd",
        str(cwd),
        "--wall-timeout-s",
        str(wall_timeout_s),
        "--idle-timeout-s",
        str(idle_timeout_s),
        "--max-tree-rss-mib",
        str(max_tree_rss_mib),
        "--",
        python,
        *command,
    ]


def run_stage(
    stage: dict[str, Any],
    out_dir: Path,
    python: str,
    lock_file: Path,
    cwd: Path,
) -> dict[str, Any]:
    """Run one declared stage behind the project guard and read its receipt."""
    label = stage["label"]
    summary = out_dir / f"{label}.guard.json"
    command = list(stage["command"])
    wall_timeout_s = float(stage.get("wall_timeout_s", 600))
    max_tree_rss_mib = int(stage.get("max_tree_rss_mib", 1536))
    idle_timeout_s = float(stage.get("idle_timeout_s", 60))

    before = sample_host(cwd)
    started = time.monotonic()
    completed = subprocess.run(
        _guard_command(
            python,
            command,
            summary,
            lock_file,
            cwd,
            wall_timeout_s,
            max_tree_rss_mib,
            idle_timeout_s,
        ),
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    after = sample_host(cwd)

    receipt: dict[str, Any] = {}
    if summary.exists():
        try:
            receipt = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            receipt = {"reason": "guard-summary-unparseable"}
    else:
        receipt = {"reason": "guard-summary-missing"}

    return {
        "label": label,
        "kind": stage.get("kind", "static"),
        "command": command,
        "exit_code": completed.returncode,
        "wall_seconds": round(elapsed, 2),
        "guard_reason": receipt.get("reason"),
        "guard_degraded": receipt.get("degraded"),
        "peak_tree_rss_mib": receipt.get("peak_tree_rss_mib"),
        "guard_started_at": receipt.get("started_at"),
        "guard_finished_at": receipt.get("finished_at"),
        "host_before": before,
        "host_after": after,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "summary_path": str(summary),
    }


# --------------------------------------------------------------------------
# probes
# --------------------------------------------------------------------------


def _cpu_worker_source(iterations: int) -> str:
    return (
        "import sys\n"
        f"n = {int(iterations)}\n"
        "total = 0\n"
        "for i in range(n):\n"
        "    total = (total + i * i) % 1000000007\n"
        "print(total)\n"
    )


def probe_cpu_scaling(
    workers: int, iterations: int, python: str, cwd: Path, out_dir: Path
) -> dict[str, Any]:
    """Measure how much real parallelism the host gives to CPU-bound work.

    The workers deliberately bypass the project heavy lock: they stand in for
    read-only reconnaissance, which is the class of work that is supposed to
    fan out across sub-agents.
    """
    worker = out_dir / "cpu_probe_worker.py"
    worker.write_text(_cpu_worker_source(iterations), encoding="utf-8")

    def run_serial() -> float:
        started = time.monotonic()
        for _ in range(workers):
            subprocess.run(
                [python, str(worker)],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
        return time.monotonic() - started

    serial_seconds = run_serial()

    started = time.monotonic()
    processes = [
        subprocess.Popen(
            [python, str(worker)],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(workers)
    ]
    for process in processes:
        process.wait()
    parallel_seconds = time.monotonic() - started

    speedup = serial_seconds / parallel_seconds if parallel_seconds else 0.0
    efficiency = speedup / workers if workers else 0.0
    return {
        "workers": workers,
        "iterations": iterations,
        "serial_seconds": round(serial_seconds, 3),
        "parallel_seconds": round(parallel_seconds, 3),
        "speedup": round(speedup, 3),
        "parallel_efficiency": round(efficiency, 3),
        "host": sample_host(cwd),
    }


def probe_lock_contention(
    python: str, lock_file: Path, cwd: Path, out_dir: Path
) -> dict[str, Any]:
    """Start two guarded runs against the same project lock at once.

    The project lock is non-blocking, so the loser is expected to fail fast
    with ``lock-busy`` instead of waiting.  Measuring it keeps the claim
    "heavy work cannot be parallelised" evidence-backed.
    """
    stage = {
        "label": "lock-contention-probe",
        "kind": "probe",
        "command": [
            "-c",
            "import time; time.sleep(6); print('probe-done')",
        ],
        "wall_timeout_s": 120,
    }
    summaries = [out_dir / f"lock-probe-{index}.guard.json" for index in (0, 1)]
    commands = [
        _guard_command(
            python,
            stage["command"],
            summary,
            lock_file,
            cwd,
            stage["wall_timeout_s"],
            1536,
            120,
        )
        for summary in summaries
    ]
    processes = [
        subprocess.Popen(
            command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        for command in commands
    ]
    results = []
    for process in processes:
        stdout, stderr = process.communicate()
        receipt: dict[str, Any] = {}
        summary = summaries[len(results)]
        if summary.exists():
            try:
                receipt = json.loads(summary.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                receipt = {"reason": "guard-summary-unparseable"}
        else:
            receipt = {"reason": "guard-summary-missing"}
        results.append(
            {
                "exit_code": process.returncode,
                "guard_reason": receipt.get("reason"),
                "stdout_tail": stdout[-500:],
                "stderr_tail": stderr[-500:],
            }
        )
    return {
        "lock_file": str(lock_file),
        "results": results,
        "rejected": sum(1 for item in results if item["guard_reason"] == "lock-busy"),
        "host": sample_host(cwd),
    }


# --------------------------------------------------------------------------
# bottleneck classification
# --------------------------------------------------------------------------


def classify_bottlenecks(
    stages: Iterable[dict[str, Any]],
    cpu_probe: dict[str, Any],
    lock_probe: dict[str, Any],
    host: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn the measurements into a ranked, actionable bottleneck list."""
    findings: list[dict[str, Any]] = []
    stage_list = list(stages)

    idle_killed = [
        stage
        for stage in stage_list
        if stage.get("guard_reason") == "idle-timeout"
    ]
    if idle_killed:
        findings.append(
            {
                "rank": 0,
                "bottleneck": "guard-idle-timeout-gate",
                "severity": "hard",
                "evidence": (
                    f"{len(idle_killed)} stage(s) were killed by the guard idle "
                    "timeout before finishing: "
                    + ", ".join(
                        f"{stage['label']}@{stage.get('wall_seconds')}s" for stage in idle_killed
                    )
                ),
                "impact": (
                    "the project guard default idle timeout is 60s while the "
                    "coverage audit and the formal proof replay stay silent far "
                    "longer than that; every heavy run silently dies with exit 124 "
                    "unless the timeout is raised, which looks like a hung tool "
                    "rather than a configuration gate"
                ),
                "mitigation": (
                    "pass an explicit idle-timeout-s for every stage that replays "
                    "committed verifiers, and treat exit 124 as a gate rejection "
                    "instead of a resource failure"
                ),
            }
        )

    if lock_probe.get("rejected"):
        findings.append(
            {
                "rank": 1,
                "bottleneck": "heavy-work-lock-serialization",
                "severity": "hard",
                "evidence": (
                    f"{lock_probe['rejected']}/{len(lock_probe.get('results', []))} "
                    "concurrent guarded runs were rejected with lock-busy instead of "
                    "waiting for the project heavy lock"
                ),
                "impact": (
                    "at most one guarded heavy operation (mGBA capture, formal proof "
                    "replay) can run at a time; extra sub-agents cannot add heavy "
                    "throughput, they only add rejected runs"
                ),
                "mitigation": (
                    "fan out read-only reconnaissance and static analysis; keep every "
                    "heavy stage on the single guarded path and queue it explicitly"
                ),
            }
        )

    efficiency = float(cpu_probe.get("parallel_efficiency", 0.0))
    workers = int(cpu_probe.get("workers", 0))
    if workers > 1 and efficiency < 0.6:
        findings.append(
            {
                "rank": 1,
                "bottleneck": "cpu-parallel-headroom",
                "severity": "soft",
                "evidence": (
                    f"{workers} concurrent CPU-bound workers reached only "
                    f"{efficiency:.2f} parallel efficiency "
                    f"(speedup {cpu_probe.get('speedup')}x)"
                ),
                "impact": (
                    "read-only fan-out scales sub-linearly; the host is already "
                    "busy, so adding sub-agents buys less than the nominal limit"
                ),
                "mitigation": (
                    "size the fan-out from the measured efficiency, not from the "
                    "nominal agent limit"
                ),
            }
        )

    available_gib = float(host.get("disk_available_gib", 0.0))
    if available_gib < 10.0:
        findings.append(
            {
                "rank": 2,
                "bottleneck": "disk-headroom",
                "severity": "hard" if available_gib < 3.0 else "soft",
                "evidence": f"only {available_gib} GiB available on the data volume",
                "impact": (
                    "artifact regeneration, mGBA capture and formal receipts all "
                    "write to disk; a full volume fails runs late and wastes the "
                    "compute spent before the failure"
                ),
                "mitigation": (
                    "reclaim regenerable experiment trees before starting a heavy "
                    "stage, and keep new captures under one run-id directory"
                ),
            }
        )

    memory_mib = float(host.get("memory_available_mib", 0.0))
    if memory_mib < 4096:
        findings.append(
            {
                "rank": 3,
                "bottleneck": "physical-memory-headroom",
                "severity": "soft",
                "evidence": f"{memory_mib:.0f} MiB available physical memory",
                "impact": (
                    "the project guard admits a run at 1024 MiB available and caps "
                    "a tree at 1536 MiB; several parallel trees therefore compete "
                    "for the same pages"
                ),
                "mitigation": (
                    "keep the number of concurrent heavy trees at or below the "
                    "measured memory budget rather than the agent limit"
                ),
            }
        )

    heavy = [stage for stage in stage_list if stage.get("kind") == "heavy"]
    if heavy:
        slowest = max(heavy, key=lambda stage: stage.get("wall_seconds", 0.0))
        findings.append(
            {
                "rank": 4,
                "bottleneck": "single-heavy-stage-latency",
                "severity": "soft",
                "evidence": (
                    f"slowest heavy stage '{slowest['label']}' took "
                    f"{slowest.get('wall_seconds')}s"
                ),
                "impact": (
                    "a single guarded stage can dominate a milestone's wall clock; "
                    "policy already forbids repeating a full formal audit for one "
                    "small packet"
                ),
                "mitigation": (
                    "batch packets up to the policy threshold and use the measured "
                    "stage cost to decide how many milestones fit in a session"
                ),
            }
        )

    return findings


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 逆向推进吞吐量实测")
    lines.append("")
    lines.append(f"- 采样时间：{payload['host']['at']}")
    lines.append(
        f"- 主机：{payload['host']['cpu_count']} 逻辑核，"
        f"可用磁盘 {payload['host']['disk_available_gib']} GiB，"
        f"可用物理内存 {payload['host']['memory_available_mib']} MiB，"
        f"1 分钟负载 {payload['host']['load_average_1m']}"
    )
    lines.append(f"- 解释器：{payload['interpreter']}")
    lines.append("")
    lines.append("## 各阶段实测")
    lines.append("")
    lines.append("| 阶段 | 类型 | 墙钟(s) | 峰值RSS(MiB) | 退出码 | 守卫结论 |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for stage in payload["stages"]:
        lines.append(
            f"| {stage['label']} | {stage.get('kind')} | {stage.get('wall_seconds')} | "
            f"{stage.get('peak_tree_rss_mib')} | {stage.get('exit_code')} | "
            f"{stage.get('guard_reason')} |"
        )
    lines.append("")
    lines.append("## 探针")
    lines.append("")
    cpu = payload["cpu_probe"]
    lines.append(
        f"- CPU 并行：{cpu['workers']} 工作者，串行 {cpu['serial_seconds']}s vs "
        f"并行 {cpu['parallel_seconds']}s，加速 {cpu['speedup']}x，"
        f"并行效率 {cpu['parallel_efficiency']}"
    )
    lock = payload["lock_probe"]
    lines.append(
        f"- heavy 锁争用：{lock['rejected']}/{len(lock['results'])} 个并发受管运行"
        f"被以 lock-busy 拒绝"
    )
    lines.append("")
    lines.append("## 瓶颈排序")
    lines.append("")
    for finding in payload["bottlenecks"]:
        lines.append(
            f"### {finding['rank']}. {finding['bottleneck']}（{finding['severity']}）"
        )
        lines.append("")
        lines.append(f"- 证据：{finding['evidence']}")
        lines.append(f"- 影响：{finding['impact']}")
        lines.append(f"- 处置：{finding['mitigation']}")
        lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure local throughput limits of the reverse pipeline."
    )
    parser.add_argument("--spec", type=Path, help="JSON stage specification file")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=Path("build/resource-guard/heavy.lock"),
    )
    parser.add_argument("--cpu-workers", type=int, default=4)
    parser.add_argument("--cpu-iterations", type=int, default=8_000_000)
    parser.add_argument("--skip-stages", action="store_true")
    parser.add_argument("--skip-cpu-probe", action="store_true")
    parser.add_argument("--skip-lock-probe", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    lock_file = args.lock_file if args.lock_file.is_absolute() else root / args.lock_file

    stages: list[dict[str, Any]] = []
    if args.spec:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        stages = list(spec.get("stages", []))

    measured: list[dict[str, Any]] = []
    if not args.skip_stages:
        for stage in stages:
            measured.append(
                run_stage(stage, out_dir, args.python, lock_file, root)
            )

    cpu_probe: dict[str, Any] = {}
    if not args.skip_cpu_probe:
        cpu_probe = probe_cpu_scaling(
            args.cpu_workers, args.cpu_iterations, args.python, root, out_dir
        )

    lock_probe: dict[str, Any] = {}
    if not args.skip_lock_probe:
        lock_probe = probe_lock_contention(args.python, lock_file, root, out_dir)

    host = sample_host(root)
    payload = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "root": str(root),
        "interpreter": args.python,
        "host": host,
        "stages": measured,
        "cpu_probe": cpu_probe,
        "lock_probe": lock_probe,
    }
    payload["bottlenecks"] = classify_bottlenecks(
        measured, cpu_probe, lock_probe, host
    )

    (out_dir / "throughput.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "throughput.md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["bottlenecks"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
