#!/usr/bin/env python3
"""Classify every reverse note into exactly one disposition bucket.

The reverse work tree holds 427 note files.  The gap measurement
(``tools/measure_butano_reverse_gap.py``) can say whether a note is
*mentioned* somewhere in the remake tree, but not what should happen with
it.  The M5 milestone of ``docs/butano-reverse-gap-roadmap.md`` asks for
exactly that: every note lands in one of four dispositions, and the
classification is produced by a script rather than by hand.

The buckets, in the order the rules are applied:

``implemented_in_code``
    the note is referenced from the remake's build chain
    (``butano-sequel/``, ``tools/``, ``sequel/``).  The row names the
    consuming file and the line, so the claim can be checked.
``not_applicable``
    the note is not about this remake: either it is a vendored snapshot of
    the reverse tree's own files carried inside an evidence bundle, or its
    subject is the reverse project's own engineering rather than the
    original game.  The row states which of the two it is and why.
``missing_evidence``
    the note's own deliverable is not established: it is a preflight, a
    plan, a gap list, or it says outright that the result is not promoted.
    These go back to the reverse side as a to-do.
``needs_guard``
    the note carries a conclusion about the original that this tree has
    not turned into a gate yet.  This is the raw material for M1 and M2.
``needs_human_review``
    the note matches none of the signals above.  This bucket is supposed
    to stay small, and every row in it says why it could not be decided
    automatically.

Two properties are load bearing and are pinned by
``tests/test_reverse_notes_index.py``:

* the script finds the notes by walking the reverse tree, and it never
  hard-codes a note name.  A roster of conclusions inside this file would
  raise the ``build`` count of the gap measurement by naming the very
  conclusions it claims to have classified.
* the script fails closed.  A missing reverse tree, an empty note set, an
  unresolvable consumer pointer or a classification that does not add up
  is a non-zero exit with a named reason -- never a quietly shorter index.

Usage::

    python3 tools/build_reverse_notes_index.py
    python3 tools/build_reverse_notes_index.py --reverse-root <path>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

NOTES_INDEX_SCHEMA = "konoha.reverse-notes-index.v1"

EXIT_OK = 0
EXIT_REVERSE_TREE_MISSING = 2
EXIT_NO_NOTES = 2
EXIT_INCONSISTENT = 3
EXIT_UNRESOLVED_POINTER = 3

# The buckets, in rule order.  ``needs_human_review`` is the last resort:
# it is allowed to exist, but it must stay small and every row must say
# why it could not be decided by a rule.
BUCKETS = (
    "implemented_in_code",
    "not_applicable",
    "missing_evidence",
    "needs_guard",
    "needs_human_review",
)

# Where a reference lands decides what it means.  The names and the order
# mirror the gap measurement so that the two agree on what "the build
# chain mentions it" means.
SCAN_ROOTS: tuple[tuple[str, str], ...] = (
    ("butano-sequel", "build"),
    ("tools", "build"),
    ("artifacts", "local_artifact"),
    ("tests", "test"),
    ("docs", "doc"),
    ("notes", "doc"),
    ("sequel", "build"),
)

STATUS_ORDER = ("build", "local_artifact", "test", "doc", "none")

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "third_party",
    ".pi",
}

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".cmake",
    ".cpp",
    ".css",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".json",
    ".lua",
    ".md",
    ".mako",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

# Identifiers shorter than this are too generic to search for as words, so
# the gap measurement only looks for them in their ``artifacts/<id>`` path
# form.  The same rule is used here so both tools agree.
MIN_BARE_IDENTIFIER = 8

MAX_FILE_BYTES = 4 * 1024 * 1024

# This tool's own outputs are the measuring apparatus, not a consumer, so
# they are excluded from the reference scan.  Without the exclusion the
# index would classify itself.
OWN_OUTPUT_PREFIXES = (
    "artifacts/reverse-notes-index-v1/",
    "docs/reverse-results-index/notes-index.md",
    "tools/build_reverse_notes_index.py",
)


def _load_excluded_prefixes() -> tuple[str, ...]:
    """The paths that are measuring apparatus rather than a consumer.

    The gap measurement already knows which files are its own apparatus
    (its output, the results index it reads, the roadmap that quotes the
    untouched families).  This tool reads the same list so that both
    agree on what "the tree references it" means; otherwise the status
    recorded here would drift from the status the gap tool reports.
    """
    try:
        from tools import measure_butano_reverse_gap as gap_tool
    except ImportError:  # running as a script from inside tools/
        import measure_butano_reverse_gap as gap_tool  # type: ignore[no-redef]
    return tuple(gap_tool.EXCLUDED_PREFIXES) + OWN_OUTPUT_PREFIXES

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# --- signal vocabulary -------------------------------------------------
#
# The signals below are rules, not a roster of notes.  They are deliberately
# narrow: a rule that fires on half the corpus tells the reader nothing.

# Original-game evidence: a ROM address, a reverse family name, or a
# pointer at a produced artifact directory.
ADDR_RE = re.compile(r"0x[0-9A-Fa-f]{4,}")
ROM_FAMILY_RE = re.compile(r"\brom-[a-z0-9][a-z0-9-]*")
ARTIFACT_REF_RE = re.compile(r"artifacts/[A-Za-z0-9_.-]+")
NOTE_REF_RE = re.compile(r"notes/([A-Za-z0-9_.-]+)\.md")

# The reverse project's own engineering: agents, benchmarks, work tree
# hygiene, guard runners.  Notes about these are not about the game.
PROCESS_RE = re.compile(
    r"(子代理|代理编码|Codex|Luna|Terra|benchmark|基准测试|计时基准|"
    r"工作树|worktree|分支隔离|清理审计|工具链编译|编译尝试|"
    r"API 所有权|run_guarded|守卫收据|资源守卫|token 成本|"
    r"模型对比|横向评测|子进程|工作流编排|吞吐量|吞吐|"
    r"误报|暂存|pre-commit|githooks|检查器|提交门禁|"
    r"恢复点|进度快照|锁争用|磁盘余量)"
)

# The same subject, but decided by the title.  A title says what a note
# is about far more reliably than a body full of quotes from other
# notes, so one title hit is enough to call a note a process note.
PROCESS_TITLE_RE = re.compile(
    r"(子代理|代理|Codex|Luna|Terra|benchmark|基准|计时|吞吐|"
    r"工作树|分支|清理|编译|工具链|守卫|门禁|暂存|提交|误报|"
    r"检查器|进度|快照|恢复点|编排|工作流|审计|审查|"
    r"依赖注入|可复现|复现命令)",
    re.IGNORECASE,
)

# The note declares its own result as not established.
OPEN_TITLE_RE = re.compile(
    r"(preflight|work-plan|remaining-|next[-_]steps|current[-_]gaps|"
    r"gap-candidate|open-root|-plan$|^plan$|todo$)",
    re.IGNORECASE,
)
OPEN_BODY_RE = re.compile(
    r"(结论未成立|尚未成立|不能晋升|未晋升|不晋升|"
    r"仅候选|只作为候选|仍为候选|未取证|尚无证据|证据不足|"
    r"仍缺证据|没有证据证明|尚未闭合|本轮未闭合|证据链缺失)"
)

# A heading that lists what is still open.  This is a flag, not a bucket:
# the note itself may well have closed its main result.
OPEN_HEADING_RE = re.compile(
    r"(尚未闭合|未闭合|未完成边界|未闭合边界|缺口|下一步|待办|"
    r"未覆盖项|证据边界|开放问题)"
)

# The section a note keeps its outstanding work in.  Wider than the flag
# above, because the obligations themselves are read out of it.
OPEN_SECTION_RE = re.compile(
    r"(尚未闭合|未闭合|还缺什么|还缺|仍缺|missing|下一步|下一包|"
    r"下一批|下一阶段|下一轮|待办|待做|尚需|未完成|缺口|后续|规划|"
    r"计划|接下来|推进依赖|完成距离|优先级|当前事实|剩余路线|债务)",
    re.IGNORECASE,
)

# What a gate built from this note would assert.
GUARD_CONDITION_RE = re.compile(
    r"(必须|不得|应当|禁止|仅当|只在|阈值|不超过|至少|不超过|"
    r"assert|guard|守卫|门禁|条件)"
)
DEFECT_SEMANTICS_RE = re.compile(
    r"(缺陷|原版没有|原版不|原版是|漏|异常|错位|不一致|相反|"
    r"bug|不刷新|未刷新|为空|为零|不成立)"
)
TICK_CADENCE_RE = re.compile(
    r"(每帧|帧|tick|时序|相位|phase|vsync|扫描线|延迟|节奏)",
    re.IGNORECASE,
)
DATA_CONTRACT_RE = re.compile(
    r"(指针|偏移|表|字段|条目|entry|descriptor|地址|布局|"
    r"结构体|bank|槽位)",
    re.IGNORECASE,
)

# The category convention shared with the results index builder.
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("rom-", "rom"),
    ("rom_", "rom"),
    ("battle-visual", "visual"),
    ("battle-effect", "visual"),
    ("character", "visual"),
    ("tile", "visual"),
    ("sprite", "visual"),
    ("portrait", "presentation"),
    ("menu", "presentation"),
    ("story", "presentation"),
    ("cutscene", "presentation"),
    ("bg-", "visual"),
    ("world", "map"),
    ("map", "map"),
    ("scene", "map"),
    ("battle", "battle"),
    ("audio", "audio"),
    ("runtime", "runtime"),
    ("s49", "s49"),
    ("scenario", "scenario"),
)

# Categories that name a part of the original game.  A note in one of
# them is a conclusion about the original, whatever its body says.
DOMAIN_CATEGORIES = frozenset(
    {
        "audio",
        "battle",
        "map",
        "presentation",
        "residual",
        "rom",
        "runtime",
        "scenario",
        "s49",
        "visual",
    }
)

PROCESS_MARKER_THRESHOLD = 3
OPEN_BODY_THRESHOLD = 2


def categorise(name: str) -> str:
    """The shared category convention for a result name."""
    lowered = name.lower()
    for prefix, category in CATEGORY_RULES:
        if lowered.startswith(prefix):
            return category
    if lowered.startswith("residual"):
        return "residual"
    if lowered.startswith("e2e") or lowered.startswith("overview"):
        return "overview"
    return "other"


def note_identifiers(note_id: str) -> list[str]:
    """The identifier forms that are searched for in a file.

    A long identifier is matched as a whole token.  A short one is only
    matched in its ``artifacts/<id>`` path form, exactly as the gap
    measurement does, because a short word would otherwise match half the
    corpus.
    """
    forms = [note_id]
    if len(note_id) < MIN_BARE_IDENTIFIER:
        forms.append(f"artifacts/{note_id}")
    return forms


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_self_output(rel: str, excluded: tuple[str, ...]) -> bool:
    return any(rel.startswith(prefix) for prefix in excluded)


def _collect_text_files(root: Path, excluded: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every scannable text file as ``(relative path, text)``."""
    found: list[tuple[str, str]] = []
    for scan_root, _status in SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:  # pragma: no cover - defensive
                continue
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = "/".join(rel_parts)
            if _is_self_output(rel, excluded):
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:  # pragma: no cover - defensive
                continue
            found.append((rel, rel + "\n" + text))
    found.sort()
    return found


def _status_for(rel: str) -> str:
    for scan_root, status in SCAN_ROOTS:
        if rel == scan_root or rel.startswith(scan_root + "/"):
            return status
    return "other"


def _find_note_references(
    files: list[tuple[str, str]], notes: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Locate every mention of every note, with the line it sits on.

    The tree is tokenised once per file and intersected with the note
    identifiers, then the line numbers are looked up only for the files
    that actually mention a note.  Doing it the other way round -- one
    pass over the tree per note -- is quadratic and takes minutes.
    """
    hits: dict[str, list[dict[str, Any]]] = {note["id"]: [] for note in notes}
    long_ids = {note["id"].lower() for note in notes if len(note["id"]) >= MIN_BARE_IDENTIFIER}
    id_by_lower = {note["id"].lower(): note["id"] for note in notes}
    short_forms = {
        note["id"]: f"artifacts/{note['id']}"
        for note in notes
        if len(note["id"]) < MIN_BARE_IDENTIFIER
    }

    # First pass: which file mentions which note.
    file_map = dict(files)
    mentioned: list[tuple[str, str, list[str]]] = []
    for rel, text in files:
        status = _status_for(rel)
        tokens = {token.lower() for token in _TOKEN_RE.findall(text)}
        found = sorted(tokens & long_ids)
        for note_id, path_form in short_forms.items():
            if path_form in text:
                found.append(note_id)
        if found:
            mentioned.append((rel, status, found))

    # Second pass: the line of every mention, for the files that have one.
    # The match text carries the path as its first line (so that a family
    # that only exists as a directory is still found), which would shift
    # every real line by one, so the line numbers are taken from the file
    # content alone.
    for rel, status, found in mentioned:
        lines = file_map[rel].splitlines()[1:]
        kind = "code" if Path(rel).suffix.lower() != ".md" else "markdown"
        for note_id in found:
            if len(note_id) >= MIN_BARE_IDENTIFIER:
                needle = note_id.lower()
                key = id_by_lower[note_id]
                for index, line in enumerate(lines):
                    if needle in {t.lower() for t in _TOKEN_RE.findall(line)}:
                        hits[key].append(
                            {
                                "path": rel,
                                "line": index + 1,
                                "status": status,
                                "kind": kind,
                                "text": line.strip()[:160],
                            }
                        )
                if not hits[key] and needle in rel.lower():
                    hits[key].append(
                        {
                            "path": rel,
                            "line": 1,
                            "status": status,
                            "kind": kind,
                            "text": rel[:160],
                        }
                    )
            else:
                path_form = short_forms[note_id]
                for index, line in enumerate(lines):
                    if path_form in line:
                        hits[note_id].append(
                            {
                                "path": rel,
                                "line": index + 1,
                                "status": status,
                                "kind": kind,
                                "text": line.strip()[:160],
                            }
                        )
                if not hits[note_id] and path_form in rel:
                    hits[note_id].append(
                        {
                            "path": rel,
                            "line": 1,
                            "status": status,
                            "kind": kind,
                            "text": rel[:160],
                        }
                    )
    return hits


def _status_from_hits(hits: list[dict[str, Any]]) -> str:
    statuses = {hit["status"] for hit in hits}
    for candidate in STATUS_ORDER[:-1]:
        if candidate in statuses:
            return candidate
    return "none"


def _rom_evidence(
    text: str, rom_closure: set[str], identifier: str, title: str, category: str
) -> dict[str, Any]:
    """How strongly a note points at the original game.

    The note's own name and title count as evidence: a note called after a
    reverse family is a conclusion about that family even when its body
    never repeats the family name.  A note in a domain category (audio,
    visual, battle, map, ...) is a conclusion about the original for the
    same reason.
    """
    haystack = f"{text}\n{identifier}\n{title}"
    addr_hits = len(ADDR_RE.findall(haystack))
    families = len(set(ROM_FAMILY_RE.findall(haystack)))
    artifacts = len(set(ARTIFACT_REF_RE.findall(text)))
    refs = NOTE_REF_RE.findall(text)
    closed_refs = sum(1 for ref in refs if f"notes/{ref}.md" in rom_closure)
    domain = category in DOMAIN_CATEGORIES
    return {
        "rom_addresses": addr_hits,
        "rom_families": families,
        "artifact_refs": artifacts,
        "rom_note_refs": closed_refs,
        "domain_category": domain,
        "is_rom_conclusion": bool(
            addr_hits or families or artifacts or closed_refs or domain
        ),
    }


def _rom_closure(notes: list[dict[str, Any]]) -> set[str]:
    """Notes that carry evidence about the original game.

    A note is a conclusion about the original when it cites an address, a
    reverse family, a produced artifact, or another conclusion note.  The
    last link is closed by a fixed point iteration so that a note which
    only points at another conclusion note still counts.
    """
    closure: set[str] = set()
    for note in notes:
        if note["rom_evidence"]["is_rom_conclusion"]:
            closure.add(note["path"])
    changed = True
    while changed:
        changed = False
        for note in notes:
            if note["path"] in closure:
                continue
            for referenced in note["note_ref_paths"]:
                if referenced in closure:
                    closure.add(note["path"])
                    changed = True
                    break
    return closure


def _material_kinds(text: str) -> list[str]:
    kinds = []
    if GUARD_CONDITION_RE.search(text):
        kinds.append("guard_condition")
    if DEFECT_SEMANTICS_RE.search(text):
        kinds.append("defect_semantics")
    if TICK_CADENCE_RE.search(text):
        kinds.append("tick_cadence")
    if DATA_CONTRACT_RE.search(text):
        kinds.append("data_contract")
    return kinds


def _open_headings(text: str) -> list[str]:
    headings = re.findall(r"^#{2,4}\s+(.+)$", text, re.MULTILINE)
    return [h.strip() for h in headings if OPEN_HEADING_RE.search(h)]


def _open_obligations(text: str, limit: int = 3) -> list[str]:
    """What the note itself lists as still open.

    A note that declares an open result usually says so in a section
    whose heading carries the gap ("尚未闭合", "缺口", "下一步").  The
    first entries of that section are the obligations the reverse side
    still has to discharge, so they are what the to-do should quote.
    """
    lines = text.splitlines()
    obligations: list[str] = []
    collecting = False
    for line in lines:
        heading = re.match(r"^(#{2,4})\s+(.+)$", line)
        if heading:
            collecting = bool(OPEN_SECTION_RE.search(heading.group(2)))
            continue
        if not collecting:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*", "|")):
            obligations.append(stripped.lstrip("-*| ").strip())
        elif obligations:
            obligations.append(stripped)
        else:
            obligations.append(stripped)
        if len(obligations) >= limit:
            break
    return [item for item in obligations if item][:limit]


def _classify(
    note: dict[str, Any],
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assign one bucket to one note and say why."""
    text = note["text"]
    build_hits = [hit for hit in hits if hit["status"] == "build"]
    other_hits = [hit for hit in hits if hit["status"] != "build"]

    if build_hits:
        return {
            "bucket": "implemented_in_code",
            "reason": (
                "本树构建链引用了本条结论（"
                + "、".join(
                    sorted({f"{hit['path']}:{hit['line']}" for hit in build_hits})[:3]
                )
                + "）。"
            ),
            "evidence": "; ".join(
                sorted({hit["path"] for hit in build_hits})[:6]
            ),
        }

    if note["vendored"]:
        return {
            "bucket": "not_applicable",
            "reason": (
                "证据包内嵌的逆向树自身文件快照（"
                f"{Path(note['path']).name}），不是新的 ROM 结论。"
            ),
            "evidence": note["path"],
        }

    if not note["rom_evidence"]["is_rom_conclusion"] and (
        note["process_in_title"] or note["process_hits"] >= PROCESS_MARKER_THRESHOLD
    ):
        return {
            "bucket": "not_applicable",
            "reason": (
                "主题是逆向工程自身的工程过程（子代理/基准/工作树/工具链/提交门禁），"
                "不是关于原版 ROM 的结论，与本复刻无关。"
            ),
            "evidence": "、".join(sorted(note["process_terms"])[:6]) or note["title"],
        }

    if note["open_title"] or note["open_body_hits"] >= OPEN_BODY_THRESHOLD:
        missing = (
            note["open_obligations"]
            or note["open_claims"]
            or ["本条自身声明结果尚未成立"]
        )
        return {
            "bucket": "missing_evidence",
            "reason": (
                "本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），"
                "证据尚未闭合，需回到逆向侧补齐。"
            ),
            "missing": "；".join(missing[:3]),
            "evidence": "、".join(note["open_claims"][:4]) or note["path"],
        }

    if note["rom_evidence"]["is_rom_conclusion"]:
        return {
            "bucket": "needs_guard",
            "reason": (
                "已给出原版行为的可核验结论（"
                + "、".join(
                    filter(
                        None,
                        [
                            f"{note['rom_evidence']['rom_addresses']} 处 ROM 地址"
                            if note["rom_evidence"]["rom_addresses"]
                            else "",
                            f"{note['rom_evidence']['rom_families']} 个逆向成果族"
                            if note["rom_evidence"]["rom_families"]
                            else "",
                            f"{note['rom_evidence']['artifact_refs']} 个产物目录"
                            if note["rom_evidence"]["artifact_refs"]
                            else "",
                        ],
                    )
                )
                + "），本树尚未把它变成门禁，是 M1/M2 的原料。"
            ),
            "evidence": note["path"],
        }

    return {
        "bucket": "needs_human_review",
        "reason": (
            "既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），"
            "也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。"
        ),
        "evidence": note["path"],
    }


def build_index(root: Path, reverse_root: Path) -> dict[str, Any]:
    """Read the reverse tree, classify every note, and return the payload."""
    notes_dir = reverse_root / "notes"
    if not notes_dir.is_dir():
        raise FileNotFoundError(f"reverse tree has no notes directory: {notes_dir}")
    note_paths = sorted(notes_dir.rglob("*.md"))
    if not note_paths:
        raise FileNotFoundError(f"reverse tree has no note files: {notes_dir}")

    notes: list[dict[str, Any]] = []
    for path in note_paths:
        rel = path.relative_to(reverse_root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        headings = re.findall(r"^#{2,4}\s+(.+)$", text, re.MULTILINE)
        process_terms = sorted(set(PROCESS_RE.findall(text)))
        title_text = headings[0].strip() if headings else ""
        process_in_title = bool(PROCESS_TITLE_RE.search(title_text))
        open_claims = sorted(set(OPEN_BODY_RE.findall(text)))
        notes.append(
            {
                "id": path.stem,
                "path": rel,
                "title": title_text,
                "category": categorise(path.stem),
                "text": text,
                "vendored": "/implementation/" in rel,
                "process_hits": len(process_terms),
                "process_in_title": process_in_title,
                "process_terms": process_terms,
                "open_title": bool(OPEN_TITLE_RE.search(path.stem)),
                "open_body_hits": len(open_claims),
                "open_claims": open_claims,
                "open_headings": _open_headings(text),
                "open_obligations": _open_obligations(text),
                "note_refs": NOTE_REF_RE.findall(text),
                "note_ref_paths": [
                    f"notes/{ref}.md" for ref in NOTE_REF_RE.findall(text)
                ],
                "rom_evidence": {},
            }
        )

    # The closure needs the raw reference lists before it can be computed.
    for note in notes:
        note["rom_evidence"] = _rom_evidence(
            note["text"], set(), note["id"], note["title"], note["category"]
        )
    closure = _rom_closure(notes)
    for note in notes:
        note["rom_evidence"] = _rom_evidence(
            note["text"], closure, note["id"], note["title"], note["category"]
        )

    excluded = _load_excluded_prefixes()
    files = _collect_text_files(root, excluded)
    hits = _find_note_references(files, notes)

    rows: list[dict[str, Any]] = []
    for note in notes:
        note_hits = hits.get(note["id"], [])
        verdict = _classify(note, note_hits)
        pre_status = _status_from_hits(note_hits)
        build_hits = [hit for hit in note_hits if hit["status"] == "build"]
        code_hits = [hit for hit in build_hits if hit["kind"] == "code"]
        row = {
            "id": note["id"],
            "path": note["path"],
            "title": note["title"],
            "category": note["category"],
            "bucket": verdict["bucket"],
            "reason": verdict["reason"],
            "evidence": verdict.get("evidence", ""),
            "missing": verdict.get("missing", ""),
            "consumers": sorted(
                (
                    {
                        "path": hit["path"],
                        "line": hit["line"],
                        "kind": hit["kind"],
                    }
                    for hit in build_hits
                ),
                key=lambda hit: (hit["path"], hit["line"]),
            ),
            "reference_strength": (
                "code"
                if code_hits
                else ("markdown-mention" if build_hits else "")
            ),
            "pre_index_status": pre_status,
            "pre_index_references": sorted(
                {f"{hit['status']}:{hit['path']}" for hit in note_hits}
            )[:8],
            "material_kinds": _material_kinds(note["text"]),
            "open_headings": note["open_headings"],
            "rom_evidence": note["rom_evidence"],
        }
        rows.append(row)

    rows.sort(key=lambda row: row["path"])

    by_bucket: dict[str, int] = {bucket: 0 for bucket in BUCKETS}
    by_bucket_pre: dict[str, int] = {status: 0 for status in STATUS_ORDER}
    by_category: dict[str, dict[str, int]] = {}
    for row in rows:
        by_bucket[row["bucket"]] = by_bucket.get(row["bucket"], 0) + 1
        by_bucket_pre[row["pre_index_status"]] = (
            by_bucket_pre.get(row["pre_index_status"], 0) + 1
        )
        by_category.setdefault(row["category"], {})
        by_category[row["category"]][row["bucket"]] = (
            by_category[row["category"]].get(row["bucket"], 0) + 1
        )

    # M5's stated goal is "turn every conclusion into a gate", so a note that
    # is already referenced from a test is *not* the same as a note nothing
    # has been done with.  The split is reported so the P2 denominator cannot
    # be misread.  The caveat is stated in the rendered table: a ``tests/``
    # hit can be a documentation test rather than a behaviour gate, so this
    # is an upper bound, not a count of real gates.
    needs_guard_referenced_from_tests = sum(
        1
        for row in rows
        if row["bucket"] == "needs_guard"
        and any(
            str(reference).startswith("test:")
            for reference in row.get("pre_index_references", [])
        )
    )

    return {
        "schema": NOTES_INDEX_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": {
            "reverse_root": str(reverse_root),
            "reverse_notes_dir": str(notes_dir),
            "reverse_commit": _git_commit(reverse_root),
            "note_files": len(note_paths),
            "unique_note_ids": len({note["id"] for note in notes}),
        },
        "measurement": {
            "unit": "reverse note file",
            "scanned_files": len(files),
            "scan_roots": [name for name, _ in SCAN_ROOTS],
            "excluded_prefixes": list(excluded),
            "min_bare_identifier": MIN_BARE_IDENTIFIER,
        },
        "summary": {
            "total": len(rows),
            "by_bucket": by_bucket,
            "by_pre_index_status": by_bucket_pre,
            "needs_guard_already_referenced_from_tests": (
                needs_guard_referenced_from_tests
            ),
            "needs_guard_without_any_test_reference": (
                by_bucket.get("needs_guard", 0) - needs_guard_referenced_from_tests
            ),
            "by_category": {
                key: dict(sorted(value.items()))
                for key, value in sorted(by_category.items())
            },
        },
        "notes": rows,
    }


def _git_commit(root: Path) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def check_payload(payload: dict[str, Any]) -> list[str]:
    """Report every way in which the payload fails its own rules."""
    problems: list[str] = []
    rows = payload.get("notes") or []
    summary = payload.get("summary") or {}
    total = summary.get("total")
    if total != len(rows):
        problems.append(f"summary total {total} != {len(rows)} rows")
    by_bucket = summary.get("by_bucket") or {}
    if sum(by_bucket.values()) != len(rows):
        problems.append(
            f"bucket counts add up to {sum(by_bucket.values())}, not {len(rows)}"
        )
    for bucket in by_bucket:
        if bucket not in BUCKETS:
            problems.append(f"unknown bucket {bucket!r}")
    seen: set[str] = set()
    for row in rows:
        path = row.get("path", "")
        if path in seen:
            problems.append(f"duplicate note path {path}")
        seen.add(path)
        if row.get("bucket") not in BUCKETS:
            problems.append(f"{path}: bucket {row.get('bucket')!r} is not a bucket")
        if not str(row.get("reason", "")).strip():
            problems.append(f"{path}: no reason given")
        if row.get("bucket") == "not_applicable" and not str(row.get("evidence", "")).strip():
            problems.append(f"{path}: not applicable without a reason")
        if row.get("bucket") == "missing_evidence" and not str(row.get("missing", "")).strip():
            problems.append(f"{path}: missing evidence without a statement of what is missing")
        if row.get("bucket") == "implemented_in_code" and not row.get("consumers"):
            problems.append(f"{path}: claims to be implemented without a consumer")
    return problems


def _verify_consumers(root: Path, payload: dict[str, Any]) -> list[str]:
    """Every claimed consumer must be a file in this tree at that line."""
    problems: list[str] = []
    for row in payload.get("notes") or []:
        if row.get("bucket") != "implemented_in_code":
            continue
        for consumer in row.get("consumers") or []:
            target = root / consumer["path"]
            if not target.is_file():
                problems.append(f"{row['path']}: consumer {consumer['path']} is not a file")
                continue
            lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
            if not 1 <= consumer["line"] <= len(lines):
                problems.append(
                    f"{row['path']}: consumer {consumer['path']}:{consumer['line']} is out of range"
                )
    return problems


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    source = payload["source"]
    lines: list[str] = []
    lines.append("# 逆向 notes 分类索引（自动生成）")
    lines.append("")
    lines.append(
        "本文件由 `tools/build_reverse_notes_index.py` 生成，不要手工编辑。"
    )
    lines.append("")
    lines.append("每条逆向 note 落在且只落在五个桶之一：")
    lines.append("")
    lines.append("| 桶 | 含义 | 条数 | 占比 |")
    lines.append("| --- | --- | ---: | ---: |")
    meanings = {
        "implemented_in_code": "本树构建链已引用，附消费文件与行号",
        "needs_guard": "已给出原版结论，尚未转成门禁——M1/M2 的原料",
        "not_applicable": "与本复刻无关，附理由",
        "missing_evidence": "证据未闭合，回逆向侧补齐",
        "needs_human_review": "自动判读不了，附原因",
    }
    for bucket in BUCKETS:
        count = summary["by_bucket"].get(bucket, 0)
        share = (100.0 * count / summary["total"]) if summary["total"] else 0.0
        lines.append(f"| `{bucket}` | {meanings[bucket]} | {count} | {share:.1f}% |")
    lines.append("")
    lines.append(f"- 合计：**{summary['total']}** 个 note 文件")
    lines.append(
        f"- 其中不重复的 note id：{source['unique_note_ids']}"
        "（证据包内嵌的快照与顶层同名，计数以文件为单位）"
    )
    lines.append(f"- 逆向 commit：`{source['reverse_commit'] or '未知'}`")
    lines.append(f"- 扫描文件数：{payload['measurement']['scanned_files']}")
    referenced = summary.get("needs_guard_already_referenced_from_tests", 0)
    without = summary.get("needs_guard_without_any_test_reference", 0)
    lines.append("")
    lines.append(
        f"- `needs_guard` 里有 **{referenced}** 条已经在 `tests/` 被引用过，"
        f"**{without}** 条连测试都没有引用 ⇒ P2 的真实分母是后者。"
        "⚠️ **上界不是真值**：`tests/` 里的引用可能是**文档类测试**而不是行为门禁，"
        "所以「已被引用」只能当作「可能已有门禁」的上界，逐条判定仍需人看。"
    )
    lines.append("")
    lines.append("## 索引前的引用状态")
    lines.append("")
    lines.append(
        "本索引把每条 note 都写进了本树，因此差异测量里这些 note 的状态会从 "
        "`none` 变成 `doc`/`local_artifact`。**那不是消费。** 下面是写入本索引"
        "之前它们在本树的真实状态（`build` 才是「被消费」）。"
    )
    lines.append("")
    lines.append("| 索引前状态 | 条数 |")
    lines.append("| --- | ---: |")
    for status in STATUS_ORDER:
        lines.append(f"| `{status}` | {summary['by_pre_index_status'].get(status, 0)} |")
    lines.append("")
    lines.append("## 按类别 × 桶")
    lines.append("")
    lines.append("| 类别 | " + " | ".join(f"`{b}`" for b in BUCKETS) + " | 合计 |")
    lines.append("| --- |" + " ---: |" * (len(BUCKETS) + 1))
    for category, counts in summary["by_category"].items():
        cells = " | ".join(str(counts.get(bucket, 0)) for bucket in BUCKETS)
        lines.append(f"| {category} | {cells} | {sum(counts.values())} |")
    lines.append("")
    for bucket in BUCKETS:
        rows = [row for row in payload["notes"] if row["bucket"] == bucket]
        lines.append(f"## `{bucket}`（{len(rows)}）")
        lines.append("")
        if not rows:
            lines.append("（无）")
            lines.append("")
            continue
        if bucket == "implemented_in_code":
            lines.append("| note | 类别 | 消费指针 | 引用强度 |")
            lines.append("| --- | --- | --- | --- |")
            for row in rows:
                pointers = "、".join(
                    f"`{c['path']}:{c['line']}`" for c in row["consumers"][:3]
                )
                lines.append(
                    f"| `{row['path']}` | {row['category']} | {pointers} | "
                    f"{row['reference_strength']} |"
                )
        elif bucket == "not_applicable":
            lines.append("| note | 类别 | 理由 | 判据 |")
            lines.append("| --- | --- | --- | --- |")
            for row in rows:
                lines.append(
                    f"| `{row['path']}` | {row['category']} | {row['reason']} | {row['evidence']} |"
                )
        elif bucket == "missing_evidence":
            lines.append("| note | 类别 | 缺什么 | 理由 |")
            lines.append("| --- | --- | --- | --- |")
            for row in rows:
                lines.append(
                    f"| `{row['path']}` | {row['category']} | {row['missing']} | {row['reason']} |"
                )
        else:
            lines.append("| note | 类别 | 可转门禁的材料 | 理由 |")
            lines.append("| --- | --- | --- | --- |")
            for row in rows:
                kinds = "、".join(row["material_kinds"]) or "—"
                lines.append(
                    f"| `{row['path']}` | {row['category']} | {kinds} | {row['reason']} |"
                )
        lines.append("")
    lines.append("## 全部条目")
    lines.append("")
    lines.append("| note | 桶 | 索引前状态 | 类别 |")
    lines.append("| --- | --- | --- | --- |")
    for row in payload["notes"]:
        lines.append(
            f"| `{row['path']}` | `{row['bucket']}` | `{row['pre_index_status']}` | {row['category']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    root: Path,
    reverse_root: Path,
    out_dir: Path,
    doc_path: Path,
) -> tuple[dict[str, Any], int]:
    payload = build_index(root, reverse_root)
    problems = check_payload(payload) + _verify_consumers(root, payload)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return payload, EXIT_INCONSISTENT

    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "notes-index.json"
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    doc_path.write_text(render_markdown(payload), encoding="utf-8")

    manifest = {
        "schema": "konoha.reverse-notes-index-manifest.v1",
        "generated_at": payload["generated_at"],
        "source": payload["source"],
        "measurement": payload["measurement"],
        "summary": payload["summary"],
        "outputs": {
            "index": {
                "path": str(index_path.relative_to(root)) if index_path.is_relative_to(root) else str(index_path),
                "sha256": _sha256(index_path),
            },
            "doc": {
                "path": str(doc_path.relative_to(root)) if doc_path.is_relative_to(root) else str(doc_path),
                "sha256": _sha256(doc_path),
            },
        },
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return payload, EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="remake work tree root")
    parser.add_argument(
        "--reverse-root",
        default="/Users/altair/github/gba-naruto-reverse",
        help="reverse work tree, read only",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/reverse-notes-index-v1",
        help="directory for the machine readable index",
    )
    parser.add_argument(
        "--doc",
        default="docs/reverse-results-index/notes-index.md",
        help="path of the human readable index",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    reverse_root = Path(args.reverse_root)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (root / out_dir).resolve()
    doc_path = Path(args.doc)
    if not doc_path.is_absolute():
        doc_path = (root / doc_path).resolve()

    if not reverse_root.is_dir():
        print(
            f"error: reverse work tree is not readable: {reverse_root}",
            file=sys.stderr,
        )
        return EXIT_REVERSE_TREE_MISSING
    if not (reverse_root / "notes").is_dir():
        print(
            f"error: reverse work tree has no notes directory: {reverse_root / 'notes'}",
            file=sys.stderr,
        )
        return EXIT_REVERSE_TREE_MISSING

    try:
        payload, code = write_outputs(root, reverse_root, out_dir, doc_path)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_NO_NOTES
    if code != EXIT_OK:
        return code

    summary = payload["summary"]
    print(f"wrote {out_dir / 'notes-index.json'}")
    print(f"wrote {out_dir / 'manifest.json'}")
    print(f"wrote {doc_path}")
    print(f"notes={summary['total']}")
    for bucket in BUCKETS:
        print(f"  {bucket}: {summary['by_bucket'].get(bucket, 0)}")
    print("  pre-index status:")
    for status in STATUS_ORDER:
        print(f"    {status}: {summary['by_pre_index_status'].get(status, 0)}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
