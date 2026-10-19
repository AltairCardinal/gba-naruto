"""Audit all frozen map resources through importer/build/readback."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.fixed_resource_roundtrip import build_cli as _build_cli
CONTRACT = 'tools/data/map-resource-fixed-roundtrip-contract-v1.json'
SCRIPT = 'tools/audit_map_resource_fixed_roundtrip.py'


def linked_domain(catalog, contents, replacements=None):
    raise NotImplementedError('independent linked map domain not implemented')


def run_roundtrip(root, run):
    raise NotImplementedError('map fixed roundtrip matrix not implemented')

if __name__ == "__main__":
    run_roundtrip(ROOT, ROOT)
