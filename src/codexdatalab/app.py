from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class CodexDataLabApp(App):
    TITLE = "CodexDataLab"
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("CodexDataLab", id="title")
        yield Footer()

