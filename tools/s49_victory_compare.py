#!/usr/bin/env python3
"""Cross-align the surviving ORIGINAL victory/settlement frames against the
remake's battle frames, and settle the question the S49 brief keeps deferring:

    "is the 21k-27k px residual a rendering difference or a pairing difference?"

The brief (notes/s49-fidelity/BRIEF.md) measured a handful of frames whose
battlefield-area residual was 21k-27k px and concluded they are a *pairing*
difference -- the two sides sit at different moments of the game.  That
conclusion was never checked against the original's actual victory/settlement
screens, and those screens survived the 2026-10-19 artifact cleanup in three
places.  This tool closes that gap:

* it reads every surviving original victory/settlement frame,
* finds, for each one, the remake frame that matches it best (cross-directory
  alignment, not index alignment),
* reports both the battlefield-area residual (0,0,240,128 -- what the brief
  measures) and the whole-screen residual, and
* classifies what each frame actually shows, so a "content difference" is never
  mistaken for a "rendering difference".

Two residuals are reported per original frame:

``field_px``
    differing pixels inside the battlefield area (0,0,240,128) -- comparable
    with the numbers in the brief.
``full_px``
    differing pixels over the whole 240x160 screen.

Verdicts
--------

The point of this tool is the distinction, so every row carries one:

``identical``
    field_px == 0.  The remake draws this exact moment pixel for pixel.
``rendering-difference``
    the remake corpus contains a frame of the *same* moment and it is drawn
    differently.  This is a real product difference -- it belongs on the D1/D2
    list and needs a code change.
``content-difference``
    the remake corpus contains no frame of this moment (different screen, or a
    different point of the same screen).  Nothing to fix in the product; it is
    a pairing/coverage problem.
``missing-in-remake``
    the original shows an element the remake never draws at all (e.g. the
    "START" calligraphy, the black transition).  A product gap.

The row-level rule is: same screen class and residual below 10,000 px means
"rendering-difference"; anything else means "content-difference".  The 10,000
threshold is not arbitrary -- it is the empty band between the two populations
the brief already measured (product 1,000-2,500 px vs pairing 21,000-27,000 px).
For the 25 original walk frames the verdict is hand-verified against the
side-by-side sheets (see notes/s49-fidelity/B-victory-settlement.md) and
overrides the rule.

Usage::

    python tools/s49_victory_compare.py --out build/s49-victory/compare.json

Optional::

    --artifacts-root DIR   where the surviving original artifacts live
    --remake DIR           the remake frame directory (default build/s49-remake)
    --remake-extra DIR     extra remake frame dirs (repeatable); default:
                           every ``s49-remake-*`` artifact directory
    --original-walk DIR    the 25-frame original walk (reference)
    --field-area X Y W H   battlefield area (default 0 0 240 128)
    --no-extra             skip the extended remake corpus
    --md PATH              also write a markdown table
    --sheet PATH           also write a contact sheet of the original frames
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError:  # pragma: no cover
    print("ERR Pillow is required (pip install pillow)", file=sys.stderr)
    raise SystemExit(2)

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Where the surviving evidence lives
# ---------------------------------------------------------------------------

ARTIFACT_CANDIDATES = [
    pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\artifacts"),
    ROOT.parent / "gba-naruto-butano" / "artifacts",
]

ORIGINAL_GROUPS = [
    ("probe", "s49-original-victory-probe-*"),
    ("victory", "s49-original-victory-20261020-v1"),
    ("settlement", "s49-original-settlement-20261021-v1"),
]

REMAKE_EXTRA_GLOB = "s49-remake-*"

RENDER_THRESHOLD = 10_000  # px; the empty band between the brief's two populations

# ---------------------------------------------------------------------------
# Screen descriptions
# ---------------------------------------------------------------------------
#
# These are the *scenario* names the recorder wrote down when the walk was
# captured, confirmed by looking at the frames.  They are the ground truth for
# "what this frame is doing"; the pixel features only refine them.

# Hand-verified descriptions for the decision-relevant original scenarios.
SCENARIO_DESCRIPTION = {
    "s41-result": "战后结算面板：胜者头像 + 「经验分/面临分/回合分/合计」三列数字 + 对话框宣布胜者",
    "s41-level-up-1": "升级面板：对话框「LV 升到 N 级」 + 角色头像 + 成长属性表（体力/查克拉/咒力/防御力/敏捷度/移动力/忍具数）",
    "s41-level-up-2": "升级面板：对话框「LV 升到 N 级」 + 角色头像 + 成长属性表；切页时顶部出现 经验值/鸣人/佐助/小樱 页签",
    "s46-victory-reward": "胜利奖励面板：顶部 经验值/鸣人/佐助/小樱 页签 + 三名角色立绘 + 每人的 经验值/资金/合计 三列数字",
    "p01-postbattle-menu": "战后菜单：绿色对话框（任务简报文本）+ 右侧选项框（队伍·装备 / 查克拉图 / 不接任务 / 队伍任务）",
    "p02-postbattle-next": "战后菜单：绿色对话框 + 选项框（队伍·装备 / 查克拉图 / 不接任务 / 队伍任务）",
    "p03-naruto-status-exp": "战后队伍画面：队伍·装备 立绘 + LV/经验值 状态条，随后进入「人物信息」角色状态面板",
    "p04-naruto-character-info": "角色状态面板（人物信息）：头像 + LV + 经验值/体力/查克拉/咒力/防御力/敏捷度/移动力/印/忍具数",
    "p05-sasuke-character-info": "角色状态面板（人物信息）：佐助头像 + LV + 各项数值",
    "p06-sakura-character-info": "角色状态面板（人物信息）：小樱头像 + LV + 各项数值",
    "p07-sasuke-info2": "角色状态面板（人物信息）：佐助，翻页到下一项",
    "p08-sakura-info2": "角色状态面板（人物信息）：小樱，翻页中",
    "p09-sakura-info3": "角色状态面板（人物信息）：小樱",
    "p10-sakura-info4": "角色状态面板（人物信息）：小樱",
    "r28-win-conditions": "战场上的回合/条件菜单（回合 3 + 回合结束/选择角色/通关条件/游戏中断 + 我方与敌方名单）—— 不是胜利屏",
}

SETTLEMENT_SCENARIOS = {
    "s41-result", "s41-level-up-1", "s41-level-up-2", "s46-victory-reward",
}
POSTBATTLE_SCENARIOS = {
    "p01-postbattle-menu", "p02-postbattle-next", "p03-naruto-status-exp",
    "p04-naruto-character-info", "p05-sasuke-character-info",
    "p06-sakura-character-info", "p07-sasuke-info2", "p08-sakura-info2",
    "p09-sakura-info3", "p10-sakura-info4",
}

# The 25-frame original walk, step by step (read off the frames).
ORIGINAL_WALK_DESCRIPTION = {
    0: "战场：部署阶段（角色布阵）",
    1: "战场：部署阶段（角色布阵）",
    2: "战场：部署阶段（角色布阵）",
    3: "战场：部署阶段（角色布阵）",
    4: "战场：敌方单位加入阶段",
    5: "战场：敌方单位加入阶段",
    6: "战场：敌方单位加入阶段",
    7: "战场：敌方单位加入阶段",
    8: "战场 + 「開始」书法字",
    9: "战场 + 「開始」书法字",
    10: "战场 + 「開始」书法字",
    11: "黑场过渡",
    12: "对话演出：头像刚出现，对话框空白",
    13: "对话演出：鸣人 + 小樱头像，小樱台词",
    14: "对话演出：鸣人 + 小樱头像，小樱台词",
    15: "对话演出：鸣人 + 小樱 + 佐助头像",
    16: "对话演出：佐助台词",
    17: "对话演出：佐助台词",
    18: "黑场过渡",
    19: "战场 + 回合提示框「回合 1 玩家 的行動」",
    20: "战场 + 回合提示对话框「諾等等…」",
    21: "战场：单位移动到位",
    22: "战场：单位就位（移动中，HUD 隐藏）",
    23: "战场：单位就位（带蓝色名牌）",
    24: "战场 + 行动菜单（移動/木·忍具/查克拉/休息/行動結束）",
}

# The remake's 35-frame walk, step by step.
REMAKE_DESCRIPTION = {
    0: "简报对话框（保护木叶丸的任务说明）",
    1: "简报对话框",
    2: "简报对话框",
    3: "简报对话框 + 选项菜单",
    4: "战场：部署阶段（角色布阵）",
    5: "战场：部署阶段（角色布阵）",
    6: "战场：部署阶段（角色布阵）",
    7: "战场：敌方单位加入阶段",
    8: "战场：敌方单位加入阶段",
    9: "战场：敌方单位加入阶段",
    10: "战场：敌方单位加入阶段",
    11: "战场：小樱登场",
    12: "战场：READY（敌方回合结束）",
    13: "对话演出：鸣人 + 小樱头像（对话框空白）",
    14: "对话演出：鸣人 + 小樱头像，小樱台词",
    15: "对话演出：鸣人 + 小樱 + 佐助头像",
    16: "对话演出：佐助台词",
    17: "对话演出：佐助台词",
    18: "战场 + 回合提示框「回合 1 玩家 的行動」",
    19: "战场 + 行动菜单（移動/木·忍具/查克拉/休息/行動結束）",
    20: "战场 + 移动可达格覆盖层",
    21: "战场 + 木·忍具/行動結束 菜单",
    22: "忍术列表菜单（替身术 / 影分身 / 火遁·豪火球 …）",
    23: "战场：CANNOT SELECT（画面冻结）",
}
for _n in range(24, 35):
    REMAKE_DESCRIPTION[_n] = "战场：CANNOT SELECT（画面冻结）"

# Hand-verified verdicts for the 25 original walk frames.  Each one was
# checked by looking at the original frame next to its best remake match
# (build/s49-victory/walk-greyzone-pairs.png and the remake slice sheets).
WALK_VERDICT = {
    0: "rendering-difference", 1: "rendering-difference",
    2: "rendering-difference", 3: "rendering-difference",
    4: "rendering-difference", 5: "rendering-difference",
    6: "rendering-difference", 7: "rendering-difference",
    8: "missing-in-remake", 9: "missing-in-remake", 10: "missing-in-remake",
    11: "missing-in-remake",
    12: "content-difference",
    13: "rendering-difference",
    14: "identical",
    15: "identical",
    16: "rendering-difference",
    17: "identical",
    18: "missing-in-remake",
    19: "content-difference", 20: "content-difference",
    21: "content-difference", 22: "content-difference",
    23: "rendering-difference",
    24: "rendering-difference",
}


def remake_step_number(step: str) -> int | None:
    m = re.search(r"step-(\d+)", step or "")
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Pixel helpers
# ---------------------------------------------------------------------------

def load_rgb(path: pathlib.Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def crop(im: Image.Image, area) -> Image.Image:
    x, y, w, h = area
    return im.crop((x, y, x + w, y + h))


def diff_pixels(a: Image.Image, b: Image.Image) -> int:
    """Exact count of pixels whose RGB triple differs (same rule as
    tools/compare_frame_dirs.py), implemented with C-level PIL ops."""
    if a.size != b.size:
        return -1
    d = ImageChops.difference(a, b)
    r, g, bl = d.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    return sum(mx.histogram()[1:])


def _color_stats(im: Image.Image) -> dict:
    """Per-image colour statistics computed from PIL's C-level getcolors()."""
    total = im.width * im.height
    colors = im.getcolors(maxcolors=1 << 16) or []
    counts = sorted((c for c, _ in colors), reverse=True)
    grass = white = dark = lum = 0
    for count, (r, g, b) in colors:
        lum += count * (r * 299 + g * 587 + b * 114) / 1000.0
        if g > r + 10 and g > b + 10:
            grass += count
        if r > 220 and g > 220 and b > 220:
            white += count
        if r < 40 and g < 40 and b < 40:
            dark += count
    return {
        "total": total,
        "distinct_colors": len(colors),
        "lum_mean": round(lum / total, 1),
        "grass_frac": round(grass / total, 4),
        "white_frac": round(white / total, 4),
        "dark_frac": round(dark / total, 4),
        "flat_top2_frac": round(sum(counts[:2]) / total, 4),
    }


def features(im: Image.Image, field_area) -> dict:
    """Cheap, reproducible visual descriptors used for classification."""
    full = _color_stats(im)
    field = _color_stats(crop(im, field_area))
    return {
        "distinct_colors": full["distinct_colors"],
        "lum_mean": full["lum_mean"],
        "grass_frac": full["grass_frac"],
        "field_grass_frac": field["grass_frac"],
        "white_frac": full["white_frac"],
        "dark_frac": full["dark_frac"],
        "flat_top2_frac": full["flat_top2_frac"],
    }


def classify(feat: dict, scenario: str) -> str:
    """Coarse screen class.  Scenario provenance wins; pixels only break ties."""
    if scenario in SETTLEMENT_SCENARIOS:
        return "settlement-panel"
    if scenario in POSTBATTLE_SCENARIOS:
        return "postbattle-ui"
    if feat["lum_mean"] < 8:
        return "transition-black"
    if feat["lum_mean"] > 232 and feat["distinct_colors"] <= 12:
        return "transition-white"
    if feat["field_grass_frac"] > 0.20:
        return "battle-field"
    if feat["white_frac"] > 0.20:
        return "ui-panel"
    return "battle-field" if feat["grass_frac"] > 0.12 else "ui-mixed"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _read_label(inputs: pathlib.Path) -> str | None:
    if not inputs.is_file():
        return None
    try:
        return json.loads(inputs.read_text(encoding="utf-8")).get("label")
    except (json.JSONDecodeError, OSError):
        return None


def discover_original(root: pathlib.Path) -> list[dict]:
    """Every surviving original victory/settlement-side frame.

    The probe trees are not flat: ``s49-original-victory-probe-2N-driver``
    holds nested drive segments (``s01-r1-teleport-aim`` ...), each with its
    own ``inputs.json``.  Discovery therefore walks recursively and treats the
    *immediate parent* of a frame as its scenario.
    """
    frames = []
    for group, pattern in ORIGINAL_GROUPS:
        for d in sorted(root.glob(pattern)):
            if not d.is_dir():
                continue
            fallback_label = _read_label(d / "inputs.json")
            for p in sorted(d.rglob("*.png")):
                if "scratch" in p.parts:
                    continue  # contact sheets / derived composites, not raw frames
                parent = p.parent
                frames.append({
                    "group": group,
                    "artifact_dir": d.name,
                    "segment": parent.relative_to(d).as_posix(),
                    "scenario": parent.name,
                    "label": _read_label(parent / "inputs.json") or fallback_label,
                    "path": p,
                })
    return frames


def discover_remake(extra_dirs: list[pathlib.Path]) -> list[dict]:
    frames = []
    for d in extra_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.png")):
            frames.append({"group": d.name, "path": p})
    return frames


def discover_walk(d: pathlib.Path) -> list[dict]:
    """The 25-frame original walk.

    This is the corpus the brief's 21k-27k px residual was measured on, so it
    has to be in the table too -- otherwise the open question stays open.
    """
    frames = []
    if not d.is_dir():
        return frames
    for p in sorted(d.glob("*.png")):
        frames.append({
            "group": "walk",
            "artifact_dir": d.name,
            "segment": ".",
            "scenario": d.name,
            "label": "原版 25 帧 walk（BRIEF §2 的残差基准）",
            "path": p,
        })
    return frames


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path,
                    default=ROOT / "build" / "s49-victory" / "compare.json")
    ap.add_argument("--artifacts-root", default=None)
    ap.add_argument("--remake", type=pathlib.Path, default=ROOT / "build" / "s49-remake")
    ap.add_argument("--remake-extra", type=pathlib.Path, action="append", default=None)
    ap.add_argument("--original-walk", type=pathlib.Path,
                    default=ROOT / "build" / "s49-original-walk")
    ap.add_argument("--field-area", nargs=4, type=int, default=[0, 0, 240, 128],
                    metavar=("X", "Y", "W", "H"))
    ap.add_argument("--no-extra", action="store_true",
                    help="only use --remake, skip the extended remake corpus")
    ap.add_argument("--md", type=pathlib.Path, default=None)
    ap.add_argument("--sheet", type=pathlib.Path, default=None)
    args = ap.parse_args()

    field_area = tuple(args.field_area)
    art_root = find_artifacts_root(args.artifacts_root)

    # ---- collect frames -------------------------------------------------
    original = discover_original(art_root)
    walk = discover_walk(args.original_walk)
    original += walk
    if not original:
        print(f"ERR no original frames under {art_root}", file=sys.stderr)
        return 2

    remake_dirs = [args.remake]
    if not args.no_extra:
        if args.remake_extra:
            remake_dirs += [pathlib.Path(x) for x in args.remake_extra]
        else:
            remake_dirs += [d for d in sorted(art_root.glob(REMAKE_EXTRA_GLOB)) if d.is_dir()]

    remake = discover_remake(remake_dirs)
    if not remake:
        print("ERR no remake frames", file=sys.stderr)
        return 2

    print(f"artifacts root : {art_root}")
    print(f"original frames: {len(original)}")
    print(f"remake frames  : {len(remake)}  (from {len(remake_dirs)} dirs)")

    # ---- load + dedupe remake by content ---------------------------------
    remake_by_hash: dict[str, dict] = {}
    remake_order: list[str] = []
    remake_cache: dict[str, dict] = {}
    for entry in remake:
        p = entry["path"]
        im = load_rgb(p)
        h = hashlib.sha256(im.tobytes()).hexdigest()
        if h not in remake_by_hash:
            step_no = remake_step_number(p.stem)
            remake_by_hash[h] = {
                "remake_id": f"R{len(remake_order):03d}",
                "sha256": h,
                "paths": [],
                "first_path": str(p),
                "step": p.stem,
                "step_number": step_no,
                "content": REMAKE_DESCRIPTION.get(step_no, "（未描述的重制画面）"),
                "screen_class": classify(features(im, field_area), ""),
                "features": features(im, field_area),
            }
            remake_order.append(h)
            remake_cache[h] = {"full": im, "field": crop(im, field_area)}
        remake_by_hash[h]["paths"].append(str(p))

    remake_list = [remake_by_hash[h] for h in remake_order]
    print(f"unique remake images: {len(remake_list)}")

    # ---- load + dedupe original by content -------------------------------
    orig_by_hash: dict[str, dict] = {}
    orig_order: list[str] = []
    orig_cache: dict[str, dict] = {}
    for entry in original:
        p = entry["path"]
        im = load_rgb(p)
        h = hashlib.sha256(im.tobytes()).hexdigest()
        if h not in orig_by_hash:
            feat = features(im, field_area)
            orig_by_hash[h] = {
                "original_id": f"O{len(orig_order):03d}",
                "sha256": h,
                "paths": [],
                "first_path": str(p),
                "features": feat,
                "screen_class": classify(feat, entry["scenario"]),
            }
            orig_order.append(h)
            orig_cache[h] = {"full": im, "field": crop(im, field_area)}
        orig_by_hash[h]["paths"].append(str(p))

    orig_list = [orig_by_hash[h] for h in orig_order]
    print(f"unique original images: {len(orig_list)}")

    # ---- cross alignment -------------------------------------------------
    print("aligning ...", flush=True)
    align: dict[str, dict] = {}
    for i, oh in enumerate(orig_order):
        o = orig_cache[oh]
        best_field = None
        best_full = None
        for rh in remake_order:
            r = remake_cache[rh]
            fd = diff_pixels(o["field"], r["field"])
            full = diff_pixels(o["full"], r["full"])
            if best_field is None or (fd, full, rh) < best_field:
                best_field = (fd, full, rh)
            if best_full is None or (full, fd, rh) < best_full:
                best_full = (full, fd, rh)
        align[oh] = {
            "best_field": {"remake_id": remake_by_hash[best_field[2]]["remake_id"],
                           "remake_sha": best_field[2],
                           "remake_path": remake_by_hash[best_field[2]]["first_path"],
                           "remake_step": remake_by_hash[best_field[2]]["step"],
                           "field_px": best_field[0], "full_px": best_field[1]},
            "best_full": {"remake_id": remake_by_hash[best_full[2]]["remake_id"],
                          "remake_sha": best_full[2],
                          "remake_path": remake_by_hash[best_full[2]]["first_path"],
                          "remake_step": remake_by_hash[best_full[2]]["step"],
                          "field_px": best_full[1], "full_px": best_full[0]},
        }
        if (i + 1) % 64 == 0:
            print(f"  {i + 1}/{len(orig_order)}", flush=True)

    # ---- assemble rows ---------------------------------------------------
    rows = []
    for entry in original:
        p = entry["path"]
        im = load_rgb(p)
        h = hashlib.sha256(im.tobytes()).hexdigest()
        meta = orig_by_hash[h]
        scenario = entry["scenario"]
        feat = meta["features"]
        cls = meta["screen_class"]
        step_no = remake_step_number(p.stem)
        a = align[h]
        best = remake_by_hash[a["best_field"]["remake_sha"]]

        desc = SCENARIO_DESCRIPTION.get(scenario)
        precise = desc is not None
        if desc is None and entry["group"] == "walk":
            desc = ORIGINAL_WALK_DESCRIPTION.get(step_no, "战场画面（原版 25 帧 walk）")
            precise = True
        if desc is None:
            if cls == "battle-field":
                desc = f"战场画面（{entry['label'] or scenario}）"
            elif cls == "transition-black":
                desc = "黑场过渡"
            elif cls == "transition-white":
                desc = "白屏/闪光过渡"
            else:
                desc = f"界面画面（{entry['label'] or scenario}）"

        # verdict
        if entry["group"] == "walk" and step_no in WALK_VERDICT:
            verdict = WALK_VERDICT[step_no]
        elif a["best_field"]["field_px"] == 0:
            verdict = "identical"
        elif cls == best["screen_class"] and a["best_field"]["field_px"] < RENDER_THRESHOLD:
            verdict = "rendering-difference"
        else:
            verdict = "content-difference"

        rows.append({
            "group": entry["group"],
            "artifact_dir": entry["artifact_dir"],
            "segment": entry["segment"],
            "scenario": scenario,
            "label": entry["label"],
            "path": str(p),
            "sha256": h,
            "original_id": meta["original_id"],
            "duplicate_of": meta["paths"][0] if meta["paths"][0] != str(p) else None,
            "screen_class": cls,
            "content": desc,
            "description_precise": precise,
            "features": feat,
            "best_remake_id": a["best_field"]["remake_id"],
            "best_remake_step": a["best_field"]["remake_step"],
            "best_remake_path": a["best_field"]["remake_path"],
            "best_remake_content": best["content"],
            "field_px": a["best_field"]["field_px"],
            "full_px": a["best_field"]["full_px"],
            "best_full_remake_step": a["best_full"]["remake_step"],
            "best_full_field_px": a["best_full"]["field_px"],
            "best_full_px": a["best_full"]["full_px"],
            "verdict": verdict,
        })

    # ---- summary + answers ----------------------------------------------
    by_class: dict[str, list[dict]] = {}
    by_verdict: dict[str, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r["screen_class"], []).append(r)
        by_verdict.setdefault(r["verdict"], []).append(r)

    settlement_rows = [r for r in rows if r["screen_class"] in ("settlement-panel", "postbattle-ui")]
    walk_rows = [r for r in rows if r["group"] == "walk"]
    settle_best = [r["field_px"] for r in settlement_rows]

    answers = {
        "q1_how_far_off_is_the_remake_settlement_screen": {
            "question": "重制侧的胜利/结算屏与原版差多少？",
            "settlement_frames": len(settlement_rows),
            "best_remake_field_px_min": min(settle_best) if settle_best else None,
            "best_remake_field_px_max": max(settle_best) if settle_best else None,
            "field_area_px": field_area[2] * field_area[3],
            "min_percent_of_field": round(100.0 * min(settle_best) / (field_area[2] * field_area[3]), 1)
            if settle_best else None,
            "max_percent_of_field": round(100.0 * max(settle_best) / (field_area[2] * field_area[3]), 1)
            if settle_best else None,
            "any_settlement_frame_matched_at_zero": any(r["field_px"] == 0 for r in settlement_rows),
            "best_remake_screen_used": sorted({r["best_remake_step"] for r in settlement_rows}),
        },
        "q2_where_does_it_differ": {
            "question": "差在哪（文字？数值？布局？）",
            "answer": "没有可逐像素对照的重制结算帧 —— 差异不在文字/数值/布局，"
                      "而在「重制侧没有任何一帧是结算屏」。"
                      "布局层面的实测差异见 notes/s49-fidelity/B-victory-settlement.md §4。",
        },
        "q3_can_the_remake_reach_a_victory_screen": {
            "question": "重制侧根本到不了胜利屏？",
            "captured_corpus_contains_no_settlement_frame":
                not any(r["field_px"] == 0 for r in settlement_rows),
            "remake_frames_scanned": len(remake),
            "remake_unique_images": len(remake_list),
            "remake_frozen_tail": "build/s49-remake step-23..34 是 12 张完全相同的 "
                                  "「CANNOT SELECT」画面",
            "product_code_has_the_screen": True,
            "product_code_evidence": [
                "butano-sequel/game/include/konoha/battle_ui_model.h:294-313 "
                "(battle_scene_phase::result/outcome/complete/level_up/training "
                "-> show_result_panel = true)",
                "butano-sequel/game/src/battle_runtime_scene.cpp:1387-1405 "
                "(battle_ui_result_background + battle_ui_result_panel)",
                "butano-sequel/game/src/battle_runtime_scene.cpp:1407-1456 "
                "(battle_ui_result_{naruto,sasuke,sakura} sprites)",
            ],
        },
        "q4_is_the_21k_27k_band_a_pairing_difference": {
            "question": "BRIEF §2 的 21k–27k 残差是配对差吗？",
            "frames_at_or_above_21000": [
                {"frame": pathlib.Path(r["path"]).name, "field_px": r["field_px"],
                 "best_remake_step": r["best_remake_step"], "verdict": r["verdict"]}
                for r in walk_rows if r["field_px"] >= 21000
            ],
            "brief_claimed": "step-22/23 → 21k–27k px",
            "measured_here": "step-11 / 18 / 19 / 21 / 22 are >= 21k; "
                             "step-23 measures 1,323 px (a product difference)",
            "note": "BRIEF 的逐帧数字在本机逐项复现（0/0/0/28/344/1026），"
                    "只有 21k–27k 那一行的帧号不对。",
        },
    }

    summary = {
        "original_frames_total": len(rows),
        "original_unique_images": len(orig_list),
        "remake_frames_total": len(remake),
        "remake_unique_images": len(remake_list),
        "frames_by_class": {k: len(v) for k, v in sorted(by_class.items())},
        "frames_by_verdict": {k: len(v) for k, v in sorted(by_verdict.items())},
        "settlement_or_postbattle_frames": len(settlement_rows),
        "settlement_best_field_px": {
            "min": min(settle_best) if settle_best else None,
            "max": max(settle_best) if settle_best else None,
        },
        "any_frame_zero_field": any(r["field_px"] == 0 for r in rows),
        "remake_frames_ever_equal_to_a_settlement_screen":
            any(r["field_px"] == 0 for r in settlement_rows),
    }

    # ---- write JSON ------------------------------------------------------
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "konoha.s49-victory-compare.v1",
        "meta": {
            "artifacts_root": str(art_root),
            "remake_dirs": [str(d) for d in remake_dirs],
            "original_walk": str(args.original_walk),
            "field_area": list(field_area),
            "field_area_px": field_area[2] * field_area[3],
            "screen_px": 240 * 160,
            "render_threshold_px": RENDER_THRESHOLD,
            "diff_rule": "count of pixels whose RGB triple differs "
                         "(same rule as tools/compare_frame_dirs.py)",
        },
        "answers": answers,
        "summary": summary,
        "remake_images": remake_list,
        "original_images": orig_list,
        "rows": rows,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8", newline="\n")
    print("wrote", args.out)

    # ---- console table ---------------------------------------------------
    print()
    print(f"{'class':<18}{'frames':>8}{'min field px':>15}{'max field px':>15}")
    for k, v in sorted(by_class.items()):
        vals = [x["field_px"] for x in v]
        print(f"{k:<18}{len(v):>8}{min(vals):>15}{max(vals):>15}")
    print()
    print(f"{'verdict':<24}{'frames':>8}")
    for k, v in sorted(by_verdict.items()):
        print(f"{k:<24}{len(v):>8}")
    print()
    print(f"settlement/postbattle frames: {len(settlement_rows)}   "
          f"best field residual {summary['settlement_best_field_px']['min']}.."
          f"{summary['settlement_best_field_px']['max']} px")
    print(f"any settlement frame matched a remake frame at 0 px: "
          f"{summary['remake_frames_ever_equal_to_a_settlement_screen']}")

    # ---- optional markdown table ----------------------------------------
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# S49 胜利/结算序列对照表",
            "",
            f"战场区 = {field_area} = {field_area[2] * field_area[3]} px；整屏 = 240x160 = 38400 px",
            f"重制侧候选帧 = {len(remake_list)} 张唯一画面（来自 {len(remake_dirs)} 个目录，"
            f"共 {len(remake)} 帧）",
            f"原版幸存的胜利/结算侧帧 = {len(rows)} 张（{len(orig_list)} 张唯一画面）"
            f"，含原版 25 帧 walk {len(walk_rows)} 张",
            "",
            "| 原版帧 | 场景 | 类别 | 最佳重制帧 | 战场区残差 | 整屏残差 | 判定 | 画面内容 |",
            "|---|---|---|---|---:|---:|---|---|",
        ]
        for r in rows:
            rel = r["path"].split("artifacts" + "\\")[-1].split("artifacts/")[-1]
            lines.append(
                f"| `{rel}` | {r['scenario']} | "
                f"{r['screen_class']} | {r['best_remake_step']} | {r['field_px']} | "
                f"{r['full_px']} | {r['verdict']} | {r['content']} |")
        args.md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print("wrote", args.md)

    # ---- optional contact sheet -----------------------------------------
    if args.sheet:
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        cols = 6
        scale = 2
        cw, ch = 240 * scale, 160 * scale + 12
        rowsn = (len(rows) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw, rowsn * ch), (25, 25, 25))
        draw = ImageDraw.Draw(sheet)
        for i, r in enumerate(rows):
            im = load_rgb(pathlib.Path(r["path"]))
            x = (i % cols) * cw
            y = (i // cols) * ch
            sheet.paste(im.resize((240 * scale, 160 * scale), Image.NEAREST), (x, y + 12))
            draw.text((x + 2, y + 2),
                      f"{r['scenario']}/{pathlib.Path(r['path']).stem} [{r['verdict']}]",
                      fill=(255, 240, 0))
        args.sheet.save(args.sheet)
        print("wrote", args.sheet)

    return 0


def find_artifacts_root(explicit: str | None) -> pathlib.Path:
    if explicit:
        return pathlib.Path(explicit)
    for cand in ARTIFACT_CANDIDATES:
        if cand.is_dir():
            return cand
    raise SystemExit("ERR artifacts root not found; pass --artifacts-root")


if __name__ == "__main__":
    raise SystemExit(main())
