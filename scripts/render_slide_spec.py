#!/usr/bin/env python3
"""Render a slide spec JSON file into a styled 16:9 SVG slide.

Implements the visual system in references/style-system.md for a subset of
patterns from references/visualization-patterns.md (22 total):

    waterfall, gap, before_after, time_series, benchmark_table,
    summary_strip, process_flow, funnel, heatmap, gantt, kpi_scorecard,
    two_by_two, scatter, distribution, small_multiples, cover,
    section_divider, end_cover, agenda, bullet_list, closing, quote

The last six are structural slide furniture (dividers, agenda, action-title
bullets, closing/next-steps, quote, back cover) rather than charts.
section_divider and end_cover are full-bleed navy slides that bypass the
standard header/footer chrome (see CHROMELESS); the rest use it like any
chart pattern.

Patterns not in this list are spec-only: the skill produces a structured spec
or an image-generation prompt for them, not an SVG (see SKILL.md).

Usage:
    python3 scripts/render_slide_spec.py examples/render-specs/arr-waterfall.json -o out.svg
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

# Canvas — design tokens (single source: references/style-system.md "Design Tokens")
# Base grid unit: 8px. Margins and anchors sit on the grid; chart geometry is data-driven.
W, H = 1280, 720
ML, MR = 80, 80
CHART_TOP, CHART_BOTTOM = 208, 560

# Palette (references/style-system.md)
# BLUE is deliberately darker than Tailwind blue-900 so that rung-1 fills stay
# distinguishable from GREY_DARK body text in greyscale print (relative-luminance
# ratio >= 1.5, asserted in tests).
BLUE = "#15296B"
BLUE2 = "#2563EB"
BLACK = "#000000"
GREY_DARK = "#374151"
GREY_MED = "#6B7280"
GREY_BORDER = "#D1D5DB"
GREY_FILL = "#F3F4F6"
RED = "#B91C1C"
RED_TINT = "#FBEAEA"
BLUE_TINT = "#EFF3FB"
NAVY_COVER = BLUE  # single navy across content and cover slides
WHITE = "#FFFFFF"

SERIF = "Georgia, 'Times New Roman', 'Hiragino Mincho ProN', 'Yu Mincho', serif"
# System Japanese faces come before Noto Sans JP: on machines where Noto is
# only partially installed (commonly just the Black weight), listing it first
# captures body text and renders everything ultra-bold.
SANS = (
    "'Helvetica Neue', Helvetica, Arial, "
    "'Hiragino Sans', 'Yu Gothic', 'Noto Sans JP', 'Meiryo', sans-serif"
)

ELLIPSIS = "…"


def _rel_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of a #RRGGBB color."""
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(color_a: str, color_b: str) -> float:
    la, lb = _rel_luminance(color_a), _rel_luminance(color_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _cell_text_color(cell_fill: str) -> str:
    """Pick black or white text, whichever clears the higher contrast on the fill."""
    return BLACK if contrast_ratio(BLACK, cell_fill) >= contrast_ratio(WHITE, cell_fill) else WHITE


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


def _char_width(char: str) -> int:
    """Approximate display width in half-width units (CJK/fullwidth = 2)."""
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _text_width(text: str) -> int:
    return sum(_char_width(c) for c in text)


def _tokens(text: str) -> list[tuple[str, bool]]:
    """Split text into wrap tokens as (token, needs_leading_space) pairs.

    Whitespace-separated chunks stay word-wrapped; runs of CJK characters are
    breakable per character so Japanese/Chinese text wraps instead of
    overflowing the canvas.
    """
    tokens: list[tuple[str, bool]] = []
    for chunk in str(text).split():
        first_in_chunk = True
        run = ""
        for char in chunk:
            if _char_width(char) == 2:
                if run:
                    tokens.append((run, first_in_chunk))
                    run, first_in_chunk = "", False
                tokens.append((char, first_in_chunk))
                first_in_chunk = False
            else:
                run += char
        if run:
            tokens.append((run, first_in_chunk))
    return tokens


# Line-start kinsoku (行頭禁則): closing punctuation that must not begin a
# line. Resolved by hanging it off the previous line (ぶら下がり組) — a
# one-character overhang reads better than orphaned punctuation.
KINSOKU_HEAD = "。、．，）」』】〉》〕！？"


def _apply_kinsoku(lines: list[str]) -> list[str]:
    for i in range(1, len(lines)):
        moved = ""
        while lines[i] and lines[i][0] in KINSOKU_HEAD:
            moved += lines[i][0]
            lines[i] = lines[i][1:]
        if moved:
            lines[i - 1] += moved
    return [line for line in lines if line]


def wrap(text: str, width: int, max_lines: int = 0) -> list[str]:
    """Wrap text to a width given in half-width character units.

    ASCII counts 1 per character, CJK counts 2, so existing English widths keep
    their meaning while Japanese wraps at roughly half the character count.
    Closing punctuation (。、」 …) never starts a line: it hangs off the end of
    the previous line instead (line-start kinsoku). When max_lines > 0 the
    result is clamped and a trailing ellipsis marks any dropped content —
    nothing is truncated silently.
    """
    lines: list[str] = []
    current = ""
    for token, needs_space in _tokens(text):
        candidate = f"{current} {token}" if (current and needs_space) else f"{current}{token}"
        if _text_width(candidate) > width and current:
            lines.append(current)
            current = token
        else:
            current = candidate
        while _text_width(current) > width:
            # Hard-break tokens with no break opportunity (URLs, codes, IDs)
            # instead of letting them overflow the canvas.
            head, rest = current, ""
            while head and _text_width(head) > width:
                head, rest = head[:-1], head[-1] + rest
            lines.append(head)
            current = rest
    if current:
        lines.append(current)
    lines = _apply_kinsoku(lines)
    if max_lines and len(lines) > max_lines:
        kept = lines[:max_lines]
        last = kept[-1]
        while last and _text_width(last + ELLIPSIS) > width:
            last = last[:-1].rstrip()
        kept[-1] = last + ELLIPSIS
        return kept
    return lines


def fmt(value: float, unit: str) -> str:
    magnitude = abs(value)
    text = f"{magnitude:,.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{magnitude:,}"
    sign = "-" if value < 0 else ""
    if not unit:
        return f"{sign}{text}"
    if unit[0] in "$€£¥":
        return f"{sign}{unit[0]}{text}{unit[1:]}"
    return f"{sign}{text}{unit}"


def text_el(
    x: float,
    y: float,
    content: str,
    size: int = 14,
    fill: str = BLACK,
    weight: str = "normal",
    family: str = SANS,
    anchor: str = "start",
    title: str = "",
) -> str:
    title_el = f"<title>{esc(title)}</title>" if title else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{title_el}{esc(content)}</text>'
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
    # The kicker bar above the headline is the deck's single signature motif.
    # Do not add sibling accent bars elsewhere (see style-system.md anti-patterns).
    parts = [rect_el(ML, 52, 56, 5, BLUE)]
    headline = spec.get("headline", "")
    lines = wrap(headline, 64)
    size, line_h = 30, 40
    if len(lines) > 2:
        lines = wrap(headline, 80, max_lines=3)
        size, line_h = 24, 32
    y = 96
    for line in lines:
        parts.append(text_el(ML, y, line, size=size, weight="bold", family=SERIF, title=headline if len(lines) > 2 else ""))
        y += line_h
    subline = spec.get("subline", "")
    if subline:
        parts.append(text_el(ML, y + 2, subline, size=17, fill=GREY_MED))
    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 40, classification.upper(), size=11, fill=GREY_MED, weight="600", anchor="end"))
    return parts


def footer(spec: dict) -> list[str]:
    parts: list[str] = []
    annotation = spec.get("annotation", "")
    if annotation:
        # Emphasis through typography only — no decorative accent bar (data-ink rule).
        y = 630
        for line in wrap(annotation, 112, max_lines=2):
            parts.append(text_el(ML, y, line, size=16, fill=BLUE, weight="600", title=annotation))
            y += 22
    footnotes = spec.get("footnotes", [])[:2]
    source = spec.get("source", "")
    note_y = 692 - 16 * len(footnotes)
    for i, note in enumerate(footnotes):
        marker = "¹²"[i]
        parts.append(text_el(ML, note_y, f"{marker} {wrap(note, 150, max_lines=1)[0]}", size=11, fill=GREY_MED, title=note))
        note_y += 16
    if source:
        parts.append(text_el(ML, 692, source, size=12, fill=GREY_MED))
    page_number = spec.get("page_number", "")
    if page_number != "":
        parts.append(text_el(W - MR, 692, str(page_number), size=12, fill=GREY_MED, anchor="end"))
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
    # Scale to the full cumulative range, floored at zero, so a run of negative
    # drivers can never push bars outside the chart band.
    raw_top = max(max(cumulative), start["value"], end_value, 0)
    raw_bottom = min(min(cumulative), start["value"], end_value, 0)
    value_range = (raw_top - raw_bottom) or 1
    top = raw_top + value_range * 0.18
    bottom = raw_bottom - (value_range * 0.10 if raw_bottom < 0 else 0)

    n = len(drivers) + 2
    span = W - ML - MR
    bar_w = min(110.0, span / n * 0.62)
    step = span / n

    def x_at(i: int) -> float:
        return ML + step * i + (step - bar_w) / 2

    def y_at(value: float) -> float:
        return CHART_BOTTOM - ((value - bottom) / (top - bottom)) * (CHART_BOTTOM - CHART_TOP)

    zero_y = y_at(0)
    parts = [
        line_el(ML, zero_y, W - MR, zero_y, GREY_DARK),
        text_el(ML - 10, zero_y + 4, "0", size=11, fill=GREY_MED, anchor="end"),
    ]

    def bar(i: int, base: float, value_top: float, fill: str, label: str, value_text: str) -> None:
        x = x_at(i)
        y1, y2 = y_at(max(base, value_top)), y_at(min(base, value_top))
        parts.append(rect_el(x, y1, bar_w, max(y2 - y1, 2), fill))
        parts.append(text_el(x + bar_w / 2, y1 - 10, value_text, size=15, weight="bold", anchor="middle"))
        for j, line in enumerate(wrap(label, 16, max_lines=2)):
            parts.append(
                text_el(x + bar_w / 2, CHART_BOTTOM + 22 + j * 16, line, size=13, fill=GREY_DARK, anchor="middle", title=label)
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
        label_lines = wrap(item["label"], 25, max_lines=2)
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

    parts = [
        line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK),
        text_el(ML - 10, CHART_BOTTOM + 4, "0", size=11, fill=GREY_MED, anchor="end"),
    ]
    before_label = spec.get("before_label", "Before")
    after_label = spec.get("after_label", "After")
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
        delta_y = min(by, ay) - (52 if i == 0 else 32)
        parts.append(
            text_el(cx, delta_y, f"{sign}{fmt(abs(delta), unit)}", size=15, fill=BLUE2, weight="bold", anchor="middle")
        )
        if i == 0:
            # Direct labels on the first pair replace a legend (style rule:
            # avoid legend hunting).
            parts.append(text_el(bx + bar_w / 2, by - 24, before_label, size=12, fill=GREY_MED, anchor="middle"))
            parts.append(text_el(ax + bar_w / 2, ay - 24, after_label, size=12, fill=GREY_DARK, weight="600", anchor="middle"))
        for j, line in enumerate(wrap(pair["label"], 22, max_lines=2)):
            parts.append(text_el(cx, CHART_BOTTOM + 24 + j * 17, line, size=14, fill=GREY_DARK, anchor="middle", title=pair["label"]))
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

    parts = [
        line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK),
        text_el(ML - 10, CHART_BOTTOM + 4, "0", size=11, fill=GREY_MED, anchor="end"),
    ]
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
        for k, line in enumerate(wrap(column, 18, max_lines=2)):
            parts.append(text_el(cx, top_y + 20 + k * 15, line, size=13, fill=GREY_MED, weight="600", anchor="middle"))
    parts.append(line_el(ML, top_y + row_h, W - MR, top_y + row_h, GREY_DARK))
    value_size = 15 if len(columns) <= 6 else 13
    cell_width_units = max(int(col_w / (value_size * 0.62)), 6)
    for i, row in enumerate(rows):
        y = top_y + row_h * (i + 1)
        label_lines = wrap(row["label"], 28, max_lines=2)
        ly = y + row_h / 2 + 6 - (len(label_lines) - 1) * 9
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=15, fill=BLACK, weight="600", title=row["label"]))
            ly += 18
        for j, value in enumerate(row["values"]):
            cx = ML + label_w + col_w * j + col_w / 2
            cell_lines = wrap(str(value), cell_width_units, max_lines=2)
            cy = y + row_h / 2 + 6 - (len(cell_lines) - 1) * 8
            if (i, j) in leaders:
                parts.append(rect_el(ML + label_w + col_w * j + 6, y + 7, col_w - 12, row_h - 14, BLUE))
                for line in cell_lines:
                    parts.append(text_el(cx, cy, line, size=value_size, fill="#FFFFFF", weight="bold", anchor="middle", title=str(value)))
                    cy += value_size + 2
            else:
                for line in cell_lines:
                    parts.append(text_el(cx, cy, line, size=value_size, fill=GREY_DARK, anchor="middle", title=str(value)))
                    cy += value_size + 2
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
        for line in wrap(block["claim"], text_width, max_lines=3):
            parts.append(text_el(inner_x, y, line, size=17, weight="bold"))
            y += 23
        y += 8
        for line in wrap(block["proof"], text_width, max_lines=4):
            parts.append(text_el(inner_x, y, line, size=14, fill=GREY_MED))
            y += 19
        y += 10
        for line in wrap(block["implication"], text_width, max_lines=3):
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
        for line in wrap(step["label"], text_width, max_lines=2):
            parts.append(text_el(x + 16, ty + 8, line, size=16, fill=title_fill, weight="bold"))
            ty += 21
        for line in wrap(step.get("detail", ""), text_width, max_lines=3):
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
        label_lines = wrap(stage["label"], 24, max_lines=2)
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


def _heatmap_cell_fill(value: float, vmin: float, vmax: float, diverging: bool) -> str:
    """Sequential single-hue ramp for non-negative data; diverging ramp anchored
    at zero (white) when the data carries sign, so negative and positive cells
    can never read as the same tone."""
    if diverging:
        extent = max(abs(vmin), abs(vmax)) or 1
        t = value / extent
        if t >= 0:
            return _lerp_color(WHITE, BLUE, min(t, 1.0))
        return _lerp_color(WHITE, RED, min(-t, 1.0))
    t = (value - vmin) / (vmax - vmin) if vmax > vmin else 0.5
    return _lerp_color(BLUE_TINT, BLUE, t)


def render_heatmap(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    rows, columns, values = spec["rows"], spec["columns"], spec["values"]
    flat = [v for row in values for v in row]
    vmin, vmax = min(flat), max(flat)
    diverging = bool(spec.get("diverging", vmin < 0 < vmax))
    label_w = 210.0
    cell_w = (W - ML - MR - label_w) / len(columns)
    cell_h = min(72.0, (CHART_BOTTOM - CHART_TOP - 30) / len(rows))

    parts: list[str] = []
    for j, column in enumerate(columns):
        cx = ML + label_w + cell_w * j + cell_w / 2
        parts.append(text_el(cx, CHART_TOP + 12, column, size=14, fill=GREY_MED, weight="600", anchor="middle"))
    for i, row_label in enumerate(rows):
        y = CHART_TOP + 26 + cell_h * i
        label_lines = wrap(row_label, 24, max_lines=2)
        ly = y + cell_h / 2 + 5 - (len(label_lines) - 1) * 8.5
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=14, fill=GREY_DARK, title=row_label))
            ly += 17
        for j, value in enumerate(values[i]):
            x = ML + label_w + cell_w * j
            fill = _heatmap_cell_fill(value, vmin, vmax, diverging)
            parts.append(rect_el(x + 2, y + 2, cell_w - 4, cell_h - 4, fill))
            # Pick the value color by measured contrast so mid-tone cells stay
            # WCAG-readable instead of trusting a fixed threshold.
            parts.append(
                text_el(x + cell_w / 2, y + cell_h / 2 + 5, fmt(value, unit), size=14, fill=_cell_text_color(fill), weight="600", anchor="middle")
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
        label_lines = wrap(bar["label"], 28, max_lines=2)
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


def render_cover(spec: dict) -> list[str]:
    """Navy cover slide. Bypasses the standard white header/footer chrome."""
    parts = [
        rect_el(0, 0, W, H, NAVY_COVER),
        rect_el(ML, 200, 56, 5, WHITE),
    ]
    y = 264
    for line in wrap(spec.get("title", ""), 40, max_lines=3):
        parts.append(text_el(ML, y, line, size=52, fill=WHITE, family=SERIF))
        y += 64
    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 70, max_lines=2):
            parts.append(text_el(ML, y, line, size=20, fill="#E5E7EB"))
            y += 28
    meta = " · ".join(str(spec[k]) for k in ("presenter", "date") if spec.get(k))
    if meta:
        parts.append(text_el(ML, 640, meta, size=15, fill="#E5E7EB"))
    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 640, classification.upper(), size=12, fill="#E5E7EB", anchor="end"))
    return parts


def render_scatter(spec: dict) -> list[str]:
    points = spec["points"]
    x_axis, y_axis = spec["x_axis"], spec["y_axis"]
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    x_min, x_max = min(xs + [0]) if spec.get("x_zero", False) else min(xs), max(xs)
    y_min, y_max = min(ys + [0]) if spec.get("y_zero", False) else min(ys), max(ys)
    x_pad = (x_max - x_min) * 0.08 or 1
    y_pad = (y_max - y_min) * 0.08 or 1
    x_min, x_max = x_min - x_pad, x_max + x_pad
    y_min, y_max = y_min - y_pad, y_max + y_pad
    plot_x, plot_w = ML + 50, W - ML - MR - 100
    plot_y, plot_h = CHART_TOP, float(CHART_BOTTOM - CHART_TOP)

    def px(value: float) -> float:
        return plot_x + plot_w * (value - x_min) / (x_max - x_min)

    def py(value: float) -> float:
        return plot_y + plot_h * (1 - (value - y_min) / (y_max - y_min))

    parts = [
        line_el(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, GREY_DARK),
        line_el(plot_x, plot_y, plot_x, plot_y + plot_h, GREY_DARK),
        text_el((plot_x + plot_x + plot_w) / 2, plot_y + plot_h + 34, x_axis["label"], size=14, fill=GREY_DARK, weight="600", anchor="middle"),
        text_el(ML, plot_y - 14, y_axis["label"], size=14, fill=GREY_DARK, weight="600"),
        # Disclosed axis ranges keep non-zero baselines honest (chart rule).
        text_el(plot_x, plot_y + plot_h + 18, fmt(x_min + x_pad, x_axis.get("unit", "")), size=11, fill=GREY_MED),
        text_el(plot_x + plot_w, plot_y + plot_h + 18, fmt(x_max - x_pad, x_axis.get("unit", "")), size=11, fill=GREY_MED, anchor="end"),
        text_el(plot_x - 8, plot_y + 10, fmt(y_max - y_pad, y_axis.get("unit", "")), size=11, fill=GREY_MED, anchor="end"),
        text_el(plot_x - 8, plot_y + plot_h, fmt(y_min + y_pad, y_axis.get("unit", "")), size=11, fill=GREY_MED, anchor="end"),
    ]
    for point in points:
        cx, cy = px(point["x"]), py(point["y"])
        emphasis = point.get("emphasis")
        radius = 9 if emphasis else 7
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="{BLUE if emphasis else GREY_MED}"/>')
        label = point.get("label", "")
        if label:
            parts.append(
                text_el(cx + radius + 6, cy + 5, wrap(label, 24, max_lines=1)[0], size=13, fill=BLACK if emphasis else GREY_DARK, weight="600" if emphasis else "normal", title=label)
            )
    return parts


def render_distribution(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    bins = spec["bins"]
    highlight = spec.get("highlight", -1)
    top = max(b["value"] for b in bins) * 1.15 or 1
    span = W - ML - MR
    step = span / len(bins)
    bar_w = step * 0.82

    parts = [
        line_el(ML, CHART_BOTTOM, W - MR, CHART_BOTTOM, GREY_DARK),
        text_el(ML - 10, CHART_BOTTOM + 4, "0", size=11, fill=GREY_MED, anchor="end"),
    ]
    for i, bucket in enumerate(bins):
        x = ML + step * i + (step - bar_w) / 2
        h = (bucket["value"] / top) * (CHART_BOTTOM - CHART_TOP)
        y = CHART_BOTTOM - h
        is_hot = i == highlight
        parts.append(rect_el(x, y, bar_w, max(h, 1), BLUE if is_hot else GREY_FILL, "none" if is_hot else GREY_BORDER))
        parts.append(text_el(x + bar_w / 2, y - 8, fmt(bucket["value"], unit), size=13, weight="bold" if is_hot else "normal", fill=BLACK if is_hot else GREY_MED, anchor="middle"))
        for j, line in enumerate(wrap(bucket["label"], max(int(step / 8), 6), max_lines=2)):
            parts.append(text_el(x + bar_w / 2, CHART_BOTTOM + 20 + j * 15, line, size=12, fill=GREY_DARK, anchor="middle", title=bucket["label"]))
    return parts


def render_small_multiples(spec: dict) -> list[str]:
    """Grid of sparkline panels on a shared scale — the dense, analytical
    counterpart to one-message slides (small multiples)."""
    unit = spec.get("unit", "")
    charts = spec["charts"]
    cols = spec.get("columns", 3)
    gap = 28.0
    panel_w = (W - ML - MR - gap * (cols - 1)) / cols
    n_rows = -(-len(charts) // cols)
    panel_h = min(160.0, (CHART_BOTTOM + 30 - CHART_TOP) / n_rows - 18)
    flat = [v for chart in charts for v in chart["values"]]
    shared_top = max(flat) * 1.1 or 1
    shared_bottom = min(min(flat), 0)

    parts: list[str] = []
    for i, chart in enumerate(charts):
        x = ML + (i % cols) * (panel_w + gap)
        y = CHART_TOP + (i // cols) * (panel_h + 18)
        values = chart["values"]
        emphasis = chart.get("emphasis")
        parts.append(text_el(x, y + 14, wrap(chart["label"], int(panel_w / 9), max_lines=1)[0], size=14, fill=BLACK if emphasis else GREY_DARK, weight="600", title=chart["label"]))
        spark_top, spark_h = y + 26, panel_h - 48
        baseline_y = spark_top + spark_h * (1 - (0 - shared_bottom) / (shared_top - shared_bottom))
        parts.append(line_el(x, baseline_y, x + panel_w, baseline_y, GREY_BORDER))

        def pt(k: int) -> tuple[float, float]:
            sx = x + panel_w * (k / max(len(values) - 1, 1))
            sy = spark_top + spark_h * (1 - (values[k] - shared_bottom) / (shared_top - shared_bottom))
            return sx, sy

        line_points = " ".join(f"{sx:.1f},{sy:.1f}" for sx, sy in (pt(k) for k in range(len(values))))
        parts.append(f'<polyline points="{line_points}" fill="none" stroke="{BLUE if emphasis else GREY_MED}" stroke-width="2.5"/>')
        lx, ly_pt = pt(len(values) - 1)
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly_pt:.1f}" r="4" fill="{BLUE if emphasis else GREY_MED}"/>')
        parts.append(text_el(x + panel_w, y + panel_h - 6, fmt(values[-1], unit), size=15, weight="bold", fill=BLUE if emphasis else GREY_DARK, anchor="end"))
        parts.append(text_el(x, y + panel_h - 6, fmt(values[0], unit), size=12, fill=GREY_MED))
    return parts


def render_section_divider(spec: dict) -> list[str]:
    """Navy full-bleed section divider (小扉). Bypasses header/footer chrome,
    mirroring render_cover's geometry (see CHROMELESS)."""
    parts = [rect_el(0, 0, W, H, NAVY_COVER), rect_el(ML, 200, 56, 5, WHITE)]
    section_number = spec["section_number"]
    parts.append(
        text_el(ML, 236, f"SECTION {section_number:02d}", size=15, fill="#E5E7EB", weight="600")
    )

    title = spec.get("title", "")
    y = 284
    lines = wrap(title, 40, max_lines=2)
    truncated = bool(lines) and lines[-1].endswith(ELLIPSIS)
    for line in lines:
        parts.append(text_el(ML, y, line, size=40, fill=WHITE, family=SERIF, title=title if truncated else ""))
        y += 50

    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 70, max_lines=2):
            parts.append(text_el(ML, y, line, size=18, fill="#E5E7EB"))
            y += 26

    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 40, classification.upper(), size=11, fill="#E5E7EB", weight="600", anchor="end"))

    # Section rail: skip entirely rather than overlap or overflow (measured in
    # the same half-width character units `wrap`/`_text_width` already use).
    sections = spec.get("sections", [])
    if sections:
        rail_y = 604
        px_per_unit = 13 * 0.62
        gap_units = 4
        items = [f"{i + 1:02d} {name}" for i, name in enumerate(sections)]
        total_units = sum(_text_width(item) for item in items) + gap_units * max(len(items) - 1, 0)
        available_units = (W - ML - MR) / px_per_unit
        if total_units <= available_units:
            current_index = section_number - 1
            x = float(ML)
            for i, item in enumerate(items):
                item_w = _text_width(item) * px_per_unit
                if i == current_index:
                    parts.append(text_el(x, rail_y, item, size=13, fill=WHITE, weight="600"))
                else:
                    parts.append(
                        f'<text x="{x:.1f}" y="{rail_y:.1f}" font-family="{SANS}" font-size="13" '
                        f'fill="#E5E7EB" opacity="0.55">{esc(item)}</text>'
                    )
                x += item_w + gap_units * px_per_unit
    return parts


def render_end_cover(spec: dict) -> list[str]:
    """Navy full-bleed back cover. Mirrors render_cover geometry exactly, with
    a contact block and a default title so a bare {"pattern": "end_cover"}
    still renders."""
    parts = [rect_el(0, 0, W, H, NAVY_COVER), rect_el(ML, 200, 56, 5, WHITE)]
    y = 264
    for line in wrap(spec.get("title") or "Thank you", 40, max_lines=3):
        parts.append(text_el(ML, y, line, size=52, fill=WHITE, family=SERIF))
        y += 64
    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 70, max_lines=2):
            parts.append(text_el(ML, y, line, size=20, fill="#E5E7EB"))
            y += 28
    contact = (spec.get("contact") or [])[:4]
    cy = 560
    for line in contact:
        parts.append(text_el(ML, cy, str(line), size=15, fill="#E5E7EB"))
        cy += 24
    meta = " · ".join(str(spec[k]) for k in ("presenter", "date") if spec.get(k))
    if meta:
        parts.append(text_el(ML, 640, meta, size=15, fill="#E5E7EB"))
    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 640, classification.upper(), size=12, fill="#E5E7EB", anchor="end"))
    return parts


def render_agenda(spec: dict) -> list[str]:
    """Numbered agenda list on hairlines; splits into two columns beyond six
    items and optionally emphasizes the current item (rung 2: tinted fill,
    accent text)."""
    items = spec["items"]
    n = len(items)
    current = spec.get("current")
    two_col = n > 6
    if two_col:
        split = -(-n // 2)  # ceil(n / 2), so 7 -> 4+3 and 8 -> 4+4
        columns = [items[:split], items[split:]]
    else:
        columns = [items]
    n_rows = max(len(col) for col in columns)
    row_h = (CHART_BOTTOM - CHART_TOP) / n_rows
    gap = 40.0
    col_w = (W - ML - MR - gap) / 2 if two_col else float(W - ML - MR)
    # Detail column sits at the same proportional offset the single-column
    # case uses literally (ML + 320 of a 1120px-wide band).
    detail_offset = col_w * (320 / 1120)
    detail_width_units = max(int((col_w - detail_offset) / (14 * 0.62)), 8)
    title_width_units = max(int((detail_offset - 46) / (17 * 0.62)), 8)

    parts: list[str] = []
    for r in range(n_rows + 1):
        ry = CHART_TOP + row_h * r
        parts.append(line_el(ML, ry, W - MR, ry, GREY_BORDER))

    index = 0
    for c, col_items in enumerate(columns):
        col_x = ML + c * (col_w + gap)
        detail_x = col_x + detail_offset
        for r, item in enumerate(col_items):
            index += 1
            y = CHART_TOP + row_h * r
            baseline = y + row_h / 2 + 6
            emphasized = current == index
            if emphasized:
                parts.append(rect_el(col_x, y, col_w, row_h, BLUE_TINT))
            parts.append(text_el(col_x, baseline, f"{index:02d}", size=24, fill=BLUE, family=SERIF))
            title_lines = wrap(item["title"], title_width_units, max_lines=1)
            title_text = title_lines[0] if title_lines else ""
            parts.append(
                text_el(
                    col_x + 46,
                    baseline,
                    title_text,
                    size=17,
                    fill=BLUE if emphasized else BLACK,
                    weight="600",
                    title=item["title"] if title_text.endswith(ELLIPSIS) else "",
                )
            )
            detail = item.get("detail", "")
            if detail:
                detail_lines = wrap(detail, detail_width_units, max_lines=1)
                detail_text = detail_lines[0] if detail_lines else ""
                parts.append(
                    text_el(
                        detail_x,
                        baseline,
                        detail_text,
                        size=14,
                        fill=GREY_MED,
                        title=detail if detail_text.endswith(ELLIPSIS) else "",
                    )
                )
    return parts


def render_bullet_list(spec: dict) -> list[str]:
    """Action-title bullet slide. One marker family (square bullets, en-dash
    subs) — no accent bars, per the single-motif ink-discipline rule."""
    bullets = spec["bullets"]
    columns = spec.get("columns", 1)
    if columns == 2:
        half = -(-len(bullets) // 2)
        column_bullets = [bullets[:half], bullets[half:]]
    else:
        column_bullets = [bullets]

    gap = 60.0
    col_w = (W - ML - MR - gap) / 2 if columns == 2 else float(W - ML - MR)
    text_indent = 22.0  # past the 6px marker square
    sub_indent = text_indent + 24.0  # one nested step past the bullet text (24px per spec)
    text_width_units = max(int((col_w - text_indent) / (16 * 0.62)), 10)
    sub_width_units = max(int((col_w - sub_indent) / (14 * 0.62)), 10)

    parts: list[str] = []
    for c, group in enumerate(column_bullets):
        col_x = ML + c * (col_w + gap)
        y = float(CHART_TOP) + 20
        for bullet in group:
            emphasized = bool(bullet.get("emphasis"))
            text_fill = BLUE if emphasized else BLACK
            weight = "600" if emphasized else "normal"
            marker_y = y
            lines = wrap(bullet["text"], text_width_units)
            parts.append(rect_el(col_x, marker_y - 10, 6, 6, BLUE))
            for line in lines:
                parts.append(text_el(col_x + text_indent, y, line, size=16, fill=text_fill, weight=weight))
                y += 24
            subs = bullet.get("sub", [])[:3]
            if subs:
                y += 4
                for sub in subs:
                    sub_lines = wrap(str(sub), sub_width_units)
                    for i, line in enumerate(sub_lines):
                        prefix = f"– {line}" if i == 0 else f"  {line}"
                        parts.append(text_el(col_x + sub_indent, y, prefix, size=14, fill=GREY_DARK))
                        y += 20
            y += 22
    return parts


def render_closing(spec: dict) -> list[str]:
    """Key-takeaways / next-steps closing slide. call_to_action rides the
    existing footer "annotation" slot mechanics (blue 600) instead of a new
    motif — this mutates `spec` in place so the render() dispatch's later
    footer(spec) call picks it up, without touching footer() itself."""
    call_to_action = spec.get("call_to_action", "")
    if call_to_action:
        spec.setdefault("annotation", call_to_action)

    takeaways = (spec.get("takeaways") or [])[:4]
    next_steps = spec["next_steps"][:5]
    parts: list[str] = []

    if takeaways:
        left_w = (W - ML - MR) * 0.45
        col_gap = 40.0
        right_x = ML + left_w + col_gap
        right_w = (W - ML - MR) - left_w - col_gap
        text_width_units = max(int((left_w - 40) / (16 * 0.62)), 10)
        detail_width_units = max(int(right_w / (16 * 0.62)), 10)

        parts.append(text_el(ML, CHART_TOP, "KEY TAKEAWAYS", size=12, fill=GREY_MED, weight="600"))
        y = CHART_TOP + 34
        for i, takeaway in enumerate(takeaways, start=1):
            parts.append(text_el(ML, y, str(i), size=20, fill=BLUE, family=SERIF, weight="bold"))
            lines = wrap(str(takeaway), text_width_units, max_lines=3)
            ly = y
            for line in lines:
                parts.append(
                    text_el(ML + 32, ly, line, size=16, fill=BLACK, title=str(takeaway) if line.endswith(ELLIPSIS) else "")
                )
                ly += 22
            y += max(len(lines), 1) * 22 + 18

        parts.append(text_el(right_x, CHART_TOP, "NEXT STEPS", size=12, fill=GREY_MED, weight="600"))
        y = CHART_TOP + 34
        for step in next_steps:
            lines = wrap(step["action"], detail_width_units, max_lines=2)
            for line in lines:
                parts.append(
                    text_el(right_x, y, line, size=16, fill=BLACK, weight="600", title=step["action"] if line.endswith(ELLIPSIS) else "")
                )
                y += 21
            meta = " · ".join(str(step[k]) for k in ("owner", "timing") if step.get(k))
            if meta:
                y += 3
                parts.append(text_el(right_x, y, meta, size=13, fill=GREY_MED))
                y += 17
            y += 18
    else:
        row_h = min(64.0, (CHART_BOTTOM - CHART_TOP) / len(next_steps))
        action_width_units = max(int((W - ML - MR - 260) / (16 * 0.62)), 10)
        for r in range(len(next_steps) + 1):
            ry = CHART_TOP + row_h * r
            parts.append(line_el(ML, ry, W - MR, ry, GREY_BORDER))
        for i, step in enumerate(next_steps):
            row_y = CHART_TOP + row_h * i
            lines = wrap(step["action"], action_width_units, max_lines=2)
            baseline = row_y + row_h / 2 - (len(lines) - 1) * 11 + 5
            ay = baseline
            for line in lines:
                parts.append(
                    text_el(ML, ay, line, size=16, fill=BLACK, weight="600", title=step["action"] if line.endswith(ELLIPSIS) else "")
                )
                ay += 21
            meta = " · ".join(str(step[k]) for k in ("owner", "timing") if step.get(k))
            if meta:
                parts.append(text_el(W - MR, row_y + row_h / 2 + 5, meta, size=13, fill=GREY_MED, anchor="end"))
    return parts


def render_quote(spec: dict) -> list[str]:
    """Pull-quote slide: one oversized opening quotation mark (structural
    motif, no closing mark) plus attributed text."""
    text = spec["text"]
    parts = [text_el(ML, CHART_TOP + 70, "“", size=90, fill=BLUE_TINT, family=SERIF)]
    x = ML + 60
    y = CHART_TOP + 160
    lines = wrap(text, 58, max_lines=4)
    truncated = bool(lines) and lines[-1].endswith(ELLIPSIS)
    for line in lines:
        parts.append(text_el(x, y, line, size=28, fill=BLACK, family=SERIF, title=text if truncated else ""))
        y += 40
    attribution = spec.get("attribution", "")
    if attribution:
        y += 20
        parts.append(text_el(x, y, f"— {attribution}", size=15, fill=GREY_DARK, weight="600"))
        y += 22
    context = spec.get("context", "")
    if context:
        parts.append(text_el(x, y, context, size=13, fill=GREY_MED))
    return parts


RENDERERS = {
    "cover": render_cover,
    "scatter": render_scatter,
    "distribution": render_distribution,
    "small_multiples": render_small_multiples,
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
    "section_divider": render_section_divider,
    "end_cover": render_end_cover,
    "agenda": render_agenda,
    "bullet_list": render_bullet_list,
    "closing": render_closing,
    "quote": render_quote,
}

# Full-bleed navy patterns bypass the standard white header/footer chrome,
# like render_cover. render() dispatches on membership in this set instead of
# a hardcoded pattern name (see render()).
CHROMELESS = {"cover", "section_divider", "end_cover"}


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


def _validate_scatter(spec: dict) -> None:
    points = _as_sequence(spec, "points")
    for index, point in enumerate(points):
        if not isinstance(point, dict) or "x" not in point or "y" not in point:
            raise RenderSpecError(f"points[{index}] must be an object with x and y")
        if not isinstance(point["x"], (int, float)) or not isinstance(point["y"], (int, float)):
            raise RenderSpecError(f"points[{index}].x and .y must be numeric")
    for axis in ("x_axis", "y_axis"):
        if not isinstance(spec.get(axis), dict) or "label" not in spec[axis]:
            raise RenderSpecError(f"{axis} must be an object with a label")


def _validate_distribution(spec: dict) -> None:
    bins = _as_sequence(spec, "bins")
    for index, bucket in enumerate(bins):
        if not isinstance(bucket, dict) or "label" not in bucket or "value" not in bucket:
            raise RenderSpecError(f"bins[{index}] must include label and value")
        if not isinstance(bucket["value"], (int, float)):
            raise RenderSpecError(f"bins[{index}].value must be numeric")


def _validate_small_multiples(spec: dict) -> None:
    charts = _as_sequence(spec, "charts")
    for index, chart in enumerate(charts):
        if not isinstance(chart, dict) or "label" not in chart:
            raise RenderSpecError(f"charts[{index}] must be an object with a label")
        values = chart.get("values")
        if not isinstance(values, list) or not values:
            raise RenderSpecError(f"charts[{index}].values must be a non-empty list")


def _validate_cover(spec: dict) -> None:
    if not spec.get("title"):
        raise RenderSpecError("cover requires a title")


def _validate_section_divider(spec: dict) -> None:
    if not spec.get("title"):
        raise RenderSpecError("section_divider requires a title")
    section_number = spec.get("section_number")
    if not isinstance(section_number, int) or isinstance(section_number, bool) or section_number < 1:
        raise RenderSpecError("section_divider requires section_number to be an integer >= 1")
    sections = spec.get("sections")
    if sections is not None and not isinstance(sections, list):
        raise RenderSpecError("section_divider sections must be a list")


def _validate_end_cover(spec: dict) -> None:
    contact = spec.get("contact")
    if contact is not None and not isinstance(contact, list):
        raise RenderSpecError("end_cover contact must be a list of strings")


def _validate_agenda(spec: dict) -> None:
    items = _as_sequence(spec, "items")
    if len(items) > 8:
        raise RenderSpecError(f"agenda supports at most 8 items; found {len(items)}")
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("title"):
            raise RenderSpecError(f"items[{index}] must be an object with a title")
    current = spec.get("current")
    if current is not None:
        if not isinstance(current, int) or isinstance(current, bool) or not (1 <= current <= len(items)):
            raise RenderSpecError(f"current must be an integer between 1 and {len(items)}")


def _validate_bullet_list(spec: dict) -> None:
    bullets = _as_sequence(spec, "bullets")
    if len(bullets) > 6:
        raise RenderSpecError(f"bullet_list supports at most 6 bullets; found {len(bullets)}")
    columns = spec.get("columns", 1)
    if columns not in (1, 2):
        raise RenderSpecError(f"bullet_list columns must be 1 or 2; found {columns!r}")
    emphasized_count = 0
    for index, bullet in enumerate(bullets):
        if not isinstance(bullet, dict) or not bullet.get("text"):
            raise RenderSpecError(f"bullets[{index}] must be an object with text")
        if bullet.get("emphasis"):
            emphasized_count += 1
        sub = bullet.get("sub", [])
        if sub and not isinstance(sub, list):
            raise RenderSpecError(f"bullets[{index}].sub must be a list")
        if sub and len(sub) > 3:
            raise RenderSpecError(f"bullets[{index}].sub supports at most 3 items; found {len(sub)}")
    if emphasized_count > 1:
        raise RenderSpecError(f"bullet_list allows at most one emphasized bullet; found {emphasized_count}")


def _validate_closing(spec: dict) -> None:
    next_steps = _as_sequence(spec, "next_steps")
    for index, step in enumerate(next_steps):
        if not isinstance(step, dict) or not step.get("action"):
            raise RenderSpecError(f"next_steps[{index}] must be an object with an action")
    takeaways = spec.get("takeaways")
    if takeaways is not None and not isinstance(takeaways, list):
        raise RenderSpecError("takeaways must be a list")


def _validate_quote(spec: dict) -> None:
    if not spec.get("text"):
        raise RenderSpecError("quote requires text")


VALIDATORS = {
    "time_series": _validate_time_series,
    "funnel": _validate_funnel,
    "benchmark_table": _validate_benchmark_table,
    "heatmap": _validate_heatmap,
    "scatter": _validate_scatter,
    "distribution": _validate_distribution,
    "small_multiples": _validate_small_multiples,
    "cover": _validate_cover,
    "section_divider": _validate_section_divider,
    "end_cover": _validate_end_cover,
    "agenda": _validate_agenda,
    "bullet_list": _validate_bullet_list,
    "closing": _validate_closing,
    "quote": _validate_quote,
}


def validate_spec(spec: dict) -> None:
    pattern = spec.get("pattern", "")
    if pattern not in RENDERERS:
        supported = ", ".join(sorted(RENDERERS))
        raise RenderSpecError(f"unsupported pattern {pattern!r}. Supported: {supported}")
    validator = VALIDATORS.get(pattern)
    if validator:
        validator(spec)


def render(spec: dict) -> str:
    validate_spec(spec)
    pattern = spec.get("pattern", "")
    if pattern in CHROMELESS:
        body = RENDERERS[pattern](spec)
        aria = spec.get("title", "")
    else:
        body = header(spec) + RENDERERS[pattern](spec) + footer(spec)
        aria = spec.get("headline", "")
    content = "\n  ".join(body)
    background = "" if pattern in CHROMELESS else f'  <rect width="{W}" height="{H}" fill="#FFFFFF"/>\n'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{esc(aria)}">\n'
        f"{background}"
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
