from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from .analysis import groupby_count, numeric_summary, schema_and_nulls, value_counts
from .data_ops import import_dataset, list_datasets, preview_dataset
from .fetch_ops import fetch_url
from .settings import add_allowed_domain
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
        def prompt(message: str) -> str:
            if self.confirm is None:
                raise ValueError("Confirmation required.")
            allowed = self.confirm(message)
            return "c" if allowed else "x"

        record = import_dataset(
            self.workspace,
            Path(path),
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
        raise NotImplementedError("Transform execution is implemented in MVP-4.")

    def create_plot(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Plot creation is implemented in MVP-6.")

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
        }
        self.workspace.save_answers(answers)
        self.workspace.commit("Record answer", paths=[".codexdatalab/qa.json"])
        return {"answer_id": answer_id}

    def fetch_url(
        self,
        url: str,
        *,
        display_name: str | None = None,
        format_hint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
