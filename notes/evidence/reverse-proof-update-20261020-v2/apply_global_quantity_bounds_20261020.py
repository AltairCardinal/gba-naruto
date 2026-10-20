#!/usr/bin/env python3
"""把审计器测试模块里剩下的「陈旧全局量断言」按全局量派生 / 批次增量硬编码改正。

用途
----
`tests/test_audit_rom_byte_coverage.py`（88 个测试类 / 359 个测试方法）里，
一批断言把**活账本的全局量**写死成字面量。账本每晋升一次它们就漂移一次。
本脚本做两件事：

1. **§A / §B**：把仍然写死的全局量（只增的累计量、只缩的 unknown 量、
   全局分母摘要）改成「界」或「与活注册表对拍」。
2. **§D**：**反向修复**第一轮改写（commit ``c3e2b71c``，131 处）引入的缺陷 ——
   那次改写用「表达式里有没有减号」来猜界的方向，把
   ``c["range"][1] - c["range"][0]`` 里的减号误读成「这个量会缩小」，
   于是给**只会增长的批次字节总量**加了上界；同时把**批次 claim 数的等号**
   放松成了下界。两处都违反「全局量派生、批次增量硬编码」：
   - 上界留错侧 ⇒ 批次合法变大时**误报失败**；
   - 批次等号被放松 ⇒ 批次变小这种**真回归漏报**。

脚本性质
--------
- **幂等**：再跑一次不会产生任何改动。
- **失败关闭**：每条替换必须在目标类的块内**恰好命中一次**，否则直接非 0 退出。
- ``--dry-run`` 先看再落盘；``--apply`` 才写。

用法
----
    /usr/local/bin/python3 notes/evidence/reverse-proof-update-20261020-v2/apply_global_quantity_bounds_20261020.py --dry-run
    /usr/local/bin/python3 notes/evidence/reverse-proof-update-20261020-v2/apply_global_quantity_bounds_20261020.py --apply
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TARGET = REPO / "tests" / "test_audit_rom_byte_coverage.py"

# ---------------------------------------------------------------------------
# 替换表：(测试类名, 旧文本, 新文本)
# ---------------------------------------------------------------------------

# §D —— 反向修复第一轮改写引入的缺陷（批次增量被错转成界）。
REVERSE_BATCH_DELTAS: list[tuple[str, str, str]] = [
    (
        "BootContinuationAndCfgV19AtomicCoverageTests",
        'self.assertGreaterEqual(len(continuation_claims), 6)',
        'self.assertEqual(6, len(continuation_claims))',
    ),
    (
        "BootContinuationAndCfgV19AtomicCoverageTests",
        'self.assertLessEqual(sum(c["range"][1] - c["range"][0] for c in continuation_claims), 94)',
        'self.assertEqual(94, sum(c["range"][1] - c["range"][0] for c in continuation_claims))',
    ),
    (
        "BootContinuationAndCfgV19AtomicCoverageTests",
        'self.assertGreaterEqual(len(target_claims), 14)',
        'self.assertEqual(14, len(target_claims))',
    ),
    (
        "BootContinuationAndCfgV19AtomicCoverageTests",
        'self.assertLessEqual(sum(c["range"][1] - c["range"][0] for c in target_claims), 1_660)',
        'self.assertEqual(1_660, sum(c["range"][1] - c["range"][0] for c in target_claims))',
    ),
    (
        "UnboundChapterScriptTailCoverageTests",
        'self.assertGreaterEqual(len(claims), 3)',
        'self.assertEqual(3, len(claims))',
    ),
    (
        "UnboundChapterScriptTailCoverageTests",
        'self.assertLessEqual(sum(c["range"][1] - c["range"][0] for c in claims), 3_186)',
        'self.assertEqual(3_186, sum(c["range"][1] - c["range"][0] for c in claims))',
    ),
    (
        "ChapterScriptConsumerRootsCoverageTests",
        'self.assertGreaterEqual(len(claims), 2)',
        'self.assertEqual(2, len(claims))',
    ),
    (
        "ChapterScriptConsumerRootsCoverageTests",
        'self.assertLessEqual(sum(c["range"][1] - c["range"][0] for c in claims), 16_175)',
        'self.assertEqual(16_175, sum(c["range"][1] - c["range"][0] for c in claims))',
    ),
    (
        "BattleConditionResultTextCoverageTests",
        'self.assertGreaterEqual(len(claims), 219)',
        'self.assertEqual(219, len(claims))',
    ),
    (
        "BattleConditionResultTextCoverageTests",
        'self.assertLessEqual(sum(row["range"][1] - row["range"][0] for row in claims), 3_961)',
        'self.assertEqual(3_961, sum(row["range"][1] - row["range"][0] for row in claims))',
    ),
    (
        "AlternateDialogueTableCoverageTests",
        'self.assertGreaterEqual(len(claims), 161)',
        'self.assertEqual(161, len(claims))',
    ),
    (
        "AlternateDialogueTableCoverageTests",
        'self.assertLessEqual(sum(row["range"][1] - row["range"][0] for row in claims), 3_200)',
        'self.assertEqual(3_200, sum(row["range"][1] - row["range"][0] for row in claims))',
    ),
    (
        "StoryStateCallbackCfgCoverageTests",
        'self.assertGreaterEqual(len(claims), 13)',
        'self.assertEqual(13, len(claims))',
    ),
    (
        "StoryStateCallbackCfgCoverageTests",
        'self.assertLessEqual(sum(row["range"][1] - row["range"][0] for row in claims), 702)',
        'self.assertEqual(702, sum(row["range"][1] - row["range"][0] for row in claims))',
    ),
    (
        "StoryStateEntryC4ccCoverageTests",
        'self.assertGreaterEqual(len(claims), 2)',
        'self.assertEqual(2, len(claims))',
    ),
    (
        "StoryStateEntryC4ccCoverageTests",
        'self.assertLessEqual(sum(row["range"][1] - row["range"][0] for row in claims), 220)',
        'self.assertEqual(220, sum(row["range"][1] - row["range"][0] for row in claims))',
    ),
    (
        "CfgConsumedLiteralBatchCoverageTests",
        'self.assertGreaterEqual(len(row["non_claims"]), 4)',
        'self.assertEqual(4, len(row["non_claims"]))',
    ),
]

# §A —— 仍然写死的全局量：只增的累计量改下界、只缩的 unknown 量改上界。
GLOBAL_QUANTITY_BOUNDS: list[tuple[str, str, str]] = [
    # --- 投影族：接收者是 _cfg_code_aggregate 的返回值 ---
    (
        "V17V18HelperCfgQuickProjectionTests",
        """        self.assertEqual(
            (165_572, 166_560, 3_969, 45),
            tuple(stable[key] for key in (
                "cfg_reachable_thumb_code_bytes", "cfg_promoted_unknown_bytes",
                "cfg_primary_claim_count", "cfg_code_claim_kind_count",
            )),
        )""",
        """        self.assertGreaterEqual(stable["cfg_reachable_thumb_code_bytes"], 165_572)
        self.assertGreaterEqual(stable["cfg_promoted_unknown_bytes"], 166_560)
        self.assertGreaterEqual(stable["cfg_primary_claim_count"], 3_969)
        self.assertGreaterEqual(stable["cfg_code_claim_kind_count"], 45)""",
    ),
    (
        "V17V18HelperCfgQuickProjectionTests",
        'self.assertEqual(166_770, projected["cfg_reachable_thumb_code_bytes"])',
        'self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 166_770)',
    ),
    (
        "V17V18HelperCfgQuickProjectionTests",
        'self.assertEqual(167_758, projected["cfg_promoted_unknown_bytes"])',
        'self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 167_758)',
    ),
    (
        "V17V18HelperCfgQuickProjectionTests",
        'self.assertEqual(3_978, projected["cfg_primary_claim_count"])',
        'self.assertGreaterEqual(projected["cfg_primary_claim_count"], 3_978)',
    ),
    (
        "V17V18HelperCfgQuickProjectionTests",
        'self.assertEqual(46, projected["cfg_code_claim_kind_count"])',
        'self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 46)',
    ),
    (
        "PrebattleMenuControllerCfgQuickProjectionTests",
        'self.assertEqual(168_334, projected["cfg_reachable_thumb_code_bytes"])',
        'self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 168_334)',
    ),
    (
        "PrebattleMenuControllerCfgQuickProjectionTests",
        'self.assertEqual(169_322, projected["cfg_promoted_unknown_bytes"])',
        'self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 169_322)',
    ),
    (
        "PrebattleMenuControllerCfgQuickProjectionTests",
        'self.assertEqual(4_005, projected["cfg_primary_claim_count"])',
        'self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_005)',
    ),
    (
        "PrebattleMenuControllerCfgQuickProjectionTests",
        'self.assertEqual(47, projected["cfg_code_claim_kind_count"])',
        'self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 47)',
    ),
    (
        "StoryCallbackDependencyQuickProjectionTests",
        'self.assertEqual(169_990, projected["cfg_reachable_thumb_code_bytes"])',
        'self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 169_990)',
    ),
    (
        "StoryCallbackDependencyQuickProjectionTests",
        'self.assertEqual(170_978, projected["cfg_promoted_unknown_bytes"])',
        'self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 170_978)',
    ),
    (
        "StoryCallbackDependencyQuickProjectionTests",
        'self.assertEqual(4_023, projected["cfg_primary_claim_count"])',
        'self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_023)',
    ),
    (
        "StoryCallbackDependencyQuickProjectionTests",
        'self.assertEqual(48, projected["cfg_code_claim_kind_count"])',
        'self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 48)',
    ),
    (
        "StoryNextDependencyCfgQuickProjectionTests",
        'self.assertEqual(171_830, projected["cfg_reachable_thumb_code_bytes"])',
        'self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 171_830)',
    ),
    (
        "StoryNextDependencyCfgQuickProjectionTests",
        'self.assertEqual(172_818, projected["cfg_promoted_unknown_bytes"])',
        'self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 172_818)',
    ),
    (
        "StoryNextDependencyCfgQuickProjectionTests",
        'self.assertEqual(4_044, projected["cfg_primary_claim_count"])',
        'self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_044)',
    ),
    (
        "StoryNextDependencyCfgQuickProjectionTests",
        'self.assertEqual(50, projected["cfg_code_claim_kind_count"])',
        'self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 50)',
    ),
    (
        "BootRegisterInitDependencyCfgQuickProjectionTests",
        'self.assertEqual(172_148, projected["cfg_reachable_thumb_code_bytes"])',
        'self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 172_148)',
    ),
    (
        "BootRegisterInitDependencyCfgQuickProjectionTests",
        'self.assertEqual(173_136, projected["cfg_promoted_unknown_bytes"])',
        'self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 173_136)',
    ),
    (
        "BootRegisterInitDependencyCfgQuickProjectionTests",
        'self.assertEqual(4_048, projected["cfg_primary_claim_count"])',
        'self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_048)',
    ),
    (
        "BootRegisterInitDependencyCfgQuickProjectionTests",
        'self.assertEqual(51, projected["cfg_code_claim_kind_count"])',
        'self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 51)',
    ),
    # --- atomize_claims 派生的全局总量 ---
    (
        "CfgProvenRootsV17CoverageTests",
        "self.assertEqual(6_153_836, classified)",
        "self.assertGreaterEqual(classified, 6_153_836)",
    ),
    (
        "CfgProvenRootsV17CoverageTests",
        "self.assertEqual(137_620, len(rom) - classified)",
        "self.assertLessEqual(len(rom) - classified, 137_620)",
    ),
    (
        "CutsceneObjPaletteDefinitionAlignmentGapCoverageTests",
        "self.assertEqual(6_106_920, classified)",
        "self.assertGreaterEqual(classified, 6_106_920)",
    ),
    (
        "CutsceneObjPaletteDefinitionAlignmentGapCoverageTests",
        "self.assertEqual(184_536, unknown)",
        "self.assertLessEqual(unknown, 184_536)",
    ),
    (
        "CutsceneObjPaletteDefinitionAlignmentGapCoverageTests",
        "self.assertEqual(14_165, len(claims))",
        "self.assertGreaterEqual(len(claims), 14_165)",
    ),
    (
        "CutsceneObjPaletteDefinitionAlignmentGapCoverageTests",
        "self.assertEqual(16_257, len(segments))",
        "self.assertGreaterEqual(len(segments), 16_257)",
    ),
    (
        "TileBgLz77PaletteAlignmentGapCoverageTests",
        "self.assertEqual(6_127_684, classified)",
        "self.assertGreaterEqual(classified, 6_127_684)",
    ),
    (
        "TileBgLz77PaletteAlignmentGapCoverageTests",
        "self.assertEqual(163_772, len(self._rom()) - classified)",
        "self.assertLessEqual(len(self._rom()) - classified, 163_772)",
    ),
    (
        "TileBgLz77PaletteAlignmentGapCoverageTests",
        "self.assertEqual(14_720, len(baseline) + len(claims))",
        "self.assertGreaterEqual(len(baseline) + len(claims), 14_720)",
    ),
    (
        "TileBgLz77PaletteAlignmentGapCoverageTests",
        "self.assertEqual(16_693, len(segments))",
        "self.assertGreaterEqual(len(segments), 16_693)",
    ),
    (
        "BootThumbCodeLiteralAlignmentGapCoverageTests",
        "self.assertEqual(6_127_684, classified)",
        "self.assertGreaterEqual(classified, 6_127_684)",
    ),
    (
        "BootThumbCodeLiteralAlignmentGapCoverageTests",
        "self.assertEqual(163_772, len(self._rom()) - classified)",
        "self.assertLessEqual(len(self._rom()) - classified, 163_772)",
    ),
    (
        "BootThumbCodeLiteralAlignmentGapCoverageTests",
        "self.assertEqual(14_720, len(baseline) + len(claims))",
        "self.assertGreaterEqual(len(baseline) + len(claims), 14_720)",
    ),
    (
        "BootThumbCodeLiteralAlignmentGapCoverageTests",
        "self.assertEqual(16_693, len(segments))",
        "self.assertGreaterEqual(len(segments), 16_693)",
    ),
]

# §B —— 全局分母摘要：不单调（新增 staged kind 就变），必须与活注册表对拍。
GLOBAL_DIGEST_DERIVATIONS: list[tuple[str, str, str]] = [
    (
        "RomByteCoverageAuditTests",
        """        self.assertEqual(
            "ad155f92858a1cbd167b807d400769bc7b5c7bad5190f838bf3605cd6467019c",
            summary["cfg_code_claim_kind_denominator_sha256"],
        )""",
        """        self.assertEqual(
            _expected_cfg_registry_sha256(manifest["claims"]),
            summary["cfg_code_claim_kind_denominator_sha256"],
        )""",
    ),
    (
        "CfgProvenRootsV15CoverageTests",
        """        self.assertEqual(
            "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f",
            summary["cfg_code_claim_kind_denominator_sha256"],
        )""",
        """        self.assertEqual(
            _expected_cfg_registry_sha256(manifest["claims"]),
            summary["cfg_code_claim_kind_denominator_sha256"],
        )""",
    ),
]

REPLACEMENTS = REVERSE_BATCH_DELTAS + GLOBAL_QUANTITY_BOUNDS + GLOBAL_DIGEST_DERIVATIONS


def class_blocks(source: str) -> list[tuple[str, int, int]]:
    """返回 [(类名, 起始行号, 结束行号)]，行号为 1-based、闭区间。"""
    matches = list(re.finditer(r"^class (\w+)", source, re.M))
    lines = source.splitlines()
    blocks: list[tuple[str, int, int]] = []
    for index, match in enumerate(matches):
        start = source[: match.start()].count("\n") + 1
        end = (
            source[: matches[index + 1].start()].count("\n")
            if index + 1 < len(matches)
            else len(lines)
        )
        blocks.append((match.group(1), start, end))
    return blocks


def apply_replacements(source: str) -> tuple[str, list[str]]:
    """在每个类的块内做替换；每条必须恰好命中一次。"""
    blocks = class_blocks(source)
    problems: list[str] = []
    changed = 0

    for class_name, old, new in REPLACEMENTS:
        entry = next((b for b in blocks if b[0] == class_name), None)
        if entry is None:
            problems.append(f"{class_name}: 类不存在")
            continue
        _, start, end = entry
        lines = source.splitlines(keepends=True)
        window = "".join(lines[start - 1 : end])
        hits = window.count(old)
        if hits == 0:
            if new in window:
                continue  # 幂等：已经改过了
            problems.append(f"{class_name}: 旧文本未命中 -> {old[:90]!r}")
            continue
        if hits > 1:
            problems.append(f"{class_name}: 旧文本命中 {hits} 次 -> {old[:90]!r}")
            continue
        window = window.replace(old, new, 1)
        source = source[: sum(len(line) for line in lines[: start - 1])] + window + source[
            sum(len(line) for line in lines[:end]) :
        ]
        changed += 1

    return source, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO))
    parser.add_argument("--target", default=None)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    target = pathlib.Path(args.target) if args.target else TARGET
    source = target.read_text(encoding="utf-8")
    updated, problems = apply_replacements(source)

    if problems:
        for problem in problems:
            print(f"PROBLEM: {problem}", file=sys.stderr)
        print(f"失败关闭：{len(problems)} 条替换未落地", file=sys.stderr)
        return 2

    if updated == source:
        print("幂等：没有任何改动")
        return 0

    if args.dry_run:
        print(f"--dry-run：将落地 {len(REPLACEMENTS)} 条替换（未写盘）")
        return 0

    target.write_text(updated, encoding="utf-8")
    print(f"已写入 {target}：{len(REPLACEMENTS)} 条替换")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
