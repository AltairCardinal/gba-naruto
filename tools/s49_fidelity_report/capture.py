"""Re-record the two walks and describe what was recorded."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

from .paths import PROBE_CLIENT, REPO

ORIGINAL_KEY_SEQUENCE = ["A"] * 24
REMAKE_KEY_SEQUENCE = ["Down", "Down"] + ["A"] * 32
ORIGINAL_ZERO_INPUT_FRAMES = 90
ORIGINAL_SETTLE_FRAMES = 90
REMAKE_ZERO_INPUT_FRAMES = 240
REMAKE_SETTLE_FRAMES = 90
HOLD_FRAMES = 4
ORIGINAL_FRAMES_BUDGET = 2000
REMAKE_FRAMES_BUDGET = 3000

ORIGINAL_STATE_SHA256 = ("a3628723ac595f41b87d329f49d5422a7b9b397a8491379"
                         "abb8c9620568a0aa1")
ORIGINAL_ROM_SHA256 = ("1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a5"
                       "5d32748c2a459d05b")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: pathlib.Path, text: str) -> None:
    """UTF-8, no BOM, LF only -- the repository's evidence identity needs it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def canonical_json(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def resolve_butano_root(explicit: str | None) -> pathlib.Path:
    candidates = []
    if explicit:
        candidates.append(pathlib.Path(explicit))
    candidates += [
        pathlib.Path(r"D:\Shell\Github\gba-naruto-butano"),
        pathlib.Path(r"D:\Github\gba-naruto-butano"),
    ]
    for candidate in candidates:
        if (candidate / "tools" / "butano").is_dir():
            return candidate
    raise SystemExit(
        "ERR butano root not found; pass --butano-root. Tried: "
        + ", ".join(str(candidate) for candidate in candidates))


def rel_to_repo(path: pathlib.Path) -> str:
    try:
        return pathlib.Path(str(path)).relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------
# The identity of a capture
# --------------------------------------------------------------------------
# A capture may only be reused when the thing it recorded is the thing we
# are about to measure.  wave 15 found the bench reusing a capture whose
# audit attested a *different* ROM and then reporting the reading under the
# requested ROM's digest => the report could describe a ROM it never
# measured, and a "the residual did not grow" conclusion could be an
# artefact of the stale frames.
#
# The capture is its own witness: it leaves an audit behind.
#   * the remake side writes the digest of the ROM it booted (``rom_sha256``);
#   * the original side boots from a savestate and writes the digest of that
#     state (``input_state_sha256``) -- its ROM is a fixed constant.
# Both witnesses are read, and a capture whose two witnesses contradict each
# other is refused: nobody can vouch for it.
AUDIT_ROM_KEY = "rom_sha256"
AUDIT_STATE_KEY = "input_state_sha256"
AUDIT_WITNESSES = ("audit.json", "done.json")


def read_audit(out_dir: pathlib.Path) -> dict:
    """What the capture in ``out_dir`` says it recorded.

    Returns a dict with the keys

      ``audit``          the attested digests, merged from the witnesses;
      ``source``         the file the digests were read from;
      ``witnesses``      the witness files that were read;
      ``contradiction``  True when the witnesses disagree about a digest.
    """
    result = {"audit": {}, "source": None, "witnesses": [],
              "contradiction": False}
    documents: dict = {}
    for name in AUDIT_WITNESSES:
        path = out_dir / name
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        documents[name] = document
        result["witnesses"].append(name)
    for name, document in documents.items():
        if result["source"] is None:
            result["source"] = name
        for key in (AUDIT_ROM_KEY, AUDIT_STATE_KEY):
            value = document.get(key)
            if value is None:
                continue
            known = result["audit"].get(key)
            if known is not None and known != value:
                # The capture's own witnesses contradict each other: refuse it.
                result["contradiction"] = True
                result["audit"][key] = None
                continue
            result["audit"][key] = value
    return result


def expected_identity(rom_sha256: str, env_extra: dict) -> dict:
    """The digests this request names: the ROM, plus the savestate if any."""
    identity = {AUDIT_ROM_KEY: rom_sha256}
    state = env_extra.get("MGBA_ORIGINAL_S49_INPUT_STATE_SHA256")
    if state:
        identity[AUDIT_STATE_KEY] = state
    return identity


def verify_capture_identity(audit: dict, identity: dict,
                            contradiction: bool = False) -> tuple[bool, str]:
    """May this capture be reused for this request?

    The audit must attest **at least one** of the digests the request
    names, and every digest it does attest must match.  An audit that
    attests nothing relevant cannot be verified => the capture is refused
    (fail closed: a capture nobody can vouch for is never reused).
    """
    if contradiction:
        return False, ("the capture's own witnesses (audit.json / done.json) "
                       "disagree about the ROM or the input state")
    if not audit:
        return False, "there is no readable audit to verify the capture against"
    attested = [key for key in (AUDIT_ROM_KEY, AUDIT_STATE_KEY)
                if audit.get(key)]
    if not attested:
        return False, ("the audit attests neither the ROM nor the input "
                       "state => the capture cannot be verified")
    for key in attested:
        expected = identity.get(key)
        if expected is None:
            return False, (f"the audit attests {key} but the request does "
                           "not name it")
        if audit[key] != expected:
            return False, (f"{key} differs: the capture recorded "
                           f"{audit[key]}, the request names {expected}")
    return True, "the capture's audit matches this request"


def run_capture(name: str, rom: pathlib.Path, lua: pathlib.Path,
                env_extra: dict, out_dir: pathlib.Path, frames_budget: int,
                bios: pathlib.Path | None, expected_frames: int,
                reuse: bool = False) -> dict:
    """Record one side with the headless mGBA probe.

    With ``reuse`` an existing, completed capture is kept and only re-read
    -- **but only when its audit says it recorded the same thing this
    request names**.  wave 15 found the bench reusing a capture of a
    different ROM and then reporting the reading under the requested ROM's
    digest, which turned "the residual did not grow" into an artefact of
    the stale frames.  The audit is therefore checked *before* anything is
    reused, and a mismatch re-records instead.
    """
    env = dict(os.environ)
    # The two Lua scripts have separate env namespaces; make sure a variable
    # of the other kind can never leak in.
    for prefix in ("MGBA_ORIGINAL_S49_OUTPUT_DIR", "MGBA_BOOT_SEQUENCE_OUTPUT_DIR"):
        env.pop(prefix, None)
    env.update(env_extra)
    done_marker = out_dir / "done.json"
    requested_rom_sha256 = sha256_file(rom)
    identity = expected_identity(requested_rom_sha256, env_extra)

    attempts = []
    reused = False
    action = "captured"
    reason = "the capture was recorded for this request"
    refused_reason = None
    if reuse and done_marker.exists() and sorted(out_dir.glob("step-*.png")):
        existing = read_audit(out_dir)
        ok, why = verify_capture_identity(existing["audit"], identity,
                                           existing["contradiction"])
        if ok:
            reused = True
            action = "reused"
            reason = ("the existing capture's audit matches this request "
                      "(the same ROM)")
        else:
            action = "recaptured"
            refused_reason = why
            reason = ("the existing capture was refused and recorded again: "
                      + why)
    if not reused:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for attempt, budget in enumerate((frames_budget, frames_budget * 3), start=1):
            if done_marker.exists():
                done_marker.unlink()
            for stale in out_dir.glob("step-*.png"):
                stale.unlink()
            for stale in out_dir.glob("step-*.ss9"):
                stale.unlink()

            command = [sys.executable, str(PROBE_CLIENT), "--rom", str(rom)]
            if bios is not None:
                command += ["--bios", str(bios)]
            command += [
                "--cmd", f"script {lua}",
                "--cmd", f"frames {budget} 0x000",
                "--out", str(out_dir / "result.json"),
            ]
            proc = subprocess.run(command, env=env, cwd=str(REPO),
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            attempts.append({
                "attempt": attempt,
                "frames_budget": budget,
                "exit_code": proc.returncode,
                "stderr_tail": (proc.stderr or "").splitlines()[-5:],
            })
            if proc.returncode == 0 and done_marker.exists():
                break
        else:
            raise SystemExit(
                f"ERR capture '{name}' did not complete; done marker "
                f"{done_marker} missing")

    frames = sorted(out_dir.glob("step-*.png"))
    audit = {}
    audit_path = out_dir / "audit.json"
    if audit_path.is_file():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            audit = {"raw": audit_path.read_text(encoding="utf-8", errors="replace")}

    # --- what was actually measured ----------------------------------------
    # ``rom_sha256`` is the ROM this request names; ``measured_rom_sha256``
    # is the ROM the frames came from.  They are the same whenever the audit
    # vouches for the capture, and the report says so in both cases.
    final = read_audit(out_dir)
    measured_rom_sha256 = final["audit"].get(AUDIT_ROM_KEY)
    measured_rom_source = "audit" if measured_rom_sha256 else "requested"
    if not measured_rom_sha256:
        measured_rom_sha256 = requested_rom_sha256
    verified, verify_reason = verify_capture_identity(
        final["audit"], identity, final["contradiction"])

    # The reuse decision is **run provenance**, not measurement: it says
    # whether the frames were recorded or taken over.  It therefore travels
    # with ``attempts`` (which the caller moves out of the measurement
    # digest), so that a re-run that reuses a capture still produces the
    # same ``content_sha256`` as the run that recorded it.
    attempts.insert(0, {
        "kind": "reuse-decision",
        "requested": bool(reuse),
        "reused": reused,
        "action": action,
        "reason": reason,
        "refused_reason": refused_reason,
        "requested_rom_sha256": requested_rom_sha256,
        "audit_rom_sha256": final["audit"].get(AUDIT_ROM_KEY),
        "audit_input_state_sha256": final["audit"].get(AUDIT_STATE_KEY),
        "audit_source": final["source"],
        "audit_witnesses": final["witnesses"],
        "identity_verified": verified,
        "identity_reason": verify_reason,
    })

    return {
        "name": name,
        "rom": str(rom),
        "rom_sha256": requested_rom_sha256,
        "measured_rom_sha256": measured_rom_sha256,
        "measured_rom_sha256_source": measured_rom_source,
        "reuse_decision": {
            "requested_rom_sha256": requested_rom_sha256,
            "audit_rom_sha256": final["audit"].get(AUDIT_ROM_KEY),
            "audit_input_state_sha256": final["audit"].get(AUDIT_STATE_KEY),
            "audit_source": final["source"],
            "rom_attested_by_audit": bool(final["audit"].get(AUDIT_ROM_KEY)),
            "identity_verified": verified,
        },
        "lua_script": str(lua),
        "lua_sha256": sha256_file(lua),
        "output_dir": str(out_dir),
        "done_marker": str(done_marker),
        "env": {key: value for key, value in sorted(env_extra.items())},
        "frames_budget": frames_budget,
        "expected_frame_count": expected_frames,
        "frame_count": len(frames),
        "capture_ok": len(frames) == expected_frames,
        "reused": reused,
        "audit": audit,
        "attempts": attempts,
        "frames": [{"name": frame.name, "sha256": sha256_file(frame),
                    "bytes": frame.stat().st_size} for frame in frames],
    }
