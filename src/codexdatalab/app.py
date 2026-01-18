from __future__ import annotations

from textual.app import App, ComposeResult
from typing import Any
import threading
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Select,
    Static,
    TabbedContent,
    RichLog,
    TabPane,
)

from .analysis import (
    categorical_summary,
    groupby_count,
    numeric_summary,
    schema_and_nulls,
    value_counts,
)
from .codex_app_server import CodexAppServerClient
from .data_ops import list_datasets, preview_dataset
from .plot_ops import create_plot_definition, list_plots, load_plot_definition
from .plotting import PlotDefinition, render_plot
from .recipe_ops import list_recipes, load_recipe
from .summary_ops import generate_summary_markdown
from .tool_harness import ToolHarness
from .tool_registry import ToolRegistry
import json
import polars as pl

from .utils import generate_id, utc_now_iso
from .workspace import Workspace

class CodexDataLabApp(App):
    TITLE = "CodexDataLab"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("ctrl+g", "toggle_plot", "Plot"),
        ("ctrl+t", "toggle_chat", "Chat"),
        ("ctrl+b", "split_view", "Split"),
        ("ctrl+f", "toggle_menu", "Menu"),
        ("tab", "toggle_focus", "Focus"),
        ("ctrl+s", "toggle_stats", "Stats"),
        ("ctrl+l", "toggle_lineage", "Lineage"),
        ("?", "toggle_help", "Help"),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self._pending_confirm: str | None = None
        self._confirm_event = None
        self._confirm_result = False
        self.tool_harness = ToolHarness(workspace, confirm=self._confirm_action)
        self.tool_registry = ToolRegistry(self.tool_harness)
        self.codex_client = CodexAppServerClient(
            workspace,
            client_version=self._get_app_version(),
        )
        self.sub_title = str(workspace.root)
        state = self.workspace.load_state()
        self._help_visible = bool(state.get("ui", {}).get("help_visible", True))
        self._stats_visible = bool(state.get("ui", {}).get("stats_visible", True))
        self._lineage_visible = bool(state.get("ui", {}).get("lineage_visible", False))
        self._selected_dataset_id: str | None = None
        self._selected_plot_id: str | None = None
        self._selected_recipe_id: str | None = None
        self._codex_ready = False
        self._filter_state = state.get("ui", {}).get("filters", {})

    def _get_app_version(self) -> str:
        try:
            from . import __version__

            return __version__
        except Exception:
            return "0.0.0"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="root"):
            with Vertical(id="menu"):
                yield Label("Project", classes="title")
                yield Select([], id="project-select")
                yield Input(placeholder="new project name", id="project-new")
                yield Button("Create Project", id="project-create")
                yield Label("Active: default", id="project-meta", classes="meta")

                yield Label("Datasets", classes="title")
                yield Label("Select a dataset.", classes="subtitle")
                yield ListView(id="dataset-list")
                yield Label("Selected: —", id="dataset-meta", classes="meta")

                yield Label("Filters", classes="title")
                yield Select([], id="filter-column")
                yield Select(
                    [
                        ("equals", "equals"),
                        ("contains", "contains"),
                        ("range", "range"),
                    ],
                    id="filter-op",
                    value="equals",
                )
                yield Input(placeholder="value", id="filter-value")
                yield Input(placeholder="min (range)", id="filter-min")
                yield Input(placeholder="max (range)", id="filter-max")
                yield Button("Apply Filter", id="filter-apply")
                yield Button("Clear Filter", id="filter-clear")

            with Vertical(id="right"):
                with TabbedContent(id="main-tabs"):
                    with TabPane("Table", id="table-tab"):
                        with Horizontal(id="table-body"):
                            yield DataTable(id="data-table")
                            yield Static("", id="stats-panel")
                    with TabPane("Plot", id="plot-tab"):
                        with Horizontal(id="plot-body"):
                            with Vertical(id="plot-controls"):
                                yield Label("Plot Controls", classes="title")
                                yield Label("Plot type", classes="subtitle")
                                yield Select(
                                    [
                                        ("scatter", "scatter"),
                                        ("line", "line"),
                                        ("bar", "bar"),
                                        ("hist", "hist"),
                                        ("violin", "violin"),
                                        ("error_bar", "error_bar"),
                                    ],
                                    id="plot-type",
                                    value="scatter",
                                )
                                yield Label("x column", classes="subtitle")
                                yield Input(placeholder="x column", id="plot-x")
                                yield Label("y column (optional)", classes="subtitle")
                                yield Input(placeholder="y column", id="plot-y")
                                yield Label("category column (optional)", classes="subtitle")
                                yield Input(placeholder="category column", id="plot-category")
                                yield Label("trend fit (optional)", classes="subtitle")
                                yield Select(
                                    [("none", "none"), ("linear", "linear")],
                                    id="plot-fit",
                                    value="none",
                                )
                                yield Button("Create Plot", id="plot-create")
                                yield Static("Plot details", id="plot-meta")
                                yield Label("Saved plots", classes="subtitle")
                                yield ListView(id="plot-list")
                            yield Static("Plot canvas", id="plot-canvas")
                    with TabPane("Recipes", id="recipe-tab"):
                        with Horizontal(id="recipe-body"):
                            with Vertical(id="recipe-controls"):
                                yield Label("Recipe Controls", classes="title")
                                yield Label("name", classes="subtitle")
                                yield Input(placeholder="recipe name", id="recipe-name")
                                yield Label("output column", classes="subtitle")
                                yield Input(placeholder="new column", id="recipe-output")
                                yield Label("expression", classes="subtitle")
                                yield Input(placeholder="e.g. col('amount') * 1.2", id="recipe-expr")
                                yield Button("Create Recipe", id="recipe-create")
                                yield Label("apply recipe id", classes="subtitle")
                                yield Input(placeholder="recipe id", id="recipe-id")
                                yield Label("output name (optional)", classes="subtitle")
                                yield Input(placeholder="output filename", id="recipe-output-name")
                                yield Button("Apply Recipe", id="recipe-apply")
                                yield Label("Saved recipes", classes="subtitle")
                                yield ListView(id="recipe-list")
                            yield Static("Recipe details", id="recipe-meta")
                    with TabPane("Summary", id="summary-tab"):
                        yield Markdown("", id="summary-view")
                        yield Button("Regenerate Summary", id="summary-refresh")
                        yield Button("Export Report", id="summary-export")

                with Vertical(id="chat"):
                    yield Label("Chat", classes="title")
                    yield Label("Tab switches focus between menu and input.", classes="subtitle")
                    yield RichLog(id="chat-log")
                    yield Input(placeholder="> Ask me anything...", id="chat-input")
                    yield Label("Tip: /help for chat commands.", classes="hint")
                    yield Label("", id="status", classes="status")
                    yield Label(
                        "Shortcuts: Ctrl+G plot, Ctrl+B split, Ctrl+F menu, Tab focus, Ctrl+S stats, Ctrl+L lineage, ? help",
                        id="help",
                        classes="help",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self._apply_help_visibility()
        self._refresh_project_select()
        self._refresh_dataset_list()
        self._refresh_plot_list()
        self._refresh_recipe_list()
        self._apply_stats_visibility()
        self._load_summary()
        self._apply_filter_state()
        self._set_status(f"Workspace loaded: {self.workspace.root}")
        if self.workspace.settings.offline_mode:
            self._set_status("Offline mode enabled; Codex disabled.")
        else:
            self._set_status("Starting Codex app-server...")
            self.run_worker(self._start_codex, exclusive=True, thread=True)

    def on_shutdown(self) -> None:
        self.codex_client.stop()

    def _start_codex(self) -> None:
        ready = self.codex_client.start()
        self._codex_ready = ready
        if ready:
            self.call_from_thread(self._set_status, "Codex connected.")
        else:
            self.call_from_thread(self._set_status, "Codex not available; offline mode.")

    def action_toggle_plot(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = "plot-tab"
        self._set_status("Plot view selected.")

    def action_toggle_chat(self) -> None:
        chat_input = self.query_one("#chat-input", Input)
        chat_input.focus()
        self._set_status("Chat focused.")

    def action_split_view(self) -> None:
        self._set_status("Split view not implemented yet.")

    def action_toggle_menu(self) -> None:
        menu = self.query_one("#menu")
        menu.toggle_class("focused")
        self._set_status("Menu toggled.")

    def action_toggle_focus(self) -> None:
        chat_input = self.query_one("#chat-input", Input)
        dataset_list = self.query_one("#dataset-list", ListView)
        if self.focused is chat_input:
            dataset_list.focus()
            self._set_status("Focus: datasets")
        else:
            chat_input.focus()
            self._set_status("Focus: chat")

    def action_toggle_stats(self) -> None:
        self._stats_visible = not self._stats_visible
        self._apply_stats_visibility()
        self.workspace.update_ui_state("stats_visible", self._stats_visible)
        state = "shown" if self._stats_visible else "hidden"
        self._set_status(f"Stats {state}.")

    def action_toggle_lineage(self) -> None:
        self._lineage_visible = not self._lineage_visible
        self.workspace.update_ui_state("lineage_visible", self._lineage_visible)
        self._refresh_stats_panel()
        state = "shown" if self._lineage_visible else "hidden"
        self._set_status(f"Lineage {state}.")

    def action_toggle_help(self) -> None:
        self._help_visible = not self._help_visible
        self._apply_help_visibility()
        self.workspace.update_ui_state("help_visible", self._help_visible)
        state = "shown" if self._help_visible else "hidden"
        self._set_status(f"Help {state}.")

    def _apply_help_visibility(self) -> None:
        help_label = self.query_one("#help", Label)
        help_label.display = self._help_visible

    def _apply_stats_visibility(self) -> None:
        stats_panel = self.query_one("#stats-panel", Static)
        stats_panel.display = self._stats_visible
        self._refresh_stats_panel()

    def _set_status(self, message: str) -> None:
        status_label = self.query_one("#status", Label)
        status_label.update(f"Status: {message}")

    def _confirm_action(self, prompt: str) -> bool:
        if self._confirm_event is None:
            self._confirm_event = threading.Event()
        self._confirm_event.clear()
        self._confirm_result = False
        self._pending_confirm = prompt
        self.call_from_thread(self._append_chat, f"[confirm] {prompt} (yes/no)")
        self.call_from_thread(self._set_status, "Awaiting confirmation in chat input.")
        self._confirm_event.wait(timeout=120)
        self._pending_confirm = None
        return self._confirm_result

    def _load_summary(self) -> None:
        summary_path = self.workspace.project_root() / "results" / "summary.md"
        summary_view = self.query_one("#summary-view", Markdown)
        if summary_path.exists():
            summary_view.update(summary_path.read_text())
        else:
            summary_view.update("")

    def _refresh_project_select(self) -> None:
        select = self.query_one("#project-select", Select)
        projects = self.workspace.list_projects()
        options = [("default", "default")] + [(name, name) for name in projects]
        select.set_options(options)
        active = self.workspace.project or "default"
        select.value = active
        meta = self.query_one("#project-meta", Label)
        meta.update(f"Active: {active}")
        self.sub_title = f"{self.workspace.root} [{active}]"

    def _apply_filter_state(self) -> None:
        filters = self._filter_state or {}
        try:
            self.query_one("#filter-op", Select).value = filters.get("op", "equals")
            self.query_one("#filter-value", Input).value = filters.get("value", "")
            self.query_one("#filter-min", Input).value = filters.get("min", "")
            self.query_one("#filter-max", Input).value = filters.get("max", "")
        except Exception:
            return

    def _refresh_dataset_list(self) -> None:
        list_view = self.query_one("#dataset-list", ListView)
        list_view.clear()
        datasets = list_datasets(self.workspace)
        for dataset in datasets:
            dataset_id = dataset.get("id")
            label = dataset.get("name") or dataset_id
            list_view.append(ListItem(Label(f"{label} ({dataset.get('kind')})"), id=dataset_id))
        self._refresh_filter_columns()

    def _refresh_plot_list(self) -> None:
        list_view = self.query_one("#plot-list", ListView)
        list_view.clear()
        plots = list_plots(self.workspace)
        for plot in plots:
            plot_id = plot.get("id")
            label = plot.get("why") or plot_id
            list_view.append(ListItem(Label(label), id=plot_id))

    def _refresh_recipe_list(self) -> None:
        list_view = self.query_one("#recipe-list", ListView)
        list_view.clear()
        recipes = list_recipes(self.workspace)
        for recipe in recipes:
            recipe_id = recipe.get("id")
            label = recipe.get("name") or recipe_id
            list_view.append(ListItem(Label(label), id=recipe_id))

    def _refresh_filter_columns(self) -> None:
        select = self.query_one("#filter-column", Select)
        if not self._selected_dataset_id:
            select.set_options([])
            return
        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id, max_rows=1, max_cols=200)
        except Exception:
            return
        options = [(col, col) for col in df.columns]
        select.set_options(options)
        current = self._filter_state.get("column") if self._filter_state else None
        if current and current in df.columns:
            select.value = current

    def _apply_filters(self, df: pl.DataFrame) -> pl.DataFrame:
        filters = self._filter_state or {}
        column = filters.get("column")
        if not column or column not in df.columns:
            return df
        op = filters.get("op", "equals")
        if op == "range":
            min_val = _parse_number(filters.get("min"))
            max_val = _parse_number(filters.get("max"))
            if min_val is not None:
                df = df.filter(pl.col(column) >= min_val)
            if max_val is not None:
                df = df.filter(pl.col(column) <= max_val)
            return df
        value = filters.get("value")
        if value is None or value == "":
            return df
        if op == "contains":
            return df.filter(pl.col(column).cast(pl.Utf8).str.contains(str(value)))
        number = _parse_number(value)
        if number is not None and df[column].dtype.is_numeric():
            return df.filter(pl.col(column) == number)
        return df.filter(pl.col(column) == value)
    def _refresh_table(self) -> None:
        if not self._selected_dataset_id:
            return
        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id)
            df = self._apply_filters(df)
        except Exception as exc:  # pragma: no cover - UI defensive guard
            self._set_status(f"Failed to load dataset: {exc}")
            return
        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        table.add_columns(*df.columns)
        for row in df.iter_rows():
            table.add_row(*[str(value) for value in row])
        self._refresh_stats_panel()

    def _refresh_stats_panel(self) -> None:
        if not self._selected_dataset_id:
            return
        panel = self.query_one("#stats-panel", Static)
        if not self._stats_visible:
            panel.update("")
            return

        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id, max_rows=500, max_cols=50)
            df = self._apply_filters(df)
        except Exception as exc:  # pragma: no cover
            panel.update(f"Stats unavailable: {exc}")
            return
        stats = numeric_summary(df)
        lines = ["Stats"]
        for row in stats.get("rows", []):
            lines.append(
                f"{row['column']}: min={row['min']} max={row['max']} mean={row['mean']}"
            )
        cat_stats = categorical_summary(df, limit=3)
        for row in cat_stats.get("rows", []):
            display_parts = []
            for item in row.get("top_values", []):
                value = item.get(row["column"])
                if value is None:
                    for key in item.keys():
                        if key not in {"count", "counts"}:
                            value = item.get(key)
                            break
                count_value = item.get("counts", item.get("count", ""))
                display_parts.append(f"{value}:{count_value}")
            top_values = ", ".join(display_parts)
            lines.append(f"{row['column']}: unique={row['unique']} top={top_values}")

        if self._lineage_visible:
            lineage = self.workspace.lineage_for(self._selected_dataset_id)
            lines.append("")
            lines.append("Lineage")
            if lineage["incoming"]:
                lines.append("From:")
                lines.extend([f"- {item}" for item in lineage["incoming"]])
            if lineage["outgoing"]:
                lines.append("To:")
                lines.extend([f"- {item}" for item in lineage["outgoing"]])

        panel.update("\n".join(lines))

    def _render_plot(self, plot_definition: dict) -> None:
        dataset_id = plot_definition.get("dataset_ids", [None])[0]
        if not dataset_id:
            return
        try:
            df = preview_dataset(self.workspace, dataset_id, max_rows=1000, max_cols=100)
            df = self._apply_filters(df)
        except Exception as exc:  # pragma: no cover
            self._set_status(f"Plot failed: {exc}")
            return
        definition = PlotDefinition(
            plot_type=plot_definition.get("plot_type", "scatter"),
            x=plot_definition.get("x"),
            y=plot_definition.get("y"),
            category=plot_definition.get("category"),
            fit=bool(plot_definition.get("fit", False)),
        )
        canvas = self.query_one("#plot-canvas", Static)
        canvas.update(render_plot(df, definition))
        meta = self.query_one("#plot-meta", Static)
        meta.update(
            f"Dataset: {dataset_id}\nType: {definition.plot_type}\nFit: {'on' if definition.fit else 'off'}"
        )

    def _render_active_plot(self) -> None:
        if not self._selected_plot_id:
            return
        try:
            definition = load_plot_definition(self.workspace, self._selected_plot_id)
        except Exception:
            return
        self._render_plot(definition)

    def _append_chat(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(text)

    def _record_answer(self, question: str, answer: str, dataset_id: str | None, artifact_id: str | None) -> None:
        answers = self.workspace.load_answers()
        answer_id = generate_id("ans")
        answers.setdefault("answers", {})[answer_id] = {
            "id": answer_id,
            "question": question,
            "answer": answer,
            "dataset_ids": [dataset_id] if dataset_id else [],
            "artifact_ids": [artifact_id] if artifact_id else [],
            "created_at": utc_now_iso(),
            "project": self.workspace.project_id(),
        }
        self.workspace.save_answers(answers)
        if dataset_id:
            self.workspace.add_lineage_edge(dataset_id, answer_id, "answer")
        if artifact_id:
            self.workspace.add_lineage_edge(artifact_id, answer_id, "answer")
        self.workspace.commit(
            "Record answer",
            paths=[".codexdatalab/qa.json", ".codexdatalab/lineage.json"],
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "dataset-list":
            if not event.item or not event.item.id:
                return
            self._selected_dataset_id = event.item.id
            dataset_meta = self.query_one("#dataset-meta", Label)
            dataset_meta.update(f"Selected: {self._selected_dataset_id}")
            self._refresh_filter_columns()
            self._refresh_table()
        elif event.list_view.id == "plot-list":
            if not event.item or not event.item.id:
                return
            plot_id = event.item.id
            self._selected_plot_id = plot_id
            definition = load_plot_definition(self.workspace, plot_id)
            self._render_plot(definition)
        elif event.list_view.id == "recipe-list":
            if not event.item or not event.item.id:
                return
            recipe_id = event.item.id
            self._selected_recipe_id = recipe_id
            try:
                recipe = load_recipe(self.workspace, recipe_id)
            except Exception:
                return
            meta = self.query_one("#recipe-meta", Static)
            meta.update(
                f"Recipe: {recipe_id}\n"
                f"Dataset: {recipe.get('dataset_id')}\n"
                f"Output: {recipe.get('output_column')}\n"
                f"Expression: {recipe.get('expression')}"
            )
            self.query_one("#recipe-id", Input).value = recipe_id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "project-create":
            name = self.query_one("#project-new", Input).value.strip()
            if not name:
                self._set_status("Enter a project name.")
                return
            self.workspace.set_active_project(name)
            self._refresh_project_select()
            self._selected_dataset_id = None
            self._refresh_dataset_list()
            self._refresh_plot_list()
            self._refresh_recipe_list()
            self._load_summary()
            self.query_one("#dataset-meta", Label).update("Selected: —")
            self._set_status(f"Active project: {name}")
            return
        if event.button.id == "filter-apply":
            column = self.query_one("#filter-column", Select).value
            op = self.query_one("#filter-op", Select).value
            value = self.query_one("#filter-value", Input).value.strip()
            min_value = self.query_one("#filter-min", Input).value.strip()
            max_value = self.query_one("#filter-max", Input).value.strip()
            self._filter_state = {
                "column": column,
                "op": op,
                "value": value,
                "min": min_value,
                "max": max_value,
            }
            self.workspace.update_ui_state("filters", self._filter_state)
            self._refresh_table()
            self._render_active_plot()
            return
        if event.button.id == "filter-clear":
            self._filter_state = {}
            self.workspace.update_ui_state("filters", self._filter_state)
            self._apply_filter_state()
            self._refresh_table()
            self._render_active_plot()
            return
        if event.button.id == "recipe-create":
            if not self._selected_dataset_id:
                self._set_status("Select a dataset before creating a recipe.")
                return
            name = self.query_one("#recipe-name", Input).value.strip()
            output_column = self.query_one("#recipe-output", Input).value.strip()
            expression = self.query_one("#recipe-expr", Input).value.strip()
            if not name or not output_column or not expression:
                self._set_status("Recipe requires name, output column, and expression.")
                return
            try:
                record = self.tool_harness.create_recipe(
                    dataset_id=self._selected_dataset_id,
                    name=name,
                    output_column=output_column,
                    expression=expression,
                )
            except Exception as exc:
                self._set_status(f"Recipe create failed: {exc}")
                return
            self._refresh_recipe_list()
            self._set_status(f"Recipe created: {record['recipe_id']}")
            return
        if event.button.id == "recipe-apply":
            recipe_id = self.query_one("#recipe-id", Input).value.strip()
            output_name = self.query_one("#recipe-output-name", Input).value.strip() or None
            if not recipe_id:
                self._set_status("Provide a recipe id to apply.")
                return
            try:
                result = self.tool_harness.apply_recipe(recipe_id=recipe_id, output_name=output_name)
            except Exception as exc:
                self._set_status(f"Recipe apply failed: {exc}")
                return
            self._refresh_dataset_list()
            self._set_status(f"Recipe output dataset: {result['dataset_id']}")
            return
        if event.button.id == "plot-create":
            if not self._selected_dataset_id:
                self._set_status("Select a dataset before plotting.")
                return
            plot_type = self.query_one("#plot-type", Select).value or "scatter"
            x = self.query_one("#plot-x", Input).value.strip() or None
            y = self.query_one("#plot-y", Input).value.strip() or None
            category = self.query_one("#plot-category", Input).value.strip() or None
            fit_value = self.query_one("#plot-fit", Select).value
            fit = fit_value == "linear"
            definition = create_plot_definition(
                self.workspace,
                dataset_id=self._selected_dataset_id,
                plot_type=plot_type,
                x=x,
                y=y,
                category=category,
                why=f"{plot_type} plot",
                fit=fit,
            )
            self._render_plot(definition)
            self._refresh_plot_list()
            self._set_status(f"Plot created: {definition['id']}")
        elif event.button.id == "summary-refresh":
            summary = generate_summary_markdown(self.workspace)
            summary_path = self.workspace.project_root() / "results" / "summary.md"
            summary_path.write_text(summary)
            summary_view = self.query_one("#summary-view", Markdown)
            summary_view.update(summary)
            self._set_status("Summary refreshed.")
        elif event.button.id == "summary-export":
            from .report_ops import export_report_notebook

            result = export_report_notebook(self.workspace)
            self._set_status(f"Report exported: {result['path']}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        message = event.value.strip()
        event.input.value = ""
        if not message:
            return
        if self._pending_confirm:
            normalized = message.lower()
            if normalized in {"y", "yes"}:
                self._confirm_result = True
            elif normalized in {"n", "no"}:
                self._confirm_result = False
            else:
                self._append_chat("Please answer yes/no for the pending confirmation.")
                return
            if self._confirm_event is not None:
                self._confirm_event.set()
            self._append_chat(f"Confirmation: {'approved' if self._confirm_result else 'declined'}.")
            return
        self._append_chat(f"You: {message}")
        self.run_worker(
            lambda: self._handle_chat_message_worker(message),
            exclusive=True,
            thread=True,
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "project-select":
            name = event.value
            if name == "default":
                self.workspace.set_active_project(None)
            else:
                self.workspace.set_active_project(str(name))
            self._refresh_project_select()
            self._selected_dataset_id = None
            self._selected_plot_id = None
            self._selected_recipe_id = None
            self._refresh_dataset_list()
            self._refresh_plot_list()
            self._refresh_recipe_list()
            self._load_summary()
            self.query_one("#dataset-meta", Label).update("Selected: —")
            self._set_status(f"Active project: {self.workspace.project or 'default'}")

    def _handle_chat_message_worker(self, message: str) -> None:
        response, artifact_id = self._handle_chat_message(message)
        self.call_from_thread(self._append_chat, f"Codex: {response}")
        self.call_from_thread(
            self._record_answer, message, response, self._selected_dataset_id, artifact_id
        )

    def _handle_chat_message(self, message: str) -> tuple[str, str | None]:
        if message.startswith("/help"):
            return (
                "Commands: /datasets, /import <path>, /fetch_url <url>, /allow_domain <domain>, "
                "/projects, /project <name>, /transform_create <name>, /transform_run <path>, "
                "/recipe_create <name> <column> <expression>, /recipe_apply <recipe_id> [output_name], "
                "/report, /describe, /stats, /value_counts <col>, /groupby <col1,col2>",
                None,
            )
        if message.startswith("/datasets"):
            datasets = list_datasets(self.workspace)
            lines = [f"{ds.get('id')} — {ds.get('name')}" for ds in datasets]
            return ("Datasets:\\n" + "\\n".join(lines) if lines else "No datasets.", None)
        if message.startswith("/projects"):
            projects = self.workspace.list_projects()
            lines = ["default"] + projects
            return ("Projects:\\n" + "\\n".join(lines), None)
        if message.startswith("/project"):
            parts = message.split(maxsplit=1)
            name = parts[1].strip() if len(parts) > 1 else ""
            if name.lower() == "default" or not name:
                self.workspace.set_active_project(None)
                self._refresh_project_select()
                self._refresh_dataset_list()
                self._refresh_plot_list()
                self._refresh_recipe_list()
                self.query_one("#dataset-meta", Label).update("Selected: —")
                return ("Active project set to default.", None)
            self.workspace.set_active_project(name)
            self._refresh_project_select()
            self._refresh_dataset_list()
            self._refresh_plot_list()
            self._refresh_recipe_list()
            self.query_one("#dataset-meta", Label).update("Selected: —")
            return (f"Active project set to {name}.", None)
        if message.startswith("/import"):
            parts = message.split(maxsplit=1)
            if len(parts) < 2:
                return ("Usage: /import <path>", None)
            try:
                record = self.tool_harness.import_dataset(parts[1])
            except Exception as exc:
                return (f"Import failed: {exc}", None)
            self._refresh_dataset_list()
            return (f"Imported dataset {record['dataset_id']}.", None)
        if message.startswith("/fetch_url"):
            parts = message.split(maxsplit=1)
            if len(parts) < 2:
                return ("Usage: /fetch_url <url>", None)
            try:
                record = self.tool_harness.fetch_url(parts[1])
            except Exception as exc:
                return (f"Fetch failed: {exc}", None)
            self._refresh_dataset_list()
            return (
                f"Fetched dataset {record['dataset_id']} (receipt {record['receipt_path']}).",
                None,
            )
        if message.startswith("/allow_domain"):
            parts = message.split(maxsplit=1)
            if len(parts) < 2:
                return ("Usage: /allow_domain <domain>", None)
            try:
                updated = self.tool_harness.add_allowed_domain(parts[1])
            except Exception as exc:
                return (f"Update failed: {exc}", None)
            return (f"Allowed domains: {', '.join(updated['allowed_domains'])}", None)
        if message.startswith("/transform_create"):
            parts = message.split(maxsplit=1)
            if len(parts) < 2:
                return ("Usage: /transform_create <name>", None)
            if not self._selected_dataset_id:
                return ("Select a dataset first.", None)
            try:
                record = self.tool_harness.create_transform(self._selected_dataset_id, parts[1])
            except Exception as exc:
                return (f"Transform create failed: {exc}", None)
            return (f"Transform created at {record['transform_path']}.", None)
        if message.startswith("/transform_run"):
            parts = message.split(maxsplit=1)
            if len(parts) < 2:
                return ("Usage: /transform_run <path>", None)
            try:
                result = self.tool_harness.run_transform_by_path(parts[1])
            except Exception as exc:
                return (f"Transform run failed: {exc}", None)
            self._refresh_dataset_list()
            return (f"Transform outputs: {', '.join(result['output_dataset_ids'])}", None)
        if message.startswith("/recipe_create"):
            parts = message.split(maxsplit=3)
            if len(parts) < 4:
                return ("Usage: /recipe_create <name> <column> <expression>", None)
            if not self._selected_dataset_id:
                return ("Select a dataset first.", None)
            name, column, expr = parts[1], parts[2], parts[3]
            try:
                record = self.tool_harness.create_recipe(
                    dataset_id=self._selected_dataset_id,
                    name=name,
                    output_column=column,
                    expression=expr,
                )
            except Exception as exc:
                return (f"Recipe create failed: {exc}", None)
            return (f"Recipe created {record['recipe_id']}.", None)
        if message.startswith("/recipe_apply"):
            parts = message.split(maxsplit=2)
            if len(parts) < 2:
                return ("Usage: /recipe_apply <recipe_id> [output_name]", None)
            recipe_id = parts[1]
            output_name = parts[2] if len(parts) > 2 else None
            try:
                result = self.tool_harness.apply_recipe(recipe_id=recipe_id, output_name=output_name)
            except Exception as exc:
                return (f"Recipe apply failed: {exc}", None)
            self._refresh_dataset_list()
            return (f"Recipe output dataset {result['dataset_id']}.", None)
        if message.startswith("/report"):
            from .report_ops import export_report_notebook

            result = export_report_notebook(self.workspace)
            return (f"Report exported: {result['path']}", None)
        if not self._selected_dataset_id:
            if self._codex_ready:
                return self._ask_codex(message)
            return ("Select a dataset first, or enable Codex for general questions.", None)

        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id, max_rows=1000, max_cols=100)
            df = self._apply_filters(df)
        except Exception as exc:  # pragma: no cover
            return f"Failed to load dataset: {exc}", None
        if message.startswith("/describe"):
            try:
                payload = schema_and_nulls(df)
            except Exception as exc:
                return f"Describe failed: {exc}", None
            artifact_id = self._save_result_artifact("schema", payload)
            return (f"Schema + null counts recorded (artifact {artifact_id}).", artifact_id)
        if message.startswith("/stats"):
            try:
                payload = numeric_summary(df)
            except Exception as exc:
                return f"Stats failed: {exc}", None
            artifact_id = self._save_result_artifact("stats", payload)
            return (f"Numeric summary recorded (artifact {artifact_id}).", artifact_id)
        if message.startswith("/value_counts"):
            parts = message.split()
            if len(parts) < 2:
                return ("Usage: /value_counts <column>", None)
            try:
                payload = value_counts(df, parts[1])
            except Exception as exc:
                return f"Value counts failed: {exc}", None
            artifact_id = self._save_result_artifact("value_counts", payload)
            return (f"Value counts for {parts[1]} recorded (artifact {artifact_id}).", artifact_id)
        if message.startswith("/groupby"):
            parts = message.split()
            if len(parts) < 2:
                return ("Usage: /groupby <col1,col2>", None)
            columns = [c.strip() for c in parts[1].split(",") if c.strip()]
            try:
                payload = groupby_count(df, columns)
            except Exception as exc:
                return f"Groupby failed: {exc}", None
            artifact_id = self._save_result_artifact("groupby", payload)
            return (
                f"Groupby counts for {', '.join(columns)} recorded (artifact {artifact_id}).",
                artifact_id,
            )

        if self._codex_ready:
            return self._ask_codex(message, dataset_id=self._selected_dataset_id)

        try:
            payload = numeric_summary(df)
        except Exception as exc:
            return f"Summary failed: {exc}", None
        artifact_id = self._save_result_artifact("summary", payload)
        return (
            f"I ran a quick numeric summary on the selected dataset (artifact {artifact_id}).",
            artifact_id,
        )

    def _ask_codex(self, message: str, *, dataset_id: str | None = None) -> tuple[str, str | None]:
        if not self._codex_ready:
            return ("Codex is not available.", None)
        tool_context = self.tool_registry.format_for_prompt()
        if dataset_id:
            tool_context = f"{tool_context}\nSelected dataset id: {dataset_id}"
        if self.workspace.project:
            tool_context = f"{tool_context}\nActive project: {self.workspace.project}"
        try:
            response = self.codex_client.run_tool_loop(
                message,
                tool_context=tool_context,
                execute_tool=self._execute_tool,
            )
            return (response or "No response.", None)
        except Exception as exc:
            return (f"Codex error: {exc}", None)

    def _execute_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        result = self.tool_registry.call(name, arguments)
        if result.effects:
            if "datasets" in result.effects:
                self.call_from_thread(self._refresh_dataset_list)
            if "plots" in result.effects:
                self.call_from_thread(self._refresh_plot_list)
            if "recipes" in result.effects:
                self.call_from_thread(self._refresh_recipe_list)
            if "projects" in result.effects:
                self.call_from_thread(self._refresh_project_select)
            if "reports" in result.effects:
                self.call_from_thread(self._load_summary)
        return {
            "ok": result.ok,
            "result": result.result,
            "error": result.error,
        }

    def _save_result_artifact(self, kind: str, payload: dict) -> str:
        artifact_id = generate_id("res")
        path = self.workspace.project_root() / "results" / f"{artifact_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": kind, "data": payload}, indent=2, sort_keys=True) + "\n")
        if self._selected_dataset_id:
            self.workspace.add_lineage_edge(self._selected_dataset_id, artifact_id, "result")
        self.workspace.commit(
            f"Record {kind} result",
            paths=[path.as_posix(), ".codexdatalab/lineage.json"],
        )
        return artifact_id


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
