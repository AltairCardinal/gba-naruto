#!/usr/bin/env python3
"""Windows-portable twin of tools/prepare_rom_verifier_contracts.py.

The upstream tool is POSIX-only: it anchors every path component with
``os.O_DIRECTORY`` / ``os.O_NOFOLLOW`` descriptors and publishes files through
``os.link(..., src_dir_fd=, dst_dir_fd=)``.  None of that exists on Windows,
so on a fresh Windows checkout the command documented in
``docs/rom-verifier-checkout-setup.md`` dies with
``AttributeError: module 'os' has no attribute 'O_DIRECTORY'`` before it can
restore the three frozen verifier contracts.

This twin keeps the *same* contract and the *same* report schema:

  * the committed source inventory must be exactly the three files;
  * every source must match its pinned size + SHA-256;
  * every consumer verifier must match its pinned SHA-256;
  * an existing destination must be byte-identical, otherwise the run fails;
  * missing destinations are only created with ``--restore``;
  * after writing, every destination is re-hashed against the pinned digest.

Symlink handling is done with ``Path.is_symlink()`` per component instead of
``O_NOFOLLOW`` descriptors, which is the closest portable equivalent.

Usage (from the reverse-tree root):

    python tools/prepare_rom_verifier_contracts_win.py --restore
    python tools/prepare_rom_verifier_contracts_win.py
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

DATA = Path('tools/data/rom-verifier-contracts-v1')
# Identical table to tools/prepare_rom_verifier_contracts.py:
# (name, size, sha256, consumer file, consumer sha256)
INPUTS = (
    ('cgbsound', 11410, '12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a',
     'verify_rom_cgbsound_bounded_cfg.py', '6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961'),
    ('cgb-helper', 8694, 'e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7',
     'verify_rom_cgb_helper_bounded_cfg.py', 'd09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3'),
    ('mp2k-dispatcher', 7761, '936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d',
     'verify_rom_mp2k_dispatcher.py', '3b342efd7ec63cc38b3eb862a881ca7c562873375a9264fdb58fe5b752bd7397'),
)
MAX_READ = 1024 * 1024


def _reject_symlinks(path: Path) -> None:
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError(f'symlink input or destination: {component}')


def _read(path: Path) -> bytes:
    """Read a regular file without following symlinks on any component."""
    _reject_symlinks(path)
    if not path.exists():
        raise ValueError(f'missing input: {path}')
    if not path.is_file():
        raise ValueError(f'nonregular input: {path}')
    raw = path.read_bytes()
    if len(raw) > MAX_READ:
        raise ValueError(f'oversized input: {path}')
    return raw


def _create(root: Path, relative: Path, raw: bytes) -> None:
    """Publish one file atomically and never replace an existing file."""
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError(f'existing contract differs: {relative}')
    temporary = target.parent / ('.restore-' + os.urandom(8).hex())
    try:
        with open(temporary, 'xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # os.replace is atomic, but we already failed closed on any existing
        # destination, so this cannot clobber a conflicting file.
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare(root: Path, *, restore: bool = False) -> dict:
    root = Path(os.path.abspath(root))
    _reject_symlinks(root)
    data_dir = root / DATA
    _reject_symlinks(data_dir)
    if {p.name for p in data_dir.iterdir()} != {name + '.json' for name, *_ in INPUTS}:
        raise ValueError('frozen source inventory mismatch')
    pending = []
    existing = 0
    receipts = []
    for name, size, digest, consumer, consumer_digest in INPUTS:
        raw = _read(data_dir / (name + '.json'))
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('frozen source identity mismatch: ' + name)
        if hashlib.sha256(_read(root / 'tools' / consumer)).hexdigest() != consumer_digest:
            raise ValueError('frozen consumer identity mismatch: ' + consumer)
        relative = Path(f'build/experiments/active/{name}-contract/codex-r1-20260829/CONTRACT.json')
        target = root / relative
        _reject_symlinks(target)
        if target.exists():
            if _read(target) != raw:
                raise ValueError('existing contract differs: ' + str(relative))
            existing += 1
        else:
            if any(p.exists() and not p.is_dir() for p in target.parents):
                raise ValueError('non-directory destination ancestor: ' + str(relative))
            pending.append((relative, raw))
        receipts.append({'source': (DATA / (name + '.json')).as_posix(),
                         'destination': relative.as_posix(), 'sha256': digest, 'size': size,
                         'consumer_path': 'tools/' + consumer, 'consumer_sha256': consumer_digest})
    if pending and not restore:
        raise ValueError('missing restored contract; run with --restore')
    for relative, raw in pending:
        _create(root, relative, raw)
    for receipt in receipts:
        if hashlib.sha256(_read(root / receipt['destination'])).hexdigest() != receipt['sha256']:
            raise ValueError('restored contract identity mismatch')
    return {'schema': 'rom-verifier-contract-input-preparation-v1', 'verified': True,
            'created_count': len(pending), 'existing_count': existing, 'inputs': receipts,
            'verification_scope': 'input_bytes_only', 'semantic_verification_performed': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--restore', action='store_true',
                        help='create missing exact inputs; never replace existing files')
    args = parser.parse_args()
    try:
        report = prepare(args.root, restore=args.restore)
    except (OSError, ValueError) as error:
        print(json.dumps({'verified': False, 'error': str(error),
                          'verification_scope': 'input_bytes_only',
                          'semantic_verification_performed': False}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
