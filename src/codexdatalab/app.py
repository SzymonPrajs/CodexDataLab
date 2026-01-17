from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListView, Static

from .tool_harness import ToolHarness
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
        ("?", "toggle_help", "Help"),
        ("enter", "pin_plot", "Pin"),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self.tool_harness = ToolHarness(workspace)
        self.sub_title = str(workspace.root)
        state = self.workspace.load_state()
        self._help_visible = bool(state.get("ui", {}).get("help_visible", True))

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="root"):
            with Vertical(id="menu"):
                yield Label("Plot Types", classes="title")
                yield Label("Use arrows to move, Enter to pin.", classes="subtitle")
                yield ListView(id="plot-list")
                yield Label("Selected: —", id="plot-meta", classes="meta")

            with Vertical(id="right"):
                with Vertical(id="plot"):
                    yield Label("Plot", id="plot-title", classes="title")
                    yield Label("x: — | y: —", id="plot-subtitle", classes="subtitle")
                    yield Label("Plot details go here.", id="plot-info", classes="meta")
                    with Horizontal(id="plot-body"):
                        yield Static("Plot canvas", id="plot-canvas")
                        yield Static("Stats panel", id="plot-stats")

                with Vertical(id="chat"):
                    yield Label("Chat", classes="title")
                    yield Label("Tab switches focus between menu and input.", classes="subtitle")
                    yield Input(placeholder="> Ask me anything...", id="chat-input")
                    yield Label("Tip: Ctrl+T for full chat, Ctrl+G for full plot.", classes="hint")
                    yield Label("", id="status", classes="status")
                    yield Label(
                        "Shortcuts: Ctrl+G plot, Ctrl+B split, Ctrl+F menu, Tab focus, ? help",
                        id="help",
                        classes="help",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self._apply_help_visibility()
        self._set_status(f"Workspace loaded: {self.workspace.root}")

    def action_toggle_plot(self) -> None:
        self._set_status("Plot toggle not implemented yet.")

    def action_toggle_chat(self) -> None:
        self._set_status("Chat toggle not implemented yet.")

    def action_split_view(self) -> None:
        self._set_status("Split view not implemented yet.")

    def action_toggle_menu(self) -> None:
        self._set_status("Menu toggle not implemented yet.")

    def action_toggle_focus(self) -> None:
        chat_input = self.query_one("#chat-input", Input)
        plot_list = self.query_one("#plot-list", ListView)
        if self.focused is chat_input:
            plot_list.focus()
            self._set_status("Focus: menu")
        else:
            chat_input.focus()
            self._set_status("Focus: chat")

    def action_toggle_help(self) -> None:
        self._help_visible = not self._help_visible
        self._apply_help_visibility()
        self.workspace.update_ui_state("help_visible", self._help_visible)
        state = "shown" if self._help_visible else "hidden"
        self._set_status(f"Help {state}.")

    def action_pin_plot(self) -> None:
        self._set_status("Pin plot not implemented yet.")

    def _apply_help_visibility(self) -> None:
        help_label = self.query_one("#help", Label)
        help_label.display = self._help_visible

    def _set_status(self, message: str) -> None:
        status_label = self.query_one("#status", Label)
        status_label.update(f"Status: {message}")
