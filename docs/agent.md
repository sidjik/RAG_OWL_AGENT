# Chat agent and Open WebUI

The agent uses LangGraph to run a bounded retrieval and tool-calling loop. It
accesses ontologies and external documents through the two MCP servers. Model
calls, including HyDE and embeddings, go through LiteLLM.

## Start the chat interface

Fill in your existing local `.env` using [.env.example](../.env.example), then run:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Open `http://localhost:3000`, create the initial Open WebUI account, select
`owl-agent`, and ask a question about the configured ontology. With the bundled
minimal ontology, try `What is the parent class of Computer?`.

The upstream chat model must support tool calling. The public `owl-agent` model
is our API endpoint; its underlying model is the `chat` alias configured in LiteLLM.
The default ontology is `ONTOLOGY_ID` from `.env`.

Open WebUI is configured to connect to `http://agent:8000/v1`. It stores chats and
its generated session secret in the `webui_data` volume. Automatic title, tag,
follow-up and autocomplete generation are disabled so background requests do not
trigger retrieval or web ingestion. Compose environment settings are reapplied at
startup rather than being overridden by saved connection settings.

## Request flow

1. Validate the text conversation and bind the request's ontology and workspace.
2. Connect to the MCP servers and discover the supported, allowlisted tools.
3. Retrieve an initial bounded graph context for the latest question.
4. Ask the chat model whether to inspect entities, navigate relationships, search
   documents, use HyDE or run web search. Execute its tool calls through MCP.
5. Supply structured observations and source IDs to the next model step.
6. Reserve the last model step for an answer without further tools. Include source
   references and a source list with IRIs / URLs and versions.

Web search writes extracted text into Qdrant. The agent must retrieve document
passages before citing those pages; search snippets and HyDE hypotheses do not
create source entries. If no supporting source was retrieved, the API returns an
insufficient-evidence response instead of the model's unsupported draft.

The source registry records actual tool results. It removes unknown citation IDs
and attaches the retrieved sources to the answer. This is provenance tracking,
not a proof that every model claim is semantically entailed by its citation.

## Limits and scope

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENT_MAX_STEPS` | 8 | Maximum chat-model calls, including the final answer |
| `AGENT_MAX_TOOL_CALLS` | 12 | Maximum executed tool calls, including initial retrieval |
| `AGENT_MAX_WEB_SEARCHES` | 1 | Web searches per user request; 0 disables ingestion through the agent |
| `AGENT_MAX_WEB_PAGES` | 3 | Maximum pages per web search |
| `AGENT_REQUEST_TIMEOUT` | 240 seconds | Total request deadline, including MCP connection setup |
| `AGENT_CALL_TIMEOUT` | 60 seconds | Model / MCP call timeout |
| `AGENT_TOOL_CHARS` | 16000 | Maximum serialized tool observation size |
| `AGENT_TOTAL_TOOL_CHARS` | 64000 | Total tool observation character budget |
| `AGENT_MAX_TOKENS` | 2000 | Maximum output tokens per chat-model call |
| `AGENT_RETRIEVAL_MODE` | hybrid | Initial ontology retrieval mode |

Per-call timeouts, character limits, token limits and retrieval mode can be set
for a host process. To override them in Docker, add the corresponding variables to
the agent's `environment` section in [compose.yaml](../compose.yaml). The common
step, tool, web and request limits are already forwarded from `.env` by Compose.

The model cannot override the selected `ontology_id` or `workspace` through tool
arguments. `workspace` is still a query filter, not per-user authorization. This
local deployment shares a default document workspace between WebUI conversations.
Graph state and MCP sessions are recreated per request; Open WebUI supplies chat
history. There is no server-side conversation checkpoint database yet.

## HTTP API

- `GET /health/live`: process liveness.
- `GET /health/ready`: MCP connectivity and tool discovery; makes no model calls.
- `GET /v1/models`: advertises `owl-agent`.
- `POST /v1/chat/completions`: runs the agent for a text conversation.

The `/v1` endpoints require a bearer key when `AGENT_API_KEY` is configured.
For local development it falls back to the proxy key; a separate `AGENT_API_KEY`
can be set without changing the upstream model credentials.

Example request body:

```json
{
  "model": "owl-agent",
  "messages": [{"role": "user", "content": "What is the parent of Computer?"}],
  "stream": false,
  "ontology_id": "demo",
  "workspace": "default"
}
```

Supported fields are `model`, plain-text `messages`, `stream`, `temperature`,
`n=1`, and the `ontology_id` / `workspace` extensions. The model defaults to
`owl-agent`. A conversation may contain up to 80 messages, 16000 characters per
message and 64000 input characters in total. Client system messages are treated
as untrusted user context. Images, audio and client-defined tool execution are
outside this API subset. Output token limits are controlled by the server.

A non-streaming response includes the standard assistant message plus `sources`,
`tool_trace` and `model_steps`. Sources contain retained RDF evidence or retrieved
document passages. The tool trace contains execution status, not hidden reasoning.
No aggregate token-usage counter is reported; provider usage remains in LiteLLM.

With `stream=true`, the API sends SSE keepalives while the agent works, then emits
the final grounded answer in chunks and terminates with `[DONE]`. Intermediate
drafts and provider tokens are not streamed. Stream failures are reported as an
in-band error frame; other failures use sanitized HTTP errors. Disconnecting a
stream cancels the request task and closes its MCP sessions.

PDF ingestion and Langfuse evaluation remain planned. Open WebUI file attachments
are not connected to the project's planned PDF knowledge library.

## Host development

Start the MCP servers and LiteLLM, then run:

```bash
uv run --env-file .env owl-agent --port 8000
```

Use the host MCP URLs from `.env.example`. For a lexical-only OWL server, set
`AGENT_RETRIEVAL_MODE=lexical`. An empty `KNOWLEDGE_MCP_URL` disables that connection.
See [Docker setup](docker.md) and the [MCP tools](mcp-tools.md) for service details.
