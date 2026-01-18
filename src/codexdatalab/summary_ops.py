from __future__ import annotations

from .workspace import Workspace


def generate_summary_markdown(workspace: Workspace) -> str:
    manifest = workspace.load_manifest()
    plots = workspace.load_plots().get("plots", {})
    answers = workspace.load_answers().get("answers", {})
    project_id = workspace.project_id()

    datasets = [
        ds
        for ds in manifest.get("datasets", {}).values()
        if not ds.get("projects") or project_id in ds.get("projects", [])
    ]
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

    project_plots = {
        plot_id: plot
        for plot_id, plot in plots.items()
        if not plot.get("project") or plot.get("project") == project_id
    }
    lines.extend(
        [
            "",
            "## Plots",
            f"- Saved plots: {len(project_plots)}",
        ]
    )
    if project_plots:
        lines.append("")
        lines.append("### Plot List")
        for plot_id, plot in project_plots.items():
            lines.append(f"- {plot_id} — {plot.get('why') or 'No description'}")

    project_answers = {
        answer_id: answer
        for answer_id, answer in answers.items()
        if not answer.get("project") or answer.get("project") == project_id
    }
    lines.extend(
        [
            "",
            "## Q&A",
            f"- Recorded answers: {len(project_answers)}",
        ]
    )
    if project_answers:
        lines.append("")
        lines.append("### Recent Answers")
        for answer_id, answer in list(project_answers.items())[-5:]:
            lines.append(f"- {answer_id}: {answer.get('question')}")

    return "\n".join(lines) + "\n"
