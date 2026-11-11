# Reading the Python implementation

1. `src/owl_rag/ontology.py`: a file becomes an RDFLib Graph, with IRI,
   BNode and Literal kept as distinct types. Start with `Ontology.load`,
   `parents`, `children` and the corresponding tests in `tests/test_ontology.py`.
2. `models.py`: RDF terms are converted to JSON while preserving language and datatype.
3. `search.py`: named subjects become BM25 documents; results can then be
   combined with Qdrant results through RRF.
4. `vector_store.py`: an encoder produces vectors, and Qdrant stores them with
   metadata. A mandatory scope restricts each query.
5. `context.py`: a BFS queue, cycle protection, depth limits and count budgets.
6. `service.py`: selects a specific ontology and returns results with source metadata.
7. `cli.py` and `mcp_server.py`: two adapters for the same operations, exposed
   through a local CLI and MCP.
8. `knowledge.py`: handles external documents separately. `hyde_search` reads
   the index; `web_search_and_index` explicitly adds knowledge to it.
9. `providers.py` and `web_search.py`: network calls sit behind small, replaceable
   interfaces. Tests do not require real paid APIs.

Start with `uv run owl-inspect examples/ontologies/minimal.owl --entity Computer`.
Then follow the call through the CLI and service down to RDFLib.

`Protocol` describes the methods expected from an adapter, `dataclass` stores data,
and Pydantic validates parameters and JSON models. Keep full `URIRef` identifiers:
the same local name can occur in different IRI namespaces.

10. `agent_settings.py`: service URLs, model aliases and request budgets.
11. `agent_mcp.py`: discovers tools, adds server prefixes and binds each request's
    ontology and workspace before calling the MCP SDK.
12. `agent.py`: the LangGraph retrieval / model / tool loop, bounded observations
    and source provenance. Start with `AgentRunner.run` and `Sources.collect`.
13. `agent_api.py`: text chat validation, bearer authentication, model listing,
    JSON completions and SSE delivery for Open WebUI.

Agent coverage is in `tests/test_agent.py`, `tests/test_agent_api.py` and
`tests/test_agent_http.py`. The HTTP test starts real local services and a
controlled model endpoint, without paid API calls.
