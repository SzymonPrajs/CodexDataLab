from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SETTINGS_DIRNAME = ".codexdatalab"
SETTINGS_FILENAME = "settings.json"
SCHEMA_VERSION = 0
DEFAULT_MAX_COPY_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_ALLOWED_DOMAINS: list[str] = []


@dataclass(frozen=True)
class Settings:
    max_copy_bytes: int
    offline_mode: bool
    prompt_on_large_file: bool
    allowed_domains: list[str]
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        return cls(
            max_copy_bytes=int(data.get("max_copy_bytes", DEFAULT_MAX_COPY_BYTES)),
            offline_mode=bool(data.get("offline_mode", False)),
            prompt_on_large_file=bool(data.get("prompt_on_large_file", True)),
            allowed_domains=list(data.get("allowed_domains", DEFAULT_ALLOWED_DOMAINS)),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "max_copy_bytes": self.max_copy_bytes,
            "offline_mode": self.offline_mode,
            "prompt_on_large_file": self.prompt_on_large_file,
            "allowed_domains": self.allowed_domains,
        }


def settings_dir() -> Path:
    return Path.home() / SETTINGS_DIRNAME


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def load_settings() -> Settings:
    path = settings_path()
    if not path.exists():
        settings = Settings(
            max_copy_bytes=DEFAULT_MAX_COPY_BYTES,
            offline_mode=False,
            prompt_on_large_file=True,
            allowed_domains=DEFAULT_ALLOWED_DOMAINS,
        )
        save_settings(settings)
        return settings

    data = json.loads(path.read_text())
    settings = Settings.from_dict(data)

    if settings.to_dict() != data:
        save_settings(settings)

    return settings


def save_settings(settings: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n")
