import hashlib

import pytest
from rdflib import OWL, RDF, RDFS, BNode, Literal, URIRef

from owl_rag.models import describe_node
from owl_rag.ontology import Ontology, parse_iri
from owl_rag.service import OntologyService


def test_rdfxml_base_terms_and_provenance(minimal):
    from rdflib import XSD

    assert minimal.source.triple_count == 11
    assert minimal.source.semantics == "asserted"
    assert list(map(str, minimal.named_classes())) == [
        "https://example.org/demo/Computer",
        "https://example.org/demo/Hardware",
    ]
    assert minimal.parents(URIRef("https://example.org/demo/Computer")) == [
        "https://example.org/demo/Hardware"
    ]
    assert any(isinstance(s, BNode) for s in minimal.graph.subjects(RDF.type, OWL.Restriction))
    label = next(
        o
        for o in minimal.graph.objects(None, RDFS.label)
        if isinstance(o, Literal) and o.language == "ru"
    )
    assert describe_node(label).language == "ru"
    typed = describe_node(Literal("12", datatype=XSD.integer))
    assert typed.datatype == str(XSD.integer)
    assert minimal.resolve_class("Hardware") == URIRef("https://example.org/demo/Hardware")


def test_turtle_nt_version_and_no_inference(tmp_path):
    text = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    <urn:A> a owl:Class; rdfs:subClassOf <urn:B> .
    <urn:B> rdfs:subClassOf <urn:C> .
    <urn:onto> owl:imports <http://unreachable.invalid/not-fetched> ."""
    path = tmp_path / "test.ttl"
    path.write_text(text)
    ontology = Ontology.load("test", path)
    assert ontology.source.version == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert ontology.parents(URIRef("urn:A")) == ["urn:B"]
    assert (URIRef("urn:A"), RDFS.subClassOf, URIRef("urn:C")) not in ontology.graph
    nt = tmp_path / "test.nt"
    nt.write_text(ontology.graph.serialize(format="nt"))
    assert len(Ontology.load("nt", nt).graph) == len(ontology.graph)
    path.write_text(text + "\n")
    assert Ontology.load("test", path).source.version != ontology.source.version


@pytest.mark.parametrize("value", ["Hardware", "_:node", "", "http://example.org/a b", "urn:x>"])
def test_bad_iris(value):
    with pytest.raises(ValueError):
        parse_iri(value)


def test_bad_files_and_ambiguous_names(tmp_path, search_ontology):
    with pytest.raises(FileNotFoundError):
        Ontology.load("bad", tmp_path / "missing.owl")
    path = tmp_path / "bad.owl"
    for content in ("", "not XML"):
        path.write_text(content)
        with pytest.raises(ValueError):
            Ontology.load("bad", path)
    with pytest.raises(ValueError, match="Ambiguous"):
        search_ontology.resolve_class("GraphDatabase")


def test_registry_pages_and_blank_navigation(minimal, search_ontology):
    service = OntologyService([minimal, search_ontology])
    first = service.list_classes("demo", limit=1)
    assert first["next_offset"] == 1
    assert service.list_classes("demo", offset=1, limit=1)["next_offset"] is None
    assert service.list_classes("demo", offset=100)["items"] == []
    computer = "https://example.org/demo/Computer"
    result = service.get_relations("demo", computer)
    blank = next(t["object"]["n3"] for t in result["items"] if t["object"]["kind"] == "blank")
    restriction = service.get_relations("demo", blank)
    assert any(t["predicate"] == str(OWL.onProperty) for t in restriction["items"])
    assert all(
        t["object"]["value"] == "https://example.org/demo/Hardware"
        for t in service.get_relations("demo", "https://example.org/demo/Hardware", "incoming")[
            "items"
        ]
    )
    for kwargs in ({"limit": 0}, {"offset": -1}, {"limit": 501}):
        with pytest.raises(ValueError):
            service.list_classes("demo", **kwargs)
    with pytest.raises(ValueError, match="Unknown"):
        service.list_classes("missing")
    with pytest.raises(ValueError, match="Duplicate"):
        OntologyService([minimal, minimal])
