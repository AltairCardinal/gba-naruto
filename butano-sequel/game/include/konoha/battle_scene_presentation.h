#ifndef KONOHA_BATTLE_SCENE_PRESENTATION_H
#define KONOHA_BATTLE_SCENE_PRESENTATION_H

#include "konoha/battle_action_animation.h"
#include "konoha/battle_combat_presentation.h"

#include <array>
#include <cstddef>

namespace konoha
{

[[nodiscard]] inline battle_scene_presentation_event
make_battlefield_object_presentation_event(
        const battlefield_object_tick_event& event,
        grid_point actor_position,
        std::uint8_t animation_family)
{
    if(! event.valid())
    {
        return {};
    }
    battle_scene_presentation_event result;
    result.valid = true;
    result.action_id = static_cast<ability_id>(
            event.object.payload_id);
    result.destination = {
        event.object.x,
        event.object.y,
    };
    result.origin = result.destination;
    result.target = result.destination;
    result.ninja_tool = true;
    result.has_battlefield_object = true;
    result.battlefield_object_kind = event.kind;
    result.battlefield_object_slot = event.slot;
    result.battlefield_object_damage =
            event.total_damage;

    if(event.kind ==
            battlefield_object_tick_kind::type_2_expired)
    {
        result.battlefield_object_tile_index_start = 0x0300;
        result.battlefield_object_tile_index_end = 0x037F;
        result.battlefield_object_palette_bank_start = 12;
        result.battlefield_object_palette_bank_end = 14;
        result.battlefield_object_effect_sequence = 7;
        return result;
    }
    if(event.kind !=
                    battlefield_object_tick_kind::type_1_due ||
            event.object.source_unit_id > 0xFF)
    {
        return {};
    }

    result.has_action = true;
    result.actor_id = static_cast<battle_unit_id>(
            event.object.source_unit_id);
    result.origin = actor_position;
    result.animation_family = animation_family;
    result.target_id = event.affected_unit_count > 0 ?
            event.affected_unit_ids[0] : no_battle_unit;
    result.affected_unit_ids =
            event.affected_unit_ids;
    result.affected_unit_count =
            event.affected_unit_count;
    result.affected_units_truncated =
            event.affected_units_truncated;
    result.impact_count = event.impact_count;
    return result;
}

[[nodiscard]] inline battle_scene_presentation_event
make_side_start_presentation_event(
        const battle_side_start_passive_event& event,
        grid_point position)
{
    if(! event.valid)
    {
        return {};
    }
    battle_scene_presentation_event result;
    result.valid = true;
    result.actor_id = event.unit_id;
    result.origin = position;
    result.destination = position;
    result.target = position;
    result.affected_unit_ids[0] = event.unit_id;
    result.affected_unit_count = 1;
    result.has_resource =
            event.hp_delta != 0 ||
            event.chakra_delta != 0;
    result.resource_hp_delta = event.hp_delta;
    result.resource_chakra_delta =
            event.chakra_delta;
    result.has_side_start_passive = true;
    result.passive = event.passive;
    result.passive_kind = event.kind;
    result.passive_status_code = event.status_code;
    result.passive_status_value = event.status_value;
    result.passive_status_duration_ticks =
            event.status_duration_ticks;
    result.passive_status_applied =
            event.status_applied;
    result.passive_secondary_status_code =
            event.secondary_status_code;
    result.passive_secondary_status_value =
            event.secondary_status_value;
    result.passive_secondary_status_duration_ticks =
            event.secondary_status_duration_ticks;
    result.passive_secondary_status_applied =
            event.secondary_status_applied;
    return result;
}

template<std::size_t Capacity>
class battle_scene_presentation_queue
{
    static_assert(Capacity > 0);

public:
    [[nodiscard]] bool push(
            const battle_scene_presentation_event& event)
    {
        if(! event.valid || _count == Capacity)
        {
            return false;
        }
        _events[_count] = event;
        ++_count;
        return true;
    }

    [[nodiscard]] battle_scene_presentation_event pop()
    {
        if(_count == 0)
        {
            return {};
        }
        const battle_scene_presentation_event result =
                _events[0];
        for(std::size_t index = 1;
                index < _count; ++index)
        {
            _events[index - 1] = _events[index];
        }
        --_count;
        _events[_count] = {};
        return result;
    }

    [[nodiscard]] constexpr std::size_t count() const
    {
        return _count;
    }

    [[nodiscard]] constexpr bool empty() const
    {
        return _count == 0;
    }

    [[nodiscard]] constexpr std::size_t available() const
    {
        return Capacity - _count;
    }

    void clear()
    {
        _events = {};
        _count = 0;
    }

private:
    std::array<
            battle_scene_presentation_event,
            Capacity> _events = {};
    std::size_t _count = 0;
};

template<
        std::size_t MaxUnits,
        std::size_t QueueCapacity>
[[nodiscard]] bool queue_new_side_start_presentations(
        const battle_session<MaxUnits>& session,
        std::uint32_t& observed_sequence,
        battle_scene_presentation_queue<
                QueueCapacity>& queue)
{
    if(session.side_start_sequence() ==
            observed_sequence)
    {
        return true;
    }
    if(queue.available() <
            session.side_start_event_count())
    {
        return false;
    }
    for(std::size_t index = 0;
            index < session.side_start_event_count();
            ++index)
    {
        const battle_side_start_passive_event* event =
                session.side_start_event_at(index);
        if(! event)
        {
            return false;
        }
        const battle_unit_instance* unit =
                session.unit(event->unit_id);
        if(! unit ||
                ! queue.push(
                        make_side_start_presentation_event(
                                *event,
                                unit->position)))
        {
            return false;
        }
    }
    observed_sequence = session.side_start_sequence();
    return true;
}

struct battle_scene_unit_pose
{
    int offset_x = 0;
    int offset_y = 0;
    bool visible = true;
    bool play_hit_cue = false;
};

class battle_scene_presentation
{
public:
    static constexpr int movement_frame_count = 16;
    static constexpr int passive_frame_count = 60;
    static constexpr int battlefield_object_expiry_graphics_frame_count =
            7;
    static constexpr int battlefield_object_expiry_frame_hold = 4;
    static constexpr int battlefield_object_expiry_frame_count =
            battlefield_object_expiry_graphics_frame_count *
            battlefield_object_expiry_frame_hold;

    [[nodiscard]] bool begin(
            battle_scene_presentation_event event)
    {
        const bool actorless_battlefield_object =
                event.has_battlefield_object &&
                event.battlefield_object_kind ==
                        battlefield_object_tick_kind::
                                type_2_expired &&
                ! event.has_action;
        if(! event.valid ||
                (event.actor_id == no_battle_unit &&
                 ! actorless_battlefield_object))
        {
            return false;
        }
        _event = event;
        _frame = 0;
        _combat = {};
        _active = true;
        return true;
    }

    [[nodiscard]] bool busy() const
    {
        return _active;
    }

    [[nodiscard]] int frame() const
    {
        return _frame;
    }

    [[nodiscard]] const battle_scene_presentation_event& event() const
    {
        return _event;
    }

    [[nodiscard]] const battle_combat_presentation& combat() const
    {
        return _combat;
    }

    [[nodiscard]] bool affects(battle_unit_id unit_id) const
    {
        if(unit_id == no_battle_unit)
        {
            return false;
        }
        for(int index = 0;
                index < _event.affected_unit_count &&
                index <
                        static_cast<int>(
                                _event.affected_unit_ids.size());
                ++index)
        {
            if(_event.affected_unit_ids[
                       static_cast<std::size_t>(index)] ==
                    unit_id)
            {
                return true;
            }
        }
        return _event.affected_unit_count == 0 &&
                unit_id == _event.target_id;
    }

    [[nodiscard]] battle_scene_unit_pose pose(
            battle_unit_id unit_id,
            grid_point settled_position) const
    {
        battle_scene_unit_pose result;
        if(! _active)
        {
            return result;
        }
        if(_frame < movement_frame_count)
        {
            if(unit_id == _event.actor_id)
            {
                const int remaining =
                        movement_frame_count - _frame;
                result.offset_x =
                        (_event.origin.x -
                         _event.destination.x) *
                        32 * remaining /
                        movement_frame_count;
                result.offset_y =
                        (_event.origin.y -
                         _event.destination.y) *
                        16 * remaining /
                        movement_frame_count;
            }
            return result;
        }
        if(! _event.has_action)
        {
            return result;
        }
        if(_combat.busy() &&
                _combat.stage() ==
                        battle_combat_presentation_stage::impact &&
                (affects(unit_id) ||
                 (_event.target_id == no_battle_unit &&
                  settled_position == _event.target)))
        {
            const int local_frame =
                    _combat.stage_frame() %
                    _combat.current_step().duration;
            result.offset_x =
                    local_frame % 4 < 2 ? -2 : 2;
            result.visible = local_frame >= 2;
            result.play_hit_cue =
                    _combat.play_impact_cue();
        }
        return result;
    }

    void advance()
    {
        if(! _active)
        {
            return;
        }
        if(_event.has_action)
        {
            if(_frame < movement_frame_count)
            {
                ++_frame;
                if(_frame == movement_frame_count &&
                        ! _combat.begin(_event))
                {
                    _active = false;
                }
                return;
            }
            if(_combat.busy())
            {
                _combat.advance();
            }
            if(! _combat.busy())
            {
                _active = false;
            }
            return;
        }
        ++_frame;
        if(_frame >= _total_frame_count())
        {
            _active = false;
        }
    }

private:
    [[nodiscard]] int _total_frame_count() const
    {
        if(_event.has_battlefield_object &&
                _event.battlefield_object_kind ==
                        battlefield_object_tick_kind::
                                type_2_expired)
        {
            return battlefield_object_expiry_frame_count;
        }
        if(_event.has_side_start_passive)
        {
            return passive_frame_count;
        }
        return movement_frame_count +
                0;
    }

    battle_scene_presentation_event _event;
    battle_combat_presentation _combat;
    int _frame = 0;
    bool _active = false;
};

}

#endif
