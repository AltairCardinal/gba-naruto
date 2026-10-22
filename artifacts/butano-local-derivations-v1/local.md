# 本地派生产物补回收据（自动生成）

本文件由 `tools/restore_butano_local_derivations.py` 生成，不要手工编辑。

| 项 | 值 |
| --- | ---: |
| candidate_families | 26 |
| rederived | 16 |
| imported | 9 |
| already_identical | 1 |
| imported_prerequisite | 0 |
| diverged | 0 |
| unavailable | 0 |
| byte_identical | 26 |

## 逐族结果

| 族 | 模式 | producer | 与逆向树逐字节相同 | manifest sha |
| --- | --- | --- | --- | --- |
| `battle-effect-affine-runtime-v1` | rederived | `tools/export_battle_effect_affine_runtime.py` | ✅ | 73635d4a42be0648 |
| `battle-effect-sprite-animations-v1` | rederived | `tools/export_battle_effect_sprite_animations.py` | ✅ | 46403c9f070c2056 |
| `battle-presentation-glyphs-v1` | rederived | `tools/export_battle_presentation_glyphs.py` | ✅ | ecc44fde0d886b75 |
| `battle-visual-runtime-timelines-v1` | rederived | `tools/export_battle_visual_runtime_timelines.py` | ✅ | 7a3fd143f76a72f9 |
| `bg-resource-canvases-v1` | rederived | `tools/export_bg_resource_canvases.py` | ✅ | 27096c9129823cc7 |
| `bg-scene-selection-v1` | rederived | `tools/export_bg_scene_selection.py` | ✅ | 907e5bdd540b0a0a |
| `character-fbff-runtime-v1` | already-identical | — | ✅ | 280b1333b6a2fdf7 |
| `cutscene-obj-v1` | rederived | `tools/export_cutscene_obj_assets.py` | ✅ | b8e1341172decef9 |
| `e2e` | imported | — | ✅ | — |
| `runtime-checkpoints` | imported | — | ✅ | — |
| `scenario-41-audio-reference-v1` | imported | — | ✅ | — |
| `scenario-41-combat-reference-v1` | imported | — | ✅ | 8d4b6571bda88780 |
| `scenario-41-extended-reference-v1` | imported | — | ✅ | 68aa17ba7fff7dca |
| `scenario-41-prebattle-reference-v1` | imported | — | ✅ | 10dab63d827bf5da |
| `scenario-41-reference-v1` | imported | — | ✅ | acde9319697c246c |
| `scene-visual-packs-v1` | rederived | `tools/export_scene_visual_packs.py` | ✅ | 4bb40dff9ac2e564 |
| `sprite-definition-animations-v1` | rederived | `tools/export_sprite_definition_animations.py` | ✅ | e432003728c8ea28 |
| `sprite-definition-assets-v2` | rederived | `tools/export_sprite_definition_runtime_chain.py` | ✅ | ee36523b6a02edb4 |
| `story-scene-layer-bindings-v1` | rederived | `tools/export_story_scene_layer_bindings.py` | ✅ | 36d8803e6a7c0380 |
| `story-scene-timelines-v1` | rederived | `tools/export_story_scene_timelines.py` | ✅ | e847b88035dc7342 |
| `story-visual-layers-v1` | rederived | `tools/export_story_visual_layers.py` | ✅ | 556a7319ce57699e |
| `tile-assets-bg-v1` | imported | — | ✅ | ac72a25f412fbcc7 |
| `tile-assets-bg-v2` | rederived | `tools/export_tile_asset_bg_layers.py` | ✅ | 1df63cf6cf490791 |
| `world-map-backgrounds-v1` | rederived | `tools/export_world_map_backgrounds.py` | ✅ | b9b879841b7605af |
| `world-map-gpu-captures` | imported | — | ✅ | — |
| `world-map-runtime-v1` | rederived | `tools/export_world_map_runtime.py` | ✅ | 83a49eb6b8c65e0c |

## 边界声明

- `rederived` 是强结论：复刻侧自己的 producer 复现了逆向树的字节，**包括解码器**。
- `imported` 是弱结论：字节来自逆向树，按 reverse commit + 逐文件摘要钉死，**不是本地派生**。
- `diverged` 是硬失败：producer 声称同一 schema 却产出不同字节，路线图要求报错而不是「就近取一个」。
- 本回执的读数来自当轮工作树与逆向树，逆向树一变就变，不得写死。
