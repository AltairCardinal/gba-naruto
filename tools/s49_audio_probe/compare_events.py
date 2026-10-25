#!/usr/bin/env python3
"""Stream J: pair the original MP2K cue sequence with the remake Maxmod cue
sequence and emit the per-event difference table.

Pairing key
------------
The two sides do not share a vocabulary, so the table is paired by *game
moment* (the thing the player perceives), not by frame number:

  original side  -> the MP2K sound ID that is live at that moment
                   (runtime-measured from the MP2K player blocks, plus the
                   cue census over the recorded savestates)
  remake side    -> the cue the product code dispatches at that moment
                   (parsed out of battle_audio_director.h + the dispatch
                   call sites + battle_audio_runtime.h)

Inputs
------
build/s49-audio/original_events.json   runtime-measured original cue sequence
build/s49-audio/cue_census.json         which cue is live at each checkpoint
build/s49-audio/remake_events.json      remake director table + wiring + sites
<reverse tree>/artifacts/audio/full-song-render-evidence.json
<reverse tree>/artifacts/audio/mgba-mp2k-differential.json (unused)
<remake tree>/artifacts/scenario-41-audio-reference-v1/*.json

Outputs
-------
build/s49-audio/event_diff.json         machine readable diff
build/s49-audio/event_diff.md           the readable table

Usage
-----
    python tools/s49_audio_probe/compare_events.py --out build/s49-audio
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from probe_driver import write_json  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
REVERSE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-reverse")
REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")

MP2K_RENDER_EVIDENCE = REVERSE_ROOT / "artifacts" / "audio" / "full-song-render-evidence.json"
REMAKE_CUE_DIR = REMAKE_ROOT / "artifacts" / "scenario-41-audio-reference-v1"

# ── the moment vocabulary ────────────────────────────────────────────────────
# (key, label, remake event, remake arm, original evidence)
#
# "original evidence" is either
#   ("measured", cue)          -- the cue ID seen in the measured a24 walk
#   ("census", [checkpoints])  -- the cue ID live in the listed savestates
ORIGINAL_EVIDENCE = {
    "battle_bgm_s49": ("census", [
        "scenario-49-battle-14-entry.ss9",
        "scenario-49-battle-14-tool67-entry.ss9",
        "scenario-49-battle-14-tool67-active-c3.ss9",
        "scenario-49-battle-14-tool67-confirmation.ss9",
        "scenario-49-battle-14-tool37-confirmation.ss9",
        "scenario-49-battle-14-turn4-two-kills.ss9",
    ]),
    "battle_bgm_s41": ("census", [
        "scenario-41-controller-entry.ss9",
        "scenario-41-action-menu-0.ss9",
        "scenario-41-player-turn.ss9",
        "scenario-41-target-select.ss9",
        "scenario-41-combat-popup.ss9",
        "scenario-41-result.ss9",
        "scenario-41-victory.ss9",
    ]),
    "prebattle_bgm": ("census", [
        "scenario-41-start-row.ss9",
        "scenario-41-prebattle-down.ss9",
        "scenario-41-prebattle-menu-candidate.ss9",
        "scenario-41-pre-controller-after-a.ss9",
    ]),
    "combo_bgm": ("census", [
        "scenario-41-combat-dialogue.ss9",
        "scenario-49-battle-14-tool37-group17-active.ss9",
    ]),
    "postbattle_dialogue_bgm": ("census", [
        "scenario-41-postbattle-dialogue-1.ss9",
        "scenario-41-postbattle-dialogue-5.ss9",
    ]),
    "postbattle_map_bgm": ("census", [
        "scenario-41-postbattle.ss9",
    ]),
    "ui_confirm_sfx": ("measured", 102),
    "ui_cancel_sfx": ("measured", 103),
    "ui_navigate_sfx": ("measured", 104),
    "input_rejected_sfx": ("measured", 105),
    "action_confirmed_sfx": ("measured", 117),
    "action_movie_sfx": ("measured", 116),
    "impact_sfx": ("measured", 138),
    "combat_popup_sfx": ("measured", 149),
    "victory_sfx": ("measured", 158),
    "result_sfx": ("measured", 157),
    "battle_opened_sfx": ("measured", 126),
    "tool_group17_sfx": ("census", ["scenario-49-battle-14-tool37-group17-active.ss9"], [15]),
    "tool_expiry_sfx": ("census", ["scenario-49-battle-14-tool67-expiry-ready.ss9"], [10]),
}

MOMENTS = [
    # key, label, remake event, arm, kind filter, original cue mode
    ("battle_bgm_s49", "S49 战斗 BGM", "battle_opened", "default", "music", "common"),
    ("battle_bgm_s41", "S41 战斗 BGM（参考）", "battle_opened", "default", "music", "common"),
    ("prebattle_bgm", "战前菜单 BGM", "preparation_opened", "default", "music", "common"),
    ("combo_bgm", "组合拳演出 BGM", "technique_title", "special", "music", "common"),
    ("postbattle_dialogue_bgm", "战后对白 BGM", "postbattle_dialogue_opened", "default", "music", "common"),
    ("postbattle_map_bgm", "战后地图 BGM", "postbattle_opened", "default", "music", "common"),
    ("battle_opened_sfx", "战斗开场音", "battle_opened", "default", "sound", "measured"),
    ("ui_confirm_sfx", "UI 确认音", "ui_confirmed", "default", "sound", "measured"),
    ("ui_cancel_sfx", "UI 取消音", "ui_cancelled", "default", "sound", "measured"),
    ("ui_navigate_sfx", "UI 移动音", "ui_navigated", "default", "sound", "measured"),
    ("input_rejected_sfx", "输入被拒音", "input_rejected", "default", "sound", "measured"),
    ("action_confirmed_sfx", "行动确认音", "action_confirmed", "default", "sound", "measured"),
    ("action_movie_sfx", "战斗演出音", "action_movie", "default", "sound", "measured"),
    ("impact_sfx", "命中音", "impact", "default", "sound", "measured"),
    ("combat_popup_sfx", "战斗结算弹窗音", "combat_popup", "default", "sound", "measured"),
    ("victory_sfx", "胜利音", "victory_shown", "default", "sound", "measured"),
    ("result_sfx", "结算音", "result_shown", "default", "sound", "measured"),
    ("tool_group17_sfx", "道具组17 专用音", None, None, None, "exclusive"),
    ("tool_expiry_sfx", "道具到期专用音", None, None, None, "exclusive"),
]


BGM_MOMENTS = {
    "battle_bgm_s49", "battle_bgm_s41", "prebattle_bgm", "combo_bgm",
    "postbattle_dialogue_bgm", "postbattle_map_bgm",
}


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def original_cue_table() -> dict:
    """Per-cue original parameters from the MP2K render evidence."""
    if not MP2K_RENDER_EVIDENCE.is_file():
        return {}
    data = load(MP2K_RENDER_EVIDENCE)
    rate = data.get("sample_rate", 15768)
    table = {}
    for song in data["songs"]:
        table[song["sound_id"]] = {
            "player_index": song["player_index"],
            "track_count": song["track_count"],
            "looping": bool(song["looping_tracks"]),
            "sample_rate": rate,
            "frames": song["frames"],
            "bounded_duration_seconds": round(song["frames"] / float(rate), 3),
            "pcm_sha256": song["pcm_sha256"],
        }
    return table


def remake_cue_table() -> dict:
    """Per-cue remake parameters from the scenario-41 audio manifests."""
    table: dict[int, dict] = {}
    if not REMAKE_CUE_DIR.is_dir():
        return table
    for path in sorted(REMAKE_CUE_DIR.glob("cue-*-manifest.json")):
        data = load(path)
        table[data["sound_id"]] = {
            "semantic": data.get("semantic"),
            "loop": data.get("loop"),
            "sample_rate": data.get("sample_rate"),
            "duration_seconds": (
                round(data["duration_seconds"], 3)
                if "duration_seconds" in data else None),
            "gain": data.get("gain"),
            "s3m_sha256": data.get("s3m_sha256"),
            "asset": "butano-sequel/audio/sound_%03d.s3m" % data["sound_id"],
        }
    sfx = REMAKE_CUE_DIR / "sfx-manifest.json"
    if sfx.is_file():
        for entry in load(sfx)["entries"]:
            row = table.setdefault(entry["sound_id"], {})
            row.update({
                "semantic": entry.get("semantic"),
                "duration_seconds": round(entry["duration_seconds"], 3),
                "sample_rate": entry["sample_rate"],
                "source_frame_count": entry["source_frame_count"],
                "asset": entry["output"],
                "wav_sha256": entry["wav_sha256"],
            })
    return table


def measured_cue_stats(original: dict) -> dict:
    """cue_id -> {starts, stops, first_frame, last_frame, slots}."""
    stats: dict[int, dict] = {}
    for event in original["events"]:
        cue = event["sound_id"]
        if cue is None:
            continue
        row = stats.setdefault(cue, {
            "cue_id": cue, "starts": 0, "stops": 0,
            "first_frame": event["frame"], "last_frame": event["frame"],
            "slots": set(),
        })
        row["last_frame"] = event["frame"]
        if event["kind"] == "cue_start":
            row["starts"] += 1
        else:
            row["stops"] += 1
        row["slots"].add(event["slot"])
    for row in stats.values():
        row["slots"] = sorted(row["slots"])
    return stats


def census_cues(census: dict) -> dict:
    out = {}
    for row in census["checkpoints"]:
        out[row["state"]] = row["live_cues"]
    return out


def classify(original_cue, original_seen, remake_cues, remake_kind,
             remake_has_call_site, original_moment_cue) -> str:
    """Difference class for one paired row."""
    if original_cue is None and not remake_cues:
        return "none"
    if original_cue is None and remake_cues:
        return "extra_on_remake"
    if original_cue is not None and not remake_cues:
        return "missing_on_remake"
    if original_moment_cue is not None and original_moment_cue != remake_cues[0]:
        return "cue_mismatch"
    if remake_kind == "sound" and remake_has_call_site:
        return "silent_on_remake"
    if not remake_has_call_site:
        return "never_dispatched"
    if not original_seen:
        return "not_reached_in_window"
    return "match"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio"))
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out)
    original = load(out_dir / "original_events.json")
    remake = load(out_dir / "remake_events.json")
    census = load(out_dir / "cue_census.json")

    original_params = original_cue_table()
    remake_params = remake_cue_table()
    measured = measured_cue_stats(original)
    census_map = census_cues(census)

    # ── the remake's cue per event / arm ────────────────────────────────────
    remake_by_event: dict[str, dict] = {}
    for event, arms in remake["director_table"].items():
        remake_by_event[event] = {
            "default": arms["default"],
            "special": arms["special"],
            "call_sites": remake["dispatch_sites"].get(event, []),
        }

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
                # the cue that only shows up in this moment's checkpoints
                exclusive = sorted(cues - set(exclude))
                original_cue = exclusive[0] if exclusive else (
                    sorted(cues)[0] if cues else None)
            else:
                common = set.intersection(*[set(census_map.get(c, []))
                                             for c in evidence[1]]) if evidence[1] else set()
                original_cue = sorted(common)[0] if common else (
                    sorted(cues)[0] if cues else None)
            original_seen = original_cue is not None
            evidence_note = "cue 普查：%s" % ", ".join(
                "%s=%s" % (c, census_map.get(c)) for c in evidence[1][:3])

        remake_entry = remake_by_event.get(event) if event else None
        if remake_entry:
            commands = remake_entry.get(arm, []) or remake_entry.get("default", [])
            if kind_filter:
                commands = [command for command in commands
                            if command["kind"] == kind_filter]
            remake_cues = [command["cue"] for command in commands]
            remake_kind = kind_filter or (commands[0]["kind"] if commands else None)
            remake_sites = remake_entry["call_sites"]
        else:
            remake_cues = []
            remake_kind = None
            remake_sites = []

        # the "moment cue" for the mismatch test is the music/BGM cue
        original_moment_cue = None
        if original_cue is not None and key in BGM_MOMENTS:
            original_moment_cue = original_cue

        diff = classify(original_cue, original_seen, remake_cues, remake_kind,
                        bool(remake_sites), original_moment_cue)

        original_row = {
            "cue_id": original_cue,
            "evidence": evidence_note,
            "observed_in_window": original_seen,
            "dispatches": (measured[original_cue]["starts"]
                            if original_cue in measured else None),
            "first_frame": (measured[original_cue]["first_frame"]
                            if original_cue in measured else None),
            "slots": (measured[original_cue]["slots"]
                      if original_cue in measured else []),
            "player_index": original_params.get(original_cue, {}).get("player_index"),
            "track_count": original_params.get(original_cue, {}).get("track_count"),
            "looping": original_params.get(original_cue, {}).get("looping"),
            "bounded_duration_seconds": original_params.get(
                original_cue, {}).get("bounded_duration_seconds"),
        }
        remake_row = {
            "event": event,
            "arm": arm,
            "cues": remake_cues,
            "kind": remake_kind,
            "call_sites": remake_sites,
            "has_call_site": bool(remake_sites),
            "reaches_sound_engine": remake_kind == "music",
            "duration_seconds": (remake_params.get(remake_cues[0], {})
                                 .get("duration_seconds") if remake_cues else None),
            "asset": (remake_params.get(remake_cues[0], {}).get("asset")
                      if remake_cues else None),
        }
        rows.append({
            "key": key,
            "moment": label,
            "diff": diff,
            "original": original_row,
            "remake": remake_row,
        })

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["diff"]] = counts.get(row["diff"], 0) + 1

    parameter_rows = build_parameter_rows(rows, original_params, remake_params)
    write_json(out_dir / "event_diff.json", {
        "original_rom_sha256": original["rom_sha256"],
        "remake_rom_sha256": remake["rom_sha256"],
        "diff_counts": counts,
        "parameter_comparison": parameter_rows,
        "rows": rows,
    })
    markdown = render_markdown(rows, counts, original, remake, parameter_rows)
    (out_dir / "event_diff.md").write_text(markdown, encoding="utf-8",
                                            newline="\n")
    print(f"diff classes: {counts}")
    print(f"wrote {out_dir / 'event_diff.md'}")
    print(f"wrote {out_dir / 'event_diff.json'}")
    return 0


def build_parameter_rows(rows, original_params, remake_params) -> list[dict]:
    """Per-cue parameter comparison: original MP2K render vs remake asset."""
    out = []
    seen = set()
    for row in rows:
        for side in ("original", "remake"):
            cue = row[side].get("cue_id")
            if cue is None and side == "remake":
                cue = (row[side].get("cues") or [None])[0]
            if cue is None or cue in seen:
                continue
            seen.add(cue)
            left = original_params.get(cue, {})
            right = remake_params.get(cue, {})
            out.append({
                "cue_id": cue,
                "original_duration_seconds": left.get("bounded_duration_seconds"),
                "original_frames": left.get("frames"),
                "original_sample_rate": left.get("sample_rate"),
                "original_looping": left.get("looping"),
                "original_track_count": left.get("track_count"),
                "remake_duration_seconds": right.get("duration_seconds"),
                "remake_loop": right.get("loop"),
                "remake_sample_rate": right.get("sample_rate"),
                "duration_delta_seconds": (
                    round(right["duration_seconds"]
                          - left["bounded_duration_seconds"], 3)
                    if right.get("duration_seconds") is not None
                    and left.get("bounded_duration_seconds") is not None
                    else None),
            })
    out.sort(key=lambda row: row["cue_id"])
    return out


def render_markdown(rows, counts, original, remake, parameter_rows) -> str:
    lines = []
    lines.append("# S49 音频事件级差异表（stream J）\n")
    lines.append("配对键 = **游戏时刻**（玩家能感知到的那个事件），"
                 "不是帧号。")
    lines.append("")
    lines.append("| 项 | 原版 | 重制侧 |")
    lines.append("|---|---|---|")
    lines.append(f"| ROM sha256 | `{original['rom_sha256']}` | "
                 f"`{remake['rom_sha256']}` |")
    lines.append("| 证据来源 | mGBA 探针读 MP2K 运行时状态 + cue 普查 | "
                 "产品代码 `battle_audio_director.h` + `battle_audio_runtime.h` "
                 "+ 调度调用点 |")
    lines.append(f"| 测量窗口 | 2556 帧（24×A + 300 帧尾巴） | "
                 f"3496 帧（Down,Down,A×32 + 300 帧尾巴） |")
    lines.append(f"| 运行时确定 | {original['event_count']} 个 MP2K 事件 | "
                 f"{len(remake['director_table'])} 类调度事件 |")
    lines.append(f"| 确定性 | 两次连跑 byte-identical = "
                 f"{original['determinism_byte_identical']} | — |")
    lines.append(f"| I/O 读不扰动模拟 | {original['io_read_does_not_perturb']} | — |")
    lines.append("")
    lines.append("## 差异分类统计\n")
    lines.append("| 分类 | 数量 | 含义 |")
    lines.append("|---|---:|---|")
    meaning = {
        "match": "两侧同一 cue、同一语义，且重制侧真的会发声",
        "silent_on_remake": "重制侧会调度该 cue，但运行时**不产生任何声音**",
        "cue_mismatch": "同一游戏时刻两侧 cue ID 不同 ⇒ 音频内容必然不同",
        "missing_on_remake": "原版会播，重制侧**连这个 cue 都没有**",
        "extra_on_remake": "重制侧有，原版这场战斗里没有",
        "never_dispatched": "重制侧表里有，但**没有任何调用点**",
        "not_reached_in_window": "两侧都有，但测量窗口内没走到",
    }
    for key, value in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{key}` | {value} | {meaning.get(key, '')} |")
    lines.append("")
    lines.append("## 逐事件配对表\n")
    lines.append("| # | 游戏时刻 | 差异分类 | 原版 cue | 原版证据 | "
                 "重制侧 cue | 重制侧调度点 | 重制侧是否发声 |")
    lines.append("|---:|---|---|---:|---|---|---|---|")
    for index, row in enumerate(rows, 1):
        left = row["original"]
        right = row["remake"]
        remake_cue_text = ", ".join(str(cue) for cue in right["cues"]) or "—"
        sites = ", ".join(right["call_sites"]) or ("⚠ 无" if right["event"] else "—")
        if right["event"] is None:
            audible = "—（重制侧无此 cue）"
        elif not right["has_call_site"]:
            audible = "**否**（表里有，但无调用点）"
        elif right["reaches_sound_engine"]:
            audible = "是"
        else:
            audible = "**否**（`play_battle_sound` 是 no-op）"
        lines.append(
            f"| {index} | {row['moment']} | `{row['diff']}` | "
            f"{left['cue_id'] if left['cue_id'] is not None else '—'} | "
            f"{left['evidence']} | {remake_cue_text} | {sites} | {audible} |")
    lines.append("")
    lines.append("## 参数对照（同一 cue 的时长 / 采样率 / 循环）\n")
    lines.append("原版时长 = 逆向线 MP2K 引擎渲染的采样帧数 ÷ 15768 Hz；"
                 "重制侧时长 = 资产 manifest。\n")
    lines.append("| cue | 原版时长 s | 原版采样率 | 原版轨道数 | 原版循环 | "
                 "重制侧时长 s | 重制侧采样率 | 差值 s |")
    lines.append("|---:|---:|---:|---:|---|---:|---:|---:|")
    for row in parameter_rows:
        lines.append(
            f"| {row['cue_id']} | "
            f"{row['original_duration_seconds'] if row['original_duration_seconds'] is not None else '—'} | "
            f"{row['original_sample_rate'] or '—'} | "
            f"{row['original_track_count'] if row['original_track_count'] is not None else '—'} | "
            f"{row['original_looping'] if row['original_looping'] is not None else '—'} | "
            f"{row['remake_duration_seconds'] if row['remake_duration_seconds'] is not None else '—'} | "
            f"{row['remake_sample_rate'] or '—'} | "
            f"{row['duration_delta_seconds'] if row['duration_delta_seconds'] is not None else '—'} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
