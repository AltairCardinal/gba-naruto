// Z1 (wave 14): the battle runtime controller's member offsets.
//
// The closed-loop driver enters the settlement chain by poking the
// controller's state (the phase byte and the outcome byte).  The controller
// is a ``BN_DATA_EWRAM_BSS static`` in the battle runtime scene, so its
// address comes from the ELF symbol table and a member's address is
// ``controller_address + offsetof(member)``.
//
// This host program prints the offsets of the members the driver needs.
// ``#define private public`` is the usual way to reach a private member's
// offset; it is a layout probe, not shipped code.
//
// Build:
//   g++ -std=c++23 -I <remake>/butano-sequel/game/include \
//       z1_controller_offsets.cpp -o z1_controller_offsets

#define private public
#include "konoha/battle_scene_controller.h"
#undef private

#include <cstddef>
#include <cstdio>

int main()
{
    using konoha::battle_runtime_controller;
    using controller_type = konoha::battle_scene_controller<12, 23, 32>;
    std::printf("sizeof(battle_scene_controller<12,23,32>) = %zu\n",
                sizeof(controller_type));
    std::printf("offsetof(_phase)   = 0x%zx (%zu)\n",
                offsetof(controller_type, _phase),
                offsetof(controller_type, _phase));
    std::printf("offsetof(_outcome) = 0x%zx (%zu)\n",
                offsetof(controller_type, _outcome),
                offsetof(controller_type, _outcome));
    std::printf("offsetof(_round)   = 0x%zx (%zu)\n",
                offsetof(controller_type, _round),
                offsetof(controller_type, _round));
    std::printf("offsetof(_cursor)  = 0x%zx (%zu)\n",
                offsetof(controller_type, _cursor),
                offsetof(controller_type, _cursor));
    std::printf("offsetof(_result)  = 0x%zx (%zu)\n",
                offsetof(controller_type, _result),
                offsetof(controller_type, _result));
    std::printf("offsetof(_script)  = 0x%zx (%zu)\n",
                offsetof(controller_type, _script),
                offsetof(controller_type, _script));
    std::printf("offsetof(_settlement_page) = 0x%zx (%zu)\n",
                offsetof(controller_type, _settlement_page),
                offsetof(controller_type, _settlement_page));
    std::printf("battle_runtime_controller alias matches: %s\n",
                sizeof(battle_runtime_controller) == sizeof(controller_type) ?
                        "yes" : "no");
    return 0;
}
