"""Reuse the existing target-limited full-ROM BL inventory; no runtime closure."""
import hashlib
import json
from pathlib import Path
from tools.verify_rom_task_scheduler_core import _producer, _find_bl, _occurrences

rom = Path('rom/base.gba').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b'
report = _producer(rom)
extra_targets = [0x61d10, 0x61d7c, 0x61d8c, 0x7c5e8, 0x61e00, 0x9c574]
extra = {f'{target:06x}': {'thumb_bl_callsites': _find_bl(rom, target),
                         'exact_tagged_pointer_occurrences': _occurrences(rom, (0x08000001 + target).to_bytes(4, 'little')),
                         'computed_and_indirect_producers_closed': False}
         for target in extra_targets}
inputs = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [
    'tools/verify_rom_task_scheduler_core.py',
    'artifacts/rom-task-scheduler-core-v1/rom-task-scheduler-core.json',
    'artifacts/rom-task-scheduler-core-v1/manifest.json']}
print(json.dumps({'schema': 'coroutine-shared-scheduler-producer-preflight-v1',
                  'rom_sha256': hashlib.sha256(rom).hexdigest(), 'helper_inputs_observed': inputs,
                  'replayed_existing_scheduler_producer_contract': report,
                  'extra_target_limited_raw_inventory': extra,
                  'full_ram_writer_lifecycle_closed': False, 'promotion_bytes': 0}, sort_keys=True, indent=2))
