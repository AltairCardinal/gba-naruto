"""Hidden smoke verifier; it never imports or executes the benchmark runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .packets import (
    MAX_CANDIDATE_FILE_BYTES,
    PreparedPacket,
    REPRODUCTION_TIMEOUT_SECONDS,
    SUBMISSION_SCHEMA,
    prepare_smoke_packet,
)


_CHILD_TIMEOUT_S = REPRODUCTION_TIMEOUT_SECONDS
_MAX_CANDIDATE_FILE_BYTES = MAX_CANDIDATE_FILE_BYTES


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    score: int
    errors: tuple[str, ...]
    error_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ChildResult:
    returncode: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_equal(left: object, right: object) -> bool:
    """Compare JSON values without Python's bool/int or int/float aliases."""

    try:
        return _canonical_json(left) == _canonical_json(right)
    except (TypeError, ValueError):
        return False


def _json_schema_errors(
    value: object,
    schema: object,
    *,
    path: str = "$",
) -> tuple[str, ...]:
    """Validate the deliberately small Draft 2020-12 subset used by packets."""

    if not isinstance(schema, dict):
        return (f"{path}: schema is not an object",)
    errors: list[str] = []

    one_of = schema.get("oneOf")
    if one_of is not None:
        if not isinstance(one_of, list) or not one_of:
            errors.append(f"{path}: oneOf is invalid")
        else:
            matches = sum(
                not _json_schema_errors(value, candidate, path=path)
                for candidate in one_of
            )
            if matches != 1:
                errors.append(f"{path}: expected exactly one oneOf match, got {matches}")

    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{path}: value does not match const")
    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not any(
            _json_equal(value, candidate) for candidate in enum
        ):
            errors.append(f"{path}: value is not in enum")

    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
    }
    if expected_type is not None:
        if expected_type not in type_matches:
            errors.append(f"{path}: unsupported schema type {expected_type!r}")
            return tuple(errors)
        if not type_matches[expected_type]:
            errors.append(f"{path}: expected {expected_type}")
            return tuple(errors)

    if isinstance(value, dict) and expected_type == "object":
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            errors.append(f"{path}: required is invalid")
            required = []
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            errors.append(f"{path}: properties is invalid")
            properties = {}
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(
                    _json_schema_errors(
                        value[key], child_schema, path=f"{path}.{key}"
                    )
                )

    if isinstance(value, list) and expected_type == "array":
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: fewer than minItems")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: more than maxItems")
        if schema.get("uniqueItems") is True:
            encoded = [_canonical_json(item) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items are not unique")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                errors.extend(
                    _json_schema_errors(
                        item, item_schema, path=f"{path}[{index}]"
                    )
                )

    if isinstance(value, str) and expected_type == "string":
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{path}: string does not match pattern")

    if isinstance(value, int) and not isinstance(value, bool) and expected_type == "integer":
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int) and value < minimum:
            errors.append(f"{path}: value is below minimum")
        if isinstance(maximum, int) and value > maximum:
            errors.append(f"{path}: value is above maximum")

    return tuple(errors)


def _public_result_schema(packet: PreparedPacket) -> dict[str, object]:
    contract = json.loads((packet.root / "CONTRACT.json").read_text(encoding="utf-8"))
    schema = contract["deliverables"]["result"]["json_schema"]
    if not isinstance(schema, dict):
        raise ValueError("public result schema is invalid")
    return schema


def _normalized_result(challenge_id: str, value: object) -> object:
    if challenge_id != "arm-thumb-control-flow" or not isinstance(value, dict):
        return value
    edges = value.get("edges")
    if not isinstance(edges, list):
        return value
    normalized = dict(value)
    normalized["edges"] = sorted(edges, key=_canonical_json)
    return normalized


def _result_matches(
    packet: PreparedPacket,
    value: object,
    expected: object,
) -> tuple[bool, str]:
    schema_errors = _json_schema_errors(value, _public_result_schema(packet))
    if schema_errors:
        return False, f"schema mismatch: {schema_errors[0]}"
    if not _json_equal(
        _normalized_result(packet.challenge_id, value),
        _normalized_result(packet.challenge_id, expected),
    ):
        return False, "value mismatch under the public comparison contract"
    return True, ""


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _load_json(path: Path, errors: list[str], codes: list[str]) -> object | None:
    if not _is_regular_file(path):
        errors.append(f"missing or unsafe required file: {path.name}")
        codes.append("missing-file")
        return None
    try:
        if path.stat().st_size > _MAX_CANDIDATE_FILE_BYTES:
            raise OSError("file exceeds verifier size limit")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"invalid JSON {path.name}: {error}")
        codes.append("invalid-json")
    return None


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    except (OSError, ValueError):
        pass


def _terminate_process_group(process_group: int) -> None:
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _tail(stream, limit: int = 2_000) -> str:
    stream.flush()
    size = stream.tell()
    stream.seek(max(0, size - limit))
    return stream.read().decode("utf-8", errors="replace")


def _run_owned(command: Sequence[str], *, cwd: Path) -> _ChildResult:
    with (
        tempfile.TemporaryDirectory(prefix="reverse-verifier-home-") as home_dir,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        safe_environment = {
            "HOME": home_dir,
            "TMPDIR": home_dir,
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=safe_environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            preexec_fn=_child_limits,
        )
        timed_out = False
        try:
            returncode = process.wait(timeout=_CHILD_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_group(process.pid)
            try:
                returncode = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                returncode = process.wait(timeout=2)
        finally:
            # A candidate may let its root exit while leaving descendants in
            # the private process group. Always close that group before return.
            _terminate_process_group(process.pid)
        return _ChildResult(
            returncode=returncode,
            stdout_tail=_tail(stdout),
            stderr_tail=_tail(stderr),
            timed_out=timed_out,
        )


def _copy_regular(source: Path, destination: Path) -> None:
    if not _is_regular_file(source):
        raise ValueError(f"candidate path is not a regular file: {source}")
    if source.stat().st_size > _MAX_CANDIDATE_FILE_BYTES:
        raise ValueError(f"candidate file exceeds size limit: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination, follow_symlinks=False)


def _copy_frozen_packet(packet: PreparedPacket, destination: Path) -> None:
    destination.mkdir(parents=True)
    for relative_path in packet.input_hashes:
        _copy_regular(packet.root / relative_path, destination / relative_path)
    _copy_regular(packet.root / "INPUTS.json", destination / "INPUTS.json")


def _copy_solution(source_packet: PreparedPacket, destination_packet: Path) -> Path:
    destination = destination_packet / "submission/solution.py"
    _copy_regular(source_packet.root / "submission/solution.py", destination)
    return destination


def _solution_command(solution: Path, packet_root: Path, output: Path) -> list[str]:
    return [
        sys.executable,
        "-B",
        str(solution),
        "--packet-root",
        str(packet_root),
        "--output",
        str(output),
    ]


def _run_reproduction(
    packet: PreparedPacket,
    *,
    destination: Path,
    expected: object,
    destination_hashes: Mapping[str, str] | None = None,
) -> tuple[bool, str]:
    solution = _copy_solution(packet, destination)
    reproduced_path = destination / "reproduced-result.json"
    inputs_contract = destination / "INPUTS.json"
    inputs_contract_before = (
        inputs_contract.read_bytes() if _is_regular_file(inputs_contract) else None
    )
    completed = _run_owned(
        _solution_command(solution, destination, reproduced_path),
        cwd=destination,
    )
    try:
        if not _is_regular_file(reproduced_path):
            raise OSError("reproduction output is not a regular file")
        if reproduced_path.stat().st_size > _MAX_CANDIDATE_FILE_BYTES:
            raise OSError("reproduction output exceeds size limit")
        reproduced = json.loads(reproduced_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        reproduced = None
    frozen_hashes = packet.input_hashes if destination_hashes is None else destination_hashes
    inputs_unchanged = all(
        _is_regular_file(destination / relative_path)
        and _sha256(destination / relative_path) == expected_hash
        for relative_path, expected_hash in frozen_hashes.items()
    ) and (
        inputs_contract_before is not None
        and _is_regular_file(inputs_contract)
        and inputs_contract.read_bytes() == inputs_contract_before
    )
    result_matches, result_detail = _result_matches(packet, reproduced, expected)
    ok = (
        not completed.timed_out
        and completed.returncode == 0
        and result_matches
        and inputs_unchanged
    )
    detail = (
        f"exit={completed.returncode} timeout={completed.timed_out} "
        f"result={result_detail or 'matched'} inputs_unchanged={inputs_unchanged} "
        f"stderr={completed.stderr_tail[-500:]}"
    )
    return ok, detail


def _hidden_seed(packet: PreparedPacket) -> int:
    digest = hashlib.sha256(
        (packet.challenge_id + "\0" + "".join(packet.input_hashes.values())).encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") ^ 0x5EED5EED


def _copy_candidate_tests(packet: PreparedPacket, destination: Path) -> int:
    source_tests = packet.root / "submission/tests"
    if not source_tests.is_dir() or source_tests.is_symlink():
        return 0
    test_files = sorted(source_tests.rglob("test*.py"))
    if not test_files:
        return 0
    for source in test_files:
        relative = source.relative_to(source_tests)
        _copy_regular(source, destination / "submission/tests" / relative)
    return len(test_files)


def _write_mutant_solution(path: Path, result: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, sort_keys=True)
    path.write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--packet-root', type=Path, required=True)\n"
        "parser.add_argument('--output', type=Path, required=True)\n"
        "args = parser.parse_args()\n"
        f"args.output.write_text({encoded!r})\n",
        encoding="utf-8",
    )


def _run_candidate_tests(packet: PreparedPacket, temporary_root: Path) -> tuple[str, str]:
    correct_root = temporary_root / "tests-correct"
    _copy_frozen_packet(packet, correct_root)
    if _copy_candidate_tests(packet, correct_root) == 0:
        return "missing", "submission has no focused tests"
    _copy_solution(packet, correct_root)
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "submission/tests",
    ]
    correct = _run_owned(command, cwd=correct_root)
    if correct.timed_out or correct.returncode != 0:
        return (
            "failed",
            f"candidate tests failed: exit={correct.returncode} "
            f"timeout={correct.timed_out} stderr={correct.stderr_tail[-500:]}",
        )
    mutants = (
        ("empty-result", {}),
        ("hardcoded-supplied-result", packet.secret.get("expected_result")),
    )
    for mutant_name, mutant_result in mutants:
        mutant_root = temporary_root / f"tests-mutant-{mutant_name}"
        _copy_frozen_packet(packet, mutant_root)
        _copy_candidate_tests(packet, mutant_root)
        _write_mutant_solution(
            mutant_root / "submission/solution.py", mutant_result
        )
        mutant = _run_owned(command, cwd=mutant_root)
        if not mutant.timed_out and mutant.returncode == 0:
            return (
                "insensitive",
                f"candidate tests passed against {mutant_name} mutant",
            )
    return "passed", ""


def _rewrite_input_hash_contract(packet_root: Path, relative_path: str) -> None:
    contract_path = packet_root / "INPUTS.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload["input_hashes"][relative_path] = _sha256(packet_root / relative_path)
    contract_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _event_lines(packet_root: Path) -> list[bytes]:
    return (packet_root / "input/events.jsonl").read_bytes().splitlines()


def _write_event_lines(packet_root: Path, lines: Sequence[bytes]) -> None:
    relative_path = "input/events.jsonl"
    (packet_root / relative_path).write_bytes(b"\n".join(lines) + b"\n")
    _rewrite_input_hash_contract(packet_root, relative_path)


def _mutate_invalid_crc(packet_root: Path) -> None:
    lines = _event_lines(packet_root)
    record = json.loads(lines[0])
    record["crc32"] = "ffffffff" if record["crc32"] != "ffffffff" else "00000000"
    lines[0] = json.dumps(record, sort_keys=True).encode("ascii")
    _write_event_lines(packet_root, lines)


def _mutate_noncanonical_crc(packet_root: Path) -> None:
    lines = _event_lines(packet_root)
    record = json.loads(lines[0])
    record["crc32"] = "0x" + record["crc32"]
    lines[0] = json.dumps(record, sort_keys=True).encode("ascii")
    _write_event_lines(packet_root, lines)


def _mutate_duplicate_sequence(packet_root: Path) -> None:
    lines = _event_lines(packet_root)
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    second["sequence"] = first["sequence"]
    payload = f"{second['sequence']}:{second['kind']}:{second['value']}".encode(
        "ascii"
    )
    import binascii

    second["crc32"] = f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}"
    lines[1] = json.dumps(second, sort_keys=True).encode("ascii")
    _write_event_lines(packet_root, lines)


def _mutate_missing_stop(packet_root: Path) -> None:
    lines = _event_lines(packet_root)
    consumed: list[bytes] = []
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        if record["kind"] == "stop":
            break
        consumed.append(line)
    _write_event_lines(packet_root, consumed)


def _run_tdd_failure_cases(
    packet: PreparedPacket,
    temporary_root: Path,
) -> tuple[bool, str]:
    if packet.challenge_id != "tdd-manifest-contract":
        return True, ""
    cases = (
        ("invalid-consumed-crc32", _mutate_invalid_crc),
        ("noncanonical-consumed-crc32", _mutate_noncanonical_crc),
        ("duplicate-consumed-sequence", _mutate_duplicate_sequence),
        ("missing-stop", _mutate_missing_stop),
    )
    for case_name, mutate in cases:
        destination = temporary_root / case_name
        _copy_frozen_packet(packet, destination)
        solution = _copy_solution(packet, destination)
        mutate(destination)
        output = destination / "failure-result.json"
        completed = _run_owned(
            _solution_command(solution, destination, output),
            cwd=destination,
        )
        if completed.timed_out or completed.returncode == 0 or output.exists():
            return (
                False,
                f"{case_name}: exit={completed.returncode} "
                f"timeout={completed.timed_out} output_exists={output.exists()} "
                f"stderr={completed.stderr_tail[-500:]}",
            )
    return True, ""


def _input_contract_is_valid(packet: PreparedPacket) -> bool:
    try:
        payload = json.loads((packet.root / "INPUTS.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return payload == {
        "schema": "reverse-benchmark-inputs-v1",
        "challenge_id": packet.challenge_id,
        "input_hashes": packet.input_hashes,
    }


def _submission_manifest_is_valid(
    packet: PreparedPacket,
    manifest: object,
) -> bool:
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema",
        "challenge_id",
        "input_hashes",
        "scope",
    }:
        return False
    scope = manifest.get("scope")
    limitations = scope.get("limitations") if isinstance(scope, dict) else None
    return (
        manifest.get("schema") == SUBMISSION_SCHEMA
        and manifest.get("challenge_id") == packet.challenge_id
        and manifest.get("input_hashes") == packet.input_hashes
        and isinstance(scope, dict)
        and set(scope) == {"complete", "limitations"}
        and scope.get("complete") is True
        and isinstance(limitations, list)
        and all(isinstance(item, str) for item in limitations)
    )


def verify_smoke_submission(packet: PreparedPacket) -> VerificationResult:
    """Verify immutable inputs, exact result, clean reproduction, and tests."""

    errors: list[str] = []
    codes: list[str] = []
    score = 0
    input_valid = True
    for relative_path, expected_hash in packet.input_hashes.items():
        path = packet.root / relative_path
        actual_hash = _sha256(path) if _is_regular_file(path) else None
        if actual_hash != expected_hash:
            errors.append(f"input hash mismatch: {relative_path}")
            codes.append("input-hash-mismatch")
            input_valid = False
    if not _input_contract_is_valid(packet):
        errors.append("INPUTS.json contract mismatch")
        codes.append("input-hash-mismatch")
        input_valid = False
    if input_valid:
        score += 15

    submission = packet.root / "submission"
    result = _load_json(submission / "result.json", errors, codes)
    result_matches, result_detail = _result_matches(
        packet, result, packet.secret.get("expected_result")
    )
    if result_matches:
        score += 40
    elif result is not None:
        errors.append(f"result does not satisfy public result contract: {result_detail}")
        codes.append(
            "schema-mismatch"
            if result_detail.startswith("schema mismatch")
            else "result-mismatch"
        )

    manifest = _load_json(submission / "run_manifest.json", errors, codes)
    if isinstance(manifest, dict):
        if _submission_manifest_is_valid(packet, manifest):
            score += 10
        else:
            errors.append("run manifest contract mismatch")
            codes.append("manifest-mismatch")

    solution_path = submission / "solution.py"
    if not _is_regular_file(solution_path):
        errors.append("missing or unsafe solution.py")
        codes.append("missing-solution")
    elif input_valid:
        try:
            with tempfile.TemporaryDirectory() as directory:
                temporary_root = Path(directory)
                fresh = temporary_root / "fresh-packet"
                _copy_frozen_packet(packet, fresh)
                original_ok, original_detail = _run_reproduction(
                    packet,
                    destination=fresh,
                    expected=packet.secret.get("expected_result"),
                )

                hidden_packet = None
                for offset in range(32):
                    hidden = temporary_root / f"hidden-packet-{offset}"
                    candidate = prepare_smoke_packet(
                        packet.challenge_id,
                        hidden,
                        seed=_hidden_seed(packet) + offset,
                    )
                    if candidate.secret.get("expected_result") != packet.secret.get(
                        "expected_result"
                    ):
                        hidden_packet = candidate
                        break
                if hidden_packet is None:
                    raise ValueError("could not construct a distinct hidden packet")
                hidden_ok, hidden_detail = _run_reproduction(
                    packet,
                    destination=hidden_packet.root,
                    expected=hidden_packet.secret.get("expected_result"),
                    destination_hashes=hidden_packet.input_hashes,
                )
                failure_cases_ok, failure_cases_detail = _run_tdd_failure_cases(
                    packet, temporary_root / "failure-cases"
                )
                if original_ok and hidden_ok and failure_cases_ok:
                    score += 20
                else:
                    errors.append(
                        "solution reproduction failed: "
                        f"original[{original_detail}] hidden[{hidden_detail}] "
                        f"failure_cases[{failure_cases_detail or 'passed'}]"
                    )
                    codes.append("reproduction-failed")

                tests_state, tests_detail = _run_candidate_tests(
                    packet, temporary_root
                )
                if tests_state == "passed":
                    score += 15
                elif tests_state == "missing":
                    errors.append(tests_detail)
                    codes.append("missing-tests")
                elif tests_state == "insensitive":
                    errors.append(tests_detail)
                    codes.append("tests-not-sensitive")
                else:
                    errors.append(tests_detail)
                    codes.append("tests-failed")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            errors.append(f"unsafe or failed candidate execution: {error}")
            codes.append("candidate-execution-failed")

    passed = not errors and score == 100
    if result is None or not input_valid:
        score = 0
    return VerificationResult(
        passed=passed,
        score=score,
        errors=tuple(errors),
        error_codes=tuple(dict.fromkeys(codes)),
    )
