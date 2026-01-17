from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import polars as pl

BRAILLE_BASE = 0x2800


@dataclass
class PlotDefinition:
    plot_type: str
    x: str | None = None
    y: str | None = None
    category: str | None = None


def render_plot(df: pl.DataFrame, definition: PlotDefinition, width: int = 60, height: int = 20) -> str:
    plot_type = definition.plot_type
    if plot_type == "scatter":
        return _braille_scatter(df, definition.x, definition.y, width, height)
    if plot_type == "line":
        return _braille_line(df, definition.x, definition.y, width, height)
    if plot_type == "bar":
        return _braille_bar(df, definition.x, definition.y, width, height)
    if plot_type == "hist":
        return _braille_hist(df, definition.x, width, height)
    return "Unsupported plot type."


def _braille_scatter(df: pl.DataFrame, x: str | None, y: str | None, width: int, height: int) -> str:
    if not x or not y:
        return "Select x and y columns."
    if x not in df.columns or y not in df.columns:
        return "Columns not found."

    points = list(zip(df[x].to_list(), df[y].to_list()))
    return _braille_points(points, width, height)


def _braille_line(df: pl.DataFrame, x: str | None, y: str | None, width: int, height: int) -> str:
    if not x or not y:
        return "Select x and y columns."
    if x not in df.columns or y not in df.columns:
        return "Columns not found."

    points = list(zip(df[x].to_list(), df[y].to_list()))
    points.sort(key=lambda item: item[0])
    return _braille_lines(points, width, height)


def _braille_bar(df: pl.DataFrame, x: str | None, y: str | None, width: int, height: int) -> str:
    if not x:
        return "Select x column."
    if x not in df.columns:
        return "Columns not found."

    if y and y in df.columns and df[y].dtype.is_numeric():
        grouped = df.group_by(x).agg(pl.col(y).mean().alias("value")).sort("value")
    else:
        grouped = df.group_by(x).len().rename({"len": "value"}).sort("value")

    categories = grouped[x].to_list()
    values = grouped["value"].to_list()
    return _braille_bars(categories, values, width, height)


def _braille_hist(df: pl.DataFrame, x: str | None, width: int, height: int) -> str:
    if not x:
        return "Select x column."
    if x not in df.columns:
        return "Columns not found."

    series = df[x]
    if not series.dtype.is_numeric():
        return "Histogram requires a numeric column."
    bins = 10
    hist = series.hist(bins=bins)
    values = hist["counts"].to_list()
    categories = list(range(1, len(values) + 1))
    return _braille_bars(categories, values, width, height)


def _braille_points(points: Iterable[tuple[float, float]], width: int, height: int) -> str:
    cleaned = []
    for x, y in points:
        try:
            cleaned.append((float(x), float(y)))
        except (TypeError, ValueError):
            continue
    points = cleaned
    if not points:
        return "No data."
    x_values = [p[0] for p in points]
    y_values = [p[1] for p in points]
    canvas = _BrailleCanvas(width, height, min(x_values), max(x_values), min(y_values), max(y_values))
    for x, y in points:
        canvas.set_point(x, y)
    return canvas.render()


def _braille_lines(points: Iterable[tuple[float, float]], width: int, height: int) -> str:
    cleaned = []
    for x, y in points:
        try:
            cleaned.append((float(x), float(y)))
        except (TypeError, ValueError):
            continue
    points = cleaned
    if not points:
        return "No data."
    x_values = [p[0] for p in points]
    y_values = [p[1] for p in points]
    canvas = _BrailleCanvas(width, height, min(x_values), max(x_values), min(y_values), max(y_values))
    last = None
    for x, y in points:
        if last is None:
            canvas.set_point(x, y)
        else:
            canvas.draw_line(last[0], last[1], x, y)
        last = (x, y)
    return canvas.render()


def _braille_bars(categories: list, values: list[float], width: int, height: int) -> str:
    if not values:
        return "No data."
    canvas = _BrailleCanvas(width, height, 0.0, 1.0, 0.0, 1.0)
    max_val = max(values) or 1
    bar_width = max(1, (width * 2) // max(1, len(values)))
    for idx, value in enumerate(values):
        height_ratio = value / max_val
        x_start = idx * bar_width
        x_end = min((idx + 1) * bar_width - 1, width * 2 - 1)
        canvas.fill_rect(x_start, x_end, height_ratio)
    return canvas.render()


class _BrailleCanvas:
    def __init__(
        self, width: int, height: int, x_min: float, x_max: float, y_min: float, y_max: float
    ) -> None:
        self.width = width
        self.height = height
        self.x_min = x_min
        self.x_max = x_max if x_max != x_min else x_min + 1.0
        self.y_min = y_min
        self.y_max = y_max if y_max != y_min else y_min + 1.0
        self.dot_width = width * 2
        self.dot_height = height * 4
        self.grid = [[0 for _ in range(self.dot_width)] for _ in range(self.dot_height)]

    def _normalize(self, x: float, y: float) -> tuple[int, int]:
        x_norm = (x - self.x_min) / (self.x_max - self.x_min)
        y_norm = (y - self.y_min) / (self.y_max - self.y_min)
        col = int(round(x_norm * (self.dot_width - 1)))
        row = int(round((1 - y_norm) * (self.dot_height - 1)))
        return col, row

    def set_point(self, x: float, y: float) -> None:
        col, row = self._normalize(float(x), float(y))
        if 0 <= row < self.dot_height and 0 <= col < self.dot_width:
            self.grid[row][col] = 1

    def draw_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        c1, r1 = self._normalize(float(x1), float(y1))
        c2, r2 = self._normalize(float(x2), float(y2))
        steps = max(abs(c2 - c1), abs(r2 - r1), 1)
        for step in range(steps + 1):
            col = int(round(c1 + (c2 - c1) * step / steps))
            row = int(round(r1 + (r2 - r1) * step / steps))
            if 0 <= row < self.dot_height and 0 <= col < self.dot_width:
                self.grid[row][col] = 1

    def fill_rect(self, x_start: int, x_end: int, height_ratio: float) -> None:
        height_ratio = max(0.0, min(1.0, height_ratio))
        filled_rows = int(round(height_ratio * (self.dot_height - 1)))
        for row in range(self.dot_height - 1, self.dot_height - 1 - filled_rows, -1):
            if row < 0:
                break
            for col in range(x_start, x_end + 1):
                if 0 <= col < self.dot_width:
                    self.grid[row][col] = 1

    def render(self) -> str:
        lines = []
        for char_row in range(self.height):
            line_chars = []
            for char_col in range(self.width):
                dots = 0
                for dy in range(4):
                    for dx in range(2):
                        row = char_row * 4 + dy
                        col = char_col * 2 + dx
                        if self.grid[row][col]:
                            dots |= _dot_mask(dx, dy)
                line_chars.append(chr(BRAILLE_BASE + dots))
            lines.append("".join(line_chars))
        return "\n".join(lines)


def _dot_mask(dx: int, dy: int) -> int:
    mapping = {
        (0, 0): 0x01,
        (0, 1): 0x02,
        (0, 2): 0x04,
        (0, 3): 0x40,
        (1, 0): 0x08,
        (1, 1): 0x10,
        (1, 2): 0x20,
        (1, 3): 0x80,
    }
    return mapping[(dx, dy)]
