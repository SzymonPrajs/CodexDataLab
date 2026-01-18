from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from rich.text import Text

import polars as pl

BRAILLE_BASE = 0x2800
SERIES_COLORS = [
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "bright_red",
    "bright_green",
    "bright_blue",
]


@dataclass
class PlotDefinition:
    plot_type: str
    x: str | None = None
    y: str | None = None
    category: str | None = None
    fit: bool = False


def render_plot(
    df: pl.DataFrame, definition: PlotDefinition, width: int = 60, height: int = 20
) -> Text | str:
    plot_type = definition.plot_type
    if plot_type == "scatter":
        return _braille_scatter(df, definition.x, definition.y, definition.category, definition.fit, width, height)
    if plot_type == "line":
        return _braille_line(df, definition.x, definition.y, definition.category, definition.fit, width, height)
    if plot_type == "bar":
        return _braille_bar(df, definition.x, definition.y, width, height)
    if plot_type == "hist":
        return _braille_hist(df, definition.x, width, height)
    if plot_type == "violin":
        return _braille_violin(df, definition.x, width, height)
    if plot_type == "error_bar":
        return _braille_error_bar(df, definition.x, definition.y, width, height)
    return "Unsupported plot type."


def _braille_scatter(
    df: pl.DataFrame,
    x: str | None,
    y: str | None,
    category: str | None,
    fit: bool,
    width: int,
    height: int,
) -> Text | str:
    if not x or not y:
        return "Select x and y columns."
    if x not in df.columns or y not in df.columns:
        return "Columns not found."

    series = _series_points(df, x, y, category)
    return _braille_points(series, width, height, fit=fit)


def _braille_line(
    df: pl.DataFrame,
    x: str | None,
    y: str | None,
    category: str | None,
    fit: bool,
    width: int,
    height: int,
) -> Text | str:
    if not x or not y:
        return "Select x and y columns."
    if x not in df.columns or y not in df.columns:
        return "Columns not found."

    series = _series_points(df, x, y, category)
    return _braille_lines(series, width, height, fit=fit)


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
    count_col = "counts" if "counts" in hist.columns else "count"
    values = hist[count_col].to_list()
    categories = list(range(1, len(values) + 1))
    return _braille_bars(categories, values, width, height)

def _series_points(
    df: pl.DataFrame, x: str, y: str, category: str | None
) -> dict[str, list[tuple[float, float]]]:
    if not category or category not in df.columns:
        points = list(zip(df[x].to_list(), df[y].to_list()))
        return {"series": points}
    series: dict[str, list[tuple[float, float]]] = {}
    for x_val, y_val, cat in zip(df[x].to_list(), df[y].to_list(), df[category].to_list()):
        key = str(cat)
        series.setdefault(key, []).append((x_val, y_val))
    return series


def _braille_points(
    series: Mapping[str, Sequence[tuple[float, float]]],
    width: int,
    height: int,
    *,
    fit: bool = False,
) -> Text | str:
    cleaned_series: dict[str, list[tuple[float, float]]] = {}
    all_points: list[tuple[float, float]] = []
    for name, points in series.items():
        cleaned = []
        for x_val, y_val in points:
            try:
                cleaned.append((float(x_val), float(y_val)))
            except (TypeError, ValueError):
                continue
        if cleaned:
            cleaned_series[name] = cleaned
            all_points.extend(cleaned)
    if not all_points:
        return "No data."
    x_values = [p[0] for p in all_points]
    y_values = [p[1] for p in all_points]
    canvas = _BrailleCanvas(width, height, min(x_values), max(x_values), min(y_values), max(y_values))
    legend: list[tuple[str, str]] = []
    for idx, (name, points) in enumerate(cleaned_series.items()):
        color = SERIES_COLORS[idx % len(SERIES_COLORS)]
        legend.append((name, color))
        for x_val, y_val in points:
            canvas.set_point(x_val, y_val, color=color)

    if fit:
        fit_line = _linear_fit(all_points)
        if fit_line is not None:
            slope, intercept = fit_line
            x_min = min(x_values)
            x_max = max(x_values)
            canvas.draw_line(x_min, slope * x_min + intercept, x_max, slope * x_max + intercept, color="bright_white")

    return _render_with_legend(canvas, legend)


def _braille_lines(
    series: Mapping[str, Sequence[tuple[float, float]]],
    width: int,
    height: int,
    *,
    fit: bool = False,
) -> Text | str:
    cleaned_series: dict[str, list[tuple[float, float]]] = {}
    all_points: list[tuple[float, float]] = []
    for name, points in series.items():
        cleaned = []
        for x_val, y_val in points:
            try:
                cleaned.append((float(x_val), float(y_val)))
            except (TypeError, ValueError):
                continue
        if cleaned:
            cleaned.sort(key=lambda item: item[0])
            cleaned_series[name] = cleaned
            all_points.extend(cleaned)
    if not all_points:
        return "No data."
    x_values = [p[0] for p in all_points]
    y_values = [p[1] for p in all_points]
    canvas = _BrailleCanvas(width, height, min(x_values), max(x_values), min(y_values), max(y_values))
    legend: list[tuple[str, str]] = []
    for idx, (name, points) in enumerate(cleaned_series.items()):
        color = SERIES_COLORS[idx % len(SERIES_COLORS)]
        legend.append((name, color))
        last = None
        for x_val, y_val in points:
            if last is None:
                canvas.set_point(x_val, y_val, color=color)
            else:
                canvas.draw_line(last[0], last[1], x_val, y_val, color=color)
            last = (x_val, y_val)

    if fit:
        fit_line = _linear_fit(all_points)
        if fit_line is not None:
            slope, intercept = fit_line
            x_min = min(x_values)
            x_max = max(x_values)
            canvas.draw_line(x_min, slope * x_min + intercept, x_max, slope * x_max + intercept, color="bright_white")

    return _render_with_legend(canvas, legend)


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


def _braille_violin(df: pl.DataFrame, x: str | None, width: int, height: int) -> Text | str:
    if not x:
        return "Select x column."
    if x not in df.columns:
        return "Columns not found."
    series = df[x]
    if not series.dtype.is_numeric():
        return "Violin plot requires a numeric column."
    bins = 12
    hist = series.hist(bins=bins)
    count_col = "counts" if "counts" in hist.columns else "count"
    counts = hist[count_col].to_list()
    if not counts:
        return "No data."
    max_count = max(counts) or 1
    canvas = _BrailleCanvas(width, height, -max_count, max_count, 0.0, float(len(counts) - 1))
    for idx, count in enumerate(counts):
        canvas.draw_line(-float(count), float(idx), float(count), float(idx), color="magenta")
    return canvas.render()


def _braille_error_bar(
    df: pl.DataFrame, x: str | None, y: str | None, width: int, height: int
) -> Text | str:
    if not x or not y:
        return "Select x and y columns."
    if x not in df.columns or y not in df.columns:
        return "Columns not found."
    if not df[y].dtype.is_numeric():
        return "Error bars require a numeric y column."
    grouped = df.group_by(x).agg(
        [
            pl.col(y).mean().alias("mean"),
            pl.col(y).std().alias("std"),
        ]
    )
    categories = grouped[x].to_list()
    means = grouped["mean"].to_list()
    stds = grouped["std"].fill_null(0).to_list()
    if not means:
        return "No data."
    max_val = max((m + s) for m, s in zip(means, stds)) or 1
    canvas = _BrailleCanvas(width, height, 0.0, float(len(categories)), 0.0, float(max_val))
    bar_width = max(0.5, 0.8)
    for idx, (mean, std) in enumerate(zip(means, stds)):
        x_center = idx + 0.5
        canvas.fill_rect_value(x_center - bar_width / 2, x_center + bar_width / 2, float(mean), color="cyan")
        lower = max(0.0, float(mean) - float(std))
        upper = float(mean) + float(std)
        canvas.draw_line(x_center, lower, x_center, upper, color="bright_white")
    legend = [("mean", "cyan"), ("std", "bright_white")]
    return _render_with_legend(canvas, legend)


def _render_with_legend(canvas: _BrailleCanvas, legend: list[tuple[str, str]]) -> Text | str:
    renderable = canvas.render()
    if not legend:
        return renderable
    if isinstance(renderable, str):
        lines = [renderable, "", "Legend:"]
        for label, _color in legend:
            lines.append(f"- {label}")
        return "\n".join(lines)
    text = Text.assemble(renderable, "\n\nLegend:\n")
    for label, color in legend:
        text.append("● ", style=color)
        text.append(label)
        text.append("\n")
    return text


def _linear_fit(points: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    if len(points) < 2:
        return None
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    n = float(len(points))
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return None
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


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
        self.cell_colors: list[list[str | None]] = [
            [None for _ in range(self.width)] for _ in range(self.height)
        ]

    def _normalize(self, x: float, y: float) -> tuple[int, int]:
        x_norm = (x - self.x_min) / (self.x_max - self.x_min)
        y_norm = (y - self.y_min) / (self.y_max - self.y_min)
        col = int(round(x_norm * (self.dot_width - 1)))
        row = int(round((1 - y_norm) * (self.dot_height - 1)))
        return col, row

    def _normalize_x(self, x: float) -> int:
        x_norm = (x - self.x_min) / (self.x_max - self.x_min)
        return int(round(x_norm * (self.dot_width - 1)))

    def _normalize_y(self, y: float) -> int:
        y_norm = (y - self.y_min) / (self.y_max - self.y_min)
        return int(round((1 - y_norm) * (self.dot_height - 1)))

    def set_point(self, x: float, y: float, *, color: str | None = None) -> None:
        col, row = self._normalize(float(x), float(y))
        if 0 <= row < self.dot_height and 0 <= col < self.dot_width:
            self.grid[row][col] = 1
            if color:
                cell_row = row // 4
                cell_col = col // 2
                if 0 <= cell_row < self.height and 0 <= cell_col < self.width:
                    self.cell_colors[cell_row][cell_col] = color

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float, *, color: str | None = None
    ) -> None:
        c1, r1 = self._normalize(float(x1), float(y1))
        c2, r2 = self._normalize(float(x2), float(y2))
        steps = max(abs(c2 - c1), abs(r2 - r1), 1)
        for step in range(steps + 1):
            col = int(round(c1 + (c2 - c1) * step / steps))
            row = int(round(r1 + (r2 - r1) * step / steps))
            if 0 <= row < self.dot_height and 0 <= col < self.dot_width:
                self.grid[row][col] = 1
                if color:
                    cell_row = row // 4
                    cell_col = col // 2
                    if 0 <= cell_row < self.height and 0 <= cell_col < self.width:
                        self.cell_colors[cell_row][cell_col] = color

    def fill_rect(self, x_start: int, x_end: int, height_ratio: float, *, color: str | None = None) -> None:
        height_ratio = max(0.0, min(1.0, height_ratio))
        filled_rows = int(round(height_ratio * (self.dot_height - 1)))
        for row in range(self.dot_height - 1, self.dot_height - 1 - filled_rows, -1):
            if row < 0:
                break
            for col in range(x_start, x_end + 1):
                if 0 <= col < self.dot_width:
                    self.grid[row][col] = 1
                    if color:
                        cell_row = row // 4
                        cell_col = col // 2
                        if 0 <= cell_row < self.height and 0 <= cell_col < self.width:
                            self.cell_colors[cell_row][cell_col] = color

    def fill_rect_value(
        self, x_start: float, x_end: float, y_value: float, *, color: str | None = None
    ) -> None:
        col_start = self._normalize_x(float(x_start))
        col_end = self._normalize_x(float(x_end))
        if col_end < col_start:
            col_start, col_end = col_end, col_start
        row_top = self._normalize_y(float(y_value))
        for row in range(row_top, self.dot_height):
            for col in range(col_start, col_end + 1):
                if 0 <= row < self.dot_height and 0 <= col < self.dot_width:
                    self.grid[row][col] = 1
                    if color:
                        cell_row = row // 4
                        cell_col = col // 2
                        if 0 <= cell_row < self.height and 0 <= cell_col < self.width:
                            self.cell_colors[cell_row][cell_col] = color

    def render(self) -> Text | str:
        lines = []
        any_color = any(any(cell for cell in row) for row in self.cell_colors)
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
        if not any_color:
            return "\n".join(lines)
        text = Text()
        for row_idx, line in enumerate(lines):
            for col_idx, ch in enumerate(line):
                style = self.cell_colors[row_idx][col_idx]
                text.append(ch, style=style)
            if row_idx < len(lines) - 1:
                text.append("\n")
        return text


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
