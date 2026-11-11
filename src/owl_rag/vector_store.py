"""Qdrant adapter shared by ontology entities and external document chunks."""

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from owl_rag.embeddings import Encoder, unit_vectors


@dataclass(frozen=True)
class VectorRecord:
    key: str
    text: str
    metadata: dict[str, Any]


class VectorStore:
    def __init__(
        self,
        client: QdrantClient,
        encoder: Encoder,
        collection: str,
        *,
        payload_indexes: bool = True,
    ):
        self.client = client
        self.encoder = encoder
        self.payload_indexes = payload_indexes
        # Different encoders never share a vector space, even at equal dimensions.
        suffix = hashlib.sha256(encoder.model_id.encode()).hexdigest()[:16]
        self.collection = f"{collection}_{suffix}"

    def _ensure_collection(self, dimensions: int) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(
                    size=dimensions, distance=models.Distance.COSINE
                ),
            )
            # Useful on the server; local mode does not need payload indexes.
            if self.payload_indexes:
                for key in ("workspace", "ontology_id", "version", "source_type", "document_id"):
                    self.client.create_payload_index(
                        self.collection, key, models.PayloadSchemaType.KEYWORD, wait=True
                    )
        params = self.client.get_collection(self.collection).config.params.vectors
        if (
            not isinstance(params, models.VectorParams)
            or params.size != dimensions
            or params.distance != models.Distance.COSINE
        ):
            raise ValueError("Embedding dimensions differ from the existing Qdrant collection")

    def delete_document_tail(self, workspace: str, document_id: str, chunk_count: int) -> None:
        """Remove surplus chunks after a shorter document has been successfully upserted."""
        self.client.delete(
            self.collection,
            models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="workspace", match=models.MatchValue(value=workspace)
                        ),
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        ),
                        models.FieldCondition(
                            key="chunk_index", range=models.Range(gte=chunk_count)
                        ),
                    ]
                )
            ),
            wait=True,
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        for start in range(0, len(records), 64):
            batch = records[start : start + 64]
            vectors = unit_vectors(self.encoder.encode([r.text for r in batch]), len(batch))
            self._ensure_collection(vectors.shape[1])
            points = [
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"{self.collection}:{record.key}")),
                    vector=vector.tolist(),
                    payload={
                        **record.metadata,
                        "text": record.text,
                        "model_id": self.encoder.model_id,
                    },
                )
                for record, vector in zip(batch, vectors, strict=True)
            ]
            self.client.upsert(self.collection, points, wait=True)

    def search(
        self,
        text: str,
        scope: dict[str, str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not text.strip() or len(text) > 16000:
            raise ValueError("Vector query must contain 1..16000 characters")
        if not 1 <= limit <= 100:
            raise ValueError("Vector search limit must be between 1 and 100")
        if not scope:
            raise ValueError("An explicit search scope is required")
        if not self.client.collection_exists(self.collection):
            return []
        vector = unit_vectors(self.encoder.encode([text]), 1)
        self._ensure_collection(vector.shape[1])
        conditions = [
            models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in {**scope, "model_id": self.encoder.model_id}.items()
        ]
        response = self.client.query_points(
            self.collection,
            query=vector[0].tolist(),
            query_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            {**(point.payload or {}), "id": str(point.id), "score": point.score}
            for point in response.points
        ]
