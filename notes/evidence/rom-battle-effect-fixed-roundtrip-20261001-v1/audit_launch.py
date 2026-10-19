import subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parent
with (r/'audit-cli.json').open('x') as out, (r/'audit-cli.stderr.txt').open('x') as err:
    p=subprocess.run([sys.executable,'tools/audit_battle_effect_fixed_roundtrip.py','--root','.', '--run',str(r)],stdout=out,stderr=err,check=False)
raise SystemExit(p.returncode)
