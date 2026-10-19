import subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parent
with (r/'refresh.log').open('x') as log:
    p=subprocess.run([sys.executable,str(r/'refresh.py')],stdout=log,stderr=subprocess.STDOUT,check=False)
raise SystemExit(p.returncode)
