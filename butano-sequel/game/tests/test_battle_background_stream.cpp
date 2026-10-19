#include "konoha/battle_background_stream.h"

#include <array>
#include <cassert>

using namespace konoha;

int main()
{
    battle_background_stream stream;
    const std::array<int, 4> battle_11_origins = {
        0, 32, 0, 0,
    };
    assert(stream.prepare(
                    544,
                    240,
                    battle_11_origins,
                    2)
                   .success());
    assert(stream.chunk_count() == 2);
    assert(stream.chunk_index() == 0);
    assert(stream.chunk_origin() == 0);

    battle_background_stream_update update =
            stream.update(392);
    assert(! update.changed);
    assert(update.chunk_index == 0);
    update = stream.update(393);
    assert(update.changed);
    assert(update.chunk_index == 1);
    assert(stream.chunk_origin() == 32);
    update = stream.update(392);
    assert(! update.changed);
    assert(update.chunk_index == 1);
    update = stream.update(152);
    assert(! update.changed);
    assert(update.chunk_index == 1);
    update = stream.update(151);
    assert(update.changed);
    assert(update.chunk_index == 0);

    const std::array<int, 4> one_origin = {
        0, 0, 0, 0,
    };
    assert(stream.prepare(
                    288, 240, one_origin, 1)
                   .success());
    assert(! stream.update(1000).changed);
    assert(stream.chunk_index() == 0);

    const std::array<int, 4> gap = {
        0, 300, 0, 0,
    };
    const battle_background_stream_result gap_result =
            stream.prepare(800, 240, gap, 2);
    assert(gap_result.error ==
           battle_background_stream_error::
                   viewport_gap);

    const std::array<int, 4> wrong_first = {
        1, 32, 0, 0,
    };
    assert(stream.prepare(
                    544,
                    240,
                    wrong_first,
                    2)
                   .error ==
           battle_background_stream_error::
                   invalid_origin);
    assert(stream.prepare(
                    544,
                    513,
                    battle_11_origins,
                    2)
                   .error ==
           battle_background_stream_error::
                   invalid_viewport);
    assert(stream.prepare(
                    544,
                    240,
                    battle_11_origins,
                    0)
                   .error ==
           battle_background_stream_error::
                   invalid_chunk_count);
}
