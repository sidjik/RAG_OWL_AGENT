"""Configuration uses environment variables; secrets stay outside source control."""

import os
from typing import Literal, overload

from qdrant_client import QdrantClient

from owl_rag.embeddings import Encoder, SentenceTransformerEncoder
from owl_rag.providers import LiteLLMEncoder, LiteLLMGenerator
from owl_rag.vector_store import VectorStore


@overload
def configured_store(collection: str, required: Literal[True]) -> VectorStore: ...


@overload
def configured_store(collection: str, required: bool = False) -> VectorStore | None: ...


def configured_store(collection: str, required: bool = False) -> VectorStore | None:
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    if not model:
        if required:
            raise ValueError("Set EMBEDDING_MODEL to enable the knowledge server")
        return None
    backend = os.getenv("EMBEDDING_BACKEND", "litellm")
    encoder: Encoder
    if backend == "sentence-transformers":
        encoder = SentenceTransformerEncoder(model)
    elif backend == "litellm":
        encoder = LiteLLMEncoder(
            os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
            model,
            os.getenv("LITELLM_API_KEY") or os.getenv("LITELLM_MASTER_KEY") or "",
        )
    else:
        raise ValueError("EMBEDDING_BACKEND must be litellm or sentence-transformers")
    client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        timeout=30,
    )
    return VectorStore(client, encoder, collection)


def configured_generator() -> LiteLLMGenerator | None:
    model = os.getenv("HYDE_MODEL", "").strip()
    return (
        LiteLLMGenerator(
            os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1"),
            model,
            os.getenv("LITELLM_API_KEY") or os.getenv("LITELLM_MASTER_KEY") or "",
        )
        if model
        else None
    )
