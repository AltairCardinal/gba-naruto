#!/usr/bin/env python3
"""The generated artifacts must name the reverse result they came from.

`tools/measure_butano_reverse_gap.py` counts a reverse family as *consumed*
when the family name shows up in the remake tree.  That is a lower bound: a
name can show up in a comment, a doc or a script without a single byte of
lineage behind it.  The M0 milestone of
``docs/butano-reverse-gap-roadmap.md`` replaces the lower bound with a fact
by making every generated product carry a machine readable declaration:

    // provenance-carrier: c-header-comment
    // reverse-source: <artifact-family> @ <manifest-sha256>

and by adding ``tools/audit_butano_reverse_provenance.py``, which reads those
declarations back, resolves every family in the reverse work tree, re-hashes
the manifest and fails closed when the manifest is gone, edited or not a
result.

The rules this test pins down:

* the declaration is the **only** way a product is bound to a family -- the
  auditor must not carry a list of family names of its own, otherwise the
  gap measurement would be inflated by the auditor itself;
* the set of audited products comes from the **generators**, not from a file
  name pattern: a generator declares ``GENERATED_PRODUCTS`` in its own
  source, the auditor reads that constant back, a generated file that no
  generator registers is a hard failure, and a registered product that
  carries no declaration is a hard failure too;
* a family whose manifest is missing from the reverse work tree is a hard
  failure that names the family, never a silent skip;
* a manifest that moved (hash mismatch) or that is not a result
  (``candidate`` / ``disproved`` / ``superseded``) is a hard failure too;
* a product that carries no declaration is reported as *undeclared* instead
  of being quietly counted as clean;
* a declaration that claims a family must also record the ROM bytes the
  product consumed, and those bytes must be recorded by that very family;
* a product that consumes no ROM byte at all has to say so explicitly
  (``// reverse-source-rom: none``) next to a not-applicable reason, so the
  gap stays visible instead of being a silent omission.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.audit_butano_reverse_provenance import (
    CARRIER,
    REPO_ROOT,
    audit,
    parse_declaration,
    provenance_block,
)

REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

FAMILY = "demo-family-v1"
OTHER_FAMILY = "demo-family-v2"

ROM_OFFSET = 0x10
ROM_LENGTH = 16

DEFAULT_GENERATOR = "tools/generate_butano_demo_content.py"
DEFAULT_PRODUCT_NAME = "generated_demo_content.h"
DEFAULT_PRODUCT = "butano-sequel/game/include/konoha/generated_demo_content.h"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rom_bytes() -> bytes:
    return bytes(range(256)) * 4


def _region_digest(rom: bytes) -> str:
    return _sha256(rom[ROM_OFFSET:ROM_OFFSET + ROM_LENGTH])


def _write_family(
    reverse_root: Path,
    family: str,
    *,
    status: str = "accepted",
    region_digest: str | None = None,
    supersedes: str | None = None,
    extra: dict | None = None,
) -> Path:
    manifest: dict = {
        "artifact_status": status,
        "rom": {"path": "rom/base.gba", "sha256": _sha256(_rom_bytes())},
    }
    if region_digest is not None:
        manifest["regions"] = [
            {
                "file_offset": ROM_OFFSET,
                "length": ROM_LENGTH,
                "sha256": region_digest,
            }
        ]
    if supersedes is not None:
        manifest["supersedes"] = {"artifact": f"artifacts/{supersedes}"}
    if extra:
        manifest.update(extra)
    directory = reverse_root / "artifacts" / family
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def _write_generator(
    root: Path,
    products: tuple[str, ...],
    *,
    generator: str = DEFAULT_GENERATOR,
    literal: bool = True,
) -> Path:
    """Write a generator that registers the given products."""
    path = root / generator
    path.parent.mkdir(parents=True, exist_ok=True)
    listing = "".join(f'    "{item}",\n' for item in products)
    if literal:
        body = f"GENERATED_PRODUCTS = (\n{listing})\n"
    else:
        body = f"GENERATED_PRODUCTS = tuple({listing!r}.split())\n"
    path.write_text(body, encoding="utf-8")
    return path


def _write_product(
    root: Path,
    body: str,
    name: str = DEFAULT_PRODUCT_NAME,
    *,
    register: bool = True,
    generator: str = DEFAULT_GENERATOR,
) -> Path:
    relative = f"butano-sequel/game/include/konoha/{name}"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    if register:
        _write_generator(root, (relative,), generator=generator)
    return path


def _header(
    *,
    sources: tuple[tuple[str, str], ...] = (),
    roms: tuple[tuple[int, int, str], ...] = (),
    not_applicable: tuple[str, ...] = (),
    no_rom_region: bool = False,
) -> str:
    lines = [
        f"// Generated by {DEFAULT_GENERATOR}. Do not edit.",
        f"// provenance-carrier: {CARRIER}",
    ]
    for family, manifest_sha in sources:
        lines.append(f"// reverse-source: {family} @ {manifest_sha}")
    for offset, length, digest in roms:
        lines.append(
            f"// reverse-source-rom: 0x{offset:06X}+{length} "
            f"sha256 {digest}"
        )
    if no_rom_region:
        lines.append("// reverse-source-rom: none")
    for reason in not_applicable:
        lines.append(f"// reverse-source: not-applicable - {reason}")
    lines.append("#define KONOHA_GENERATED_DEMO_CONTENT_H")
    return "\n".join(lines) + "\n"


class DeclarationParsingTests(unittest.TestCase):
    """The declaration grammar is the contract between product and auditor."""

    def test_block_round_trips_through_the_parser(self):
        block = provenance_block(
            sources=((FAMILY, "a" * 64),),
            roms=((ROM_OFFSET, ROM_LENGTH, "b" * 64),),
            not_applicable=("no signed manifest covers the region",),
        )
        declaration = parse_declaration(block)
        self.assertIsNotNone(declaration)
        assert declaration is not None
        self.assertEqual(declaration.carrier, CARRIER)
        self.assertEqual(
            [(source.family, source.manifest_sha256)
             for source in declaration.sources],
            [(FAMILY, "a" * 64)],
        )
        self.assertEqual(
            [(rom.offset, rom.length, rom.sha256) for rom in declaration.roms],
            [(ROM_OFFSET, ROM_LENGTH, "b" * 64)],
        )
        self.assertEqual(
            declaration.not_applicable,
            ("no signed manifest covers the region",),
        )
        self.assertFalse(declaration.consumes_no_rom)

    def test_a_product_without_a_declaration_parses_to_none(self):
        self.assertIsNone(
            parse_declaration("// Generated by tools/generate_butano_demo.py.\n")
        )

    def test_a_not_applicable_declaration_without_a_reason_is_rejected(self):
        declaration = parse_declaration(
            f"// provenance-carrier: {CARRIER}\n"
            "// reverse-source: not-applicable - \n"
        )
        self.assertIsNotNone(declaration)
        assert declaration is not None
        self.assertEqual(declaration.not_applicable, ())

    def test_the_no_rom_region_statement_is_parsed(self):
        block = provenance_block(
            not_applicable=("the product consumes no rom byte",),
            no_rom_region=True,
        )
        declaration = parse_declaration(block)
        self.assertIsNotNone(declaration)
        assert declaration is not None
        self.assertTrue(declaration.consumes_no_rom)
        self.assertEqual(declaration.roms, ())


class AuditTests(unittest.TestCase):
    """The auditor resolves every declaration against the reverse work tree."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name) / "repo"
        self.reverse_root = Path(self._temporary.name) / "reverse"
        (self.root / "rom").mkdir(parents=True)
        (self.root / "rom" / "base.gba").write_bytes(_rom_bytes())
        (self.reverse_root / "artifacts").mkdir(parents=True)

    def tearDown(self):
        self._temporary.cleanup()

    def test_missing_manifest_fails_closed_and_names_the_family(self):
        manifest = _write_family(
            self.reverse_root, OTHER_FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, "c" * 64),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn(FAMILY, report.summary())
        self.assertIn("manifest", report.summary())
        self.assertIn("manifest not found", report.summary())
        # the family that does have a manifest must not be reported as broken
        self.assertNotIn(f"{OTHER_FAMILY}: manifest", report.summary())
        self.assertEqual(manifest.is_file(), True)

    def test_a_product_without_a_declaration_is_reported_as_undeclared(self):
        _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            "// Generated by tools/generate_butano_demo_content.py. Do not edit.\n"
            "#define KONOHA_GENERATED_DEMO_CONTENT_H\n",
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        statuses = {product.path: product.status for product in report.products}
        self.assertIn("undeclared", statuses.values())
        self.assertEqual(report.declared_product_count, 0)

    def test_a_matching_manifest_produces_a_mapping(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(report.declared_product_count, 1)
        self.assertEqual(
            [(product, family) for product, family in report.mapping],
            [("butano-sequel/game/include/konoha/generated_demo_content.h", FAMILY)],
        )

    def test_a_manifest_whose_bytes_moved_fails_closed(self):
        _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, "d" * 64),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("sha256", report.summary())

    def test_a_candidate_family_is_rejected(self):
        manifest = _write_family(
            self.reverse_root,
            FAMILY,
            status="candidate",
            region_digest=_region_digest(_rom_bytes()),
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("candidate", report.summary())

    def test_a_superseded_family_is_rejected(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_family(
            self.reverse_root,
            OTHER_FAMILY,
            supersedes=FAMILY,
            region_digest=_region_digest(_rom_bytes()),
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("superseded", report.summary())

    def test_a_family_that_does_not_record_the_consumed_rom_region_fails(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=None
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, "e" * 64),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("rom region", report.summary())

    def test_a_rom_region_whose_bytes_do_not_match_fails(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest="f" * 64
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, "f" * 64),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("rom", report.summary())

    def test_a_not_applicable_declaration_passes_when_no_family_covers_it(self):
        # No family in the reverse tree records this region, so the product
        # may say that it is not applicable -- and the auditor checks it.
        _write_product(
            self.root,
            _header(
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
                not_applicable=(
                    "no signed reverse manifest records the units table",
                ),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(report.declared_product_count, 1)
        self.assertEqual(report.mapping, [])

    def test_a_region_covered_by_another_family_must_be_declared(self):
        # The region is recorded by OTHER_FAMILY, so a product that consumes
        # it has to name that family.
        _write_family(
            self.reverse_root, OTHER_FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        manifest = _write_family(self.reverse_root, FAMILY, region_digest=None)
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("does not declare", report.summary())

    def test_a_product_may_declare_a_family_and_a_not_applicable_reason(self):
        # One region is covered by the declared family, another one is
        # covered by nobody: the product has to say so.
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
                not_applicable=(
                    "no signed reverse manifest records the positions table",
                ),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(report.declared_product_count, 1)
        self.assertEqual(
            report.mapping,
            [("butano-sequel/game/include/konoha/generated_demo_content.h", FAMILY)],
        )

    def test_a_missing_reverse_work_tree_fails_closed(self):
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, "a" * 64),),
            ),
        )
        report = audit(self.root, Path(self._temporary.name) / "absent")
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("reverse", report.summary().lower())


class RegistryTests(unittest.TestCase):
    """The product set comes from the generators, not from a file pattern."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name) / "repo"
        self.reverse_root = Path(self._temporary.name) / "reverse"
        (self.root / "rom").mkdir(parents=True)
        (self.root / "rom" / "base.gba").write_bytes(_rom_bytes())
        (self.reverse_root / "artifacts").mkdir(parents=True)

    def tearDown(self):
        self._temporary.cleanup()

    def test_a_product_outside_any_file_name_pattern_is_audited(self):
        # The product is named ``demo_content.h``: no ``generated_*.h`` glob
        # would ever find it, the registry does.
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        relative = "butano-sequel/game/include/konoha/demo_content.h"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
            encoding="utf-8",
        )
        _write_generator(self.root, (relative,))
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(report.declared_product_count, 1)
        self.assertEqual(report.mapping, [(relative, FAMILY)])

    def test_a_generated_file_that_no_generator_registers_fails(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        # The product carries the marker of a generator that exists but does
        # not register it: the registry has to cover it.
        relative = "butano-sequel/game/include/konoha/generated_demo_content.h"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
            ),
            encoding="utf-8",
        )
        _write_generator(
            self.root,
            ("butano-sequel/game/include/konoha/generated_other_content.h",),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("not registered", report.summary())
        self.assertIn(relative, report.summary())

    def test_a_generated_file_of_a_generator_outside_the_registry_is_reported(self):
        # The generator exists but never joined the provenance contract, so
        # there is no registry entry to check it against.  The gap stays
        # visible in the report instead of being counted as clean.
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        relative = "butano-sequel/game/include/konoha/generated_demo_content.h"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _header(
            sources=((FAMILY, _sha256(manifest.read_bytes())),),
            roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
        ).replace(
            DEFAULT_GENERATOR, "tools/generate_butano_outsider.py"
        )
        path.write_text(body, encoding="utf-8")
        outsider = self.root / "tools" / "generate_butano_outsider.py"
        outsider.parent.mkdir(parents=True, exist_ok=True)
        outsider.write_text("OUTPUTS = ()\n", encoding="utf-8")
        report = audit(self.root, self.reverse_root)
        self.assertEqual(
            [item.path for item in report.unattributed],
            [relative],
        )
        self.assertEqual(report.out_of_scope, [])

    def test_a_registered_product_that_does_not_exist_fails(self):
        _write_generator(
            self.root,
            ("butano-sequel/game/include/konoha/generated_absent_content.h",),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("does not exist", report.summary())

    def test_a_registered_product_without_a_declaration_fails(self):
        _write_product(
            self.root,
            "// Generated by tools/generate_butano_demo_content.py. Do not edit.\n"
            "#define KONOHA_GENERATED_DEMO_CONTENT_H\n",
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("no reverse-source declaration", report.summary())

    def test_a_generator_whose_registry_is_not_a_literal_fails(self):
        _write_generator(
            self.root,
            ("butano-sequel/game/include/konoha/generated_demo_content.h",),
            literal=False,
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("literal", report.summary())

    def test_a_product_registered_by_two_generators_fails(self):
        _write_generator(self.root, (DEFAULT_PRODUCT,))
        _write_generator(
            self.root,
            (DEFAULT_PRODUCT,),
            generator="tools/generate_butano_other_content.py",
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("registered by", report.summary())

    def test_the_marker_must_name_the_registering_generator(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        body = _header(
            sources=((FAMILY, _sha256(manifest.read_bytes())),),
            roms=((ROM_OFFSET, ROM_LENGTH, _region_digest(_rom_bytes())),),
        ).replace(
            DEFAULT_GENERATOR, "tools/generate_butano_somebody_else.py"
        )
        _write_product(self.root, body)
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("registered it", report.summary())

    def test_a_product_that_consumes_no_rom_region_has_to_say_so(self):
        # A not-applicable reason alone is not enough: the product has to
        # state that it consumes no rom byte at all.
        _write_product(
            self.root,
            _header(
                not_applicable=("the product is a remake side reconstruction",),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("no consumed rom region", report.summary())

    def test_a_product_that_states_it_consumes_no_rom_region_passes(self):
        _write_product(
            self.root,
            _header(
                not_applicable=("the product is a remake side reconstruction",),
                no_rom_region=True,
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(report.declared_product_count, 1)
        self.assertEqual(report.mapping, [])

    def test_the_no_rom_region_statement_may_not_accompany_a_family(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
                not_applicable=("the product is a remake side reconstruction",),
                no_rom_region=True,
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("consumes no rom region", report.summary())

    def test_a_declared_family_must_record_the_regions_the_product_consumed(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=None
        )
        _write_product(
            self.root,
            _header(
                sources=((FAMILY, _sha256(manifest.read_bytes())),),
            ),
        )
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn("no consumed rom region", report.summary())


class AuditorHonestyTests(unittest.TestCase):
    """The auditor must not carry a family list of its own."""

    def test_the_auditor_source_embeds_no_artifact_family_name(self):
        source = (
            REPO_ROOT / "tools" / "audit_butano_reverse_provenance.py"
        ).read_text(encoding="utf-8")
        literals = re.findall(r"[\"']([a-z0-9][a-z0-9-]*-v[0-9]+)[\"']", source)
        self.assertEqual(
            literals,
            [],
            "the auditor must resolve families from the declarations, "
            "not from a list of family names",
        )

    def test_the_auditor_carries_no_product_list_of_its_own(self):
        source = (
            REPO_ROOT / "tools" / "audit_butano_reverse_provenance.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "generated_battle",
            source,
            "the auditor must not name a product; the registry comes from the "
            "generators",
        )


class RepositoryIntegrationTests(unittest.TestCase):
    """The repository's own generated products must carry a declaration."""

    def test_every_generated_product_in_the_repository_declares_its_source(self):
        report = audit(REPO_ROOT, REVERSE_ROOT)
        products = [
            product for product in report.products
        ]
        self.assertTrue(products, "no generated product was discovered")
        for product in products:
            with self.subTest(product=product.path):
                self.assertNotEqual(
                    product.status,
                    "undeclared",
                    f"{product.path} carries no reverse-source declaration",
                )
                if product.status == "not-applicable":
                    self.assertTrue(
                        product.reasons,
                        f"{product.path} must state why it is not applicable",
                    )

    def test_the_repository_registry_covers_every_generated_product(self):
        report = audit(REPO_ROOT, REVERSE_ROOT)
        self.assertEqual(
            [item.path for item in report.out_of_scope],
            [],
            "a generated file that no generator registers is not audited",
        )

    def test_the_repository_products_are_not_guessed_from_a_file_name_pattern(self):
        report = audit(REPO_ROOT, REVERSE_ROOT)
        paths = {product.path for product in report.products}
        self.assertTrue(
            any(
                not Path(path).name.startswith("generated_")
                for path in paths
            ),
            "the audited product set must not be a `generated_*.h` glob",
        )
        self.assertTrue(
            any(
                Path(path).parent.as_posix() != "butano-sequel/game/include/konoha"
                for path in paths
            ),
            "the audited product set must not be limited to one directory",
        )

    @unittest.skipUnless(
        (REVERSE_ROOT / "artifacts").is_dir(),
        "reverse work tree is not available on this machine",
    )
    def test_the_repository_audit_passes_against_the_reverse_work_tree(self):
        report = audit(REPO_ROOT, REVERSE_ROOT)
        self.assertEqual(report.exit_code, 0, report.summary())
        self.assertEqual(
            report.declared_product_count,
            len([p for p in report.products if p.status != "undeclared"]),
        )


if __name__ == "__main__":
    unittest.main()


class ImporterCarrierTests(unittest.TestCase):
    """The header comment is not the only carrier.

    The two ROM importers bind their own families with a family name and the
    SHA-256 of its manifest, checked at run time.  Reading only the header
    carrier reports those families as "mentioned but not declared", which
    understates what is wired -- by 54 families in this tree.
    """

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name) / "repo"
        self.reverse_root = Path(self._temporary.name) / "reverse"
        (self.root / "tools" / "butano").mkdir(parents=True)
        (self.root / "rom").mkdir(parents=True)
        (self.root / "rom" / "base.gba").write_bytes(_rom_bytes())
        (self.reverse_root / "artifacts").mkdir(parents=True)

    def tearDown(self):
        self._temporary.cleanup()

    def _write_importer(self, family: str, manifest_sha256: str) -> None:
        path = self.root / "tools" / "butano" / "import_rom_pixel_ab_baselines.py"
        path.write_text(
            "from __future__ import annotations\n"
            "\n"
            "PIXEL_AB_FAMILIES: tuple[tuple[str, str], ...] = (\n"
            f'    ("{family}", "{manifest_sha256}"),\n'
            ")\n",
            encoding="utf-8",
        )

    def test_the_importer_carrier_binds_a_family(self):
        manifest = _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        self._write_importer(FAMILY, _sha256(manifest.read_bytes()))
        report = audit(self.root, self.reverse_root)
        self.assertEqual([wire.family for wire in report.importer_wires], [FAMILY])
        self.assertEqual(report.declared_family_count, 1)
        self.assertEqual(report.importer_wires[0].manifest_status, "accepted")
        # The tree has no generator registry, which is its own problem -- but
        # no problem may be raised against the importer-carrier family.
        self.assertEqual(report.importer_wires[0].problems, ())
        self.assertFalse(
            [message for _code, message in report.problems if FAMILY in message]
        )

    def test_an_importer_pin_with_a_moved_manifest_fails_closed(self):
        _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        self._write_importer(FAMILY, "c" * 64)
        report = audit(self.root, self.reverse_root)
        self.assertNotEqual(report.exit_code, 0)
        self.assertIn(FAMILY, report.summary())
        self.assertTrue(report.importer_wires)
        self.assertTrue(report.importer_wires[0].problems)

    def test_a_tree_without_importers_has_no_importer_wire(self):
        """A missing importer is a different tree, not an error."""
        _write_family(
            self.reverse_root, FAMILY, region_digest=_region_digest(_rom_bytes())
        )
        report = audit(self.root, self.reverse_root)
        self.assertEqual(report.importer_wires, [])


class RepositoryImporterCarrierTests(unittest.TestCase):
    """The real tree declares 66 families across the two carriers."""

    def test_the_real_tree_declares_both_carriers(self):
        report = audit(REPO_ROOT, REVERSE_ROOT)
        header = {family for _product, family in report.mapping}
        importer = {wire.family for wire in report.importer_wires}
        self.assertTrue(header, "the header carrier must declare families")
        self.assertTrue(importer, "the importer carrier must declare families")
        self.assertEqual(
            report.declared_family_count,
            len(header | importer),
        )
        self.assertEqual(report.exit_code, 0, report.summary())
