import pytest
from rdflib import OWL, Graph, URIRef

from owl_rag.models import ContextOptions
from owl_rag.ontology import Ontology
from owl_rag.search import EntityIndex
from owl_rag.service import OntologyService


def test_bm25_labels_descriptions_names_and_filters(search_ontology, minimal):
    index = EntityIndex(search_ontology.graph)
    assert index.search("графовая база")[0].iri.endswith("/GraphDatabase")
    assert "label" in index.search("Network storage")[0].matched_fields
    assert "description" in index.search("vertices edges")[0].matched_fields
    assert index.search("https://other.example/GraphDatabase")[0].iri == (
        "https://other.example/GraphDatabase"
    )
    assert {hit.iri for hit in index.search("GraphDatabase", "class")[:2]} == {
        "https://example.org/search/GraphDatabase",
        "https://other.example/GraphDatabase",
    }
    assert all("property" in h.kinds for h in index.search("embedding", "property"))
    assert index.search("VectorService", "individual")[0].iri.endswith("VectorService")
    assert index.search("HiddenRestriction") == []
    assert index.search("word-that-does-not-occur") == []
    hit = EntityIndex(minimal.graph).search("оборудование")[0]
    assert hit.evidence[0].object.language == "ru"
    with pytest.raises(ValueError):
        index.search(" ")
    with pytest.raises(ValueError, match="Hybrid"):
        index.search("hello", mode="hybrid")


def test_qdrant_hybrid_and_version_isolation(search_ontology, minimal, store):
    service = OntologyService([search_ontology, minimal], store)
    result = service.search_entities("search", "meaning representation", mode="hybrid")
    assert result["items"]
    assert result["items"][0]["iri"].startswith("https://example.org/search/")
    assert "embedding" in result["items"][0]["matched_fields"]
    assert "rrf" in result["items"][0]["scores"]
    assert all(
        "class" in hit["kinds"]
        for hit in service.search_entities("search", "meaning", kind="class", mode="hybrid")[
            "items"
        ]
    )
    assert store.search("meaning", {"ontology_id": "missing"}) == []
    assert store.search("meaning", {"ontology_id": "search", "version": "stale"}) == []
    assert all(
        h["ontology_id"] == "demo" for h in store.search("computer", {"ontology_id": "demo"})
    )


def test_context_restrictions_depth_and_limits(minimal):
    service = OntologyService([minimal])
    result = service.retrieve_context("demo", "Computer", options=ContextOptions(seed_limit=1))
    assert any(t["statement"]["predicate"] == str(OWL.onProperty) for t in result["statements"])
    assert any(t["node"]["kind"] == "blank" for t in result["nodes"])
    assert not result["truncated"]
    zero = service.retrieve_context("demo", "Computer", options=ContextOptions(max_depth=0))
    assert len(zero["nodes"]) == 1 and zero["statements"] == []
    for options, reason in [
        (ContextOptions(max_nodes=1), "max_nodes"),
        (ContextOptions(max_statements=1), "max_statements"),
    ]:
        bounded = service.retrieve_context("demo", "Computer", options=options)
        assert bounded["truncated"] and reason in bounded["truncation_reasons"]
        assert len(bounded["nodes"]) <= options.max_nodes
        assert len(bounded["statements"]) <= options.max_statements
    assert service.retrieve_context("demo", "absent")["nodes"] == []


def test_cycles_and_shared_vocabulary_are_bounded(minimal):
    graph = Graph().parse(
        data="""@prefix owl: <http://www.w3.org/2002/07/owl#> .
    <urn:A> a owl:Class; <urn:link> <urn:B> .
    <urn:B> a owl:Class; <urn:link> <urn:A> .
    <urn:Unrelated> a owl:Class .""",
        format="turtle",
    )
    doc = Ontology(source=minimal.source.model_copy(update={"ontology_id": "cycle"}), graph=graph)
    service = OntologyService([doc])
    result = service.retrieve_context("cycle", "urn:A", options=ContextOptions(max_depth=4))
    nodes = [n["node"]["value"] for n in result["nodes"]]
    assert "urn:Unrelated" not in nodes
    assert set(nodes) == {"urn:A", "urn:B", str(OWL.Class)}
    assert len(result["statements"]) == 4
    assert graph.value(URIRef("urn:B"), URIRef("urn:link")) == URIRef("urn:A")
