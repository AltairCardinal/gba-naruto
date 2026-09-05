#!/usr/bin/env python3
"""Rebuild the fixed historical snapshot from exact local source identities."""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

try:
    from tools.legacy_artifact_acceptance_contract import BUNDLE_IDENTITIES
except ModuleNotFoundError:
    from legacy_artifact_acceptance_contract import BUNDLE_IDENTITIES


def rebuild(root: Path, catalog_raw: bytes, output: Path,
            *, expected_snapshot: dict | None = None) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    catalog = json.loads(catalog_raw)
    records = {}
    for path, expected in sorted(catalog['input_files'].items()):
        pure = PurePosixPath(path)
        if pure.is_absolute() or str(pure) != path or '..' in pure.parts or '\\' in path:
            raise ValueError('unsafe source path')
        source = root/path
        if any((root/Path(*pure.parts[:i])).is_symlink() for i in range(1, len(pure.parts)+1)):
            raise ValueError('symlink source path')
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError('nonregular source')
            value = stream.read()
        mode = '100755' if metadata.st_mode & 0o111 else '100644'
        actual = {'mode': mode, 'size': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
        if actual != expected:
            raise ValueError('source identity mismatch: '+path)
        records[path] = {'mode': mode, 'data_base64': base64.b64encode(value).decode('ascii')}
    raw = (json.dumps({'schema': 'legacy-artifact-snapshot-v1', 'files': records},
                      sort_keys=True, indent=2)+'\n').encode()
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if expected_snapshot is not None and (
        hashlib.sha256(compressed).hexdigest() != expected_snapshot.get('sha256') or
        len(compressed) != expected_snapshot.get('size')
    ):
        raise ValueError('frozen snapshot output identity mismatch')
    # Exclusive creation prevents overwriting evidence, including a raced output.
    with output.open('xb') as stream:
        stream.write(compressed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        catalog = args.catalog.read_bytes()
        pin = BUNDLE_IDENTITIES.get('catalog.json', {})
        if hashlib.sha256(catalog).hexdigest() != pin.get('sha256') or len(catalog) != pin.get('size'):
            raise ValueError('frozen catalog identity mismatch')
        snapshot_pin = BUNDLE_IDENTITIES.get('snapshot.json.gz')
        if (not isinstance(snapshot_pin, dict) or
            set(snapshot_pin) != {'mode', 'size', 'sha256'} or
            snapshot_pin['mode'] != '100644' or type(snapshot_pin['size']) is not int or
            snapshot_pin['size'] < 0 or not isinstance(snapshot_pin['sha256'], str) or
            len(snapshot_pin['sha256']) != 64 or
            any(c not in '0123456789abcdef' for c in snapshot_pin['sha256'])):
            raise ValueError('invalid frozen snapshot identity')
        rebuild(args.root, catalog, args.output,
                expected_snapshot=snapshot_pin)
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({'rebuilt': False, 'error': str(error)}, sort_keys=True))
        return 1
    value = args.output.read_bytes()
    print(json.dumps({'rebuilt': True, 'sha256': hashlib.sha256(value).hexdigest(), 'size': len(value)}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
