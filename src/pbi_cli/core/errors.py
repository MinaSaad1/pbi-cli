"""User-facing error types for pbi-cli.

These exceptions integrate with Click's error formatting so that
errors display cleanly in both normal and REPL modes.
"""

from __future__ import annotations

import click


class PbiCliError(click.ClickException):
    """Base error for all pbi-cli user-facing failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DotNetNotFoundError(PbiCliError):
    """Raised when pythonnet or the bundled .NET DLLs are missing."""

    def __init__(
        self,
        message: str = ("pythonnet is required. Install it with: pip install pythonnet"),
    ) -> None:
        super().__init__(message)


class ConnectionRequiredError(PbiCliError):
    """Raised when a command requires an active connection but none exists."""

    def __init__(self, message: str = "No active connection. Run 'pbi connect' first.") -> None:
        super().__init__(message)


class TomError(PbiCliError):
    """Raised when a TOM operation fails."""

    def __init__(self, operation: str, detail: str) -> None:
        self.operation = operation
        self.detail = detail
        super().__init__(f"{operation}: {detail}")


class VisualTypeError(PbiCliError):
    """Raised when a visual type is not recognised."""

    def __init__(self, visual_type: str) -> None:
        self.visual_type = visual_type
        super().__init__(
            f"Unknown visual type '{visual_type}'. Run 'pbi visual types' to see supported types."
        )


class ReportNotFoundError(PbiCliError):
    """Raised when no PBIR report definition folder can be found."""

    def __init__(
        self,
        message: str = (
            "No PBIR report found. Run this command inside a .pbip project "
            "or pass --path to the .Report folder."
        ),
    ) -> None:
        super().__init__(message)


class AmbiguousReportError(PbiCliError):
    """Raised when auto-detection finds more than one candidate .Report folder."""

    def __init__(self, candidates: list[str]) -> None:
        self.candidates = candidates
        listed = "\n".join(f"  - {c}" for c in candidates)
        super().__init__(
            "Multiple .Report folders found and no --path was given:\n"
            f"{listed}\n"
            "Pass --path to pick one."
        )
