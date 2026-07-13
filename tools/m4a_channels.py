#!/usr/bin/env python3
"""ROM-exact MP2K DirectSound/CGB channel allocation and track chains."""

from __future__ import annotations

from dataclasses import dataclass

DIRECT_CHANNEL_COUNT = 10
CGB_CHANNEL_COUNT = 4
ACTIVE_MASK = 0xC7
RELEASE_BIT = 0x40


@dataclass
class Channel:
    status: int = 0
    priority: int = 0
    track_ptr: int = 0
    midi_key: int = 0
    prev: int | None = None
    next: int | None = None


@dataclass
class TrackChannels:
    track_ptr: int
    head: int | None = None


def effective_priority(player_priority: int, track_priority: int) -> int:
    if not 0 <= player_priority <= 0xFF or not 0 <= track_priority <= 0xFF:
        raise ValueError("player and track priorities must fit u8")
    return min(0xFF, player_priority + track_priority)


def _free(channel: Channel) -> bool:
    return (channel.status & ACTIVE_MASK) == 0


def _released(channel: Channel) -> bool:
    return bool(channel.status & RELEASE_BIT)


def cgb_can_allocate(
    channel: Channel, new_priority: int, new_track_ptr: int
) -> bool:
    """Apply the fixed CGB-channel replacement test at 0x0809A7B6."""
    if _free(channel) or _released(channel):
        return True
    if channel.priority != new_priority:
        return channel.priority < new_priority
    return channel.track_ptr >= new_track_ptr


def direct_channel_index(
    channels: list[Channel], new_priority: int, new_track_ptr: int
) -> int | None:
    """Select the pool slot exactly as 0x0809A7F4..0x0809A846."""
    best: int | None = None
    threshold_priority = new_priority
    threshold_track = new_track_ptr
    have_release = False
    for index, channel in enumerate(channels):
        if _free(channel):
            return index
        released = _released(channel)
        if released and not have_release:
            have_release = True
            best = index
            threshold_priority = channel.priority
            threshold_track = channel.track_ptr
            continue
        if not released and have_release:
            continue
        if channel.priority < threshold_priority:
            best = index
            threshold_priority = channel.priority
            threshold_track = channel.track_ptr
        elif (
            channel.priority == threshold_priority
            and channel.track_ptr > threshold_track
        ):
            best = index
            threshold_track = channel.track_ptr
    return best


def clear_chain(
    channels: list[Channel], track: TrackChannels, channel_index: int
) -> None:
    channel = channels[channel_index]
    if channel.prev is None:
        if track.head == channel_index:
            track.head = channel.next
    else:
        channels[channel.prev].next = channel.next
    if channel.next is not None:
        channels[channel.next].prev = channel.prev
    channel.prev = None
    channel.next = None
    channel.track_ptr = 0


def link_head(
    channels: list[Channel], track: TrackChannels, channel_index: int
) -> None:
    channel = channels[channel_index]
    channel.prev = None
    channel.next = track.head
    if track.head is not None:
        channels[track.head].prev = channel_index
    track.head = channel_index
    channel.track_ptr = track.track_ptr


def release_first_key(
    channels: list[Channel], track: TrackChannels, midi_key: int
) -> int | None:
    """Release only the newest linked active matching key, as EOT does."""
    index = track.head
    while index is not None:
        channel = channels[index]
        if (
            not _free(channel)
            and not _released(channel)
            and channel.midi_key == midi_key
        ):
            channel.status |= RELEASE_BIT
            return index
        index = channel.next
    return None
