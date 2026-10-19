#ifndef KONOHA_BATTLE_PRESENTATION_CONTENT_H
#define KONOHA_BATTLE_PRESENTATION_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint16_t no_presentation_index = 0xFFFF;
inline constexpr std::uint8_t
        no_battle_presentation_portrait_motion = 0xFF;

enum class battle_presentation_script_opcode : std::uint8_t
{
    end = 0x00,
    render_encoded_text = 0x01,
    show_portrait = 0x02,
    hide_portrait = 0x03,
    update_portrait = 0x04,
    goto_address = 0x07,
    select_message_speaker = 0x08,
    wait_frames = 0x0F,
    set_portrait_focus = 0x11,
    initialize_portrait_pair = 0x12,
    animate_portrait = 0x17,
    render_parameterized_encoded_text = 0x20,
    selector_dispatch = 0x32,
    append_selector = 0x33,
    conditional_round_and_side = 0x34,
    conditional_unit_relationship = 0x35,
    conditional_unit_query = 0x36,
    set_script_flag = 0x37,
    conditional_script_flag = 0x38,
    conditional_battle_state = 0x39,
};

struct battle_presentation_selector_dispatch_case
{
    std::uint8_t selector = 0;
    std::uint16_t instruction_index =
            no_presentation_index;
};

struct battle_presentation_selector_instruction
{
    std::uint32_t source_address = 0;
    battle_presentation_script_opcode opcode =
            battle_presentation_script_opcode::end;
    std::array<std::uint8_t, 4> operands = {};
    std::uint16_t fallthrough_index =
            no_presentation_index;
    std::uint16_t branch_index =
            no_presentation_index;
    std::uint16_t dispatch_offset = 0;
    std::uint8_t dispatch_count = 0;
    std::uint16_t text_offset = 0;
    std::uint8_t text_length = 0;
};

struct battle_presentation_command
{
    std::uint32_t source_address = 0;
    battle_presentation_script_opcode opcode =
            battle_presentation_script_opcode::end;
    std::array<std::uint8_t, 4> operands = {};
    std::uint16_t text_offset = 0;
    std::uint8_t text_length = 0;
};

struct battle_presentation_case
{
    std::uint32_t source_address = 0;
    std::uint16_t command_offset = 0;
    std::uint8_t command_count = 0;
    std::uint8_t selector = 0;
};

struct battle_presentation_definition
{
    std::uint8_t battle_id = 0;
    std::uint16_t selector_root_instruction =
            no_presentation_index;
    std::uint16_t selector_instruction_offset = 0;
    std::uint8_t selector_instruction_count = 0;
    std::uint16_t case_offset = 0;
    std::uint8_t case_count = 0;
};

}

#endif
