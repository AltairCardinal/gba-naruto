#!/usr/bin/env python3
"""Enumerate every wiring point between the reverse results and the remake.

The provenance registry (``tools/audit_butano_reverse_provenance.py``) already
records the *declared* wires: every generated product states which reverse
family it consumes and which ROM bytes it read.  That registry is the truth
about the wires that exist -- but it is not the truth about the wires that are
missing, because a wire can only be declared by a product that somebody
wrote.  Three things stay invisible when you only look at the registry:

* a reverse family that **nobody consumes** -- the result is closed and
  shipped, and the remake re-derives the same thing from the ROM instead;
* a remake artifact that **consumes nothing** -- a hand-written header or a
  content bank with no source at all, so nobody can say where its bytes came
  from;
* a wire that exists but has **no gate** -- the product is declared, but
  nothing in ``tests/`` would notice if the bytes drifted.

So the complete answer needs both sides enumerated, not one:

* **source side** -- every reverse family, from the index;
* **sink side** -- every remake artifact that can carry a source, grouped by
  the mechanism that could carry it (generated product / hand-written header /
  content bank / graphic asset / gate).

Each source family and each sink then gets exactly one state:

``wired-and-gated``
    a declared product binds the family *and* something in ``tests/`` names
    that product.
``wired-ungated``
    a declared product binds the family, but no test names the product.  The
    wire exists and nothing would catch it rotting.
``on-shelf``
    the family is ``accepted``, carries a payload and is bound to nothing.
    This is the backlog: closed, importable, unconsumed.
``not-importable``
    the family carries no importable payload -- a control-flow or coverage
    analysis.  It constrains behaviour, it is not material.
``unclassified``
    the family is on the shelf but the tier probe could not decide what it
    is.  It is reported, not forced.

The sink side gets its own census, because "which products have no source" is
a different question from "which families have no consumer":

``declared``
    the product is in a generator's ``GENERATED_PRODUCTS`` and carries a
    provenance declaration.
``declared-not-applicable``
    the product is declared and states, with a reason, that it consumes no
    reverse result.
``undeclared``
    the file is remake source or data that no generator claims and that
    carries no source declaration.

The gate side of the matrix is an **upper bound**, not a verdict: a test that
names a product may be a behavioural gate or merely a documentation test.  The
receipt says so, and the count is labelled ``gate_upper_bound``.

Usage::

    python3 tools/measure_butano_wiring_coverage.py \\
        --root . \\
        --backlog artifacts/butano-usable-backlog-v1/backlog.json \\
        --out-dir artifacts/butano-wiring-coverage-v1
"""

from __future__ import annotations

import argparse
import ast
import collections
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.audit_butano_reverse_provenance import audit  # noqa: E402

WIRING_SCHEMA = "konoha.butano-wiring-coverage.v1"

#: Source-side states.
STATE_WIRED_GATED = "wired-and-gated"
STATE_WIRED_UNGATED = "wired-ungated"
STATE_SHELF = "on-shelf"
STATE_NOT_IMPORTABLE = "not-importable"
STATE_UNCLASSIFIED = "unclassified"
STATE_MENTIONED = "wired-mentioned"
STATE_NO_MATERIAL = "no-material"
STATE_IMPORTED_GATED = "imported-and-gated"
STATE_IMPORTED_UNGATED = "imported-ungated"
STATE_VERIFIED_AGAINST = "verified-against"
STATE_LOCAL_MISSING = "local-derivation-missing"
STATE_LOCAL_IDENTICAL = "local-rederived-identical"
STATE_LOCAL_DIVERGED = "local-rederived-diverged"

#: Sink-side states.
SINK_DECLARED = "declared"
SINK_DECLARED_NA = "declared-not-applicable"
SINK_UNDECLARED = "undeclared"

#: Suffixes that can carry a ``reverse-source`` declaration today.  Only the
#: C++ header carrier exists, so only headers can be declared; the other
#: surfaces are censused, not declared, until a carrier exists for them.
C_HEADER_SUFFIXES = (".h", ".hpp", ".c", ".cpp")

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".json",
    ".md",
    ".py",
    ".txt",
}

SKIP_DIRS = {".git", "__pycache__", "node_modules", "third_party", ".venv"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_text_files(root: Path) -> list[tuple[str, str]]:
    """Every text file under ``tests/``, as ``(relative path, text)``."""
    base = root / "tests"
    found: list[tuple[str, str]] = []
    if not base.is_dir():
        return found
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 4 * 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:  # pragma: no cover - defensive
            continue
        found.append((str(path.relative_to(root)), text))
    return found


def _reference_kinds(root: Path, families: list[str]) -> dict[str, list[str]]:
    """Where each family is named in the build chain, and how.

    ``evidence`` means the family is only read as *evidence* -- a verifier
    opening its manifest to check that the reverse result still holds.  The
    remake does not consume its payload, so this is a check, not a wire.
    ``consume`` means something else names it, which needs a human read.
    """
    kinds: dict[str, list[str]] = {family: [] for family in families}
    for base in ("tools", "butano-sequel", "sequel"):
        root_dir = root / base
        if not root_dir.is_dir():
            continue
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # pragma: no cover - defensive
                continue
            relative = str(path.relative_to(root))
            for family in families:
                if family in text:
                    kinds[family].append(relative)
    return kinds


def _gate_evidence(tests: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Which test files gate which product.

    Two links count, because both are real:

    * a test that names the **product path** -- the direct form;
    * a test that **imports the generator module** that writes the product --
      the indirect form, and the one the importers use.  A test module that
      imports ``tools.butano.import_rom_pixel_ab_baselines`` gates every
      family that importer pins, because that module's ``verify`` subcommand
      re-hashes the manifest and the copied files.

    This is an upper bound on "has a gate": a test that mentions a product may
    be a behavioural gate or a documentation test.  The receipt says so.
    """
    evidence: dict[str, list[str]] = collections.defaultdict(list)
    for rel, text in tests:
        for product in _PRODUCT_PATHS:
            if product in text:
                evidence[product].append(rel)
        for product, generator in _PRODUCT_GENERATORS.items():
            module = generator[:-3].replace("/", ".") if generator.endswith(".py") else generator
            if module in text:
                evidence[product].append(rel)
    return evidence


_PRODUCT_PATHS: list[str] = []
_PRODUCT_GENERATORS: dict[str, str] = {}


def _read_importer_specs(root: Path) -> dict[str, dict[str, Any]]:
    """The families the importers pin by manifest SHA-256.

    The provenance carrier (a ``reverse-source`` header comment) is not the
    only way this tree binds a product to a reverse family.  The two ROM
    importers carry their own contract: a family plus the SHA-256 of its
    manifest, checked at run time, with the files copied into this tree.
    That is a declared wire too -- and it is the contract that put the 32
    pixel-A/B baselines and the 22 relocation specs here in the first place.

    Reading only the header carrier would report those 54 families as
    "mentioned but not declared", which understates what is actually wired.
    """
    specs: dict[str, dict[str, Any]] = {}
    for relative in (
        "tools/butano/import_rom_pixel_ab_baselines.py",
        "tools/butano/import_rom_relocation_specs.py",
    ):
        path = root / relative
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - defensive
            continue
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign) or not isinstance(
                node.target, ast.Name
            ):
                continue
            if not node.target.id.endswith("_FAMILIES"):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            for family, manifest_sha256 in value:
                specs.setdefault(
                    family,
                    {
                        "manifest_sha256": manifest_sha256,
                        "importers": [],
                    },
                )["importers"].append(relative)
    return specs


def _census_sinks(root: Path) -> dict[str, Any]:
    """Count the remake artifacts that could carry a source declaration."""
    konoha = root / "butano-sequel" / "game" / "include" / "konoha"
    generated = sorted(p.name for p in konoha.glob("generated_*.h")) if konoha.is_dir() else []
    handwritten = (
        sorted(p.name for p in konoha.glob("*.h") if not p.name.startswith("generated_"))
        if konoha.is_dir()
        else []
    )
    banks = (
        sorted(str(p.relative_to(root)) for p in (root / "sequel" / "content").glob("*/bank.json"))
        if (root / "sequel" / "content").is_dir()
        else []
    )
    graphics_dir = root / "butano-sequel" / "graphics"
    graphics = (
        sorted(p.name for p in graphics_dir.iterdir() if p.is_file())
        if graphics_dir.is_dir()
        else []
    )
    tests = sorted(p.name for p in (root / "tests").glob("test_*.py")) if (root / "tests").is_dir() else []
    src = root / "butano-sequel" / "game" / "src"
    sources = sorted(p.name for p in src.glob("*.cpp")) if src.is_dir() else []
    return {
        "generated_headers": len(generated),
        "handwritten_headers": len(handwritten),
        "content_banks": len(banks),
        "graphic_assets": len(graphics),
        "game_sources": len(sources),
        "test_modules": len(tests),
        "_generated": generated,
        "_handwritten": handwritten,
        "_banks": banks,
    }


def measure(
    root: Path,
    backlog_path: Path,
    gap_path: Path,
    index_path: Path,
    reverse_root: Path,
) -> dict[str, Any]:
    global _PRODUCT_PATHS

    for path in (backlog_path, gap_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(f"input not found: {path}")
    backlog = _read_json(backlog_path)
    gap = _read_json(gap_path)
    index = _read_json(index_path)
    shelf_by_id = {row["id"]: row for row in backlog.get("shelf") or []}
    gap_status = {
        str(row.get("id")): str(row.get("status"))
        for row in (gap.get("rows") or [])
        if row.get("id")
    }
    families = {
        str(entry.get("id")): str(entry.get("category") or "other")
        for entry in (index.get("entries") or [])
        if entry.get("kind") == "artifact" and entry.get("id")
    }

    report = audit(root=root, reverse_root=reverse_root)
    products = list(report.products)
    _PRODUCT_PATHS = [product.path for product in products]
    _PRODUCT_GENERATORS.update(
        {product.path: product.generator for product in products}
    )

    tests = _collect_text_files(root)
    gates = _gate_evidence(tests)
    imported = _read_importer_specs(root)

    # -- source side ---------------------------------------------------
    source_rows: list[dict[str, Any]] = []
    bound_families: dict[str, list[str]] = collections.defaultdict(list)
    for product in products:
        for family in product.families:
            bound_families[family].append(product.path)

    reference_kinds = _reference_kinds(
        root,
        [
            family
            for family in families
            if family not in imported and family not in bound_families
        ],
    )

    for family_id, category in sorted(families.items()):
        consumers = bound_families.get(family_id, [])
        # The gate evidence is keyed by product; the receipt wants the test
        # files that provide it, not the product path.
        gated = [test for path in consumers for test in gates.get(path, [])]
        shelf_row = shelf_by_id.get(family_id)
        importer = imported.get(family_id)
        if importer:
            # Bound by manifest SHA-256 and copied into this tree.  The
            # products live under the importer's own output directory, so
            # the gate evidence is looked up by that path.
            consumer_paths = [
                f"artifacts/butano-reverse-m3-import-v1/{'pixel-ab' if 'pixel_ab' in path else 'relocation'}/{family_id}"
                for path in importer["importers"]
            ]
            importer_gates = sorted(
                {
                    rel
                    for rel, text in tests
                    for path in importer["importers"]
                    if path[:-3].replace("/", ".") in text
                }
            )
            gated = importer_gates or [
                path for path in consumer_paths if gates.get(path)
            ]
            state = STATE_IMPORTED_GATED if gated else STATE_IMPORTED_UNGATED
            source_rows.append(
                {
                    "id": family_id,
                    "category": category,
                    "tier": "importer-pinned",
                    "scope_closed": None,
                    "payload_bytes": 0,
                    "state": state,
                    "consumers": consumer_paths,
                    "gated_by": gated,
                    "gate_upper_bound": bool(gated),
                    "consumption_status": gap_status.get(family_id, "none"),
                    "importers": importer["importers"],
                    "manifest_sha256": importer["manifest_sha256"],
                }
            )
            continue
        if consumers:
            # A declared wire: the product states this family and the ROM
            # bytes it read.  This is a fact, not a name match.
            state = STATE_WIRED_GATED if gated else STATE_WIRED_UNGATED
            tier = "declared-consumer"
            scope_closed = None
            payload_bytes = 0
        elif gap_status.get(family_id) == "build":
            # The build chain mentions the family but no product declares it.
            # This is the gap tool's lower bound: the name shows up, but
            # nothing states that a single byte of lineage runs through it.
            references = reference_kinds.get(family_id, [])
            evidence_only = bool(references) and all(
                "/verify_" in ref or ref.startswith("tests/") for ref in references
            )
            if evidence_only:
                state = STATE_VERIFIED_AGAINST
                tier = "verified-against"
            else:
                # The family name is used by a remake-side tool as a schema
                # tag, and that tool writes into this tree's own
                # ``artifacts/<family>/``.  Whether that copy is actually
                # here -- and whether it still matches the reverse tree's
                # original -- decides whether the remake re-derived the
                # result or merely left a tool that would.
                local_manifest = root / "artifacts" / family_id / "manifest.json"
                reverse_manifest = reverse_root / "artifacts" / family_id / "manifest.json"
                if not local_manifest.is_file():
                    state = STATE_LOCAL_MISSING
                    tier = "local-output-absent"
                elif not reverse_manifest.is_file():
                    state = STATE_LOCAL_MISSING
                    tier = "local-only-no-reverse-twin"
                elif _sha256(local_manifest) == _sha256(reverse_manifest):
                    state = STATE_LOCAL_IDENTICAL
                    tier = "local-rederived"
                else:
                    state = STATE_LOCAL_DIVERGED
                    tier = "local-rederived"
            scope_closed = None
            payload_bytes = 0
        elif shelf_row is not None:
            tier = shelf_row["tier"]
            scope_closed = shelf_row["scope_closed"]
            payload_bytes = shelf_row["payload_bytes"]
            if tier == "unclassified":
                state = STATE_UNCLASSIFIED
            elif tier == "analysis-only":
                state = STATE_NOT_IMPORTABLE
            else:
                state = STATE_SHELF
        else:
            state = STATE_NO_MATERIAL
            tier = "no-payload"
            scope_closed = None
            payload_bytes = 0
        source_rows.append(
            {
                "id": family_id,
                "category": category,
                "tier": tier,
                "scope_closed": scope_closed,
                "payload_bytes": payload_bytes,
                "state": state,
                "consumers": consumers,
                "gated_by": gated,
                "gate_upper_bound": bool(gated),
                "consumption_status": gap_status.get(family_id, "none"),
                "references": reference_kinds.get(family_id, [])[:8],
            }
        )

    source_rows.sort(key=lambda row: (row["state"], row["category"], row["id"]))

    # -- sink side -----------------------------------------------------
    sink_rows: list[dict[str, Any]] = []
    for product in products:
        sink_rows.append(
            {
                "path": product.path,
                "generator": product.generator,
                "state": SINK_DECLARED if product.families else SINK_DECLARED_NA,
                "families": list(product.families),
                "reasons": list(product.reasons),
                "gated_by": gates.get(product.path, []),
            }
        )
    sink_rows.sort(key=lambda row: row["path"])

    census = _census_sinks(root)
    sinks_by_state = collections.Counter(row["state"] for row in sink_rows)
    source_by_state = collections.Counter(row["state"] for row in source_rows)

    return {
        "schema": WIRING_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": {
            "backlog": {
                "path": str(backlog_path.relative_to(root))
                if backlog_path.is_relative_to(root)
                else str(backlog_path),
                "sha256": _sha256(backlog_path),
            },
            "gap": {
                "path": str(gap_path.relative_to(root))
                if gap_path.is_relative_to(root)
                else str(gap_path),
                "sha256": _sha256(gap_path),
            },
            "index": {
                "path": str(index_path.relative_to(root))
                if index_path.is_relative_to(root)
                else str(index_path),
                "sha256": _sha256(index_path),
            },
            "reverse_root": str(reverse_root),
        },
        "rules": {
            "wired": "a declared product binds the family",
            "gated": "a test file names the product -- an UPPER BOUND, not a verdict",
            "shelf": "accepted, carries a payload, bound to no product",
            "not_importable": "no importable payload: control-flow / coverage analysis",
            "wired_mentioned": "the build chain names the family but NO product declares it -- the "
            "gap tool's lower bound, not a proven lineage",
            "imported": "the family is pinned by manifest SHA-256 in a ROM importer and its files "
            "are copied into this tree -- a declared wire through the importer's own carrier",
            "verified_against": "the family is only read as evidence by a verifier; the remake does "
            "not consume its payload",
            "local_derivation": "a remake-side tool uses the family name as a schema tag and writes "
            "this tree's own artifacts/<family>/ -- the state says whether that copy is present and "
            "whether it still matches the reverse tree's original",
            "no_material": "neither declared, nor mentioned by the build chain, nor carrying "
            "importable payload",
            "sink_declared": "product is in a generator's GENERATED_PRODUCTS and carries a declaration",
            "sink_undeclared": "remake source or data that no generator claims and that carries no declaration",
        },
        "summary": {
            "source_total": len(source_rows),
            "source_by_state": dict(sorted(source_by_state.items())),
            "sink_total": len(sink_rows),
            "sink_by_state": dict(sorted(sinks_by_state.items())),
            "families_bound": len(bound_families),
            "families_imported": len(imported),
            "products_gated_upper_bound": sum(
                1 for row in sink_rows if row["gated_by"]
            ),
            "sink_surface": {
                key: value
                for key, value in census.items()
                if not key.startswith("_")
            },
        },
        "source_rows": source_rows,
        "sink_rows": sink_rows,
        "sink_surface": census,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines: list[str] = []
    lines.append("# 接线覆盖矩阵（自动生成）")
    lines.append("")
    lines.append("本文件由 `tools/measure_butano_wiring_coverage.py` 生成，不要手工编辑。")
    lines.append("")
    lines.append("**接线点 = （逆向族, 复刻产物）二元组。** 两端都要枚举，缺一端就查不全。")
    lines.append("")
    lines.append("## 口径")
    lines.append("")
    for key, value in payload["rules"].items():
        lines.append(f"- **{key}**：{value}")
    lines.append("")
    lines.append("## source 侧（逆向族）")
    lines.append("")
    lines.append("| 状态 | 族数 |")
    lines.append("| --- | ---: |")
    meaning = {
        STATE_WIRED_GATED: "已接线，且有测试提到该产物（**上界**，不等于行为门禁）",
        STATE_WIRED_UNGATED: "已接线，但没有任何测试提到该产物——线存在，烂了没人知道",
        STATE_SHELF: "已闭合且带 payload，**没有任何产物接它**",
        STATE_UNCLASSIFIED: "在货架上但分层判不出来，要人读",
        STATE_NOT_IMPORTABLE: "不是可导入素材（控制流／覆盖分母），只约束行为",
        STATE_MENTIONED: "构建链**提到**这个族，但没有任何产物声明它——名字引用，不是血缘",
        STATE_NO_MATERIAL: "既没声明、也没被构建链提到、也没有可导入 payload",
        STATE_IMPORTED_GATED: "**导入器钉了 manifest 哈希**，文件已复制进复刻树，且有门禁",
        STATE_IMPORTED_UNGATED: "**导入器钉了 manifest 哈希**，文件已复制进复刻树，但无门禁",
        STATE_VERIFIED_AGAINST: "只被 `verify_*` 当证据核对，复刻侧不消费其 payload",
        STATE_LOCAL_MISSING: "复刻侧有 exporter（用族名做 schema 标识），但**本地产物不在工作树里**",
        STATE_LOCAL_IDENTICAL: "复刻侧本地重导出，manifest 与逆向树**逐字节相同**",
        STATE_LOCAL_DIVERGED: "复刻侧本地重导出，但 manifest 与逆向树**已经分叉**",
    }
    for state, count in summary["source_by_state"].items():
        lines.append(f"| `{state}` | {count} |")
    lines.append("")
    lines.append("## sink 侧（复刻产物）")
    lines.append("")
    lines.append("| 状态 | 产物数 |")
    lines.append("| --- | ---: |")
    lines.append(f"| `{SINK_DECLARED}`（绑定了族） | {summary['sink_by_state'].get(SINK_DECLARED, 0)} |")
    lines.append(
        f"| `{SINK_DECLARED_NA}`（声明了「不消费逆向结果」+ 理由） | "
        f"{summary['sink_by_state'].get(SINK_DECLARED_NA, 0)} |"
    )
    lines.append("")
    lines.append("### 未登记的 sink 面（**没有接线声明**的部分）")
    lines.append("")
    surface = summary["sink_surface"]
    lines.append("| 面 | 数量 | 有载体吗 |")
    lines.append("| --- | ---: | --- |")
    lines.append(f"| 生成器产物（generated header） | {surface['generated_headers']} | ✅ 已登记 |")
    lines.append(
        f"| 手写头（`konoha/*.h`，非 generated） | {surface['handwritten_headers']} | ❌ 无载体 |"
    )
    lines.append(f"| 内容库（`sequel/content/*/bank.json`） | {surface['content_banks']} | ❌ 无载体 |")
    lines.append(f"| 图形资产（`butano-sequel/graphics/`） | {surface['graphic_assets']} | ❌ 无载体 |")
    lines.append(f"| 运行时源码（`game/src/*.cpp`） | {surface['game_sources']} | ❌ 无载体 |")
    lines.append(f"| 门禁（`tests/test_*.py`） | {surface['test_modules']} | — |")
    lines.append("")
    lines.append("## 未接线的族（on-shelf，按类别）")
    lines.append("")
    shelf = [row for row in payload["source_rows"] if row["state"] == STATE_SHELF]
    by_cat: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in shelf:
        by_cat[row["category"]].append(row)
    lines.append("| 类别 | 族数 | 族 |")
    lines.append("| --- | ---: | --- |")
    for category in sorted(by_cat):
        names = ", ".join(f"`{row['id']}`" for row in by_cat[category][:12])
        if len(by_cat[category]) > 12:
            names += " …"
        lines.append(f"| {category} | {len(by_cat[category])} | {names} |")
    lines.append("")
    lines.append("## 已接线但无门禁的族")
    lines.append("")
    ungated = [row for row in payload["source_rows"] if row["state"] == STATE_WIRED_UNGATED]
    lines.append(f"共 **{len(ungated)}** 族（线在，但没有测试提到它的产物）：")
    lines.append("")
    for row in ungated:
        lines.append(
            f"- `{row['id']}` → {', '.join('`' + path + '`' for path in row['consumers'])}"
        )
    lines.append("")
    lines.append("## 边界声明")
    lines.append("")
    lines.append("- 「有门禁」是**上界**：测试提到产物路径可能是文档类测试，不等于行为门禁。")
    lines.append("- sink 侧的未登记面**只是盘点**，不是缺陷判定——手写头与内容库本来就不消费逆向族 payload。")
    lines.append("- 本工具不判定「该接哪个族」：那是按子系统的设计决定，不是脚本能读出来的事实。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enumerate every wiring point between the reverse results and the remake."
    )
    parser.add_argument("--root", default=Path("."), type=Path)
    parser.add_argument(
        "--backlog",
        default=Path("artifacts/butano-usable-backlog-v1/backlog.json"),
        type=Path,
    )
    parser.add_argument(
        "--gap",
        default=Path("artifacts/butano-reverse-gap-v1/gap.json"),
        type=Path,
    )
    parser.add_argument(
        "--index",
        default=Path("artifacts/reverse-results-index-v1/index.json"),
        type=Path,
    )
    parser.add_argument(
        "--reverse-root", default=Path("/Users/altair/github/gba-naruto-reverse"), type=Path
    )
    parser.add_argument(
        "--out-dir", default=Path("artifacts/butano-wiring-coverage-v1"), type=Path
    )
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        payload = measure(
            root=root,
            backlog_path=args.backlog,
            gap_path=args.gap,
            index_path=args.index,
            reverse_root=args.reverse_root,
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wiring.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "wiring.md").write_text(render_markdown(payload), encoding="utf-8")

    summary = payload["summary"]
    print(f"wrote {out_dir / 'wiring.json'}")
    print(f"wrote {out_dir / 'wiring.md'}")
    print(f"source states: {summary['source_by_state']}")
    print(f"sink states:   {summary['sink_by_state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
