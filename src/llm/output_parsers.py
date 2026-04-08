"""Pydantic models for structured LLM output."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ResearchSource(BaseModel):
    """A citation source used in the research."""
    title: str = Field(description="The title of the website or article")
    url: str = Field(description="The source URL")
    summary: str = Field(description="A brief summary of what this source contributed")


class ResearchReport(BaseModel):
    """Structured research report with key sections."""
    title: str = Field(description="A descriptive title for the research")
    executive_summary: str = Field(description="A high-level summary of the findings")
    key_findings: List[str] = Field(description="List of core insights discovered")
    conclusion: str = Field(description="Closing summary and final thoughts")
    sources: List[ResearchSource] = Field(default_factory=list, description="List of sources cited")

    def to_markdown(self) -> str:
        """Convert the structured report to a polished markdown string."""
        md = f"# {self.title}\n\n"
        md += "## Executive Summary\n\n"
        md += f"{self.executive_summary}\n\n"
        md += "## Key Findings\n\n"
        for finding in self.key_findings:
            md += f"- {finding}\n"
        md += "\n## Conclusion\n\n"
        md += f"{self.conclusion}\n\n"

        if self.sources:
            md += "## References\n\n"
            for src in self.sources:
                md += f"- [{src.title}]({src.url})\n"

        return md


# ---------------------------------------------------------------------------
# V2: Claim-centric structured output
# ---------------------------------------------------------------------------

class Claim(BaseModel):
    """A discrete, verifiable finding extracted from research sources."""
    id: str = Field(description="Unique short identifier, e.g. 'claim-1'")
    text: str = Field(description="The claim statement in one or two sentences")
    confidence: float = Field(
        description="Confidence score between 0.0 (very uncertain) and 1.0 (highly certain)",
        ge=0.0,
        le=1.0,
    )
    evidence_source_urls: List[str] = Field(
        default_factory=list,
        description="URLs of sources that support this claim",
    )
    evidence_quote: str = Field(
        default="",
        description="A short verbatim or paraphrased excerpt from the source that supports this claim",
    )

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class SourceAssessment(BaseModel):
    """Quality assessment of a single research source."""
    url: str = Field(description="The source URL")
    reliability_score: float = Field(
        description="Reliability score between 0.0 (unreliable) and 1.0 (highly reliable)",
        ge=0.0,
        le=1.0,
    )
    bias_flags: List[str] = Field(
        default_factory=list,
        description="List of detected bias or quality concerns, e.g. ['promotional', 'outdated']",
    )
    freshness_days: Optional[int] = Field(
        default=None,
        description="Estimated age of the content in days (null if unknown)",
    )

    @field_validator("reliability_score")
    @classmethod
    def clamp_reliability(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class StructuredReportV2(BaseModel):
    """Claim-centric research report with confidence scores and source assessments."""
    title: str = Field(description="A descriptive title for the research")
    executive_summary: str = Field(description="A high-level summary of the findings (2-3 sentences)")
    claims: List[Claim] = Field(
        description="List of discrete, verifiable claims extracted from the research",
    )
    conclusion: str = Field(description="Closing summary and recommended next steps")
    source_assessments: List[SourceAssessment] = Field(
        default_factory=list,
        description="Quality assessments for each source consulted",
    )

    def to_markdown(self) -> str:
        """Render the structured report as a polished markdown string."""
        LOW_CONFIDENCE_THRESHOLD = 0.5

        md = f"# {self.title}\n\n"
        md += "## Executive Summary\n\n"
        md += f"{self.executive_summary}\n\n"

        md += "## Key Claims\n\n"
        for claim in self.claims:
            confidence_pct = int(claim.confidence * 100)
            warning = " ⚠️ Low confidence" if claim.confidence < LOW_CONFIDENCE_THRESHOLD else ""
            md += f"### {claim.id}{warning}\n\n"
            md += f"{claim.text}\n\n"
            md += f"**Confidence:** {confidence_pct}%\n\n"
            if claim.evidence_quote:
                md += f"> {claim.evidence_quote}\n\n"
            if claim.evidence_source_urls:
                links = ", ".join(f"[source]({u})" for u in claim.evidence_source_urls)
                md += f"**Sources:** {links}\n\n"

        md += "## Conclusion\n\n"
        md += f"{self.conclusion}\n\n"

        if self.source_assessments:
            md += "## Source Assessments\n\n"
            for sa in self.source_assessments:
                reliability_pct = int(sa.reliability_score * 100)
                flags = ", ".join(sa.bias_flags) if sa.bias_flags else "none"
                age = f"{sa.freshness_days}d" if sa.freshness_days is not None else "unknown"
                md += f"- **{sa.url}** — reliability {reliability_pct}%, flags: {flags}, age: {age}\n"

        return md
