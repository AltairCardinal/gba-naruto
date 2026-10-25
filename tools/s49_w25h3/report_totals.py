"""Print the totals of a judgement-bench report.json (and per-frame field px).

Usage:
    python tools/s49_w25h3/report_totals.py build/w25-h3/report.json
"""

import json
import sys


def main():
    path = sys.argv[1]
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    print("top keys:", list(data.keys()))
    for key, value in data.items():
        if not isinstance(value, (dict, list)):
            print("  %-28s = %s" % (key, value))

    frames = data.get("frames") or data.get("per_frame") or []
    print("first frame keys:", list(frames[0].keys()) if frames else None)
    print("summary:", json.dumps(data.get("summary"), ensure_ascii=False)[:2000])
    total_field = 0
    total_all = 0
    print("%-16s %10s %10s" % ("frame", "field px", "all px"))
    for frame in frames:
        name = frame.get("name") or frame.get("step") or "?"
        field = frame.get("field_px")
        allpx = frame.get("all_px")
        if field is None:
            diff = frame.get("diff_px") or {}
            field = diff.get("field_px")
            allpx = diff.get("all_px")
        if field is None:
            diff = frame.get("diff") or {}
            field = diff.get("field_px")
            allpx = diff.get("all_px")
        print("%-16s %10s %10s" % (name, field, allpx))
        if isinstance(field, int):
            total_field += field
        if isinstance(allpx, int):
            total_all += allpx
    print("TOTAL field px =", total_field)
    print("TOTAL all px   =", total_all)


if __name__ == "__main__":
    main()
