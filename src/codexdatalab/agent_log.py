from __future__ import annotations

import json
from typing import Any

from .utils import utc_now_iso
from .workspace import Workspace


def log_event(workspace: Workspace, event_type: str, payload: dict[str, Any]) -> None:
    path = workspace.meta_dir() / "agent_log.jsonl"
    entry = {
        "timestamp": utc_now_iso(),
        "type": event_type,
        "payload": payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
