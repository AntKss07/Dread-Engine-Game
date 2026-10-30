"""Configuration loader and models for Dread Engine."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class AppConfig(BaseModel):
    """Configuration settings for Dread Engine."""

    backend: Literal["ollama", "llamacpp"] = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"
    temperature: float = 0.7
    timeout_seconds: float = 15.0
    max_tokens: int = 300

    difficulty: Literal["story", "normal", "nightmare"] = "normal"
    default_scenario: str = "the_last_ofrenda"
    enable_hallucinations: bool = True

    voice_enabled: bool = False
    voice_model: str = "en_US-lessac-medium"

    save_dir: str = "saves"
    transcript_dir: str = "transcripts"


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    """Load configuration from a YAML file, falling back to defaults if not found."""
    path = Path(config_path)
    if not path.is_file():
        return AppConfig()

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return AppConfig(**data)
    except Exception:
        return AppConfig()
