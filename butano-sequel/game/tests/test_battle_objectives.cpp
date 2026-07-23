#include "konoha/battle_objectives.h"

#include <array>
#include <cassert>

using namespace konoha;

namespace
{

battle_unit_instance unit(
        battle_unit_id id, battle_side side, grid_point position, int hp = 20)
{
    return {
        id,
        side,
        battle_control::player,
        position,
        battle_facing::down,
        hp,
        20,
        0,
        10,
        3,
        hp > 0,
        {},
    };
}

objective_node predicate(objective_predicate value)
{
    objective_node node;
    node.kind = objective_node_kind::predicate;
    node.condition = value;
    return node;
}

}

int main()
{
    objective_context<4, 4> context;
    assert(context.add_unit(unit(1, battle_side::player, { 4, 4 })));
    battle_unit_instance* actor = context.mutable_unit(1);
    assert(actor);
    actor->facing = battle_facing::right;
    actor->ledger.completed = true;

    objective_rule<8> placement;
    placement.trigger = battle_domain_event::unit_completed;
    placement.outcome = battle_outcome::victory;
    placement.priority = 10;
    placement.nodes[0] = predicate({ objective_predicate_kind::at_position, 1, { 4, 4 } });
    placement.nodes[1] = predicate({
        objective_predicate_kind::facing, 1, {}, battle_facing::right });
    placement.nodes[2] = predicate({ objective_predicate_kind::completed, 1 });
    placement.nodes[3] = { objective_node_kind::all, {}, 3, 0 };
    placement.node_count = 4;
    const std::array placement_rules = { placement };
    objective_result result = objective_engine::evaluate(
            context, battle_domain_event::unit_completed, placement_rules);
    assert(result.success());
    assert(result.outcome == battle_outcome::victory);

    battle_unit_instance cat = unit(2, battle_side::enemy, { 6, 5 });
    cat.captured = true;
    cat.active = false;
    assert(context.add_unit(cat));
    objective_rule<8> capture;
    capture.trigger = battle_domain_event::effects_resolved;
    capture.outcome = battle_outcome::victory;
    capture.priority = 20;
    capture.nodes[0] = predicate({ objective_predicate_kind::captured, 2 });
    capture.node_count = 1;
    const std::array capture_rules = { capture };
    result = objective_engine::evaluate(
            context, battle_domain_event::effects_resolved, capture_rules);
    assert(result.outcome == battle_outcome::victory);
    assert(result.interrupts_action_tail);

    battle_unit_instance escort = unit(3, battle_side::player, { 2, 2 }, 8);
    assert(context.add_unit(escort));
    assert(context.set_script_variable(0, 1));

    objective_rule<8> escort_alive;
    escort_alive.trigger = battle_domain_event::effects_resolved;
    escort_alive.outcome = battle_outcome::victory;
    escort_alive.priority = 5;
    escort_alive.nodes[0] = predicate({ objective_predicate_kind::alive, 3 });
    escort_alive.node_count = 1;

    objective_rule<8> scripted_failure;
    scripted_failure.trigger = battle_domain_event::effects_resolved;
    scripted_failure.outcome = battle_outcome::failure;
    scripted_failure.priority = 30;
    scripted_failure.nodes[0] = predicate({
        objective_predicate_kind::script_variable_equals,
        no_battle_unit,
        {},
        battle_facing::up,
        0,
        1,
    });
    scripted_failure.node_count = 1;
    const std::array escort_rules = { escort_alive, scripted_failure };
    result = objective_engine::evaluate(
            context, battle_domain_event::effects_resolved, escort_rules);
    assert(context.unit(3)->hp > 0);
    assert(result.outcome == battle_outcome::failure);
    assert(result.priority == 30);

    objective_rule<8> malformed;
    malformed.trigger = battle_domain_event::round_ended;
    malformed.outcome = battle_outcome::victory;
    malformed.nodes[0] = { objective_node_kind::all, {}, 2, 0 };
    malformed.node_count = 1;
    const std::array malformed_rules = { malformed };
    result = objective_engine::evaluate(
            context, battle_domain_event::round_ended, malformed_rules);
    assert(result.error == objective_error::malformed_expression);
    assert(result.outcome == battle_outcome::none);
}
