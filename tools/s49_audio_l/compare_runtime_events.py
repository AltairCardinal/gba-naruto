#!/usr/bin/env python3
"""Runtime-aware S49 audio event comparison (stream L).

Why a new comparator
--------------------
Stream J's ``tools/s49_audio_probe/compare_events.py`` classifies a sound row
as ``silent_on_remake`` whenever the remake's director schedules a sound cue
with a call site, because the remake side had no runtime instrument at all
(``play_battle_sound()`` was ``(void) cue;`` and the PSG/DMA register block
never changes while a Maxmod stream plays).  That classifier can therefore
never report a sound row as ``match``.

The remake now records every audio dispatch into a fixed IWRAM ring buffer
(``konoha::battle_audio_trace_buffer``), so this comparator grades the
*runtime* cue sequence instead of the static table, and pairs it with the
original side exactly like stream J does (same moment vocabulary, same
original-side evidence tables, imported read-only from stream J's module).

Usage:
    python tools/s49_audio_l/compare_runtime_events.py \
        --original build/s49-audio --trace build/s49-audio-l/remake_trace.json \
        --out build/s49-audio-l
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
J_PROBE_DIR = REPO / "tools" / "s49_audio_probe"
if str(J_PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(J_PROBE_DIR))

import compare_events as j_compare  # noqa: E402  (read-only reuse of stream J)
import extract_remake as j_extract  # noqa: E402  (read-only reuse of stream J)

REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
DIRECTOR_HEADER = REMAKE_ROOT / "game" / "include" / "konoha" / "battle_audio_director.h"

# The moment vocabulary is stream J's, unchanged.  Only the remake side of
# each row is re-derived from the runtime trace.
MOMENTS = j_compare.MOMENTS
ORIGINAL_EVIDENCE = j_compare.ORIGINAL_EVIDENCE

# The two battle BGM moments name a battle id, because the original ROM picks
# the battle BGM per scenario.  The S49 row is graded on the runtime trace of
# this capture; the S41 reference row is graded on the product's battle id
# mapping, because this capture never enters the scenario 41 battle.
MOMENT_BATTLE_ID = {
    "battle_bgm_s49": 14,
    "battle_bgm_s41": 41,
}

BGM_CUE_RE = re.compile(
    r"battle_audio_battle_bgm_cue\s*\(\s*int\s+battle_id\s*\)\s*\{[^}]*?"
    r"battle_id\s*==\s*(\d+)\s*\?\s*(\d+)\s*:\s*(\d+)", re.S)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def battle_bgm_cue_map(header: pathlib.Path) -> dict[int, int]:
    """battle id -> battle BGM cue, read out of the product header."""
    text = header.read_text(encoding="utf-8")
    match = BGM_CUE_RE.search(text)
    if not match:
        raise SystemExit(
            f"ERR could not read battle_audio_battle_bgm_cue() from {header}")
    special_id, special_cue, default_cue = (int(group) for group in match.groups())
    return {special_id: special_cue}, default_cue


def trace_cue_index(trace: dict) -> dict:
    """(kind, cue) -> the runtime dispatches."""
    index: dict[tuple[str, int], list[dict]] = {}
    for event in trace["events"]:
        key = (event["kind"], event["cue"])
        index.setdefault(key, []).append(event)
    return index


def classify(
    original_cue: int | None,
    remake_cues: list[int],
    remake_kind: str | None,
    runtime_dispatched: bool,
    has_call_site: bool,
    original_moment_cue: int | None,
    audible: bool | None,
) -> str:
    if original_cue is None and not remake_cues:
        return "none"
    if original_cue is None and remake_cues:
        return "extra_on_remake"
    if original_cue is not None and not remake_cues:
        return "missing_on_remake"
    if original_moment_cue is not None and original_moment_cue not in remake_cues:
        return "cue_mismatch"
    if not has_call_site:
        return "never_dispatched"
    if not runtime_dispatched:
        # The cue exists and has a call site, but this capture never walked
        # into that moment.
        return "not_reached_in_window"
    if remake_kind == "sound":
        if audible is False:
            return "silent_on_remake"
        if audible is None:
            return "audibility_unmeasured"
        return "match"
    return "match"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original", default=str(REPO / "build" / "s49-audio"))
    parser.add_argument("--trace", default=str(
        REPO / "build" / "s49-audio-l" / "remake_trace.json"))
    parser.add_argument("--audibility", default=str(
        REPO / "build" / "s49-audio-l" / "audibility.json"))
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio-l"))
    args = parser.parse_args()

    original_dir = pathlib.Path(args.original)
    out_dir = pathlib.Path(args.out)
    original = load(original_dir / "original_events.json")
    census = load(original_dir / "cue_census.json")
    trace = load(pathlib.Path(args.trace))
    audibility = {}
    per_cue = {}
    audibility_path = pathlib.Path(args.audibility)
    if audibility_path.is_file():
        audibility = load(audibility_path)
        per_cue = audibility.get("per_cue", {})

    director_table = j_extract.parse_director_table(DIRECTOR_HEADER)
    sites = j_extract.find_dispatch_sites(REMAKE_ROOT / "game" / "src")
    bgm_cue_map, bgm_default_cue = battle_bgm_cue_map(DIRECTOR_HEADER)
    index = trace_cue_index(trace)
    original_params = j_compare.original_cue_table()
    remake_params = j_compare.remake_cue_table()
    measured = j_compare.measured_cue_stats(original)
    census_map = j_compare.census_cues(census)

    rows = []
    for key, label, event, arm, kind_filter, cue_mode in MOMENTS:
        evidence = ORIGINAL_EVIDENCE[key]
        original_cue = None
        original_seen = False
        evidence_note = ""
        if evidence[0] == "measured":
            original_cue = evidence[1]
            stat = measured.get(original_cue)
            original_seen = stat is not None and stat["starts"] > 0
            evidence_note = ("运行时实测：%d 次 / 首帧 f%s"
                             % (stat["starts"], stat["first_frame"])
                             if stat else "运行时未出现")
        else:
            exclude = evidence[2] if len(evidence) > 2 else []
            cues: set[int] = set()
            for checkpoint in evidence[1]:
                cues.update(census_map.get(checkpoint, []))
            if cue_mode == "exclusive":
                exclusive = sorted(cues - set(exclude))
                original_cue = exclusive[0] if exclusive else (
                    sorted(cues)[0] if cues else None)
            else:
                common = set.intersection(*[set(census_map.get(c, []))
                                             for c in evidence[1]]) \
                    if evidence[1] else set()
                original_cue = sorted(common)[0] if common else (
                    sorted(cues)[0] if cues else None)
            original_seen = original_cue is not None
            evidence_note = "cue 普查：%s" % ", ".join(
                "%s=%s" % (c, census_map.get(c)) for c in evidence[1][:3])

        arms = director_table.get(event) if event else None
        if arms:
            commands = arms.get(arm, []) or arms.get("default", [])
            if kind_filter:
                commands = [command for command in commands
                            if command["kind"] == kind_filter]
            remake_cues = [command["cue"] for command in commands]
            remake_kind = kind_filter or (commands[0]["kind"] if commands else None)
        else:
            remake_cues = []
            remake_kind = None

        # The two battle BGM moments are scenario specific: the cue of the
        # battle they name replaces the static table cue.
        battle_id = MOMENT_BATTLE_ID.get(key)
        if battle_id is not None and remake_kind == "music" and remake_cues:
            remake_cues = [bgm_cue_map.get(battle_id, bgm_default_cue)]

        # Runtime side: which of the director's cues were really dispatched?
        runtime_frames: list[int] = []
        runtime_dispatched = False
        handles: list[int] = []
        for cue in remake_cues:
            for event_record in index.get((remake_kind or "sound", cue), []):
                runtime_dispatched = True
                runtime_frames.append(event_record["trace_frame"])
                handles.append(event_record.get("handle", 0))

        original_moment_cue = original_cue if (
            original_cue is not None and key in j_compare.BGM_MOMENTS) else None

        # Audibility: measured by the A/B of the two remake ROMs that differ
        # only in whether the sound effect is submitted to the Maxmod mixer
        # (tools/s49_audio_l/measure_audibility.py).
        audible = None
        if remake_kind == "sound" and runtime_dispatched and remake_cues:
            cue_row = per_cue.get(str(remake_cues[0]))
            if cue_row:
                audible = cue_row["audible_dispatches"] > 0

        has_call_site = bool(sites.get(event, [])) if event else False
        diff = classify(original_cue, remake_cues, remake_kind,
                        runtime_dispatched, has_call_site,
                        original_moment_cue, audible)

        rows.append({
            "key": key,
            "moment": label,
            "diff": diff,
            "original": {
                "cue_id": original_cue,
                "evidence": evidence_note,
                "observed_in_window": original_seen,
                "dispatches": (measured[original_cue]["starts"]
                                if original_cue in measured else None),
                "first_frame": (measured[original_cue]["first_frame"]
                                if original_cue in measured else None),
                "bounded_duration_seconds": original_params.get(
                    original_cue, {}).get("bounded_duration_seconds"),
            },
            "remake": {
                "event": event,
                "arm": arm,
                "cues": remake_cues,
                "kind": remake_kind,
                "battle_id": battle_id,
                "call_sites": sites.get(event, []) if event else [],
                "runtime_dispatched": runtime_dispatched,
                "runtime_frames": sorted(runtime_frames),
                "sound_handles": handles,
                "audible": audible,
                "duration_seconds": (remake_params.get(
                    remake_cues[0], {}).get("duration_seconds")
                    if remake_cues else None),
                "asset": (remake_params.get(remake_cues[0], {}).get("asset")
                          if remake_cues else None),
            },
        })

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["diff"]] = counts.get(row["diff"], 0) + 1

    payload = {
        "original_rom_sha256": original["rom_sha256"],
        "remake_rom_sha256": trace["rom_sha256"],
        "diff_counts": counts,
        "rows": rows,
        "runtime_trace_events": len(trace["events"]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "event_diff.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (out_dir / "event_diff.md").write_text(
        render_markdown(payload, rows, counts), encoding="utf-8", newline="\n")
    print(f"diff classes: {counts}")
    print(f"wrote {out_dir / 'event_diff.md'}")
    return 0


def render_markdown(payload: dict, rows: list[dict], counts: dict) -> str:
    lines = []
    lines.append("# S49 音频事件级差异表（stream L，运行时口径）\n")
    lines.append("配对键 = **游戏时刻**。原版证据与 stream J 完全一致"
                 "（同一套 moment 词表与同一批存档/实测证据）；"
                 "重制侧改用**运行时 cue 轨迹**"
                 "（IWRAM 环形缓冲），不再用静态表推断。\n")
    lines.append("| 项 | 原版 | 重制侧 |")
    lines.append("|---|---|---|")
    lines.append(f"| ROM sha256 | `{payload['original_rom_sha256']}` | "
                 f"`{payload['remake_rom_sha256']}` |")
    lines.append(f"| 证据来源 | mGBA 探针读 MP2K 运行时状态 + cue 普查 | "
                 f"重制 ROM 运行时 cue 环形缓冲 |")
    lines.append(f"| 运行时 cue 事件数 | — | {payload['runtime_trace_events']} |")
    lines.append("")
    lines.append("## 差异分类统计\n")
    lines.append("| 分类 | 数量 | 含义 |")
    lines.append("|---|---:|---|")
    meaning = {
        "match": "两侧同一 cue、同一语义，且重制侧运行时真的派发了它",
        "silent_on_remake": "重制侧派发了该 cue，但**听不到声音**",
        "cue_mismatch": "同一游戏时刻两侧 cue ID 不同",
        "missing_on_remake": "原版会播，重制侧**连这个 cue 都没有**",
        "extra_on_remake": "重制侧有，原版这场战斗里没有",
        "never_dispatched": "重制侧表里有，但**没有调用点**",
        "not_reached_in_window": "两侧都有且重制侧已接线，但这次采集没走到该时刻",
        "audibility_unmeasured": "运行时派发了，但**没有可闻性证据**",
        "none": "该时刻两侧都没有 cue",
    }
    for key, value in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{key}` | {value} | {meaning.get(key, '')} |")
    lines.append("")
    lines.append("## 逐事件配对表\n")
    lines.append("| # | 游戏时刻 | 差异分类 | 原版 cue | 原版证据 | "
                 "重制侧 cue | 运行时派发帧 | 可闻 |")
    lines.append("|---:|---|---|---:|---|---|---|---|")
    for index, row in enumerate(rows, start=1):
        remake = row["remake"]
        frames = remake["runtime_frames"]
        frame_text = ", ".join(str(frame) for frame in frames[:6]) or "—"
        if len(frames) > 6:
            frame_text += f" … (+{len(frames) - 6})"
        audible = remake["audible"]
        audible_text = "—" if audible is None else ("是" if audible else "否")
        lines.append(
            f"| {index} | {row['moment']} | `{row['diff']}` | "
            f"{row['original']['cue_id'] if row['original']['cue_id'] is not None else '—'} | "
            f"{row['original']['evidence']} | "
            f"{', '.join(str(cue) for cue in remake['cues']) or '—'} | "
            f"{frame_text} | {audible_text} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
