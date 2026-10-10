"""Speaker protocol, pyttsx3 adapter, and loop controller."""

from __future__ import annotations

import importlib
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol


class Speaker(Protocol):
    """Protocol implemented by speech engines and test doubles."""

    def speak(self, text: str) -> None: ...

    def stop(self) -> None: ...


@dataclass
class FakeSpeaker:
    """Record spoken text and stop timestamps without using audio devices."""

    spoken: list[str] = field(default_factory=list)
    stopped: list[float] = field(default_factory=list)

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        self.stopped.append(time.time())


class LoopSpeaker:
    """Repeat one text through a speaker on a daemon thread."""

    def __init__(self, speaker: Speaker, interval_s: float = 3.0) -> None:
        self.speaker = speaker
        self.interval_s = interval_s
        self._event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self, text: str, max_repeats: int | None = None) -> None:
        with self._lock:
            self._stop_locked()
            self._event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                args=(text, self._event, max_repeats),
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _stop_locked(self) -> None:
        self._event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run(self, text: str, event: threading.Event, max_repeats: int | None) -> None:
        if max_repeats is not None and max_repeats <= 0:
            return
        repeats = 0
        while not event.is_set():
            self.speaker.speak(text)
            repeats += 1
            if max_repeats is not None and repeats >= max_repeats:
                return
            event.wait(self.interval_s)


class Pyttsx3Speaker:
    """Lazy pyttsx3 adapter that disables itself after any failure."""

    def __init__(self, rate: int = 180) -> None:
        self.rate = rate
        self._disabled = False
        self._engine: Any = None
        self._engine_lock = threading.Lock()
        try:
            self._pyttsx3: Any = importlib.import_module("pyttsx3")
        except Exception:
            self._disabled = True
            self._pyttsx3 = None

    def speak(self, text: str) -> None:
        if self._disabled:
            return
        threading.Thread(target=self._speak_in_thread, args=(text,), daemon=True).start()

    def stop(self) -> None:
        with self._engine_lock:
            engine = self._engine
        if engine is None:
            return
        with suppress(Exception):
            engine.stop()

    def _speak_in_thread(self, text: str) -> None:
        if self._disabled:
            return
        engine: Any = None
        try:
            engine = self._pyttsx3.init()
            with self._engine_lock:
                self._engine = engine
            engine.setProperty("rate", self.rate)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            self._disabled = True
        finally:
            with self._engine_lock:
                if self._engine is engine:
                    self._engine = None
