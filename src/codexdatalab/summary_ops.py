from __future__ import annotations

from .workspace import Workspace


def generate_summary_markdown(workspace: Workspace) -> str:
    manifest = workspace.load_manifest()
    plots = workspace.load_plots().get("plots", {})
    answers = workspace.load_answers().get("answers", {})

    datasets = list(manifest.get("datasets", {}).values())
    cleaned = [ds for ds in datasets if ds.get("kind") == "cleaned"]
    raw = [ds for ds in datasets if ds.get("kind") == "raw"]

    lines = [
        "# Workspace Summary",
        "",
        "## Datasets",
        f"- Raw datasets: {len(raw)}",
        f"- Cleaned datasets: {len(cleaned)}",
    ]
    if datasets:
        lines.append("")
        lines.append("### Dataset List")
        for ds in datasets:
            name = ds.get("name") or ds.get("id")
            lines.append(f"- {ds.get('id')} ({ds.get('kind')}) — {name}")

    lines.extend(
        [
            "",
            "## Plots",
            f"- Saved plots: {len(plots)}",
        ]
    )
    if plots:
        lines.append("")
        lines.append("### Plot List")
        for plot_id, plot in plots.items():
            lines.append(f"- {plot_id} — {plot.get('why') or 'No description'}")

    lines.extend(
        [
            "",
            "## Q&A",
            f"- Recorded answers: {len(answers)}",
        ]
    )
    if answers:
        lines.append("")
        lines.append("### Recent Answers")
        for answer_id, answer in list(answers.items())[-5:]:
            lines.append(f"- {answer_id}: {answer.get('question')}")

    return "\n".join(lines) + "\n"

