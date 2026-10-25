#!/bin/bash
# Y1: list the biggest stack frames of the remake ROM (GCC .su files).
set -u
cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel || exit 2
cat build/*.su | awk -F'\t' '{print $2"\t"$1}' | sort -rn | head -"${1:-35}"
