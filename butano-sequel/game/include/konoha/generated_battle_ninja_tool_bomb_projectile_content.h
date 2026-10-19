#ifndef KONOHA_GENERATED_BATTLE_NINJA_TOOL_BOMB_PROJECTILE_CONTENT_H
#define KONOHA_GENERATED_BATTLE_NINJA_TOOL_BOMB_PROJECTILE_CONTENT_H

#include "konoha/battle_effect_sequence.h"

#include <array>

namespace konoha
{

inline constexpr std::array<battle_effect_asset, 4>
battle_ninja_tool_bomb_projectile_assets = {{
        battle_effect_asset{ 0, 32, 32 },
        battle_effect_asset{ 16, 32, 32 },
        battle_effect_asset{ 32, 32, 32 },
        battle_effect_asset{ 48, 32, 32 },
}};

inline constexpr battle_effect_sequence
battle_ninja_tool_bomb_projectile_sequence = { {{
        battle_effect_frame{ {{
            battle_effect_component{ 81, 58, 0, false, false, 2 },
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
        }}, 1, 2 },
        battle_effect_frame{ {{
            battle_effect_component{ 81, 58, 1, false, false, 2 },
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
        }}, 1, 2 },
        battle_effect_frame{ {{
            battle_effect_component{ 81, 58, 2, false, false, 2 },
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
        }}, 1, 2 },
        battle_effect_frame{ {{
            battle_effect_component{ 81, 58, 3, false, false, 2 },
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
            battle_effect_component{},
        }}, 1, 1 },
}}, 4 };

}

#endif
