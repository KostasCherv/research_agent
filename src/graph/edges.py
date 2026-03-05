"""Edge (routing) logic for the research graph."""

import logging

from src.graph.state import ResearchState

logger = logging.getLogger(__name__)


def should_abort(state: ResearchState) -> str:
    """Route to 'abort' if the search node surfaced an error, else continue.

    Returns:
        ``"abort"`` if ``state["error"]`` is set, otherwise ``"continue"``.
    """
    if state.get("error"):
        logger.warning("Pipeline aborting due to error: %s", state["error"])
        return "abort"
    return "continue"


def has_results(state: ResearchState) -> str:
    """Check whether there are search results to process.

    Returns:
        ``"ok"`` if results exist, ``"empty"`` otherwise.
    """
    return "ok" if state.get("search_results") else "empty"
