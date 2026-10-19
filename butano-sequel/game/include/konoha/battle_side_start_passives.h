#ifndef KONOHA_BATTLE_SIDE_START_PASSIVES_H
#define KONOHA_BATTLE_SIDE_START_PASSIVES_H

#include "konoha/battle_attributes.h"
#include "konoha/generated_battle_passive_content.h"
#include "konoha/battle_status_store.h"

#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t
        nine_tail_chakra_passive_target = 0x1D;
inline constexpr std::uint8_t
        berserk_symbol_passive_target = 0x1E;
inline constexpr std::uint8_t
        inner_sakura_passive_target = 0x1F;
inline constexpr std::uint8_t
        battle_11_side_start_passive_target = 0x20;

enum class battle_side_start_passive_kind : std::uint8_t
{
    none,
    nine_tail_chakra = nine_tail_chakra_passive_target,
    berserk_symbol = berserk_symbol_passive_target,
    inner_sakura = inner_sakura_passive_target,
    battle_11_dual_boost =
            battle_11_side_start_passive_target,
};

struct battle_side_start_passive_event
{
    bool valid = false;
    battle_side_start_passive_kind kind =
            battle_side_start_passive_kind::none;
    std::uint8_t unit_id = 0xFF;
    passive_id passive = no_passive;
    int hp_delta = 0;
    int chakra_delta = 0;
    std::uint8_t status_code = 0;
    std::uint8_t status_value = 0;
    std::uint8_t status_duration_ticks = 0;
    bool status_applied = false;
    std::uint8_t secondary_status_code = 0;
    std::uint8_t secondary_status_value = 0;
    std::uint8_t secondary_status_duration_ticks = 0;
    bool secondary_status_applied = false;

    constexpr bool operator==(
            const battle_side_start_passive_event&) const =
            default;
};

class battle_side_start_passive_system
{
public:
    template<typename Unit>
    [[nodiscard]] static battle_side_start_passive_event
    apply(Unit& unit, std::uint8_t battle_id = 0)
    {
        passive_query_result passive;
        battle_side_start_passive_kind kind =
                battle_side_start_passive_kind::none;
        for(const battle_side_start_passive_kind candidate :
                {
                    battle_side_start_passive_kind::
                            nine_tail_chakra,
                    battle_side_start_passive_kind::
                            berserk_symbol,
                    battle_side_start_passive_kind::
                            inner_sakura,
                    battle_side_start_passive_kind::
                            battle_11_dual_boost,
                })
        {
            passive = unit.passives.query(
                    static_cast<std::uint8_t>(candidate),
                    passive_definitions);
            if(passive.found)
            {
                kind = candidate;
                break;
            }
        }
        if(! passive.found)
        {
            return {};
        }

        const bool condition =
                _condition(unit, kind, battle_id);
        if(unit.side_start_passive_latched)
        {
            if(! condition)
            {
                unit.side_start_passive_latched = false;
            }
            return {};
        }
        if(! condition)
        {
            return {};
        }

        battle_side_start_passive_event event;
        event.valid = true;
        event.kind = kind;
        event.unit_id = unit.id;
        event.passive = passive.id;
        if(kind ==
                battle_side_start_passive_kind::
                        battle_11_dual_boost)
        {
            Unit changed = unit;
            event.status_code = 0x1E;
            event.status_value =
                    static_cast<std::uint8_t>(
                            passive.value_a);
            event.secondary_status_code = 0x22;
            event.secondary_status_value =
                    static_cast<std::uint8_t>(
                            passive.value_b);
            if(! changed.statuses.upsert({
                       event.status_code,
                       0,
                       0,
                       0,
                       unit.id,
                       0,
                       event.status_value,
                   }) ||
                    ! changed.statuses.upsert({
                       event.secondary_status_code,
                       0,
                       0,
                       0,
                       unit.id,
                       0,
                       event.secondary_status_value,
                   }))
            {
                return {};
            }
            event.status_applied = true;
            event.secondary_status_applied = true;
            changed.side_start_passive_latched = true;
            battle_attribute_system::recompute(changed);
            unit = changed;
            return event;
        }
        if(kind ==
                battle_side_start_passive_kind::
                        nine_tail_chakra)
        {
            const int previous_hp = unit.hp;
            const int previous_chakra = unit.chakra;
            unit.hp = _clamp_add(
                    unit.hp, passive.value_a, unit.max_hp);
            unit.chakra = unit.max_chakra;
            event.hp_delta = unit.hp - previous_hp;
            event.chakra_delta =
                    unit.chakra - previous_chakra;
        }
        else
        {
            const std::uint8_t raw_duration =
                    kind ==
                                    battle_side_start_passive_kind::
                                            berserk_symbol ?
                            5 :
                            3;
            event.status_code = 0x1E;
            event.status_value =
                    static_cast<std::uint8_t>(
                            passive.value_a);
            event.status_duration_ticks =
                    encode_status_duration_ticks(
                            raw_duration);
            event.status_applied =
                    unit.statuses.upsert({
                        event.status_code,
                        0,
                        event.status_duration_ticks,
                        0,
                        unit.id,
                        0,
                        event.status_value,
                    });
            if(kind ==
                    battle_side_start_passive_kind::
                            berserk_symbol)
            {
                const int previous_hp = unit.hp;
                unit.hp = _clamp_add(
                        unit.hp,
                        passive.value_b,
                        unit.max_hp);
                event.hp_delta = unit.hp - previous_hp;
            }
            battle_attribute_system::recompute(unit);
        }
        unit.side_start_passive_latched = true;
        return event;
    }

private:
    template<typename Unit>
    [[nodiscard]] static bool _condition(
            const Unit& unit,
            battle_side_start_passive_kind kind,
            std::uint8_t battle_id)
    {
        if(kind ==
                battle_side_start_passive_kind::
                        battle_11_dual_boost)
        {
            return battle_id == 11;
        }
        if(kind ==
                        battle_side_start_passive_kind::
                                nine_tail_chakra ||
                kind ==
                        battle_side_start_passive_kind::
                                berserk_symbol)
        {
            return unit.hp <= 9;
        }
        return unit.hp <= unit.max_hp / 4;
    }

    [[nodiscard]] static constexpr int _clamp_add(
            int current, int amount, int maximum)
    {
        const int result = current + amount;
        return result > maximum ? maximum : result;
    }
};

}

#endif
