from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import numeric_summary, schema_and_nulls
from .data_ops import preview_dataset
from .fetch_ops import fetch_url
from .plot_ops import create_plot_definition
from .settings import add_allowed_domain, load_settings
from .tool_harness import ToolHarness
from .workspace import load_workspace

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "codexdatalab"


@dataclass
class MCPServer:
    tool_harness: ToolHarness

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            _tool(
                "codexdatalab.list_datasets",
                "List datasets registered in the workspace.",
                {},
            ),
            _tool(
                "codexdatalab.import_dataset",
                "Import a local CSV/Parquet file into the workspace raw/ folder.",
                {
                    "path": {"type": "string"},
                    "link": {"type": "boolean", "default": False},
                    "force_copy": {"type": "boolean", "default": False},
                },
                required=["path"],
            ),
            _tool(
                "codexdatalab.preview_dataset",
                "Preview a dataset as a list of rows (truncated).",
                {
                    "dataset_id": {"type": "string"},
                    "max_rows": {"type": "integer", "default": 50},
                    "max_cols": {"type": "integer", "default": 12},
                },
                required=["dataset_id"],
            ),
            _tool(
                "codexdatalab.dataset_stats",
                "Compute schema + numeric summary for a dataset.",
                {"dataset_id": {"type": "string"}},
                required=["dataset_id"],
            ),
            _tool(
                "codexdatalab.create_plot",
                "Create a plot definition for the selected dataset.",
                {
                    "dataset_id": {"type": "string"},
                    "plot_type": {"type": "string"},
                    "x": {"type": ["string", "null"]},
                    "y": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "why": {"type": "string"},
                },
                required=["dataset_id", "plot_type"],
            ),
            _tool(
                "codexdatalab.record_answer",
                "Record a Q&A answer for traceability.",
                {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                    "dataset_ids": {"type": "array", "items": {"type": "string"}},
                    "artifact_ids": {"type": "array", "items": {"type": "string"}},
                },
                required=["question", "answer"],
            ),
            _tool(
                "codexdatalab.fetch_url",
                "Download a dataset URL into raw/ with provenance.",
                {
                    "url": {"type": "string"},
                    "display_name": {"type": "string"},
                    "format_hint": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                required=["url"],
            ),
            _tool(
                "codexdatalab.add_allowed_domain",
                "Add a domain to the allowed download list.",
                {"domain": {"type": "string"}},
                required=["domain"],
            ),
        ]

    def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "codexdatalab.list_datasets":
            return {"datasets": self.tool_harness.list_datasets()}
        if name == "codexdatalab.import_dataset":
            return self.tool_harness.import_dataset(
                arguments["path"],
                link=bool(arguments.get("link", False)),
                force_copy=bool(arguments.get("force_copy", False)),
            )
        if name == "codexdatalab.preview_dataset":
            df = preview_dataset(
                self.tool_harness.workspace,
                arguments["dataset_id"],
                max_rows=int(arguments.get("max_rows", 50)),
                max_cols=int(arguments.get("max_cols", 12)),
            )
            return {"columns": df.columns, "rows": df.to_dicts()}
        if name == "codexdatalab.dataset_stats":
            df = preview_dataset(
                self.tool_harness.workspace,
                arguments["dataset_id"],
                max_rows=1000,
                max_cols=100,
            )
            return {"schema": schema_and_nulls(df), "numeric": numeric_summary(df)}
        if name == "codexdatalab.create_plot":
            definition = create_plot_definition(
                self.tool_harness.workspace,
                dataset_id=arguments["dataset_id"],
                plot_type=arguments["plot_type"],
                x=arguments.get("x"),
                y=arguments.get("y"),
                category=arguments.get("category"),
                why=arguments.get("why", ""),
            )
            return {"plot": definition}
        if name == "codexdatalab.record_answer":
            return self.tool_harness.record_answer(
                question=arguments["question"],
                answer=arguments["answer"],
                dataset_ids=arguments.get("dataset_ids"),
                artifact_ids=arguments.get("artifact_ids"),
            )
        if name == "codexdatalab.fetch_url":
            result = fetch_url(
                self.tool_harness.workspace,
                arguments["url"],
                display_name=arguments.get("display_name"),
                format_hint=arguments.get("format_hint"),
                metadata=arguments.get("metadata"),
                prompt=None,
            )
            return {
                "dataset_id": result.dataset_id,
                "path": str(result.path),
                "receipt_path": str(result.receipt_path),
            }
        if name == "codexdatalab.add_allowed_domain":
            updated = add_allowed_domain(arguments["domain"])
            self.tool_harness.workspace.settings = updated
            return {"allowed_domains": updated.allowed_domains}
        raise ValueError(f"Unknown tool: {name}")


def serve_stdio(workspace_root: Path) -> None:
    settings = load_settings()
    workspace = load_workspace(workspace_root, settings)
    server = MCPServer(ToolHarness(workspace))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_request(payload, server)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def handle_request(payload: dict[str, Any], server: MCPServer) -> dict[str, Any] | None:
    method = payload.get("method")
    request_id = payload.get("id")
    if method is None:
        return None
    if method == "notifications/initialized":
        return None

    if request_id is None:
        return None

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": SERVER_NAME, "version": "0.1"},
                "capabilities": {"tools": {"listChanged": False}},
                "instructions": "CodexDataLab MCP server for dataset tools.",
            }
            return jsonrpc_result(request_id, result)
        if method == "tools/list":
            result = {"tools": server.list_tools(), "nextCursor": None}
            return jsonrpc_result(request_id, result)
        if method == "tools/call":
            params = payload.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not name:
                return jsonrpc_error(request_id, -32602, "Missing tool name.")
            try:
                output = server.handle_tool_call(name, arguments)
            except Exception as exc:
                return jsonrpc_result(
                    request_id,
                    {
                        "content": [{"type": "text", "text": f"Tool error: {exc}"}],
                        "isError": True,
                    },
                )
            return jsonrpc_result(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(output, indent=2, sort_keys=True)}
                    ],
                    "structuredContent": output,
                },
            )
        if method in {"resources/list", "resources/read", "resourceTemplates/list"}:
            empty = {"resources": [], "resourceTemplates": [], "nextCursor": None}
            if method == "resources/read":
                return jsonrpc_error(request_id, -32001, "No resources available.")
            if method == "resources/list":
                return jsonrpc_result(request_id, {"resources": [], "nextCursor": None})
            if method == "resourceTemplates/list":
                return jsonrpc_result(request_id, {"resourceTemplates": [], "nextCursor": None})
        return jsonrpc_error(request_id, -32601, f"Unknown method: {method}")
    except Exception as exc:
        return jsonrpc_error(request_id, -32603, f"Server error: {exc}")


def jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return {"name": name, "description": description, "inputSchema": schema}


def main() -> int:
    parser = argparse.ArgumentParser(description="CodexDataLab MCP stdio server.")
    parser.add_argument("--workspace", required=True, help="Workspace root to serve.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace).expanduser().resolve()
    serve_stdio(workspace_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
