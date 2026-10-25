"""The semantic walk -- one script, two translations.

A **beat** is the semantic unit both sides execute:

    "press the confirm key, hold it for HOLD frames, release it, wait SETTLE
     frames, and look at the picture"

The two sides translate the beat into their own keys and their own starting
point, but the *beat* is the same, so beat ``k`` is the same game moment on
both sides -- provided the two games reach the end of a beat at the same
frame.  They do not: the original reaches the end of its beat about one
sub-beat later than the remake does (measured: the acting unit pointer and
the camera's vertical scroll).  That is why the walk is recorded with an
**inner stride**: the frames inside a beat are recorded too, so the same game
moment can be found on both sides.

The original side starts from the pinned savestate ``scenario-49-battle-14-entry``
and needs no navigation.  The remake side boots from power on and has to walk
into the battle first, so it carries a **prefix** of navigation beats; the
prefix beats are recorded but are not part of the semantic script.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Beat:
    """One semantic step of the walk."""

    key: str
    label: str


@dataclass(frozen=True)
class WalkSpec:
    """One side's translation of the shared semantic script."""

    side: str
    prefix: tuple[str, ...]
    beats: int
    hold_frames: int
    settle_frames: int
    zero_input_frames: int
    input_state: str | None
    rom: str
    frames_budget: int
    keys: tuple[str, ...] = field(default=())

    def sequence(self) -> list[str]:
        return list(self.prefix) + ["A"] * self.beats

    def describe(self) -> list[dict]:
        """The script, beat by beat, with the phase each beat belongs to."""
        script = []
        for index, key in enumerate(self.prefix):
            script.append({"index": index, "key": key, "phase": "navigate"})
        for index in range(self.beats):
            script.append({"index": len(self.prefix) + index, "key": "A",
                           "phase": "beat"})
        return script


# The shared semantic script: "advance the battle one beat".
BEATS = 24
# The remake side is recorded over the whole key sequence the pinned baseline
# used (Down, Down, A x 32), so the remake's game-time line is a superset of
# the baseline's and the judgment bench's arg-min always has the whole line
# available.
REMAKE_BEATS = 30
HOLD_FRAMES = 4
SETTLE_FRAMES = 90
# The inner capture stride: how often a frame inside a beat is recorded.
# A beat is 90 settle frames long, so a stride of 4 samples 23 frames inside
# every beat plus the beat end itself.
CAPTURE_STRIDE = 4

# The original's savestate is already at the battle entry.
ORIGINAL_STATE = (r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
                  r"\scenario-49-battle-14-entry.ss9")
ORIGINAL_ROM = r"D:\Shell\Github\gba-naruto-butano\rom\base.gba"
REMAKE_ROM = r"D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba"

# The remake boots from power on: two menu moves and two confirmations walk
# it into the battle.  The last prefix beat ends at the battle entry, which is
# the moment the original's savestate starts from.
REMAKE_PREFIX = ("Down", "Down", "A", "A")


def original_spec(beats: int = BEATS) -> WalkSpec:
    return WalkSpec(
        side="original",
        prefix=(),
        beats=beats,
        hold_frames=HOLD_FRAMES,
        settle_frames=SETTLE_FRAMES,
        zero_input_frames=90,
        input_state=ORIGINAL_STATE,
        rom=ORIGINAL_ROM,
        frames_budget=3000,
    )


def remake_spec(beats: int = REMAKE_BEATS) -> WalkSpec:
    return WalkSpec(
        side="remake",
        prefix=REMAKE_PREFIX,
        beats=beats,
        hold_frames=HOLD_FRAMES,
        settle_frames=SETTLE_FRAMES,
        zero_input_frames=240,
        input_state=None,
        rom=REMAKE_ROM,
        frames_budget=4000,
    )


def specs(beats: int = BEATS) -> dict:
    return {"original": original_spec(beats),
            "remake": remake_spec(REMAKE_BEATS)}
