from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListView, Static


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
                    yield Label("Status: Ready", id="status", classes="status")
                    yield Label(
                        "Shortcuts: Ctrl+G plot, Ctrl+B split, Ctrl+F menu, Tab focus, ? help",
                        id="help",
                        classes="help",
                    )
        yield Footer()

    def action_toggle_plot(self) -> None:
        pass

    def action_toggle_chat(self) -> None:
        pass

    def action_split_view(self) -> None:
        pass

    def action_toggle_menu(self) -> None:
        pass

    def action_toggle_focus(self) -> None:
        pass

    def action_toggle_help(self) -> None:
        pass

    def action_pin_plot(self) -> None:
        pass
