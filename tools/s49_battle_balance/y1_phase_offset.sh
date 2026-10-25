#!/bin/bash
# Y1: find the byte offset of battle_scene_controller::_phase inside the
# controller object (from the DWARF), so the settlement chain can be poked.
set -u
source /opt/devkitpro/devkitarm.sh
ELF=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/butano-sequel.elf
arm-none-eabi-readelf --debug-dump=info "$ELF" 2>/dev/null | \
  awk '
    /DW_AT_name/ { name=$0 }
    /DW_TAG_member/ { member=1; mname=""; loc="" }
    /DW_AT_name/ && member { mname=$0 }
    /DW_AT_data_member_location/ && member { loc=$0 }
    /DW_AT_data_member_location/ && member {
      if (mname ~ /_phase/) { print mname; print loc; }
      member=0
    }
  ' | head -40
