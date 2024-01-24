"""Tests for wyoming-snowboy"""
import asyncio
import sys
import wave
from asyncio.subprocess import PIPE
from pathlib import Path

import pytest
from wyoming.audio import AudioStart, AudioStop, wav_to_chunks
from wyoming.event import async_read_event, async_write_event
from wyoming.info import Describe, Info
from wyoming.wake import Detect, Detection, NotDetected

_DIR = Path(__file__).parent
_SAMPLES_PER_CHUNK = 1024


@pytest.mark.asyncio
async def test_snowboy() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "wyoming_snowboy",
        "--uri",
        "stdio://",
        stdin=PIPE,
        stdout=PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    # Check info
    await async_write_event(Describe().event(), proc.stdin)
    while True:
        event = await asyncio.wait_for(async_read_event(proc.stdout), timeout=1)
        assert event is not None

        if not Info.is_type(event.type):
            continue

        info = Info.from_event(event)
        assert len(info.wake) == 1, "Expected one wake service"
        wake = info.wake[0]
        assert len(wake.models) > 0, "Expected at least one model"
        assert any(m.name == "snowboy" for m in wake.models), "Expected snowboy model"
        break

    # We want to use the snowboy model
    await async_write_event(Detect(names=["snowboy"]).event(), proc.stdin)

    # Test positive WAV
    with wave.open(str(_DIR / "snowboy.wav"), "rb") as snowboy_wav:
        await async_write_event(
            AudioStart(
                rate=snowboy_wav.getframerate(),
                width=snowboy_wav.getsampwidth(),
                channels=snowboy_wav.getnchannels(),
            ).event(),
            proc.stdin,
        )
        for chunk in wav_to_chunks(snowboy_wav, _SAMPLES_PER_CHUNK):
            await async_write_event(chunk.event(), proc.stdin)

        await async_write_event(AudioStop().event(), proc.stdin)

    while True:
        event = await asyncio.wait_for(async_read_event(proc.stdout), timeout=1)
        assert event is not None

        if not Detection.is_type(event.type):
            continue

        detection = Detection.from_event(event)
        assert detection.name == "snowboy"  # success
        break

    # Test negative WAV
    with wave.open(str(_DIR / "okay_rhasspy.wav"), "rb") as rhasspy_wav:
        await async_write_event(
            AudioStart(
                rate=rhasspy_wav.getframerate(),
                width=rhasspy_wav.getsampwidth(),
                channels=rhasspy_wav.getnchannels(),
            ).event(),
            proc.stdin,
        )
        for chunk in wav_to_chunks(rhasspy_wav, _SAMPLES_PER_CHUNK):
            await async_write_event(chunk.event(), proc.stdin)

        await async_write_event(AudioStop().event(), proc.stdin)

    while True:
        event = await asyncio.wait_for(async_read_event(proc.stdout), timeout=1)
        assert event is not None

        if not NotDetected.is_type(event.type):
            continue

        # Should receive a not-detected message after audio-stop
        break

    # Need to close stdin for graceful termination
    proc.stdin.close()
    await proc.communicate()

    assert proc.returncode == 0
