"""Pure decoder for the frozen bounded Thumb dispatcher contract."""

import hashlib


ROM_BASE = 0x08000000
PREFIX_HALFWORDS = 13
PREFIX_SIZE = PREFIX_HALFWORDS * 2
OUTPUT_KEYS = {
    "root",
    "prefix_range",
    "instructions",
    "literal_bindings",
    "state_base_value",
    "state_pointer_field_offset",
    "command_field_offset",
    "subtract",
    "maximum_index",
    "default_target",
    "table_range",
    "table_sha256",
    "table_entries",
    "input_domain",
}


def _read_u16(rom, offset):
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("Thumb halfword is truncated")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _read_u32(rom, offset):
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError("literal or table word is truncated")
    return int.from_bytes(rom[offset : offset + 4], "little")


def _overlaps(first, second):
    return first[0] < second[1] and second[0] < first[1]


def _sign_extend(value, width):
    sign = 1 << (width - 1)
    return (value ^ sign) - sign


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _literal_target(source, opcode, rom_length):
    target = ((source + 4) & ~3) + (opcode & 0xFF) * 4
    _require(target % 4 == 0, "literal is not word aligned")
    _require(0 <= target <= rom_length - 4, "literal leaves ROM")
    return target


def _validate_rom(rom):
    _require(isinstance(rom, (bytes, bytearray, memoryview)), "rom must be bytes-like")
    return bytes(rom)


def _validate_data_domains(prefix, literals, table, default_target, rom_length):
    ranges = [prefix, literals[0], literals[1], table]
    for index, first in enumerate(ranges):
        _require(first[0] < first[1], "empty data range")
        for second in ranges[index + 1 :]:
            _require(not _overlaps(first, second), "dispatcher data ranges overlap")
    _require(0 <= default_target <= rom_length - 2, "BHI target leaves ROM")
    _require(default_target % 2 == 0, "BHI target is not halfword aligned")
    for data_range in ranges:
        _require(
            not (data_range[0] <= default_target < data_range[1]),
            "BHI target enters dispatcher data",
        )


def _decode_prefix(rom, root):
    _require(isinstance(root, int) and not isinstance(root, bool), "root must be an integer")
    _require(root % 2 == 0, "root must be halfword aligned")
    _require(root >= 0 and root + PREFIX_SIZE <= len(rom), "prefix leaves ROM")
    words = [_read_u16(rom, root + 2 * index) for index in range(PREFIX_HALFWORDS)]

    _require(words[0] == 0xB5F0, "wrong push prefix")
    _require(words[1] & 0xF800 == 0x4800 and (words[1] >> 8) & 7 == 0, "wrong state literal load")
    _require(words[2] & 0xF800 == 0x3000 and (words[2] >> 8) & 7 == 0, "wrong state field add")
    _require(words[3] == 0x6800, "wrong state load")
    _require(
        words[4] & 0xF800 == 0x7800
        and words[4] & 7 == 0
        and (words[4] >> 3) & 7 == 0,
        "wrong command byte load",
    )
    _require(words[5] & 0xF800 == 0x3800 and (words[5] >> 8) & 7 == 0, "wrong subtract")
    _require(words[6] & 0xF800 == 0x2800 and (words[6] >> 8) & 7 == 0, "wrong comparison")
    _require(words[7] & 0xF000 == 0xD000 and (words[7] >> 8) & 0xF == 8, "wrong unsigned BHI")
    _require(words[8] == 0x0080, "wrong LSL scale")
    _require(words[9] & 0xF800 == 0x4800 and (words[9] >> 8) & 7 == 1, "wrong table literal load")
    _require(words[10] == 0x1840, "wrong table address add")
    _require(words[11] == 0x6800, "wrong table load")
    _require(words[12] == 0x4687, "wrong retaining Thumb PC write")

    instructions = [
        {
            "offset": root + 2 * index,
            "size": 2,
            "raw_hex": rom[root + 2 * index : root + 2 * index + 2].hex(),
        }
        for index in range(PREFIX_HALFWORDS)
    ]
    state_literal = _literal_target(root + 2, words[1], len(rom))
    table_literal = _literal_target(root + 18, words[9], len(rom))
    state_field = words[2] & 0xFF
    command_field = (words[4] >> 6) & 0x1F
    subtract = words[5] & 0xFF
    maximum = words[6] & 0xFF
    _require(subtract + maximum <= 0xFF, "u8 command witness range overflows")

    branch_delta = _sign_extend(words[7] & 0xFF, 8) << 1
    default_target = root + 14 + 4 + branch_delta
    return (
        instructions,
        state_literal,
        table_literal,
        state_field,
        command_field,
        subtract,
        maximum,
        default_target,
    )


def decode_dispatch(rom: bytes, root: int) -> dict:
    """Decode one exact 13-halfword Thumb dispatcher without filesystem access."""

    data = _validate_rom(rom)
    (
        instructions,
        state_literal,
        table_literal,
        state_field,
        command_field,
        subtract,
        maximum,
        default_target,
    ) = _decode_prefix(data, root)
    prefix = (root, root + PREFIX_SIZE)
    literal_ranges = [
        (state_literal, state_literal + 4),
        (table_literal, table_literal + 4),
    ]
    table_pointer = _read_u32(data, table_literal)
    _require(ROM_BASE <= table_pointer < ROM_BASE + len(data), "table pointer leaves ROM")
    _require(table_pointer % 4 == 0, "table pointer is not word aligned")
    table_start = table_pointer - ROM_BASE
    table_stop = table_start + (maximum + 1) * 4
    _require(table_stop <= len(data), "table leaves ROM")
    table = (table_start, table_stop)
    _validate_data_domains(prefix, literal_ranges, table, default_target, len(data))

    table_entries = []
    for slot_index in range(maximum + 1):
        entry_offset = table_start + slot_index * 4
        raw_pointer = _read_u32(data, entry_offset)
        _require(ROM_BASE <= raw_pointer < ROM_BASE + len(data), "table target leaves ROM")
        _require(raw_pointer % 2 == 0, "table target is not an even Thumb address")
        target = raw_pointer - ROM_BASE
        _require(
            all(not (start <= target < stop) for start, stop in [prefix, *literal_ranges, table]),
            "table target enters dispatcher data",
        )
        table_entries.append(
            {
                "slot_index": slot_index,
                "entry_offset": entry_offset,
                "raw_pointer": raw_pointer,
                "target": target,
                "mode": "thumb",
            }
        )

    literal_bindings = [
        [root + 2, state_literal, data[state_literal : state_literal + 4].hex()],
        [root + 18, table_literal, data[table_literal : table_literal + 4].hex()],
    ]
    entry_targets = [entry["target"] for entry in table_entries]
    input_domain = []
    for command in range(256):
        index_u32 = (command - subtract) & 0xFFFFFFFF
        if index_u32 > maximum:
            slot_index = None
            target = default_target
        else:
            slot_index = index_u32
            target = entry_targets[slot_index]
        input_domain.append(
            {
                "command": command,
                "index_u32": index_u32,
                "slot_index": slot_index,
                "target": target,
            }
        )

    result = {
        "root": root,
        "prefix_range": [root, root + PREFIX_SIZE],
        "instructions": instructions,
        "literal_bindings": literal_bindings,
        "state_base_value": _read_u32(data, state_literal),
        "state_pointer_field_offset": state_field,
        "command_field_offset": command_field,
        "subtract": subtract,
        "maximum_index": maximum,
        "default_target": default_target,
        "table_range": [table_start, table_stop],
        "table_sha256": hashlib.sha256(data[table_start:table_stop]).hexdigest(),
        "table_entries": table_entries,
        "input_domain": input_domain,
    }
    _require(set(result) == OUTPUT_KEYS, "dispatcher output schema changed")
    return result
