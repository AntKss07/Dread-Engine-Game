"""Unified LLM client interface for local backends (Ollama, llama.cpp) and MockLLM."""

import json
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

import httpx

from dread.config import AppConfig


class BaseLLMClient(ABC):
    """Abstract base class for local LLM inference engines."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        """Synchronously generate text or structured JSON from the model."""

    @abstractmethod
    def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream generated tokens as they arrive."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend server is reachable and responsive."""


class OllamaClient(BaseLLMClient):
    """Client for Ollama local inference API."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:7b-instruct",
        timeout: float = 15.0,
        default_temperature: float = 0.7,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.default_temperature = default_temperature

    def is_available(self) -> bool:
        """Verify Ollama server is alive."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.endpoint}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        """Call Ollama /api/generate endpoint."""
        url = f"{self.endpoint}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }
        if system:
            payload["system"] = system

        if json_schema is not None:
            # Ollama accepts structured schema in format or "json"
            payload["format"] = json_schema

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

    def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream chunks from Ollama /api/generate."""
        url = f"{self.endpoint}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                    except Exception:
                        continue


class LlamaCppClient(BaseLLMClient):
    """Client for llama.cpp server API."""

    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8080",
        timeout: float = 15.0,
        default_temperature: float = 0.7,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.default_temperature = default_temperature

    def is_available(self) -> bool:
        """Verify llama.cpp server is reachable."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.endpoint}/health")
                return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        """Generate response via /completion endpoint."""
        url = f"{self.endpoint}/completion"
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload: dict[str, Any] = {
            "prompt": full_prompt,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "stream": False,
        }
        if json_schema:
            payload["json_schema"] = json_schema

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("content", "").strip()

    def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream completion from llama.cpp."""
        url = f"{self.endpoint}/completion"
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload: dict[str, Any] = {
            "prompt": full_prompt,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "stream": True,
        }

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.removeprefix("data: ")
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("content", "")
                        if token:
                            yield token
                    except Exception:
                        continue


class MockLLM(BaseLLMClient):
    """Deterministic Mock LLM for tests and offline headless verification."""

    def __init__(self, responses: list[str] | None = None):
        self.responses: list[str] = list(responses or [])
        self.call_history: list[dict[str, Any]] = []

    def set_next_responses(self, responses: list[str]) -> None:
        """Queue responses to return on subsequent calls."""
        self.responses.extend(responses)

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> str:
        self.call_history.append(
            {"prompt": prompt, "system": system, "schema": json_schema, "temp": temperature}
        )
        if self.responses:
            return self.responses.pop(0)

        # Default smart response if schema is requested (Parser)
        if json_schema and "verb" in json_schema.get("properties", {}):
            return json.dumps(
                {
                    "verb": "LOOK",
                    "target": None,
                    "instrument": None,
                    "confidence": 0.95,
                }
            )

        # Default narrator response
        return "You take a tentative step into the gloom. The damp stone floor chills your boots as shadows whisper around you."

    def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        text = self.generate(prompt, system=system, temperature=temperature)
        for word in text.split(" "):
            yield word + " "


def create_llm_client(config: AppConfig) -> BaseLLMClient:
    """Factory creating an LLM client based on application configuration."""
    if config.backend == "ollama":
        return OllamaClient(
            endpoint=config.endpoint,
            model=config.model,
            timeout=config.timeout_seconds,
            default_temperature=config.temperature,
        )
    elif config.backend == "llamacpp":
        return LlamaCppClient(
            endpoint=config.endpoint,
            timeout=config.timeout_seconds,
            default_temperature=config.temperature,
        )
    return MockLLM()
