import argparse
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import nullcontext, redirect_stderr
from pathlib import Path
from unittest.mock import Mock, call, patch

from tools import mgba_gdb_probe as probe


class ScriptedSocket:
    def __init__(self, incoming: bytes):
        self.incoming = bytearray(incoming)
        self.sent: list[bytes] = []

    def recv(self, size: int) -> bytes:
        if not self.incoming:
            return b""
        result = bytes(self.incoming[:size])
        del self.incoming[:size]
        return result

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def close(self) -> None:
        pass


class FakeRspServer:
    def __init__(self, handler, *, close_listener_after_accept=False):
        self.handler = handler
        self.close_listener_after_accept = close_listener_after_accept
        self.commands = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == "nt":
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 2345))
        self.listener.listen(1)
        self.listener.settimeout(1)
        self.connection = None
        self.server_local = None
        self.server_remote = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _recv_byte(self):
        data = self.connection.recv(1)
        if not data:
            raise EOFError
        return data

    def _serve(self):
        try:
            self.connection, _ = self.listener.accept()
            self.server_local = self.connection.getsockname()
            self.server_remote = self.connection.getpeername()
            if self.close_listener_after_accept:
                self.listener.close()
            while True:
                byte = self._recv_byte()
                while byte != b"$":
                    byte = self._recv_byte()
                payload = bytearray()
                while True:
                    byte = self._recv_byte()
                    if byte == b"#":
                        break
                    payload.extend(byte)
                self._recv_byte()
                self._recv_byte()
                command = payload.decode("ascii")
                self.commands.append(command)
                response = self.handler(command)
                self.connection.sendall(b"+" + probe.encode_packet(response))
        except (EOFError, OSError, socket.timeout):
            return
        finally:
            if self.connection is not None:
                self.connection.close()

    def close(self):
        if self.connection is not None:
            self.thread.join(timeout=1)
            if self.thread.is_alive():
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
        self.listener.close()
        self.thread.join(timeout=1)
        if self.connection is not None:
            self.connection.close()


class FakeProcess:
    def __init__(self, server=None, *, pid=4242, returncode=None):
        self.server = server
        self.pid = pid
        self.returncode = returncode
        self.stdout = io.StringIO("fake stdout")
        self.stderr = io.StringIO("fake stderr")

    def poll(self):
        return self.returncode

    def terminate(self):
        if self.server is not None:
            self.server.close()
        self.returncode = 0 if self.returncode is None else self.returncode

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        return self.returncode


LSOF_TCP_FIXTURE = """\
p4242
n127.0.0.1:2345
TST=LISTEN
n127.0.0.1:2345->127.0.0.1:54000
TST=ESTABLISHED
n127.0.0.1:9999->127.0.0.1:54001
TST=ESTABLISHED
p7777
n127.0.0.1:54000->127.0.0.1:2345
TST=ESTABLISHED
n127.0.0.1:2345->127.0.0.1:54000
TST=ESTABLISHED
"""


class DarwinTcpOwnerTests(unittest.TestCase):
    def test_lsof_parser_returns_exact_complete_tcp_records(self):
        records = probe.parse_lsof_tcp_records(LSOF_TCP_FIXTURE)

        self.assertEqual(
            [(record.pid, record.state, record.local, record.remote) for record in records],
            [
                (4242, "LISTEN", ("127.0.0.1", 2345), None),
                (
                    4242,
                    "ESTABLISHED",
                    ("127.0.0.1", 2345),
                    ("127.0.0.1", 54000),
                ),
                (
                    4242,
                    "ESTABLISHED",
                    ("127.0.0.1", 9999),
                    ("127.0.0.1", 54001),
                ),
                (
                    7777,
                    "ESTABLISHED",
                    ("127.0.0.1", 54000),
                    ("127.0.0.1", 2345),
                ),
                (
                    7777,
                    "ESTABLISHED",
                    ("127.0.0.1", 2345),
                    ("127.0.0.1", 54000),
                ),
            ],
        )

    def test_lsof_parser_rejects_malformed_or_incomplete_records(self):
        cases = (
            "pnot-a-pid\nn127.0.0.1:2345\nTST=LISTEN\n",
            "p4242\nTST=LISTEN\n",
            "p4242\nn127.0.0.1:2345\n",
            "p4242\nnlocalhost:2345\nTST=LISTEN\n",
            "p4242\nn127.0.0.1:not-a-port\nTST=LISTEN\n",
            "p4242\nn127.0.0.1:2345\nTST=CLOSE_WAIT\n",
            "p4242\nn127.0.0.1:2345\nTST=ESTABLISHED\n",
        )
        for output in cases:
            with self.subTest(output=output):
                with self.assertRaisesRegex(RuntimeError, "lsof|TCP|PID|endpoint|state"):
                    probe.parse_lsof_tcp_records(output)

    def test_lsof_query_uses_bounded_argv_and_fails_closed(self):
        completed = subprocess.CompletedProcess([], 0, LSOF_TCP_FIXTURE, "")
        with patch.object(probe.subprocess, "run", return_value=completed) as run:
            records = probe._lsof_tcp_owner_records(2345)

        self.assertEqual(len(records), 5)
        run.assert_called_once_with(
            ["/usr/sbin/lsof", "-nP", "-FpnT", "-iTCP:2345"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            check=False,
        )

        failures = (
            subprocess.TimeoutExpired(["/usr/sbin/lsof"], 3),
            OSError("lsof unavailable"),
        )
        for error in failures:
            with self.subTest(error=type(error).__name__):
                with patch.object(probe.subprocess, "run", side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, "lsof"):
                        probe._lsof_tcp_owner_records(2345)

        for completed in (
            subprocess.CompletedProcess([], 1, "", "permission denied"),
            subprocess.CompletedProcess([], 0, "", ""),
        ):
            with self.subTest(returncode=completed.returncode):
                with patch.object(probe.subprocess, "run", return_value=completed):
                    with self.assertRaisesRegex(RuntimeError, "lsof"):
                        probe._lsof_tcp_owner_records(2345)

    def test_darwin_owner_filters_keep_exact_server_direction_and_all_owners(self):
        records = probe.parse_lsof_tcp_records(LSOF_TCP_FIXTURE)
        with (
            patch.object(probe.os, "name", "posix"),
            patch.object(probe, "_lsof_tcp_owner_records", return_value=records),
        ):
            self.assertEqual(probe.listener_owner_pids("127.0.0.1", 2345), {4242})
            self.assertEqual(
                probe.connection_owner_pids(
                    ("127.0.0.1", 2345),
                    ("127.0.0.1", 54000),
                ),
                [4242, 7777],
            )

    @unittest.skipUnless(sys.platform == "darwin", "Darwin lsof is required")
    def test_darwin_lsof_finds_real_loopback_listener_and_connection_owner(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = None
        server = None
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            self.assertEqual(
                probe.listener_owner_pids(*listener.getsockname()),
                {os.getpid()},
            )

            client = socket.create_connection(listener.getsockname())
            server, _ = listener.accept()
            self.assertEqual(
                probe.connection_owner_pids(server.getsockname(), server.getpeername()),
                [os.getpid()],
            )
        finally:
            if server is not None:
                server.close()
            if client is not None:
                client.close()
            listener.close()


class MgbaGdbProbeTests(unittest.TestCase):
    def setUp(self):
        temporary_rom = tempfile.NamedTemporaryFile(delete=False)
        temporary_rom.write(bytes(range(256)) * 4)
        temporary_rom.close()
        self.rom_path = Path(temporary_rom.name)
        temporary_mgba = tempfile.NamedTemporaryFile(delete=False)
        temporary_mgba.write(b"fake-mgba")
        temporary_mgba.close()
        self.mgba_path = Path(temporary_mgba.name)

    def tearDown(self):
        self.rom_path.unlink(missing_ok=True)
        self.mgba_path.unlink(missing_ok=True)

    def make_args(self, **overrides):
        values = {
            "mgba": self.mgba_path,
            "rom": self.rom_path,
            "savestate": None,
            "breakpoint": 0x08000020,
            "read": [(0x02000000, 4)],
            "timeout": 0.5,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def make_rsp_handler(
        self,
        *,
        pc=0x08000022,
        wrong_rom=False,
        register_error=False,
        second_read_error=False,
        read_payload=None,
    ):
        rom = self.rom_path.read_bytes()
        read_count = 0

        def handler(command):
            nonlocal read_count
            if command == "?":
                return "S05"
            if command.startswith("Z0,"):
                return "OK"
            if command == "c":
                return "S05"
            if command == "g":
                if register_error:
                    return "E01"
                registers = list(range(17))
                registers[15] = pc
                return b"".join(value.to_bytes(4, "little") for value in registers).hex()
            if command.startswith("m"):
                address_text, size_text = command[1:].split(",", 1)
                address = int(address_text, 16)
                size = int(size_text, 16)
                if 0x08000000 <= address < 0x08000000 + len(rom):
                    data = rom[address - 0x08000000 : address - 0x08000000 + size]
                    if wrong_rom:
                        data = bytes([data[0] ^ 0xFF]) + data[1:]
                    return data.hex()
                read_count += 1
                if second_read_error and read_count == 2:
                    return "E06"
                if read_payload is not None:
                    return read_payload
                return (bytes([read_count]) * size).hex()
            raise AssertionError(f"unexpected RSP command: {command}")

        return handler

    def run_fake_rsp(
        self,
        handler,
        *,
        args=None,
        process_pid=4242,
        owner_pids=None,
        connection_owner_pids=None,
        connection_owner_side_effect=None,
        use_real_connection_owner=False,
        close_listener_after_accept=False,
    ):
        holder = {}

        def launch(*unused_args, **unused_kwargs):
            server = FakeRspServer(
                handler,
                close_listener_after_accept=close_listener_after_accept,
            )
            process = FakeProcess(server, pid=process_pid)
            holder["server"] = server
            holder["process"] = process
            return process

        connection_owner_query = patch.object(
            probe,
            "connection_owner_pids",
            return_value=(
                [process_pid] if connection_owner_pids is None else connection_owner_pids
            ),
            side_effect=connection_owner_side_effect,
            create=True,
        )
        connection_owner_context = (
            nullcontext() if use_real_connection_owner else connection_owner_query
        )
        with (
            patch.object(probe.subprocess, "Popen", side_effect=launch),
            patch.object(probe, "read_mgba_version", return_value="mGBA 0.10.5"),
            patch.object(
                probe,
                "listener_owner_pids",
                return_value={process_pid} if owner_pids is None else owner_pids,
                create=True,
            ),
            connection_owner_context as connection_owner_mock,
        ):
            result = probe.run_probe(args or self.make_args())
        if not use_real_connection_owner:
            holder["connection_owner_query"] = connection_owner_mock
        return result, holder

    def test_build_command_uses_gdb_and_loads_state_before_rom(self):
        self.assertEqual(
            probe.build_mgba_command("mGBA.exe", "probe.gba", "battle.ss9"),
            [
                "mGBA.exe",
                "--gdb",
                "-C",
                "mute=1",
                "-C",
                "volume=0",
                "--savestate",
                "battle.ss9",
                "probe.gba",
            ],
        )

    def test_encode_packet_uses_rsp_checksum(self):
        self.assertEqual(probe.encode_packet("m203f080,10"), b"$m203f080,10#8d")

    def test_rsp_ack_returns_packet_and_acknowledges_response(self):
        sock = ScriptedSocket(b"+" + probe.encode_packet("OK"))
        client = probe.GdbRemoteClient(sock)

        self.assertEqual(client.command("?"), "OK")
        self.assertEqual(sock.sent, [probe.encode_packet("?"), b"+"])

    def test_rsp_nack_retransmits_command(self):
        sock = ScriptedSocket(b"-+" + probe.encode_packet("OK"))
        client = probe.GdbRemoteClient(sock)

        self.assertEqual(client.command("?"), "OK")
        self.assertEqual(sock.sent[:2], [probe.encode_packet("?"), probe.encode_packet("?")])

    def test_rsp_checksum_mismatch_sends_nack(self):
        sock = ScriptedSocket(b"+$OK#00")
        client = probe.GdbRemoteClient(sock)

        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            client.command("?")
        self.assertEqual(sock.sent[-1], b"-")

    def test_decode_registers_uses_arm_little_endian_order(self):
        values = list(range(17))
        payload = b"".join(value.to_bytes(4, "little") for value in values).hex()
        registers = probe.decode_registers(payload)
        self.assertEqual(registers["r0"], 0)
        self.assertEqual(registers["r12"], 12)
        self.assertEqual(registers["sp"], 13)
        self.assertEqual(registers["lr"], 14)
        self.assertEqual(registers["pc"], 15)
        self.assertEqual(registers["cpsr"], 16)

    def test_parse_memory_rejects_error_packets(self):
        self.assertEqual(probe.parse_memory("50434f31"), bytes.fromhex("50434f31"))
        with self.assertRaisesRegex(RuntimeError, "GDB memory read failed"):
            probe.parse_memory("E01")

    def test_large_memory_reads_are_split_at_mgba_packet_limit(self):
        client = probe.GdbRemoteClient.__new__(probe.GdbRemoteClient)
        client.command = Mock(
            side_effect=[
                (bytes([0x11]) * 256).hex(),
                (bytes([0x22]) * 256).hex(),
                (bytes([0x33]) * 88).hex(),
            ]
        )

        data = client.read_memory(0x02000000, 600)

        self.assertEqual(data, bytes([0x11]) * 256 + bytes([0x22]) * 256 + bytes([0x33]) * 88)
        self.assertEqual(
            client.command.call_args_list,
            [
                call("m2000000,100"),
                call("m2000100,100"),
                call("m2000200,58"),
            ],
        )

    def test_memory_read_reports_one_error_subchunk(self):
        client = probe.GdbRemoteClient.__new__(probe.GdbRemoteClient)
        client.command = Mock(side_effect=[(bytes(256)).hex(), "E06"])

        with self.assertRaisesRegex(RuntimeError, "E06"):
            client.read_memory(0x02000000, 600)

    def test_memory_read_rejects_short_long_and_malformed_subchunks(self):
        for payload in ("00", bytes(257).hex(), "xyz"):
            with self.subTest(payload=payload[:8]):
                client = probe.GdbRemoteClient.__new__(probe.GdbRemoteClient)
                client.command = Mock(return_value=payload)
                with self.assertRaisesRegex(RuntimeError, "memory|hex|chunk"):
                    client.read_memory(0x02000000, 256)

    def test_memory_read_rejects_whitespace_empty_and_odd_length_hex(self):
        for payload in ("00 00", "00\t00", "00\r00", "00\n00", "", "000"):
            with self.subTest(payload=repr(payload)):
                client = probe.GdbRemoteClient.__new__(probe.GdbRemoteClient)
                client.command = Mock(return_value=payload)
                with self.assertRaisesRegex(RuntimeError, "memory|hex|chunk"):
                    client.read_memory(0x02000000, 2)

    def test_memory_read_rejects_nonpositive_and_overflowing_ranges(self):
        client = probe.GdbRemoteClient.__new__(probe.GdbRemoteClient)
        client.command = Mock()
        for address, size in (
            (0x02000000, 0),
            (0x02000000, -1),
            (-1, 1),
            (0xFFFFFFFF, 2),
        ):
            with self.subTest(address=address, size=size):
                with self.assertRaisesRegex(ValueError, "range|size|address"):
                    client.read_memory(address, size)
        client.command.assert_not_called()

    def test_stop_reply_parses_signal_trap_and_exit(self):
        signal = probe.parse_stop_reply("S05")
        trap = probe.parse_stop_reply("T05thread:1;20:34120708;")
        exited = probe.parse_stop_reply("W00")

        self.assertEqual((signal.kind, signal.signal, signal.exit_code), ("signal", 5, None))
        self.assertEqual((trap.kind, trap.signal, trap.fields), ("trap", 5, {"thread": "1", "20": "34120708"}))
        self.assertEqual((exited.kind, exited.signal, exited.exit_code), ("exit", None, 0))

    def test_stop_reply_requires_target_pc(self):
        stop = probe.parse_stop_reply("T05thread:1;")
        with self.assertRaisesRegex(RuntimeError, "expected PC"):
            probe.validate_breakpoint_stop(stop, {"pc": 0x08070000}, 0x08073946)

    def test_stop_reply_accepts_thumb_breakpoint_pc_advance(self):
        stop = probe.parse_stop_reply("S05")
        probe.validate_breakpoint_stop(stop, {"pc": 0x08073948}, 0x08073946)

    def test_stop_reply_rejects_exit_as_breakpoint(self):
        stop = probe.parse_stop_reply("W00")
        with self.assertRaisesRegex(RuntimeError, "unexpected GDB stop"):
            probe.validate_breakpoint_stop(stop, {"pc": 0x08073946}, 0x08073946)

    def test_port_conflict_fails_before_launcher(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                probe.ensure_port_available("127.0.0.1", port)

    def test_run_probe_checks_port_before_launcher(self):
        args = self.make_args(read=[])
        with (
            patch.object(
                probe,
                "ensure_port_available",
                side_effect=RuntimeError("GDB port 127.0.0.1:2345 is already in use"),
            ) as precheck,
            patch.object(probe.subprocess, "Popen") as launcher,
            patch.object(probe, "read_mgba_version", return_value="mGBA 0.10.5"),
        ):
            result = probe.run_probe(args)

        launcher.assert_not_called()
        precheck.assert_called_once_with("127.0.0.1", 2345)
        self.assertEqual(result["outcome"], "error")
        self.assertIn("already in use", result["error"])

    def test_parser_rejects_configurable_port(self):
        parser = probe.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "--mgba", "mGBA.exe",
                        "--rom", "probe.gba",
                        "--output", "result.json",
                        "--breakpoint", "0x08000000",
                        "--port", "3456",
                    ]
                )

    def test_full_fake_rsp_wiring_verifies_owned_session_and_all_gates(self):
        result, holder = self.run_fake_rsp(self.make_rsp_handler())

        self.assertEqual(result["outcome"], "verified")
        self.assertEqual(result["listenerOwnerPid"], 4242)
        self.assertEqual(result["connectionOwnerPid"], 4242)
        self.assertEqual(result["connectionOwnerPids"], [4242])
        self.assertEqual(result["rawStop"], "S05")
        self.assertEqual(result["actualPc"], 0x08000022)
        self.assertEqual(result["readRegions"][0]["hex"], "01010101")
        commands = holder["server"].commands
        self.assertIn("m8000000,20", commands)
        self.assertIn("m8000020,20", commands)
        self.assertIn("c", commands)
        self.assertIn("g", commands)
        self.assertIn("m2000000,4", commands)
        holder["connection_owner_query"].assert_called_once_with(
            holder["server"].server_local,
            holder["server"].server_remote,
        )
        self.assertEqual(
            result["connectionLocalEndpoint"],
            {
                "address": holder["server"].server_remote[0],
                "port": holder["server"].server_remote[1],
            },
        )
        self.assertEqual(
            result["connectionPeerEndpoint"],
            {
                "address": holder["server"].server_local[0],
                "port": holder["server"].server_local[1],
            },
        )

    def test_mixed_listener_owners_are_not_verified(self):
        result, _ = self.run_fake_rsp(
            self.make_rsp_handler(),
            owner_pids={4242, 9999},
            connection_owner_pids=[4242],
        )

        self.assertEqual(result["outcome"], "error")
        self.assertIn("listener owner", result["error"].lower())

    def test_connection_owner_query_failures_are_not_verified(self):
        cases = (
            ([], None),
            ([4242, 4242], None),
            ([4242, 9999], None),
            (None, RuntimeError("TCP owner query failed with Windows error 5")),
        )
        for owner_pids, query_error in cases:
            with self.subTest(owner_pids=owner_pids, query_error=query_error):
                result, _ = self.run_fake_rsp(
                    self.make_rsp_handler(),
                    connection_owner_pids=owner_pids,
                    connection_owner_side_effect=query_error,
                )

                self.assertEqual(result["outcome"], "error")
                self.assertNotEqual(result["outcome"], "verified")

    def test_owned_child_exit_during_connection_owner_query_is_not_verified(self):
        holder = {}

        def exit_owned_process(*unused_args):
            holder["process"].returncode = 1
            return [4242]

        def launch(*unused_args, **unused_kwargs):
            server = FakeRspServer(self.make_rsp_handler())
            process = FakeProcess(server, pid=4242)
            holder["process"] = process
            return process

        with (
            patch.object(probe.subprocess, "Popen", side_effect=launch),
            patch.object(probe, "read_mgba_version", return_value="mGBA 0.10.5"),
            patch.object(probe, "listener_owner_pids", return_value={4242}),
            patch.object(probe, "connection_owner_pids", side_effect=exit_owned_process),
        ):
            result = probe.run_probe(self.make_args())

        self.assertEqual(result["outcome"], "error")
        self.assertIn("exited", result["error"])

    @unittest.skipUnless(os.name == "nt", "Windows TCP owner table is required")
    def test_listener_handoff_to_owned_pid_does_not_verify_external_connection(self):
        result, _ = self.run_fake_rsp(
            self.make_rsp_handler(),
            owner_pids={4242},
            use_real_connection_owner=True,
            close_listener_after_accept=True,
        )

        self.assertEqual(result["outcome"], "error")
        self.assertIn("connection owner", result["error"].lower())

    @unittest.skipUnless(os.name == "nt", "Windows TCP owner table is required")
    def test_windows_connection_owner_query_finds_real_loopback_server_pid(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            with socket.create_connection(listener.getsockname()) as client:
                server, _ = listener.accept()
                with server:
                    self.assertTrue(
                        hasattr(probe, "connection_owner_pids"),
                        "production connection owner query is missing",
                    )
                    owners = probe.connection_owner_pids(
                        server.getsockname(),
                        server.getpeername(),
                    )

        self.assertEqual(owners, [os.getpid()])

    def test_external_same_rom_endpoint_is_not_owned(self):
        result, _ = self.run_fake_rsp(
            self.make_rsp_handler(), process_pid=4242, owner_pids={9999}
        )

        self.assertEqual(result["outcome"], "error")
        self.assertIn("owner", result["error"].lower())

    def test_owned_child_bind_failure_is_not_verified(self):
        dead = FakeProcess(returncode=1)
        with (
            patch.object(probe.subprocess, "Popen", return_value=dead),
            patch.object(probe, "read_mgba_version", return_value="mGBA 0.10.5"),
        ):
            result = probe.run_probe(self.make_args(timeout=0.05))

        self.assertEqual(result["outcome"], "error")
        self.assertIn("exited", result["error"])

    def test_full_wiring_rejects_wrong_rom_and_wrong_stop_pc(self):
        wrong_rom, _ = self.run_fake_rsp(self.make_rsp_handler(wrong_rom=True))
        self.assertEqual(wrong_rom["outcome"], "error")
        self.assertIn("ROM fingerprint", wrong_rom["error"])

        wrong_pc, _ = self.run_fake_rsp(self.make_rsp_handler(pc=0x08000080))
        self.assertEqual(wrong_pc["outcome"], "error")
        self.assertIn("expected PC", wrong_pc["error"])

    def test_failure_evidence_keeps_raw_stop_and_each_completed_read(self):
        register_failure, _ = self.run_fake_rsp(
            self.make_rsp_handler(register_error=True), args=self.make_args(read=[])
        )
        self.assertEqual(register_failure["outcome"], "error")
        self.assertEqual(register_failure["rawStop"], "S05")

        second_read_failure, _ = self.run_fake_rsp(
            self.make_rsp_handler(second_read_error=True),
            args=self.make_args(read=[(0x02000000, 4), (0x02000010, 4)]),
        )
        self.assertEqual(second_read_failure["outcome"], "error")
        self.assertEqual(len(second_read_failure["readRegions"]), 1)
        self.assertEqual(second_read_failure["readRegions"][0]["address"], 0x02000000)

    def test_malformed_memory_region_never_writes_success_evidence(self):
        for payload in ("00 00", "00\t00", "00\r00", "00\n00", "", "000"):
            with self.subTest(payload=repr(payload)):
                result, _ = self.run_fake_rsp(
                    self.make_rsp_handler(read_payload=payload),
                )

                self.assertEqual(result["outcome"], "error")
                self.assertEqual(result["readRegions"], [])

    def test_file_hashes_are_kept_when_port_precheck_fails(self):
        args = self.make_args()
        with (
            patch.object(probe, "ensure_port_available", side_effect=RuntimeError("occupied")),
            patch.object(probe.subprocess, "Popen") as launcher,
            patch.object(probe, "read_mgba_version", return_value="mGBA 0.10.5"),
        ):
            result = probe.run_probe(args)

        launcher.assert_not_called()
        self.assertEqual(result["emulator"]["sha256"], probe.sha256_file(self.mgba_path))
        self.assertEqual(result["rom"]["sha256"], probe.sha256_file(self.rom_path))

    def test_broken_progress_pipe_does_not_replace_probe_result(self):
        with patch.object(probe, "emit_progress", side_effect=BrokenPipeError("closed")):
            result, _ = self.run_fake_rsp(self.make_rsp_handler())

        self.assertEqual(result["outcome"], "verified")
        self.assertTrue(result["progressErrors"])

    def test_cleanup_never_sends_remote_kill(self):
        client = Mock()
        process = Mock()
        probe.close_owned_session(client, process)

        self.assertNotIn(call("k"), client.command.call_args_list)
        client.close.assert_called_once_with()
        process.terminate.assert_called_once_with()

    def test_rom_fingerprint_accepts_matching_endpoint_windows(self):
        client = Mock()
        client.read_memory.side_effect = lambda address, size: self.rom_path.read_bytes()[
            address - 0x08000000 : address - 0x08000000 + size
        ]

        windows = probe.verify_rom_fingerprint(client, self.rom_path, 0x08000080)

        self.assertEqual([window["address"] for window in windows], [0x08000000, 0x08000080])

    def test_rom_fingerprint_rejects_wrong_endpoint(self):
        client = Mock()
        client.read_memory.return_value = b"wrong"
        with self.assertRaisesRegex(RuntimeError, "ROM fingerprint"):
            probe.verify_rom_fingerprint(client, self.rom_path)

    def test_child_output_tails_are_bounded(self):
        tail = probe.BoundedTextTail(32)
        thread = probe.start_pipe_drain(io.StringIO("before-" + "x" * 64 + "-after"), tail)
        thread.join(timeout=1)

        self.assertFalse(thread.is_alive())
        self.assertLessEqual(len(tail.value()), 32)
        self.assertTrue(tail.value().endswith("-after"))

    def test_windows_launch_is_hidden(self):
        startupinfo = probe.windows_startupinfo()
        if os.name == "nt":
            self.assertEqual(
                startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW,
                subprocess.STARTF_USESHOWWINDOW,
            )
            self.assertEqual(startupinfo.wShowWindow, subprocess.SW_HIDE)
        else:
            self.assertIsNone(startupinfo)

    def test_parser_rejects_removed_input_and_watch_interfaces(self):
        parser = probe.build_parser()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "--mgba",
                        "mGBA.exe",
                        "--rom",
                        "probe.gba",
                        "--output",
                        "result.json",
                        "--breakpoint",
                        "0x08000000",
                        "--key",
                        "A",
                    ]
                )
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "--mgba",
                        "mGBA.exe",
                        "--rom",
                        "probe.gba",
                        "--output",
                        "result.json",
                        "--watch-write",
                        "0x04000130",
                    ]
                )

    def test_failure_payload_marks_timeouts_not_proven_and_keeps_context(self):
        payload = probe.failure_payload(
            TimeoutError("breakpoint not reached"),
            {"command": ["mGBA.exe"], "port": 2345, "stdoutTail": "bounded"},
        )

        self.assertEqual(payload["outcome"], "not-proven")
        self.assertEqual(payload["errorType"], "TimeoutError")
        self.assertEqual(payload["command"], ["mGBA.exe"])
        self.assertEqual(payload["stdoutTail"], "bounded")


if __name__ == "__main__":
    unittest.main()
