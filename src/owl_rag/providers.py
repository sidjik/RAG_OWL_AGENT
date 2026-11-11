"""Small provider adapters using the LiteLLM HTTP interface."""

from typing import Protocol

import httpx
import numpy as np


class Generator(Protocol):
    def generate(self, system: str, prompt: str) -> str: ...


class LiteLLMGenerator:
    def __init__(self, base_url: str, model: str, api_key: str = "", client=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=60)
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def generate(self, system: str, prompt: str) -> str:
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("HyDE model returned an empty or oversized document")
        return text.strip()


class LiteLLMEncoder:
    def __init__(self, base_url: str, model: str, api_key: str = "", client=None):
        self.base_url = base_url.rstrip("/")
        # Include the configured endpoint: identical aliases can denote different models.
        # Change the model alias when changing model versions behind the proxy.
        self.model_id = f"{self.base_url}::{model}"
        self.model = model
        self.client = client or httpx.Client(timeout=60)
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def encode(self, texts: list[str]) -> np.ndarray:
        response = self.client.post(
            f"{self.base_url}/embeddings",
            headers=self.headers,
            json={"model": self.model, "input": texts, "encoding_format": "float"},
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        if [item["index"] for item in data] != list(range(len(texts))):
            raise ValueError("Embedding response indices do not match the input")
        return np.asarray([item["embedding"] for item in data], dtype=float)
