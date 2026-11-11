"""Web search adapter. Only extracted page text is eligible for indexing."""

import ipaddress
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx


@dataclass(frozen=True)
class WebPage:
    url: str
    title: str
    snippet: str
    text: str | None


class WebSearch(Protocol):
    def search(self, query: str, max_results: int) -> list[WebPage]: ...


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise ValueError("Expected a public HTTP(S) source URL")
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("Local source URLs are unsupported")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("Expected a public hostname") from None
    else:
        if not address.is_global:
            raise ValueError("Private source URLs are unsupported")
    # We do not fetch these URLs ourselves: Tavily supplies the extracted text.
    # Query strings can distinguish different documents; fragments cannot.
    port = parsed.port
    authority = f"[{host}]" if ":" in host else host
    if port and not (
        parsed.scheme == "https" and port == 443 or parsed.scheme == "http" and port == 80
    ):
        authority += f":{port}"
    return urlunsplit((parsed.scheme.lower(), authority, parsed.path or "/", parsed.query, ""))


class TavilySearch:
    def __init__(self, api_key: str, client=None):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=60)

    def search(self, query: str, max_results: int) -> list[WebPage]:
        response = self.client.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
                "include_answer": False,
                "include_raw_content": "text",
            },
        )
        response.raise_for_status()
        return [
            WebPage(
                url=item["url"],
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                text=item.get("raw_content"),
            )
            for item in response.json().get("results", [])[:max_results]
        ]
