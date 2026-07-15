#!/usr/bin/env python3
"""Collect strict, read-only evidence from one owned Windows mGBA GDB session."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import socket
import subprocess
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


REGISTER_NAMES = [*(f"r{index}" for index in range(13)), "sp", "lr", "pc", "cpsr"]
MGBA_GDB_MAX_MEMORY_READ = 256
ROM_BASE = 0x08000000
ROM_FINGERPRINT_WINDOW = 32
CHILD_OUTPUT_TAIL_LIMIT = 16 * 1024
GDB_HOST = "127.0.0.1"
MGBA_GDB_PORT = 2345


@dataclass(frozen=True)
class StopReply:
    kind: str
    signal: int | None
    exit_code: int | None
    fields: dict[str, str]
    raw: str


@dataclass(frozen=True)
class TcpOwnerRow:
    state: int
    local: tuple[str, int]
    remote: tuple[str, int]
    owner_pid: int


class BoundedTextTail:
    """Thread-safe tail buffer that never retains more than ``limit`` characters."""

    def __init__(self, limit: int = CHILD_OUTPUT_TAIL_LIMIT):
        self.limit = limit
        self._text = ""
        self._lock = threading.Lock()

    def append(self, text: str) -> None:
        with self._lock:
            self._text = (self._text + text)[-self.limit :]

    def value(self) -> str:
        with self._lock:
            return self._text


def start_pipe_drain(pipe: TextIO, tail: BoundedTextTail) -> threading.Thread:
    def drain() -> None:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                return
            tail.append(chunk)

    thread = threading.Thread(target=drain, name="mgba-output-drain", daemon=True)
    thread.start()
    return thread


def encode_packet(payload: str) -> bytes:
    data = payload.encode("ascii")
    checksum = sum(data) & 0xFF
    return b"$" + data + f"#{checksum:02x}".encode("ascii")


def decode_registers(payload: str) -> dict[str, int]:
    if payload.startswith("E"):
        raise RuntimeError(f"GDB register read failed: {payload}")
    raw = bytes.fromhex(payload)
    expected = len(REGISTER_NAMES) * 4
    if len(raw) != expected:
        raise RuntimeError(f"unexpected ARM register payload size: {len(raw)} (expected {expected})")
    return {
        name: int.from_bytes(raw[offset : offset + 4], "little")
        for index, name in enumerate(REGISTER_NAMES)
        for offset in [index * 4]
    }


def parse_memory(payload: str, expected_size: int | None = None) -> bytes:
    if payload.startswith("E"):
        raise RuntimeError(f"GDB memory read failed: {payload}")
    if expected_size is None:
        expected_size = len(payload) // 2
    expected_hex_length = expected_size * 2
    if (
        not payload
        or len(payload) != expected_hex_length
        or any(character not in "0123456789abcdefABCDEF" for character in payload)
    ):
        raise RuntimeError(
            f"malformed GDB memory hex payload: expected {expected_hex_length} "
            f"continuous hex characters, received {payload!r}"
        )
    try:
        return bytes.fromhex(payload)
    except ValueError as error:
        raise RuntimeError(f"malformed GDB memory hex payload: {payload}") from error


def parse_stop_reply(payload: str) -> StopReply:
    if len(payload) >= 3 and payload[0] in {"S", "T"}:
        try:
            signal = int(payload[1:3], 16)
        except ValueError as error:
            raise RuntimeError(f"malformed GDB stop reply: {payload}") from error
        fields: dict[str, str] = {}
        if payload[0] == "T":
            for field in payload[3:].split(";"):
                if not field:
                    continue
                if ":" not in field:
                    raise RuntimeError(f"malformed GDB stop reply field: {payload}")
                name, value = field.split(":", 1)
                fields[name] = value
        return StopReply(
            kind="signal" if payload[0] == "S" else "trap",
            signal=signal,
            exit_code=None,
            fields=fields,
            raw=payload,
        )
    if len(payload) >= 3 and payload[0] == "W":
        try:
            exit_code = int(payload[1:3], 16)
        except ValueError as error:
            raise RuntimeError(f"malformed GDB exit reply: {payload}") from error
        return StopReply(kind="exit", signal=None, exit_code=exit_code, fields={}, raw=payload)
    return StopReply(kind="unknown", signal=None, exit_code=None, fields={}, raw=payload)


def validate_breakpoint_stop(stop: StopReply, registers: dict[str, int], expected: int) -> None:
    if stop.kind not in {"signal", "trap"} or stop.signal != 5:
        raise RuntimeError(f"unexpected GDB stop: {stop.raw}")
    actual = registers["pc"] & ~1
    accepted = {expected & ~1, (expected + 2) & ~1}
    if actual not in accepted:
        raise RuntimeError(f"breakpoint stopped at 0x{actual:08X}; expected PC 0x{expected:08X}")


def build_mgba_command(mgba: str, rom: str, savestate: str | None = None) -> list[str]:
    command = [mgba, "--gdb", "-C", "mute=1", "-C", "volume=0"]
    if savestate:
        command.extend(["--savestate", savestate])
    command.append(rom)
    return command


def windows_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


def ensure_port_available(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if os.name == "nt":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((host, port))
    except OSError as error:
        raise RuntimeError(f"GDB port {host}:{port} is already in use") from error


def _windows_tcp_owner_rows(table_class: int) -> list[TcpOwnerRow]:
    if os.name != "nt":
        raise RuntimeError("GDB TCP ownership can only be proven on Windows")

    af_inet = 2
    insufficient_buffer = 122
    size = ctypes.c_ulong(0)
    api = ctypes.windll.iphlpapi.GetExtendedTcpTable
    result = api(
        None,
        ctypes.byref(size),
        False,
        af_inet,
        table_class,
        0,
    )
    if result != insufficient_buffer:
        raise RuntimeError(f"TCP owner query sizing failed with Windows error {result}")
    buffer = ctypes.create_string_buffer(size.value)
    result = api(
        buffer,
        ctypes.byref(size),
        False,
        af_inet,
        table_class,
        0,
    )
    if result != 0:
        raise RuntimeError(f"TCP owner query failed with Windows error {result}")

    data = buffer.raw[: size.value]
    count = struct.unpack_from("<I", data, 0)[0]
    row = struct.Struct("<6I")
    rows: list[TcpOwnerRow] = []
    for index in range(count):
        (
            state,
            local_address,
            local_port,
            remote_address,
            remote_port,
            owner_pid,
        ) = row.unpack_from(data, 4 + index * row.size)
        rows.append(
            TcpOwnerRow(
                state=state,
                local=(
                    socket.inet_ntoa(struct.pack("<I", local_address)),
                    socket.ntohs(local_port & 0xFFFF),
                ),
                remote=(
                    socket.inet_ntoa(struct.pack("<I", remote_address)),
                    socket.ntohs(remote_port & 0xFFFF),
                ),
                owner_pid=owner_pid,
            )
        )
    return rows


def listener_owner_pids(host: str, port: int) -> set[int]:
    """Return Windows PIDs owning the requested IPv4 listening endpoint."""
    tcp_table_owner_pid_listener = 3
    owners: set[int] = set()
    for row in _windows_tcp_owner_rows(tcp_table_owner_pid_listener):
        if row.local[1] == port and row.local[0] in {host, "0.0.0.0"}:
            owners.add(row.owner_pid)
    return owners


def connection_owner_pids(
    server_local: tuple[str, int],
    server_remote: tuple[str, int],
) -> list[int]:
    """Return owners of the exact established server-side IPv4 TCP row."""
    tcp_table_owner_pid_connections = 4
    mib_tcp_state_established = 5
    return [
        row.owner_pid
        for row in _windows_tcp_owner_rows(tcp_table_owner_pid_connections)
        if row.state == mib_tcp_state_established
        and row.local == server_local
        and row.remote == server_remote
    ]


class GdbRemoteClient:
    def __init__(self, sock: socket.socket):
        self.sock = sock

    @classmethod
    def connect(cls, host: str, port: int, timeout: float) -> "GdbRemoteClient":
        deadline = time.monotonic() + timeout
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            try:
                sock = socket.create_connection((host, port), timeout=min(1.0, timeout))
                sock.settimeout(timeout)
                return cls(sock)
            except OSError as error:
                last_error = error
                time.sleep(0.05)
        raise TimeoutError(f"mGBA GDB endpoint did not open on {host}:{port}") from last_error

    def close(self) -> None:
        self.sock.close()

    def _recv_byte(self) -> bytes:
        data = self.sock.recv(1)
        if not data:
            raise ConnectionError("mGBA closed the GDB connection")
        return data

    def _receive_packet(self, first: bytes | None = None) -> str:
        byte = first
        while byte != b"$":
            byte = self._recv_byte()
        payload = bytearray()
        while True:
            byte = self._recv_byte()
            if byte == b"#":
                break
            payload.extend(byte)
        received_checksum = int((self._recv_byte() + self._recv_byte()).decode("ascii"), 16)
        actual_checksum = sum(payload) & 0xFF
        if received_checksum != actual_checksum:
            self.sock.sendall(b"-")
            raise RuntimeError(
                f"GDB checksum mismatch: received {received_checksum:02x}, expected {actual_checksum:02x}"
            )
        self.sock.sendall(b"+")
        return payload.decode("ascii")

    def command(self, payload: str) -> str:
        packet = encode_packet(payload)
        self.sock.sendall(packet)
        while True:
            byte = self._recv_byte()
            if byte == b"+":
                return self._receive_packet()
            if byte == b"-":
                self.sock.sendall(packet)
                continue
            if byte == b"$":
                return self._receive_packet(first=byte)

    def registers(self) -> dict[str, int]:
        return decode_registers(self.command("g"))

    def read_memory(self, address: int, size: int) -> bytes:
        if type(address) is not int or address < 0 or address > 0xFFFFFFFF:
            raise ValueError("GDB memory address is outside the 32-bit range")
        if type(size) is not int or size <= 0:
            raise ValueError("GDB memory read size must be positive")
        if address + size > 0x100000000:
            raise ValueError("GDB memory range exceeds the 32-bit address space")
        chunks = []
        for offset in range(0, size, MGBA_GDB_MAX_MEMORY_READ):
            chunk_size = min(MGBA_GDB_MAX_MEMORY_READ, size - offset)
            chunk = parse_memory(
                self.command(f"m{address + offset:x},{chunk_size:x}"),
                chunk_size,
            )
            if len(chunk) != chunk_size:
                raise RuntimeError(
                    f"GDB memory chunk length mismatch at 0x{address + offset:08X}: "
                    f"received {len(chunk)}, expected {chunk_size}"
                )
            chunks.append(chunk)
        return b"".join(chunks)


def connect_owned_endpoint(
    host: str,
    port: int,
    timeout: float,
    process: subprocess.Popen[str],
) -> tuple[
    GdbRemoteClient,
    set[int],
    list[int],
    tuple[str, int],
    tuple[str, int],
]:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        returncode = process.poll()
        if returncode is not None:
            raise RuntimeError(
                f"owned mGBA exited with code {returncode} before binding GDB port {port}"
            )
        try:
            sock = socket.create_connection((host, port), timeout=min(0.2, timeout))
            sock.settimeout(timeout)
        except OSError as error:
            last_error = error
            time.sleep(0.05)
            continue

        try:
            if process.poll() is not None:
                raise RuntimeError("owned mGBA exited while GDB endpoint was connecting")
            owners = listener_owner_pids(host, port)
            if process.poll() is not None:
                raise RuntimeError("owned mGBA exited during GDB listener ownership query")
            if owners != {process.pid}:
                owner_text = ",".join(str(pid) for pid in sorted(owners)) or "none"
                raise RuntimeError(
                    f"GDB listener owner mismatch: expected PID {process.pid}, found {owner_text}"
                )
            client_local = (str(sock.getsockname()[0]), int(sock.getsockname()[1]))
            client_peer = (str(sock.getpeername()[0]), int(sock.getpeername()[1]))
            if process.poll() is not None:
                raise RuntimeError("owned mGBA exited before GDB connection ownership query")
            connection_owners = connection_owner_pids(client_peer, client_local)
            if process.poll() is not None:
                raise RuntimeError("owned mGBA exited during GDB connection ownership query")
            if connection_owners != [process.pid]:
                owner_text = ",".join(str(pid) for pid in connection_owners) or "none"
                raise RuntimeError(
                    "GDB connection owner mismatch for "
                    f"{client_peer[0]}:{client_peer[1]} <- "
                    f"{client_local[0]}:{client_local[1]}: "
                    f"expected PID {process.pid}, found {owner_text}"
                )
            return (
                GdbRemoteClient(sock),
                owners,
                connection_owners,
                client_local,
                client_peer,
            )
        except BaseException:
            sock.close()
            raise
    raise TimeoutError(f"mGBA GDB endpoint did not open on {host}:{port}") from last_error


def verify_rom_fingerprint(
    client: GdbRemoteClient,
    rom: Path,
    stop_point: int | None = None,
    *,
    evidence_windows: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    rom_bytes = rom.read_bytes()
    offsets = [0]
    if stop_point is not None:
        stop_offset = (stop_point & ~1) - ROM_BASE
        if stop_offset < 0 or stop_offset >= len(rom_bytes):
            raise RuntimeError(f"stop point 0x{stop_point:08X} is outside ROM fingerprint range")
        if stop_offset not in offsets:
            offsets.append(stop_offset)

    windows = []
    for offset in offsets:
        size = min(ROM_FINGERPRINT_WINDOW, len(rom_bytes) - offset)
        expected = rom_bytes[offset : offset + size]
        address = ROM_BASE + offset
        actual = client.read_memory(address, size)
        if actual != expected:
            raise RuntimeError(
                f"ROM fingerprint mismatch at 0x{address:08X}: "
                f"expected {expected.hex()}, received {actual.hex()}"
            )
        window = {
            "address": address,
            "addressHex": f"0x{address:08X}",
            "size": size,
            "sha256": hashlib.sha256(expected).hexdigest(),
        }
        windows.append(window)
        if evidence_windows is not None:
            evidence_windows.append(window)
    return windows


def close_owned_session(
    client: GdbRemoteClient | None,
    process: subprocess.Popen[str],
    *,
    timeout: float = 2.0,
) -> None:
    errors: list[BaseException] = []
    if client is not None:
        try:
            client.close()
        except BaseException as error:
            errors.append(error)
    try:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)
    except BaseException as error:
        errors.append(error)
    if errors:
        raise RuntimeError("owned mGBA cleanup failed: " + "; ".join(map(str, errors)))


def parse_region(value: str) -> tuple[int, int]:
    try:
        address_text, size_text = value.split(":", 1)
        address, size = int(address_text, 0), int(size_text, 0)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("read region must be ADDRESS:SIZE") from error
    if address < 0 or address > 0xFFFFFFFF or size <= 0 or address + size > 0x100000000:
        raise argparse.ArgumentTypeError("read region must be a positive in-range 32-bit span")
    return address, size


def emit_progress(event: str, **details: object) -> None:
    print(
        "resource-progress "
        + json.dumps({"event": event, **details}, separators=(",", ":"), ensure_ascii=False),
        flush=True,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_evidence(path: Path) -> dict[str, object]:
    return {"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size}


def read_mgba_version(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
            startupinfo=windows_startupinfo(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = completed.stdout.strip()
    return output.splitlines()[0] if output else None


def initial_evidence(args: argparse.Namespace) -> dict[str, object]:
    command = build_mgba_command(
        str(args.mgba),
        str(args.rom),
        str(args.savestate) if args.savestate else None,
    )
    return {
        "schemaVersion": 2,
        "emulator": {"path": str(args.mgba), "sha256": None, "size": None, "version": None},
        "rom": {"path": str(args.rom), "sha256": None, "size": None},
        "savestate": (
            {"path": str(args.savestate), "sha256": None, "size": None}
            if args.savestate
            else None
        ),
        "command": command,
        "port": MGBA_GDB_PORT,
        "listenerOwnerPid": None,
        "listenerOwnerPids": [],
        "connectionOwnerPid": None,
        "connectionOwnerPids": [],
        "connectionLocalEndpoint": None,
        "connectionPeerEndpoint": None,
        "rawStop": None,
        "expectedPc": args.breakpoint,
        "expectedPcHex": f"0x{args.breakpoint:08X}",
        "actualPc": None,
        "actualPcHex": None,
        "registers": {},
        "romFingerprint": [],
        "readRegions": [],
        "stdoutTail": "",
        "stderrTail": "",
        "childReturncode": None,
        "progressErrors": [],
    }


def failure_payload(
    error: BaseException, context: dict[str, object] | None = None
) -> dict[str, object]:
    payload = {"schemaVersion": 2, **(context or {})}
    payload.update(
        {
            "outcome": "not-proven" if isinstance(error, (TimeoutError, socket.timeout)) else "error",
            "errorType": type(error).__name__,
            "error": str(error),
        }
    )
    return payload


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    evidence = initial_evidence(args)
    process: subprocess.Popen[str] | None = None
    client: GdbRemoteClient | None = None
    stdout_tail = BoundedTextTail()
    stderr_tail = BoundedTextTail()
    drain_threads: list[threading.Thread] = []
    primary_error: BaseException | None = None

    def progress(event: str, **details: object) -> None:
        try:
            emit_progress(event, **details)
        except BaseException as error:
            evidence["progressErrors"].append(f"{type(error).__name__}: {error}")

    try:
        emulator = file_evidence(args.mgba)
        emulator["version"] = read_mgba_version(args.mgba)
        evidence["emulator"] = emulator
        evidence["rom"] = file_evidence(args.rom)
        evidence["savestate"] = file_evidence(args.savestate) if args.savestate else None
        ensure_port_available(GDB_HOST, MGBA_GDB_PORT)

        env = os.environ.copy()
        if "sdl" in args.mgba.name.lower():
            env["SDL_VIDEODRIVER"] = "dummy"
            env["SDL_AUDIODRIVER"] = "dummy"
        process = subprocess.Popen(
            evidence["command"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=env,
            startupinfo=windows_startupinfo(),
        )
        if process.stdout is not None:
            drain_threads.append(start_pipe_drain(process.stdout, stdout_tail))
        if process.stderr is not None:
            drain_threads.append(start_pipe_drain(process.stderr, stderr_tail))
        progress("mgba-launched", pid=process.pid)

        (
            client,
            owner_pids,
            connection_owner_ids,
            client_local,
            client_peer,
        ) = connect_owned_endpoint(GDB_HOST, MGBA_GDB_PORT, args.timeout, process)
        evidence["listenerOwnerPid"] = process.pid
        evidence["listenerOwnerPids"] = sorted(owner_pids)
        evidence["connectionOwnerPid"] = connection_owner_ids[0]
        evidence["connectionOwnerPids"] = connection_owner_ids
        evidence["connectionLocalEndpoint"] = {
            "address": client_local[0],
            "port": client_local[1],
        }
        evidence["connectionPeerEndpoint"] = {
            "address": client_peer[0],
            "port": client_peer[1],
        }
        progress("gdb-connected", port=MGBA_GDB_PORT, ownerPid=process.pid)
        verify_rom_fingerprint(
            client,
            args.rom,
            args.breakpoint,
            evidence_windows=evidence["romFingerprint"],
        )
        progress("rom-fingerprint-verified", windows=len(evidence["romFingerprint"]))

        client.command("?")
        response = client.command(f"Z0,{args.breakpoint:x},2")
        if response != "OK":
            raise RuntimeError(f"mGBA rejected breakpoint: {response}")
        progress("stop-point-set", kind="breakpoint", address=f"0x{args.breakpoint:08X}")

        raw_stop = client.command("c")
        evidence["rawStop"] = raw_stop
        stop = parse_stop_reply(raw_stop)
        registers = client.registers()
        actual_pc = registers["pc"] & ~1
        evidence.update(
            {
                "actualPc": actual_pc,
                "actualPcHex": f"0x{actual_pc:08X}",
                "registers": registers,
            }
        )
        validate_breakpoint_stop(stop, registers, args.breakpoint)
        progress("stop-point-verified", response=stop.raw, actualPc=f"0x{actual_pc:08X}")

        for address, size in args.read:
            data = client.read_memory(address, size)
            evidence["readRegions"].append(
                {
                    "address": address,
                    "addressHex": f"0x{address:08X}",
                    "size": size,
                    "hex": data.hex(),
                }
            )
    except BaseException as error:
        primary_error = error
    finally:
        if process is not None:
            try:
                close_owned_session(client, process)
            except BaseException as cleanup_error:
                evidence["cleanupError"] = str(cleanup_error)
                if primary_error is None:
                    primary_error = cleanup_error
            for thread in drain_threads:
                thread.join(timeout=1)
            evidence["childReturncode"] = process.returncode
            progress("mgba-exited", returncode=process.returncode)
        evidence["stdoutTail"] = stdout_tail.value()
        evidence["stderrTail"] = stderr_tail.value()

    if primary_error is not None:
        return failure_payload(primary_error, evidence)
    return {**evidence, "outcome": "verified"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mgba", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--savestate", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--breakpoint", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--read", action="append", type=parse_region, default=[])
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for path in [args.mgba, args.rom, *([args.savestate] if args.savestate else [])]:
            if not path.is_file():
                raise FileNotFoundError(path)
        result = run_probe(args)
    except BaseException as error:
        result = failure_payload(error, initial_evidence(args))

    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if result["outcome"] == "verified":
        try:
            emit_progress("result-written", output=str(args.output), outcome="verified")
        except (BrokenPipeError, OSError):
            pass
        return 0
    try:
        emit_progress(
            "probe-failed",
            output=str(args.output),
            outcome=result["outcome"],
            errorType=result["errorType"],
            error=result["error"],
        )
    except (BrokenPipeError, OSError):
        pass
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
