#!/usr/bin/env python3
"""Render a slide spec JSON file into a styled 16:9 SVG slide.

Implements the visual system in references/style-system.md for a subset of
patterns from references/visualization-patterns.md:

    waterfall, gap, before_after, time_series, benchmark_table,
    summary_strip, process_flow, funnel, heatmap, gantt, kpi_scorecard,
    two_by_two

Usage:
    python3 scripts/render_slide_spec.py examples/render-specs/arr-waterfall.json -o out.svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Canvas
W, H = 1280, 720
ML, MR = 80, 80
CHART_TOP, CHART_BOTTOM = 210, 560

# Palette (references/style-system.md)
BLUE = "#1E3A8A"
BLUE2 = "#2563EB"
BLACK = "#000000"
GREY_DARK = "#374151"
GREY_MED = "#6B7280"
GREY_BORDER = "#D1D5DB"
GREY_FILL = "#F3F4F6"
RED = "#B91C1C"

SERIF = "Georgia, 'Times New Roman', serif"
SANS = "'Helvetica Neue', Helvetica, Arial, sans-serif"


class RenderSpecError(ValueError):
    """Raised when a slide spec is structurally invalid."""


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in str(text).split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def fmt(value: float, unit: str) -> str:
    text = f"{value:,.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    if not unit:
        return text
    if unit[0] in "$€£¥":
        return f"{unit[0]}{text}{unit[1:]}"
    return f"{text}{unit}"


def text_el(
    x: float,
    y: float,
    content: str,
    size: int = 14,
    fill: str = BLACK,
    weight: str = "normal",
    family: str = SANS,
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{esc(content)}</text>'
    )


def rect_el(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none") -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}"/>'
    )


def line_el(x1: float, y1: float, x2: float, y2: float, stroke: str = GREY_BORDER, dash: str = "") -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}"{dash_attr}/>'


def header(spec: dict) -> list[str]:
    parts = [rect_el(ML, 52, 56, 5, BLUE)]
    headline = spec.get("headline", "")
    lines = wrap(headline, 64)
    size, line_h = 30, 40
    if len(lines) > 2:
        lines = wrap(headline, 80)[:3]
        size, line_h = 24, 32
    y = 96
    for line in lines:
        parts.append(text_el(ML, y, line, size=size, weight="bold", family=SERIF))
        y += line_h
    subline = spec.get("subline", "")
    if subline:
        parts.append(text_el(ML, y + 2, subline, size=17, fill=GREY_MED))
    return parts


def footer(spec: dict) -> list[str]:
    parts: list[str] = []
    annotation = spec.get("annotation", "")
    if annotation:
        parts.append(rect_el(ML, 612, 4, 40, BLUE))
        y = 630
        for line in wrap(annotation, 110)[:2]:
            parts.append(text_el(ML + 16, y, line, size=16, fill=BLUE, weight="600"))
            y += 22
    source = spec.get("source", "")
    if source:
        parts.append(text_el(ML, 692, source, size=12, fill=GREY_MED))
    return parts


def render_waterfall(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    start = spec["start"]
    drivers = spec["drivers"]
    end_value = start["value"] + sum(d["value"] for d in drivers)
    end_label = spec.get("end_label", "End")

    cumulative = [start["value"]]
    for driver in drivers:
        cumulative.append(cumulative[-1] + driver["value"])
    top = max(max(cumulative), start["value"], end_value) * 1.18 or 1

    n = len(drivers) + 2
    span = W - ML - MR
    bar_w = min(110.0, span / n * 0.62)
    step = span / n

    def x_at(i: int) -> float:
        return ML + step * i + (step - bar_w) / 2

    def y_at(value: float) -> float:
        return CHART_BOTTOM - (value / top) * (CHART_BOTTOM - CHART_TOP)

    parts = [line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK)]

    def bar(i: int, base: float, value_top: float, fill: str, label: str, value_text: str) -> None:
        x = x_at(i)
        y1, y2 = y_at(max(base, value_top)), y_at(min(base, value_top))
        parts.append(rect_el(x, y1, bar_w, max(y2 - y1, 2), fill))
        parts.append(text_el(x + bar_w / 2, y1 - 10, value_text, size=15, weight="bold", anchor="middle"))
        for j, line in enumerate(wrap(label, 16)[:2]):
            parts.append(
                text_el(x + bar_w / 2, CHART_BOTTOM + 22 + j * 16, line, size=13, fill=GREY_DARK, anchor="middle")
            )

    bar(0, 0, start["value"], BLUE, start["label"], fmt(start["value"], unit))
    running = start["value"]
    for i, driver in enumerate(drivers, start=1):
        value = driver["value"]
        fill = BLUE2 if value >= 0 else RED
        sign = "+" if value >= 0 else "−"
        bar(i, running, running + value, fill, driver["label"], f"{sign}{fmt(abs(value), unit)}")
        parts.append(line_el(x_at(i - 1) + bar_w, y_at(running), x_at(i), y_at(running), GREY_BORDER, "4 3"))
        running += value
    parts.append(line_el(x_at(n - 2) + bar_w, y_at(running), x_at(n - 1), y_at(running), GREY_BORDER, "4 3"))
    bar(n - 1, 0, end_value, BLUE, end_label, fmt(end_value, unit))
    return parts


def render_gap(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    items = spec["items"]
    top = max(item["value"] for item in items) or 1
    span = W - ML - MR - 280
    row_h = min(86.0, (CHART_BOTTOM - CHART_TOP) / len(items))
    bar_h = row_h * 0.52

    parts: list[str] = []
    for i, item in enumerate(items):
        y = CHART_TOP + 30 + i * row_h
        width = span * item["value"] / top
        fill = BLUE if item.get("emphasis") else GREY_FILL
        stroke = "none" if item.get("emphasis") else GREY_BORDER
        label_lines = wrap(item["label"], 25)[:2]
        label_y = y + bar_h / 2 + 5 - (len(label_lines) - 1) * 9
        for line in label_lines:
            parts.append(text_el(ML, label_y, line, size=16, fill=GREY_DARK))
            label_y += 19
        parts.append(rect_el(ML + 220, y, width, bar_h, fill, stroke))
        value_fill = BLUE if item.get("emphasis") else GREY_DARK
        parts.append(
            text_el(ML + 232 + width, y + bar_h / 2 + 6, fmt(item["value"], unit), size=17, fill=value_fill, weight="bold")
        )
    gap_label = spec.get("gap_label", "")
    if gap_label:
        parts.append(text_el(W - MR, CHART_TOP + 6, gap_label, size=18, fill=BLUE, weight="bold", anchor="end"))
    return parts


def render_before_after(spec: dict) -> list[str]:
    pairs = spec["pairs"]
    top = max(max(p["before"], p["after"]) for p in pairs) * 1.15 or 1
    span = W - ML - MR
    step = span / len(pairs)
    bar_w = min(72.0, step * 0.24)

    def y_at(value: float) -> float:
        return CHART_BOTTOM - (value / top) * (CHART_BOTTOM - CHART_TOP)

    parts = [line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK)]
    for i, pair in enumerate(pairs):
        unit = pair.get("unit", spec.get("unit", ""))
        cx = ML + step * i + step / 2
        bx, ax = cx - bar_w - 8, cx + 8
        by, ay = y_at(pair["before"]), y_at(pair["after"])
        parts.append(rect_el(bx, by, bar_w, CHART_BOTTOM - by, GREY_FILL, GREY_BORDER))
        parts.append(rect_el(ax, ay, bar_w, CHART_BOTTOM - ay, BLUE))
        parts.append(text_el(bx + bar_w / 2, by - 8, fmt(pair["before"], unit), size=14, fill=GREY_MED, anchor="middle"))
        parts.append(text_el(ax + bar_w / 2, ay - 8, fmt(pair["after"], unit), size=15, weight="bold", anchor="middle"))
        delta = pair["after"] - pair["before"]
        sign = "+" if delta >= 0 else "−"
        parts.append(
            text_el(cx, min(by, ay) - 32, f"{sign}{fmt(abs(delta), unit)}", size=15, fill=BLUE2, weight="bold", anchor="middle")
        )
        for j, line in enumerate(wrap(pair["label"], 22)[:2]):
            parts.append(text_el(cx, CHART_BOTTOM + 24 + j * 17, line, size=14, fill=GREY_DARK, anchor="middle"))
    legend_y = CHART_TOP - 16
    parts.append(rect_el(W - MR - 230, legend_y - 11, 14, 14, GREY_FILL, GREY_BORDER))
    parts.append(text_el(W - MR - 210, legend_y, spec.get("before_label", "Before"), size=13, fill=GREY_MED))
    parts.append(rect_el(W - MR - 120, legend_y - 11, 14, 14, BLUE))
    parts.append(text_el(W - MR - 100, legend_y, spec.get("after_label", "After"), size=13, fill=GREY_DARK))
    return parts


def render_time_series(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    labels = spec["x_labels"]
    values = spec["series"][0]["values"]
    top = max(values) * 1.2 or 1
    span = W - ML - MR

    def pt(i: int) -> tuple[float, float]:
        x = ML + span * (i / max(len(values) - 1, 1))
        y = CHART_BOTTOM - (values[i] / top) * (CHART_BOTTOM - CHART_TOP)
        return x, y

    parts = [line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK)]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i) for i in range(len(values))))
    parts.append(f'<polyline points="{points}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
    for i, value in enumerate(values):
        x, y = pt(i)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{BLUE}"/>')
        parts.append(text_el(x, y - 14, fmt(value, unit), size=14, weight="bold", anchor="middle"))
        parts.append(text_el(x, CHART_BOTTOM + 24, labels[i], size=13, fill=GREY_DARK, anchor="middle"))
    parts.append(text_el(ML, CHART_TOP - 16, spec["series"][0].get("label", ""), size=13, fill=GREY_MED))
    return parts


def render_benchmark_table(spec: dict) -> list[str]:
    columns = spec["columns"]
    rows = spec["rows"]
    leaders = {tuple(pair) for pair in spec.get("leaders", [])}
    label_w = 230.0
    col_w = (W - ML - MR - label_w) / len(columns)
    row_h = min(64.0, (CHART_BOTTOM + 40 - CHART_TOP) / (len(rows) + 1))
    top_y = CHART_TOP - 10

    parts: list[str] = []
    for j, column in enumerate(columns):
        cx = ML + label_w + col_w * j + col_w / 2
        for k, line in enumerate(wrap(column, 18)[:2]):
            parts.append(text_el(cx, top_y + 20 + k * 15, line, size=13, fill=GREY_MED, weight="600", anchor="middle"))
    parts.append(line_el(ML, top_y + row_h, W - MR, top_y + row_h, GREY_DARK))
    for i, row in enumerate(rows):
        y = top_y + row_h * (i + 1)
        parts.append(text_el(ML, y + row_h / 2 + 6, row["label"], size=15, fill=BLACK, weight="600"))
        for j, value in enumerate(row["values"]):
            cx = ML + label_w + col_w * j + col_w / 2
            if (i, j) in leaders:
                parts.append(rect_el(ML + label_w + col_w * j + 6, y + 7, col_w - 12, row_h - 14, BLUE))
                parts.append(text_el(cx, y + row_h / 2 + 6, str(value), size=15, fill="#FFFFFF", weight="bold", anchor="middle"))
            else:
                parts.append(text_el(cx, y + row_h / 2 + 6, str(value), size=15, fill=GREY_DARK, anchor="middle"))
        parts.append(line_el(ML, y + row_h, W - MR, y + row_h, GREY_BORDER))
    return parts


def render_summary_strip(spec: dict) -> list[str]:
    blocks = spec["blocks"]
    span = W - ML - MR
    col_w = span / len(blocks)

    parts: list[str] = []
    strip_top = CHART_TOP + 50
    for i, block in enumerate(blocks):
        x = ML + col_w * i
        if i > 0:
            parts.append(line_el(x, strip_top - 40, x, strip_top + 230, GREY_BORDER))
        inner_x, text_width = x + (18 if i else 0), int(col_w / 8.2)
        y = strip_top + 18
        parts.append(rect_el(inner_x, y - 24, 28, 4, BLUE))
        for line in wrap(block["claim"], text_width)[:3]:
            parts.append(text_el(inner_x, y, line, size=17, weight="bold"))
            y += 23
        y += 8
        for line in wrap(block["proof"], text_width)[:4]:
            parts.append(text_el(inner_x, y, line, size=14, fill=GREY_MED))
            y += 19
        y += 10
        for line in wrap(block["implication"], text_width)[:3]:
            parts.append(text_el(inner_x, y, line, size=14, fill=BLUE, weight="600"))
            y += 19
    return parts


def render_process_flow(spec: dict) -> list[str]:
    steps = spec["steps"]
    highlight = spec.get("highlight", -1)
    span = W - ML - MR
    gap = 26.0
    box_w = (span - gap * (len(steps) - 1)) / len(steps)
    box_h, y = 130.0, (CHART_TOP + CHART_BOTTOM) / 2 - 65

    parts: list[str] = []
    for i, step in enumerate(steps):
        x = ML + i * (box_w + gap)
        is_hot = i == highlight
        parts.append(rect_el(x, y, box_w, box_h, BLUE if is_hot else GREY_FILL, "none" if is_hot else GREY_BORDER))
        title_fill = "#FFFFFF" if is_hot else BLACK
        detail_fill = "#E5E7EB" if is_hot else GREY_MED
        ty, text_width = y + 34, int(box_w / 7.6)
        parts.append(text_el(x + 16, ty - 14, f"{i + 1:02d}", size=13, fill=BLUE2 if not is_hot else "#E5E7EB", weight="bold"))
        for line in wrap(step["label"], text_width)[:2]:
            parts.append(text_el(x + 16, ty + 8, line, size=16, fill=title_fill, weight="bold"))
            ty += 21
        for line in wrap(step.get("detail", ""), text_width)[:3]:
            parts.append(text_el(x + 16, ty + 12, line, size=13, fill=detail_fill))
            ty += 17
        if i < len(steps) - 1:
            ax = x + box_w + gap / 2
            ay = y + box_h / 2
            parts.append(
                f'<path d="M {ax - 7:.1f} {ay - 8:.1f} L {ax + 7:.1f} {ay:.1f} L {ax - 7:.1f} {ay + 8:.1f} Z" fill="{GREY_MED}"/>'
            )
    return parts


def _lerp_color(start: str, end: str, t: float) -> str:
    s = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
    e = [int(end[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(s[i] + (e[i] - s[i]) * t):02X}" for i in range(3))


def render_funnel(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    stages = spec["stages"]
    top_value = max(s["value"] for s in stages) or 1
    row_h = (CHART_BOTTOM - CHART_TOP) / len(stages)
    bar_h = min(row_h * 0.66, 60.0)
    span = W - ML - MR - 330
    cx = ML + 210 + span / 2

    parts: list[str] = []
    for i, stage in enumerate(stages):
        y = CHART_TOP + row_h * i + (row_h - bar_h) / 2
        bw = max(span * stage["value"] / top_value, 6)
        parts.append(rect_el(cx - bw / 2, y, bw, bar_h, BLUE))
        label_lines = wrap(stage["label"], 24)[:2]
        ly = y + bar_h / 2 + 5 - (len(label_lines) - 1) * 8.5
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=15, fill=GREY_DARK))
            ly += 17
        value_text = fmt(stage["value"], unit)
        if bw > 110:
            parts.append(text_el(cx, y + bar_h / 2 + 6, value_text, size=16, fill="#FFFFFF", weight="bold", anchor="middle"))
        else:
            parts.append(text_el(cx + bw / 2 + 10, y + bar_h / 2 + 6, value_text, size=16, weight="bold"))
        if i > 0:
            previous_value = stages[i - 1]["value"]
            conversion = "n/a" if previous_value == 0 else f"{stage['value'] / previous_value * 100:.0f}%"
            parts.append(
                text_el(cx + span / 2 + 28, CHART_TOP + row_h * i + 5, f"↓ {conversion}", size=15, fill=BLUE2, weight="600")
            )
    return parts


def render_heatmap(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    rows, columns, values = spec["rows"], spec["columns"], spec["values"]
    flat = [v for row in values for v in row]
    vmin, vmax = min(flat), max(flat)
    label_w = 210.0
    cell_w = (W - ML - MR - label_w) / len(columns)
    cell_h = min(72.0, (CHART_BOTTOM - CHART_TOP - 30) / len(rows))

    parts: list[str] = []
    for j, column in enumerate(columns):
        cx = ML + label_w + cell_w * j + cell_w / 2
        parts.append(text_el(cx, CHART_TOP + 12, column, size=14, fill=GREY_MED, weight="600", anchor="middle"))
    for i, row_label in enumerate(rows):
        y = CHART_TOP + 26 + cell_h * i
        label_lines = wrap(row_label, 24)[:2]
        ly = y + cell_h / 2 + 5 - (len(label_lines) - 1) * 8.5
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=14, fill=GREY_DARK))
            ly += 17
        for j, value in enumerate(values[i]):
            t = (value - vmin) / (vmax - vmin) if vmax > vmin else 0.5
            x = ML + label_w + cell_w * j
            parts.append(rect_el(x + 2, y + 2, cell_w - 4, cell_h - 4, _lerp_color("#EFF3FB", BLUE, t)))
            text_fill = "#FFFFFF" if t > 0.55 else GREY_DARK
            parts.append(
                text_el(x + cell_w / 2, y + cell_h / 2 + 5, fmt(value, unit), size=14, fill=text_fill, weight="600", anchor="middle")
            )
    return parts


def render_gantt(spec: dict) -> list[str]:
    periods = spec["periods"]
    bars = spec["bars"]
    gates = spec.get("gates", [])
    label_w = 250.0
    col_w = (W - ML - MR - label_w) / len(periods)
    grid_top = CHART_TOP + 14
    row_h = min(56.0, (CHART_BOTTOM - grid_top - (26 if gates else 0)) / len(bars))
    grid_bottom = grid_top + row_h * len(bars)

    parts: list[str] = []
    for j, period in enumerate(periods):
        x = ML + label_w + col_w * j
        parts.append(text_el(x + col_w / 2, CHART_TOP, period, size=13, fill=GREY_MED, weight="600", anchor="middle"))
        parts.append(line_el(x, grid_top, x, grid_bottom, GREY_BORDER))
    parts.append(line_el(W - MR, grid_top, W - MR, grid_bottom, GREY_BORDER))
    parts.append(line_el(ML, grid_top, W - MR, grid_top, GREY_DARK))
    for i, bar in enumerate(bars):
        y = grid_top + row_h * i
        label_lines = wrap(bar["label"], 28)[:2]
        ly = y + row_h / 2 + 5 - (len(label_lines) - 1) * 8.5
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=14, fill=GREY_DARK))
            ly += 17
        bx = ML + label_w + col_w * bar["start"] + 3
        bw = col_w * (bar["end"] - bar["start"] + 1) - 6
        hot = bar.get("highlight")
        parts.append(rect_el(bx, y + (row_h - 24) / 2, bw, 24, BLUE if hot else GREY_FILL, "none" if hot else GREY_BORDER))
        note = bar.get("note", "")
        if note:
            parts.append(text_el(bx + bw + 10, y + row_h / 2 + 5, note, size=12, fill=GREY_MED))
        parts.append(line_el(ML, y + row_h, W - MR, y + row_h, GREY_BORDER))
    for gate in gates:
        gx = ML + label_w + col_w * (gate["period"] + 1)
        gy = grid_bottom + 12
        parts.append(f'<path d="M {gx:.1f} {gy - 8:.1f} L {gx + 8:.1f} {gy:.1f} L {gx:.1f} {gy + 8:.1f} L {gx - 8:.1f} {gy:.1f} Z" fill="{BLUE}"/>')
        parts.append(text_el(gx, gy + 24, gate["label"], size=12, fill=BLUE, weight="600", anchor="middle"))
    return parts


def render_kpi_scorecard(spec: dict) -> list[str]:
    metrics = spec["metrics"]
    cols = spec.get("columns", 3)
    gap = 24.0
    card_w = (W - ML - MR - gap * (cols - 1)) / cols
    n_rows = -(-len(metrics) // cols)
    card_h = min(150.0, (CHART_BOTTOM - CHART_TOP) / n_rows - 14)
    status_fill = {"good": BLUE, "watch": GREY_MED, "risk": RED}

    parts: list[str] = []
    for i, metric in enumerate(metrics):
        x = ML + (i % cols) * (card_w + gap)
        y = CHART_TOP + (i // cols) * (card_h + 18)
        parts.append(rect_el(x, y, card_w, card_h, "#FFFFFF", GREY_BORDER))
        parts.append(rect_el(x, y, 5, card_h, status_fill.get(metric.get("status", "watch"), GREY_MED)))
        parts.append(text_el(x + 24, y + 30, metric["label"], size=14, fill=GREY_MED, weight="600"))
        parts.append(text_el(x + 24, y + 72, str(metric["value"]), size=32, weight="bold"))
        trend = metric.get("trend", "")
        if trend:
            trend_fill = RED if metric.get("status") == "risk" else BLUE2
            parts.append(text_el(x + card_w - 18, y + 72, trend, size=14, fill=trend_fill, weight="600", anchor="end"))
        target = metric.get("target", "")
        if target:
            parts.append(text_el(x + 24, y + card_h - 16, f"Target: {target}", size=12, fill=GREY_MED))
    return parts


def render_two_by_two(spec: dict) -> list[str]:
    plot_x = ML + 50
    plot_w = W - MR - plot_x - 50
    plot_y, plot_h = CHART_TOP, float(CHART_BOTTOM - CHART_TOP)
    mid_x, mid_y = plot_x + plot_w / 2, plot_y + plot_h / 2
    x_axis, y_axis = spec["x_axis"], spec["y_axis"]
    quadrants = spec.get("quadrants", [])

    parts = [
        rect_el(plot_x, plot_y, plot_w, plot_h, "#FFFFFF", GREY_BORDER),
        line_el(mid_x, plot_y, mid_x, plot_y + plot_h, GREY_BORDER),
        line_el(plot_x, mid_y, plot_x + plot_w, mid_y, GREY_BORDER),
    ]
    corners = [
        (plot_x + 14, plot_y + 24, "start"),
        (plot_x + plot_w - 14, plot_y + 24, "end"),
        (plot_x + 14, plot_y + plot_h - 12, "start"),
        (plot_x + plot_w - 14, plot_y + plot_h - 12, "end"),
    ]
    for (qx, qy, anchor), label in zip(corners, quadrants):
        parts.append(text_el(qx, qy, label.upper(), size=12, fill=GREY_MED, weight="600", anchor=anchor))
    parts.append(text_el(mid_x, plot_y + plot_h + 30, x_axis["label"], size=14, fill=GREY_DARK, weight="600", anchor="middle"))
    parts.append(text_el(plot_x, plot_y + plot_h + 30, x_axis.get("low", "Low"), size=12, fill=GREY_MED))
    parts.append(text_el(plot_x + plot_w, plot_y + plot_h + 30, x_axis.get("high", "High"), size=12, fill=GREY_MED, anchor="end"))
    parts.append(text_el(plot_x - 12, plot_y + 10, y_axis.get("high", "High"), size=12, fill=GREY_MED, anchor="end"))
    parts.append(text_el(plot_x - 12, plot_y + plot_h, y_axis.get("low", "Low"), size=12, fill=GREY_MED, anchor="end"))
    parts.append(text_el(ML, plot_y - 14, y_axis["label"], size=14, fill=GREY_DARK, weight="600"))
    for point in spec["points"]:
        px = plot_x + plot_w * point["x"] / 100
        py = plot_y + plot_h * (1 - point["y"] / 100)
        emphasis = point.get("emphasis")
        radius = 9 if emphasis else 7
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius}" fill="{BLUE if emphasis else GREY_MED}"/>')
        parts.append(
            text_el(px + radius + 6, py + 5, point["label"], size=14, fill=BLACK if emphasis else GREY_DARK, weight="600" if emphasis else "normal")
        )
    return parts


RENDERERS = {
    "waterfall": render_waterfall,
    "gap": render_gap,
    "before_after": render_before_after,
    "time_series": render_time_series,
    "benchmark_table": render_benchmark_table,
    "summary_strip": render_summary_strip,
    "process_flow": render_process_flow,
    "funnel": render_funnel,
    "heatmap": render_heatmap,
    "gantt": render_gantt,
    "kpi_scorecard": render_kpi_scorecard,
    "two_by_two": render_two_by_two,
}


def _as_sequence(spec: dict, key: str) -> list:
    value = spec.get(key)
    if not isinstance(value, list) or not value:
        raise RenderSpecError(f"{key} must be a non-empty list")
    return value


def _validate_time_series(spec: dict) -> None:
    labels = _as_sequence(spec, "x_labels")
    series = _as_sequence(spec, "series")
    first_series = series[0]
    if not isinstance(first_series, dict):
        raise RenderSpecError("series[0] must be an object")
    values = first_series.get("values")
    if not isinstance(values, list) or not values:
        raise RenderSpecError("series[0].values must be a non-empty list")
    if len(labels) != len(values):
        raise RenderSpecError(f"x_labels must contain {len(values)} labels; found {len(labels)}")


def _validate_funnel(spec: dict) -> None:
    stages = _as_sequence(spec, "stages")
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise RenderSpecError(f"stages[{index}] must be an object")
        if "label" not in stage or "value" not in stage:
            raise RenderSpecError(f"stages[{index}] must include label and value")
        if not isinstance(stage["value"], (int, float)):
            raise RenderSpecError(f"stages[{index}].value must be numeric")


def _validate_benchmark_table(spec: dict) -> None:
    columns = _as_sequence(spec, "columns")
    rows = _as_sequence(spec, "rows")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RenderSpecError(f"rows[{index}] must be an object")
        values = row.get("values")
        if not isinstance(values, list):
            raise RenderSpecError(f"rows[{index}].values must be a list")
        if len(values) != len(columns):
            raise RenderSpecError(f"rows[{index}].values must contain {len(columns)} values; found {len(values)}")


def _validate_heatmap(spec: dict) -> None:
    rows = _as_sequence(spec, "rows")
    columns = _as_sequence(spec, "columns")
    values = _as_sequence(spec, "values")
    if len(values) != len(rows):
        raise RenderSpecError(f"values must contain {len(rows)} rows; found {len(values)}")
    for row_index, row_values in enumerate(values):
        if not isinstance(row_values, list):
            raise RenderSpecError(f"values[{row_index}] must be a list")
        if len(row_values) != len(columns):
            raise RenderSpecError(f"values[{row_index}] must contain {len(columns)} cells; found {len(row_values)}")
        for col_index, value in enumerate(row_values):
            if not isinstance(value, (int, float)):
                raise RenderSpecError(f"values[{row_index}][{col_index}] must be numeric")


def validate_spec(spec: dict) -> None:
    pattern = spec.get("pattern", "")
    if pattern not in RENDERERS:
        supported = ", ".join(sorted(RENDERERS))
        raise RenderSpecError(f"unsupported pattern {pattern!r}. Supported: {supported}")

    if pattern == "time_series":
        _validate_time_series(spec)
    elif pattern == "funnel":
        _validate_funnel(spec)
    elif pattern == "benchmark_table":
        _validate_benchmark_table(spec)
    elif pattern == "heatmap":
        _validate_heatmap(spec)


def render(spec: dict) -> str:
    validate_spec(spec)
    pattern = spec.get("pattern", "")
    body = header(spec) + RENDERERS[pattern](spec) + footer(spec)
    content = "\n  ".join(body)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{esc(spec.get("headline", ""))}">\n'
        f'  <rect width="{W}" height="{H}" fill="#FFFFFF"/>\n'
        f"  {content}\n"
        f"</svg>\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a slide spec JSON into an SVG slide.")
    parser.add_argument("spec", help="Path to the slide spec JSON file")
    parser.add_argument("-o", "--output", help="Output SVG path (default: spec path with .svg)")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read spec: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        svg = render(spec)
    except (RenderSpecError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: invalid spec: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output) if args.output else spec_path.with_suffix(".svg")
    output_path.write_text(svg, encoding="utf-8")
    print(f"OK: rendered {spec.get('pattern')} slide to {output_path}")


if __name__ == "__main__":
    main()
