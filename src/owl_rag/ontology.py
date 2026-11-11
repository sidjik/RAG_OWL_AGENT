"""Local RDF loading and asserted graph operations. No LLM dependency."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from rdflib import OWL, RDF, RDFS, BNode, Graph, URIRef
from rdflib.term import Identifier

from owl_rag.models import Source

FORMATS = {".owl": "xml", ".rdf": "xml", ".xml": "xml", ".ttl": "turtle", ".nt": "nt"}
SUPPORTED_FORMATS = {"xml", "turtle", "nt"}


@dataclass(frozen=True)
class Ontology:
    source: Source
    graph: Graph

    @classmethod
    def load(cls, ontology_id: str, path: str | Path, format: str | None = None) -> "Ontology":
        if not ontology_id.strip() or ontology_id != ontology_id.strip():
            raise ValueError("ontology_id must be non-empty and have no surrounding whitespace")
        path = Path(path).resolve(strict=True)
        syntax = format or FORMATS.get(path.suffix.lower())
        if syntax not in SUPPORTED_FORMATS:
            raise ValueError("Supported formats: xml (RDF/XML), turtle, nt. Specify --format.")
        data = path.read_bytes()
        if not data.strip():
            raise ValueError(f"Empty ontology: {path}")
        graph = Graph(bind_namespaces="none")
        # Passing bytes and a file base avoids treating the argument as a remote URL.
        # owl:imports remains a triple: imported documents are never fetched here.
        try:
            graph.parse(data=data, format=syntax, publicID=path.as_uri())
        except Exception as exc:
            raise ValueError(f"Cannot parse {path.name} as {syntax}: {exc}") from exc
        return cls(
            source=Source(
                ontology_id=ontology_id,
                version="sha256:" + hashlib.sha256(data).hexdigest(),
                document=path.as_uri(),
                format=syntax,
                triple_count=len(graph),
            ),
            graph=graph,
        )

    def named_classes(self) -> list[URIRef]:
        return sorted(
            {s for s in self.graph.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)},
            key=str,
        )

    def resolve_class(self, name: str) -> URIRef:
        matches = [iri for iri in self.named_classes() if str(iri) == name]
        if not matches:
            matches = [iri for iri in self.named_classes() if local_name(iri) == name]
        if not matches:
            raise ValueError(f"Named owl:Class not found: {name}")
        if len(matches) > 1:
            raise ValueError(f"Ambiguous class name {name!r}; use the full IRI: {matches}")
        return matches[0]

    def parents(self, iri: URIRef) -> list[str]:
        return sorted(
            str(o) for o in self.graph.objects(iri, RDFS.subClassOf) if isinstance(o, URIRef)
        )

    def children(self, iri: URIRef) -> list[str]:
        return sorted(
            str(s) for s in self.graph.subjects(RDFS.subClassOf, iri) if isinstance(s, URIRef)
        )


def local_name(iri: str | URIRef) -> str:
    value = str(iri).rstrip("/")
    return unquote(value.rsplit("#", 1)[-1].rsplit("/", 1)[-1].rsplit(":", 1)[-1])


def parse_iri(value: str) -> URIRef:
    if not value or any(c.isspace() or c in '<>"{}|\\^`' for c in value):
        raise ValueError("Expected an absolute IRI without whitespace")
    try:
        scheme = urlsplit(value).scheme
    except ValueError as exc:
        raise ValueError("Invalid IRI") from exc
    if not scheme or value.startswith("_:"):
        raise ValueError("Expected an absolute IRI")
    return URIRef(value)


def parse_node(value: str) -> URIRef | BNode:
    if value.startswith("_:"):
        if len(value) == 2 or any(c.isspace() for c in value):
            raise ValueError("Invalid blank node identifier")
        return BNode(value[2:])
    return parse_iri(value)


def sorted_triples(graph: Graph, node: Identifier, direction: str) -> list[tuple]:
    pattern = (node, None, None) if direction == "outgoing" else (None, None, node)
    return sorted(graph.triples(pattern), key=lambda t: tuple(term.n3() for term in t))
