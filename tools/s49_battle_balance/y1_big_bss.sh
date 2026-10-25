#!/bin/bash
# Y1: list the biggest bss/data symbols of the remake ELF (with addresses).
set -u
source /opt/devkitpro/devkitarm.sh
ELF=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/butano-sequel.elf
arm-none-eabi-nm -S "$ELF" 2>/dev/null | \
  awk '$3 == "b" || $3 == "B" { print $2, $1, $4 }' | \
  sort -rn | head -"${1:-25}"
