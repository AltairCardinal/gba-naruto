# Editor E2E Test Report

**RUN_ID:** E2E_20260624_095516
**Date:** 2026-06-24 09:55:19

## Summary

- Total: 41
- Passed: 34
- Failed: 7

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
| units.create | ✓ | id=1 char_id=6117 |
| units.read | ✓ |  |
| units.update | ✓ |  |
| units.list | ✓ |  |
| units.delete | ✓ |  |
| skills.create | ✗ | no units available to attach skill |
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
| maps.create_via_put | ✗ | status=422 body={"detail":[{"type":"missing","loc":["body","tile_grid"],"msg":"Field required","input":{"name":"E2E_20260624_095516-map","tilemap_data":"{}","width":32,"height":32}}]} |
| chapters.create | ✗ | status=404 body={"detail":"Not Found"} |
| chapters.read | ✗ | status=404 body={"detail":"Not Found"} |
| chapters.list | ✗ | endpoint ok |
| characters.create | ✗ | status=500 body=Internal Server Error |
| unit_positions.create | ✗ | no units available |
| battle_config.export | ✓ | patch_file=/root/gba-naruto/build/battle-config-1-20260624095517.json |
| build.trigger | ✓ | build_id=96ed1f78-0576-4a41-a924-6d474934de4d |
| build.done | ✓ | build_id=96ed1f78-0576-4a41-a924-6d474934de4d |
| rom.download | ✓ | size=6291456 |
| rom.file.exists | ✓ | path=/root/gba-naruto/build/users/kibox/96ed1f78-0576-4a41-a924-6d474934de4d/naruto-sequel-dev.gba |
| rom.sha1.stable | ✓ | build=145f72d165f8 base=26f60795fa5e |
| rom.size.sane | ✓ | 6291456 bytes |
| cleanup.battle_config | ✓ |  |

## Build Artifacts

- build_id: `96ed1f78-0576-4a41-a924-6d474934de4d`
- ROM path: `/root/gba-naruto/build/users/kibox/96ed1f78-0576-4a41-a924-6d474934de4d/naruto-sequel-dev.gba`
- ROM SHA1: `145f72d165f8342bebad35104007432b07934b25`
- Base ROM SHA1: `26f60795fa5e63b4f0264b84e453beffd56b9f7d`
- ROM size: 6291456 bytes
- Battle config patch file: `/root/gba-naruto/build/battle-config-1-20260624095517.json`
