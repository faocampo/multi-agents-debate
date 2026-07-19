from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr = SecretStr("ollama")
    llm_model: str = "qwen2.5:32b"
    llm_timeout_seconds: float = Field(default=120, ge=1, le=1800)
    llm_orchestrator_temperature: float = Field(default=0.9, ge=0, le=2)
    llm_expert_temperature: float = Field(default=0.7, ge=0, le=2)
    llm_debate_temperature: float = Field(default=0.6, ge=0, le=2)
    llm_advocate_temperature: float = Field(default=0.8, ge=0, le=2)
    llm_merge_temperature: float = Field(default=0.4, ge=0, le=2)
    cors_origins: str = "http://localhost:5173"
    roles_file: Path = Field(default=Path("data/roles.json"))

    @field_validator("llm_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute http or https URL")
        return normalized

    @field_validator("llm_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("must contain at least one origin")
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"contains an invalid origin: {origin}")
        return ",".join(origins)

    @property
    def cors_origin_list(self) -> list[str]:
        return self.cors_origins.split(",")
