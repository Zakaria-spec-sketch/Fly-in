class MapParseError(Exception):
    """Raised when the input map file is syntactically or semantically invalid.

    Attributes:
        line_number: The 1-indexed line number where the error was detected,
            or ``None`` if the error is not tied to a specific line.
        reason: A short human-readable description of the problem.
    """

    def __init__(self, reason: str, line_number: int | None = None) -> None:
        """Initialize the error with a reason and an optional line number.

        Args:
            reason: Human readable explanation of the parsing failure.
            line_number: The 1-indexed source line related to the failure.
        """
        self.line_number = line_number
        self.reason = reason
        if line_number is not None:
            message = f"line {line_number}: {reason}"
        else:
            message = reason
        super().__init__(message)


class SimulationError(Exception):
    """Raised when the simulation reaches an unrecoverable/invalid state."""
