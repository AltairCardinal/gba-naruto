"""Local manual actual-key investigation. Probe actions remain in commands log."""
from pathlib import Path
import os,sys,traceback
ROOT=Path(__file__).resolve().parents[2]
ns={'__file__':str(ROOT/'continuation/tools/play_campaign.py')}
exec((ROOT/'continuation/tools/play_campaign.py').read_text().split('q=Player();report=')[0],ns)
q=ns['Player']();out=ns['out']
try:
 q.boot();q.start(int(os.environ.get('NARUTO_REPLAY_FIRST','56')));q.shot('booted');print('READY_INPUT',out,flush=True)
 for line in sys.stdin:
  if line.strip()=='quit':break
  try:exec(line)
  except Exception:traceback.print_exc()
  print('READY_INPUT',flush=True)
finally:q.p.close()
