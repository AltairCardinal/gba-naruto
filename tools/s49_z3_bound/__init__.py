"""Wave 14 / stream Z3 -- the residual lower bound for the *current* ROM and the
attribution of the 130 "walk phase" overlay cells.

Three instruments, all built on the read-only reuse of other streams' work:

``z3record``
    The dense semantic walk recorder.  It reuses the pairing stream's walk
    script (``tools/s49_pairing/lua/record_walk.lua``) and its beat script
    (``tools/s49_pairing/walkspec.py``) **read-only**, but it drives the probe
    with the line-safe client of ``tools/s49_battle_balance/w1_probe.py``
    (one background reader thread + a queue) instead of the per-line reader
    threads, and it **pins the ROM** (a byte copy) before recording so that a
    parallel stream rebuilding the ROM cannot change the measurement half way
    through.

``z3bound``
    The provable pixel floor.  It reuses the pairing stream's algorithm
    (``tools/s49_pairing/pair.py::beat_floor``) read-only and adds the ROM
    digests and a byte-stable receipt.

``z3phase``
    The phase attribution of the 130 overlay cells that the Y2/Y4 streams
    classified as "walk phase".  It decides, from the original game's **own**
    six-frame captures of each moment, whether the original's picture is a
    stable state or a single-frame transient -- and then checks whether the
    remake ever reaches that phase.

Nothing in this directory modifies the remake line, the reverse line or any
other stream's instrument.
"""
