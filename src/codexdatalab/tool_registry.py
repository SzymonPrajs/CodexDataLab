from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .analysis import numeric_summary, schema_and_nulls
from .data_ops import preview_dataset
from .plot_ops import create_plot_definition
from .tool_harness import ToolHarness
from .utils import utc_now_iso


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    effects: list[str]


@dataclass(frozen=True)
class ToolCallResult:
    ok: bool
    result: dict[str, Any] | None
    error: str | None
    effects: list[str]


class ToolRegistry:
    def __init__(self, tool_harness: ToolHarness) -> None:
        self._tool_harness = tool_harness
        self._tools = {tool.name: tool for tool in self._build_tools()}

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        tool = self.get(name)
        if tool is None:
            return ToolCallResult(False, None, f"Unknown tool: {name}", [])

        errors = _validate_schema(tool.input_schema, arguments)
        if errors:
            return ToolCallResult(False, None, "; ".join(errors), tool.effects)

        try:
            result = tool.handler(arguments)
        except Exception as exc:
            return ToolCallResult(False, None, f"{exc}", tool.effects)
        return ToolCallResult(True, result, None, tool.effects)

    def format_for_prompt(self) -> str:
        lines = ["Available tools (name, description, input schema):"]
        for tool in self.list_tools():
            lines.append(f"- {tool.name}: {tool.description}")
            lines.append(f"  input_schema: {tool.input_schema}")
        return "\n".join(lines)

    def _build_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="codexdatalab.list_datasets",
                description="List datasets registered in the workspace.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=lambda _args: {"datasets": self._tool_harness.list_datasets()},
                effects=[],
            ),
            ToolSpec(
                name="codexdatalab.import_dataset",
                description="Import a local CSV/Parquet file into raw/.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "link": {"type": "boolean"},
                        "force_copy": {"type": "boolean"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=lambda args: self._tool_harness.import_dataset(
                    args["path"],
                    link=bool(args.get("link", False)),
                    force_copy=bool(args.get("force_copy", False)),
                ),
                effects=["datasets"],
            ),
            ToolSpec(
                name="codexdatalab.preview_dataset",
                description="Preview a dataset (columns + rows).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "max_rows": {"type": "integer"},
                        "max_cols": {"type": "integer"},
                    },
                    "required": ["dataset_id"],
                    "additionalProperties": False,
                },
                handler=self._preview_dataset,
                effects=[],
            ),
            ToolSpec(
                name="codexdatalab.dataset_stats",
                description="Compute schema + numeric summary for a dataset.",
                input_schema={
                    "type": "object",
                    "properties": {"dataset_id": {"type": "string"}},
                    "required": ["dataset_id"],
                    "additionalProperties": False,
                },
                handler=self._dataset_stats,
                effects=[],
            ),
            ToolSpec(
                name="codexdatalab.create_plot",
                description="Create a plot definition for a dataset.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "plot_type": {"type": "string"},
                        "x": {"type": ["string", "null"]},
                        "y": {"type": ["string", "null"]},
                        "category": {"type": ["string", "null"]},
                        "why": {"type": "string"},
                    },
                    "required": ["dataset_id", "plot_type"],
                    "additionalProperties": False,
                },
                handler=self._create_plot,
                effects=["plots"],
            ),
            ToolSpec(
                name="codexdatalab.record_answer",
                description="Record a Q&A answer for traceability.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                        "dataset_ids": {"type": "array", "items": {"type": "string"}},
                        "artifact_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["question", "answer"],
                    "additionalProperties": False,
                },
                handler=lambda args: self._tool_harness.record_answer(
                    question=args["question"],
                    answer=args["answer"],
                    dataset_ids=args.get("dataset_ids"),
                    artifact_ids=args.get("artifact_ids"),
                ),
                effects=["answers"],
            ),
            ToolSpec(
                name="codexdatalab.fetch_url",
                description="Download a dataset URL into raw/ with provenance.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "display_name": {"type": "string"},
                        "format_hint": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
                handler=lambda args: self._tool_harness.fetch_url(
                    args["url"],
                    display_name=args.get("display_name"),
                    format_hint=args.get("format_hint"),
                    metadata=args.get("metadata"),
                ),
                effects=["datasets"],
            ),
            ToolSpec(
                name="codexdatalab.add_allowed_domain",
                description="Add a domain to the allowed download list.",
                input_schema={
                    "type": "object",
                    "properties": {"domain": {"type": "string"}},
                    "required": ["domain"],
                    "additionalProperties": False,
                },
                handler=lambda args: self._tool_harness.add_allowed_domain(args["domain"]),
                effects=["settings"],
            ),
            ToolSpec(
                name="codexdatalab.now",
                description="Return current server timestamp.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                handler=lambda _args: {"timestamp": utc_now_iso()},
                effects=[],
            ),
        ]

    def _preview_dataset(self, args: dict[str, Any]) -> dict[str, Any]:
        df = preview_dataset(
            self._tool_harness.workspace,
            args["dataset_id"],
            max_rows=int(args.get("max_rows", 50)),
            max_cols=int(args.get("max_cols", 12)),
        )
        return {"columns": df.columns, "rows": df.to_dicts()}

    def _dataset_stats(self, args: dict[str, Any]) -> dict[str, Any]:
        df = preview_dataset(
            self._tool_harness.workspace,
            args["dataset_id"],
            max_rows=1000,
            max_cols=100,
        )
        return {"schema": schema_and_nulls(df), "numeric": numeric_summary(df)}

    def _create_plot(self, args: dict[str, Any]) -> dict[str, Any]:
        definition = create_plot_definition(
            self._tool_harness.workspace,
            dataset_id=args["dataset_id"],
            plot_type=args["plot_type"],
            x=args.get("x"),
            y=args.get("y"),
            category=args.get("category"),
            why=args.get("why", ""),
        )
        return {"plot": definition}


def _validate_schema(schema: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if schema.get("type") != "object":
        return errors
    if not isinstance(arguments, dict):
        return ["Arguments must be an object."]
    required = schema.get("required", [])
    for key in required:
        if key not in arguments:
            errors.append(f"Missing required field: {key}")
    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)
    for key, value in arguments.items():
        if key not in properties:
            if not additional:
                errors.append(f"Unexpected field: {key}")
            continue
        expected = properties[key].get("type")
        if expected is None:
            continue
        if not _matches_type(value, expected):
            errors.append(f"Field {key} must be of type {expected}")
    return errors


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return True
