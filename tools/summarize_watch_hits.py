#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

HIT_RE = re.compile(
    r"hit=(?P<hit>\d+)\s+frame=(?P<frame>\d+)\s+cycle=(?P<cycle>\d+)\s+"
    r"pc=(?P<pc>[0-9A-F]{8})\s+lr=(?P<lr>[0-9A-F]{8})\s+sp=(?P<sp>[0-9A-F]{8})\s+"
    r"addr=(?P<addr>[0-9A-F]{8})\s+old=(?P<old>-?\d+)\s+new=(?P<new>-?\d+)\s+"
    r"type=(?P<access_type>-?\d+)\s+width=(?P<width>-?\d+)"
)


def parse_hits(path: Path) -> list[dict[str, int | str]]:
    hits: list[dict[str, int | str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HIT_RE.search(line)
        if not match:
            continue
        item: dict[str, int | str] = {}
        for key, value in match.groupdict().items():
            if key in {"pc", "lr", "sp", "addr"}:
                item[key] = value
            else:
                item[key] = int(value)
        hits.append(item)
    return hits


def render_markdown(
    title: str, log_path: Path, hits: list[dict[str, int | str]]
) -> str:
    pcs = Counter(hit["pc"] for hit in hits)
    lrs = Counter(hit["lr"] for hit in hits)
    addrs = Counter(hit["addr"] for hit in hits)
    widths = Counter(int(hit["width"]) for hit in hits)

    lines = [
        f"# {title}",
        "",
        f"- source log: `{log_path.name}`",
        f"- total hits: `{len(hits)}`",
    ]
    if not hits:
        lines.append("- result: `no hits parsed`")
        lines.append("")
        return "\n".join(lines) + "\n"

    first = hits[0]
    last = hits[-1]
    lines.extend(
        [
            f"- first hit: frame `{first['frame']}`, pc `0x{first['pc']}`, addr `0x{first['addr']}`",
            f"- last hit: frame `{last['frame']}`, pc `0x{last['pc']}`, addr `0x{last['addr']}`",
            "",
            "## Top PCs",
            "",
        ]
    )
    for pc, count in pcs.most_common(10):
        lines.append(f"- `0x{pc}`: `{count}` hits")

    lines.extend(["", "## Top LRs", ""])
    for lr, count in lrs.most_common(10):
        lines.append(f"- `0x{lr}`: `{count}` hits")

    lines.extend(["", "## Top Addresses", ""])
    for addr, count in addrs.most_common(10):
        lines.append(f"- `0x{addr}`: `{count}` hits")

    lines.extend(["", "## Widths", ""])
    for width, count in widths.most_common():
        lines.append(f"- `{width}` bytes: `{count}` hits")

    lines.extend(["", "## First 10 Hits", ""])
    for hit in hits[:10]:
        lines.append(
            "- frame `{frame}` pc `0x{pc}` lr `0x{lr}` addr `0x{addr}` width `{width}` old `{old}` new `{new}`".format(
                **hit
            )
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize mGBA watchpoint logs.")
    parser.add_argument("log", help="Path to the raw watchpoint log.")
    parser.add_argument("--title", default="Watchpoint Summary")
    parser.add_argument("--output", required=True, help="Output markdown path.")
    args = parser.parse_args()

    log_path = Path(args.log)
    hits = parse_hits(log_path)
    output_path = Path(args.output)
    output_path.write_text(
        render_markdown(args.title, log_path, hits),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
