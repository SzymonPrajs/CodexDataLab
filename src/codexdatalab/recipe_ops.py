from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from .data_ops import get_dataset, load_dataset_lazy
from .utils import generate_id, hash_file, utc_now_iso
from .workspace import Workspace


@dataclass(frozen=True)
class RecipeRecord:
    recipe_id: str
    path: Path


def create_recipe(
    workspace: Workspace,
    *,
    dataset_id: str,
    name: str,
    output_column: str,
    expression: str,
    why: str = "",
    parent_recipe_id: str | None = None,
) -> RecipeRecord:
    recipe_id = generate_id("rc")
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_"}).strip() or "recipe"
    recipe_dir = workspace.project_root() / "transforms" / "recipes"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    recipe_path = recipe_dir / f"{recipe_id}_{safe_name}.json"

    record = {
        "id": recipe_id,
        "dataset_id": dataset_id,
        "name": name,
        "output_column": output_column,
        "expression": expression,
        "why": why,
        "created_at": utc_now_iso(),
        "parent_recipe_id": parent_recipe_id,
        "project": workspace.project_id(),
    }
    recipe_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    manifest = workspace.load_manifest()
    recipes = manifest.setdefault("recipes", {})
    recipes[recipe_id] = {
        "id": recipe_id,
        "path": str(recipe_path.relative_to(workspace.root)),
        "dataset_id": dataset_id,
        "name": name,
        "output_column": output_column,
        "expression": expression,
        "why": why,
        "created_at": record["created_at"],
        "parent_recipe_id": parent_recipe_id,
        "project": workspace.project_id(),
    }
    workspace.save_manifest(manifest)
    workspace.commit("Create recipe", paths=[str(recipe_path.relative_to(workspace.root)), ".codexdatalab/manifest.json"])
    return RecipeRecord(recipe_id=recipe_id, path=recipe_path)


def load_recipe(workspace: Workspace, recipe_id: str) -> dict[str, Any]:
    manifest = workspace.load_manifest()
    recipe = manifest.get("recipes", {}).get(recipe_id)
    if not recipe:
        raise KeyError(f"Unknown recipe: {recipe_id}")
    path = workspace.root / recipe["path"]
    return json.loads(path.read_text())


def list_recipes(workspace: Workspace) -> list[dict[str, Any]]:
    manifest = workspace.load_manifest()
    project_id = workspace.project_id()
    recipes = []
    for recipe in manifest.get("recipes", {}).values():
        if recipe.get("project") and recipe.get("project") != project_id:
            continue
        recipes.append(recipe)
    return sorted(recipes, key=lambda item: item.get("created_at", ""))


def apply_recipe(
    workspace: Workspace,
    *,
    recipe_id: str,
    output_name: str | None = None,
) -> dict[str, Any]:
    recipe = load_recipe(workspace, recipe_id)
    dataset_id = recipe["dataset_id"]
    dataset = get_dataset(workspace, dataset_id)
    if dataset is None:
        raise KeyError(f"Unknown dataset: {dataset_id}")

    df = load_dataset_lazy(workspace, dataset_id).collect()
    output_column = recipe["output_column"]
    expression = recipe["expression"]

    expr = _evaluate_expression(expression, df)
    if isinstance(expr, pl.Expr):
        df = df.with_columns(expr.alias(output_column))
    elif isinstance(expr, pl.Series):
        df = df.with_columns(pl.Series(output_column, expr))
    else:
        raise ValueError("Recipe expression must return a Polars Expr or Series.")

    output_dir = workspace.project_root() / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    ext = "parquet" if (output_name or "").lower().endswith(".parquet") else "csv"
    filename = output_name or f"{dataset_id}_{recipe_id}.{ext}"
    output_path = output_dir / filename

    if ext == "parquet":
        df.write_parquet(output_path)
    else:
        df.write_csv(output_path)

    sha256 = hash_file(output_path)
    new_dataset_id = f"ds_{sha256[:12]}"

    manifest = workspace.load_manifest()
    datasets = manifest.setdefault("datasets", {})
    project_id = workspace.project_id()
    datasets[new_dataset_id] = {
        "id": new_dataset_id,
        "kind": "cleaned",
        "path": str(output_path.relative_to(workspace.root)),
        "paths_by_project": {project_id: str(output_path.relative_to(workspace.root))},
        "projects": [project_id],
        "format": ext,
        "sha256": sha256,
        "size_bytes": output_path.stat().st_size,
        "sources": [],
        "created_at": utc_now_iso(),
        "name": output_path.name,
        "parent_dataset_id": dataset_id,
        "produced_by_recipe_id": recipe_id,
    }
    workspace.save_manifest(manifest)
    workspace.add_lineage_edge(dataset_id, new_dataset_id, "derived")
    workspace.add_lineage_edge(recipe_id, new_dataset_id, "recipe")
    workspace.commit(
        "Apply recipe",
        paths=[
            str(output_path.relative_to(workspace.root)),
            ".codexdatalab/manifest.json",
            ".codexdatalab/lineage.json",
        ],
    )
    return {"dataset_id": new_dataset_id, "path": str(output_path.relative_to(workspace.root))}


def _evaluate_expression(expression: str, df: pl.DataFrame) -> Any:
    safe_builtins = {"abs": abs, "min": min, "max": max, "round": round}
    scope = {"pl": pl, "col": pl.col, "df": df, **safe_builtins}
    return eval(expression, {"__builtins__": {}}, scope)
