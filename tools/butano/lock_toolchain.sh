#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd -P)
image_tag=devkitpro/devkitarm:20260610

docker info >/dev/null
docker pull "$image_tag"
repo_digest=$(docker image inspect --format '{{index .RepoDigests 0}}' "$image_tag")
case "$repo_digest" in
    devkitpro/devkitarm@sha256:*) ;;
    *) echo "Unable to resolve immutable devkitARM digest: $repo_digest" >&2; exit 2 ;;
esac

lock_file="$repo_root/tools/butano/toolchain.lock"
printf '%s\n' \
    'BUTANO_VERSION=21.7.1' \
    'BUTANO_COMMIT=112a1827c9c6d9e6041a7e93e66f04c4561a6415' \
    "DEVKITARM_IMAGE=$repo_digest" \
    > "$lock_file"
echo "Locked $repo_digest"
