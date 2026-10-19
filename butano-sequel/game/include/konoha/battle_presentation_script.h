#ifndef KONOHA_BATTLE_PRESENTATION_SCRIPT_H
#define KONOHA_BATTLE_PRESENTATION_SCRIPT_H

#include "konoha/generated_battle_presentation_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

enum class battle_presentation_selector_error : std::uint8_t
{
    none,
    invalid_definition,
    invalid_instruction,
    selector_overflow,
    unsupported_condition,
    execution_limit,
};

struct battle_presentation_script_flags
{
    std::array<std::uint32_t, 8> words = {};

    [[nodiscard]] constexpr bool test(
            std::uint8_t index) const
    {
        return (words[index / 32] &
                (std::uint32_t(1) << (index % 32))) != 0;
    }

    constexpr void set(
            std::uint8_t index, bool value)
    {
        const std::uint32_t mask =
                std::uint32_t(1) << (index % 32);
        if(value)
        {
            words[index / 32] |= mask;
        }
        else
        {
            words[index / 32] &= ~mask;
        }
    }
};

struct battle_presentation_selector_unit
{
    std::uint8_t character_id = 0;
    std::uint8_t side = 0;
    std::int8_t x = 0;
    std::int8_t y = 0;
    bool active = false;
};

struct battle_presentation_selector_context
{
    int round_index = 0;
    std::uint8_t side = 0;
    std::uint8_t dispatch_selector = 0;
    std::uint8_t battle_state = 0;
    std::array<battle_presentation_selector_unit, 13>
            units = {};
    std::uint8_t unit_count = 0;
    battle_presentation_script_flags* flags = nullptr;
};

struct battle_presentation_selector_result
{
    battle_presentation_selector_error error =
            battle_presentation_selector_error::none;
    std::array<std::uint8_t, 16> selectors = {};
    std::uint8_t count = 0;

    [[nodiscard]] constexpr bool success() const
    {
        return error ==
                battle_presentation_selector_error::none;
    }
};

class battle_presentation_selector
{
public:
    [[nodiscard]] battle_presentation_selector_result evaluate(
            const battle_presentation_definition& definition,
            const battle_presentation_selector_context& context) const
    {
        battle_presentation_selector_result result;
        if(definition.selector_instruction_count == 0)
        {
            if(definition.selector_root_instruction !=
                    no_presentation_index)
            {
                result.error =
                        battle_presentation_selector_error::
                                invalid_definition;
            }
            return result;
        }
        if(! _inside_definition(
                    definition,
                    definition.selector_root_instruction))
        {
            result.error =
                    battle_presentation_selector_error::
                            invalid_definition;
            return result;
        }

        std::uint16_t instruction_index =
                definition.selector_root_instruction;
        for(int step = 0; step < 4096; ++step)
        {
            if(! _inside_definition(
                        definition, instruction_index))
            {
                result.error =
                        battle_presentation_selector_error::
                                invalid_instruction;
                return result;
            }
            const battle_presentation_selector_instruction&
                    instruction =
                            battle_presentation_selector_instructions[
                                    instruction_index];
            switch(instruction.opcode)
            {
            case battle_presentation_script_opcode::end:
                return result;
            case battle_presentation_script_opcode::goto_address:
                instruction_index =
                        instruction.branch_index;
                break;
            case battle_presentation_script_opcode::append_selector:
                if(result.count == result.selectors.size())
                {
                    result.error =
                            battle_presentation_selector_error::
                                    selector_overflow;
                    return result;
                }
                result.selectors[result.count] =
                        instruction.operands[0];
                ++result.count;
                instruction_index =
                        instruction.fallthrough_index;
                break;
            case battle_presentation_script_opcode::
                    conditional_round_and_side:
            {
                const bool condition =
                        context.side ==
                                instruction.operands[2] &&
                        _compare(
                                context.round_index,
                                instruction.operands[0],
                                instruction.operands[1]);
                instruction_index = condition ?
                        instruction.branch_index :
                        instruction.fallthrough_index;
                break;
            }
            case battle_presentation_script_opcode::
                    conditional_unit_relationship:
            {
                if(context.unit_count >
                        context.units.size())
                {
                    result.error =
                            battle_presentation_selector_error::
                                    invalid_definition;
                    return result;
                }
                const bool condition =
                        _unit_relationship(
                                context,
                                instruction.operands[1],
                                instruction.operands[2],
                                instruction.operands[3]) ==
                        (instruction.operands[0] != 0);
                instruction_index = condition ?
                        instruction.branch_index :
                        instruction.fallthrough_index;
                break;
            }
            case battle_presentation_script_opcode::
                    conditional_unit_query:
            {
                if(context.unit_count >
                        context.units.size())
                {
                    result.error =
                            battle_presentation_selector_error::
                                    invalid_definition;
                    return result;
                }
                const bool condition =
                        _unit_query(
                                context,
                                instruction.operands[1],
                                instruction.operands[2]) ==
                        (instruction.operands[0] != 0);
                instruction_index = condition ?
                        instruction.branch_index :
                        instruction.fallthrough_index;
                break;
            }
            case battle_presentation_script_opcode::
                    set_script_flag:
                if(! context.flags)
                {
                    result.error =
                            battle_presentation_selector_error::
                                    unsupported_condition;
                    return result;
                }
                context.flags->set(
                        instruction.operands[1],
                        instruction.operands[0] == 1);
                instruction_index =
                        instruction.fallthrough_index;
                break;
            case battle_presentation_script_opcode::
                    conditional_script_flag:
            {
                const bool set = context.flags &&
                        context.flags->test(
                                instruction.operands[1]);
                const bool condition =
                        instruction.operands[0] == 0 ?
                                set : ! set;
                instruction_index = condition ?
                        instruction.branch_index :
                        instruction.fallthrough_index;
                break;
            }
            case battle_presentation_script_opcode::
                    conditional_battle_state:
                instruction_index =
                        context.battle_state ==
                                instruction.operands[0] ?
                        instruction.branch_index :
                        instruction.fallthrough_index;
                break;
            case battle_presentation_script_opcode::
                    selector_dispatch:
            {
                instruction_index =
                        instruction.fallthrough_index;
                const std::size_t end =
                        instruction.dispatch_offset +
                        instruction.dispatch_count;
                if(end >
                        battle_presentation_selector_dispatch_cases
                                .size())
                {
                    result.error =
                            battle_presentation_selector_error::
                                    invalid_instruction;
                    return result;
                }
                for(std::size_t index =
                            instruction.dispatch_offset;
                        index < end; ++index)
                {
                    const battle_presentation_selector_dispatch_case&
                            candidate =
                                    battle_presentation_selector_dispatch_cases[
                                            index];
                    if(candidate.selector ==
                            context.dispatch_selector)
                    {
                        instruction_index =
                                candidate.instruction_index;
                        break;
                    }
                }
                break;
            }
            case battle_presentation_script_opcode::
                    render_encoded_text:
            case battle_presentation_script_opcode::
                    show_portrait:
            case battle_presentation_script_opcode::
                    select_message_speaker:
                instruction_index =
                        instruction.fallthrough_index;
                break;
            default:
                result.error =
                        battle_presentation_selector_error::
                                unsupported_condition;
                return result;
            }
        }
        result.error =
                battle_presentation_selector_error::
                        execution_limit;
        return result;
    }

private:
    [[nodiscard]] static constexpr bool _inside_definition(
            const battle_presentation_definition& definition,
            std::uint16_t instruction_index)
    {
        return instruction_index != no_presentation_index &&
                instruction_index >=
                        definition.selector_instruction_offset &&
                instruction_index <
                        definition.selector_instruction_offset +
                                definition.selector_instruction_count &&
                instruction_index <
                        battle_presentation_selector_instructions.size();
    }

    [[nodiscard]] static constexpr bool _compare(
            int left, std::uint8_t comparison, int right)
    {
        switch(comparison)
        {
        case 0:
            return left == right;
        case 1:
            return left != right;
        case 2:
            return left > right;
        case 3:
            return left >= right;
        case 4:
            return left < right;
        case 5:
            return left <= right;
        default:
            return false;
        }
    }

    [[nodiscard]] static constexpr bool
    _identity_matches(
            std::uint8_t actual,
            std::uint8_t requested)
    {
        return actual == requested ||
                (requested == 8 && actual == 0x39) ||
                (requested == 15 && actual == 0x3A) ||
                (requested == 12 && actual == 0x3C);
    }

    [[nodiscard]] static constexpr bool _unit_query(
            const battle_presentation_selector_context& context,
            std::uint8_t side,
            std::uint8_t character_id)
    {
        for(std::size_t index = 0;
                index < context.unit_count; ++index)
        {
            const battle_presentation_selector_unit& unit =
                    context.units[index];
            if(unit.active && unit.side == side &&
                    _identity_matches(
                            unit.character_id,
                            character_id))
            {
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] static constexpr bool
    _unit_relationship(
            const battle_presentation_selector_context& context,
            std::uint8_t mode,
            std::uint8_t first_character_id,
            std::uint8_t second_character_id)
    {
        for(std::size_t first_index = 0;
                first_index < context.unit_count;
                ++first_index)
        {
            const battle_presentation_selector_unit& first =
                    context.units[first_index];
            if(! first.active ||
                    ! _identity_matches(
                            first.character_id,
                            first_character_id) ||
                    (mode <= 1 && first.side != mode) ||
                    (mode == 2 && first.side != 0))
            {
                continue;
            }
            const std::uint8_t second_side =
                    mode <= 1 ?
                            mode :
                    mode == 2 ?
                            1 :
                            std::uint8_t(1 - first.side);
            for(std::size_t second_index = 0;
                    second_index < context.unit_count;
                    ++second_index)
            {
                const battle_presentation_selector_unit&
                        second =
                                context.units[
                                        second_index];
                if(! second.active ||
                        second.side != second_side ||
                        ! _identity_matches(
                                second.character_id,
                                second_character_id))
                {
                    continue;
                }
                int distance =
                        int(first.x) - int(second.x);
                if(distance < 0)
                {
                    distance = -distance;
                }
                int vertical =
                        int(first.y) - int(second.y);
                if(vertical < 0)
                {
                    vertical = -vertical;
                }
                if(distance + vertical <= 1)
                {
                    return true;
                }
            }
        }
        return false;
    }
};

enum class battle_presentation_script_phase : std::uint8_t
{
    idle,
    wait_for_input,
    wait_frames,
    complete,
    error,
};

struct battle_presentation_portrait_snapshot
{
    bool visible = false;
    bool focused = false;
    std::uint8_t portrait_id = 0;
    std::uint8_t expression_id = 0;
    std::uint8_t motion_mode =
            no_battle_presentation_portrait_motion;
    std::uint8_t motion_parameter = 0;
    std::uint16_t revision = 0;

    constexpr bool operator==(
            const battle_presentation_portrait_snapshot&) const =
                    default;
};

struct battle_presentation_script_snapshot
{
    battle_presentation_script_phase phase =
            battle_presentation_script_phase::idle;
    std::uint8_t selector = 0;
    std::uint8_t speaker = 0;
    std::uint8_t command_index = 0;
    std::uint8_t remaining_frames = 0;
    std::uint32_t text_address = 0;
    std::uint16_t text_offset = 0;
    std::uint8_t text_length = 0;
    bool message_window_visible = false;
    std::array<
            battle_presentation_portrait_snapshot,
            3> portraits = {};
    battle_presentation_script_opcode last_visual_opcode =
            battle_presentation_script_opcode::end;
    std::array<std::uint8_t, 4>
            last_visual_operands = {};

    constexpr bool operator==(
            const battle_presentation_script_snapshot&) const =
                    default;
};

class battle_presentation_script
{
public:
    [[nodiscard]] bool begin(
            const battle_presentation_definition& definition,
            std::uint8_t selector)
    {
        _state = {};
        _case = battle_presentation_case_for(
                definition, selector);
        if(! _case ||
                static_cast<std::size_t>(
                        _case->command_offset) +
                        _case->command_count >
                        battle_presentation_commands.size())
        {
            _state.phase =
                    battle_presentation_script_phase::error;
            return false;
        }
        _state.selector = selector;
        _advance_to_block();
        return _state.phase !=
                battle_presentation_script_phase::error;
    }

    [[nodiscard]] const battle_presentation_script_snapshot&
    snapshot() const
    {
        return _state;
    }

    [[nodiscard]] const std::uint8_t* text_data() const
    {
        if(_state.text_length == 0 ||
                static_cast<std::size_t>(_state.text_offset) +
                        _state.text_length >
                        battle_presentation_text.size())
        {
            return nullptr;
        }
        return battle_presentation_text.data() +
                _state.text_offset;
    }

    [[nodiscard]] bool confirm()
    {
        if(_state.phase !=
                battle_presentation_script_phase::
                        wait_for_input)
        {
            return false;
        }
        ++_state.command_index;
        _advance_to_block();
        return true;
    }

    [[nodiscard]] bool tick()
    {
        if(_state.phase !=
                battle_presentation_script_phase::
                        wait_frames)
        {
            return false;
        }
        if(_state.remaining_frames > 0)
        {
            --_state.remaining_frames;
        }
        if(_state.remaining_frames == 0)
        {
            ++_state.command_index;
            _advance_to_block();
        }
        return true;
    }

private:
    void _advance_to_block()
    {
        _state.text_address = 0;
        _state.text_offset = 0;
        _state.text_length = 0;
        _state.message_window_visible = false;
        for(int step = 0; step < 256; ++step)
        {
            if(! _case ||
                    _state.command_index >=
                            _case->command_count)
            {
                _state.phase =
                        battle_presentation_script_phase::error;
                return;
            }
            const battle_presentation_command& command =
                    battle_presentation_commands[
                            _case->command_offset +
                                    _state.command_index];
            switch(command.opcode)
            {
            case battle_presentation_script_opcode::end:
                _state.phase =
                        battle_presentation_script_phase::
                                complete;
                return;
            case battle_presentation_script_opcode::
                    select_message_speaker:
                _state.speaker = command.operands[0];
                _focus_portrait_id(_state.speaker);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::
                    render_encoded_text:
            case battle_presentation_script_opcode::
                    render_parameterized_encoded_text:
                if(static_cast<std::size_t>(
                                command.text_offset) +
                                command.text_length >
                        battle_presentation_text.size())
                {
                    _state.phase =
                            battle_presentation_script_phase::
                                    error;
                    return;
                }
                _state.text_address =
                        command.source_address;
                _state.text_offset = command.text_offset;
                _state.text_length = command.text_length;
                _state.message_window_visible = true;
                _state.phase =
                        battle_presentation_script_phase::
                                wait_for_input;
                return;
            case battle_presentation_script_opcode::wait_frames:
                _state.remaining_frames =
                        command.operands[0];
                if(_state.remaining_frames == 0)
                {
                    ++_state.command_index;
                }
                else
                {
                    _state.phase =
                            battle_presentation_script_phase::
                                    wait_frames;
                    return;
                }
                break;
            case battle_presentation_script_opcode::show_portrait:
                _set_portrait(
                        command.operands[0],
                        command.operands[1],
                        command.operands[2],
                        true);
                _focus_portrait_slot(command.operands[0]);
                _record_visual(command);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::hide_portrait:
                _hide_portrait(command.operands[0]);
                _record_visual(command);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::update_portrait:
                _set_portrait(
                        command.operands[0],
                        command.operands[1],
                        command.operands[2],
                        false);
                _focus_portrait_slot(command.operands[0]);
                _record_visual(command);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::
                    set_portrait_focus:
                if(command.operands[0] == 0xFF)
                {
                    _clear_portrait_focus();
                }
                else
                {
                    _focus_portrait_slot(
                            command.operands[0]);
                }
                _record_visual(command);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::
                    initialize_portrait_pair:
                _set_portrait(
                        0,
                        command.operands[0],
                        command.operands[1],
                        true);
                _set_portrait(
                        1,
                        command.operands[2],
                        command.operands[3],
                        true);
                _clear_portrait_focus();
                _record_visual(command);
                ++_state.command_index;
                break;
            case battle_presentation_script_opcode::
                    animate_portrait:
                _animate_portrait(
                        command.operands[0],
                        command.operands[1],
                        command.operands[2]);
                _record_visual(command);
                ++_state.command_index;
                break;
            default:
                _state.phase =
                        battle_presentation_script_phase::error;
                return;
            }
        }
        _state.phase =
                battle_presentation_script_phase::error;
    }

    void _set_portrait(
            std::uint8_t slot,
            std::uint8_t portrait_id,
            std::uint8_t expression_id,
            bool reset_motion)
    {
        if(slot >= _state.portraits.size())
        {
            return;
        }
        battle_presentation_portrait_snapshot& portrait =
                _state.portraits[slot];
        portrait.visible = true;
        portrait.portrait_id = portrait_id;
        portrait.expression_id = expression_id;
        if(reset_motion)
        {
            portrait.motion_mode =
                    no_battle_presentation_portrait_motion;
            portrait.motion_parameter = 0;
        }
        ++portrait.revision;
    }

    void _hide_portrait(std::uint8_t slot)
    {
        if(slot == 0xFF)
        {
            for(auto& portrait : _state.portraits)
            {
                portrait.visible = false;
                portrait.focused = false;
                ++portrait.revision;
            }
            return;
        }
        if(slot < _state.portraits.size())
        {
            battle_presentation_portrait_snapshot& portrait =
                    _state.portraits[slot];
            portrait.visible = false;
            portrait.focused = false;
            ++portrait.revision;
        }
    }

    void _clear_portrait_focus()
    {
        for(auto& portrait : _state.portraits)
        {
            portrait.focused = false;
        }
    }

    void _focus_portrait_slot(std::uint8_t slot)
    {
        _clear_portrait_focus();
        if(slot < _state.portraits.size() &&
                _state.portraits[slot].visible)
        {
            _state.portraits[slot].focused = true;
        }
    }

    void _focus_portrait_id(std::uint8_t portrait_id)
    {
        _clear_portrait_focus();
        for(std::size_t slot = 0;
                slot < 2 && slot < _state.portraits.size();
                ++slot)
        {
            battle_presentation_portrait_snapshot& portrait =
                    _state.portraits[slot];
            if(portrait.visible &&
                    portrait.portrait_id == portrait_id)
            {
                portrait.focused = true;
                return;
            }
        }
    }

    void _animate_portrait(
            std::uint8_t slot,
            std::uint8_t motion_mode,
            std::uint8_t motion_parameter)
    {
        if(slot >= _state.portraits.size())
        {
            return;
        }
        battle_presentation_portrait_snapshot& portrait =
                _state.portraits[slot];
        portrait.motion_mode = motion_mode;
        portrait.motion_parameter = motion_parameter;
        ++portrait.revision;
    }

    void _record_visual(
            const battle_presentation_command& command)
    {
        _state.last_visual_opcode = command.opcode;
        _state.last_visual_operands = command.operands;
    }

    const battle_presentation_case* _case = nullptr;
    battle_presentation_script_snapshot _state;
};

}

#endif
