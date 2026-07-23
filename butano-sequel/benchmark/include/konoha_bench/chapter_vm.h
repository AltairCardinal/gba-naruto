#ifndef KONOHA_BENCH_CHAPTER_VM_H
#define KONOHA_BENCH_CHAPTER_VM_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha_bench
{

enum class chapter_opcode : std::uint8_t
{
    emit_text = 1,
    set_flag = 2,
    jump_if_flag = 3,
    wait = 4,
    start_battle = 5,
    end = 255,
};

enum class event_kind
{
    text,
    battle,
};

struct chapter_event
{
    event_kind kind;
    std::uint8_t value;

    constexpr bool operator==(const chapter_event&) const = default;
};

enum class vm_status
{
    running,
    emitted,
    waiting,
    battle,
    ended,
    error,
};

enum class vm_error
{
    none,
    truncated_operand,
    invalid_opcode,
    invalid_flag,
    jump_out_of_range,
    event_overflow,
    step_budget_exhausted,
    missing_end,
};

template<std::size_t ProgramCapacity, std::size_t EventCapacity>
class chapter_vm
{
public:
    chapter_vm(
            const std::array<std::uint8_t, ProgramCapacity>& program,
            std::size_t program_size) :
        _program(program),
        _program_size(program_size <= ProgramCapacity ? program_size : ProgramCapacity)
    {
    }

    vm_status run(std::size_t step_budget)
    {
        if(_terminal_status == vm_status::ended || _terminal_status == vm_status::error)
        {
            return _terminal_status;
        }
        if(_waiting)
        {
            return vm_status::waiting;
        }
        for(std::size_t step = 0; step < step_budget; ++step)
        {
            if(_pc >= _program_size)
            {
                return fail(vm_error::missing_end);
            }
            const auto opcode = static_cast<chapter_opcode>(_program[_pc++]);
            switch(opcode)
            {
            case chapter_opcode::emit_text:
            {
                std::uint8_t text_id = 0;
                if(! read_byte(text_id))
                {
                    return fail(vm_error::truncated_operand);
                }
                if(! append_event({ event_kind::text, text_id }))
                {
                    return fail(vm_error::event_overflow);
                }
                return vm_status::emitted;
            }

            case chapter_opcode::set_flag:
            {
                std::uint8_t flag_id = 0;
                if(! read_byte(flag_id))
                {
                    return fail(vm_error::truncated_operand);
                }
                if(flag_id >= _flags.size())
                {
                    return fail(vm_error::invalid_flag);
                }
                _flags[flag_id] = true;
                break;
            }

            case chapter_opcode::jump_if_flag:
            {
                std::uint8_t flag_id = 0;
                std::uint8_t target = 0;
                if(! read_byte(flag_id) || ! read_byte(target))
                {
                    return fail(vm_error::truncated_operand);
                }
                if(flag_id >= _flags.size())
                {
                    return fail(vm_error::invalid_flag);
                }
                if(target >= _program_size)
                {
                    return fail(vm_error::jump_out_of_range);
                }
                if(_flags[flag_id])
                {
                    _pc = target;
                }
                break;
            }

            case chapter_opcode::wait:
                _waiting = true;
                return vm_status::waiting;

            case chapter_opcode::start_battle:
            {
                std::uint8_t battle_id = 0;
                if(! read_byte(battle_id))
                {
                    return fail(vm_error::truncated_operand);
                }
                if(! append_event({ event_kind::battle, battle_id }))
                {
                    return fail(vm_error::event_overflow);
                }
                return vm_status::battle;
            }

            case chapter_opcode::end:
                _terminal_status = vm_status::ended;
                return _terminal_status;

            default:
                return fail(vm_error::invalid_opcode);
            }
        }
        return fail(vm_error::step_budget_exhausted);
    }

    bool resume()
    {
        if(! _waiting)
        {
            return false;
        }
        _waiting = false;
        return true;
    }

    [[nodiscard]] bool flag(std::size_t flag_id) const
    {
        return flag_id < _flags.size() && _flags[flag_id];
    }

    [[nodiscard]] std::size_t pc() const
    {
        return _pc;
    }

    [[nodiscard]] std::size_t event_count() const
    {
        return _event_count;
    }

    [[nodiscard]] chapter_event event(std::size_t index) const
    {
        return _events[index];
    }

    [[nodiscard]] vm_error error() const
    {
        return _error;
    }

private:
    bool read_byte(std::uint8_t& value)
    {
        if(_pc >= _program_size)
        {
            return false;
        }
        value = _program[_pc++];
        return true;
    }

    bool append_event(chapter_event value)
    {
        if(_event_count >= EventCapacity)
        {
            return false;
        }
        _events[_event_count++] = value;
        return true;
    }

    vm_status fail(vm_error error)
    {
        _error = error;
        _terminal_status = vm_status::error;
        return _terminal_status;
    }

    std::array<std::uint8_t, ProgramCapacity> _program;
    std::size_t _program_size;
    std::size_t _pc = 0;
    std::array<bool, 32> _flags = {};
    std::array<chapter_event, EventCapacity> _events = {};
    std::size_t _event_count = 0;
    vm_status _terminal_status = vm_status::running;
    vm_error _error = vm_error::none;
    bool _waiting = false;
};

}

#endif
