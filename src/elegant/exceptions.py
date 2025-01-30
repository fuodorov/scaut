class ElegantBaseError(Exception):
    """Base class for all Elegant-related errors."""


class ElegantFileNotFoundError(ElegantBaseError, FileNotFoundError, ValueError):
    """Error raised when a required Elegant file is missing or not found."""


class ElegantFieldNotFoundError(ElegantBaseError, ValueError):
    """Error raised when a Elegant field not found."""


class ElegantElementNotFoundError(ElegantBaseError, ValueError):
    """Error raised when a Elegant field not found."""


class ElegantParseError(ElegantBaseError, ValueError):
    """Error raised when a parse name."""


class ElegantProcessError(ElegantBaseError):
    """Error raised when an Elegant process did not finish successfully."""


class ElegantRemoveFileError(ElegantBaseError):
    """Error raised when an Elegant remove file process did not finish successfully."""
