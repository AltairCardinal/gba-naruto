#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd -P)
project_dir=${1:-butano-sequel}

python3 "$repo_root/tools/butano/verify_setup.py" --root "$repo_root"
source "$repo_root/tools/butano/toolchain.lock"

case "$DEVKITARM_IMAGE" in
    devkitpro/devkitarm@sha256:*) ;;
    *) echo "Invalid DEVKITARM_IMAGE in toolchain.lock" >&2; exit 2 ;;
esac

if ! docker info >/dev/null 2>&1; then
    echo "Docker Desktop is not running; start it and retry." >&2
    exit 2
fi

# Butano does not encode the selected audio backend in object filenames.  If a
# project was first built with the null backend, changing Makefile to Maxmod can
# otherwise reuse a silent bn_audio_manager object indefinitely.
audio_dependency="$repo_root/$project_dir/build/bn_audio_manager.bn_noflto.d"
if [[ -f "$audio_dependency" ]] && \
        grep -Eq '^AUDIOBACKEND[[:space:]]*:=[[:space:]]*maxmod' "$repo_root/$project_dir/Makefile" && \
        ! grep -q 'bn_hw_audio_maxmod.h' "$audio_dependency"; then
    echo "Stale null audio backend detected; rebuilding the project from clean objects"
    docker run --rm \
        --user "$(id -u):$(id -g)" \
        --volume "$repo_root:/workspace" \
        --workdir "/workspace/$project_dir" \
        "$DEVKITARM_IMAGE" \
        make clean
fi

docker run --rm \
    --user "$(id -u):$(id -g)" \
    --volume "$repo_root:/workspace" \
    --workdir "/workspace/$project_dir" \
    "$DEVKITARM_IMAGE" \
    make -j2
