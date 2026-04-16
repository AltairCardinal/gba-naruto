import os
from pathlib import Path

LOG_PATH = Path(os.environ.get("LLDB_LOG_PATH", "notes/lldb-dialogue-callers.log"))
HIT_COUNT = 0


def reset(path=None):
    global LOG_PATH, HIT_COUNT
    if path:
        LOG_PATH = Path(path)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    HIT_COUNT = 0


def _reg(frame, name):
    value = frame.FindRegister(name)
    if value.IsValid():
        text = value.GetValue()
        if text:
            return text
    return "?"


def log_and_continue(frame, bp_loc, _internal_dict):
    global HIT_COUNT
    HIT_COUNT += 1
    addr = bp_loc.GetAddress().GetLoadAddress(
        frame.GetThread().GetProcess().GetTarget()
    )
    line = (
        f"hit={HIT_COUNT} "
        f"addr=0x{addr:08X} "
        f"pc={_reg(frame, 'pc')} "
        f"lr={_reg(frame, 'lr')} "
        f"r0={_reg(frame, 'r0')} "
        f"r1={_reg(frame, 'r1')} "
        f"r2={_reg(frame, 'r2')} "
        f"r3={_reg(frame, 'r3')}\n"
    )
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return False


def finish_marker(status):
    done_path = LOG_PATH.with_suffix(LOG_PATH.suffix + ".done")
    done_path.write_text(status + "\n", encoding="utf-8")


def configure_from_env() -> None:
    path = os.getenv("NARUTO_LLDB_TRACE_LOG")
    if path:
        reset(path)
