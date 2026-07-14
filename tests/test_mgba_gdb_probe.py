import argparse
import io
import os
import socket
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
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


class MgbaGdbProbeTests(unittest.TestCase):
    def setUp(self):
        temporary_rom = tempfile.NamedTemporaryFile(delete=False)
        temporary_rom.write(bytes(range(256)) * 4)
        temporary_rom.close()
        self.rom_path = Path(temporary_rom.name)

    def tearDown(self):
        self.rom_path.unlink(missing_ok=True)

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
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            args = argparse.Namespace(
                mgba=Path("mGBA.exe"),
                rom=self.rom_path,
                savestate=None,
                breakpoint=0x08000020,
                read=[],
                port=listener.getsockname()[1],
                timeout=0.1,
            )
            with patch.object(probe.subprocess, "Popen") as launcher:
                result = probe.run_probe(args)

        launcher.assert_not_called()
        self.assertEqual(result["outcome"], "error")
        self.assertIn("already in use", result["error"])

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
