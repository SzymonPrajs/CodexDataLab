from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .workspace import Workspace


@dataclass
class TurnResult:
    text: str
    turn_id: str


class CodexAppServerClient:
    def __init__(
        self,
        workspace: Workspace,
        *,
        client_name: str = "codexdatalab",
        client_title: str = "CodexDataLab",
        client_version: str = "0.1.0",
    ) -> None:
        self.workspace = workspace
        self.client_name = client_name
        self.client_title = client_title
        self.client_version = client_version
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._responses: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._active_turn_id: str | None = None
        self._active_turn_text: list[str] = []
        self._active_turn_done = threading.Event()
        self._pending_turn = False
        self._thread_id: str | None = None

    def start(self) -> bool:
        if self._process:
            return True
        try:
            self._process = subprocess.Popen(
                ["codex", "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
            )
        except FileNotFoundError:
            return False

        if not self._process.stdin or not self._process.stdout:
            return False

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        self._initialize()
        self._ensure_mcp_server()
        return True

    def stop(self) -> None:
        if not self._process:
            return
        self._process.terminate()
        self._process = None

    def send_message(self, text: str) -> TurnResult:
        self._ensure_thread()
        if self._thread_id is None:
            raise RuntimeError("Codex thread not initialized.")

        self._active_turn_text = []
        self._active_turn_done.clear()
        params = {
            "threadId": self._thread_id,
            "input": [{"type": "text", "text": text}],
        }
        self._pending_turn = True
        self._active_turn_id = None
        response = self._send_request("turn/start", params)
        turn = response.get("turn", {})
        turn_id = turn.get("id", "")
        if not turn_id:
            raise RuntimeError("Codex did not return a turn id.")

        self._active_turn_id = turn_id
        self._pending_turn = False
        if not self._active_turn_done.wait(timeout=120):
            raise RuntimeError("Codex response timed out.")
        message = "".join(self._active_turn_text).strip()
        return TurnResult(text=message, turn_id=turn_id)

    def _initialize(self) -> None:
        params = {
            "clientInfo": {
                "name": self.client_name,
                "title": self.client_title,
                "version": self.client_version,
            }
        }
        self._send_request("initialize", params)
        self._send_notification("initialized", {})

    def _ensure_thread(self) -> None:
        if self._thread_id:
            return
        state = self.workspace.load_state()
        stored_thread = state.get("ui", {}).get("codex_thread_id")
        if stored_thread:
            try:
                response = self._send_request("thread/resume", {"threadId": stored_thread})
                self._thread_id = response.get("thread", {}).get("id")
            except Exception:
                self._thread_id = None

        if not self._thread_id:
            response = self._send_request(
                "thread/start",
                {
                    "cwd": str(self.workspace.root),
                    "developerInstructions": _default_instructions(self.workspace.root),
                    "config": {"web_search": "live"},
                },
            )
            self._thread_id = response.get("thread", {}).get("id")

        if self._thread_id:
            self.workspace.update_ui_state("codex_thread_id", self._thread_id)

    def _ensure_mcp_server(self) -> None:
        command = sys.executable
        args = ["-m", "codexdatalab.mcp_server", "--workspace", str(self.workspace.root)]
        value = {
            "command": command,
            "args": args,
            "cwd": str(self.workspace.root),
            "enabled": True,
        }
        params = {
            "keyPath": "mcp_servers.codexdatalab",
            "value": value,
            "mergeStrategy": "upsert",
        }
        try:
            self._send_request("config/value/write", params)
            self._send_request("config/mcpServer/reload", {})
        except Exception:
            return

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_request_id()
        message = {"id": request_id, "method": method, "params": params}
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._lock:
            self._responses[request_id] = response_queue
        self._write(message)
        response = response_queue.get(timeout=60)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response.get("result", {})

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def _write(self, payload: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("Codex app-server process not running.")
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _next_request_id(self) -> int:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            return request_id

    def _reader_loop(self) -> None:
        if not self._process or not self._process.stdout:
            return
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "id" in payload and "result" in payload:
                response_queue = self._responses.pop(payload["id"], None)
                if response_queue:
                    response_queue.put(payload)
                continue
            if "id" in payload and "error" in payload:
                response_queue = self._responses.pop(payload["id"], None)
                if response_queue:
                    response_queue.put(payload)
                continue
            if "id" in payload and "method" in payload:
                self._handle_server_request(payload)
                continue
            if "method" in payload:
                self._handle_notification(payload)

    def _handle_notification(self, payload: dict[str, Any]) -> None:
        method = payload.get("method")
        params = payload.get("params", {})
        if method == "turn/started":
            turn = params.get("turn", {})
            if self._pending_turn and not self._active_turn_id:
                self._active_turn_id = turn.get("id")
        elif method == "item/agentMessage/delta":
            if self._active_turn_id or self._pending_turn:
                delta = params.get("delta", "")
                self._active_turn_text.append(delta)
        elif method == "item/completed":
            item = params.get("item", {})
            if item.get("type") == "agentMessage" and item.get("text"):
                self._active_turn_text = [item["text"]]
        elif method == "turn/completed":
            turn = params.get("turn", {})
            if self._pending_turn or turn.get("id") == self._active_turn_id:
                self._active_turn_done.set()

    def _handle_server_request(self, payload: dict[str, Any]) -> None:
        method = payload.get("method")
        request_id = payload.get("id")
        if not request_id:
            return
        if method == "item/commandExecution/requestApproval":
            response = {"id": request_id, "result": {"decision": "decline"}}
            self._write(response)
            return
        if method == "item/fileChange/requestApproval":
            response = {"id": request_id, "result": {"decision": "decline"}}
            self._write(response)
            return
        response = {"id": request_id, "result": {}}
        self._write(response)


def _default_instructions(workspace_root: Path) -> str:
    return (
        "You are Codex for CodexDataLab. Use the codexdatalab MCP tools to operate on "
        "datasets and results in this workspace. Prefer MCP tools over shell commands. "
        "For web data discovery, use the web search tool to find dataset URLs, then call "
        "codexdatalab.fetch_url to download into raw/. If a domain is blocked, call "
        "codexdatalab.add_allowed_domain after asking the user for confirmation. "
        f"Workspace root: {workspace_root}."
    )
