"""OWL MCP adapter. Core navigation and lexical retrieval do not require an LLM."""

import argparse
from functools import partial
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from owl_rag.config import configured_store
from owl_rag.models import ContextOptions, Direction, Kind, SearchMode
from owl_rag.ontology import Ontology
from owl_rag.service import OntologyService

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


def create_server(service: OntologyService, host: str = "127.0.0.1", port: int = 8001) -> FastMCP:
    server = FastMCP(
        "OWL GraphRAG",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        instructions="Select ontology_id explicitly. "
        "Results contain asserted RDF, not inferred facts.",
    )

    @server.tool(annotations=READ)
    def list_ontologies() -> dict[str, Any]:
        """List loaded ontologies and their exact source versions."""
        return service.list_ontologies()

    @server.tool(annotations=READ)
    def list_classes(ontology_id: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        """List named subjects explicitly declared owl:Class; results are paginated."""
        return service.list_classes(ontology_id, offset, limit)

    @server.tool(annotations=READ)
    def get_entity(ontology_id: str, iri: str) -> dict[str, Any]:
        """Get a named subject and its direct named parents/children. Use full IRI."""
        return service.get_entity(ontology_id, iri)

    @server.tool(annotations=READ)
    def get_relations(
        ontology_id: str,
        node: str,
        direction: Direction = "outgoing",
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get asserted triples, including anonymous OWL expressions via their _: identifiers."""
        return service.get_relations(ontology_id, node, direction, offset, limit)

    @server.tool(annotations=READ)
    async def search_entities(
        ontology_id: str,
        query: str,
        kind: Kind = "all",
        mode: SearchMode = "lexical",
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Find named entities with BM25 or BM25+Qdrant RRF; return matching RDF evidence."""
        return await anyio.to_thread.run_sync(
            partial(service.search_entities, ontology_id, query, kind, mode, offset, limit)
        )

    @server.tool(annotations=READ)
    async def retrieve_context(
        ontology_id: str,
        query: str,
        kind: Kind = "all",
        mode: SearchMode = "lexical",
        seed_limit: int = 3,
        max_depth: int = 2,
        max_nodes: int = 50,
        max_statements: int = 100,
        direction: Direction = "both",
    ) -> dict[str, Any]:
        """Search for seeds, then traverse their asserted graph within explicit budgets."""
        options = ContextOptions(
            seed_limit=seed_limit,
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_statements=max_statements,
            direction=direction,
        )
        return await anyio.to_thread.run_sync(
            partial(service.retrieve_context, ontology_id, query, kind, mode, options)
        )

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", action="append", required=True, metavar="ID=PATH")
    parser.add_argument("--format", choices=["xml", "turtle", "nt"])
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    store = None
    try:
        docs = []
        for argument in args.ontology:
            identifier, separator, path = argument.partition("=")
            if not separator or not path:
                raise ValueError("--ontology must use the form ID=PATH")
            docs.append(Ontology.load(identifier, path, args.format))
        store = configured_store("owl_entities")
        service = OntologyService(docs, store)
        create_server(service, args.host, args.port).run(transport=args.transport)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"owl-mcp: {exc}\n")
    finally:
        if store:
            store.client.close()


if __name__ == "__main__":
    main()
