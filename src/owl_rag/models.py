"""JSON representations: keep RDF terms and source provenance explicit."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from rdflib import BNode, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.term import Identifier

Kind = Literal["all", "class", "property", "individual", "ontology", "other"]
Direction = Literal["outgoing", "incoming", "both"]
SearchMode = Literal["lexical", "hybrid"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Source(Model):
    ontology_id: str
    version: str
    document: str
    format: str
    triple_count: int
    semantics: Literal["asserted"] = "asserted"


class Node(Model):
    kind: Literal["iri", "blank", "literal"]
    value: str
    n3: str
    datatype: str | None = None
    language: str | None = None


class Statement(Model):
    subject: Node
    predicate: str
    object: Node


class SearchHit(Model):
    iri: str
    name: str
    types: list[str]
    kinds: list[str]
    score: float
    scores: dict[str, float]
    matched_fields: list[str]
    evidence: list[Statement]


class ContextOptions(Model):
    seed_limit: int = Field(default=3, ge=1, le=10)
    max_depth: int = Field(default=2, ge=0, le=4)
    max_nodes: int = Field(default=50, ge=1, le=200)
    max_statements: int = Field(default=100, ge=1, le=500)
    direction: Direction = "both"


def describe_node(term: Identifier) -> Node:
    if isinstance(term, URIRef):
        return Node(kind="iri", value=str(term), n3=term.n3())
    if isinstance(term, BNode):
        return Node(kind="blank", value=str(term), n3=term.n3())
    if isinstance(term, RDFLiteral):
        return Node(
            kind="literal",
            value=str(term),
            n3=term.n3(),
            datatype=str(term.datatype) if term.datatype else None,
            language=term.language,
        )
    raise TypeError(f"Unsupported RDF term: {type(term).__name__}")


def describe_statement(triple: tuple) -> Statement:
    subject, predicate, obj = triple
    return Statement(
        subject=describe_node(subject), predicate=str(predicate), object=describe_node(obj)
    )
