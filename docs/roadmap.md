# Iterations toward a demonstrable project

## 1. Python retrieval and MCP — implemented

- RDFLib: RDF/XML, Turtle, N-Triples, source provenance and versions.
- BM25, Qdrant, RRF and bounded graph traversal.
- OWL MCP and a separate Knowledge MCP.
- HyDE as query expansion without storing the hypothesis as knowledge.
- Web search with indexing of extracted pages and metadata.
- CLI, Compose for LiteLLM, Qdrant and MCP, `.env.example`, and tests without paid APIs.

Acceptance criterion: an MCP client retrieves supporting RDF triples and actual
documents. Reindexing a URL creates no duplicate chunks, and query scopes keep
sources isolated.

## 2. Agent and user workflow — implemented, live-provider validation pending

- LangGraph ReAct through LiteLLM, with tool discovery from both MCP servers.
- Limits on steps, timeouts, web page counts and result sizes.
- Treat external text as data and retain source provenance in answers.
- FastAPI: compatible chat API and streaming responses for Open WebUI.
- Add Open WebUI and the agent to Compose; verify question → tools → answer.

Implemented: scoped MCP discovery, a bounded LangGraph loop, source references,
authenticated text chat API, SSE delivery and Open WebUI wiring in Compose.
Tests cover real MCP sessions, HTTP transports and a controlled model endpoint.
A run with configured provider credentials is still required to assess live answers.

Acceptance criterion: users receive cited answers and a clear indication when
supporting sources are insufficient. The agent selects HyDE and web search as needed.

## 3. PDFs and the paper library

- pypdf, text per page and chunk metadata with title / URL / page.
- Ingestion and reindexing of papers from the [reading list](paper-library.md).
- A shared external-knowledge vector database with pdf / web filters.
- Retrieval of specific passages and verifiable citations in agent answers.

Acceptance criterion: questions about methods find supporting paper passages with
page references.

## 4. Quality and project delivery

- Questions covering multiple ontologies and papers, with source checks.
- Compare BM25 / hybrid / HyDE and investigate unsuccessful answers.
- Langfuse, provider failure handling and reproducible startup.
- A demonstration guide, architecture, limitations and a project presentation scenario.

Timing depends on model access, embedding hardware and delivery requirements.
A reasoner and full OWL semantic support are outside this MVP.
