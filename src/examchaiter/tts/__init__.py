"""Text-to-speech package."""

from examchaiter.tts.speaker import FakeSpeaker, LoopSpeaker, Pyttsx3Speaker, Speaker

__all__ = ["FakeSpeaker", "LoopSpeaker", "Pyttsx3Speaker", "Speaker"]
