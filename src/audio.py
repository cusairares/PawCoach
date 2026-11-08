"""Non-blocking audio cues.

Sound keys: ``sit``, ``down``, ``stand`` (cue words) and ``marker`` (the "good!" /
click sound that marks the correct behavior). A custom recording in
``data/audio/custom/<key>.wav`` overrides the default in ``assets/audio/default``.
Customizations are uploaded by the app through ``set_custom_sound``.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Iterable, List, Optional

from .config import ASSETS_DIR, DATA_DIR

log = logging.getLogger(__name__)

SOUND_KEYS = ("sit", "down", "stand", "marker")
DEFAULT_DIR = ASSETS_DIR / "audio" / "default"
CUSTOM_DIR = DATA_DIR / "audio" / "custom"


def resolve_sound(key: str, default_dir: Path = DEFAULT_DIR, custom_dir: Path = CUSTOM_DIR) -> Optional[Path]:
    for path in (Path(custom_dir) / f"{key}.wav", Path(default_dir) / f"{key}.wav"):
        if path.exists():
            return path
    return None


def set_custom_sound(key: str, wav_bytes: bytes, custom_dir: Path = CUSTOM_DIR) -> Path:
    if key not in SOUND_KEYS:
        raise ValueError(f"Unknown sound key '{key}'. Expected one of {SOUND_KEYS}")
    if wav_bytes[:4] != b"RIFF":
        raise ValueError("Expected a WAV (RIFF) file")
    custom_dir = Path(custom_dir)
    custom_dir.mkdir(parents=True, exist_ok=True)
    path = custom_dir / f"{key}.wav"
    path.write_bytes(wav_bytes)
    return path


def reset_custom_sound(key: str, custom_dir: Path = CUSTOM_DIR) -> None:
    (Path(custom_dir) / f"{key}.wav").unlink(missing_ok=True)


class AudioPlayer:
    """Plays sequences of sounds on a background thread (never blocks inference)."""

    def __init__(self, enabled: bool = True, volume: float = 1.0,
                 default_dir: Path = DEFAULT_DIR, custom_dir: Path = CUSTOM_DIR):
        self.default_dir, self.custom_dir = Path(default_dir), Path(custom_dir)
        self.volume = volume
        self.history: List[str] = []           # keys played (useful for tests / overlay)
        self._queue: "queue.Queue[List[str]]" = queue.Queue()
        self._mixer = None
        if enabled:
            try:
                import pygame
                pygame.mixer.init()
                self._mixer = pygame.mixer
            except Exception as exc:  # no audio device etc.
                log.warning("Audio disabled (%s). Cues will only be logged.", exc)
        threading.Thread(target=self._worker, daemon=True, name="audio").start()

    def play(self, keys: Iterable[str]) -> None:
        keys = list(keys)
        self.history.extend(keys)
        self._queue.put(keys)

    def _worker(self) -> None:
        while True:
            for key in self._queue.get():
                path = resolve_sound(key, self.default_dir, self.custom_dir)
                if path is None:
                    log.warning("No sound file for '%s'", key)
                    continue
                log.info("[audio] %s (%s)", key, path.name)
                if self._mixer is None:
                    continue
                try:
                    sound = self._mixer.Sound(str(path))
                    sound.set_volume(self.volume)
                    channel = sound.play()
                    while channel is not None and channel.get_busy():
                        time.sleep(0.02)
                    time.sleep(0.15)               # small gap between cue and marker
                except Exception as exc:
                    log.warning("Failed to play %s: %s", path, exc)
