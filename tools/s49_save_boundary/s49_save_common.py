#!/usr/bin/env python3
"""Shared constants and helpers for the S49 save / boundary forensics.

Everything here is derived from two sources that this stream treats as
read-only ground truth:

* the reverse line's save descriptor bank
  (``D:\\Shell\\Github\\gba-naruto-reverse\\sequel\\content\\save-state\\bank.json``)
  -- the original game's ten SRAM records,
* the remake tree's own save codec
  (``game/include/konoha/battle_campaign_save.h``) -- the two 4096-byte
  ``KBCS`` slots.

The descriptor table is embedded here so the tool still runs when the reverse
line is not mounted, and it is cross-checked against the reverse line on every
run (``check_descriptor_bank``) so a stale copy cannot silently pass.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

REMAKE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
REVERSE_ROOT = pathlib.Path(r"D:\Shell\Github\gba-naruto-reverse")

# --- original side ---------------------------------------------------------
ORIGINAL_ROM = REMAKE_ROOT / "rom" / "base.gba"
ORIGINAL_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
BATTLE14_STATE = (
    REMAKE_ROOT
    / "artifacts"
    / "runtime-checkpoints"
    / "scenario-49-battle-14-entry.ss9"
)
BATTLE14_STATE_SHA256 = (
    "a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1"
)
#: Named original-side checkpoints of battle 14, from the reverse line's
#: natural-runtime checkpoint set.  ``post-battle`` is the state *after* the
#: battle was won (the task menu that follows it), which is the only
#: first-hand "original post-battle" artifact that exists.
ORIGINAL_CHECKPOINTS = [
    (
        "original-pre-battle",
        "scenario-49-battle-14-entry.ss9",
        "a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1",
    ),
    (
        "original-battle-tool67-entry",
        "scenario-49-battle-14-tool67-entry.ss9",
        "2c95de937efb785d537c45f39224bb3fdae319e410f6abbc3cbdfcc32fb2812c",
    ),
    (
        "original-battle-tool67-confirmation",
        "scenario-49-battle-14-tool67-confirmation.ss9",
        "95cc6805139fa6bad2a8af3353bcc161b38db51067b558f02b6c7c1dc4764012",
    ),
    (
        "original-battle-tool37-confirmation",
        "scenario-49-battle-14-tool37-confirmation.ss9",
        "af37457d4cd41e180e61338fed77d6322b4aecd21386917739f2e56599708a46",
    ),
    (
        "original-battle-turn4-two-kills",
        "scenario-49-battle-14-turn4-two-kills.ss9",
        "e8b2a5ee0cc4dfbcf89086c8a5fd8fb2bc9e38b9a7bec83cfcb2e3e2a44de350",
    ),
    (
        "original-post-battle",
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        "8dfca22976fdb741bf8d2521aab8f03e067781c9c2284d003f8bfe6893f76484",
    ),
]
CHECKPOINT_DIR = REMAKE_ROOT / "artifacts" / "runtime-checkpoints"
#: A genuine original save image written by the in-game Save menu
#: (reverse line artifact, tutorial victory flow).
ORIGINAL_REFERENCE_SAVE = (
    REVERSE_ROOT / "artifacts" / "runtime-checkpoints" / "tutorial-ui-save.sav"
)
ORIGINAL_REFERENCE_SAVE_SHA256 = (
    "9fedf6bf1c43ad08f7c821c76914726801f9a96147b64b181baed7562e0a972b"
)
ORIGINAL_SCRIPTS = REMAKE_ROOT / "tools" / "butano"

# --- remake side -----------------------------------------------------------
REMAKE_ROM = REMAKE_ROOT / "butano-sequel" / "butano-sequel.gba"

# --- instrument ------------------------------------------------------------
PRIVATE_PROBE = REPO / "build" / "mgba-probe-w4" / "mgba-probe.exe"
SHARED_PROBE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
PROBE_CLIENT = REPO / "tools" / "mgba_probe" / "probe_client.py"

WORK = REPO / "build" / "s49-save-boundary"
SRAM_DIR = WORK / "sram"
RECEIPTS = WORK / "receipts"

#: GBA cartridge SRAM lives at 0x0E000000..0x0E00FFFF on both ROMs.
SRAM_BASE = 0x0E000000
SRAM_SIZE = 32768

# --- original save format --------------------------------------------------
#: Every active record of the original starts with this 19-byte identity
#: header, followed by ``payload_length`` payload bytes and one checksum
#: byte.  Records advance by ``payload_length + 0x14``.
ORIGINAL_RECORD_HEADER = b"Naruto-KONOHASENKI\x00"
ORIGINAL_RECORD_HEADER_SIZE = 0x13
ORIGINAL_SRAM_ADVANCE_OVERHEAD = 0x14

#: Embedded copy of ``sequel/content/save-state/bank.json`` (entries only).
ORIGINAL_DESCRIPTORS = [
    {"index": 0, "ewram_buffer": 33697328, "payload_length": 4732},
    {"index": 1, "ewram_buffer": 33697328, "payload_length": 4732},
    {"index": 2, "ewram_buffer": 33702060, "payload_length": 20},
    {"index": 3, "ewram_buffer": 33697328, "payload_length": 4732},
    {"index": 4, "ewram_buffer": 33702060, "payload_length": 20},
    {"index": 5, "ewram_buffer": 33712132, "payload_length": 8},
    {"index": 6, "ewram_buffer": 33713096, "payload_length": 24},
    {"index": 7, "ewram_buffer": 33702080, "payload_length": 6084},
    {"index": 8, "ewram_buffer": 33708164, "payload_length": 1404},
    {"index": 9, "ewram_buffer": 33711620, "payload_length": 512},
]

#: The original's descriptor 7 payload is the battle unit pool: 13 slots of
#: 0x1D4 bytes (see notes/s49-fidelity/C-logic-state.md 4.2).
ORIGINAL_BATTLE_POOL_DESCRIPTOR = 7
ORIGINAL_BATTLE_POOL_SLOT_SIZE = 0x1D4
ORIGINAL_BATTLE_POOL_SLOTS = 13

# --- remake save format ----------------------------------------------------
REMAKE_SLOT_SIZE = 4096
REMAKE_SLOT_COUNT = 2
REMAKE_MAGIC = b"KBCS"
REMAKE_VERSION = 2
REMAKE_PAYLOAD_OFFSET = 12
REMAKE_CRC_OFFSET = REMAKE_SLOT_SIZE - 4
REMAKE_HEADER_SIZE = 12
REMAKE_CAMPAIGN_HEADER_SIZE = 10
REMAKE_NINJA_TOOL_CAPACITY = 94
REMAKE_MATERIAL_CAPACITY = 18
REMAKE_PARTY_CAPACITY = 3
REMAKE_CHARACTER_CAPACITY = 63
REMAKE_PRIMARY_ACTION_CAPACITY = 15
REMAKE_SECONDARY_ACTION_CAPACITY = 24
REMAKE_EQUIPPED_TOOL_CAPACITY = 9
REMAKE_CHARACTER_SIZE = 54
REMAKE_INVENTORY_SIZE = (
    REMAKE_NINJA_TOOL_CAPACITY + REMAKE_MATERIAL_CAPACITY
)
REMAKE_PAYLOAD_SIZE = (
    REMAKE_CAMPAIGN_HEADER_SIZE
    + REMAKE_INVENTORY_SIZE
    + REMAKE_CHARACTER_CAPACITY * REMAKE_CHARACTER_SIZE
)


def sha256_file(path: os.PathLike | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: os.PathLike | str, payload) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        )


def write_text(path: os.PathLike | str, text: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def probe_exe() -> pathlib.Path:
    """The private probe first; the shared one is only a fallback.

    The shared ``build/mgba-probe/mgba-probe.exe`` was built from a source
    revision whose ``framedump`` signature differs from the checked-in
    ``tools/mgba_probe/host_main.c`` (its usage line says
    ``framedump <count> <addr> <len> <prefix> [keymask]`` while the source
    parses ``<count> <addr> <len> <keymask> <prefix>``).  Both orders fail
    against the shared binary with "Parse error", so this stream builds its
    own probe into ``build/mgba-probe-w4`` and never touches the shared one.
    """

    if PRIVATE_PROBE.is_file():
        return PRIVATE_PROBE
    if SHARED_PROBE.is_file():
        return SHARED_PROBE
    raise SystemExit(
        "ERR no probe found; run:\n"
        "  $env:KONOHA_PROBE_OUT='%s'; python tools/mgba_probe/build.py"
        % (REPO / "build" / "mgba-probe-w4")
    )


def run_probe(commands: list[str], out_json: pathlib.Path,
              timeout: float = 900.0) -> dict:
    """Run the headless probe with a list of debugger commands."""

    command = [
        sys.executable,
        str(PROBE_CLIENT),
        "--exe",
        str(probe_exe()),
        "--timeout",
        str(timeout),
    ]
    for item in commands:
        command += ["--cmd", item]
    command += ["--out", str(out_json)]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "probe failed with exit %d: %s"
            % (completed.returncode, completed.stderr.strip()[:800])
        )
    return json.loads(out_json.read_text(encoding="utf-8"))


def dump_region(commands: list[str], out_json: pathlib.Path,
                timeout: float = 900.0) -> bytes:
    """Run the probe and return the bytes of the last ``dump`` region."""

    document = run_probe(commands, out_json, timeout)
    for step in document["steps"]:
        if step.get("dump"):
            payload = step["dump"]["bytes"]
            return bytes.fromhex(payload)
    raise RuntimeError("the probe produced no dump payload")


def check_descriptor_bank() -> dict:
    """Cross-check the embedded descriptor table against the reverse line."""

    bank_path = (
        REVERSE_ROOT / "sequel" / "content" / "save-state" / "bank.json"
    )
    if not bank_path.is_file():
        return {"available": False, "matches": None}
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    entries = bank.get("entries", [])
    mismatches = []
    if len(entries) != len(ORIGINAL_DESCRIPTORS):
        mismatches.append("entry count")
    for embedded, actual in zip(ORIGINAL_DESCRIPTORS, entries):
        if embedded["payload_length"] != actual["payload_length"]:
            mismatches.append("descriptor %d payload_length" % embedded["index"])
        if embedded["ewram_buffer"] != actual["ewram_buffer"]:
            mismatches.append("descriptor %d ewram_buffer" % embedded["index"])
    return {
        "available": True,
        "bank_sha256": sha256_file(bank_path),
        "matches": not mismatches,
        "mismatches": mismatches,
    }


def original_record_offsets() -> list[int]:
    offsets = []
    current = 0
    for entry in ORIGINAL_DESCRIPTORS:
        offsets.append(current)
        current += entry["payload_length"] + ORIGINAL_SRAM_ADVANCE_OVERHEAD
    return offsets
