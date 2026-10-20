#!/usr/bin/env python3
"""Audit the provenance declarations of the generated Butano artifacts.

``tools/measure_butano_reverse_gap.py`` counts a reverse family as *consumed*
when the family name shows up somewhere in the remake tree.  That is a lower
bound: a name can show up in a comment, a doc or a script without a single
byte of lineage behind it.  This tool turns the lower bound into a fact.

Every generated product carries one machine readable declaration, and this
tool reads those declarations back, resolves every family against the reverse
work tree and re-hashes the manifest.  The rules:

1.  **The declaration is the only link.**  A product is bound to a family
    because the product says so, never because a tool knows the family list.
    The auditor therefore carries no family name of its own; the mapping is
    recovered from the products.
2.  **One carrier, library wide.**  The whole library uses the C++ header
    comment carrier.  Every generated header states the carrier it uses, so a
    third party can see the choice from inside the artifact:

        // provenance-carrier: c-header-comment
        // reverse-source: <artifact-family> @ <manifest-sha256>
        // reverse-source-rom: 0x<offset>+<length> sha256 <region-sha256>
        // reverse-source-rom: none
        // reverse-source: not-applicable - <reason>

    A product that consumes ROM bytes records them in the ``reverse-source-rom``
    line, so the lineage can be re-checked against the ROM itself instead of
    being taken on trust.  A product that consumes no ROM byte at all has to
    say so explicitly with ``reverse-source-rom: none`` -- the absence of a
    region is a claim too, and the auditor does not accept a silent gap.
3.  **Only results may be bound.**  A manifest that is missing, that moved,
    that is ``candidate`` / ``disproved`` or that another family supersedes
    is a hard failure naming the family -- never a silent skip.
4.  **The consumed bytes must belong to the declared family.**  The region
    digest has to be recorded by that very family, and the bytes at the
    declared ROM offset have to hash to the declared digest.  A product that
    consumes bytes no family covers has to say so with a ``not-applicable``
    reason, and the auditor checks that reason against the reverse tree.
5.  **The product set comes from the generators, not from a file name
    pattern.**  Every generator states in its own source which products it
    writes:

        GENERATED_PRODUCTS = (
            "butano-sequel/game/include/konoha/example_content.h",
        )

    The auditor reads that constant back through the abstract syntax tree, so
    the registry is the generators' own statement and never a guess.  A
    generated file that the registry does not list is a hard failure, and a
    registered product that carries no declaration is a hard failure too.

The audit fails closed: any problem makes the command exit non-zero and the
report names what broke.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Root of this repository.  The tool is always run against its own tree.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Default location of the reverse work tree.  Matches the default used by
#: ``tools/measure_butano_reverse_gap.py`` and ``tools/butano/import_*.py``
#: so every tool reads the same tree.
DEFAULT_REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

#: The one carrier used by every generated product in the library.  The
#: value is written into the products themselves, so a third party can see
#: which convention this tree uses without reading this file.
CARRIER = "c-header-comment"

#: The module level constant a generator uses to register the products it
#: writes.  The value has to be a literal list of repository relative paths
#: so that the auditor can read it without executing the generator.
REGISTRY_CONSTANT = "GENERATED_PRODUCTS"

#: Where the generators live.  Every Python file below this directory that
#: declares ``GENERATED_PRODUCTS`` joins the registry.
GENERATOR_ROOT = Path("tools")

#: The trees the auditor sweeps for files that claim to be generated but
#: that no generator registered.  The sweep is a safety net for the
#: registry, never the registry itself.
PRODUCT_SCAN_ROOTS = ("butano-sequel",)

#: Directories that never hold a product.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "build",
        "third_party",
        ".pi",
    }
)

#: The file types the sweep looks at.  A product declares its provenance in
#: a text comment, so a binary file can never carry the marker.
TEXT_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cfg",
        ".cmake",
        ".cpp",
        ".h",
        ".hpp",
        ".json",
        ".lua",
        ".mako",
        ".py",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)

#: The ROM the generated products were derived from, relative to the root.
ROM_PATH = Path("rom") / "base.gba"

#: Only results may be bound to a generated product.
ACCEPTED_STATUS = "accepted"

#: Statuses that must never be bound, listed so the failure message can name
#: them instead of only reporting "not accepted".
REJECTED_STATUSES = ("candidate", "disproved", "superseded")

# Exit codes.  Every problem is reported with the code of its own kind.
EXIT_OK = 0
EXIT_MISSING_MANIFEST = 1
EXIT_MANIFEST_MISMATCH = 2
EXIT_STATUS_REJECTED = 3
EXIT_UNDECLARED = 4
EXIT_SUPERSEDED = 5
EXIT_ROM_REGION = 6
EXIT_INPUT = 7
EXIT_REGISTRY = 8

_CARRIER_RE = re.compile(
    r"^//\s*provenance-carrier:\s*(?P<carrier>[A-Za-z0-9-]+)\s*$", re.MULTILINE
)
_SOURCE_RE = re.compile(
    r"^//\s*reverse-source:\s*(?P<value>.+?)\s*$", re.MULTILINE
)
_ROM_RE = re.compile(
    r"^//\s*reverse-source-rom:\s*"
    r"0x(?P<offset>[0-9a-fA-F]+)\+(?P<length>\d+)\s+"
    r"sha256\s+(?P<sha256>[0-9a-f]{64})\s*$",
    re.MULTILINE,
)
_ROM_NONE_RE = re.compile(
    r"^//\s*reverse-source-rom:\s*none\s*$", re.MULTILINE
)
_GENERATED_BY_RE = re.compile(
    r"^//\s*Generated by\s+(?P<generator>tools/[A-Za-z0-9_/]+\.py)",
    re.MULTILINE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceDeclaration:
    """One ``reverse-source`` line: a family and the hash of its manifest."""

    family: str
    manifest_sha256: str


@dataclass(frozen=True)
class RomDeclaration:
    """One ``reverse-source-rom`` line: ROM bytes the product consumed."""

    offset: int
    length: int
    sha256: str


@dataclass(frozen=True)
class ProductDeclaration:
    """The declaration block of a single generated product."""

    carrier: str
    sources: tuple[SourceDeclaration, ...] = ()
    roms: tuple[RomDeclaration, ...] = ()
    not_applicable: tuple[str, ...] = ()
    consumes_no_rom: bool = False

    @property
    def is_declared(self) -> bool:
        """True when the product states where its bytes came from."""
        return bool(self.sources) or bool(self.not_applicable)


@dataclass(frozen=True)
class ProductAudit:
    """What the auditor found in one generated product."""

    path: str
    generator: str
    status: str
    families: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class FamilyAudit:
    """The result of resolving one declared family in the reverse work tree."""

    family: str
    manifest_path: str
    declared_sha256: str
    actual_sha256: str | None = None
    manifest_status: str = "unknown"
    notes: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutOfScopeProduct:
    """A generated file the generator registry does not cover, kept visible."""

    path: str
    reason: str


@dataclass(frozen=True)
class GeneratorRegistry:
    """One generator and the products it registered."""

    generator: str
    products: tuple[str, ...]


@dataclass
class AuditReport:
    """The whole audit: products, families and every problem found."""

    root: str
    reverse_root: str
    carrier: str = CARRIER
    registry: list[GeneratorRegistry] = field(default_factory=list)
    products: list[ProductAudit] = field(default_factory=list)
    families: list[FamilyAudit] = field(default_factory=list)
    out_of_scope: list[OutOfScopeProduct] = field(default_factory=list)
    unattributed: list[OutOfScopeProduct] = field(default_factory=list)
    problems: list[tuple[int, str]] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Zero only when nothing is wrong."""
        return self.problems[0][0] if self.problems else EXIT_OK

    @property
    def declared_product_count(self) -> int:
        """How many generated products carry a declaration."""
        return len([p for p in self.products if p.status != "undeclared"])

    @property
    def mapping(self) -> list[tuple[str, str]]:
        """The ``(generated product, artifact family)`` pairs."""
        pairs: list[tuple[str, str]] = []
        for product in self.products:
            for family in product.families:
                pairs.append((product.path, family))
        return pairs

    def summary(self) -> str:
        """A human readable report of the audit."""
        lines = [
            "Butano reverse provenance audit",
            f"  root:         {self.root}",
            f"  reverse tree: {self.reverse_root}",
            f"  carrier:      {self.carrier}",
            "",
            f"generators in the registry: {len(self.registry)}",
            f"generated products: {len(self.products)}",
            f"  declared:     {self.declared_product_count}",
            f"  with family:  {len(self.mapping)}",
            "",
        ]
        if self.registry:
            lines.append("generator registry")
            for entry in self.registry:
                lines.append(
                    f"  {entry.generator}: {len(entry.products)} product(s)"
                )
            lines.append("")
        if self.mapping:
            lines.append("generated product -> artifact family")
            for product, family in self.mapping:
                lines.append(f"  {product} -> {family}")
            lines.append("")
        for family in self.families:
            lines.append(
                f"  {family.family}: manifest {family.manifest_status}"
                f" ({family.manifest_path})"
            )
            for note in family.notes:
                lines.append(f"    note: {note}")
        if self.families:
            lines.append("")
        if self.out_of_scope:
            lines.append(
                "generated files outside the generator registry: "
                f"{len(self.out_of_scope)}"
            )
            for item in self.out_of_scope:
                lines.append(f"  {item.path}: {item.reason}")
            lines.append("")
        if self.unattributed:
            lines.append(
                "generated files whose generator is not in the registry: "
                f"{len(self.unattributed)}"
            )
            for item in self.unattributed:
                lines.append(f"  {item.path}: {item.reason}")
            lines.append("")
        if self.problems:
            lines.append(f"problems: {len(self.problems)}")
            for _, message in self.problems:
                lines.append(f"  - {message}")
        else:
            lines.append("problems: none")
        return "\n".join(lines)

    def as_json(self) -> dict[str, Any]:
        """A machine readable form of the same report."""
        return {
            "schema": "konoha.butano-reverse-provenance.v2",
            "root": self.root,
            "reverse_root": self.reverse_root,
            "carrier": self.carrier,
            "exit_code": self.exit_code,
            "declared_product_count": self.declared_product_count,
            "registry": [
                {
                    "generator": entry.generator,
                    "products": list(entry.products),
                }
                for entry in self.registry
            ],
            "products": [
                {
                    "path": product.path,
                    "generator": product.generator,
                    "status": product.status,
                    "families": list(product.families),
                    "reasons": list(product.reasons),
                    "problems": list(product.problems),
                }
                for product in self.products
            ],
            "families": [
                {
                    "family": family.family,
                    "manifest": family.manifest_path,
                    "declared_sha256": family.declared_sha256,
                    "actual_sha256": family.actual_sha256,
                    "manifest_status": family.manifest_status,
                    "notes": list(family.notes),
                    "problems": list(family.problems),
                }
                for family in self.families
            ],
            "mapping": [
                {"product": product, "family": family}
                for product, family in self.mapping
            ],
            "out_of_scope": [
                {"path": item.path, "reason": item.reason}
                for item in self.out_of_scope
            ],
            "unattributed": [
                {"path": item.path, "reason": item.reason}
                for item in self.unattributed
            ],
            "problems": [
                {"code": code, "message": message}
                for code, message in self.problems
            ],
        }


def provenance_block(
    sources: Sequence[tuple[str, str]] = (),
    *,
    roms: Sequence[tuple[int, int, str]] = (),
    not_applicable: Sequence[str] = (),
    no_rom_region: bool = False,
) -> str:
    """Render the uniform provenance declaration of a generated product.

    ``sources`` are ``(artifact family, manifest sha256)`` pairs, ``roms`` are
    ``(offset, length, sha256)`` triples describing the ROM bytes the product
    consumed and ``not_applicable`` holds the reasons for a product that no
    reverse family covers.  ``no_rom_region`` states explicitly that the
    product consumes no ROM byte at all; it may only be used together with a
    not-applicable reason.
    """
    lines = [f"// provenance-carrier: {CARRIER}"]
    for family, manifest_sha256 in sources:
        lines.append(f"// reverse-source: {family} @ {manifest_sha256}")
    for offset, length, sha256 in roms:
        lines.append(
            f"// reverse-source-rom: 0x{offset:06X}+{length} sha256 {sha256}"
        )
    if no_rom_region:
        lines.append("// reverse-source-rom: none")
    for reason in not_applicable:
        lines.append(f"// reverse-source: not-applicable - {reason}")
    return "\n".join(lines)


def parse_declaration(text: str) -> ProductDeclaration | None:
    """Read a declaration block back, or ``None`` when there is none."""
    carrier_match = _CARRIER_RE.search(text)
    carrier = carrier_match.group("carrier") if carrier_match else ""
    sources: list[SourceDeclaration] = []
    not_applicable: list[str] = []
    for match in _SOURCE_RE.finditer(text):
        value = match.group("value")
        if value.startswith("not-applicable"):
            reason = value[len("not-applicable"):].lstrip("-: ").strip()
            if reason:
                not_applicable.append(reason)
            continue
        family, separator, manifest_sha256 = value.partition("@")
        family = family.strip()
        manifest_sha256 = manifest_sha256.strip()
        if not separator or not family or not _SHA256_RE.match(manifest_sha256):
            continue
        sources.append(SourceDeclaration(family, manifest_sha256))
    roms = tuple(
        RomDeclaration(
            int(match.group("offset"), 16),
            int(match.group("length")),
            match.group("sha256"),
        )
        for match in _ROM_RE.finditer(text)
    )
    consumes_no_rom = _ROM_NONE_RE.search(text) is not None
    if (
        not carrier
        and not sources
        and not not_applicable
        and not roms
        and not consumes_no_rom
    ):
        return None
    return ProductDeclaration(
        carrier=carrier,
        sources=tuple(sources),
        roms=roms,
        not_applicable=tuple(not_applicable),
        consumes_no_rom=consumes_no_rom,
    )


def sha256_file(path: Path) -> str:
    """The SHA-256 of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _registry_value(tree: ast.Module) -> ast.expr | None:
    """The module level ``GENERATED_PRODUCTS`` assignment, if there is one."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id != REGISTRY_CONSTANT:
            continue
        return node.value
    return None


def read_registry(root: Path | str) -> tuple[list[GeneratorRegistry], list[str]]:
    """Read the generator registry: every generator that declares products.

    The registry is the generators' own statement, not a file name pattern:
    a generator joins it by declaring a module level ``GENERATED_PRODUCTS``
    constant.  The constant is read through the abstract syntax tree, so the
    auditor never has to execute a generator and never has to guess which
    files a generator writes.
    """
    root = Path(root)
    registry: list[GeneratorRegistry] = []
    problems: list[str] = []
    tools_root = root / GENERATOR_ROOT
    if not tools_root.is_dir():
        return registry, problems
    for path in sorted(tools_root.rglob("*.py")):
        relative = _relative(path, root)
        if any(part in SKIP_DIRS for part in Path(relative).parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError:
            problems.append(
                f"registry: {relative} cannot be parsed, so its "
                f"{REGISTRY_CONSTANT} declaration cannot be read"
            )
            continue
        value = _registry_value(tree)
        if value is None:
            continue
        try:
            products = ast.literal_eval(value)
        except (ValueError, SyntaxError, TypeError):
            problems.append(
                f"registry: {relative} declares {REGISTRY_CONSTANT} that is "
                "not a literal list of repository relative product paths"
            )
            continue
        if isinstance(products, str):
            # ``GENERATED_PRODUCTS = ("a.h")`` is a plain string in the
            # abstract syntax tree; it still states one product.
            products = (products,)
        if not isinstance(products, (list, tuple)) or not all(
            isinstance(item, str) for item in products
        ):
            problems.append(
                f"registry: {relative} declares {REGISTRY_CONSTANT} that is "
                "not a literal list of repository relative product paths"
            )
            continue
        registry.append(GeneratorRegistry(relative, tuple(products)))
    return registry, problems


def _registered_products(
    root: Path,
    registry: Sequence[GeneratorRegistry],
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Read every registered product.

    Returns the ``(path, generator, text)`` triples of the products that
    exist and the problems of the ones that do not.
    """
    root = Path(root)
    found: list[tuple[str, str, str]] = []
    problems: list[str] = []
    for entry in registry:
        for relative in entry.products:
            path = root / relative
            if not path.is_file():
                problems.append(
                    f"registry: {relative} is registered by {entry.generator} "
                    "but the file does not exist"
                )
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                problems.append(
                    f"registry: {relative} is registered by {entry.generator} "
                    f"but cannot be read ({error})"
                )
                continue
            found.append((relative, entry.generator, text))
    return found, problems


def _duplicate_registrations(
    registry: Sequence[GeneratorRegistry],
) -> list[str]:
    """Products that more than one generator claims."""
    owners: dict[str, list[str]] = {}
    for entry in registry:
        for relative in entry.products:
            owners.setdefault(relative, []).append(entry.generator)
    problems: list[str] = []
    for relative, generators in sorted(owners.items()):
        if len(generators) > 1:
            problems.append(
                f"registry: {relative} is registered by "
                f"{', '.join(sorted(generators))}"
            )
    return problems


def _text_files(root: Path) -> list[tuple[str, str]]:
    """Every text file of the swept trees, as ``(relative path, text)``."""
    found: list[tuple[str, str]] = []
    for scan_root in PRODUCT_SCAN_ROOTS:
        base = Path(root) / scan_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = _relative(path, Path(root))
            if any(part in SKIP_DIRS for part in Path(relative).parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            found.append((relative, text))
    return found


def discover_generated_files(
    root: Path | str,
    registry: Sequence[GeneratorRegistry],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Find the files that claim to be generated.

    A file claims to be generated when it carries the ``Generated by
    tools/...`` marker.  When the generator that wrote it joined the product
    registry, the file is *attributed*: the registry has to list it, or the
    audit fails closed.  When the generator did not join the registry the
    file is *unattributed*: there is no registry entry to check it against,
    so the auditor reports it as an open gap instead of claiming that it is
    clean.
    """
    root = Path(root)
    registered_generators = {entry.generator for entry in registry}
    attributed: list[tuple[str, str]] = []
    unattributed: list[tuple[str, str]] = []
    for relative, text in _text_files(root):
        match = _GENERATED_BY_RE.search(text)
        if match is None:
            continue
        generator = match.group("generator")
        if generator in registered_generators:
            attributed.append((relative, generator))
        else:
            unattributed.append((relative, generator))
    return attributed, unattributed


def _family_directories(reverse_root: Path) -> list[Path]:
    artifacts = Path(reverse_root) / "artifacts"
    if not artifacts.is_dir():
        return []
    return sorted(path for path in artifacts.iterdir() if path.is_dir())


def _family_blobs(family_dir: Path) -> list[bytes]:
    """The manifest of a family plus the files that manifest vouches for."""
    blobs: list[bytes] = []
    manifest_path = family_dir / "manifest.json"
    if not manifest_path.is_file():
        return blobs
    try:
        raw = manifest_path.read_bytes()
    except OSError:
        return blobs
    blobs.append(raw)
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return blobs
    files = manifest.get("files")
    if not isinstance(files, dict):
        return blobs
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            continue
        path = family_dir / relative
        if not path.is_file():
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if hashlib.sha256(payload).hexdigest() == expected:
            blobs.append(payload)
    return blobs


def _superseded_families(reverse_root: Path) -> dict[str, str]:
    """Map every superseded family to the family that replaced it."""
    superseded: dict[str, str] = {}
    for family_dir in _family_directories(reverse_root):
        manifest_path = family_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        relation = manifest.get("supersedes")
        if not isinstance(relation, dict):
            continue
        artifact = relation.get("artifact")
        if not isinstance(artifact, str):
            continue
        target = artifact.split("/")[-1]
        if target:
            superseded[target] = family_dir.name
    return superseded


def _families_recording(
    reverse_root: Path, digests: Iterable[str]
) -> dict[str, set[str]]:
    """Which families record each of the given ROM region digests."""
    wanted = {digest for digest in digests if digest}
    found: dict[str, set[str]] = {digest: set() for digest in wanted}
    if not wanted:
        return found
    for family_dir in _family_directories(reverse_root):
        blobs = _family_blobs(family_dir)
        if not blobs:
            continue
        for digest in wanted:
            needle = digest.encode("ascii")
            if any(needle in blob for blob in blobs):
                found[digest].add(family_dir.name)
    return found


def _verify_family(
    reverse_root: Path,
    family: str,
    declared_sha256: str,
    superseded: dict[str, str],
) -> FamilyAudit:
    """Resolve one declared family in the reverse work tree."""
    manifest_path = Path(reverse_root) / "artifacts" / family / "manifest.json"
    display = _relative(manifest_path, Path(reverse_root))
    if not manifest_path.is_file():
        return FamilyAudit(
            family=family,
            manifest_path=display,
            declared_sha256=declared_sha256,
            manifest_status="missing",
            problems=(
                f"{family}: manifest not found at {display} "
                "(the reverse work tree no longer carries this result)",
            ),
        )
    actual = sha256_file(manifest_path)
    problems: list[str] = []
    notes: list[str] = []
    status = "unknown"
    if actual != declared_sha256:
        problems.append(
            f"{family}: manifest sha256 mismatch "
            f"(declared {declared_sha256}, actual {actual})"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        manifest = None
    if not isinstance(manifest, dict):
        problems.append(f"{family}: manifest is not a JSON object")
    else:
        raw_status = manifest.get("artifact_status")
        if raw_status is None:
            status = "native-result"
            notes.append(
                "manifest carries no artifact_status; it is accepted as a "
                "native result manifest because no candidate, disproved or "
                "superseded marker is present"
            )
        else:
            status = str(raw_status)
            if raw_status != ACCEPTED_STATUS:
                problems.append(
                    f"{family}: artifact_status is {raw_status!r}, only "
                    f"{ACCEPTED_STATUS!r} results may be bound to a product"
                )
    if family in superseded:
        status = "superseded"
        problems.append(
            f"{family}: the family is superseded by {superseded[family]} and "
            "may not be bound to a product"
        )
    return FamilyAudit(
        family=family,
        manifest_path=display,
        declared_sha256=declared_sha256,
        actual_sha256=actual,
        manifest_status=status,
        notes=tuple(notes),
        problems=tuple(problems),
    )


def audit(root: Path | str, reverse_root: Path | str) -> AuditReport:
    """Audit every generated product against the reverse work tree."""
    root = Path(root)
    reverse_root = Path(reverse_root)
    report = AuditReport(
        root=str(root),
        reverse_root=str(reverse_root),
        carrier=CARRIER,
    )
    registry, registry_problems = read_registry(root)
    report.registry = registry
    for message in registry_problems:
        report.problems.append((EXIT_REGISTRY, message))
    for message in _duplicate_registrations(registry):
        report.problems.append((EXIT_REGISTRY, message))
    products, product_problems = _registered_products(root, registry)
    for message in product_problems:
        report.problems.append((EXIT_REGISTRY, message))
    attributed, unattributed = discover_generated_files(root, registry)
    registered = {path for path, _, _ in products}
    for path, generator in attributed:
        if path not in registered:
            report.out_of_scope.append(
                OutOfScopeProduct(
                    path=path,
                    reason=(
                        f"generated by {generator} but is not registered by "
                        "any generator"
                    ),
                )
            )
    for path, generator in unattributed:
        report.unattributed.append(
            OutOfScopeProduct(
                path=path,
                reason=(
                    f"generated by {generator}, which does not declare the "
                    "product registry, so no registry entry can be checked"
                ),
            )
        )
    for item in report.out_of_scope:
        report.problems.append(
            (
                EXIT_REGISTRY,
                f"registry: {item.path} is {item.reason}",
            )
        )
    if not registry:
        report.problems.append(
            (
                EXIT_REGISTRY,
                f"registry: no generator below {GENERATOR_ROOT.as_posix()} "
                f"declares {REGISTRY_CONSTANT}, so no product is audited",
            )
        )
        return report
    if not products:
        report.problems.append(
            (
                EXIT_REGISTRY,
                "registry: the registered products do not exist, so no "
                "declaration can be audited",
            )
        )
        return report
    if not (reverse_root / "artifacts").is_dir():
        report.problems.append(
            (
                EXIT_INPUT,
                f"the reverse work tree {reverse_root} carries no artifacts "
                "directory, so no declaration can be resolved",
            )
        )
        return report
    rom_path = root / ROM_PATH
    rom: bytes | None = None
    if rom_path.is_file():
        rom = rom_path.read_bytes()
    superseded = _superseded_families(reverse_root)
    declarations = [
        (path, generator, text, parse_declaration(text))
        for path, generator, text in products
    ]
    declared_digests = {
        rom.sha256
        for _, _, _, declaration in declarations
        if declaration is not None
        for rom in declaration.roms
    }
    recording = _families_recording(reverse_root, declared_digests)
    families: dict[str, FamilyAudit] = {}
    for path, generator, text, declaration in declarations:
        product_problems: list[str] = []
        status = "undeclared"
        families_here: list[str] = []
        reasons: list[str] = []
        marker = _GENERATED_BY_RE.search(text)
        if marker is None:
            product_problems.append(
                f"{path}: carries no 'Generated by tools/...' marker, so no "
                "generator can be held responsible for it"
            )
        elif marker.group("generator") != generator:
            product_problems.append(
                f"{path}: says it was generated by {marker.group('generator')} "
                f"but {generator} registered it"
            )
        if declaration is None:
            product_problems.append(
                f"{path}: carries no reverse-source declaration"
            )
        else:
            if declaration.carrier != CARRIER:
                product_problems.append(
                    f"{path}: declares carrier {declaration.carrier!r} but the "
                    f"library uses {CARRIER!r}"
                )
            if declaration.sources:
                status = "declared"
                families_here = [source.family for source in declaration.sources]
            elif declaration.not_applicable:
                status = "not-applicable"
            else:
                product_problems.append(
                    f"{path}: the declaration names neither a family nor a "
                    "not-applicable reason"
                )
            reasons = list(declaration.not_applicable)
            if declaration.consumes_no_rom:
                if declaration.sources:
                    product_problems.append(
                        f"{path}: declares a family but states that it "
                        "consumes no rom region"
                    )
                if not reasons:
                    product_problems.append(
                        f"{path}: states that it consumes no rom region but "
                        "gives no not-applicable reason"
                    )
            for source in declaration.sources:
                if source.family in families:
                    continue
                families[source.family] = _verify_family(
                    reverse_root, source.family, source.manifest_sha256, superseded
                )
            # The manifest gate comes first: a family that cannot be resolved
            # makes every later check meaningless.
            for family in families_here:
                family_audit = families.get(family)
                if family_audit is None:
                    continue
                product_problems.extend(family_audit.problems)
            if not declaration.roms and not declaration.consumes_no_rom:
                product_problems.append(
                    f"{path}: the declaration records no consumed rom region"
                )
            covered, region_problems = _check_rom_regions(
                path=path,
                roms=declaration.roms,
                families=families_here,
                reasons=reasons,
                rom=rom,
                recording=recording,
            )
            for family in families_here:
                if family not in covered:
                    product_problems.append(
                        f"{path}: the declared family {family} records none of "
                        "the consumed rom regions of this product"
                    )
            product_problems.extend(region_problems)
        report.products.append(
            ProductAudit(
                path=path,
                generator=generator,
                status=status,
                families=tuple(families_here),
                reasons=tuple(reasons),
                problems=tuple(product_problems),
            )
        )
        for problem in product_problems:
            code = _problem_code(problem)
            report.problems.append((code, problem))
    report.families = [families[name] for name in sorted(families)]
    return report


def _check_rom_regions(
    *,
    path: str,
    roms: Sequence[RomDeclaration],
    families: Sequence[str],
    reasons: Sequence[str],
    rom: bytes | None,
    recording: dict[str, set[str]],
) -> tuple[set[str], list[str]]:
    """Check the consumed ROM regions of one product.

    A region that a reverse family records has to be covered by a family the
    product declares -- a product may not consume bytes of a result it does
    not name.  A region that no family records has to be covered by a
    not-applicable reason, so that the gap stays visible.
    """
    problems: list[str] = []
    covered: set[str] = set()
    for declaration in roms:
        where = f"0x{declaration.offset:06X}+{declaration.length}"
        if rom is not None:
            if declaration.offset + declaration.length > len(rom):
                problems.append(
                    f"{path}: the consumed rom region {where} lies outside "
                    "the ROM"
                )
            else:
                actual = hashlib.sha256(
                    rom[declaration.offset:declaration.offset + declaration.length]
                ).hexdigest()
                if actual != declaration.sha256:
                    problems.append(
                        f"{path}: the consumed rom region {where} hashes to "
                        f"{actual}, not to the declared {declaration.sha256}"
                    )
        recording_families = recording.get(declaration.sha256, set())
        if recording_families:
            if not recording_families.intersection(families):
                problems.append(
                    f"{path}: the consumed rom region {where} is recorded by "
                    f"{', '.join(sorted(recording_families))}, which the "
                    "product does not declare"
                )
            covered.update(recording_families.intersection(families))
        elif not reasons:
            problems.append(
                f"{path}: the consumed rom region {where} is recorded by no "
                "reverse family, so the product must state a not-applicable "
                "reason"
            )
    return covered, problems


def _problem_code(message: str) -> int:
    """Classify a problem message into its exit code."""
    if "manifest not found" in message:
        return EXIT_MISSING_MANIFEST
    if "sha256 mismatch" in message:
        return EXIT_MANIFEST_MISMATCH
    if "artifact_status" in message or "superseded" in message:
        return EXIT_STATUS_REJECTED
    if "rom region" in message or "outside the ROM" in message:
        return EXIT_ROM_REGION
    if "no reverse-source declaration" in message:
        return EXIT_UNDECLARED
    if "no 'Generated by" in message or "registered it" in message:
        return EXIT_REGISTRY
    return EXIT_INPUT


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root that holds the generated products",
    )
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=DEFAULT_REVERSE_ROOT,
        help="reverse work tree that holds the signed manifests",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the report as JSON instead of text",
    )
    args = parser.parse_args(argv)
    report = audit(args.root, args.reverse_root)
    if args.json:
        print(json.dumps(report.as_json(), ensure_ascii=False, indent=2))
    else:
        print(report.summary())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
