"""Application operations shared by the CLI and MCP; explicit ontology selection."""

from owl_rag.context import graph_context
from owl_rag.models import ContextOptions, Direction, Kind, SearchMode, describe_statement
from owl_rag.ontology import Ontology, parse_iri, parse_node, sorted_triples
from owl_rag.search import EntityIndex
from owl_rag.vector_store import VectorStore


def page(items: list, offset: int, limit: int) -> dict:
    if offset < 0 or not 1 <= limit <= 500:
        raise ValueError("offset must be non-negative; limit must be between 1 and 500")
    end = min(offset + limit, len(items))
    return {
        "items": items[offset:end],
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "next_offset": end if end < len(items) else None,
    }


class OntologyService:
    def __init__(self, ontologies: list[Ontology], vector_store: VectorStore | None = None):
        if not ontologies:
            raise ValueError("At least one ontology is required")
        self.documents: dict[str, Ontology] = {}
        self.indices: dict[str, EntityIndex] = {}
        for ontology in ontologies:
            identifier = ontology.source.ontology_id
            if identifier in self.documents:
                raise ValueError(f"Duplicate ontology_id: {identifier}")
            self.documents[identifier] = ontology
            self.indices[identifier] = EntityIndex(
                ontology.graph,
                vector_store,
                {"ontology_id": identifier, "version": ontology.source.version},
            )

    def document(self, ontology_id: str) -> Ontology:
        if ontology_id not in self.documents:
            raise ValueError(f"Unknown ontology_id: {ontology_id}")
        return self.documents[ontology_id]

    def list_ontologies(self) -> dict:
        return {
            "ontologies": [
                self.documents[key].source.model_dump() for key in sorted(self.documents)
            ]
        }

    def list_classes(self, ontology_id: str, offset: int = 0, limit: int = 100) -> dict:
        doc = self.document(ontology_id)
        return {
            "source": doc.source.model_dump(),
            **page(list(map(str, doc.named_classes())), offset, limit),
        }

    def get_entity(self, ontology_id: str, iri: str) -> dict:
        doc = self.document(ontology_id)
        node = parse_iri(iri)
        if not any(doc.graph.triples((node, None, None))):
            raise ValueError(f"Named subject not found: {iri}")
        return {
            "source": doc.source.model_dump(),
            "iri": iri,
            "parents": doc.parents(node),
            "children": doc.children(node),
        }

    def get_relations(
        self,
        ontology_id: str,
        node: str,
        direction: Direction = "outgoing",
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        doc = self.document(ontology_id)
        term = parse_node(node)
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError("Invalid relation direction")
        directions = ("outgoing", "incoming") if direction == "both" else (direction,)
        triples = list(
            dict.fromkeys(t for d in directions for t in sorted_triples(doc.graph, term, d))
        )
        return {
            "source": doc.source.model_dump(),
            "node": node,
            "direction": direction,
            **page([describe_statement(t).model_dump() for t in triples], offset, limit),
        }

    def search_entities(
        self,
        ontology_id: str,
        query: str,
        kind: Kind = "all",
        mode: SearchMode = "lexical",
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        doc = self.document(ontology_id)
        index = self.indices[ontology_id]
        hits = index.search(query, kind, mode)
        return {
            "source": doc.source.model_dump(),
            "query": query,
            "mode": mode,
            "embedding_model": index.embedding_model,
            **page([hit.model_dump() for hit in hits], offset, limit),
        }

    def retrieve_context(
        self,
        ontology_id: str,
        query: str,
        kind: Kind = "all",
        mode: SearchMode = "lexical",
        options: ContextOptions | None = None,
    ) -> dict:
        doc = self.document(ontology_id)
        options = options or ContextOptions()
        hits = self.indices[ontology_id].search(query, kind, mode)
        seeds = hits[: options.seed_limit]
        return {
            "source": doc.source.model_dump(),
            "query": query,
            "mode": mode,
            "options": options.model_dump(),
            "search_total": len(hits),
            "seeds": [{"iri": h.iri, "name": h.name, "score": h.score} for h in seeds],
            **graph_context(doc, [hit.iri for hit in seeds], options),
        }
