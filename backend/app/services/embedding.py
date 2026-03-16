"""
KGKB Embedding Service - Vector embedding with multiple providers

Supports:
- OpenAI API (text-embedding-3-small, text-embedding-ada-002)
- Ollama API (nomic-embed-text, mxbai-embed-large, etc.)
- Local transformers (optional)
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import httpx
from pydantic import BaseModel

from ..models.knowledge import EmbeddingConfig


class EmbeddingResult(BaseModel):
    """Result from embedding operation."""
    embedding: List[float]
    tokens_used: int = 0
    model: str
    provider: str


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        pass


class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model or "text-embedding-3-small"
        self.base_url = config.endpoint or "https://api.openai.com/v1"

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding using OpenAI API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text,
                    "model": self.model,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return EmbeddingResult(
                embedding=data["data"][0]["embedding"],
                tokens_used=data["usage"]["total_tokens"],
                model=self.model,
                provider="openai",
            )

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        # OpenAI supports batch in single request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": self.model,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for i, item in enumerate(data["data"]):
                results.append(EmbeddingResult(
                    embedding=item["embedding"],
                    tokens_used=data["usage"]["total_tokens"] // len(texts),
                    model=self.model,
                    provider="openai",
                ))
            return results


class OllamaProvider(EmbeddingProvider):
    """Ollama embedding provider."""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.model = config.model or "nomic-embed-text"
        self.base_url = config.endpoint or "http://localhost:11434"

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding using Ollama API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            return EmbeddingResult(
                embedding=data["embedding"],
                tokens_used=0,  # Ollama doesn't report tokens
                model=self.model,
                provider="ollama",
            )

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts (sequential for Ollama)."""
        # Ollama doesn't have native batch API, so we do sequential
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
            # Small delay to avoid overwhelming Ollama
            await asyncio.sleep(0.01)
        return results


class EmbeddingService:
    """
    Main embedding service that routes to appropriate provider.
    """

    PROVIDERS = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._provider = self._create_provider()

    def _create_provider(self) -> EmbeddingProvider:
        """Create the appropriate provider based on config."""
        provider_name = self.config.provider.lower()
        if provider_name not in self.PROVIDERS:
            raise ValueError(f"Unknown embedding provider: {provider_name}")

        provider_class = self.PROVIDERS[provider_name]
        return provider_class(self.config)

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        return await self._provider.embed(text)

    async def embed_batch(self, texts: List[str], batch_size: int = 10) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts with batching."""
        all_results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results = await self._provider.embed_batch(batch)
            all_results.extend(results)

        return all_results

    async def embed_knowledge(self, content: str, metadata: Dict[str, Any] = None) -> List[float]:
        """
        Embed knowledge content with optional metadata.
        Returns just the embedding vector.
        """
        # Optionally enrich content with metadata for better embeddings
        text_to_embed = content
        if metadata and metadata.get("tags"):
            tags_str = " ".join(metadata["tags"])
            text_to_embed = f"{content}\nTags: {tags_str}"

        result = await self.embed(text_to_embed)
        return result.embedding


# Factory function for easy instantiation
def create_embedding_service(
    provider: str = "ollama",
    model: str = None,
    endpoint: str = None,
    api_key: str = None,
    dimension: int = 768,
) -> EmbeddingService:
    """Create an embedding service with specified configuration."""
    config = EmbeddingConfig(
        provider=provider,
        model=model,
        endpoint=endpoint,
        api_key=api_key,
        dimension=dimension,
    )
    return EmbeddingService(config)
