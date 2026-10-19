"""Generate deterministic, answer-free smoke challenge packets."""

from __future__ import annotations

import binascii
import hashlib
import json
import random
import struct
from dataclasses import dataclass
from pathlib import Path

from tools.thumb_branch import encode_thumb_bl


SMOKE_CHALLENGE_IDS = (
    "fixed-pointer-table",
    "arm-thumb-control-flow",
    "tdd-manifest-contract",
)

SUBMISSION_SCHEMA = "reverse-benchmark-submission-v1"
PACKET_CONTRACT_SCHEMA = "reverse-benchmark-public-contract-v2"
RESULT_JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
REPRODUCTION_TIMEOUT_SECONDS = 15
MAX_CANDIDATE_FILE_BYTES = 4 * 1024 * 1024

_AGENT_POLICY = """# Benchmark agent policy

- Work only inside this challenge packet. Do not inspect parent or unrelated paths.
- Network access, external search, plugins, skills, and prior sessions are forbidden.
- Treat every input as immutable and write all deliverables below `submission/`.
- Treat `CONTRACT.json` as the authoritative machine-readable output contract.
- Use red-green-refactor: first create a test that fails for the intended missing behavior,
  then implement the smallest solution, then rerun the tests after cleanup.
- Do not guess hidden checks. Derive claims from the supplied bytes and document boundaries.
- Finish by running your tests and the reproduction command from `TASK.md`.
"""


_PUBLIC_CONTRACT_GUIDANCE = """
`CONTRACT.json` is authoritative for exact output paths, JSON field names,
types, enums, required fields, field semantics, comparison rules, scoring, and
whether extra fields are allowed. Follow it exactly; semantically similar field
names are not interchangeable.

Tests must match `submission/tests/test*.py`. The candidate-test phase copies the
frozen packet inputs, `INPUTS.json`, `submission/solution.py`, and matching test
files into a clean directory. Tests must not depend on `submission/result.json`,
and tests must not depend on `submission/run_manifest.json` or unlisted helper
files. Tests must reject both mutants listed in `CONTRACT.json`.

The solution-reproduction phase runs the supplied packet and one distinct valid
same-contract unseen packet. It copies only frozen packet inputs, `INPUTS.json`,
and `submission/solution.py`; tests and other submission files are absent. The
exact command, cwd, limits, comparison rules, and any failure cases are in
`CONTRACT.json`.
"""


@dataclass(frozen=True, slots=True)
class PreparedPacket:
    challenge_id: str
    root: Path
    input_hashes: dict[str, str]
    secret: dict[str, object]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _address_schema(description: str | None = None) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "string",
        "pattern": "^0x[0-9A-F]{8}$",
    }
    if description is not None:
        schema["description"] = description
    return schema


def _scope_schema(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _pointer_result_schema() -> dict[str, object]:
    non_null_record = {
        "type": "object",
        "additionalProperties": False,
        "required": ["slot", "pointer", "text", "length", "sha256"],
        "properties": {
            "slot": {
                "type": "integer",
                "minimum": 0,
                "maximum": 7,
                "description": "Zero-based table slot; equals this record's array index.",
            },
            "pointer": _address_schema(
                "Raw unsigned 32-bit slot value in canonical uppercase address form."
            ),
            "text": {
                "type": "string",
                "description": "Strict ASCII decoding of consumed_bytes.",
            },
            "length": {
                "type": "integer",
                "minimum": 0,
                "description": "Raw byte count of consumed_bytes, excluding NUL.",
            },
            "sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
                "description": (
                    "Lowercase SHA-256 hexadecimal digest of consumed_bytes exactly."
                ),
            },
        },
    }
    null_record = {
        "type": "object",
        "additionalProperties": False,
        "required": ["slot", "pointer", "text"],
        "properties": {
            "slot": {
                "type": "integer",
                "minimum": 0,
                "maximum": 7,
                "description": "Zero-based table slot; equals this record's array index.",
            },
            "pointer": {"type": "null"},
            "text": {"type": "null"},
        },
    }
    properties = {
        "schema": {"const": "fixed-pointer-table-result-v1"},
        "base_address": {
            "const": "0x08004000",
            "description": "Address mapped to file offset zero.",
        },
        "table_offset": {
            "const": 0x20,
            "description": "Byte offset of the fixed little-endian pointer table.",
        },
        "entry_count": {
            "const": 8,
            "description": "Exact number of table slots and records.",
        },
        "records": {
            "type": "array",
            "minItems": 8,
            "maxItems": 8,
            "description": (
                "Exactly one entry per zero-based table slot in ascending slot order; "
                "preserve null slots and duplicate pointers."
            ),
            "items": {"oneOf": [null_record, non_null_record]},
        },
        "scope": _scope_schema(
            {
                "terminator": {"const": "first-nul"},
                "bytes_after_terminator_classified": {"const": False},
            }
        ),
    }
    return {
        "$schema": RESULT_JSON_SCHEMA_DIALECT,
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _control_flow_result_schema() -> dict[str, object]:
    edge_properties = {
        "source": _address_schema(
            "Normalized instruction address with bit zero clear."
        ),
        "target": _address_schema(
            "Normalized transfer target address with bit zero clear."
        ),
        "source_mode": {"enum": ["thumb", "arm"]},
        "target_mode": {"enum": ["thumb", "arm"]},
        "kind": {"enum": ["bl", "b", "bx-pc"]},
    }
    terminal_properties = {
        "address": _address_schema(
            "Normalized address of the reachable terminal ARM BX lr."
        ),
        "mode": {"const": "arm"},
        "instruction": {"const": "bx-lr"},
    }
    properties = {
        "schema": {"const": "arm-thumb-control-flow-result-v1"},
        "base_address": {
            "const": "0x08010000",
            "description": "Address mapped to file offset zero.",
        },
        "edges": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "uniqueItems": True,
            "description": (
                "Order-insensitive unique set of reachable explicit transfer "
                "instructions; repeated arrival at one state does not duplicate an edge."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(edge_properties),
                "properties": edge_properties,
            },
        },
        "terminal": _scope_schema(terminal_properties),
        "scope": _scope_schema(
            {
                "thumb_ranges": {
                    "const": [["0x08010000", "0x08010014"]],
                    "description": (
                        "Declared half-open Thumb decode envelope copied verbatim; "
                        "not a reached-byte span."
                    ),
                },
                "arm_ranges": {
                    "const": [["0x08010014", "0x08010024"]],
                    "description": (
                        "Declared half-open ARM decode envelope copied verbatim; "
                        "not a reached-byte span."
                    ),
                },
                "random_filler_classified": {"const": False},
            }
        ),
    }
    return {
        "$schema": RESULT_JSON_SCHEMA_DIALECT,
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _manifest_result_schema() -> dict[str, object]:
    properties = {
        "schema": {"const": "tdd-manifest-contract-result-v1"},
        "accepted_sequences": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "integer"},
            "description": (
                "Sequence numbers of every successfully validated non-blank record "
                "from file start through the first stop, preserving physical line "
                "order; the consumed stop is the final element."
            ),
        },
        "value_count": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Number of consumed kind=value records; excludes the stop record."
            ),
        },
        "value_sum": {
            "type": "integer",
            "description": (
                "Arithmetic sum of value for consumed kind=value records only."
            ),
        },
        "first_stop_sequence": {
            "type": "integer",
            "description": (
                "Sequence of the first consumed kind=stop record and final "
                "accepted_sequences element."
            ),
        },
        "ignored_after_stop": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Number of non-empty physical lines after the first stop; count raw "
                "lines without decoding or parsing; whitespace-only lines do not count."
            ),
        },
        "all_consumed_crc32_valid": {"const": True},
        "scope": _scope_schema(
            {
                "stop_is_consumed": {"const": True},
                "records_after_stop_interpreted": {"const": False},
            }
        ),
    }
    return {
        "$schema": RESULT_JSON_SCHEMA_DIALECT,
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


_RESULT_SCHEMAS = {
    "fixed-pointer-table": _pointer_result_schema,
    "arm-thumb-control-flow": _control_flow_result_schema,
    "tdd-manifest-contract": _manifest_result_schema,
}


def _challenge_semantics(challenge_id: str) -> dict[str, object]:
    if challenge_id == "fixed-pointer-table":
        return {
            "address_mapping": "file offset o maps to base_address + o",
            "records_order": "records[i] describes zero-based table slot i",
            "pointer_offset": "pointer - base_address",
            "valid_input_guarantee": (
                "every supplied non-null pointer is mapped and reaches NUL before EOF"
            ),
            "consumed_bytes": (
                "bytes from pointer_offset up to but excluding the first NUL"
            ),
            "derived_fields": {
                "text": "strict ASCII decoding of consumed_bytes",
                "length": "raw byte count of consumed_bytes",
                "sha256": "SHA-256 lowercase hex of consumed_bytes exactly",
            },
        }
    if challenge_id == "arm-thumb-control-flow":
        return {
            "endianness": "little-endian",
            "traversal_state": "normalized instruction address plus mode",
            "state_visit_policy": "process each traversal state at most once",
            "address_normalization": (
                "bit zero clear; execution state is carried only by mode fields"
            ),
            "thumb_bl_target": (
                "S + 4 + sign_extend((imm_hi << 12) | (imm_lo << 1), 23)"
            ),
            "thumb_bl_continuation": "S + 4; schedule but do not emit as an edge",
            "thumb_b_target": "S + 4 + sign_extend(imm11 << 1, 12)",
            "thumb_bx_pc_target": "(S + 4) & ~3; switch to ARM",
            "arm_b_target": "S + 8 + sign_extend(imm24 << 2, 26)",
            "terminal": "reachable ARM BX lr is recorded only in terminal",
            "scope_ranges": (
                "copy declared half-open decoder envelopes, not reached-byte spans"
            ),
        }
    if challenge_id == "tdd-manifest-contract":
        record_common = {
            "sequence": {"type": "integer"},
            "crc32": {"type": "string", "pattern": "^[0-9a-f]{8}$"},
        }
        return {
            "consumed_order": "physical non-blank line order; never sort",
            "blank_before_stop": "invalid and must fail closed",
            "sequence_rule": (
                "strictly increasing non-boolean integers; gaps allowed; stop participates"
            ),
            "consumed_record_json_schema": {
                "$schema": RESULT_JSON_SCHEMA_DIALECT,
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["sequence", "kind", "value", "crc32"],
                        "properties": {
                            **record_common,
                            "kind": {"const": "value"},
                            "value": {"type": "integer"},
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["sequence", "kind", "value", "crc32"],
                        "properties": {
                            **record_common,
                            "kind": {"const": "stop"},
                            "value": {"const": 0},
                        },
                    },
                ],
            },
            "crc32": (
                "IEEE CRC-32 of ASCII '<sequence>:<kind>:<value>' using canonical "
                "base-10 JSON integers, rendered as exactly eight lowercase hex digits"
            ),
            "stop": (
                "consume and validate the first stop; EOF before stop fails closed"
            ),
            "after_stop": (
                "count non-empty raw physical lines only; do not decode, parse, "
                "CRC-check, or sequence-check; whitespace-only lines do not count"
            ),
            "fail_closed": "non-zero exit and output absent or byte-identical",
        }
    raise ValueError(f"unknown challenge semantics: {challenge_id}")


def _verification_contract(challenge_id: str) -> dict[str, object]:
    reproduction: dict[str, object] = {
        "valid_packets": ["supplied", "distinct-same-contract-unseen"],
        "copied_paths": [
            "frozen packet inputs",
            "INPUTS.json",
            "submission/solution.py",
        ],
        "excluded_paths": ["submission/tests/**", "other submission files"],
        "command": (
            "python -B submission/solution.py --packet-root <clean-packet-root> "
            "--output <clean-packet-root>/reproduced-result.json"
        ),
        "cwd": "<clean-packet-root>",
        "timeout_seconds": REPRODUCTION_TIMEOUT_SECONDS,
        "max_output_bytes": MAX_CANDIDATE_FILE_BYTES,
        "output_contract": "regular UTF-8 JSON file",
        "frozen_inputs_must_remain_byte_identical": True,
        "failure_cases": [],
    }
    if challenge_id == "tdd-manifest-contract":
        reproduction["failure_cases"] = [
            "invalid-consumed-crc32",
            "noncanonical-consumed-crc32",
            "duplicate-consumed-sequence",
            "missing-stop",
        ]
    return {
        "score_points": {
            "input_integrity": 15,
            "result_correctness": 40,
            "run_manifest": 10,
            "solution_reproduction": 20,
            "candidate_tests": 15,
        },
        "missing_result_or_mutated_input_forces_zero": True,
        "result_comparison": {
            "json_schema_required": True,
            "object_key_order": "ignored",
            "array_order_default": "significant",
            "arm-thumb-control-flow.edges": "order-insensitive unique set",
        },
        "solution_reproduction": reproduction,
        "candidate_tests": {
            "runner": "python -B -m unittest discover -s submission/tests",
            "mutants_must_fail": ["empty-result", "hardcoded-supplied-result"],
        },
    }


def _public_contract(challenge_id: str) -> dict[str, object]:
    return {
        "schema": PACKET_CONTRACT_SCHEMA,
        "challenge_id": challenge_id,
        "challenge_semantics": _challenge_semantics(challenge_id),
        "verification": _verification_contract(challenge_id),
        "deliverables": {
            "result": {
                "path": "submission/result.json",
                "json_schema": _RESULT_SCHEMAS[challenge_id](),
            },
            "solution": {
                "path": "submission/solution.py",
                "required_arguments": [
                    "--packet-root <directory>",
                    "--output <json-file>",
                ],
            },
            "tests": {
                "glob": "submission/tests/test*.py",
                "runner": "python -B -m unittest discover -s submission/tests",
                "hidden_copy": [
                    "frozen packet inputs",
                    "submission/solution.py",
                    "submission/tests/test*.py",
                ],
                "must_not_depend_on": [
                    "submission/result.json",
                    "submission/run_manifest.json",
                ],
            },
            "run_manifest": {
                "path": "submission/run_manifest.json",
                "additional_fields_allowed": False,
                "limitations_must_be_strings": True,
                "required_shape": {
                    "schema": SUBMISSION_SCHEMA,
                    "challenge_id": challenge_id,
                    "input_hashes": "copy INPUTS.json.input_hashes exactly",
                    "scope": {
                        "complete": True,
                        "limitations": ["string"],
                    },
                },
            },
        },
    }


def _pointer_packet(root: Path, rng: random.Random) -> dict[str, object]:
    base = 0x08004000
    entry_count = 8
    blob = bytearray(rng.randrange(0, 256) for _ in range(256))
    words = ["ramen", "konoha", "chakra", "leaf", "mission"]
    rng.shuffle(words)
    values = tuple(f"{word}{rng.randrange(10, 100)}" for word in words)
    offsets = (0x60, 0x70, 0x80, 0x90, 0xA0)
    for value, offset in zip(values, offsets, strict=True):
        encoded = value.encode("ascii")
        blob[offset : offset + len(encoded)] = encoded
        blob[offset + len(encoded)] = 0
        blob[offset + len(encoded) + 1 : offset + len(encoded) + 4] = b"XYZ"
    pointers = [
        base + offsets[0],
        0,
        base + offsets[2],
        base + offsets[1],
        base + offsets[0],
        base + offsets[4],
        base + offsets[3],
        0,
    ]
    rng.shuffle(pointers)
    struct.pack_into(f"<{entry_count}I", blob, 0x20, *pointers)
    input_path = root / "input/resource.bin"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(blob)
    records = []
    for slot, pointer in enumerate(pointers):
        if pointer == 0:
            records.append({"slot": slot, "pointer": None, "text": None})
            continue
        offset = pointer - base
        terminator = blob.index(0, offset)
        consumed = bytes(blob[offset:terminator])
        records.append(
            {
                "slot": slot,
                "pointer": f"0x{pointer:08X}",
                "text": consumed.decode("ascii"),
                "length": len(consumed),
                "sha256": hashlib.sha256(consumed).hexdigest(),
            }
        )
    expected = {
        "schema": "fixed-pointer-table-result-v1",
        "base_address": f"0x{base:08X}",
        "table_offset": 0x20,
        "entry_count": entry_count,
        "records": records,
        "scope": {
            "terminator": "first-nul",
            "bytes_after_terminator_classified": False,
        },
    }
    _write_text(
        root / "TASK.md",
        f"""# Fixed pointer-table consumer closure

Analyze `input/resource.bin` as a blob mapped at GBA address `0x{base:08X}`.
The fixed table starts at file offset `0x20`, has {entry_count} little-endian
32-bit slots, and uses zero as a null slot. A non-null pointer selects an ASCII
record consumed only through the first NUL byte. Bytes after that NUL remain
outside scope even if they look meaningful.

File offset `o` maps to `base_address + o`; for a non-null pointer `p`, use
`pointer_offset = p - base_address`. Every supplied non-null pointer is mapped
and reaches a NUL before EOF. `records[i]` describes zero-based slot `i`, so the
array has exactly `entry_count` entries and preserves null and duplicate slots.
For non-null slots, `consumed_bytes` begins at `pointer_offset` and ends just
before the first NUL; the NUL is excluded. `text` is strict ASCII decoding of
those bytes, `length` is their raw byte count, and `sha256` is the lowercase
SHA-256 hexadecimal digest of exactly those bytes.

Create:

- `submission/result.json` with schema `fixed-pointer-table-result-v1`, the
  mapping metadata, all slots in order, and explicit scope boundaries;
- `submission/solution.py` supporting
  `--packet-root <dir> --output <json>` and reproducing the result from input;
- `submission/tests/test_solution.py`;
- `submission/run_manifest.json` using schema `{SUBMISSION_SCHEMA}`, containing
  `challenge_id`, exact `input_hashes`, and `scope.complete/limitations`.

Do not classify bytes after the first NUL and do not omit null or duplicate slots.

{_PUBLIC_CONTRACT_GUIDANCE}
""",
    )
    return {"expected_result": expected}


def _control_flow_packet(root: Path, rng: random.Random) -> dict[str, object]:
    base = 0x08010000
    blob = bytearray(rng.randrange(0, 256) for _ in range(0x30))
    blob[0:4] = encode_thumb_bl(base, base + 0x10)
    struct.pack_into("<H", blob, 0x04, 0xE004)  # B from +0x04 to +0x10.
    struct.pack_into("<H", blob, 0x06, 0x46C0)  # NOP.
    struct.pack_into("<H", blob, 0x10, 0x4778)  # BX pc -> ARM at +0x14.
    struct.pack_into("<H", blob, 0x12, 0x46C0)  # alignment filler.
    terminal_offset = rng.choice((0x1C, 0x20))
    arm_branch_displacement = (terminal_offset - (0x14 + 8)) // 4
    struct.pack_into(
        "<I", blob, 0x14, 0xEA000000 | (arm_branch_displacement & 0x00FFFFFF)
    )
    struct.pack_into("<I", blob, terminal_offset, 0xE12FFF1E)  # ARM BX lr.
    input_path = root / "input/code.bin"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(blob)
    expected = {
        "schema": "arm-thumb-control-flow-result-v1",
        "base_address": f"0x{base:08X}",
        "edges": [
            {
                "source": f"0x{base:08X}",
                "target": f"0x{base + 0x10:08X}",
                "source_mode": "thumb",
                "target_mode": "thumb",
                "kind": "bl",
            },
            {
                "source": f"0x{base + 0x04:08X}",
                "target": f"0x{base + 0x10:08X}",
                "source_mode": "thumb",
                "target_mode": "thumb",
                "kind": "b",
            },
            {
                "source": f"0x{base + 0x10:08X}",
                "target": f"0x{base + 0x14:08X}",
                "source_mode": "thumb",
                "target_mode": "arm",
                "kind": "bx-pc",
            },
            {
                "source": f"0x{base + 0x14:08X}",
                "target": f"0x{base + terminal_offset:08X}",
                "source_mode": "arm",
                "target_mode": "arm",
                "kind": "b",
            },
        ],
        "terminal": {
            "address": f"0x{base + terminal_offset:08X}",
            "mode": "arm",
            "instruction": "bx-lr",
        },
        "scope": {
            "thumb_ranges": [[f"0x{base:08X}", f"0x{base + 0x14:08X}"]],
            "arm_ranges": [[f"0x{base + 0x14:08X}", f"0x{base + 0x24:08X}"]],
            "random_filler_classified": False,
        },
    }
    _write_text(
        root / "TASK.md",
        f"""# ARM/Thumb interwork closure

Analyze `input/code.bin`, mapped at `0x{base:08X}`. Decode only these declared
ranges: Thumb `[0x{base:08X}, 0x{base + 0x14:08X})` and ARM
`[0x{base + 0x14:08X}, 0x{base + 0x24:08X})`.

Build the direct reachable edge chain rooted at `0x{base:08X}`. Recognize Thumb
BL/B, the `BX pc` mode switch (Thumb PC is instruction address + 4, aligned for
ARM), ARM B (PC is instruction address + 8), and terminal ARM `BX lr`. Random
filler outside reachable instructions must remain unclassified.

Decode Thumb halfwords and ARM words as little-endian. Traversal state is the
pair `(normalized instruction address, mode)`; addresses have bit zero clear,
and each state is processed at most once. At source `S`, use these formulas:

- Thumb BL target: `S + 4 + sign_extend((imm_hi << 12) | (imm_lo << 1), 23)`;
- Thumb BL continuation: `S + 4`;
- Thumb B target: `S + 4 + sign_extend(imm11 << 1, 12)`;
- Thumb `BX pc` target: `(S + 4) & ~3`, switching to ARM;
- ARM B target: `S + 8 + sign_extend(imm24 << 2, 26)`.

For traversal, Thumb BL schedules both its branch target and its sequential
continuation. Emit only the explicit BL/B/BX-pc/ARM-B transfer instructions in
`edges`; do not emit an implicit return, fallthrough, or continuation edge.
Treat `edges` as an order-insensitive unique set, so a transfer instruction
reached through multiple predecessors appears once. `scope.thumb_ranges` and
`scope.arm_ranges` copy the declared half-open decoder envelopes exactly; they
are not reached-byte or classified-byte spans.

Create `submission/result.json` with schema
`arm-thumb-control-flow-result-v1`, `submission/solution.py` supporting
`--packet-root/--output`, focused unit tests, and a `{SUBMISSION_SCHEMA}` run
manifest with exact input hashes and scope.

{_PUBLIC_CONTRACT_GUIDANCE}
""",
    )
    return {"expected_result": expected}


def _manifest_packet(root: Path, rng: random.Random) -> dict[str, object]:
    records: list[dict[str, object]] = []
    values = [rng.randrange(10, 100) for _ in range(rng.randrange(3, 8))]
    sequence = rng.randrange(80, 161)
    accepted_sequences: list[int] = []
    for value in values:
        payload = f"{sequence}:value:{value}".encode("ascii")
        records.append(
            {
                "sequence": sequence,
                "kind": "value",
                "value": value,
                "crc32": f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}",
            }
        )
        accepted_sequences.append(sequence)
        sequence += rng.randrange(1, 4)
    stop_sequence = sequence
    stop_payload = f"{stop_sequence}:stop:0".encode("ascii")
    records.append(
        {
            "sequence": stop_sequence,
            "kind": "stop",
            "value": 0,
            "crc32": f"{binascii.crc32(stop_payload) & 0xFFFFFFFF:08x}",
        }
    )
    accepted_sequences.append(stop_sequence)
    ignored_count = rng.randrange(1, 4)
    ignored_lines = [
        f"opaque-after-stop-{rng.randrange(0, 1_000_000)}".encode("ascii")
        for _ in range(ignored_count)
    ]
    input_path = root / "input/events.jsonl"
    input_path.parent.mkdir(parents=True)
    input_path.write_bytes(
        b"".join(
            json.dumps(record, sort_keys=True).encode("ascii") + b"\n"
            for record in records
        )
        + b"   \n"
        + b"\n".join(ignored_lines)
        + b"\n"
    )
    expected = {
        "schema": "tdd-manifest-contract-result-v1",
        "accepted_sequences": accepted_sequences,
        "value_count": len(values),
        "value_sum": sum(values),
        "first_stop_sequence": stop_sequence,
        "ignored_after_stop": ignored_count,
        "all_consumed_crc32_valid": True,
        "scope": {
            "stop_is_consumed": True,
            "records_after_stop_interpreted": False,
        },
    }
    _write_text(
        root / "TASK.md",
        f"""# TDD and manifest contract

Parse `input/events.jsonl` in sequence order. For each consumed record, validate
`crc32` over ASCII `<sequence>:<kind>:<value>` using lowercase eight-digit hex.
Consume the first `stop` record as the terminator but do not interpret later
records. Any duplicate/non-increasing consumed sequence or invalid CRC must fail
closed. `accepted_sequences` must include the consumed `stop` sequence.

Process non-blank lines in physical order and never sort. Before and including
the first stop, every line must be a JSON object matching the record schema in
`CONTRACT.json`; sequence values are non-boolean integers, strictly increase
(gaps are allowed), and the stop participates in validation. CRC means IEEE
CRC-32 of ASCII `<sequence>:<kind>:<value>` with canonical base-10 JSON integer
text, rendered as exactly eight lowercase hexadecimal digits. The first stop
has value zero; EOF before it fails closed.

After the first stop, count non-empty physical lines in `ignored_after_stop`
without decoding, JSON parsing, CRC checking, or sequence checking; whitespace-
only lines do not count. `value_count` and `value_sum` use only consumed
`kind=value` records and exclude the stop. Failure closed means a non-zero CLI
exit while `--output` remains absent or byte-for-byte unchanged; emitting a
result with `all_consumed_crc32_valid=false` is not failure closed.

Use red-green-refactor and create:

- `submission/result.json` with schema `tdd-manifest-contract-result-v1`;
- `submission/solution.py` supporting `--packet-root/--output`;
- focused tests covering bad CRC, bad ordering, and stop behavior;
- `submission/run_manifest.json` with schema `{SUBMISSION_SCHEMA}`, exact input
  hashes, and explicit scope.

{_PUBLIC_CONTRACT_GUIDANCE}
""",
    )
    return {"expected_result": expected}


_BUILDERS = {
    "fixed-pointer-table": _pointer_packet,
    "arm-thumb-control-flow": _control_flow_packet,
    "tdd-manifest-contract": _manifest_packet,
}


def prepare_smoke_packet(
    challenge_id: str,
    destination: Path,
    *,
    seed: int,
) -> PreparedPacket:
    """Create one immutable-input challenge packet at a new destination."""

    if challenge_id not in _BUILDERS:
        raise ValueError(f"unknown smoke challenge: {challenge_id}")
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"challenge destination must not exist: {destination}")
    destination.mkdir(parents=True)
    _write_text(destination / "AGENTS.md", _AGENT_POLICY)
    rng = random.Random(f"{seed}:{challenge_id}")
    secret = _BUILDERS[challenge_id](destination, rng)
    _write_text(
        destination / "CONTRACT.json",
        json.dumps(_public_contract(challenge_id), indent=2, sort_keys=True),
    )
    visible_inputs = [
        destination / "AGENTS.md",
        destination / "TASK.md",
        destination / "CONTRACT.json",
    ]
    visible_inputs.extend(
        path
        for path in sorted((destination / "input").rglob("*"))
        if path.is_file()
    )
    input_hashes = {
        path.relative_to(destination).as_posix(): _sha256(path)
        for path in visible_inputs
    }
    _write_text(
        destination / "INPUTS.json",
        json.dumps(
            {
                "schema": "reverse-benchmark-inputs-v1",
                "challenge_id": challenge_id,
                "input_hashes": input_hashes,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return PreparedPacket(
        challenge_id=challenge_id,
        root=destination,
        input_hashes=input_hashes,
        secret=secret,
    )
