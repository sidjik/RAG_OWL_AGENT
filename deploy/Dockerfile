FROM python:3.12-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
RUN pip install --no-cache-dir uv==0.11.2
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

EXPOSE 8001 8002
CMD ["owl-mcp", "--ontology", "demo=/app/ontologies/minimal.owl", "--transport", "streamable-http", "--host", "0.0.0.0"]
