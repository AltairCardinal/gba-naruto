import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MapInteractionWiringTest(unittest.TestCase):
    def test_pickup_feedback_releases_before_scene_resource_changes(self):
        source = (ROOT / 'butano-sequel/game/src/battle_runtime_scene.cpp').read_text()
        loop = source[source.index('bn::vector<bn::sprite_ptr, 8> pickup_text_sprites;'):]
        for start, end in (
            ('if(state.phase == battle_scene_phase::complete)', 'return finish_scene('),
            ('if(battle_phase_uses_full_screen_result(', 'const bool dialogue_background_requested'),
            ('if(resource_transition.changed)', 'apply_visual_resource_transition('),
        ):
            section = loop[loop.index(start):]
            section = section[:section.index(end)]
            self.assertIn('pickup_text_sprites.clear();', section)
            self.assertIn('pickup_text_frames = 0;', section)

    def test_new_pickup_feedback_is_limited_to_the_map(self):
        source = (ROOT / 'butano-sequel/game/src/battle_runtime_scene.cpp').read_text()
        section = source[source.index('if(pickup.sequence != observed_pickup)'):]
        section = section[:section.index('text_generator.generate(')]
        self.assertIn('resource_coordinator.current()', section)
        self.assertIn('battle_visual_resource_cohort::map', section)
        self.assertIn('! battle_phase_uses_full_screen_result(state.phase)', section)

    def test_pickup_feedback_has_both_material_names(self):
        from tools.generate_butano_battle_identity_content import load_identity_content
        characters = load_identity_content(ROOT)['utf8_characters']
        for character in '钢石毒草':
            self.assertIn(character, characters)

    def test_scene_carries_pickups_through_campaign_commit(self):
        source = (ROOT / 'butano-sequel/game/src/battle_runtime_scene.cpp').read_text()
        self.assertIn('controller.inventory().materials', source)
        self.assertIn('&scene_progression.materials()', source)
        self.assertIn('config.initial_inventory', source)
        self.assertIn('object.type == 3', source)
        self.assertIn('object.position', source)

    def test_move_renderer_uses_original_animation_and_intermediate_pose(self):
        source = (ROOT / 'butano-sequel/game/src/battle_runtime_scene.cpp').read_text()
        self.assertIn('sample.sequence = movement_pose.sequence', source)
        self.assertIn('scene_pose.offset_x + movement_pose.offset_x', source)
        self.assertIn('scene_pose.offset_y + movement_pose.offset_y', source)
        self.assertIn('unit_sprites, false, &map_movement', source)
        catalog = json.loads((ROOT / 'butano-sequel/graphics/battle_unit_visual_catalog.json').read_text())
        for character in (1, 2, 3):
            sequences = catalog['entries'][character - 1]['visuals'][0]['animations']
            for direction in range(4):
                self.assertEqual(sequences[direction + 4]['total_duration'], 12)
                self.assertEqual(sequences[direction + 8]['total_duration'], 14)
                self.assertNotEqual(sequences[direction]['steps'], sequences[direction + 4]['steps'])

    def test_pickup_definitions_match_original_rom_and_frozen_checkpoint(self):
        from tools.inspect_mgba_savestate import load_gba_state
        rom = (ROOT / 'rom/base.gba').read_bytes()
        offset = 0x5461C4 + 14 * 0x1AAC + 0x8A4
        self.assertEqual(offset, 0x55DFD0)
        self.assertEqual(rom[offset:offset + 8], bytes.fromhex('0203040402040d05'))
        self.assertEqual(rom[offset + 8:offset + 64], bytes(56))
        state = load_gba_state(ROOT / 'artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9')
        for slot, x, y, material in ((1, 4, 4, 3), (2, 13, 5, 4)):
            raw = state.read_memory(0x02026604 + slot * 16, 16)
            self.assertEqual(raw[:8], bytes((3, x, y, 0, 2, 0, material, 0)))
