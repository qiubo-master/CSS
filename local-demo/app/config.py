from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    llm_mode: str = os.getenv("LLM_MODE", "auto")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:1.7b-q4_K_M")
    embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
    vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:4b-instruct-q4_K_M")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    data_dir: Path = Path(os.getenv("DEMO_DATA_DIR", str(ROOT / "data"))).resolve()
    foundation_base_url: str = os.getenv("FOUNDATION_BASE_URL", "http://127.0.0.1:6008")
    foundation_app_id: str = os.getenv("FOUNDATION_APP_ID", "customer-service")
    foundation_api_key: str = os.getenv("FOUNDATION_API_KEY", "")
    foundation_timeout: float = float(os.getenv("FOUNDATION_TIMEOUT_SECONDS", "180"))


settings = Settings()
