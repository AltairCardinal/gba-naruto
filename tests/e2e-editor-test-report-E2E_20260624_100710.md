# Editor E2E Test Report

**RUN_ID:** E2E_20260624_100710
**Date:** 2026-06-24 10:07:13

## Summary

- Total: 55
- Passed: 52
- Failed: 3

## Results

| Test | OK | Detail |
|------|----|--------|
| auth.me | ✓ | user=kibox |
| users.list | ✓ | count=4 |
| dialogues.create | ✓ | id=3 |
| dialogues.read | ✓ |  |
| dialogues.update | ✓ |  |
| dialogues.list | ✓ |  |
| dialogues.delete | ✓ |  |
| units.create | ✓ | id=3 char_id=6831 |
| units.read | ✓ |  |
| units.update | ✓ |  |
| units.list | ✓ |  |
| units.delete | ✓ |  |
| skills.create | ✓ | id=1 |
| skills.read | ✓ |  |
| skills.update | ✓ |  |
| skills.list | ✓ |  |
| skills.delete | ✓ |  |
| story_beats.create | ✓ | id=1 |
| story_beats.read | ✓ |  |
| story_beats.update | ✓ |  |
| story_beats.list | ✓ |  |
| story_beats.delete | ✓ |  |
| audio.create | ✓ | id=1 |
| audio.read | ✓ |  |
| audio.update | ✓ |  |
| audio.list | ✓ |  |
| audio.delete | ✓ |  |
| battle_configs.create | ✓ | id=1 |
| battle_configs.read | ✓ |  |
| battle_configs.update | ✓ |  |
| battle_configs.list | ✓ |  |
| maps.update_via_put | ✓ | map_id=map_1 |
| maps.read | ✓ |  |
| maps.list | ✓ |  |
| chapters.create | ✓ | chapter_number=99 |
| chapters.read | ✓ |  |
| chapters.list | ✓ | count=1 |
| chapters.update | ✓ |  |
| characters.create | ✓ | id=3 char_id=6831 |
| characters.read | ✗ |  |
| characters.update | ✗ |  |
| characters.list | ✓ |  |
| characters.delete | ✗ |  |
| unit_positions.create | ✓ | id=1 |
| unit_positions.list | ✓ |  |
| unit_positions.update | ✓ |  |
| unit_positions.delete | ✓ |  |
| battle_config.export | ✓ | patch_file=/root/gba-naruto/build/battle-config-1-20260624100711.json |
| build.trigger | ✓ | build_id=37cb8fa8-7f79-46e5-9e81-98146ef6247f |
| build.done | ✓ | build_id=37cb8fa8-7f79-46e5-9e81-98146ef6247f |
| rom.download | ✓ | size=6291456 |
| rom.file.exists | ✓ | path=/root/gba-naruto/build/users/kibox/37cb8fa8-7f79-46e5-9e81-98146ef6247f/naruto-sequel-dev.gba |
| rom.sha1.stable | ✓ | build=145f72d165f8 base=26f60795fa5e |
| rom.size.sane | ✓ | 6291456 bytes |
| cleanup.battle_config | ✓ |  |

## Build Artifacts

- build_id: `37cb8fa8-7f79-46e5-9e81-98146ef6247f`
- ROM path: `/root/gba-naruto/build/users/kibox/37cb8fa8-7f79-46e5-9e81-98146ef6247f/naruto-sequel-dev.gba`
- ROM SHA1: `145f72d165f8342bebad35104007432b07934b25`
- Base ROM SHA1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`
- ROM size: 6291456 bytes
- Battle config patch file: `/root/gba-naruto/build/battle-config-1-20260624100711.json`
