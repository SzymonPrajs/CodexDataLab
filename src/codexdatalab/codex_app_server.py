from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .agent_log import log_event
from .codex_home import ensure_codex_home
from .skill_store import SKILL_NAME, ensure_skill_file
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
        self._skill_path: Path | None = None

    def start(self) -> bool:
        if self._process:
            return True
        codex_home = ensure_codex_home()
        if codex_home.error:
            log_event(
                self.workspace,
                "codex_home_error",
                {"path": str(codex_home.path), "error": codex_home.error},
            )
        else:
            log_event(
                self.workspace,
                "codex_home_ready",
                {
                    "path": str(codex_home.path),
                    "auth_present": codex_home.auth_present,
                    "auth_copied": codex_home.auth_copied,
                },
            )
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home.path)
        try:
            self._process = subprocess.Popen(
                ["codex", "app-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                env=env,
            )
        except FileNotFoundError:
            return False

        if not self._process.stdin or not self._process.stdout:
            return False

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        self._initialize()
        return True

    def stop(self) -> None:
        if not self._process:
            return
        self._process.terminate()
        self._process = None

    def send_message(self, text: str) -> TurnResult:
        return self._send_turn(
            [{"type": "text", "text": text}],
            output_schema=None,
        )

    def run_tool_loop(
        self,
        user_message: str,
        *,
        tool_context: str,
        execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_steps: int = 6,
    ) -> str:
        self._ensure_thread()
        if self._thread_id is None:
            raise RuntimeError("Codex thread not initialized.")

        self._ensure_skill_file(TOOL_PROTOCOL)
        log_event(self.workspace, "user_message", {"text": user_message})

        prompt = f"{tool_context}\nUser: {user_message}"
        input_items = self._build_input_items(prompt, include_skill=True)

        for _ in range(max_steps):
            turn = self._send_turn(input_items, output_schema=TOOL_RESPONSE_SCHEMA)
            raw = turn.text.strip()
            log_event(self.workspace, "codex_response_raw", {"text": raw})
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                error = "Codex response was not valid JSON."
                log_event(self.workspace, "tool_protocol_error", {"error": error, "text": raw})
                return error

            if payload.get("type") == "final":
                message = payload.get("message", "")
                log_event(self.workspace, "codex_final", {"message": message})
                return message or "No response."
            if payload.get("type") != "tool_call":
                error = "Invalid response type; expected tool_call or final."
                log_event(self.workspace, "tool_protocol_error", {"error": error, "payload": payload})
                return error

            tool_name = payload.get("tool")
            arguments = payload.get("arguments")
            if not tool_name or not isinstance(arguments, dict):
                error = "Tool call missing tool name or arguments."
                log_event(self.workspace, "tool_protocol_error", {"error": error, "payload": payload})
                return error

            log_event(
                self.workspace,
                "tool_call",
                {"tool": tool_name, "arguments": arguments},
            )
            result = execute_tool(tool_name, arguments)
            log_event(self.workspace, "tool_result", result)

            tool_result_payload = {
                "type": "tool_result",
                "tool": tool_name,
                "ok": result.get("ok"),
                "result": result.get("result"),
                "error": result.get("error"),
            }
            input_items = [{"type": "text", "text": json.dumps(tool_result_payload)}]

        return "Tool loop exceeded max steps."

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

    def _ensure_skill_file(self, tool_protocol: str) -> None:
        if self._skill_path is None:
            self._skill_path = ensure_skill_file(tool_protocol)

    def _build_input_items(self, text: str, *, include_skill: bool) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = [{"type": "text", "text": text}]
        if include_skill and self._skill_path is not None:
            items.append(
                {
                    "type": "skill",
                    "name": SKILL_NAME,
                    "path": str(self._skill_path),
                }
            )
        return items

    def _send_turn(
        self, input_items: list[dict[str, Any]], *, output_schema: dict[str, Any] | None
    ) -> TurnResult:
        self._ensure_thread()
        if self._thread_id is None:
            raise RuntimeError("Codex thread not initialized.")

        self._active_turn_text = []
        self._active_turn_done.clear()
        params: dict[str, Any] = {
            "threadId": self._thread_id,
            "input": input_items,
        }
        if output_schema is not None:
            params["outputSchema"] = output_schema

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
        "You are Codex for CodexDataLab. Use the CodexDataLab tool protocol to operate on "
        "datasets and results in this workspace. Prefer tools over shell commands. "
        "For web data discovery, use the web search tool to find dataset URLs, then call "
        "codexdatalab.fetch_url to download into raw/. If a domain is blocked, ask the user "
        "and then call codexdatalab.add_allowed_domain. "
        "Use recipes for lightweight computed columns, transforms for heavier cleaning, "
        "and export reports via codexdatalab.export_report when requested. "
        "Respect the active project (codexdatalab.set_active_project). "
        f"Workspace root: {workspace_root}."
    )


TOOL_PROTOCOL = (
    "Respond with a single JSON object. Use type=tool_call to invoke tools, "
    "and type=final with a message when done. Do not include extra text."
)

TOOL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["tool_call", "final"]},
        "tool": {"type": "string"},
        "arguments": {"type": "object"},
        "message": {"type": "string"},
    },
    "required": ["type"],
    "additionalProperties": False,
}
