"""
Embedding Generation Module

Supports multiple backends:
- Local: sentence-transformers (offline, privacy-first)
- Cloudflare: Workers AI @cf/baai/bge-base-en-v1.5 (edge deployment)
- OpenAI: text-embedding-3-small (optional cloud fallback)

Usage:
    # Local (default)
    embedder = get_embedder("local")
    vectors = embedder.embed(["Hello world", "How are you?"])
    
    # Cloudflare Workers AI
    embedder = get_embedder("cloudflare", account_id="...", api_token="...")
    vectors = embedder.embed(["Hello world"])
"""

import os
import json
import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path

# Embedding dimensions for different models
EMBEDDING_DIMS = {
    "local": 384,               # all-MiniLM-L6-v2
    "cloudflare": 768,          # @cf/baai/bge-base-en-v1.5
    "openai": 1536,             # text-embedding-3-small
    "openai-large": 3072,       # text-embedding-3-large
}


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector dimensions."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass
    
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        pass
    
    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]


class LocalEmbedder(EmbeddingProvider):
    """Local embedding using sentence-transformers (offline, privacy-first)."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_dir: Optional[Path] = None):
        self._model_name = model_name
        self._model = None
        self._cache_dir = cache_dir or Path.home() / ".cache" / "inchive" / "embeddings"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                )
        return self._model
    
    @property
    def dimensions(self) -> int:
        return EMBEDDING_DIMS.get("local", 384)
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def embed(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """Generate embeddings, optionally using disk cache."""
        results = []
        texts_to_embed = []
        indices_to_embed = []
        
        # Check cache first
        if use_cache:
            for i, text in enumerate(texts):
                cache_file = self._cache_dir / f"{self._cache_key(text)}.json"
                if cache_file.exists():
                    with open(cache_file) as f:
                        results.append(json.load(f))
                else:
                    results.append(None)
                    texts_to_embed.append(text)
                    indices_to_embed.append(i)
        else:
            texts_to_embed = texts
            indices_to_embed = list(range(len(texts)))
            results = [None] * len(texts)
        
        # Embed uncached texts
        if texts_to_embed:
            model = self._load_model()
            embeddings = model.encode(texts_to_embed, convert_to_numpy=True)
            
            for idx, embedding in zip(indices_to_embed, embeddings):
                vec = embedding.tolist()
                results[idx] = vec
                
                # Cache result
                if use_cache:
                    cache_file = self._cache_dir / f"{self._cache_key(texts[idx])}.json"
                    with open(cache_file, "w") as f:
                        json.dump(vec, f)
        
        return results


class CloudflareEmbedder(EmbeddingProvider):
    """Cloudflare Workers AI embedding using @cf/baai/bge-base-en-v1.5."""
    
    MODEL = "@cf/baai/bge-base-en-v1.5"
    API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    
    def __init__(self, account_id: str, api_token: str):
        self.account_id = account_id
        self.api_token = api_token
    
    @property
    def dimensions(self) -> int:
        return EMBEDDING_DIMS["cloudflare"]
    
    @property
    def model_name(self) -> str:
        return self.MODEL
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via Cloudflare Workers AI API."""
        import requests
        
        url = self.API_URL.format(account_id=self.account_id, model=self.MODEL)
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # Cloudflare accepts batch of texts
        payload = {"text": texts}
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"Cloudflare API error: {result.get('errors')}")
        
        # Result format: {"result": {"data": [[...], [...], ...]}}
        return result["result"]["data"]


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI embedding using text-embedding-3-small."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var.")
    
    @property
    def dimensions(self) -> int:
        if "large" in self._model:
            return EMBEDDING_DIMS["openai-large"]
        return EMBEDDING_DIMS["openai"]
    
    @property
    def model_name(self) -> str:
        return self._model
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via OpenAI API."""
        import requests
        
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self._model,
                "input": texts
            }
        )
        response.raise_for_status()
        
        result = response.json()
        return [item["embedding"] for item in result["data"]]


def get_embedder(
    provider: str = "local",
    **kwargs
) -> EmbeddingProvider:
    """
    Factory function to get an embedding provider.
    
    Args:
        provider: "local", "cloudflare", or "openai"
        **kwargs: Provider-specific arguments
            - local: model_name, cache_dir
            - cloudflare: account_id, api_token
            - openai: api_key, model
    
    Returns:
        EmbeddingProvider instance
    """
    if provider == "local":
        return LocalEmbedder(
            model_name=kwargs.get("model_name", "all-MiniLM-L6-v2"),
            cache_dir=kwargs.get("cache_dir")
        )
    elif provider == "cloudflare":
        account_id = kwargs.get("account_id") or os.environ.get("CF_ACCOUNT_ID")
        api_token = kwargs.get("api_token") or os.environ.get("CF_API_TOKEN")
        if not account_id or not api_token:
            raise ValueError(
                "Cloudflare credentials required. Set CF_ACCOUNT_ID and CF_API_TOKEN env vars."
            )
        return CloudflareEmbedder(account_id, api_token)
    elif provider == "openai":
        return OpenAIEmbedder(
            api_key=kwargs.get("api_key"),
            model=kwargs.get("model", "text-embedding-3-small")
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


# Utility functions for chunking long texts

def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks suitable for embedding.
    
    Uses simple word-based splitting. For production, consider
    using tiktoken for accurate token counting.
    """
    words = text.split()
    chunks = []
    
    # Rough estimate: 1 token ~= 0.75 words
    max_words = int(max_tokens * 0.75)
    overlap_words = int(overlap * 0.75)
    
    start = 0
    while start < len(words):
        end = start + max_words
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap_words
        
        if end >= len(words):
            break
    
    return chunks


def embed_with_chunking(
    embedder: EmbeddingProvider,
    text: str,
    max_tokens: int = 512
) -> Dict[str, Any]:
    """
    Embed a long text by chunking and averaging.
    
    Returns:
        {
            "embedding": [...],  # Averaged embedding
            "chunks": [{"text": "...", "embedding": [...]}]
        }
    """
    chunks = chunk_text(text, max_tokens=max_tokens)
    embeddings = embedder.embed(chunks)
    
    # Average the embeddings
    if len(embeddings) == 1:
        avg_embedding = embeddings[0]
    else:
        import numpy as np
        avg_embedding = np.mean(embeddings, axis=0).tolist()
    
    return {
        "embedding": avg_embedding,
        "chunks": [
            {"text": chunk, "embedding": emb}
            for chunk, emb in zip(chunks, embeddings)
        ]
    }

