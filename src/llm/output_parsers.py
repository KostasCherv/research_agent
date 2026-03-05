"""Pydantic models for structured LLM output."""

from typing import List
from pydantic import BaseModel, Field


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
