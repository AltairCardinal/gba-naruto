#!/usr/bin/env python3
"""Group the remake's graphic assets by the generator that produced them.

``docs/butano-wiring-roadmap.md`` (W3, action 2, third part) asks that the
1,819 graphic assets be grouped **by generator** with a sidecar per group,
instead of a declaration per file.

The grouping has to be *measured*, not guessed.  Three rules do it, each
recorded as evidence on the asset it decided:

``literal``
    the generator's source names the asset outright;
``pattern``
    one of the generator's f-string / format-string literals matches the
    asset name once the placeholders are read as wildcards;
``prefix``
    the asset's stem starts with the generator's own name.

An asset no rule explains is **not** quietly dropped: it lands in the
receipt's ``unattributed`` list, which is the gray zone made visible.  The
sidecar also records whether the generator declares a reverse family
(``reverse-source``); when it does not, that is said out loud too.

The tool is idempotent: the sidecars it writes are a pure function of the
tree, so a second run produces the same bytes.

Usage::

    python3 tools/butano/annotate_graphic_asset_provenance.py \\
        --root . \\
        --out-dir artifacts/butano-graphic-asset-provenance-v1
"""

from __future__ import annotations

import argparse
import datetime
import ast
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "konoha.butano-graphic-asset-provenance.v1"
SIDECAR_SCHEMA = "konoha.butano-graphic-asset-sidecar.v1"

EXIT_OK = 0
EXIT_INPUT_ERROR = 2

#: The directories the graphic assets live in.
GRAPHIC_DIRS = ("butano-sequel/graphics",)

#: Where the assets live, resolved once.
GRAPHIC_ROOT = Path("butano-sequel/graphics")

#: A generator is a tool whose name says it generates something.
GENERATOR_GLOBS = ("tools/generate_*.py", "tools/butano/generate_*.py", "tools/export_*.py", "tools/butano/export_*.py")

#: An f-string literal, e.g. ``f"battle_{ch_id:02d}_map_{name}.png"``.
_FSTRING = re.compile(r'f"([^"]*)"')
#: A ``%``-format literal, e.g. ``"atlas_%03d.png"``.
_PCTFORMAT = re.compile(r'"([^"\n]*%[0-9]*d[^"\n]*)"')
#: ``{placeholder}`` inside an f-string.
_PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def _mtime_minute(path: Path) -> str:
    """The minute a file was last written, as a comparable string."""
    import time

    return time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))


def _mtime_clusters(
    graphics_dir: Path,
    unique: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    """For each generator, the minutes its own assets were written in."""
    clusters: dict[str, set[str]] = {}
    for path, info in unique.items():
        minutes = set()
        for asset in info["assets"]:
            candidate = graphics_dir / asset
            if candidate.is_file():
                minutes.add(_mtime_minute(candidate))
        clusters[path] = minutes
    return clusters


def _declared_sources(generator: Path) -> list[dict[str, str]]:
    """The reverse families a generator declares through ``provenance_block``.

    The generators that consume a reverse result already declare it with the
    tree's own contract::

        PROVENANCE = provenance_block(
            sources=(("rom-...-v1", "<manifest sha256>"),), roms=(...))

    That declaration is the machine-readable form of "where do my bytes come
    from", so the sidecar reads it instead of grepping the source.
    """
    try:
        tree = ast.parse(
            generator.read_text(encoding="utf-8"), filename=generator.as_posix()
        )
    except (OSError, SyntaxError):
        return []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "PROVENANCE"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg != "sources":
                continue
            try:
                entries = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError):
                continue
            out: list[dict[str, str]] = []
            for entry in entries:
                if isinstance(entry, (tuple, list)) and len(entry) == 2:
                    out.append(
                        {"family": str(entry[0]), "manifest_sha256": str(entry[1])}
                    )
            return out
    return []


def _longest_fragment(stem: str) -> str | None:
    """The longest fixed fragment of an asset stem, e.g. ``_map_chunk_``."""
    parts = re.split(r"[_\-]|\d+", stem)
    parts = [part for part in parts if len(part) >= 5]
    if not parts:
        return None
    best = max(parts, key=len)
    return f"_{best}_"


def _fixed_prefix(pattern: str) -> str:
    """The literal text in front of a pattern's first placeholder.

    A pattern may only claim an asset whose name starts with this prefix.
    Without that rule a pattern such as ``atlas_%03d.png`` would match every
    asset in the directory through the wildcards, and the grouping would
    collapse into "everything matches everything".
    """
    cut = len(pattern)
    for marker in ("{", "%"):
        index = pattern.find(marker)
        if index != -1:
            cut = min(cut, index)
    return pattern[:cut]


def _pattern_to_regex(pattern: str) -> re.Pattern[str] | None:
    """Turn a generator's name pattern into a regular expression."""
    if "%" in pattern:
        # ``%02d`` / ``%d`` / ``%s``: one character class each.
        out: list[str] = []
        index = 0
        while index < len(pattern):
            char = pattern[index]
            if char == "%" and index + 1 < len(pattern):
                spec = pattern[index + 1]
                if spec == "%":
                    out.append("%")
                else:
                    out.append("[^/]*")
                index += 2
                continue
            out.append(re.escape(char))
            index += 1
        body = "".join(out)
    else:
        body = _PLACEHOLDER.sub("[^/]*", pattern)
    if not body:
        return None
    try:
        return re.compile(f"^{body}$")
    except re.error:
        return None


def _normalised_stem(generator: Path) -> str:
    stem = generator.stem
    stem = re.sub(r"^(generate|export|build)_", "", stem)
    stem = re.sub(r"_(assets|content|bundle|canvas|export)$", "", stem)
    if stem.startswith("butano_"):
        stem = stem[len("butano_") :]
    return stem


def collect_generators(root: Path) -> list[Path]:
    generators: set[Path] = set()
    for pattern in GENERATOR_GLOBS:
        generators.update(root.glob(pattern))
    return sorted(generators)


def generator_evidence(generator: Path, assets: list[str]) -> dict[str, Any]:
    """The literals, patterns and prefix one generator can be credited with."""
    source = generator.read_text(encoding="utf-8", errors="ignore")
    literals = {name for name in assets if name in source}
    patterns: list[str] = []
    for match in _FSTRING.finditer(source):
        text = match.group(1)
        if "." not in text:
            continue
        if any(text.endswith(extension) for extension in (".bmp", ".png", ".json", ".bin", ".4bpp", ".8bpp")):
            patterns.append(text)
    for match in _PCTFORMAT.finditer(source):
        text = match.group(1)
        if any(text.endswith(extension) for extension in (".bmp", ".png", ".json", ".bin")):
            patterns.append(text)
    # A name built by concatenating two f-strings never appears whole in the
    # source.  Pairs of f-strings that sit close together are therefore
    # concatenated as well, so a name such as
    # ``battle_{battle_id:02d}_map_chunk_{index}`` can still be recognised.
    # (Concatenating two f-strings that both carry a placeholder does NOT
    # rebuild the name -- the two fragments overlap in the variable part.
    # A concatenation rule was tried and removed.)
    # A symbol name without an extension ("battle_{id:02d}_map_chunk_{index}")
    # names a graphic just as well as "atlas_%03d.png" does -- it is the C++
    # item name the graphic was generated for.  Such patterns are kept when
    # their fixed prefix is long enough to be specific.
    for match in _FSTRING.finditer(source):
        text = match.group(1)
        if "." in text:
            continue
        if "_" not in text:
            continue
        if len(_fixed_prefix(text)) < 6:
            continue
        if text not in patterns:
            patterns.append(text)
    prefix = _normalised_stem(generator)
    # A generator often names its outputs through a string constant
    # ("symbol_prefix=\"battle_ninja_tool_bomb_projectile\"").  Those
    # constants are the most specific prefix available, so they are collected
    # as candidates too.
    constant_prefixes = sorted(
        {
            match.group(1)
            for match in re.finditer(
                r'"([a-z][a-z0-9]*(?:_[a-z0-9]+){1,})"', source
            )
            if len(match.group(1)) >= 8
        }
    )
    declared_family = None
    family_match = re.search(r"reverse-source:\s*([A-Za-z0-9_.\-]+)", source)
    if family_match:
        declared_family = family_match.group(1)
    return {
        "source": source,
        "constant_prefixes": constant_prefixes,
        "literals": sorted(literals),
        "patterns": sorted(set(patterns)),
        "prefix": prefix,
        "declared_reverse_family": declared_family,
        "declared_families": _declared_sources(generator),
    }


def attribute(
    generators: list[Path],
    assets: list[str],
    graphics_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Attribute every asset to at most one generator, with the evidence."""
    evidence = {generator.as_posix(): generator_evidence(generator, assets) for generator in generators}
    owners: dict[str, list[tuple[str, str]]] = {}
    for name in assets:
        hits: list[tuple[str, str]] = []
        stem = name.split(".")[0]
        for path, info in evidence.items():
            rule = None
            if name in info["literals"]:
                rule = "literal"
            else:
                for pattern in info["patterns"]:
                    prefix = _fixed_prefix(pattern)
                    if len(prefix) < 6 or not name.startswith(prefix):
                        continue
                    compiled = _pattern_to_regex(pattern)
                    if compiled is not None and compiled.match(name):
                        rule = "pattern"
                        break
            if rule is None:
                prefix = info["prefix"]
                if prefix and (stem.startswith(prefix + "_") or stem == prefix):
                    rule = "prefix"
            if rule is None:
                for candidate in info.get("constant_prefixes", ()):
                    if stem.startswith(candidate + "_") or stem == candidate:
                        rule = "constant"
                        break
            # A "fragment" rule (does any fixed piece of the name appear in
            # the source?) was tried and **rejected**: pieces like
            # ``_character_`` occur in many generators, so it turns 1,600
            # unambiguous attributions into 1,700 ambiguous ones.  A rule
            # that guesses is worse than an open list.
            if rule is not None:
                hits.append((path, rule))
        owners[name] = hits
    unique: dict[str, dict[str, Any]] = {}
    ambiguous: list[dict[str, str]] = []
    unattributed: list[dict[str, str]] = []
    # A specific rule beats a loose one: a generator that names an asset
    # outright (or by pattern) owns it, even if another generator's name
    # happens to be a prefix of it.
    strength = {"literal": 3, "pattern": 2, "constant": 2, "prefix": 1}
    pre_disambiguation = {name: list(hits) for name, hits in owners.items()}
    for name, hits in list(owners.items()):
        if len(hits) > 1:
            best = max(strength.get(rule, 0) for _path, rule in hits)
            hits = [hit for hit in hits if strength.get(hit[1], 0) == best]
            owners[name] = hits
    # Still tied?  A run writes its whole batch in the same minute, so the
    # generator whose own assets carry the same minute is the producer.
    # A candidate's own batch was written in one minute, so the minutes of the
    # assets it matched identify its runs.  The clusters have to be built from
    # the *pre-disambiguation* matches: a candidate that has not won a single
    # asset yet is exactly the one that needs this rule.
    clusters: dict[str, set[str]] = {}
    for asset, hits in pre_disambiguation.items():
        for path, _rule in hits:
            minute = _mtime_minute(graphics_dir / asset)
            if minute:
                clusters.setdefault(path, set()).add(minute)
    for name, hits in list(owners.items()):
        if len(hits) <= 1:
            continue
        minute = _mtime_minute(graphics_dir / name)
        matching = [
            path for path, _rule in hits if minute in clusters.get(path, ())
        ]
        if len(matching) == 1:
            owners[name] = [hit for hit in hits if hit[0] == matching[0]]
    for name, hits in owners.items():
        if len(hits) == 1:
            path, rule = hits[0]
            unique.setdefault(path, {"assets": [], "rules": {}})["assets"].append(name)
            unique[path]["rules"][name] = rule
        elif len(hits) > 1:
            ambiguous.append(
                {"asset": name, "candidates": ", ".join(sorted(path for path, _ in hits))}
            )
        else:
            unattributed.append({"asset": name})
    return unique, ambiguous + unattributed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/butano-graphic-asset-provenance-v1"),
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    assets: list[str] = []
    for relative in GRAPHIC_DIRS:
        directory = root / relative
        if not directory.is_dir():
            print(f"missing graphic directory: {directory}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        assets.extend(
            sorted(
                path.name
                for path in directory.iterdir()
                if path.is_file() and not path.name.startswith(".")
            )
        )

    generators = collect_generators(root)
    unique, leftovers = attribute(generators, assets, GRAPHIC_ROOT)

    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    sidecar_dir = out_dir / "sidecars"
    sidecar_dir.mkdir(parents=True, exist_ok=True)

    groups: list[dict[str, Any]] = []
    for path, info in sorted(unique.items()):
        generator = root / path
        evidence = generator_evidence(generator, assets)
        sidecar = {
            "schema": SIDECAR_SCHEMA,
            "generator": path,
            "asset_count": len(info["assets"]),
            "assets": sorted(info["assets"]),
            "attribution_rules": dict(sorted(info["rules"].items())),
            "name_patterns": evidence["patterns"],
            "reverse_family": evidence["declared_reverse_family"],
            "declared_families": evidence.get("declared_families", []),
            "reverse_family_reason": (
                None
                if evidence["declared_reverse_family"]
                else "the generator declares no reverse-source family"
            ),
        }
        sidecar_path = sidecar_dir / (generator.stem + ".json")
        sidecar_path.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        groups.append(
            {
                "generator": path,
                "sidecar": (
                    sidecar_path.relative_to(root).as_posix()
                    if sidecar_path.is_relative_to(root)
                    else sidecar_path.as_posix()
                ),
                "asset_count": len(info["assets"]),
                "rules": dict(
                    sorted(
                        {
                            rule: sum(1 for r in info["rules"].values() if r == rule)
                            for rule in set(info["rules"].values())
                        }.items()
                    )
                ),
                "reverse_family": evidence["declared_reverse_family"],
                "declared_families": evidence.get("declared_families", []),
            }
        )

    declaration_gap = [
        group["generator"]
        for group in groups
        if not group.get("declared_families")
    ]
    ambiguous = [item for item in leftovers if "candidates" in item]
    unattributed = [item for item in leftovers if "candidates" not in item]
    summary = {
        "assets": len(assets),
        "generators": len(generators),
        "groups": len(groups),
        "attributed": sum(group["asset_count"] for group in groups),
        "ambiguous": len(ambiguous),
        "unattributed": len(unattributed),
        "generators_with_declared_family": len(groups) - len(declaration_gap),
        "generators_without_declared_family": len(declaration_gap),
    }
    payload = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": summary,
        "groups": groups,
        "ambiguous": ambiguous,
        "unattributed": unattributed,
        "declaration_gap": declaration_gap,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "provenance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 图形资产按生成器归组（自动生成）",
        "",
        "本文件由 `tools/butano/annotate_graphic_asset_provenance.py` 生成，"
        "不要手工编辑。",
        "",
        "| 项 | 值 |",
        "| --- | ---: |",
    ]
    for key, value in summary.items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "| 生成器 | 资产数 | 归属规则 | 逆向族 | sidecar |", "| --- | ---: | --- | --- | --- |"]
    for group in sorted(groups, key=lambda g: -g["asset_count"]):
        rules = ", ".join(f"{k}×{v}" for k, v in group["rules"].items())
        lines.append(
            f"| `{group['generator']}` | {group['asset_count']} | {rules} | "
            f"{group['reverse_family'] or '—'} | `{group['sidecar']}` |"
        )
    lines.append("")
    (out_dir / "provenance.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
