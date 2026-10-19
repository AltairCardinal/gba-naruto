#ifndef KONOHA_BATTLEFIELD_OBJECTS_H
#define KONOHA_BATTLEFIELD_OBJECTS_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t no_battlefield_object = 0xFF;

struct battlefield_object_record
{
    std::uint8_t type = 0;
    std::uint8_t x = 0;
    std::uint8_t y = 0;
    std::uint8_t reserved_3 = 0;
    std::uint16_t payload_id = 0;
    union
    {
        std::uint16_t duration_ticks = 0;
        std::uint16_t behavior;
    };
    std::uint16_t source_unit_id = 0;
    std::uint16_t auxiliary = 0;
    std::uint32_t runtime_handle = 0;

    [[nodiscard]] constexpr bool operator==(
            const battlefield_object_record& other) const
    {
        return type == other.type &&
                x == other.x &&
                y == other.y &&
                reserved_3 == other.reserved_3 &&
                payload_id == other.payload_id &&
                duration_ticks == other.duration_ticks &&
                source_unit_id == other.source_unit_id &&
                auxiliary == other.auxiliary &&
                runtime_handle == other.runtime_handle;
    }
};

static_assert(sizeof(battlefield_object_record) == 16);
static_assert(offsetof(battlefield_object_record, type) == 0);
static_assert(offsetof(battlefield_object_record, x) == 1);
static_assert(offsetof(battlefield_object_record, y) == 2);
static_assert(offsetof(battlefield_object_record, payload_id) == 4);
static_assert(offsetof(battlefield_object_record, duration_ticks) == 6);
static_assert(offsetof(battlefield_object_record, source_unit_id) == 8);
static_assert(offsetof(battlefield_object_record, auxiliary) == 10);
static_assert(offsetof(battlefield_object_record, runtime_handle) == 12);

enum class battlefield_object_tick_kind : std::uint8_t
{
    none,
    type_1_due,
    type_2_expired,
};

struct battlefield_object_tick_event
{
    battlefield_object_tick_kind kind =
            battlefield_object_tick_kind::none;
    std::uint8_t slot = no_battlefield_object;
    battlefield_object_record object = {};
    std::array<std::uint8_t, 12> affected_unit_ids = {};
    int affected_unit_count = 0;
    bool affected_units_truncated = false;
    int impact_count = 0;
    int total_damage = 0;

    [[nodiscard]] constexpr bool valid() const
    {
        return kind != battlefield_object_tick_kind::none &&
                slot != no_battlefield_object;
    }

    constexpr bool operator==(
            const battlefield_object_tick_event&) const = default;
};

class battlefield_object_table
{
public:
    static constexpr std::size_t capacity = 32;
    static constexpr std::size_t usable_capacity = capacity - 1;

    [[nodiscard]] std::uint8_t allocate(battlefield_object_record value)
    {
        if(value.type == 0)
        {
            return no_battlefield_object;
        }
        for(std::uint8_t slot = 1; slot < _records.size(); ++slot)
        {
            if(_records[slot].type == 0)
            {
                _records[slot] = value;
                return slot;
            }
        }
        return no_battlefield_object;
    }

    [[nodiscard]] bool place(
            std::uint8_t slot,
            battlefield_object_record value)
    {
        if(slot == 0 || slot >= _records.size() ||
                value.type == 0 ||
                _records[slot].type != 0)
        {
            return false;
        }
        _records[slot] = value;
        return true;
    }

    [[nodiscard]] std::size_t tick_side_end(
            std::array<
                    battlefield_object_tick_event,
                    usable_capacity>& events)
    {
        events = {};
        std::size_t event_count = 0;
        for(std::uint8_t slot = 1; slot < _records.size(); ++slot)
        {
            battlefield_object_record& object = _records[slot];
            if(object.type != 1 && object.type != 2)
            {
                continue;
            }
            if(object.duration_ticks > 0)
            {
                --object.duration_ticks;
            }
            if(object.duration_ticks != 0)
            {
                continue;
            }
            events[event_count] = {
                object.type == 1 ?
                        battlefield_object_tick_kind::type_1_due :
                        battlefield_object_tick_kind::type_2_expired,
                slot,
                object,
            };
            ++event_count;
            object = {};
        }
        return event_count;
    }

    [[nodiscard]] bool free(std::uint8_t slot)
    {
        if(slot == 0 || slot >= _records.size() || _records[slot].type == 0)
        {
            return false;
        }
        _records[slot] = {};
        return true;
    }

    [[nodiscard]] const battlefield_object_record* record(
            std::uint8_t slot) const
    {
        return slot < _records.size() ? &_records[slot] : nullptr;
    }

    constexpr bool operator==(
            const battlefield_object_table&) const = default;

private:
    std::array<battlefield_object_record, capacity> _records = {};
};

}

#endif
