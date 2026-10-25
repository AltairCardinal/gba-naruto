#!/bin/bash
# Y1: resolve an address in the remake ELF (host + ARM toolchain).
set -u
source /opt/devkitpro/devkitarm.sh
ELF=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/butano-sequel.elf
for a in "$@"; do
  echo "== $a =="
  arm-none-eabi-addr2line -f -C -i -e "$ELF" "$a"
done
