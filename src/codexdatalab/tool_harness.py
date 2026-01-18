from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from .analysis import groupby_count, numeric_summary, schema_and_nulls, value_counts
from .data_ops import import_dataset, list_datasets, preview_dataset
from .fetch_ops import fetch_url
from .plot_ops import create_plot_definition
from .recipe_ops import apply_recipe, create_recipe, list_recipes
from .settings import add_allowed_domain
from .transform_ops import init_transform, run_transform
from .report_ops import export_report_notebook
from .utils import generate_id, utc_now_iso
from .workspace import Workspace


ConfirmCallback = Callable[[str], bool]


@dataclass
class ToolHarness:
    workspace: Workspace
    confirm: ConfirmCallback | None = None

    def _confirm(self, prompt: str) -> bool:
        if self.confirm is None:
            return False
        return bool(self.confirm(prompt))

    def list_datasets(self) -> list[dict[str, Any]]:
        return list_datasets(self.workspace)

    def import_dataset(self, path: str, *, link: bool = False, force_copy: bool = False) -> dict[str, Any]:
        source_path = Path(path).expanduser().resolve()
        if self.workspace.settings.prompt_on_external_paths:
            if not _is_within_workspace(source_path, self.workspace.root):
                if not self._confirm(f"Import file outside workspace? {source_path} [y/N]: "):
                    raise ValueError("External path import not approved.")

        def prompt(message: str) -> str:
            if self.confirm is None:
                raise ValueError("Confirmation required.")
            allowed = self.confirm(message)
            return "c" if allowed else "x"

        record = import_dataset(
            self.workspace,
            source_path,
            link=link,
            force_copy=force_copy,
            prompt=prompt if self.confirm else None,
        )
        return {"dataset_id": record.dataset_id, "path": str(record.path)}

    def preview_dataset(self, dataset_id: str, *, max_rows: int = 50, max_cols: int = 12) -> Any:
        return preview_dataset(self.workspace, dataset_id, max_rows=max_rows, max_cols=max_cols)

    def dataset_stats(self, dataset_id: str) -> dict[str, Any]:
        df = preview_dataset(self.workspace, dataset_id, max_rows=1000, max_cols=50)
        return {
            "schema": schema_and_nulls(df),
            "numeric": numeric_summary(df),
        }

    def run_transform(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Use run_transform_by_path in tool harness.")

    def create_transform(self, dataset_id: str, name: str, *, why: str = "") -> dict[str, Any]:
        path = init_transform(self.workspace, dataset_id, name, why=why)
        return {"transform_path": str(path.relative_to(self.workspace.root))}

    def run_transform_by_path(
        self,
        transform_path: str,
        *,
        input_dataset_id: str | None = None,
        why: str = "",
    ) -> dict[str, Any]:
        if self.workspace.settings.prompt_on_transform:
            if not self._confirm(f"Run transform {transform_path}? [y/N]: "):
                raise ValueError("Transform execution not approved.")
        outputs = run_transform(
            self.workspace,
            Path(transform_path),
            input_dataset_id=input_dataset_id,
            why=why,
        )
        return {"output_dataset_ids": outputs}

    def create_plot(
        self,
        *,
        dataset_id: str,
        plot_type: str,
        x: str | None = None,
        y: str | None = None,
        category: str | None = None,
        why: str = "",
        fit: bool | None = None,
    ) -> dict[str, Any]:
        definition = create_plot_definition(
            self.workspace,
            dataset_id=dataset_id,
            plot_type=plot_type,
            x=x,
            y=y,
            category=category,
            why=why,
            fit=fit,
        )
        return {"plot": definition}

    def create_recipe(
        self,
        *,
        dataset_id: str,
        name: str,
        output_column: str,
        expression: str,
        why: str = "",
        parent_recipe_id: str | None = None,
    ) -> dict[str, Any]:
        record = create_recipe(
            self.workspace,
            dataset_id=dataset_id,
            name=name,
            output_column=output_column,
            expression=expression,
            why=why,
            parent_recipe_id=parent_recipe_id,
        )
        return {"recipe_id": record.recipe_id, "path": str(record.path.relative_to(self.workspace.root))}

    def apply_recipe(self, *, recipe_id: str, output_name: str | None = None) -> dict[str, Any]:
        return apply_recipe(self.workspace, recipe_id=recipe_id, output_name=output_name)

    def list_recipes(self) -> dict[str, Any]:
        return {"recipes": list_recipes(self.workspace)}

    def record_answer(
        self,
        *,
        question: str,
        answer: str,
        dataset_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        answers = self.workspace.load_answers()
        answer_id = generate_id("ans")
        answers.setdefault("answers", {})[answer_id] = {
            "id": answer_id,
            "question": question,
            "answer": answer,
            "dataset_ids": dataset_ids or [],
            "artifact_ids": artifact_ids or [],
            "created_at": utc_now_iso(),
            "project": self.workspace.project_id(),
        }
        self.workspace.save_answers(answers)
        for dataset_id in dataset_ids or []:
            self.workspace.add_lineage_edge(dataset_id, answer_id, "answer")
        for artifact_id in artifact_ids or []:
            self.workspace.add_lineage_edge(artifact_id, answer_id, "answer")
        self.workspace.commit("Record answer", paths=[".codexdatalab/qa.json", ".codexdatalab/lineage.json"])
        return {"answer_id": answer_id}

    def fetch_url(
        self,
        url: str,
        *,
        display_name: str | None = None,
        format_hint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.workspace.settings.prompt_on_network:
            if not self._confirm(f"Allow network download from {url}? [y/N]: "):
                raise ValueError("Network download not approved.")
        result = fetch_url(
            self.workspace,
            url,
            display_name=display_name,
            format_hint=format_hint,
            metadata=metadata,
            prompt=None,
        )
        return {
            "dataset_id": result.dataset_id,
            "path": str(result.path),
            "receipt_path": str(result.receipt_path),
        }

    def add_allowed_domain(self, domain: str) -> dict[str, Any]:
        updated = add_allowed_domain(domain)
        self.workspace.settings = updated
        return {"allowed_domains": updated.allowed_domains}

    def export_report(self, *, title: str | None = None) -> dict[str, Any]:
        return export_report_notebook(self.workspace, title=title)

    def list_projects(self) -> dict[str, Any]:
        return {"projects": self.workspace.list_projects()}

    def create_project(self, name: str) -> dict[str, Any]:
        self.workspace.ensure_project(name)
        return {"project": name}

    def set_active_project(self, name: str | None) -> dict[str, Any]:
        cleaned = name.strip() if isinstance(name, str) else ""
        self.workspace.set_active_project(cleaned or None)
        return {"active_project": self.workspace.project}


def _is_within_workspace(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
