#include "konoha/battle_presentation.h"

#include <cassert>

using namespace konoha;

int main()
{
    presentation_queue<3> queue;
    assert(! queue.push_automatic(presentation_cue::black, 0));
    assert(! queue.push_wait_for_input(presentation_cue::black, false));
    assert(queue.empty());

    assert(queue.push_automatic(presentation_cue::start_title, 2));
    assert(queue.push_automatic(presentation_cue::black, 12));
    assert(queue.push_wait_for_input(presentation_cue::entrance_dialogue, true));
    assert(! queue.push_automatic(presentation_cue::shuriken_transition, 8));
    assert(queue.size() == 3);

    const presentation_step* current = queue.current();
    assert(current);
    assert(current->cue == presentation_cue::start_title);
    assert(current->mode == presentation_mode::automatic);
    assert(current->visible);
    assert(! queue.confirm());
    assert(queue.tick());
    assert(queue.current()->remaining_frames == 1);
    assert(queue.tick());

    current = queue.current();
    assert(current);
    assert(current->cue == presentation_cue::black);
    assert(current->mode == presentation_mode::automatic);
    assert(! current->visible);
    for(int frame = 0; frame < 12; ++frame)
    {
        assert(queue.tick());
    }

    current = queue.current();
    assert(current);
    assert(current->cue == presentation_cue::entrance_dialogue);
    assert(current->mode == presentation_mode::wait_for_input);
    assert(current->visible);
    assert(! queue.tick());
    assert(queue.confirm());
    assert(queue.empty());
    assert(! queue.tick());
    assert(! queue.confirm());

    assert(queue.push_automatic(presentation_cue::shuriken_transition, 1));
    assert(queue.tick());
    assert(queue.empty());
}
