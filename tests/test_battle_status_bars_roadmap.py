import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusBarsRoadmapTests(unittest.TestCase):
    def test_roadmap_does_not_leave_the_resolved_visible_gap_current(self):
        roadmap = (ROOT / "docs/sequel-roadmap.md").read_text(encoding="utf-8")
        self.assertIn(
            "battle-status-bars-v1` 随后逐项闭合这 181/181 cell、22/22 种内容",
            roadmap,
        )
        self.assertIn("当前已跟踪可见图像未知分母为 0/0", roadmap)


if __name__ == "__main__":
    unittest.main()
