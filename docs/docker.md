# Running the infrastructure with a local .env

Requires Docker Engine and Docker Compose 2.20.3+. The main file is
[compose.yaml](../compose.yaml) at the repository root. The previous
`deploy/compose.yaml` path remains available as a wrapper using `include`.

## Settings to fill in

Copy the required settings from [.env.example](../.env.example) into your `.env`.
If the file already exists, extend it while preserving existing keys.
Replace the example's placeholders with your own values.

| Variable | Value |
| --- | --- |
| `LITELLM_MASTER_KEY` | A key you choose for access to the local proxy, such as `sk-` followed by a random string |
| `CHAT_UPSTREAM_MODEL` | Full chat-model name in LiteLLM's `provider/model-id` format; the future agent requires tool calling |
| `CHAT_API_KEY` | Chat provider API key; `none` is usually suitable for a local API without authentication |
| `CHAT_API_BASE` | Custom provider/compatible-server URL; leave empty for the provider default |
| `EMBEDDING_UPSTREAM_MODEL` | Full embedding-model name in LiteLLM's `provider/model-id` format |
| `EMBEDDING_API_KEY` | Embedding provider API key; it may be the same as the chat key |
| `EMBEDDING_API_BASE` | Custom embedding endpoint; leave empty for the provider default |
| `TAVILY_API_KEY` | Tavily key; the server starts without it, but web search reports missing configuration |
| `ONTOLOGY_PATH` | File path relative to the repository root, or an absolute path |
| `ONTOLOGY_ID` | Ontology identifier in MCP; defaults to `demo` |
| `ONTOLOGY_FORMAT` | `xml`, `turtle` or `nt`; defaults to `xml` |

Upstream models are configured in LiteLLM. The
[proxy configuration](../deploy/litellm/config.yaml) defines two public aliases:

- `chat` → `CHAT_UPSTREAM_MODEL`, used by HyDE and later by the agent;
- `embeddings` → `EMBEDDING_UPSTREAM_MODEL`, used for indexing and retrieval.

LiteLLM's `provider/model-id` format, `api_key`, `api_base` and `os.environ/NAME`
references are described in the
[official documentation](https://docs.litellm.ai/docs/proxy/configs).
If a provider needs additional settings, such as an API version or credentials file,
add them to its `litellm_params` block.

For a model server running on the same computer, use
`http://host.docker.internal:PORT/v1` from Docker. This host alias is already
configured for LiteLLM. Inside a container, `localhost` refers to that container.

## Start the services

From the repository root, after filling in `.env`:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 litellm owl-mcp knowledge-mcp agent open-webui
```

If a required `LITELLM_MASTER_KEY`, `CHAT_UPSTREAM_MODEL` or
`EMBEDDING_UPSTREAM_MODEL` is missing, Compose identifies the variable to fill in.
`config --quiet` validates the configuration without printing keys.

| Service | Address from the host |
| --- | --- |
| LiteLLM API | `http://localhost:4000/v1` |
| LiteLLM readiness probe | `http://localhost:4000/health/readiness` |
| Qdrant | `http://localhost:6333` |
| OWL MCP | `http://localhost:8001/mcp` |
| Knowledge MCP | `http://localhost:8002/mcp` |
| Agent API | `http://localhost:8000/v1` |
| Open WebUI | `http://localhost:3000` |

MCP containers use `http://litellm:4000/v1` and `http://qdrant:6333` internally;
Compose supplies these addresses. The example's `LITELLM_BASE_URL` and `QDRANT_URL`
are for Python commands running on the host. For local Python commands,
`LITELLM_API_KEY` falls back to `LITELLM_MASTER_KEY`. Compose passes the key explicitly.

LiteLLM receives upstream provider keys, and Knowledge MCP receives the Tavily key.
MCP services receive the proxy key rather than model-provider keys. Local development
uses the master key; user virtual keys and database-backed model management are not
configured here.

On startup, OWL MCP creates embeddings for entities in the selected ontology,
which calls the embedding API. For an invalid endpoint, model or key, check LiteLLM
and OWL MCP logs. Container readiness probes do not call models; a healthy LiteLLM
process does not establish that upstream models are working.

LiteLLM runs without PostgreSQL: models are configured in YAML rather than through
the Admin UI. Its image is pinned to the official
[v1.106.6 release](https://github.com/BerriAI/litellm/releases/tag/v1.106.6).

## Check from the host

```bash
curl --fail http://localhost:4000/health/readiness
uv run --env-file .env owl-inspect examples/ontologies/search.owl \
  --query "vector database" --mode hybrid
```

The second command makes real embedding requests. MCP endpoints are intended for
an MCP client or Inspector. Open WebUI is available at `http://localhost:3000`. Create the initial account,
select `owl-agent` and ask about the configured ontology. The API also supports
text chat clients directly; see the [agent guide](agent.md).

## Update settings and stop services

After changing a model, endpoint or key, recreate the dependent containers:

```bash
docker compose up -d --force-recreate litellm owl-mcp knowledge-mcp agent open-webui
docker compose down
```

When changing the embedding model, remove the old index or use a new vector-space
identifier. The client currently identifies the encoder by proxy address and alias:
replacing the upstream behind `embeddings` requires reindexing even when dimensions
are unchanged. The OWL index is rebuilt at startup; web documents need to be ingested
again. Automatic migration of existing vectors is a separate future step.

Qdrant retains data in the `qdrant_data` named volume after `docker compose down`.
Reuse the same `.env` for subsequent starts.

## Agent and UI settings

The agent uses LiteLLM's `chat` alias. Open WebUI connects to the agent API,
so all retrieval and tool execution goes through LangGraph. Set `AGENT_API_KEY`
for a separate client credential; otherwise local development uses the proxy key.
`ONTOLOGY_ID` selects the ontology used by WebUI requests. Step, tool and web
budgets are described in the [agent guide](agent.md).

The agent readiness probe waits for the MCP servers to expose their tools. The
UI starts after the agent is ready. Upstream chat quality and model availability
are checked by actual requests, not by the readiness probe.

WebUI chats and its automatically generated session key are retained in the
`webui_data` volume. You can set `WEBUI_SECRET_KEY` explicitly in `.env`; keep
it stable across container recreation. Background title, tag, follow-up and
autocomplete generation are disabled. Connections are configured by Compose.
