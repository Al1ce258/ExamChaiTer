"""Project-specific exception hierarchy."""


class ExamChaiTerError(Exception):
    """Base class for every expected ExamChaiTer error."""


class ConfigurationError(ExamChaiTerError):
    """Raised when configuration cannot satisfy the requested operation."""


class WindowError(ExamChaiTerError):
    """Raised when a target window cannot be found or controlled."""


class CaptureError(ExamChaiTerError):
    """Raised when screen capture fails or returns invalid data."""


class OcrError(ExamChaiTerError):
    """Raised when OCR processing fails."""


class LlmError(ExamChaiTerError):
    """Raised when an LLM request or response cannot be handled."""


class OutputError(ExamChaiTerError):
    """Raised when an answer cannot be presented to the user."""


class TtsError(ExamChaiTerError):
    """Raised when text-to-speech fails."""


class HotkeyError(ExamChaiTerError):
    """Raised when the global hotkey listener cannot be initialized."""


class PipelineError(ExamChaiTerError):
    """Raised when the answer pipeline cannot complete."""


class StorageError(ExamChaiTerError):
    """Raised when configuration or history storage cannot be read or written."""
