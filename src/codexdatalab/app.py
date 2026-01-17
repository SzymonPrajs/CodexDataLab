from __future__ import annotations

from textual.app import App, ComposeResult
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
from .data_ops import list_datasets, preview_dataset
from .plot_ops import create_plot_definition, list_plots, load_plot_definition
from .plotting import PlotDefinition, render_plot
from .summary_ops import generate_summary_markdown
from .tool_harness import ToolHarness
import json

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
        self.tool_harness = ToolHarness(workspace)
        self.sub_title = str(workspace.root)
        state = self.workspace.load_state()
        self._help_visible = bool(state.get("ui", {}).get("help_visible", True))
        self._stats_visible = bool(state.get("ui", {}).get("stats_visible", True))
        self._lineage_visible = bool(state.get("ui", {}).get("lineage_visible", False))
        self._selected_dataset_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="root"):
            with Vertical(id="menu"):
                yield Label("Datasets", classes="title")
                yield Label("Select a dataset.", classes="subtitle")
                yield ListView(id="dataset-list")
                yield Label("Selected: —", id="dataset-meta", classes="meta")

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
                                    ],
                                    id="plot-type",
                                    value="scatter",
                                )
                                yield Label("x column", classes="subtitle")
                                yield Input(placeholder="x column", id="plot-x")
                                yield Label("y column (optional)", classes="subtitle")
                                yield Input(placeholder="y column", id="plot-y")
                                yield Button("Create Plot", id="plot-create")
                                yield Static("Plot details", id="plot-meta")
                                yield Label("Saved plots", classes="subtitle")
                                yield ListView(id="plot-list")
                            yield Static("Plot canvas", id="plot-canvas")
                    with TabPane("Summary", id="summary-tab"):
                        yield Markdown("", id="summary-view")
                        yield Button("Regenerate Summary", id="summary-refresh")

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
        self._refresh_dataset_list()
        self._refresh_plot_list()
        self._apply_stats_visibility()
        self._load_summary()
        self._set_status(f"Workspace loaded: {self.workspace.root}")

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

    def _load_summary(self) -> None:
        summary_path = self.workspace.root / "results" / "summary.md"
        summary_view = self.query_one("#summary-view", Markdown)
        if summary_path.exists():
            summary_view.update(summary_path.read_text())
        else:
            summary_view.update("")

    def _refresh_dataset_list(self) -> None:
        list_view = self.query_one("#dataset-list", ListView)
        list_view.clear()
        datasets = list_datasets(self.workspace)
        for dataset in datasets:
            dataset_id = dataset.get("id")
            label = dataset.get("name") or dataset_id
            list_view.append(ListItem(Label(f"{label} ({dataset.get('kind')})"), id=dataset_id))

    def _refresh_plot_list(self) -> None:
        list_view = self.query_one("#plot-list", ListView)
        list_view.clear()
        plots = list_plots(self.workspace)
        for plot in plots:
            plot_id = plot.get("id")
            label = plot.get("why") or plot_id
            list_view.append(ListItem(Label(label), id=plot_id))

    def _refresh_table(self) -> None:
        if not self._selected_dataset_id:
            return
        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id)
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
            top_values = ", ".join(
                f"{item.get(row['column'], item.get('column', ''))}:{item.get('counts', '')}"
                for item in row.get("top_values", [])
            )
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
        except Exception as exc:  # pragma: no cover
            self._set_status(f"Plot failed: {exc}")
            return
        definition = PlotDefinition(
            plot_type=plot_definition.get("plot_type", "scatter"),
            x=plot_definition.get("x"),
            y=plot_definition.get("y"),
            category=plot_definition.get("category"),
        )
        canvas = self.query_one("#plot-canvas", Static)
        canvas.update(render_plot(df, definition))
        meta = self.query_one("#plot-meta", Static)
        meta.update(f"Dataset: {dataset_id}\nType: {definition.plot_type}")

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
            self._refresh_table()
        elif event.list_view.id == "plot-list":
            if not event.item or not event.item.id:
                return
            plot_id = event.item.id
            definition = load_plot_definition(self.workspace, plot_id)
            self._render_plot(definition)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "plot-create":
            if not self._selected_dataset_id:
                self._set_status("Select a dataset before plotting.")
                return
            plot_type = self.query_one("#plot-type", Select).value or "scatter"
            x = self.query_one("#plot-x", Input).value.strip() or None
            y = self.query_one("#plot-y", Input).value.strip() or None
            definition = create_plot_definition(
                self.workspace,
                dataset_id=self._selected_dataset_id,
                plot_type=plot_type,
                x=x,
                y=y,
                category=None,
                why=f"{plot_type} plot",
            )
            self._render_plot(definition)
            self._refresh_plot_list()
            self._set_status(f"Plot created: {definition['id']}")
        elif event.button.id == "summary-refresh":
            summary = generate_summary_markdown(self.workspace)
            summary_path = self.workspace.root / "results" / "summary.md"
            summary_path.write_text(summary)
            summary_view = self.query_one("#summary-view", Markdown)
            summary_view.update(summary)
            self._set_status("Summary refreshed.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        message = event.value.strip()
        event.input.value = ""
        if not message:
            return
        self._append_chat(f"You: {message}")
        response, artifact_id = self._handle_chat_message(message)
        self._append_chat(f"Codex: {response}")
        self._record_answer(message, response, self._selected_dataset_id, artifact_id)

    def _handle_chat_message(self, message: str) -> tuple[str, str | None]:
        if message.startswith("/help"):
            return (
                "Commands: /datasets, /describe, /stats, /value_counts <col>, /groupby <col1,col2>",
                None,
            )
        if message.startswith("/datasets"):
            datasets = list_datasets(self.workspace)
            lines = [f"{ds.get('id')} — {ds.get('name')}" for ds in datasets]
            return ("Datasets:\\n" + "\\n".join(lines) if lines else "No datasets.", None)
        if not self._selected_dataset_id:
            return ("Select a dataset first.", None)

        try:
            df = preview_dataset(self.workspace, self._selected_dataset_id, max_rows=1000, max_cols=100)
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

        try:
            payload = numeric_summary(df)
        except Exception as exc:
            return f"Summary failed: {exc}", None
        artifact_id = self._save_result_artifact("summary", payload)
        return (
            f"I ran a quick numeric summary on the selected dataset (artifact {artifact_id}).",
            artifact_id,
        )

    def _save_result_artifact(self, kind: str, payload: dict) -> str:
        artifact_id = generate_id("res")
        path = self.workspace.root / "results" / f"{artifact_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": kind, "data": payload}, indent=2, sort_keys=True) + "\n")
        if self._selected_dataset_id:
            self.workspace.add_lineage_edge(self._selected_dataset_id, artifact_id, "result")
        self.workspace.commit(
            f"Record {kind} result",
            paths=[path.as_posix(), ".codexdatalab/lineage.json"],
        )
        return artifact_id
