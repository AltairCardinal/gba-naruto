"""Offline typed replay of four map41 resource-content A/B cells."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
CONTRACT='tools/data/maps-partial-bank-contract-v1.json'
SCRIPT='tools/verify_maps_partial_bank.py'
BANK='sequel/content/maps/bank.json'


def verify_partial_bank(root):raise NotImplementedError('maps partial bank contract not implemented')


def proof_binding(root,result):raise NotImplementedError('maps proof binding not implemented')


if __name__=='__main__':verify_partial_bank(ROOT)
