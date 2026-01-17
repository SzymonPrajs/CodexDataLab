from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

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
        manifest = self.workspace.load_json(
            "manifest.json",
            {"schema_version": 0, "datasets": {}, "transforms": {}},
        )
        datasets = manifest.get("datasets", {})
        return [datasets[key] for key in sorted(datasets.keys())]

    def import_dataset(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Dataset import is implemented in MVP-1.")

    def preview_dataset(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Dataset preview is implemented in MVP-2.")

    def dataset_stats(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Dataset stats are implemented in MVP-3.")

    def run_transform(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Transform execution is implemented in MVP-4.")

    def create_plot(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Plot creation is implemented in MVP-6.")

    def record_answer(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError("Answer recording is implemented in MVP-7.")

