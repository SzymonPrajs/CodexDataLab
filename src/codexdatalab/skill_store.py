from __future__ import annotations

from pathlib import Path

from .codex_home import codex_home_dir

SKILL_NAME = "codexdatalab-tools"


def skill_path() -> Path:
    return codex_home_dir() / "skills" / SKILL_NAME / "SKILL.md"


def ensure_skill_file(tool_protocol: str) -> Path:
    path = skill_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _skill_template(tool_protocol)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
    return path


def _skill_template(tool_protocol: str) -> str:
    return (
        "---\n"
        f"name: {SKILL_NAME}\n"
        "description: Use CodexDataLab tools via the JSON tool-call protocol.\n"
        "---\n\n"
        "# CodexDataLab Tool Protocol\n\n"
        "You can control CodexDataLab by emitting JSON tool calls. The client will parse\n"
        "your response. Always reply with a single JSON object and no extra text.\n\n"
        "Response types:\n"
        "- Tool call: {\"type\":\"tool_call\",\"tool\":\"<name>\",\"arguments\":{...}}\n"
        "- Final response: {\"type\":\"final\",\"message\":\"...\"}\n\n"
        "If a tool call fails, you will receive a tool_result payload and should fix the\n"
        "arguments or call a different tool.\n\n"
        "Tool results are sent as input JSON with this shape:\n"
        "{\"type\":\"tool_result\",\"tool\":\"<name>\",\"ok\":true|false,"
        "\"result\":{...},\"error\":\"...\"}\n\n"
        "Use the tool list provided in the prompt for names and schemas.\n\n"
        "Protocol details:\n"
        f"{tool_protocol}\n"
    )
