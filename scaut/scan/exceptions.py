class ScanBaseError(Exception):
    """Base class for all Scan-related errors."""


class ScanValueError(ScanBaseError, ValueError):
    """Error raised when a device value outside the allowed range."""

