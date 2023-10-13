#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict, Final, Optional

from snowboy import snowboydecoder, snowboydetect
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, WakeModel, WakeProgram
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.wake import Detect, Detection, NotDetected

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent

SAMPLES_PER_CHUNK: Final = 1024
BYTES_PER_CHUNK: Final = SAMPLES_PER_CHUNK * 2  # 16-bit
DEFAULT_KEYWORD: Final = "snowboy"


@dataclass
class KeywordSettings:
    sensitivity: Optional[float] = None
    audio_gain: Optional[float] = None
    apply_frontend: Optional[bool] = None
    num_keywords: int = 1


# https://kalliope-project.github.io/kalliope/settings/triggers/snowboy/
DEFAULT_SETTINGS: Dict[str, KeywordSettings] = {
    "alexa": KeywordSettings(apply_frontend=True),
    "snowboy": KeywordSettings(apply_frontend=False),
    "jarvis": KeywordSettings(num_keywords=2, apply_frontend=True),
    "smart_mirror": KeywordSettings(apply_frontend=False),
    "subex": KeywordSettings(apply_frontend=True),
    "neoya": KeywordSettings(num_keywords=2, apply_frontend=True),
    "computer": KeywordSettings(apply_frontend=True),
    "view_glass": KeywordSettings(apply_frontend=True),
}


@dataclass
class Keyword:
    """Single snowboy keyword"""

    name: str
    model_path: Path
    settings: KeywordSettings


class State:
    """State of system"""

    def __init__(self, args: argparse.Namespace):
        self.args = args

    def get_detector(self, keyword_name: str) -> snowboydetect.SnowboyDetect:
        keyword: Optional[Keyword] = None
        for kw_dir in self.args.custom_model_dir + [self.args.data_dir]:
            if not kw_dir.is_dir():
                continue

            for kw_path in itertools.chain(
                kw_dir.glob("*.umdl"), kw_dir.glob("*.pmdl")
            ):
                kw_name = kw_path.stem
                if kw_name == keyword_name:
                    keyword = Keyword(
                        name=kw_name,
                        model_path=kw_path,
                        settings=DEFAULT_SETTINGS.get(kw_name, KeywordSettings()),
                    )
                    break

        if keyword is None:
            raise ValueError(f"No keyword {keyword_name}")

        sensitivity = self.args.sensitivity
        if keyword.settings.sensitivity is not None:
            sensitivity = keyword.settings.sensitivity

        sensitivity_str = ",".join(
            str(sensitivity) for _ in range(keyword.settings.num_keywords)
        )

        audio_gain = self.args.audio_gain
        if keyword.settings.audio_gain is not None:
            audio_gain = keyword.settings.audio_gain

        apply_frontend = self.args.apply_frontend
        if keyword.settings.apply_frontend is not None:
            apply_frontend = keyword.settings.apply_frontend

        _LOGGER.debug(
            "Loading %s with sensitivity=%s, audio_gain=%s, apply_frontend=%s",
            keyword.name,
            sensitivity_str,
            audio_gain,
            apply_frontend,
        )

        detector = snowboydetect.SnowboyDetect(
            snowboydecoder.RESOURCE_FILE.encode(), str(keyword.model_path).encode()
        )

        detector.SetSensitivity(sensitivity_str.encode())
        detector.SetAudioGain(audio_gain)
        detector.ApplyFrontend(apply_frontend)

        return detector


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--data-dir",
        default=_DIR / "data",
        help="Path to directory with default keywords",
    )
    parser.add_argument(
        "--custom-model-dir",
        action="append",
        default=[],
        help="Path to directory with custom wake word models (*.pmdl, *.umdl)",
    )
    #
    parser.add_argument("--sensitivity", type=float, default=0.5)
    parser.add_argument("--audio-gain", type=float, default=1.0)
    parser.add_argument("--apply-frontend", action="store_true")
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    logging.getLogger().setLevel(logging.DEBUG)
    _LOGGER.debug(args)

    args.data_dir = Path(args.data_dir)
    args.custom_model_dir = [Path(p) for p in args.custom_model_dir]

    state = State(args=args)

    _LOGGER.info("Ready")

    # Start server
    server = AsyncServer.from_uri(args.uri)

    try:
        await server.run(partial(SnowboyEventHandler, args, state))
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


class SnowboyEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        cli_args: argparse.Namespace,
        state: State,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.client_id = str(time.monotonic_ns())
        self.state = state
        self.converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self.detected = False
        self.audio_buffer = bytes()

        self.detector: Optional[snowboydetect.SnowboyDetect] = None
        self.keyword_name: str = ""

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            wyoming_info = self._get_info()
            await self.write_event(wyoming_info.event())
            _LOGGER.debug("Sent info to client: %s", self.client_id)
            return True

        if Detect.is_type(event.type):
            detect = Detect.from_event(event)
            if detect.names:
                # TODO: use all names
                self._load_keyword(detect.names[0])
        elif AudioStart.is_type(event.type):
            self.detected = False
        elif AudioChunk.is_type(event.type):
            if self.detector is None:
                # Default keyword
                self._load_keyword(DEFAULT_KEYWORD)

            assert self.detector is not None

            chunk = AudioChunk.from_event(event)
            chunk = self.converter.convert(chunk)
            self.audio_buffer += chunk.audio

            while len(self.audio_buffer) >= BYTES_PER_CHUNK:
                # Return is:
                # -2 silence
                # -1 error
                #  0 voice
                #  n index n-1
                result_index = self.detector.RunDetection(
                    self.audio_buffer[:BYTES_PER_CHUNK]
                )
                if result_index > 0:
                    _LOGGER.debug(
                        "Detected %s from client %s", self.keyword_name, self.client_id
                    )
                    await self.write_event(
                        Detection(
                            name=self.keyword_name, timestamp=chunk.timestamp
                        ).event()
                    )

                self.audio_buffer = self.audio_buffer[BYTES_PER_CHUNK:]

        elif AudioStop.is_type(event.type):
            # Inform client if not detections occurred
            if not self.detected:
                # No wake word detections
                await self.write_event(NotDetected().event())

                _LOGGER.debug(
                    "Audio stopped without detection from client: %s", self.client_id
                )

            return False
        else:
            _LOGGER.debug("Unexpected event: type=%s, data=%s", event.type, event.data)

        return True

    async def disconnect(self) -> None:
        _LOGGER.debug("Client disconnected: %s", self.client_id)

    def _load_keyword(self, keyword_name: str):
        self.detector = self.state.get_detector(keyword_name)
        self.keyword_name = keyword_name

    def _get_info(self) -> Info:
        # name -> keyword
        keywords: Dict[str, Keyword] = {}
        for kw_dir in [self.cli_args.data_dir] + self.cli_args.custom_model_dir:
            if not kw_dir.is_dir():
                continue

            for kw_path in itertools.chain(
                kw_dir.glob("*.umdl"), kw_dir.glob("*.pmdl")
            ):
                kw_name = kw_path.stem
                keywords[kw_name] = Keyword(
                    name=kw_name,
                    model_path=kw_path,
                    settings=DEFAULT_SETTINGS.get(kw_name, KeywordSettings()),
                )

        return Info(
            wake=[
                WakeProgram(
                    name="snowboy",
                    description="DNN based hotword and wake word detection toolkit",
                    attribution=Attribution(
                        name="Kitt.AI", url="https://github.com/Kitt-AI/snowboy"
                    ),
                    installed=True,
                    models=[
                        WakeModel(
                            name=kw.name,
                            description=kw.name,
                            attribution=Attribution(
                                name="Kitt.AI",
                                url="https://github.com/Kitt-AI/snowboy",
                            ),
                            installed=True,
                            languages=[],
                        )
                        for kw in keywords.values()
                    ],
                )
            ],
        )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
