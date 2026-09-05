#!/usr/bin/env python3
"""Check or restore three frozen inputs required by unchanged legacy verifiers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

DATA = Path('tools/data/rom-verifier-contracts-v1')
# These are original CONTRACT_SHA256 values, not new semantic attestations.
INPUTS = (
    ('cgbsound', 11410, '12171aa29cd29d14f26dc491e4b0a5bb8ddd3fe6d6daac9f73e732786194561a',
     'verify_rom_cgbsound_bounded_cfg.py', '6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961'),
    ('cgb-helper', 8694, 'e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7',
     'verify_rom_cgb_helper_bounded_cfg.py', 'd09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3'),
    ('mp2k-dispatcher', 7761, '936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d',
     'verify_rom_mp2k_dispatcher.py', '3b342efd7ec63cc38b3eb862a881ca7c562873375a9264fdb58fe5b752bd7397'),
)


def _reject_symlinks(path):
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError(f'symlink input or destination: {component}')


def _read(path):
    _reject_symlinks(path)
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        handle = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(handle, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError(f'nonregular input: {path}')
            raw = stream.read(1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    if len(raw) > 1024 * 1024:
        raise ValueError(f'oversized input: {path}')
    return raw


def _create(root, relative, raw):
    # Anchor each directory with a no-follow descriptor. Publishing by hard link
    # makes a complete file visible atomically and never replaces another file.
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        for part in relative.parts[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        candidate = '.restore-' + uuid.uuid4().hex
        handle = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=descriptor)
        temporary = candidate  # Cleanup ownership begins only after creation.
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, relative.name, src_dir_fd=descriptor,
                dst_dir_fd=descriptor, follow_symlinks=False)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=descriptor)
            except FileNotFoundError:
                pass
        os.close(descriptor)


def prepare(root, *, restore=False):
    root = Path(os.path.abspath(root))
    _reject_symlinks(root)
    _reject_symlinks(root / DATA)
    if {p.name for p in (root / DATA).iterdir()} != {name + '.json' for name, *_ in INPUTS}:
        raise ValueError('frozen source inventory mismatch')
    pending = []
    existing = 0
    receipts = []
    for name, size, digest, consumer, consumer_digest in INPUTS:
        raw = _read(root / DATA / (name + '.json'))
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
            # Detect non-directory ancestors during preflight, before any write.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--restore', action='store_true', help='create missing exact inputs; never replace existing files')
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
    raise SystemExit(main())
