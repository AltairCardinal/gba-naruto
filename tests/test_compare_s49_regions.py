#!/usr/bin/env python3
"""The region comparison must measure what it claims and refuse soft alignment."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.butano.compare_s49_regions import (
    RegionComparisonError,
    compare_pair,
    compare_regions,
    difference_mask,
    load_regions,
)


def frame(colour: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    return Image.new("RGB", (240, 160), colour)


class CompareRegionsTest(unittest.TestCase):
    def test_identical_frames_report_zero_everywhere(self):
        report = compare_regions(frame((5, 6, 7)), frame((5, 6, 7)))
        self.assertEqual(report["status-bar"]["different_pixels"], 0)
        self.assertIsNone(report["status-bar"]["difference_bbox"])
        self.assertEqual(report["full-screen"]["area_pixels"], 240 * 160)

    def test_counts_only_the_changed_pixels(self):
        left = frame()
        right = frame()
        left.putpixel((217, 144), (255, 0, 0))
        report = compare_regions(left, right)
        self.assertEqual(report["status-bar"]["different_pixels"], 1)
        self.assertEqual(report["status-bar"]["difference_bbox"], [217, 144, 218, 145])
        self.assertEqual(report["full-screen"]["different_pixels"], 1)

    def test_bbox_is_reported_in_screen_coordinates(self):
        left = frame()
        right = frame()
        left.putpixel((3, 120), (1, 1, 1))
        report = compare_regions(left, right)
        self.assertEqual(report["dialogue-area"]["difference_bbox"], [3, 120, 4, 121])

    def test_regions_do_not_leak_into_each_other(self):
        left = frame()
        right = frame()
        left.putpixel((10, 10), (9, 9, 9))
        report = compare_regions(left, right)
        self.assertEqual(report["portrait-area"]["different_pixels"], 1)
        self.assertEqual(report["status-bar"]["different_pixels"], 0)
        self.assertEqual(report["dialogue-area"]["different_pixels"], 0)

    def test_rejects_wrong_screen_size(self):
        with self.assertRaises(RegionComparisonError):
            compare_regions(Image.new("RGB", (8, 8)), frame())

    def test_rejects_region_outside_the_screen(self):
        with self.assertRaises(RegionComparisonError):
            compare_regions(frame(), frame(), {"bad": (0, 0, 400, 160)})

    def test_no_tolerance_means_near_identical_still_counts(self):
        left = frame((10, 10, 10))
        right = frame((11, 10, 10))
        self.assertEqual(compare_regions(left, right)["full-screen"]["different_pixels"],
                         240 * 160)


class DifferenceMaskTest(unittest.TestCase):
    def test_mask_is_binary(self):
        left = frame((0, 0, 0))
        right = frame((1, 2, 3))
        self.assertEqual(sum(mask.histogram()[255] for mask in [difference_mask(left, right)]), 240 * 160)


class ComparePairTest(unittest.TestCase):
    def test_reads_declared_frames_from_disk(self):
        with TemporaryDirectory() as root:
            left = Path(root) / "a.png"
            right = Path(root) / "b.png"
            frame().save(left)
            frame().save(right)
            result = compare_pair(left, right)
            self.assertEqual(result["original_frame"], "a.png")
            self.assertEqual(result["comparison"],
                             "declared-pair-no-alignment-search-no-mask")

    def test_missing_frame_is_refused(self):
        with TemporaryDirectory() as root:
            left = Path(root) / "a.png"
            frame().save(left)
            with self.assertRaises(RegionComparisonError):
                compare_pair(left, Path(root) / "absent.png")


class LoadRegionsTest(unittest.TestCase):
    def test_reads_explicit_region_table(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "regions.json"
            path.write_text('{"top": [0, 0, 240, 96]}', encoding="utf-8")
            self.assertEqual(load_regions(path), {"top": (0, 0, 240, 96)})

    def test_rejects_malformed_region(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "regions.json"
            path.write_text('{"top": [0, 0, 240]}', encoding="utf-8")
            with self.assertRaises(RegionComparisonError):
                load_regions(path)

    def test_none_means_the_default_table(self):
        self.assertIsNone(load_regions(None))


if __name__ == "__main__":
    unittest.main()
