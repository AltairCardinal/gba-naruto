#!/usr/bin/env python3
"""Publish four frozen packets using the existing atomic no-replace primitives."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import rom_small_cfg_dependency_packets as packets
from tools import verify_rom_small_cfg_dependency_batch as verifier
from tools.export_rom_cfg_proven_roots_v21 import _publish_exclusive_at, _write_file_at


def output_parent(root, output):
    output = Path(output)
    if '..' in output.parts:
        raise ValueError('unsafe output path')
    destination = output if output.is_absolute() else root/output
    destination = destination.absolute()
    allowed = root/'build/experiments/active'
    if not destination.is_relative_to(allowed) or destination == allowed:
        raise ValueError('candidate output must be in an initialized experiment')
    relative = destination.relative_to(root)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        try:
            os.stat(destination.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(destination)
        return destination, fd
    except Exception:
        os.close(fd)
        raise


def export_batch(root, output):
    root = Path(root).absolute()
    target, parent_fd = output_parent(root, output)
    stage_fd = None
    stage_name = '.small-cfg-stage-'+secrets.token_hex(12)
    try:
        contract = verifier.load_contract(root)
        payloads = {key: packets.build_candidate(root, key) for key in packets.PACKETS}
        raw = verifier.canonical(verifier.aggregate(payloads, contract))
        os.mkdir(stage_name, 0o700, dir_fd=parent_fd)
        stage_fd = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=parent_fd)
        identity = os.fstat(stage_fd)
        _write_file_at(stage_fd, verifier.PAYLOAD, raw)
        _write_file_at(stage_fd, 'manifest.json', verifier.canonical(
            verifier.intended_manifest(root, raw)))
        stage = target.parent/stage_name
        report = verifier.verify_artifact(root, stage, allow_candidate=True)
        if not report['verified']:
            raise ValueError(f'independent verifier rejected candidate: {report}')
        _write_file_at(stage_fd, '.accepted-manifest', verifier.canonical(
            verifier.intended_manifest(root, raw, report)))
        os.replace('.accepted-manifest', 'manifest.json', src_dir_fd=stage_fd,
                   dst_dir_fd=stage_fd)
        os.fsync(stage_fd)
        final_report = verifier.verify_artifact(root, stage)
        if final_report != report:
            raise ValueError('accepted replay changed')
        named = os.stat(stage_name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('verified staging directory replaced')
        _publish_exclusive_at(parent_fd, stage_name, target.name)
        named = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError('published directory differs from verified staging')
        if verifier.verify_artifact(root, target) != report:
            raise ValueError('published replay changed')
        return target
    finally:
        # Preserve failed owned staging; never remove a replaceable pathname.
        if stage_fd is not None:
            os.close(stage_fd)
        os.close(parent_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export_batch(args.root, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
