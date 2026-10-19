#include "konoha/battle_primary_training_flow.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

std::size_t select_action(
        battle_primary_training_flow& flow,
        const std::array<character_progression_record, 3>& roster,
        ability_id action_id)
{
    const std::size_t count = flow.snapshot(roster).entry_count;
    for(std::size_t index = 0; index < count; ++index)
    {
        if(flow.snapshot(roster).selected_action_id == action_id)
        {
            return index;
        }
        assert(flow.cycle_action(1, roster));
    }
    assert(false);
    return 0;
}

}

int main()
{
    std::array<character_progression_record, 3> roster = {{
        character_progression_record{ 1, 2, 25, 1, true },
        character_progression_record{ 2, 3, 0, 2, true },
        {},
    }};
    assert(initialize_character_action_progression(
            roster[0], unit_definitions[1]));
    assert(initialize_character_action_progression(
            roster[1], unit_definitions[2]));

    battle_primary_training_flow flow;
    assert(flow.begin(roster));
    battle_primary_training_snapshot state =
            flow.snapshot(roster);
    assert(state.active);
    assert(state.participant_index == 0);
    assert(state.character_id == 1);
    assert(state.training_points == 1);
    assert(state.entry_count == 32);

    (void) select_action(flow, roster, 8);
    state = flow.snapshot(roster);
    assert(state.selected_slot_index == 6);
    assert(state.selected_action_id == 8);
    assert(state.selected_level == unlocked_action_level);

    const action_training_result learned =
            flow.confirm(roster);
    assert(learned.success());
    assert(learned.action_id == 8);
    assert(learned.before_level == unlocked_action_level);
    assert(learned.after_level == 1);
    assert(roster[0].training_points == 0);
    assert(roster[0].primary_action_levels[6] == 1);
    state = flow.snapshot(roster);
    assert(state.last_error == action_training_error::none);
    assert(state.selected_level == 1);

    const action_training_result no_points =
            flow.confirm(roster);
    assert(no_points.error ==
           action_training_error::no_training_points);
    assert(roster[0].primary_action_levels[6] == 1);
    assert(flow.snapshot(roster).last_error ==
           action_training_error::no_training_points);

    assert(flow.cycle_character(1, roster));
    state = flow.snapshot(roster);
    assert(state.participant_index == 1);
    assert(state.character_id == 2);
    assert(state.training_points == 2);

    (void) select_action(flow, roster, 2);
    roster[1].primary_action_levels[
            flow.snapshot(roster).selected_slot_index] =
                    maximum_action_level;
    const action_training_result maximum =
            flow.confirm(roster);
    assert(maximum.error ==
           action_training_error::maximum_level);
    assert(roster[1].training_points == 2);

    (void) select_action(flow, roster, 4);
    const action_training_result locked =
            flow.confirm(roster);
    assert(locked.error == action_training_error::locked);
    assert(roster[1].training_points == 2);

    std::array<character_progression_record, 3>
            empty_roster = {};
    battle_primary_training_flow empty;
    assert(! empty.begin(empty_roster));
    assert(! empty.snapshot(empty_roster).active);
    assert(! empty.cycle_action(1, empty_roster));
    assert(! empty.cycle_character(1, empty_roster));
    assert(empty.confirm(empty_roster).error ==
           action_training_error::invalid_character);
}
