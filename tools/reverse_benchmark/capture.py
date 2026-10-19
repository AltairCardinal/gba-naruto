"""Capture a child process's JSONL/text streams with monotonic timestamps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TextIO


_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPENAI_SECRET_RE = re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{20,}")
_BEARER_SECRET_RE = re.compile(
    r"(?i)(\b(?:authorization\s*:\s*)?bearer\s+)[A-Za-z0-9._~+/=-]{8,}"
)
_JWT_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
    r"[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
)


def _redact_credential_material(
    text: str, sensitive_values: tuple[str, ...]
) -> tuple[str, bool]:
    redacted = text
    for value in sensitive_values:
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    redacted = _OPENAI_SECRET_RE.sub("[REDACTED]", redacted)
    redacted = _BEARER_SECRET_RE.sub(r"\1[REDACTED]", redacted)
    redacted = _JWT_SECRET_RE.sub("[REDACTED]", redacted)
    return redacted, redacted != text


def contains_credential_material(
    text: str, sensitive_values: tuple[str, ...] = ()
) -> bool:
    """Return whether text contains an explicit or credential-shaped secret."""

    _, detected = _redact_credential_material(text, sensitive_values)
    return detected


def contains_credential_material_bytes(
    data: bytes, sensitive_values: tuple[str, ...] = ()
) -> bool:
    """Apply the same credential detector to arbitrary archived bytes."""

    return contains_credential_material(
        data.decode("utf-8", errors="replace"), sensitive_values
    )


def _write_event(stream: TextIO, event: dict[str, object], lock: threading.Lock) -> None:
    encoded = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    with lock:
        stream.write(encoded + "\n")
        stream.flush()


def _drain(
    source: TextIO,
    destination: TextIO,
    *,
    stream_name: str,
    lock: threading.Lock,
    activity_lock: threading.Lock,
    errors: queue.Queue[str],
    sensitive_values: tuple[str, ...] = (),
    credential_detected: threading.Event | None = None,
) -> None:
    try:
        for raw_line in iter(source.readline, ""):
            safe_line, detected = _redact_credential_material(
                raw_line.rstrip("\r\n"), sensitive_values
            )
            if detected and credential_detected is not None:
                credential_detected.set()
            _write_event(
                destination,
                {
                    "type": "stream.line",
                    "stream": stream_name,
                    "monotonic_ns": time.monotonic_ns(),
                    "line": safe_line,
                },
                lock,
            )
            # The resource guard monitors this wrapper's pipes rather than the
            # nested model process. Emit a content-free complete line so genuine
            # model activity refreshes the guard without leaking response text.
            with activity_lock:
                sys.stdout.write("benchmark-child-activity\n")
                sys.stdout.flush()
    except Exception as error:
        errors.put(type(error).__name__)


def _join_drain_threads(
    threads: tuple[threading.Thread, ...], *, timeout: float
) -> None:
    for thread in threads:
        thread.join(timeout=timeout)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("stream reader did not finish after child exit")


def _raise_reader_errors(errors: queue.Queue[str]) -> None:
    if not errors.empty():
        raise RuntimeError("stream reader failed before reaching EOF")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture one benchmark child without exposing credentials in logs."
    )
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--stderr", required=True, type=Path)
    parser.add_argument("--stdin", required=True, type=Path)
    parser.add_argument("--redact-env", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in raw_argv:
        raise SystemExit("a literal -- separator is required before the command")
    separator = raw_argv.index("--")
    args = build_parser().parse_args(raw_argv[:separator])
    command = raw_argv[separator + 1 :]
    if not command:
        raise SystemExit("a command is required after --")
    if not args.stdin.is_file():
        raise SystemExit(f"stdin file does not exist: {args.stdin}")
    if args.events.resolve() == args.stderr.resolve():
        raise SystemExit("events and stderr paths must differ")
    if any(not _ENV_NAME_RE.fullmatch(name) for name in args.redact_env):
        raise SystemExit("--redact-env names must be valid environment variables")
    sensitive_values = tuple(
        value
        for name in args.redact_env
        if (value := os.environ.get(name))
    )
    args.events.parent.mkdir(parents=True, exist_ok=True)
    args.stderr.parent.mkdir(parents=True, exist_ok=True)
    command_contract = json.dumps(command, separators=(",", ":")).encode("utf-8")
    with (
        args.stdin.open("r", encoding="utf-8") as stdin_stream,
        args.events.open("x", encoding="utf-8") as stdout_log,
        args.stderr.open("x", encoding="utf-8") as stderr_log,
    ):
        stdout_lock = threading.Lock()
        stderr_lock = threading.Lock()
        activity_lock = threading.Lock()
        reader_errors: queue.Queue[str] = queue.Queue()
        credential_detected = threading.Event()
        _write_event(
            stdout_log,
            {
                "type": "process.started",
                "monotonic_ns": time.monotonic_ns(),
                "executable": Path(command[0]).name,
                "command_sha256": hashlib.sha256(command_contract).hexdigest(),
            },
            stdout_lock,
        )
        process = subprocess.Popen(
            command,
            stdin=stdin_stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_thread = threading.Thread(
            target=_drain,
            args=(process.stdout, stdout_log),
            kwargs={
                "stream_name": "stdout",
                "lock": stdout_lock,
                "activity_lock": activity_lock,
                "errors": reader_errors,
                "sensitive_values": sensitive_values,
                "credential_detected": credential_detected,
            },
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_drain,
            args=(process.stderr, stderr_log),
            kwargs={
                "stream_name": "stderr",
                "lock": stderr_lock,
                "activity_lock": activity_lock,
                "errors": reader_errors,
                "sensitive_values": sensitive_values,
                "credential_detected": credential_detected,
            },
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        exit_code = process.wait()
        _join_drain_threads((stdout_thread, stderr_thread), timeout=5)
        _raise_reader_errors(reader_errors)
        if credential_detected.is_set():
            _write_event(
                stdout_log,
                {
                    "type": "security.credential-material-redacted",
                    "monotonic_ns": time.monotonic_ns(),
                },
                stdout_lock,
            )
        _write_event(
            stdout_log,
            {
                "type": "process.exited",
                "monotonic_ns": time.monotonic_ns(),
                "exit_code": exit_code,
            },
            stdout_lock,
        )
    return 86 if credential_detected.is_set() else exit_code


if __name__ == "__main__":
    raise SystemExit(main())
