#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

FRAMES = [2160, 2340, 2520, 2700]


def u16(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def best_match(wram: bytes, vram: bytes) -> tuple[int, int]:
    best_score = -1
    best_off = -1
    for off in range(0, 0x4000 - len(wram) + 1, 2):
        score = sum(1 for a, b in zip(wram, vram[off : off + len(wram)]) if a == b)
        if score > best_score:
            best_score = score
            best_off = off
    return best_off, best_score


def diff_count(a: bytes, b: bytes, off: int, size: int = 0x100) -> int:
    return sum(x != y for x, y in zip(a[off : off + size], b[off : off + size]))


def main() -> int:
    out = Path("notes/dialogue-render-analysis.md")
    lines = [
        "# Dialogue Render Analysis",
        "",
        "This report correlates dialogue-frame `IO`, `WRAM`, and `VRAM` snapshots.",
        "",
    ]

    for frame in FRAMES:
        io_data = Path(f"notes/dialogue-io-{frame}-io.bin").read_bytes()
        wram = Path(f"notes/dialogue-{frame}-wram.bin").read_bytes()[0xA8C0:0xAA80]
        vram = Path(f"notes/dialogue-{frame}-vram.bin").read_bytes()
        dispcnt = u16(io_data, 0x00)
        bg0cnt = u16(io_data, 0x08)
        bg3cnt = u16(io_data, 0x0E)
        match_off, match_score = best_match(wram, vram)

        lines.extend(
            [
                f"## Frame `{frame}`",
                "",
                f"- `DISPCNT`: `0x{dispcnt:04X}`",
                f"- `BG0CNT`: `0x{bg0cnt:04X}`",
                f"- `BG3CNT`: `0x{bg3cnt:04X}`",
                f"- Best `WRAM 0xA8C0-0xAA7F` match in `VRAM`: `0x{match_off:04X}` with `{match_score}/{len(wram)}` identical bytes",
                "",
            ]
        )

    pairs = [(2160, 2340), (2340, 2520), (2520, 2700)]
    lines.append("## VRAM Diff Hotspots")
    lines.append("")
    for a, b in pairs:
        va = Path(f"notes/dialogue-{a}-vram.bin").read_bytes()
        vb = Path(f"notes/dialogue-{b}-vram.bin").read_bytes()
        lines.append(f"### `{a} -> {b}`")
        lines.append("")
        for off in [0x1C00, 0x2000, 0x2200, 0x2400, 0x2600]:
            lines.append(f"- `0x{off:04X}`: `{diff_count(va, vb, off)}` changed bytes")
        lines.append("")

    lines.extend(
        [
            "## Interpretation",
            "",
            "- The dialogue scene is `Mode 0` with `BG0` and `BG3` enabled.",
            "- `BG3CNT = 0x0300` means `BG3` uses `char base 0x0000` and `screen base 0x1800`.",
            "- The `WRAM 0xA8C0-0xAA7F` buffer best matches `VRAM` around `0x1B0A`, inside the `BG3` screen block region.",
            "- Page flips also heavily mutate `VRAM 0x2000+`, which is outside the `BG3` screen block and is therefore more likely glyph/tile graphics upload.",
            "",
            "Working model:",
            "",
            "1. Dialogue renderer builds `BG3` tilemap entries in `WRAM 0xA900+`.",
            "2. That tilemap is copied into `VRAM 0x1800+`.",
            "3. Character glyph tiles are uploaded or refreshed in `VRAM 0x2000+`.",
            "",
        ]
    )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
