from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import generate_id, utc_now_iso
from .workspace import Workspace


def create_plot_definition(
    workspace: Workspace,
    *,
    dataset_id: str,
    plot_type: str,
    x: str | None,
    y: str | None,
    category: str | None = None,
    why: str = "",
) -> dict[str, Any]:
    plot_id = generate_id("pl")
    plot_path = workspace.root / "plots" / f"{plot_id}.json"
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    definition = {
        "id": plot_id,
        "plot_type": plot_type,
        "dataset_ids": [dataset_id],
        "x": x,
        "y": y,
        "category": category,
        "why": why,
        "created_at": utc_now_iso(),
    }

    plot_path.write_text(json.dumps(definition, indent=2, sort_keys=True) + "\n")

    plots_registry = workspace.load_plots()
    plots_registry.setdefault("plots", {})[plot_id] = {
        "id": plot_id,
        "path": str(plot_path.relative_to(workspace.root)),
        "dataset_ids": [dataset_id],
        "why": why,
        "created_at": definition["created_at"],
    }
    workspace.save_plots(plots_registry)
    workspace.add_lineage_edge(dataset_id, plot_id, "plot")
    workspace.commit(
        f"Create plot {plot_id}",
        paths=[plot_path.as_posix(), ".codexdatalab/plots.json", ".codexdatalab/lineage.json"],
    )
    return definition


def list_plots(workspace: Workspace) -> list[dict[str, Any]]:
    plots = workspace.load_plots().get("plots", {})
    return [plots[key] for key in sorted(plots.keys())]


def load_plot_definition(workspace: Workspace, plot_id: str) -> dict[str, Any]:
    plots = workspace.load_plots().get("plots", {})
    plot_meta = plots.get(plot_id)
    if not plot_meta:
        raise KeyError(f"Unknown plot: {plot_id}")
    path = workspace.root / plot_meta["path"]
    return json.loads(path.read_text())
