#ifndef KONOHA_BATTLE_MATERIAL_PICKUPS_H
#define KONOHA_BATTLE_MATERIAL_PICKUPS_H

#include "konoha/battle_campaign_inventory.h"
#include "konoha/battle_session.h"

namespace konoha
{

struct battle_material_pickup
{
    std::uint32_t sequence = 0;
    std::uint8_t material_id = 0;
    bool added = false;
};

class battle_material_pickups
{
public:
    template<std::size_t MaxUnits>
    [[nodiscard]] static bool initialize(battle_session<MaxUnits>& session,
            int battle_id, int variant)
    {
        if(battle_id != 14 || variant != 0) return true;
        // ROM 0x0855DFD0: category, material ID, x, y; producer 0x0806E818.
        return session.objects().place(1, {3, 4, 4, 0, 2, {3}}) &&
                session.objects().place(2, {3, 13, 5, 0, 2, {4}});
    }

    template<std::size_t MaxUnits>
    static void complete_action(battle_session<MaxUnits>& session,
            battle_unit_id actor_id, battle_campaign_inventory& inventory,
            battle_material_pickup& receipt)
    {
        const battle_unit_instance* actor = session.unit(actor_id);
        if(! actor || ! actor->active || actor->side != battle_side::player)
            return;
        for(std::uint8_t slot = 1; slot < battlefield_object_table::capacity; ++slot)
        {
            const battlefield_object_record* object = session.objects().record(slot);
            if(! object || object->type != 3 || object->payload_id != 2 ||
                    actor->position != grid_point{object->x, object->y}) continue;
            const auto material = object->behavior;
            if(material == 0 || material >= inventory.materials.size()) continue;
            // 0x0808173C consumes the box before 0x0808FCA0's 99 cap.
            if(! session.objects().free(slot)) return;
            const bool added = inventory.materials[material] < 99;
            if(added) ++inventory.materials[material];
            receipt = {receipt.sequence + 1, static_cast<std::uint8_t>(material), added};
            return;
        }
    }
};

}
#endif
