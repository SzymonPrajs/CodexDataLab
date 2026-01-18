from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .settings import settings_dir

CODEX_HOME_DIRNAME = "codex"
AUTH_FILENAME = "auth.json"
DEFAULT_CODEX_HOME = Path.home() / ".codex"


@dataclass(frozen=True)
class CodexHomeSetup:
    path: Path
    auth_copied: bool
    auth_present: bool
    error: str | None


def codex_home_dir() -> Path:
    return settings_dir() / CODEX_HOME_DIRNAME


def ensure_codex_home() -> CodexHomeSetup:
    path = codex_home_dir()
    path.mkdir(parents=True, exist_ok=True)

    source_auth = DEFAULT_CODEX_HOME / AUTH_FILENAME
    target_auth = path / AUTH_FILENAME
    auth_copied = False
    error: str | None = None

    try:
        if not target_auth.exists() and source_auth.exists():
            shutil.copy2(source_auth, target_auth)
            auth_copied = True
    except OSError as exc:
        error = str(exc)

    return CodexHomeSetup(
        path=path,
        auth_copied=auth_copied,
        auth_present=target_auth.exists(),
        error=error,
    )
