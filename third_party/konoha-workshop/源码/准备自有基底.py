from pathlib import Path
import sys,hashlib
from bps import apply
r=Path(__file__).resolve().parent
if len(sys.argv)!=2:raise SystemExit('用法: python 准备自有基底.py 你自己的原版.gba')
source=Path(sys.argv[1]).read_bytes()
if hashlib.sha256(source).hexdigest()!='1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b':raise SystemExit('原版不匹配，请核对00说明中的SHA256')
target=apply(source,(r/'基础引擎_v0.1.5.bps').read_bytes())
assert hashlib.sha256(target).hexdigest()=='52a33419f601b2f01b26ba13d9305b4a0aebde634a907e85577ba9c6c2165250'
for p,b in [(r/'originals/naruto_konoha_bearteam_simp.gba',source),(r/'build/naruto_role_swap_v0.1.5_EXPERIMENTAL.gba',target)]:
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists()and p.read_bytes()!=b:raise SystemExit('已有不同内容，保留原件: '+str(p))
 if not p.exists():p.write_bytes(b)
print('基底准备完成。原输入未改动。')
