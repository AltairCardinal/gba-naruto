import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for d in ["exp1-right-then-a", "exp2-full-chain", "exp3-control-a-only",
          "original-walk", "original-walk-states", "original-arrow-test",
          "original-idle-test"]:
    p = pathlib.Path("build/w22-d3") / d / "receipt.json"
    j = json.loads(p.read_text(encoding="utf-8"))
    steps = len(j["steps"])
    rom = j["rom"]["sha256"][:10]
    st = pathlib.Path(j["state"]["path"]).name
    print("%-24s steps=%3d  rom=%s  state=%s" % (d, steps, rom, st))
