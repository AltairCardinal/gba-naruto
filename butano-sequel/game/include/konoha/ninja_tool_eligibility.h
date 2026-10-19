#ifndef KONOHA_NINJA_TOOL_ELIGIBILITY_H
#define KONOHA_NINJA_TOOL_ELIGIBILITY_H

#include "konoha/generated_battle_action_content.h"

#include <cstdint>

namespace konoha
{

[[nodiscard]] constexpr bool character_is_eligible(
        const ninja_tool_upgrade_recipe& recipe,
        std::uint8_t character_id)
{
    return (recipe.eligible_character_0 == 0 &&
                   recipe.eligible_character_1 == 0) ||
            recipe.eligible_character_0 == character_id ||
            recipe.eligible_character_1 == character_id;
}

}

#endif
