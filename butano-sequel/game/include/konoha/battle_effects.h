#ifndef KONOHA_BATTLE_EFFECTS_H
#define KONOHA_BATTLE_EFFECTS_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

struct unit_state
{
    int hp;
    int max_hp;
    int chakra;
    int x;
    int y;
    std::uint32_t status_mask;
    bool active;
    bool captured = false;
    bool summoned = false;
    bool substitution_ready = false;
    std::uint8_t defense_ability = 0xFF;
    int scripted_event = 0;

    constexpr bool operator==(const unit_state&) const = default;
};

enum class effect_kind
{
    damage,
    heal,
    spend_chakra,
    add_status,
    move,
    summon,
    capture,
    prepare_defense,
    substitute,
    scripted_event,
};

struct effect
{
    effect_kind kind;
    int value;
    int secondary;
};

enum class effect_error
{
    none,
    invalid_target,
    insufficient_chakra,
    invalid_effect,
};

struct effect_chain_result
{
    effect_error error;
    std::size_t applied_count;

    [[nodiscard]] constexpr bool success() const
    {
        return error == effect_error::none;
    }
};

template<std::size_t Count>
effect_chain_result apply_effect_chain(
        unit_state& source, unit_state& target, const std::array<effect, Count>& effects)
{
    unit_state next_source = source;
    unit_state next_target = target;
    for(const effect& current : effects)
    {
        switch(current.kind)
        {
        case effect_kind::damage:
            if(! next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            if(current.value < 0)
            {
                return { effect_error::invalid_effect, 0 };
            }
            if(next_target.substitution_ready)
            {
                next_target.substitution_ready = false;
            }
            else
            {
                next_target.hp = current.value >= next_target.hp ?
                        0 : next_target.hp - current.value;
            }
            break;

        case effect_kind::heal:
            if(! next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            if(current.value < 0)
            {
                return { effect_error::invalid_effect, 0 };
            }
            next_target.hp = current.value >= next_target.max_hp - next_target.hp ?
                    next_target.max_hp : next_target.hp + current.value;
            break;

        case effect_kind::spend_chakra:
            if(current.value < 0)
            {
                return { effect_error::invalid_effect, 0 };
            }
            if(current.value > next_source.chakra)
            {
                return { effect_error::insufficient_chakra, 0 };
            }
            next_source.chakra -= current.value;
            break;

        case effect_kind::add_status:
            if(! next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            if(current.value <= 0)
            {
                return { effect_error::invalid_effect, 0 };
            }
            next_target.status_mask |= static_cast<std::uint32_t>(current.value);
            break;

        case effect_kind::move:
            if(! next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            next_target.x += current.value;
            next_target.y += current.secondary;
            break;

        case effect_kind::summon:
            if(next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            next_target.active = true;
            next_target.summoned = true;
            next_target.x = current.value;
            next_target.y = current.secondary;
            break;

        case effect_kind::capture:
            if(! next_target.active)
            {
                return { effect_error::invalid_target, 0 };
            }
            next_target.captured = true;
            next_target.active = false;
            break;

        case effect_kind::prepare_defense:
            if(current.value < 0 || current.value > 0xFF)
            {
                return { effect_error::invalid_effect, 0 };
            }
            next_source.defense_ability = static_cast<std::uint8_t>(current.value);
            break;

        case effect_kind::substitute:
            next_source.substitution_ready = true;
            break;

        case effect_kind::scripted_event:
            if(current.value <= 0)
            {
                return { effect_error::invalid_effect, 0 };
            }
            next_source.scripted_event = current.value;
            break;

        default:
            return { effect_error::invalid_effect, 0 };
        }
    }

    source = next_source;
    target = next_target;
    return { effect_error::none, Count };
}

}

#endif
