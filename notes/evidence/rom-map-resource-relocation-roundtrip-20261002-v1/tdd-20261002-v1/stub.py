"""Frozen map relocation build/readback batches; no database or runtime."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
CONTRACT='tools/data/map-resource-relocation-roundtrip-contract-v1.json'
SCRIPT='tools/audit_map_resource_relocation_roundtrip.py'


def _build_cli(fixture,name,specs,*,with_layout=True):
    raise NotImplementedError('relocation CLI recipe not implemented')


def run_roundtrip(root,run):
    raise NotImplementedError('relocation build/readback batches not implemented')


if __name__=='__main__':run_roundtrip(ROOT,ROOT)
