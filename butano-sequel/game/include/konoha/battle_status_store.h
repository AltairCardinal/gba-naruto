#ifndef KONOHA_BATTLE_STATUS_STORE_H
#define KONOHA_BATTLE_STATUS_STORE_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{

inline constexpr std::uint8_t no_status_slot = 0xFF;

struct status_record
{
    std::uint8_t code_with_flags = 0;
    std::uint8_t raw_parameter_1 = 0;
    std::uint8_t duration_ticks = 0;
    std::uint8_t raw_parameter_3_low5 = 0;
    std::uint8_t raw_parameter_4 = 0;
    std::uint8_t unwritten_by_upsert = 0;
    std::uint16_t value_u16 = 0;

    [[nodiscard]] constexpr std::uint8_t code() const
    {
        return code_with_flags & 0x3F;
    }

    [[nodiscard]] constexpr bool active() const
    {
        return code() != 0;
    }

    constexpr bool operator==(const status_record&) const = default;
};

static_assert(sizeof(status_record) == 8);

enum class status_remove_mode : std::uint8_t
{
    consume_without_event = 0,
    preserve_removed_event = 1,
};

class battle_status_store
{
public:
    [[nodiscard]] std::uint8_t find(std::uint8_t code) const
    {
        const std::uint8_t masked = code & 0x3F;
        for(std::uint8_t index = 0; index < _active.size(); ++index)
        {
            if(_active[index].active() && _active[index].code() == masked)
            {
                return index;
            }
        }
        return no_status_slot;
    }

    [[nodiscard]] bool upsert(status_record record)
    {
        if(! record.active())
        {
            return false;
        }
        const std::uint8_t existing = find(record.code());
        if(existing != no_status_slot)
        {
            status_record& current = _active[existing];
            if(record.code() == 0x3F)
            {
                if(current.duration_ticks == 0 ||
                        current.duration_ticks >= record.duration_ticks)
                {
                    return true;
                }
            }
            current = record;
            return true;
        }
        for(status_record& slot : _active)
        {
            if(! slot.active())
            {
                slot = record;
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] bool remove(std::uint8_t code, status_remove_mode mode)
    {
        const std::uint8_t index = find(code);
        if(index == no_status_slot)
        {
            return false;
        }
        const status_record removed = _active[index];
        if(mode == status_remove_mode::preserve_removed_event)
        {
            for(status_record& slot : _removed)
            {
                if(! slot.active())
                {
                    slot = removed;
                    break;
                }
            }
        }
        _active[index] = {};
        return true;
    }

    [[nodiscard]] int tick_side_end()
    {
        int removed_count = 0;
        for(std::size_t index = 0; index < _active.size(); ++index)
        {
            status_record& slot = _active[index];
            if(! slot.active() || slot.duration_ticks == 0)
            {
                continue;
            }
            --slot.duration_ticks;
            if(slot.duration_ticks == 0)
            {
                const std::uint8_t code = slot.code();
                if(remove(code, status_remove_mode::preserve_removed_event))
                {
                    ++removed_count;
                }
            }
        }
        return removed_count;
    }

    [[nodiscard]] const status_record* active(std::size_t index) const
    {
        return index < _active.size() && _active[index].active() ? &_active[index] : nullptr;
    }

    [[nodiscard]] const status_record* removed(std::size_t index) const
    {
        return index < _removed.size() && _removed[index].active() ? &_removed[index] : nullptr;
    }

    [[nodiscard]] std::size_t active_count() const
    {
        return _count(_active);
    }

    [[nodiscard]] std::size_t removed_count() const
    {
        return _count(_removed);
    }

    constexpr bool operator==(const battle_status_store&) const = default;

private:
    [[nodiscard]] static std::size_t _count(const std::array<status_record, 16>& records)
    {
        std::size_t result = 0;
        for(const status_record& record : records)
        {
            result += record.active();
        }
        return result;
    }

    std::array<status_record, 16> _active = {};
    std::array<status_record, 16> _removed = {};
};

}

#endif
