import subprocess,sys
from pathlib import Path
run=Path(__file__).parent
with (run/"audit-cli.json").open("w") as out,(run/"audit-cli.stderr.txt").open("w") as err:
 result=subprocess.run([sys.executable,"tools/audit_map_resource_fixed_roundtrip.py","--root",".","--run",str(run)],stdout=out,stderr=err,check=False)
raise SystemExit(result.returncode)
