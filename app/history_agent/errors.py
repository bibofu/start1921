import httpx


def llm_http_error_code(exc: httpx.HTTPError) -> str:
    """Use the same provider error labels for every LLM execution path."""
    if isinstance(exc, httpx.HTTPStatusError):
        return {
            401: "authentication_failed",
            402: "insufficient_balance",
            429: "rate_limited",
        }.get(exc.response.status_code, f"http_{exc.response.status_code}")
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    return "network_error"


class HistoryAgentError(Exception):
    """Base class for expected project errors."""


class ConfigurationError(HistoryAgentError):
    """Raised when required configuration is missing or invalid."""


class CatalogError(HistoryAgentError):
    """Raised when the corpus catalog is invalid."""


class CorpusScanError(HistoryAgentError):
    """Raised when a corpus scan cannot be completed safely."""


class ExtractionError(HistoryAgentError):
    """Raised when a PDF page cannot be processed."""


class IndexBuildError(HistoryAgentError):
    """Raised when a retrieval index cannot be built safely."""


class RetrievalError(HistoryAgentError):
    """Raised when a retrieval request is invalid or cannot be executed."""


class ResearchDataError(HistoryAgentError):
    """Raised when structured research data violates an auditable constraint."""
