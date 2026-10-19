#!/usr/bin/env python3
"""Integration contracts for isolated smoke packets and hidden verification."""

from __future__ import annotations

import binascii
import hashlib
import json
import struct
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from tools.reverse_benchmark.packets import (
    PACKET_CONTRACT_SCHEMA,
    SMOKE_CHALLENGE_IDS,
    prepare_smoke_packet,
)
from tools.reverse_benchmark.verifier import (
    _copy_frozen_packet,
    _json_schema_errors,
    _result_matches,
    _run_candidate_tests,
    _run_reproduction,
    _run_tdd_failure_cases,
    _submission_manifest_is_valid,
    verify_smoke_submission,
)


class SmokePacketIsolationTests(unittest.TestCase):
    @staticmethod
    def _public_reference_result(packet):
        contract = json.loads(
            (packet.root / "CONTRACT.json").read_text(encoding="utf-8")
        )
        properties = contract["deliverables"]["result"]["json_schema"][
            "properties"
        ]
        if packet.challenge_id == "fixed-pointer-table":
            blob = (packet.root / "input/resource.bin").read_bytes()
            base = int(properties["base_address"]["const"], 16)
            table_offset = properties["table_offset"]["const"]
            entry_count = properties["entry_count"]["const"]
            records = []
            for slot, pointer in enumerate(
                struct.unpack_from(f"<{entry_count}I", blob, table_offset)
            ):
                if pointer == 0:
                    records.append({"slot": slot, "pointer": None, "text": None})
                    continue
                offset = pointer - base
                consumed = blob[offset : blob.index(0, offset)]
                records.append(
                    {
                        "slot": slot,
                        "pointer": f"0x{pointer:08X}",
                        "text": consumed.decode("ascii"),
                        "length": len(consumed),
                        "sha256": hashlib.sha256(consumed).hexdigest(),
                    }
                )
            return {
                "schema": properties["schema"]["const"],
                "base_address": properties["base_address"]["const"],
                "table_offset": table_offset,
                "entry_count": entry_count,
                "records": records,
                "scope": {
                    "terminator": "first-nul",
                    "bytes_after_terminator_classified": False,
                },
            }

        if packet.challenge_id == "arm-thumb-control-flow":
            blob = (packet.root / "input/code.bin").read_bytes()
            base = int(properties["base_address"]["const"], 16)

            def signed(value, bits):
                return value - (1 << bits) if value & (1 << (bits - 1)) else value

            hi, lo = struct.unpack_from("<HH", blob, 0)
            bl_target = base + 4 + signed(
                ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1), 23
            )
            thumb_b = struct.unpack_from("<H", blob, 4)[0]
            thumb_b_target = base + 8 + signed((thumb_b & 0x7FF) << 1, 12)
            bx_source = bl_target
            bx_target = (bx_source + 4) & ~3
            arm_word = struct.unpack_from("<I", blob, bx_target - base)[0]
            arm_target = bx_target + 8 + signed((arm_word & 0xFFFFFF) << 2, 26)

            def address(value):
                return f"0x{value:08X}"

            return {
                "schema": properties["schema"]["const"],
                "base_address": properties["base_address"]["const"],
                "edges": [
                    {
                        "source": address(base),
                        "target": address(bl_target),
                        "source_mode": "thumb",
                        "target_mode": "thumb",
                        "kind": "bl",
                    },
                    {
                        "source": address(base + 4),
                        "target": address(thumb_b_target),
                        "source_mode": "thumb",
                        "target_mode": "thumb",
                        "kind": "b",
                    },
                    {
                        "source": address(bx_source),
                        "target": address(bx_target),
                        "source_mode": "thumb",
                        "target_mode": "arm",
                        "kind": "bx-pc",
                    },
                    {
                        "source": address(bx_target),
                        "target": address(arm_target),
                        "source_mode": "arm",
                        "target_mode": "arm",
                        "kind": "b",
                    },
                ],
                "terminal": {
                    "address": address(arm_target),
                    "mode": "arm",
                    "instruction": "bx-lr",
                },
                "scope": {
                    "thumb_ranges": properties["scope"]["properties"][
                        "thumb_ranges"
                    ]["const"],
                    "arm_ranges": properties["scope"]["properties"][
                        "arm_ranges"
                    ]["const"],
                    "random_filler_classified": False,
                },
            }

        lines = (packet.root / "input/events.jsonl").read_bytes().splitlines()
        accepted = []
        values = []
        previous = None
        stop = None
        stop_index = None
        for index, raw in enumerate(lines):
            if not raw.strip():
                raise AssertionError("valid consumed prefix contains a blank line")
            record = json.loads(raw)
            self_payload = (
                f"{record['sequence']}:{record['kind']}:{record['value']}".encode(
                    "ascii"
                )
            )
            if record["crc32"] != f"{binascii.crc32(self_payload) & 0xFFFFFFFF:08x}":
                raise AssertionError("valid packet has invalid CRC")
            if previous is not None and record["sequence"] <= previous:
                raise AssertionError("valid packet is not strictly increasing")
            previous = record["sequence"]
            accepted.append(record["sequence"])
            if record["kind"] == "value":
                values.append(record["value"])
            else:
                stop = record["sequence"]
                stop_index = index
                break
        if stop_index is None:
            raise AssertionError("valid packet is missing stop")
        ignored = sum(bool(line.strip()) for line in lines[stop_index + 1 :])
        return {
            "schema": properties["schema"]["const"],
            "accepted_sequences": accepted,
            "value_count": len(values),
            "value_sum": sum(values),
            "first_stop_sequence": stop,
            "ignored_after_stop": ignored,
            "all_consumed_crc32_valid": True,
            "scope": {
                "stop_is_consumed": True,
                "records_after_stop_interpreted": False,
            },
        }

    def test_public_reference_rebuilds_all_expected_results_across_seeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for challenge_id in SMOKE_CHALLENGE_IDS:
                for seed in range(8):
                    with self.subTest(challenge_id=challenge_id, seed=seed):
                        packet = prepare_smoke_packet(
                            challenge_id,
                            root / f"{challenge_id}-{seed}",
                            seed=seed,
                        )
                        self.assertEqual(
                            packet.secret["expected_result"],
                            self._public_reference_result(packet),
                        )

    def test_submission_manifest_contract_rejects_extra_or_typed_wrong_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = prepare_smoke_packet(
                "fixed-pointer-table", Path(directory) / "packet", seed=37
            )
            manifest = {
                "schema": "reverse-benchmark-submission-v1",
                "challenge_id": packet.challenge_id,
                "input_hashes": packet.input_hashes,
                "scope": {"complete": True, "limitations": []},
            }
            self.assertTrue(_submission_manifest_is_valid(packet, manifest))

            wrong_type = deepcopy(manifest)
            wrong_type["scope"]["limitations"] = [1]
            self.assertFalse(_submission_manifest_is_valid(packet, wrong_type))

            extra = deepcopy(manifest)
            extra["extra"] = True
            self.assertFalse(_submission_manifest_is_valid(packet, extra))

            extra_scope = deepcopy(manifest)
            extra_scope["scope"]["extra"] = True
            self.assertFalse(_submission_manifest_is_valid(packet, extra_scope))

    def test_tdd_packets_vary_structure_and_treat_post_stop_lines_as_opaque(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packets = [
                prepare_smoke_packet(
                    "tdd-manifest-contract", root / f"packet-{seed}", seed=seed
                )
                for seed in range(8)
            ]

            accepted_lengths = {
                len(packet.secret["expected_result"]["accepted_sequences"])
                for packet in packets
            }
            ignored_counts = {
                packet.secret["expected_result"]["ignored_after_stop"]
                for packet in packets
            }
            sequence_starts = {
                packet.secret["expected_result"]["accepted_sequences"][0]
                for packet in packets
            }
            self.assertGreater(len(accepted_lengths), 1)
            self.assertGreater(len(ignored_counts), 1)
            self.assertGreater(len(sequence_starts), 1)

            for packet in packets:
                lines = (packet.root / "input/events.jsonl").read_bytes().splitlines()
                stop_index = next(
                    index
                    for index, line in enumerate(lines)
                    if json.loads(line)["kind"] == "stop"
                )
                trailing = lines[stop_index + 1 :]
                non_blank = [line for line in trailing if line.strip()]
                self.assertEqual(
                    packet.secret["expected_result"]["ignored_after_stop"],
                    len(non_blank),
                )
                self.assertTrue(
                    any(
                        self._is_invalid_json(line)
                        for line in non_blank
                    )
                )

    @staticmethod
    def _is_invalid_json(payload: bytes) -> bool:
        try:
            json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        return False

    def test_tdd_verifier_owned_fail_closed_cases_reject_permissive_solution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = prepare_smoke_packet(
                "tdd-manifest-contract", root / "packet", seed=29
            )
            submission = packet.root / "submission"
            submission.mkdir()
            (submission / "solution.py").write_text(
                "import argparse, binascii, json\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "lines = (args.packet_root / 'input/events.jsonl').read_bytes().splitlines()\n"
                "accepted, values, stop, stop_index = [], [], None, None\n"
                "for index, raw in enumerate(lines):\n"
                "    if not raw.strip():\n"
                "        continue\n"
                "    record = json.loads(raw)\n"
                "    accepted.append(record['sequence'])\n"
                "    if record['kind'] == 'value': values.append(record['value'])\n"
                "    if record['kind'] == 'stop':\n"
                "        stop, stop_index = record['sequence'], index\n"
                "        break\n"
                "ignored = sum(bool(line.strip()) for line in lines[stop_index + 1:])\n"
                "result = {'schema':'tdd-manifest-contract-result-v1', "
                "'accepted_sequences':accepted, 'value_count':len(values), "
                "'value_sum':sum(values), 'first_stop_sequence':stop, "
                "'ignored_after_stop':ignored, 'all_consumed_crc32_valid':True, "
                "'scope':{'stop_is_consumed':True, "
                "'records_after_stop_interpreted':False}}\n"
                "args.output.write_text(json.dumps(result))\n",
                encoding="utf-8",
            )

            accepted, detail = _run_tdd_failure_cases(
                packet, root / "negative-cases"
            )

        self.assertFalse(accepted)
        self.assertIn("invalid-consumed-crc32", detail)

    def test_tdd_verifier_owned_fail_closed_cases_accept_strict_solution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = prepare_smoke_packet(
                "tdd-manifest-contract", root / "packet", seed=30
            )
            submission = packet.root / "submission"
            submission.mkdir()
            (submission / "solution.py").write_text(
                "import argparse, binascii, json, re\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "lines = (args.packet_root / 'input/events.jsonl').read_bytes().splitlines()\n"
                "accepted, values, previous, stop, stop_index = [], [], None, None, None\n"
                "for index, raw in enumerate(lines):\n"
                "    if not raw.strip(): raise ValueError('blank consumed line')\n"
                "    record = json.loads(raw)\n"
                "    if set(record) != {'sequence','kind','value','crc32'}: raise ValueError('shape')\n"
                "    if type(record['sequence']) is not int or type(record['value']) is not int: raise ValueError('type')\n"
                "    if record['kind'] not in {'value','stop'}: raise ValueError('kind')\n"
                "    if record['kind'] == 'stop' and record['value'] != 0: raise ValueError('stop')\n"
                "    if re.fullmatch(r'[0-9a-f]{8}', record['crc32']) is None: raise ValueError('crc format')\n"
                "    payload = f\"{record['sequence']}:{record['kind']}:{record['value']}\".encode('ascii')\n"
                "    if record['crc32'] != f\"{binascii.crc32(payload) & 0xffffffff:08x}\": raise ValueError('crc')\n"
                "    if previous is not None and record['sequence'] <= previous: raise ValueError('order')\n"
                "    previous = record['sequence']; accepted.append(previous)\n"
                "    if record['kind'] == 'value': values.append(record['value'])\n"
                "    else: stop, stop_index = previous, index; break\n"
                "if stop_index is None: raise ValueError('missing stop')\n"
                "ignored = sum(bool(line.strip()) for line in lines[stop_index + 1:])\n"
                "result = {'schema':'tdd-manifest-contract-result-v1', "
                "'accepted_sequences':accepted, 'value_count':len(values), "
                "'value_sum':sum(values), 'first_stop_sequence':stop, "
                "'ignored_after_stop':ignored, 'all_consumed_crc32_valid':True, "
                "'scope':{'stop_is_consumed':True, "
                "'records_after_stop_interpreted':False}}\n"
                "args.output.write_text(json.dumps(result))\n",
                encoding="utf-8",
            )

            accepted, detail = _run_tdd_failure_cases(
                packet, root / "negative-cases"
            )

        self.assertTrue(accepted, detail)

    def test_candidate_tests_must_kill_hardcoded_visible_result_mutant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = prepare_smoke_packet(
                "fixed-pointer-table", root / "packet", seed=31
            )
            submission = packet.root / "submission"
            tests = submission / "tests"
            tests.mkdir(parents=True)
            expected = json.dumps(packet.secret["expected_result"], sort_keys=True)
            (submission / "solution.py").write_text(
                "import argparse, json\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                f"args.output.write_text({expected!r})\n",
                encoding="utf-8",
            )
            (tests / "test_solution.py").write_text(
                "import json, struct, subprocess, sys, tempfile, unittest\n"
                "from pathlib import Path\n"
                f"EXPECTED = json.loads({expected!r})\n"
                "class Tests(unittest.TestCase):\n"
                "    def test_visible_result(self):\n"
                "        packet = Path(__file__).resolve().parents[2]\n"
                "        with tempfile.TemporaryDirectory() as directory:\n"
                "            output = Path(directory) / 'result.json'\n"
                "            completed = subprocess.run([sys.executable, "
                "str(packet / 'submission/solution.py'), '--packet-root', "
                "str(packet), '--output', str(output)])\n"
                "            self.assertEqual(0, completed.returncode)\n"
                "            self.assertEqual(EXPECTED, json.loads(output.read_text()))\n",
                encoding="utf-8",
            )

            state, detail = _run_candidate_tests(packet, root / "test-runs")

        self.assertEqual("insensitive", state)
        self.assertIn("hardcoded-supplied-result", detail)

    def test_public_schema_is_enforced_and_control_flow_edges_are_a_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pointer = prepare_smoke_packet(
                "fixed-pointer-table", root / "pointer", seed=17
            )
            contract = json.loads(
                (pointer.root / "CONTRACT.json").read_text(encoding="utf-8")
            )
            schema = contract["deliverables"]["result"]["json_schema"]
            invalid_bool = deepcopy(pointer.secret["expected_result"])
            invalid_bool["records"][0]["slot"] = False
            self.assertTrue(_json_schema_errors(invalid_bool, schema))
            invalid_float = deepcopy(pointer.secret["expected_result"])
            invalid_float["table_offset"] = 32.0
            self.assertTrue(_json_schema_errors(invalid_float, schema))

            control = prepare_smoke_packet(
                "arm-thumb-control-flow", root / "control", seed=19
            )
            reordered = deepcopy(control.secret["expected_result"])
            reordered["edges"].reverse()
            matches, detail = _result_matches(
                control, reordered, control.secret["expected_result"]
            )
            self.assertTrue(matches, detail)

            duplicated = deepcopy(control.secret["expected_result"])
            duplicated["edges"][1] = deepcopy(duplicated["edges"][0])
            matches, detail = _result_matches(
                control, duplicated, control.secret["expected_result"]
            )
            self.assertFalse(matches)
            self.assertIn("schema", detail)

    def test_reproduction_detects_inputs_json_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = prepare_smoke_packet(
                "fixed-pointer-table", root / "source", seed=23
            )
            submission = packet.root / "submission"
            submission.mkdir()
            encoded = json.dumps(packet.secret["expected_result"], sort_keys=True)
            (submission / "solution.py").write_text(
                "import argparse, json\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "inputs = args.packet_root / 'INPUTS.json'\n"
                "inputs.write_text('{}')\n"
                f"args.output.write_text({encoded!r})\n",
                encoding="utf-8",
            )
            destination = root / "destination"
            _copy_frozen_packet(packet, destination)
            accepted, detail = _run_reproduction(
                packet,
                destination=destination,
                expected=packet.secret["expected_result"],
            )

        self.assertFalse(accepted, detail)

    def test_all_three_packets_are_deterministic_and_answer_free(self):
        self.assertEqual(
            (
                "fixed-pointer-table",
                "arm-thumb-control-flow",
                "tdd-manifest-contract",
            ),
            SMOKE_CHALLENGE_IDS,
        )

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for challenge_id in SMOKE_CHALLENGE_IDS:
                with self.subTest(challenge_id=challenge_id):
                    first_packet = prepare_smoke_packet(
                        challenge_id,
                        Path(first) / challenge_id,
                        seed=20260816,
                    )
                    second_packet = prepare_smoke_packet(
                        challenge_id,
                        Path(second) / challenge_id,
                        seed=20260816,
                    )

                    self.assertEqual(
                        first_packet.input_hashes,
                        second_packet.input_hashes,
                    )
                    self.assertIn("AGENTS.md", first_packet.input_hashes)
                    self.assertIn("TASK.md", first_packet.input_hashes)
                    self.assertIn("CONTRACT.json", first_packet.input_hashes)
                    self.assertEqual(first_packet.secret, second_packet.secret)
                    contract = json.loads(
                        (first_packet.root / "CONTRACT.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(PACKET_CONTRACT_SCHEMA, contract["schema"])
                    self.assertEqual(challenge_id, contract["challenge_id"])
                    self.assertEqual(
                        "https://json-schema.org/draft/2020-12/schema",
                        contract["deliverables"]["result"]["json_schema"][
                            "$schema"
                        ],
                    )
                    verification = contract["verification"]
                    self.assertEqual(
                        {
                            "input_integrity": 15,
                            "result_correctness": 40,
                            "run_manifest": 10,
                            "solution_reproduction": 20,
                            "candidate_tests": 15,
                        },
                        verification["score_points"],
                    )
                    self.assertTrue(
                        verification["missing_result_or_mutated_input_forces_zero"]
                    )
                    reproduction = verification["solution_reproduction"]
                    self.assertEqual(
                        ["supplied", "distinct-same-contract-unseen"],
                        reproduction["valid_packets"],
                    )
                    self.assertEqual(
                        [
                            "frozen packet inputs",
                            "INPUTS.json",
                            "submission/solution.py",
                        ],
                        reproduction["copied_paths"],
                    )
                    self.assertEqual(15, reproduction["timeout_seconds"])
                    self.assertEqual(4 * 1024 * 1024, reproduction["max_output_bytes"])
                    self.assertEqual(
                        ["empty-result", "hardcoded-supplied-result"],
                        verification["candidate_tests"]["mutants_must_fail"],
                    )
                    deliverables = contract["deliverables"]
                    self.assertEqual(
                        "submission/result.json", deliverables["result"]["path"]
                    )
                    self.assertEqual(
                        "submission/solution.py", deliverables["solution"]["path"]
                    )
                    self.assertEqual(
                        "submission/tests/test*.py",
                        deliverables["tests"]["glob"],
                    )
                    self.assertEqual(
                        ["submission/result.json", "submission/run_manifest.json"],
                        deliverables["tests"]["must_not_depend_on"],
                    )
                    self.assertEqual(
                        "submission/run_manifest.json",
                        deliverables["run_manifest"]["path"],
                    )
                    self.assertFalse(
                        deliverables["run_manifest"][
                            "additional_fields_allowed"
                        ]
                    )
                    self.assertTrue(
                        deliverables["run_manifest"][
                            "limitations_must_be_strings"
                        ]
                    )
                    manifest_example = deliverables["run_manifest"][
                        "required_shape"
                    ]
                    self.assertEqual(
                        "reverse-benchmark-submission-v1",
                        manifest_example["schema"],
                    )
                    self.assertEqual(challenge_id, manifest_example["challenge_id"])
                    self.assertEqual(
                        "copy INPUTS.json.input_hashes exactly",
                        manifest_example["input_hashes"],
                    )
                    self.assertEqual(True, manifest_example["scope"]["complete"])
                    self.assertEqual(
                        ["string"], manifest_example["scope"]["limitations"]
                    )
                    result_schema = deliverables["result"]["json_schema"]
                    expected_result = first_packet.secret["expected_result"]
                    self.assertFalse(result_schema["additionalProperties"])
                    self.assertEqual(
                        set(expected_result), set(result_schema["required"])
                    )
                    self.assertEqual(
                        set(expected_result), set(result_schema["properties"])
                    )
                    semantics = contract["challenge_semantics"]
                    if challenge_id == "fixed-pointer-table":
                        records_schema = result_schema["properties"]["records"]
                        self.assertEqual(8, records_schema["minItems"])
                        self.assertEqual(8, records_schema["maxItems"])
                        self.assertEqual(
                            "records[i] describes zero-based table slot i",
                            semantics["records_order"],
                        )
                        self.assertEqual(
                            "SHA-256 lowercase hex of consumed_bytes exactly",
                            semantics["derived_fields"]["sha256"],
                        )
                        self.assertEqual(
                            "raw byte count of consumed_bytes",
                            semantics["derived_fields"]["length"],
                        )
                    elif challenge_id == "arm-thumb-control-flow":
                        edges_schema = result_schema["properties"]["edges"]
                        self.assertTrue(edges_schema["uniqueItems"])
                        self.assertEqual(
                            "order-insensitive unique set",
                            verification["result_comparison"][
                                "arm-thumb-control-flow.edges"
                            ],
                        )
                        self.assertEqual("little-endian", semantics["endianness"])
                        self.assertEqual(
                            "normalized instruction address plus mode",
                            semantics["traversal_state"],
                        )
                        self.assertIn("sign_extend", semantics["thumb_b_target"])
                        self.assertIn("sign_extend", semantics["thumb_bl_target"])
                    else:
                        self.assertEqual(
                            "Number of non-empty physical lines after the first "
                            "stop; count raw lines without decoding or parsing; "
                            "whitespace-only lines do not count.",
                            result_schema["properties"]["ignored_after_stop"][
                                "description"
                            ],
                        )
                        self.assertEqual(
                            "physical non-blank line order; never sort",
                            semantics["consumed_order"],
                        )
                        self.assertEqual(
                            "non-zero exit and output absent or byte-identical",
                            semantics["fail_closed"],
                        )
                        self.assertIn(
                            "invalid-consumed-crc32",
                            reproduction["failure_cases"],
                        )
                    if challenge_id == "tdd-manifest-contract":
                        accepted_sequences = result_schema["properties"][
                            "accepted_sequences"
                        ]
                        self.assertEqual(
                            "Sequence numbers of every successfully validated "
                            "non-blank record from file start through the first stop, "
                            "preserving physical line order; the consumed stop is the "
                            "final element.",
                            accepted_sequences["description"],
                        )
                        self.assertIn(
                            expected_result["first_stop_sequence"],
                            expected_result["accepted_sequences"],
                        )
                    task = (first_packet.root / "TASK.md").read_text(
                        encoding="utf-8"
                    )
                    for required_text in (
                        "CONTRACT.json",
                        "authoritative",
                        "submission/tests/test*.py",
                        "must not depend on `submission/result.json`",
                        "must not depend on `submission/run_manifest.json`",
                    ):
                        self.assertIn(required_text, task)
                    if challenge_id == "tdd-manifest-contract":
                        self.assertIn(
                            "`accepted_sequences` must include the consumed `stop` "
                            "sequence",
                            task,
                        )
                    visible_names = {
                        path.relative_to(first_packet.root).as_posix()
                        for path in first_packet.root.rglob("*")
                        if path.is_file()
                    }
                    self.assertNotIn("verifier.py", visible_names)
                    self.assertFalse(
                        any(
                            "golden" in name or "secret" in name
                            for name in visible_names
                        )
                    )
                    visible_text = "\n".join(
                        path.read_text(encoding="utf-8", errors="ignore")
                        for path in first_packet.root.rglob("*")
                        if path.is_file()
                    )
                    self.assertNotIn(json.dumps(first_packet.secret), visible_text)

    def test_hidden_verifier_accepts_exact_submission_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = prepare_smoke_packet(
                "fixed-pointer-table",
                Path(directory) / "packet",
                seed=7,
            )
            submission = packet.root / "submission"
            submission.mkdir()
            (submission / "result.json").write_text(
                json.dumps(packet.secret["expected_result"], indent=2) + "\n",
                encoding="utf-8",
            )
            (submission / "solution.py").write_text(
                "import argparse, hashlib, json, struct\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "blob = (args.packet_root / 'input/resource.bin').read_bytes()\n"
                "base = 0x08004000\n"
                "records = []\n"
                "for slot, pointer in enumerate(struct.unpack_from('<8I', blob, 0x20)):\n"
                "    if pointer == 0:\n"
                "        records.append({'slot': slot, 'pointer': None, 'text': None})\n"
                "        continue\n"
                "    offset = pointer - base\n"
                "    consumed = blob[offset:blob.index(0, offset)]\n"
                "    records.append({'slot': slot, 'pointer': f'0x{pointer:08X}', "
                "'text': consumed.decode('ascii'), 'length': len(consumed), "
                "'sha256': hashlib.sha256(consumed).hexdigest()})\n"
                "result = {'schema': 'fixed-pointer-table-result-v1', "
                "'base_address': f'0x{base:08X}', 'table_offset': 0x20, "
                "'entry_count': 8, 'records': records, 'scope': "
                "{'terminator': 'first-nul', 'bytes_after_terminator_classified': False}}\n"
                "args.output.write_text(json.dumps(result))\n",
                encoding="utf-8",
            )
            tests = submission / "tests"
            tests.mkdir()
            (tests / "test_solution.py").write_text(
                "import json, struct, subprocess, sys, tempfile, unittest\n"
                "from pathlib import Path\n\n"
                "class SubmissionTests(unittest.TestCase):\n"
                "    def test_solution_parses_null_and_duplicate_slots(self):\n"
                "        packet = Path(__file__).resolve().parents[2]\n"
                "        with tempfile.TemporaryDirectory() as directory:\n"
                "            output = Path(directory) / 'result.json'\n"
                "            completed = subprocess.run([sys.executable, "
                "str(packet / 'submission/solution.py'), '--packet-root', "
                "str(packet), '--output', str(output)])\n"
                "            self.assertEqual(0, completed.returncode)\n"
                "            result = json.loads(output.read_text())\n"
                "        self.assertIsNone(result['records'][1]['pointer'])\n"
                "        texts = [record['text'] for record in result['records'] "
                "if record['text'] is not None]\n"
                "        self.assertGreater(len(texts), len(set(texts)))\n"
                "    def test_solution_depends_on_input_bytes(self):\n"
                "        packet = Path(__file__).resolve().parents[2]\n"
                "        with tempfile.TemporaryDirectory() as directory:\n"
                "            root = Path(directory)\n"
                "            changed = root / 'changed'\n"
                "            (changed / 'input').mkdir(parents=True)\n"
                "            blob = bytearray((packet / 'input/resource.bin').read_bytes())\n"
                "            pointers = struct.unpack_from('<8I', blob, 0x20)\n"
                "            pointer = next(value for value in pointers if value)\n"
                "            blob[pointer - 0x08004000] = ord('Q')\n"
                "            (changed / 'input/resource.bin').write_bytes(blob)\n"
                "            original_output = root / 'original.json'\n"
                "            changed_output = root / 'changed.json'\n"
                "            for packet_root, output in ((packet, original_output), "
                "(changed, changed_output)):\n"
                "                completed = subprocess.run([sys.executable, "
                "str(packet / 'submission/solution.py'), '--packet-root', "
                "str(packet_root), '--output', str(output)])\n"
                "                self.assertEqual(0, completed.returncode)\n"
                "            self.assertNotEqual(json.loads(original_output.read_text()), "
                "json.loads(changed_output.read_text()))\n",
                encoding="utf-8",
            )
            (submission / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "reverse-benchmark-submission-v1",
                        "challenge_id": "fixed-pointer-table",
                        "input_hashes": packet.input_hashes,
                        "scope": {"complete": True, "limitations": []},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            accepted = verify_smoke_submission(packet)
            self.assertTrue(accepted.passed, accepted.errors)

            input_path = next(iter(packet.input_hashes))
            (packet.root / input_path).write_bytes(b"tampered")
            rejected = verify_smoke_submission(packet)

        self.assertFalse(rejected.passed)
        self.assertIn("input-hash-mismatch", rejected.error_codes)

    def test_hidden_verifier_rejects_copying_result_and_trivial_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            packet = prepare_smoke_packet(
                "fixed-pointer-table",
                Path(directory) / "packet",
                seed=13,
            )
            submission = packet.root / "submission"
            (submission / "tests").mkdir(parents=True)
            (submission / "result.json").write_text(
                json.dumps(packet.secret["expected_result"]), encoding="utf-8"
            )
            embedded_result = json.dumps(packet.secret["expected_result"])
            (submission / "solution.py").write_text(
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--packet-root', type=Path, required=True)\n"
                "parser.add_argument('--output', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                f"args.output.write_text({embedded_result!r})\n",
                encoding="utf-8",
            )
            (submission / "tests/test_solution.py").write_text(
                "import unittest\n\n"
                "class Tests(unittest.TestCase):\n"
                "    def test_true(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (submission / "run_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "reverse-benchmark-submission-v1",
                        "challenge_id": packet.challenge_id,
                        "input_hashes": packet.input_hashes,
                        "scope": {"complete": True, "limitations": []},
                    }
                ),
                encoding="utf-8",
            )

            rejected = verify_smoke_submission(packet)

        self.assertFalse(rejected.passed)
        self.assertIn("reproduction-failed", rejected.error_codes)
        self.assertIn("tests-not-sensitive", rejected.error_codes)

    def test_packet_rejects_unknown_challenge_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "unknown smoke challenge"):
                prepare_smoke_packet("unknown", root / "unknown", seed=1)

            destination = root / "existing"
            destination.mkdir()
            with self.assertRaisesRegex(FileExistsError, "must not exist"):
                prepare_smoke_packet(
                    "fixed-pointer-table",
                    destination,
                    seed=1,
                )


if __name__ == "__main__":
    unittest.main()
