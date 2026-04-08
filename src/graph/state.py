"""LangGraph state definition for the research agent."""

from typing import TypedDict


class ResearchState(TypedDict, total=False):
    """Shared mutable state passed between all graph nodes.

    Fields are optional (total=False) so nodes only need to populate
    the fields they produce.
    """

    # Input
    query: str                      # The original user research query

    # Search node output
    search_results: list[dict]      # Raw Tavily results [{url, title, content}, ...]

    # Retrieve node output
    retrieved_contents: list[dict]  # [{url, title, raw_text}, ...]

    # Summarize node output
    summaries: list[dict]           # [{url, title, summary}, ...]

    # Combine node output
    combined_insights: str          # Single merged synthesis

    # Report node output
    report: str                     # Final markdown report
    report_metadata: dict           # {title, sources, generated_at}

    # Structured report v2 output
    structured_report: dict         # StructuredReportV2 serialized as dict
    claims: list[dict]              # List of Claim dicts
    source_assessments: list[dict]  # List of SourceAssessment dicts

    # Control flow
    error: str | None               # Set on unrecoverable errors
    use_vector_store: bool          # Whether to persist to Chroma

    memory_context: str | None      # Memory context for the LLM
