import subprocess,sys
from pathlib import Path
r=Path(__file__).parent
with (r/"audit-cli.json").open("w") as out,(r/"stderr.txt").open("w") as err:
 p=subprocess.run([sys.executable,"tools/audit_map_resource_relocation_roundtrip.py","--root",".","--run",str(r)],stdout=out,stderr=err,check=False)
raise SystemExit(p.returncode)
