#!/usr/bin/env python3
"""Publish one frozen menu graphics-pointer runtime experiment in a managed run."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import verify_menu_portrait_pointer_ab as verifier
from tools.export_rom_small_cfg_dependency_batch import output_parent
from tools.export_rom_cfg_proven_roots_v21 import _publish_exclusive_at, _write_file_at


def export_artifact(root, source, output):
    root, source = Path(root).resolve(strict=True), Path(source).absolute()
    target, parent_fd = output_parent(root, output)
    stage_fd = None
    stage_name = '.menu-pointer-stage-' + secrets.token_hex(12)
    try:
        relative = target.relative_to(root / 'build/experiments/active')
        if len(relative.parts) < 3:
            raise ValueError('output lacks managed run')
        run = root / 'build/experiments/active' / relative.parts[0] / relative.parts[1]
        metadata = json.loads(verifier.read_regular(run / '.experiment.json'))
        if (metadata.get('status') != 'active' or metadata.get('task') != relative.parts[0]
                or metadata.get('run_id') != relative.parts[1]):
            raise ValueError('output run is not active and initialized')
        evidence = verifier.verify_source(root, source)
        objects = {name: verifier.read_regular(source / name) for name in verifier.RAW_FILES}
        data = {'raw.tar': verifier.pack_raw(objects), 'evidence.json': verifier.canonical(evidence),
                'baseline.png': objects['runtime/input-baseline/frame80.png'],
                'candidate.png': objects['runtime/input-candidate/frame80.png']}
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_fd = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        identity = os.fstat(stage_fd)
        for name, raw in data.items():
            _write_file_at(stage_fd, name, raw)
        _write_file_at(stage_fd, 'manifest.json', verifier.canonical(verifier.intended_manifest(root, data)))
        stage = target.parent / stage_name
        report = verifier.verify_artifact(root, stage, allow_candidate=True)
        if report['verified'] is not True:
            raise ValueError(f'independent menu pointer verifier rejected candidate: {report}')
        _write_file_at(stage_fd, '.accepted-manifest', verifier.canonical(verifier.intended_manifest(root, data, report)))
        os.replace('.accepted-manifest', 'manifest.json', src_dir_fd=stage_fd, dst_dir_fd=stage_fd)
        os.fsync(stage_fd)
        if verifier.verify_artifact(root, stage) != report:
            raise ValueError('accepted menu pointer replay changed')
        named = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('verified staging directory replaced')
        _publish_exclusive_at(parent_fd, stage_name, target.name)
        named = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('published directory differs from verified staging')
        if verifier.verify_artifact(root, target) != report:
            raise ValueError('published menu pointer replay changed')
        return target
    finally:
        # Preserve failed owned staging; never delete a replaceable path.
        if stage_fd is not None:
            os.close(stage_fd)
        os.close(parent_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    export_artifact(args.root, args.source_dir, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
