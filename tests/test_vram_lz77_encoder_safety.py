from __future__ import annotations

import unittest


def _distances(record: bytes) -> list[int]:
    size = int.from_bytes(record[1:4], "little")
    cursor = 4
    produced = 0
    result = []
    while produced < size:
        flags = record[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if produced >= size:
                break
            if flags & (1 << bit):
                token = (record[cursor] << 8) | record[cursor + 1]
                cursor += 2
                produced += (token >> 12) + 3
                result.append((token & 0x0FFF) + 1)
            else:
                cursor += 1
                produced += 1
    return result


class VramLz77EncoderSafetyTests(unittest.TestCase):
    def test_all_independent_encoders_avoid_distance_one(self):
        from tools.verify_battle_effect_resource_writeback_audit import (
            _encode as battle_effect,
        )
        from tools.verify_bg_resource_writeback_audit import _encode as bg
        from tools.verify_direct_image_palette_relocation_audit import (
            _encode_lz77 as direct,
        )
        from tools.verify_menu_portrait_writeback_audit import (
            _encode_lz77 as menu,
        )
        from tools.verify_generic_sprite_bundle_relocation_audit import (
            _encode as generic_sprite,
        )
        from tools.verify_map_resource_writeback_audit import _encode as map_resource
        from tools.verify_residual_lz77_graphics_relocation_audit import (
            _encode_lz77 as residual_graphics,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            _encode_lz77 as residual_text,
        )
        from tools.verify_residual_wram_derived_tilemap_relocation_audit import (
            _encode_lz77 as residual_derived,
        )
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            _encode_lz77 as residual_wram,
        )
        from tools.verify_world_map_background_relocation_audit import (
            _encode as world_map,
        )

        for encoder in (
            battle_effect,
            bg,
            direct,
            generic_sprite,
            map_resource,
            menu,
            residual_graphics,
            residual_text,
            residual_derived,
            residual_wram,
            world_map,
        ):
            with self.subTest(encoder=encoder.__module__):
                self.assertNotIn(1, _distances(encoder(b"\x7f" * 64)))


if __name__ == "__main__":
    unittest.main()
