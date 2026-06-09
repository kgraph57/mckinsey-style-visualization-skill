#!/usr/bin/env python3
"""Render a slide spec JSON file into a styled 16:9 SVG slide.

Implements the visual system in references/style-system.md for a subset of
patterns from references/visualization-patterns.md:

    waterfall, gap, before_after, time_series, benchmark_table,
    summary_strip, process_flow

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


RENDERERS = {
    "waterfall": render_waterfall,
    "gap": render_gap,
    "before_after": render_before_after,
    "time_series": render_time_series,
    "benchmark_table": render_benchmark_table,
    "summary_strip": render_summary_strip,
    "process_flow": render_process_flow,
}


def render(spec: dict) -> str:
    pattern = spec.get("pattern", "")
    if pattern not in RENDERERS:
        supported = ", ".join(sorted(RENDERERS))
        raise SystemExit(f"ERROR: unsupported pattern {pattern!r}. Supported: {supported}")
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

    output_path = Path(args.output) if args.output else spec_path.with_suffix(".svg")
    output_path.write_text(render(spec), encoding="utf-8")
    print(f"OK: rendered {spec.get('pattern')} slide to {output_path}")


if __name__ == "__main__":
    main()
