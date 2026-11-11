import sys
from datetime import timedelta

from conftest import ROOT
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from owl_rag.knowledge import KnowledgeService
from owl_rag.knowledge_server import create_server
from owl_rag.web_search import WebPage


async def test_owl_stdio_protocol_and_tool_errors():
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "owl_rag.mcp_server",
            "--ontology",
            f"demo={ROOT / 'examples/ontologies/minimal.owl'}",
        ],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=10)
        ) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            assert {t.name for t in tools} == {
                "list_ontologies",
                "list_classes",
                "get_entity",
                "get_relations",
                "search_entities",
                "retrieve_context",
            }
            result = await session.call_tool(
                "retrieve_context",
                {
                    "ontology_id": "demo",
                    "query": "Computer",
                    "max_statements": 1,
                },
            )
            assert not result.isError
            data = result.structuredContent
            assert data["source"]["semantics"] == "asserted"
            assert data["truncated"] and len(data["statements"]) == 1
            bad = await session.call_tool("list_classes", {"ontology_id": "missing"})
            assert bad.isError
            # An invalid tool call does not terminate the MCP session.
            assert not (await session.call_tool("list_ontologies", {})).isError


async def test_knowledge_tools_and_write_annotation(store):
    server = create_server(KnowledgeService(store))
    tools = await server.list_tools()
    assert {t.name for t in tools} == {"search_knowledge", "hyde_search", "web_search_and_index"}
    write = next(t for t in tools if t.name == "web_search_and_index")
    assert write.annotations.readOnlyHint is False
    assert "workspace" in write.inputSchema["properties"]
    assert all(tool.outputSchema is not None for tool in tools)


async def test_knowledge_tool_ingestion_then_hyde(store):
    class Web:
        def search(self, query, max_results):
            return [
                WebPage("https://example.org/method", "Method", "short", "Vector embedding " * 30)
            ]

    class Generator:
        def generate(self, system, prompt):
            return "Hypothetical description of vector embedding similarity."

    server = create_server(KnowledgeService(store, Generator(), Web()))
    _, indexed = await server.call_tool("web_search_and_index", {"query": "embedding"})
    assert indexed["indexed_documents"] == 1
    before = store.client.count(store.collection, exact=True).count
    _, found = await server.call_tool("hyde_search", {"query": "meaning"})
    assert found["hypothesis_is_evidence"] is False
    assert found["hits"][0]["url"] == "https://example.org/method"
    assert store.client.count(store.collection, exact=True).count == before
