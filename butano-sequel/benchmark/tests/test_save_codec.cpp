#include "konoha_bench/save_codec.h"

#include <cassert>

using namespace konoha_bench;

int main()
{
    const save_payload payload{ 12, 34567, 91, 0x10203040 };
    const save_slot first = encode_slot(payload, 7);
    const save_slot second = encode_slot(payload, 7);
    assert(first == second);

    const decode_result decoded = decode_slot(first.bytes.data(), first.bytes.size());
    assert(decoded.valid());
    assert(! decoded.used_default);
    assert(decoded.payload == payload);
    assert(decoded.generation == 7);

    const decode_result truncated = decode_slot(first.bytes.data(), first.bytes.size() - 1);
    assert(truncated.error == save_error::wrong_size);

    save_slot bad_magic = first;
    bad_magic.bytes[0] = 0;
    assert(decode_slot(bad_magic).error == save_error::bad_magic);

    save_slot bad_version = first;
    bad_version.bytes[4] = 2;
    assert(decode_slot(bad_version).error == save_error::unsupported_version);

    save_slot bad_crc = first;
    bad_crc.bytes[20] ^= 0x80;
    assert(decode_slot(bad_crc).error == save_error::bad_crc);

    const save_slot blank;
    const decode_result new_game = load_newest(blank, blank);
    assert(new_game.valid());
    assert(new_game.used_default);
    assert(new_game.payload == default_save());
    assert(new_game.generation == 0);

    const save_payload older_payload{ 3, 100, 2, 4 };
    const save_payload newer_payload{ 4, 200, 3, 8 };
    const save_slot older = encode_slot(older_payload, 10);
    save_slot newer = encode_slot(newer_payload, 11);
    const decode_result newest = load_newest(older, newer);
    assert(newest.valid() && ! newest.used_default);
    assert(newest.payload == newer_payload);
    assert(newest.generation == 11);

    newer.bytes[31] ^= 1;
    const decode_result recovered = load_newest(older, newer);
    assert(recovered.valid());
    assert(recovered.payload == older_payload);
    assert(recovered.generation == 10);
}
