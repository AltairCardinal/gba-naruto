#ifndef KONOHA_BATTLE_CAMPAIGN_INVENTORY_H
#define KONOHA_BATTLE_CAMPAIGN_INVENTORY_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::size_t
        battle_campaign_ninja_tool_quantity_capacity = 94;
inline constexpr std::size_t
        battle_campaign_material_quantity_capacity = 18;

struct battle_campaign_inventory
{
    std::array<
            std::uint8_t,
            battle_campaign_ninja_tool_quantity_capacity>
            ninja_tools = {};
    std::array<
            std::uint8_t,
            battle_campaign_material_quantity_capacity>
            materials = {};

    constexpr bool operator==(
            const battle_campaign_inventory&) const =
                    default;
};

}

#endif
