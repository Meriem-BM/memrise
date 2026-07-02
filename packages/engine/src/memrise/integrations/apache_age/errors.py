class AgeError(RuntimeError):
    """Base error for Apache AGE integration."""


class AgeUnavailableError(AgeError):
    """Raised when the AGE extension is not installed or cannot be loaded."""


class AgeQueryError(AgeError):
    """Raised when a controlled Cypher statement fails."""
