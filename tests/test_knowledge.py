import httpx
import numpy as np
import pytest

from owl_rag.knowledge import KnowledgeService, chunks
from owl_rag.providers import LiteLLMEncoder, LiteLLMGenerator
from owl_rag.vector_store import VectorRecord
from owl_rag.web_search import TavilySearch, WebPage, canonical_url

TEXT = "Vector databases index embedding vectors for semantic retrieval. " * 40


class Web:
    def search(self, query, max_results):
        return [
            WebPage("https://example.org/article#section", "Vectors", "snippet", TEXT),
            WebPage("https://example.org/article", "Duplicate", "snippet", TEXT),
            WebPage("https://example.org/empty", "No extraction", "snippet", None),
            WebPage("http://127.0.0.1/private", "Local", "snippet", TEXT),
        ][:max_results]


class Generator:
    def generate(self, system, prompt):
        assert "hypothetical" in system
        return "Vector databases store embedding vectors for semantic similarity search."


def test_web_ingestion_metadata_dedup_and_hyde_never_writes(store):
    service = KnowledgeService(store, Generator(), Web())
    result = service.web_search_and_index("how embeddings work")
    assert result["indexed_documents"] == 1
    assert len(result["results"]) == 3  # Canonical duplicate is ignored.
    assert result["results"][1]["status"] == "skipped"
    count = store.client.count(store.collection, exact=True).count
    assert count > 1
    service.web_search_and_index("how embeddings work")
    assert store.client.count(store.collection, exact=True).count == count
    hyde = service.hyde_search("meaning representation")
    assert hyde["hypothesis_is_evidence"] is False
    assert hyde["hits"]
    hit = hyde["hits"][0]
    assert hit["url"] == "https://example.org/article"
    assert hit["source_type"] == "web"
    assert hit["trust"] == "external_unverified"
    assert hit["version"].startswith("sha256:") and hit["retrieved_at"]
    assert hit["text"] != hyde["hypothesis"]
    assert store.client.count(store.collection, exact=True).count == count
    assert service.search("embedding", workspace="another")["hits"] == []
    assert service.search("embedding", source_type="pdf")["hits"] == []


def test_updated_url_removes_old_tail_and_preserves_other_workspaces(store):
    service = KnowledgeService(store)
    url = "https://example.org/doc"
    old = service.index_web_page(url, "Old", TEXT, "q", "default")
    service.index_web_page(url, "Separate", TEXT, "q", "other")
    new_text = "Graph vertices and edges support relationship traversal. " * 3
    new = service.index_web_page(url, "New", new_text, "q", "default")
    assert old["version"] != new["version"]
    current = store.search("graph", {"workspace": "default"}, limit=100)
    assert len(current) == 1
    assert current[0]["text"] == new_text.strip()
    assert current[0]["version"] == new["version"]
    assert len(store.search("vector", {"workspace": "other"}, limit=100)) > 1


def test_missing_config_empty_collection_and_validation(store):
    service = KnowledgeService(store)
    assert service.search("something")["hits"] == []
    with pytest.raises(ValueError, match="HYDE_MODEL"):
        service.hyde_search("q")
    with pytest.raises(ValueError, match="TAVILY"):
        service.web_search_and_index("q")
    with pytest.raises(ValueError):
        service.search("q", workspace="../another")
    with pytest.raises(ValueError):
        service.index_web_page("https://example.org", "", "short", "q", "default")
    with pytest.raises(ValueError):
        store.search("q", {})
    with pytest.raises(ValueError):
        store.search("q", {"workspace": "default"}, limit=101)
    with pytest.raises(ValueError):
        chunks("q", overlap=1200)


def test_invalid_hyde_request_does_not_call_model(store):
    class Generator:
        def generate(self, system, prompt):
            raise AssertionError("Invalid parameters must be rejected before a paid model call")

    service = KnowledgeService(store, Generator())
    with pytest.raises(ValueError, match="limit"):
        service.hyde_search("question", limit=0)
    with pytest.raises(ValueError, match="source_type"):
        service.hyde_search("question", source_type="invalid")


def test_model_space_and_invalid_embedding_are_rejected(store):
    store.upsert([VectorRecord("first", "vector", {"workspace": "default"})])
    store.encoder.encode = lambda _: np.zeros((1, 4))
    with pytest.raises(ValueError, match="zero vector"):
        store.search("q", {"workspace": "default"})


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/private",
        "http://localhost/x",
        "http://192.168.1.1/",
        "https://a:b@example.org/",
        "http://host/",
    ],
)
def test_nonpublic_urls(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_provider_http_contracts():
    def handler(request):
        import json

        body = json.loads(request.content)
        if request.url.path == "/v1/embeddings":
            assert body["input"] == ["a", "b"]
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [0, 1]},
                        {"index": 0, "embedding": [1, 0]},
                    ]
                },
            )
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(200, json={"choices": [{"message": {"content": "hypothesis"}}]})
        assert request.url.host == "api.tavily.com"
        assert body["include_answer"] is False and body["include_raw_content"] == "text"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/",
                        "title": "T",
                        "content": "snippet",
                        "raw_content": TEXT,
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert LiteLLMEncoder("http://test/v1", "embed", client=client).encode(
            ["a", "b"]
        ).tolist() == [[1, 0], [0, 1]]
        assert LiteLLMGenerator("http://test/v1", "chat", client=client).generate("s", "p") == (
            "hypothesis"
        )
        assert TavilySearch("key", client=client).search("q", 1)[0].text == TEXT
