from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .summary_ops import generate_summary_markdown
from .utils import generate_id, utc_now_iso
from .workspace import Workspace


def export_report_notebook(workspace: Workspace, *, title: str | None = None) -> dict[str, Any]:
    report_id = generate_id("rep")
    report_title = title or "CodexDataLab Report"
    project_id = workspace.project_id()

    manifest = workspace.load_manifest()
    plots = workspace.load_plots().get("plots", {})
    answers = workspace.load_answers().get("answers", {})

    datasets = [
        ds
        for ds in manifest.get("datasets", {}).values()
        if not ds.get("projects") or project_id in ds.get("projects", [])
    ]
    project_plots = {
        plot_id: plot
        for plot_id, plot in plots.items()
        if not plot.get("project") or plot.get("project") == project_id
    }
    project_answers = {
        answer_id: answer
        for answer_id, answer in answers.items()
        if not answer.get("project") or answer.get("project") == project_id
    }

    cells: list[dict[str, Any]] = []
    cells.append(
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [f"# {report_title}\n", f"\nGenerated: {utc_now_iso()}\n"],
        }
    )

    summary = generate_summary_markdown(workspace)
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [summary]})

    if datasets:
        lines = ["## Datasets\n"]
        for ds in datasets:
            lines.append(f"- {ds.get('id')} ({ds.get('kind')}) — {ds.get('name')}\n")
        cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})
        for ds in datasets:
            rel_path = ds.get("paths_by_project", {}).get(project_id, ds.get("path"))
            if not rel_path:
                continue
            code = [
                "import polars as pl\n",
                f"df = pl.read_parquet(r\"{rel_path}\")\n"
                if str(rel_path).endswith(".parquet")
                else f"df = pl.read_csv(r\"{rel_path}\")\n",
                "df.head()\n",
            ]
            cells.append({"cell_type": "code", "metadata": {}, "source": code, "outputs": [], "execution_count": None})

    if project_plots:
        lines = ["## Plots\n"]
        for plot_id, plot in project_plots.items():
            lines.append(f"- {plot_id}: {plot.get('why') or 'No description'}\n")
        cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})

        for plot_id, plot in project_plots.items():
            path = plot.get("path")
            if not path:
                continue
            code = [
                "import json\n",
                "import polars as pl\n",
                "import matplotlib.pyplot as plt\n",
                f"plot = json.load(open(r\"{path}\"))\n",
                "dataset_id = plot['dataset_ids'][0]\n",
                "manifest = json.load(open('.codexdatalab/manifest.json'))\n",
                "dataset = manifest['datasets'][dataset_id]\n",
                f"project_id = \"{project_id}\"\n",
                "data_path = dataset.get('paths_by_project', {}).get(project_id, dataset.get('path'))\n",
                "df = pl.read_parquet(data_path) if data_path.endswith('.parquet') else pl.read_csv(data_path)\n",
                "# TODO: recreate plot based on plot definition\n",
                "df.head()\n",
            ]
            cells.append({"cell_type": "code", "metadata": {}, "source": code, "outputs": [], "execution_count": None})

    if project_answers:
        lines = ["## Q&A\n"]
        for answer_id, answer in project_answers.items():
            lines.append(f"### {answer.get('question')}\n")
            lines.append(f"{answer.get('answer')}\n\n")
        cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})

    notebook = {
        "cells": cells,
        "metadata": {"language_info": {"name": "python"}, "codexdatalab_report_id": report_id},
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    report_path = workspace.project_root() / "reports" / f"{report_id}.ipynb"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(notebook, indent=2) + "\n")

    manifest.setdefault("reports", {})[report_id] = {
        "id": report_id,
        "path": str(report_path.relative_to(workspace.root)),
        "created_at": utc_now_iso(),
        "project": project_id,
        "title": report_title,
    }
    workspace.save_manifest(manifest)
    for ds in datasets:
        workspace.add_lineage_edge(ds["id"], report_id, "report")
    workspace.commit(
        "Export report notebook",
        paths=[str(report_path.relative_to(workspace.root)), ".codexdatalab/manifest.json", ".codexdatalab/lineage.json"],
    )

    return {"report_id": report_id, "path": str(report_path.relative_to(workspace.root))}
