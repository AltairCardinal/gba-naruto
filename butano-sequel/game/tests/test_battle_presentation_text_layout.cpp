#include "konoha/battle_presentation_text_layout.h"
#include "konoha/generated_battle_presentation_content.h"

#include <cassert>

using namespace konoha;

int main()
{
    const battle_presentation_case* battle_41_case =
            battle_presentation_case_for(
                    *battle_presentation_definition_for(41),
                    1);
    assert(battle_41_case);
    const battle_presentation_command& first_text =
            battle_presentation_commands[
                    battle_41_case->command_offset + 2];
    battle_presentation_text_layout<64> layout;
    const battle_presentation_text_layout_result result =
            layout.build(
                    battle_presentation_text.data() +
                            first_text.text_offset,
                    first_text.text_length);
    assert(result ==
            battle_presentation_text_layout_result::ok);
    assert(layout.glyph_count() == 12);
    assert(layout.glyph(0)->code == 0x8167);
    assert(layout.glyph(0)->column == 0);
    assert(layout.glyph(0)->row == 0);
    assert(layout.glyph(11)->column == 11);

    const std::array<std::uint8_t, 7> two_lines = {
        0x81, 0x67, 0x0A, 0x81, 0x40, 0x81, 0x68,
    };
    assert(layout.build(
                   two_lines.data(),
                   two_lines.size()) ==
           battle_presentation_text_layout_result::ok);
    assert(layout.glyph_count() == 2);
    assert(layout.glyph(0)->row == 0);
    assert(layout.glyph(1)->row == 1);
    assert(layout.glyph(1)->column == 1);

    const std::array<std::uint8_t, 1> truncated = {
        0x81,
    };
    assert(layout.build(
                   truncated.data(),
                   truncated.size()) ==
           battle_presentation_text_layout_result::
                   truncated_code);
    assert(layout.glyph_count() == 0);
    return 0;
}
