#ifndef KONOHA_BENCH_ACTION_STATE_MACHINE_H
#define KONOHA_BENCH_ACTION_STATE_MACHINE_H

namespace konoha_bench
{

enum class action_phase
{
    unit_select,
    move_preview,
    action_menu,
    target_select,
    committed,
    turn_end,
};

enum class action_input
{
    select_unit,
    confirm_move,
    choose_action,
    confirm_target,
    cancel,
    end_turn,
};

struct action_result
{
    bool accepted;
    action_phase from;
    action_phase to;
};

class action_state_machine
{
public:
    [[nodiscard]] action_phase phase() const
    {
        return _phase;
    }

    [[nodiscard]] bool committed() const
    {
        return _phase == action_phase::committed;
    }

    action_result step(action_input input)
    {
        const action_phase from = _phase;
        action_phase next = from;

        switch(from)
        {
        case action_phase::unit_select:
            if(input == action_input::select_unit)
            {
                next = action_phase::move_preview;
            }
            else if(input == action_input::end_turn)
            {
                next = action_phase::turn_end;
            }
            break;

        case action_phase::move_preview:
            if(input == action_input::confirm_move)
            {
                next = action_phase::action_menu;
            }
            else if(input == action_input::cancel)
            {
                next = action_phase::unit_select;
            }
            break;

        case action_phase::action_menu:
            if(input == action_input::choose_action)
            {
                next = action_phase::target_select;
            }
            else if(input == action_input::cancel)
            {
                next = action_phase::move_preview;
            }
            break;

        case action_phase::target_select:
            if(input == action_input::confirm_target)
            {
                next = action_phase::committed;
            }
            else if(input == action_input::cancel)
            {
                next = action_phase::action_menu;
            }
            break;

        case action_phase::committed:
        case action_phase::turn_end:
            break;

        default:
            break;
        }

        const bool accepted = next != from;
        _phase = next;
        return { accepted, from, next };
    }

private:
    action_phase _phase = action_phase::unit_select;
};

}

#endif
