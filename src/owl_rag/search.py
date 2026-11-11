"""Entity documents, BM25 and optional cosine search combined using RRF."""

import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Plus
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, URIRef

from owl_rag.models import Kind, SearchHit, SearchMode, describe_statement
from owl_rag.ontology import local_name
from owl_rag.vector_store import VectorRecord, VectorStore

LABELS = {RDFS.label, SKOS.prefLabel, SKOS.altLabel}
DESCRIPTIONS = {
    RDFS.comment,
    SKOS.definition,
    URIRef("http://purl.org/dc/terms/description"),
    URIRef("http://purl.org/dc/elements/1.1/description"),
}
PROPERTY_TYPES = {
    RDF.Property,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
    OWL.AsymmetricProperty,
    OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty,
}


def tokens(text: str) -> list[str]:
    """Unicode words plus CamelCase parts, retaining the original identifier."""
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    result = []
    for word in words:
        result.append(word.casefold())
        split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", word)
        split = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", split)
        if split != word:
            result.extend(part.casefold() for part in split.split())
    return result


@dataclass(frozen=True)
class Entity:
    iri: URIRef
    name: str
    types: list[str]
    kinds: list[str]
    triples: list[tuple]
    fields: list[tuple[str, str, tuple | None]]


def entity_kinds(types: set[URIRef]) -> list[str]:
    kinds = []
    if OWL.Class in types or RDFS.Class in types:
        kinds.append("class")
    if types & PROPERTY_TYPES:
        kinds.append("property")
    if OWL.NamedIndividual in types:
        kinds.append("individual")
    if OWL.Ontology in types:
        kinds.append("ontology")
    return kinds or ["other"]


class EntityIndex:
    def __init__(
        self,
        graph: Graph,
        vector_store: VectorStore | None = None,
        scope: dict[str, str] | None = None,
    ):
        self.vector_store = vector_store
        self.scope = scope or {}
        if vector_store and not {"ontology_id", "version"}.issubset(self.scope):
            raise ValueError("Ontology vector index requires ontology_id and version")
        outgoing: dict[URIRef, list[tuple]] = {}
        for triple in graph:
            if isinstance(triple[0], URIRef):
                outgoing.setdefault(triple[0], []).append(triple)
        self.entities = []
        for iri in sorted(outgoing, key=str):
            triples = sorted(outgoing[iri], key=lambda t: tuple(term.n3() for term in t))
            types = {o for _, p, o in triples if p == RDF.type and isinstance(o, URIRef)}
            fields: list[tuple[str, str, tuple | None]] = [("name", local_name(iri), None)]
            for triple in triples:
                _, predicate, obj = triple
                if isinstance(obj, Literal) and predicate in LABELS | DESCRIPTIONS:
                    field = "label" if predicate in LABELS else "description"
                    fields.append((field, str(obj), triple))
            self.entities.append(
                Entity(
                    iri,
                    local_name(iri),
                    sorted(map(str, types)),
                    entity_kinds(types),
                    triples,
                    fields,
                )
            )
        self.texts = ["\n".join(value for _, value, _ in e.fields) for e in self.entities]
        corpus = [tokens(text) for text in self.texts]
        # delta=0: no baseline score for documents that do not contain query words.
        # BM25Plus IDF is positive even in tiny ontologies with common words.
        self.bm25 = BM25Plus(corpus, k1=1.2, b=0.75, delta=0) if any(corpus) else None
        if vector_store:
            vector_store.upsert(
                [
                    VectorRecord(
                        key=f"{self.scope}:{entity.iri}",
                        text=text,
                        metadata={
                            **self.scope,
                            "iri": str(entity.iri),
                            "kinds": entity.kinds,
                            "source_type": "ontology",
                        },
                    )
                    for entity, text in zip(self.entities, self.texts, strict=True)
                ]
            )

    @property
    def embedding_model(self) -> str | None:
        return self.vector_store.encoder.model_id if self.vector_store else None

    def search(
        self, query: str, kind: Kind = "all", mode: SearchMode = "lexical"
    ) -> list[SearchHit]:
        query = query.strip()
        if not query or len(query.encode("utf-8")) > 4096:
            raise ValueError("query must contain 1..4096 UTF-8 bytes after trimming")
        if kind not in {"all", "class", "property", "individual", "ontology", "other"}:
            raise ValueError("Invalid entity kind")
        if mode not in {"lexical", "hybrid"}:
            raise ValueError("mode must be lexical or hybrid")
        if mode == "hybrid" and self.vector_store is None:
            raise ValueError("Hybrid search requires an explicitly configured embedding model")
        query_tokens = list(dict.fromkeys(tokens(query)))
        word_set = set(query_tokens)
        lexical = self.bm25.get_scores(query_tokens) if self.bm25 else np.zeros(len(self.entities))
        candidates = [i for i, e in enumerate(self.entities) if kind == "all" or kind in e.kinds]
        exact = {}
        for i in candidates:
            e = self.entities[i]
            exact[i] = (
                8.0
                if str(e.iri) == query
                else (
                    4.0
                    if any(
                        query.casefold() == value.casefold()
                        for field, value, _ in e.fields
                        if field in {"label", "name"}
                    )
                    else 0.0
                )
            )
        scores = {i: float(lexical[i]) + exact[i] for i in candidates}
        cosine: dict[int, float] = {}
        rrf: dict[int, float] = {}
        if mode == "hybrid" and self.vector_store is not None:
            scope = {**self.scope, "source_type": "ontology"}
            if kind != "all":
                scope["kinds"] = kind
            vector_hits = self.vector_store.search(query, scope, limit=50)
            indices = {str(entity.iri): i for i, entity in enumerate(self.entities)}
            cosine = {
                indices[hit["iri"]]: hit["score"]
                for hit in vector_hits
                if hit.get("iri") in indices and hit["score"] > 0
            }
            # Fuse only the best 50 per channel; a kind filter is applied before ranking.
            lexical_order = sorted(
                (i for i in candidates if scores[i] > 0),
                key=lambda i: (-scores[i], str(self.entities[i].iri)),
            )[:50]
            vector_order = sorted(
                (i for i in candidates if i in cosine),
                key=lambda i: (-cosine[i], str(self.entities[i].iri)),
            )[:50]
            for order in (lexical_order, vector_order):
                for rank, i in enumerate(order, 1):
                    rrf[i] = rrf.get(i, 0.0) + 1.0 / (60 + rank)
            scores = {i: rrf.get(i, 0.0) + exact[i] for i in candidates}
        hits = []
        for i in sorted(candidates, key=lambda i: (-scores[i], str(self.entities[i].iri))):
            if scores[i] <= 0:
                continue
            entity = self.entities[i]
            matched_fields = set()
            evidence = set()
            if exact[i] == 8:
                matched_fields.add("iri")
            for field, value, triple in entity.fields:
                if word_set.intersection(tokens(value)) or query.casefold() == value.casefold():
                    matched_fields.add(field)
                    if triple:
                        evidence.add(triple)
            if i in cosine:
                matched_fields.add("embedding")
            if not evidence:
                evidence.update(t for t in entity.triples if t[1] == RDF.type)
                if not evidence:
                    evidence.update(entity.triples[:1])
            parts = {"bm25": float(lexical[i]), "exact": exact[i]}
            if i in cosine:
                parts["cosine"] = cosine[i]
            if i in rrf:
                parts["rrf"] = rrf[i]
            hits.append(
                SearchHit(
                    iri=str(entity.iri),
                    name=entity.name,
                    types=entity.types,
                    kinds=entity.kinds,
                    score=scores[i],
                    scores=parts,
                    matched_fields=sorted(matched_fields),
                    evidence=[
                        describe_statement(t)
                        for t in sorted(evidence, key=lambda t: tuple(term.n3() for term in t))
                    ],
                )
            )
        return hits
