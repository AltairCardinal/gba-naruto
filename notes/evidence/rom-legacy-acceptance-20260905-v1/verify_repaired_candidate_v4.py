"""Run the independent archive verifier on the repaired frozen candidate."""
import json
from pathlib import Path
import sys

ROOT=Path('/Users/altair/github/gba-naruto-reverse')
sys.path.insert(0,str(ROOT))
from tools.verify_legacy_artifact_acceptance import verify_archive

RUN=Path(__file__).parent
candidate=RUN/'candidate-v4'
report=verify_archive((candidate/'catalog.json').read_bytes(),(candidate/'snapshot.json.gz').read_bytes())
with (RUN/'candidate-verify-v4.json').open('x') as stream:
    json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({k:v for k,v in report.items() if k!='authorizations'},sort_keys=True))
