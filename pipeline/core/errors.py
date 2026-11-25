"""Exceptions the pipeline treats differently."""

from __future__ import annotations


class PipelineError(RuntimeError):
    """Anything the CLI reports without a traceback."""


class PermanentError(PipelineError):
    """Retrying cannot help: bad request, bad key, blocked content."""


class MissingCredentialError(PermanentError):
    """A provider is not configured."""


class TransientError(PipelineError):
    """Retrying may help: rate limit, server error, timeout."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class StoryboardError(PipelineError):
    """The storyboard breaks its contract."""


class TimingError(PipelineError):
    """The film would fall outside the allowed duration."""
