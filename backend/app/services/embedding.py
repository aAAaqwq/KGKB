"""
KGKB Embedding Service - Vector embedding with multiple providers

Supports:
- Ollama API (default: qwen3-embedding:0.6b at configurable URL)
- OpenAI API (text-embedding-3-small, text-embedding-ada-002)
- Custom OpenAI-compatible endpoints (any endpoint implementing the /v1/embeddings spec)

Configuration:
- Defaults: Ollama at http://localhost:11434 with qwen3-embedding:0.6b
- Config file: ~/.kgkb/config.json (auto-loaded if present)
- Programmatic override via create_embedding_service() / load_config()

Error handling:
- All provider methods are wrapped to handle network/service unavailability gracefully.
- EmbeddingService exposes is_available() for callers to check before embedding.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from pydantic import BaseModel

from ..models.knowledge import EmbeddingConfig, ConfigModel

logger = logging.getLogger("kgkb.embedding")


# ============ Config File Support ============

CONFIG_PATH = Path.home() / ".kgkb" / "config.json"


def load_config(config_path: Path = CONFIG_PATH) -> ConfigModel:
    """Load KGKB configuration from JSON file.

    If the config file doesn't exist, returns defaults.
    If the file is malformed, logs a warning and returns defaults.
    """
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
            return ConfigModel(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Failed to parse config at %s: %s — using defaults", config_path, e)
    return ConfigModel()


def save_config(config: ConfigModel, config_path: Path = CONFIG_PATH) -> None:
    """Save KGKB configuration to JSON file.

    Creates parent directories if needed.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


# ============ Result Model ============

class EmbeddingResult(BaseModel):
    """Result from embedding operation."""
    embedding: List[float]
    tokens_used: int = 0
    model: str
    provider: str


# ============ Provider Base ============

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

    async def check_available(self) -> bool:
        """Check if the embedding provider is reachable.

        Default implementation tries to embed a trivial string.
        Subclasses may override with a lighter health check.
        """
        try:
            await self.embed("test")
            return True
        except Exception:
            return False


# ============ Ollama Provider ============

class OllamaProvider(EmbeddingProvider):
    """Ollama embedding provider.

    Default model: qwen3-embedding:0.6b (1024-dim).
    Default endpoint: http://localhost:11434
    Uses POST /api/embed (Ollama ≥0.4) with /api/embeddings fallback.
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.model = config.model or "qwen3-embedding:0.6b"
        self.base_url = (config.endpoint or "http://localhost:11434").rstrip("/")

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding using Ollama API."""
        async with httpx.AsyncClient() as client:
            # Try the newer /api/embed endpoint first (Ollama ≥0.4)
            try:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text},
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()
                # /api/embed returns {"embeddings": [[...]]}
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return EmbeddingResult(
                        embedding=embeddings[0],
                        tokens_used=0,
                        model=self.model,
                        provider="ollama",
                    )
            except (httpx.HTTPStatusError, KeyError):
                pass  # Fall through to legacy endpoint

            # Legacy /api/embeddings endpoint
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            return EmbeddingResult(
                embedding=data["embedding"],
                tokens_used=0,
                model=self.model,
                provider="ollama",
            )

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts.

        Tries batch via /api/embed first; falls back to sequential if unavailable.
        """
        # Try batch via /api/embed (Ollama ≥0.4 supports list input)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": texts},
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings", [])
                if len(embeddings) == len(texts):
                    return [
                        EmbeddingResult(
                            embedding=emb,
                            tokens_used=0,
                            model=self.model,
                            provider="ollama",
                        )
                        for emb in embeddings
                    ]
        except Exception:
            pass  # Fall back to sequential

        # Sequential fallback
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
            await asyncio.sleep(0.01)
        return results

    async def check_available(self) -> bool:
        """Check if Ollama is reachable via its /api/tags endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False


# ============ OpenAI Provider ============

class OpenAIProvider(EmbeddingProvider):
    """OpenAI embedding provider.

    Supports the official OpenAI API and any compatible endpoint.
    Default model: text-embedding-3-small.
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.api_key = config.api_key or ""
        self.model = config.model or "text-embedding-3-small"
        self.base_url = (config.endpoint or "https://api.openai.com/v1").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding using OpenAI API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"input": text, "model": self.model},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            return EmbeddingResult(
                embedding=data["data"][0]["embedding"],
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
                model=self.model,
                provider="openai",
            )

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings in a single batched request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"input": texts, "model": self.model},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            total_tokens = data.get("usage", {}).get("total_tokens", 0)
            per_item = total_tokens // max(len(texts), 1)

            return [
                EmbeddingResult(
                    embedding=item["embedding"],
                    tokens_used=per_item,
                    model=self.model,
                    provider="openai",
                )
                for item in data["data"]
            ]

    async def check_available(self) -> bool:
        """Check if the OpenAI-compatible endpoint is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                    timeout=5.0,
                )
                return response.status_code in (200, 401)  # 401 means reachable but needs auth
        except Exception:
            return False


# ============ Custom Provider ============

class CustomProvider(EmbeddingProvider):
    """Custom embedding provider for any OpenAI-compatible /v1/embeddings endpoint.

    Use this for self-hosted or third-party embedding APIs that follow the
    OpenAI embedding spec (e.g., vLLM, LocalAI, text-embedding-inference).

    Config:
        endpoint: Full base URL (e.g., "http://myserver:8080/v1")
        model: Model name to send in the request
        api_key: Bearer token (optional)
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.model = config.model or "default"
        self.base_url = (config.endpoint or "http://localhost:8080/v1").rstrip("/")
        self.api_key = config.api_key or ""

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding using custom OpenAI-compatible endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"input": text, "model": self.model},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            return EmbeddingResult(
                embedding=data["data"][0]["embedding"],
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
                model=self.model,
                provider="custom",
            )

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings in batch."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"input": texts, "model": self.model},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            total_tokens = data.get("usage", {}).get("total_tokens", 0)
            per_item = total_tokens // max(len(texts), 1)

            return [
                EmbeddingResult(
                    embedding=item["embedding"],
                    tokens_used=per_item,
                    model=self.model,
                    provider="custom",
                )
                for item in data["data"]
            ]

    async def check_available(self) -> bool:
        """Check if the custom endpoint is reachable."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                    timeout=5.0,
                )
                return response.status_code < 500
        except Exception:
            return False


# ============ Main Embedding Service ============

class EmbeddingService:
    """
    Main embedding service that routes to the appropriate provider.

    Wraps all operations with graceful error handling — callers never see
    raw network exceptions. On failure, methods return None / empty list
    and log the error. Use is_available() to check reachability.

    Providers: ollama (default), openai, custom.
    Config: loaded from ~/.kgkb/config.json or passed programmatically.
    """

    PROVIDERS = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "custom": CustomProvider,
    }

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._provider = self._create_provider()
        self._available: Optional[bool] = None  # cached availability

    def _create_provider(self) -> EmbeddingProvider:
        """Create the appropriate provider based on config."""
        provider_name = self.config.provider.lower()
        if provider_name not in self.PROVIDERS:
            logger.error("Unknown embedding provider '%s', falling back to ollama", provider_name)
            provider_name = "ollama"

        provider_class = self.PROVIDERS[provider_name]
        return provider_class(self.config)

    async def is_available(self, force_check: bool = False) -> bool:
        """Check if the embedding provider is reachable.

        Caches the result until force_check=True is passed.
        """
        if self._available is None or force_check:
            self._available = await self._provider.check_available()
        return self._available

    async def embed(self, text: str) -> Optional[EmbeddingResult]:
        """Generate embedding for a single text.

        Returns None if the embedding service is unavailable or errors out.
        """
        try:
            result = await self._provider.embed(text)
            self._available = True
            return result
        except httpx.ConnectError:
            logger.warning(
                "Embedding service unavailable (%s at %s) — connection refused",
                self.config.provider,
                self.config.endpoint,
            )
            self._available = False
            return None
        except httpx.TimeoutException:
            logger.warning("Embedding request timed out for provider %s", self.config.provider)
            return None
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return None

    async def embed_batch(
        self, texts: List[str], batch_size: int = 10
    ) -> List[Optional[EmbeddingResult]]:
        """Generate embeddings for multiple texts with batching.

        Returns a list of results; failed items are None.
        """
        all_results: List[Optional[EmbeddingResult]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                results = await self._provider.embed_batch(batch)
                all_results.extend(results)
                self._available = True
            except httpx.ConnectError:
                logger.warning(
                    "Embedding service unavailable during batch (%s at %s)",
                    self.config.provider,
                    self.config.endpoint,
                )
                self._available = False
                all_results.extend([None] * len(batch))
            except Exception as e:
                logger.error("Batch embedding failed: %s", e)
                all_results.extend([None] * len(batch))

        return all_results

    async def embed_knowledge(
        self, content: str, metadata: Dict[str, Any] = None
    ) -> Optional[List[float]]:
        """Embed knowledge content with optional metadata enrichment.

        Returns the embedding vector, or None if embedding fails/unavailable.
        Enriches content with tags for better semantic representation.
        """
        text_to_embed = content
        if metadata:
            # Prepend title if available for richer embeddings
            title = metadata.get("title", "")
            if title:
                text_to_embed = f"{title}\n{content}"
            # Append tags
            tags = metadata.get("tags")
            if tags:
                tags_str = " ".join(tags)
                text_to_embed = f"{text_to_embed}\nTags: {tags_str}"

        result = await self.embed(text_to_embed)
        if result is None:
            return None
        return result.embedding

    def get_provider_info(self) -> Dict[str, Any]:
        """Return information about the active provider (for diagnostics)."""
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "endpoint": self.config.endpoint,
            "dimension": self.config.dimension,
            "available": self._available,
        }


# ============ Factory Functions ============

def create_embedding_service(
    provider: str = "ollama",
    model: str = None,
    endpoint: str = None,
    api_key: str = None,
    dimension: int = 1024,
) -> EmbeddingService:
    """Create an embedding service with specified configuration.

    If no arguments override, loads defaults from ~/.kgkb/config.json.
    Falls back to Ollama qwen3-embedding:0.6b at localhost:11434.
    """
    config = EmbeddingConfig(
        provider=provider,
        model=model or ("qwen3-embedding:0.6b" if provider == "ollama" else None),
        endpoint=endpoint,
        api_key=api_key,
        dimension=dimension,
    )
    return EmbeddingService(config)


def create_embedding_service_from_config(
    config_path: Path = CONFIG_PATH,
) -> EmbeddingService:
    """Create an embedding service from the config file.

    Reads ~/.kgkb/config.json and initializes the appropriate provider.
    If no config file exists, returns default Ollama service.
    """
    app_config = load_config(config_path)
    return EmbeddingService(app_config.embedding)
