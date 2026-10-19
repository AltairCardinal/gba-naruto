#include "konoha/battle_training_flow.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

std::size_t select_entry(
        battle_training_flow& flow,
        const std::array<character_progression_record, 3>&
                roster,
        battle_training_entry_kind kind,
        std::uint8_t definition_id)
{
    const std::size_t count =
            flow.snapshot(roster).entry_count;
    for(std::size_t index = 0; index < count; ++index)
    {
        const battle_training_snapshot state =
                flow.snapshot(roster);
        if(state.selected_kind == kind &&
                state.selected_definition_id ==
                        definition_id)
        {
            return index;
        }
        assert(flow.cycle_entry(1, roster));
    }
    assert(false);
    return 0;
}

}

int main()
{
    std::array<character_progression_record, 3> roster = {{
        character_progression_record{ 1, 9, 0, 2, true },
        character_progression_record{ 3, 5, 0, 1, true },
        {},
    }};
    assert(initialize_character_action_progression(
            roster[0], unit_definitions[1]));
    assert(initialize_character_action_progression(
            roster[1], unit_definitions[3]));

    battle_training_flow flow;
    assert(flow.begin(roster));
    battle_training_snapshot state =
            flow.snapshot(roster);
    assert(state.active);
    assert(state.participant_index == 0);
    assert(state.character_id == 1);
    assert(state.training_points == 2);
    assert(state.entry_count == 32);
    assert(state.selected_kind ==
           battle_training_entry_kind::primary_action);
    assert(state.selected_definition_id == 2);

    for(int index = 0; index < 8; ++index)
    {
        assert(flow.cycle_entry(1, roster));
    }
    state = flow.snapshot(roster);
    assert(state.entry_index == 8);
    assert(state.selected_kind ==
           battle_training_entry_kind::secondary_passive);
    assert(state.selected_slot_index == 0);
    assert(state.selected_definition_id == 1);
    assert(state.selected_level == unlocked_action_level);

    const action_training_result learned_passive =
            flow.confirm(roster);
    assert(learned_passive.success());
    assert(learned_passive.trained_passive_id == 1);
    assert(roster[0].secondary_action_levels[0] == 1);
    assert(roster[0].training_points == 1);

    (void) select_entry(
            flow,
            roster,
            battle_training_entry_kind::primary_action,
            2);
    const action_training_result trained_action =
            flow.confirm(roster);
    assert(trained_action.success());
    assert(trained_action.action_id == 2);
    assert(roster[0].primary_action_levels[0] == 2);
    assert(roster[0].training_points == 0);

    assert(flow.cycle_character(1, roster));
    state = flow.snapshot(roster);
    assert(state.participant_index == 1);
    assert(state.character_id == 3);
    assert(state.entry_count == 30);

    (void) select_entry(
            flow,
            roster,
            battle_training_entry_kind::secondary_passive,
            15);
    state = flow.snapshot(roster);
    assert(state.selected_slot_index == 13);
    assert(state.selected_level == unlocked_action_level);
    const action_training_result sakura_passive =
            flow.confirm(roster);
    assert(sakura_passive.success());
    assert(sakura_passive.trained_passive_id == 15);
    assert(roster[1].secondary_action_levels[13] == 1);
    assert(roster[1].training_points == 0);

    const battle_training_snapshot after =
            flow.snapshot(roster);
    assert(after.last_error == action_training_error::none);
    assert(after.selected_level == 1);

    std::array<character_progression_record, 3>
            empty_roster = {};
    battle_training_flow empty;
    assert(! empty.begin(empty_roster));
    assert(! empty.snapshot(empty_roster).active);
    assert(! empty.cycle_entry(1, empty_roster));
    assert(! empty.cycle_character(1, empty_roster));
    assert(empty.confirm(empty_roster).error ==
           action_training_error::invalid_character);
}
