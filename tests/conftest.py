from pathlib import Path

import numpy as np
import pytest
from qdrant_client import QdrantClient

from owl_rag.ontology import Ontology
from owl_rag.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[1]


class TestEncoder:
    """Deterministic vectors for integration tests, not a real semantic model."""

    __test__ = False
    model_id = "test-encoder-v1"

    def encode(self, texts):
        vectors = []
        for text in texts:
            text = text.casefold()
            vectors.append(
                [
                    0.1,
                    sum(text.count(w) for w in ("graph", "vertices", "edges", "network")),
                    sum(text.count(w) for w in ("vector", "embedding", "semantic", "meaning")),
                    sum(text.count(w) for w in ("hardware", "computer", "оборудование")),
                ]
            )
        return np.asarray(vectors, dtype=float)


@pytest.fixture
def minimal():
    return Ontology.load("demo", ROOT / "examples/ontologies/minimal.owl")


@pytest.fixture
def search_ontology():
    return Ontology.load("search", ROOT / "examples/ontologies/search.owl")


@pytest.fixture
def store():
    client = QdrantClient(":memory:")
    try:
        yield VectorStore(client, TestEncoder(), "test_chunks", payload_indexes=False)
    finally:
        client.close()
