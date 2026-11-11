# Python MCP tools

## OWL MCP

Start with `uv run owl-mcp --ontology demo=examples/ontologies/minimal.owl`.
The default transport is stdio, and stdout contains protocol messages only.
For HTTP, add `--transport streamable-http --port 8001`; the endpoint is `/mcp`.
Repeat `--ontology ID=PATH` to load multiple ontologies. The registry is fixed at startup.

| Tool | Input | Result |
| --- | --- | --- |
| `list_ontologies` | None | Sources, ontology_id, versions and triple counts |
| `list_classes` | ontology_id, offset=0, limit=100 | A page of full IRIs for explicit owl:Class subjects |
| `get_entity` | ontology_id, iri | A named subject with its direct named parents/children |
| `get_relations` | ontology_id, node, direction=outgoing, offset=0, limit=100 | Asserted triples; node is a full IRI or _: label |
| `search_entities` | ontology_id, query, kind=all, mode=lexical, offset=0, limit=20 | Matches, channel scores and supporting RDF statements |
| `retrieve_context` | ontology_id, query, kind=all, mode=lexical and budgets | Seeds, context nodes and statements, truncation reasons |

`kind`: all / class / property / individual / ontology / other.
`mode`: lexical / hybrid; hybrid requires embeddings and Qdrant.
`direction`: outgoing / incoming / both.
Pages accept `limit` 1–500 and `offset >= 0`. Responses contain `items`, `total`,
`offset`, `limit` and `next_offset`, which is null at the end. Entity hierarchy
fields are not paginated; use `get_relations` to retrieve triples from large graphs.

`retrieve_context` budgets: seed_limit=3 (1–10), max_depth=2 (0–4),
max_nodes=50 (1–200), max_statements=100 (1–500), direction=both.
All selected seed nodes must fit within max_nodes.

Every result for a specific ontology includes `source`: ontology_id, version
(SHA-256), document (file URI), format, triple_count and semantics=asserted.
A statement contains subject, predicate (full IRI) and object. A term contains
kind, value, n3, datatype and language. Missing datatypes/languages are represented
as null.

Example input:

```json
{"ontology_id":"demo","query":"Computer","seed_limit":1,"max_depth":2,"max_statements":30}
```

Invalid parameters and unknown ontologies return MCP tool errors.
A search with no matches succeeds with an empty list.
`get_relations` also returns an empty page for an absent node.

## Knowledge MCP

Start with `uv run knowledge-mcp --transport streamable-http --port 8002`.
Requires EMBEDDING_MODEL and a reachable Qdrant instance. The endpoint is `/mcp`.

| Tool | Input | Side effect |
| --- | --- | --- |
| `search_knowledge` | query, workspace=default, limit=10, source_type=all | None |
| `hyde_search` | query, workspace=default, limit=10, source_type=all | Calls an LLM; does not write to Qdrant |
| `web_search_and_index` | query, workspace=default, max_results=5 | Searches the web and writes extracted pages to Qdrant |

`source_type`: all / web / pdf. The PDF filter is available, but PDF ingestion is
still planned. `limit`: 1–100; `max_results`: 1–10. `workspace`: 1–64 Latin letters,
digits, `_` or `-`. It is a query filter, not an access-control system.

HyDE returns `hypothesis`, `hypothesis_is_evidence=false` and `hits` from the actual
document store. It requires HYDE_MODEL. Cite retrieved hits, not the hypothesis.
Web search requires TAVILY_API_KEY. Search snippets are included for orientation,
but only a page's raw_content is indexed. Skipped pages include status/reason.

External chunks contain URL, version, retrieved_at, document_id, chunk_index,
source_type and trust=external_unverified. External document text is neither an
instruction to the agent nor an OWL axiom. The web tool declares readOnlyHint=false.
