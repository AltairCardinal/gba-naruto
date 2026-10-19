#ifndef KONOHA_BATTLE_VISUAL_RESOURCE_COORDINATOR_H
#define KONOHA_BATTLE_VISUAL_RESOURCE_COORDINATOR_H

namespace konoha
{

// OBJ VRAM and OBJ palette RAM are shared scene resources.  These cohorts
// describe mutually exclusive owners; a transition must release the outgoing
// owners and commit one frame before the incoming owners allocate.
enum class battle_visual_resource_cohort
{
    deployment,
    map,
    script_dialogue,
    combat_portrait,
};

struct battle_visual_resource_contract
{
    bool map_units = false;
    bool map_cursor = false;
    bool map_ui = false;
    bool map_text = false;
    bool combat_stage = false;
    bool script_glyphs = false;
    bool script_message_window = false;
    bool portrait = false;

    constexpr explicit battle_visual_resource_contract(
            battle_visual_resource_cohort cohort)
    {
        switch(cohort)
        {
        case battle_visual_resource_cohort::deployment:
            map_units = true;
            map_text = true;
            break;
        case battle_visual_resource_cohort::map:
            map_units = true;
            map_cursor = true;
            map_ui = true;
            map_text = true;
            combat_stage = true;
            break;
        case battle_visual_resource_cohort::script_dialogue:
            script_glyphs = true;
            script_message_window = true;
            portrait = true;
            break;
        case battle_visual_resource_cohort::combat_portrait:
            portrait = true;
            break;
        default:
            break;
        }
    }
};

[[nodiscard]] constexpr battle_visual_resource_cohort
select_battle_visual_resource_cohort(
        bool script_dialogue_visible,
        bool combat_portrait_visible)
{
    if(combat_portrait_visible)
    {
        return battle_visual_resource_cohort::
                combat_portrait;
    }
    if(script_dialogue_visible)
    {
        return battle_visual_resource_cohort::
                script_dialogue;
    }
    return battle_visual_resource_cohort::map;
}

struct battle_visual_resource_transition
{
    battle_visual_resource_cohort from =
            battle_visual_resource_cohort::map;
    battle_visual_resource_cohort to =
            battle_visual_resource_cohort::map;
    bool changed = false;
    bool release_map = false;
    bool release_script = false;
    bool release_portrait = false;
    bool commit_before_allocate = false;
};

class battle_visual_resource_coordinator
{
public:
    [[nodiscard]] battle_visual_resource_transition
    transition_to(battle_visual_resource_cohort next)
    {
        battle_visual_resource_transition result;
        result.from = _current;
        result.to = next;
        if(next == _current)
        {
            return result;
        }

        result.changed = true;
        switch(_current)
        {
        case battle_visual_resource_cohort::deployment:
            result.release_map = true;
            break;
        case battle_visual_resource_cohort::map:
            result.release_map = true;
            break;
        case battle_visual_resource_cohort::script_dialogue:
            result.release_script = true;
            break;
        case battle_visual_resource_cohort::combat_portrait:
            result.release_portrait = true;
            break;
        default:
            break;
        }
        result.commit_before_allocate = true;
        _current = next;
        return result;
    }

    [[nodiscard]] constexpr battle_visual_resource_cohort
    current() const
    {
        return _current;
    }

private:
    battle_visual_resource_cohort _current =
            battle_visual_resource_cohort::deployment;
};

}

#endif
