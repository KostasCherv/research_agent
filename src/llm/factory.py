"""LLM factory — returns the configured chat model (Ollama or OpenAI)."""

from langchain_core.language_models import BaseChatModel

from src.config import settings
from src.errors import ConfigurationError


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """Return a chat model based on the configured LLM_PROVIDER.

    Args:
        temperature: Sampling temperature (0 = deterministic, 1 = creative).

    Returns:
        A LangChain BaseChatModel instance.

    Raises:
        ConfigurationError: If the provider is unknown or required keys are missing.
    """
    provider = settings.llm_provider.lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is not set.")
        from langchain_openai import ChatOpenAI
        from typing import Any
        return ChatOpenAI(
            model=settings.openai_model,
            temperature=temperature,
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            temperature=temperature,
            base_url=settings.ollama_base_url,
        )

    raise ConfigurationError(
        f"Unknown LLM_PROVIDER '{provider}'. Choose 'openai' or 'ollama'."
    )
