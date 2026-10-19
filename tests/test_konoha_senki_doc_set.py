#!/usr/bin/env python3
"""The Konoha Senki decomposition doc set must stay internally consistent.

The set is the project's long-term memory for the remake, so a dangling
cross-reference or a document that claims coverage it cannot support would
silently mislead the next session. This gate checks both.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_SET = ROOT / "docs/konoha-senki"
LINK = re.compile(r"\]\(([^)#][^)]*)\)")
HEADING = re.compile(r"^#{1,3} ", re.MULTILINE)


def documents() -> list[Path]:
    return sorted(DOC_SET.glob("*.md"))


class KonohaSenkiDocSetTest(unittest.TestCase):
    def test_index_exists_and_points_at_every_other_document(self):
        self.assertTrue((DOC_SET / "README.md").is_file())
        index = (DOC_SET / "README.md").read_text(encoding="utf-8")
        for path in documents():
            if path.name == "README.md":
                continue
            with self.subTest(document=path.name):
                self.assertIn(path.name, index)

    def test_every_relative_link_resolves(self):
        broken = []
        for document in documents():
            text = document.read_text(encoding="utf-8")
            for target in LINK.findall(text):
                if target.startswith("http"):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    broken.append(f"{document.name} -> {target}")
        self.assertEqual(broken, [], f"dangling links: {broken}")

    def test_documents_declare_coverage_and_evidence_rules(self):
        index = (DOC_SET / "README.md").read_text(encoding="utf-8")
        for rule in ("只写有证据的结论", "像素等价优先于观感", "模型结论必须回原图复核"):
            with self.subTest(rule=rule):
                self.assertIn(rule, index)
        self.assertIn("覆盖状态", index)

    def test_index_points_at_the_reverse_engineering_chain_and_its_tools(self):
        index = (DOC_SET / "README.md").read_text(encoding="utf-8")
        for token in ("A 键处理链", "0x0806289C", "read_rom_unit_pool.py",
                      "disasm_thumb.py", "连续判断错了十二次", "红测不一定意味着产品错", "开场对白", "逐句一致", "按画面内容对齐", "不要从接触表"):
            with self.subTest(token=token):
                self.assertIn(token, index)

    def test_refuted_claims_are_kept_with_their_refuting_evidence(self):
        """A refuted root cause must stay visible so nobody re-applies it."""
        s49 = (DOC_SET / "01-battle-s49.md").read_text(encoding="utf-8")
        self.assertIn("被自我更正过两次", s49)
        self.assertIn("不要改", s49)
        self.assertIn("语义未定", s49)

    def test_unverified_claims_are_marked_instead_of_asserted(self):
        """A known-refuted claim must stay flagged, not silently deleted."""
        index = (DOC_SET / "README.md").read_text(encoding="utf-8")
        self.assertIn("覆盖不足的部分不得因为", index)
        s49 = (DOC_SET / "01-battle-s49.md").read_text(encoding="utf-8")
        self.assertIn("待验证", s49)
        self.assertIn("红门禁", s49)


if __name__ == "__main__":
    unittest.main()
