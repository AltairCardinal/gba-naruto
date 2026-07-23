#ifndef KONOHA_BATTLE_ATTRIBUTES_H
#define KONOHA_BATTLE_ATTRIBUTES_H

#include <cstdint>

namespace konoha
{

struct battle_attribute_view
{
    int attack = 0;
    int defense = 0;
    int agility = 0;
    int move_range = 0;
    int max_hp = 0;
};

class battle_attribute_system
{
public:
    template<typename Unit>
    static void initialize_base(Unit& unit)
    {
        if(unit.base_attack < 0)
        {
            unit.base_attack = unit.attack;
        }
        if(unit.base_defense < 0)
        {
            unit.base_defense = unit.defense;
        }
        if(unit.base_agility < 0)
        {
            unit.base_agility = unit.agility;
        }
        if(unit.base_move_range < 0)
        {
            unit.base_move_range = unit.move_range;
        }
        if(unit.base_max_hp < 0)
        {
            unit.base_max_hp = unit.max_hp;
        }
    }

    template<typename Unit>
    [[nodiscard]] static battle_attribute_view view(const Unit& unit)
    {
        battle_attribute_view result = {
            _base_or_current(unit.base_attack, unit.attack),
            _base_or_current(unit.base_defense, unit.defense),
            _base_or_current(unit.base_agility, unit.agility),
            _base_or_current(unit.base_move_range, unit.move_range),
            _base_or_current(unit.base_max_hp, unit.max_hp),
        };
        for(int index = 0; index < 16; ++index)
        {
            const auto* status = unit.statuses.active(index);
            if(! status)
            {
                continue;
            }
            const int value = status->value_u16;
            switch(status->code())
            {
            case 0x12:
            case 0x1E:
                result.attack = _increase_percent(result.attack, value, 99);
                break;
            case 0x1F:
                result.attack = _decrease_percent(result.attack, value);
                break;
            case 0x20:
                result.defense = _increase_percent(result.defense, value, 99);
                break;
            case 0x21:
                result.defense = _decrease_percent(result.defense, value);
                break;
            case 0x22:
                result.agility = _increase_percent(result.agility, value, 99);
                break;
            case 0x23:
                result.agility = _decrease_percent(result.agility, value);
                break;
            case 0x24:
                result.move_range = _clamp(result.move_range + value, 0, 9);
                break;
            case 0x25:
                result.move_range = _clamp(result.move_range - value, 0, 9);
                break;
            case 0x1B:
                result.max_hp = _increase_percent(result.max_hp, value, 999);
                break;
            default:
                break;
            }
        }
        return result;
    }

    template<typename Unit>
    static void recompute(Unit& unit)
    {
        initialize_base(unit);
        const battle_attribute_view attributes = view(unit);
        unit.attack = attributes.attack;
        unit.defense = attributes.defense;
        unit.agility = attributes.agility;
        unit.move_range = attributes.move_range;
        unit.max_hp = attributes.max_hp;
        if(unit.hp > unit.max_hp)
        {
            unit.hp = unit.max_hp;
        }
    }

private:
    [[nodiscard]] static constexpr int _base_or_current(int base, int current)
    {
        return base < 0 ? current : base;
    }

    [[nodiscard]] static constexpr int _clamp(int value, int minimum, int maximum)
    {
        return value < minimum ? minimum : (value > maximum ? maximum : value);
    }

    [[nodiscard]] static constexpr int _increase_percent(
            int current, int percent, int maximum)
    {
        return _clamp(current + current * percent / 100, 0, maximum);
    }

    [[nodiscard]] static constexpr int _decrease_percent(int current, int percent)
    {
        return _clamp(current - current * percent / 100, 0, current);
    }
};

}

#endif
