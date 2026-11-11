"""Bounded breadth-first traversal, preserving asserted statement orientation."""

from collections import deque
from typing import Any

from rdflib import OWL, RDF, RDFS, SKOS, XSD, BNode, URIRef

from owl_rag.models import ContextOptions, describe_node, describe_statement
from owl_rag.ontology import Ontology, sorted_triples

TERMINAL_NAMESPACES = tuple(map(str, (RDF, RDFS, OWL, XSD, SKOS)))


def graph_context(ontology: Ontology, seeds: list[str], options: ContextOptions) -> dict:
    if len(seeds) > options.max_nodes:
        raise ValueError("max_nodes must accommodate every selected seed")
    nodes: dict[URIRef | BNode, dict[str, Any]] = {}
    queue: deque[tuple[URIRef | BNode, int]] = deque()
    for value in seeds:
        seed_node = URIRef(value)
        if seed_node not in nodes:
            nodes[seed_node] = {
                "node": describe_node(seed_node).model_dump(),
                "depth": 0,
                "seed": True,
            }
            queue.append((seed_node, 0))
    statements: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    reasons: set[str] = set()
    directions = ("outgoing", "incoming") if options.direction == "both" else (options.direction,)
    while queue:
        current, depth = queue.popleft()
        if depth >= options.max_depth:
            continue
        if isinstance(current, URIRef) and str(current).startswith(TERMINAL_NAMESPACES):
            continue
        for direction in directions:
            for triple in sorted_triples(ontology.graph, current, direction):
                if triple in seen:
                    continue
                if len(statements) >= options.max_statements:
                    reasons.add("max_statements")
                    return _result(nodes, statements, reasons)
                resources = [t for t in (triple[0], triple[2]) if isinstance(t, (URIRef, BNode))]
                new_nodes = list(dict.fromkeys(t for t in resources if t not in nodes))
                if len(nodes) + len(new_nodes) > options.max_nodes:
                    reasons.add("max_nodes")
                    continue
                for node in new_nodes:
                    nodes[node] = {
                        "node": describe_node(node).model_dump(),
                        "depth": depth + 1,
                        "seed": False,
                    }
                    queue.append((node, depth + 1))
                seen.add(triple)
                statements.append(
                    {
                        "statement": describe_statement(triple).model_dump(),
                        "depth": depth + 1,
                        "discovered_from": current.n3(),
                    }
                )
    return _result(nodes, statements, reasons)


def _result(nodes: dict, statements: list, reasons: set) -> dict:
    return {
        "nodes": list(nodes.values()),
        "statements": statements,
        "truncated": bool(reasons),
        "truncation_reasons": sorted(reasons),
    }
