# Editor E2E Test Report

**RUN_ID:** E2E_20260624_100133
**Date:** 2026-06-24 10:01:36

## Summary

- Total: 48
- Passed: 44
- Failed: 4

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
| units.create | ✓ | id=2 char_id=6494 |
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
| maps.create_via_put | ✗ | status=404 body={"detail":"Map 1 not found"} |
| chapters.create | ✗ | status=422 body={"detail":[{"type":"missing","loc":["body","chapter_number"],"msg":"Field required","input":{"chapter_num":99,"title":"E2E_20260624_100133-chapter","episode_id":1}}]} |
| chapters.read | ✓ | status=200 body={"id":1,"chapter_number":1,"title":"Chapter 1","title_ja":"第1章","title_zh":"第1章","tilemap_entry_ptr":"0x53D914","start_m |
| chapters.list | ✗ | endpoint ok |
| characters.create | ✗ | status=500 body=Internal Server Error |
| unit_positions.create | ✓ | id=1 |
| unit_positions.list | ✓ |  |
| unit_positions.update | ✓ |  |
| unit_positions.delete | ✓ |  |
| battle_config.export | ✓ | patch_file=/root/gba-naruto/build/battle-config-1-20260624100134.json |
| build.trigger | ✓ | build_id=bb00b0bd-e187-4fc2-a845-e5439b763004 |
| build.done | ✓ | build_id=bb00b0bd-e187-4fc2-a845-e5439b763004 |
| rom.download | ✓ | size=6291456 |
| rom.file.exists | ✓ | path=/root/gba-naruto/build/users/kibox/bb00b0bd-e187-4fc2-a845-e5439b763004/naruto-sequel-dev.gba |
| rom.sha1.stable | ✓ | build=145f72d165f8 base=26f60795fa5e |
| rom.size.sane | ✓ | 6291456 bytes |
| cleanup.battle_config | ✓ |  |

## Build Artifacts

- build_id: `bb00b0bd-e187-4fc2-a845-e5439b763004`
- ROM path: `/root/gba-naruto/build/users/kibox/bb00b0bd-e187-4fc2-a845-e5439b763004/naruto-sequel-dev.gba`
- ROM SHA1: `145f72d165f8342bebad35104007432b07934b25`
- Base ROM SHA1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`
- ROM size: 6291456 bytes
- Battle config patch file: `/root/gba-naruto/build/battle-config-1-20260624100134.json`
