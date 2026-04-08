"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = Field(default="openai", description="LLM provider: 'ollama' or 'openai'")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama base URL")
    ollama_model: str = Field(default="llama3.2", description="Ollama model name")

    # Search
    tavily_api_key: str = Field(default="", description="Tavily search API key")
    max_search_results: int = Field(default=5, description="Max Tavily search results")

    # Vector store
    chroma_persist_directory: str = Field(default="./chroma_db", description="ChromaDB directory")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Observability (LangSmith)
    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing for workflow and node spans.",
    )
    langsmith_project: str = Field(
        default="research-agent",
        description="LangSmith project name for traced runs.",
    )
    langsmith_api_key: str = Field(default="", description="LangSmith API key")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint.",
    )
    langsmith_redaction_mode: str = Field(
        default="redacted_default",
        description="Trace payload policy: full_payloads|redacted_default|metadata_only",
    )
    langsmith_sampling_rate: float = Field(
        default=1.0,
        description="Fraction of runs to trace (0.0 to 1.0).",
    )


settings = Settings()
