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
import math
import sys
import unicodedata
from pathlib import Path

# Canvas — design tokens (single source: references/style-system.md "Design Tokens")
# Base grid unit: 8px. Margins and anchors sit on the grid; chart geometry is data-driven.
W, H = 1280, 720
ML, MR = 80, 80
CHART_TOP, CHART_BOTTOM = 208, 560

# Type scale — a role-based system (references/style-system.md "Typography"),
# not a grab-bag of pixel values. Headline, reading text, structural labels,
# and chrome keep a tested hierarchy while body copy stays legible at room
# projection scale. Every
# text-drawing call site below references one of these tokens; naked size
# literals for a text role are a bug. Two roles stay deliberately small on
# purpose and are exempt from the "reading floor" below: T_TICK (axis ticks /
# range numerals / funnel conversion %, which are referenced, not read at
# length) and T_CHROME (source line, footnotes, page number, classification —
# whisper-small by design, never raised further). Every other text role has a
# floor of T_LABEL (22px).
T_COVER_TITLE = 54       # cover / end_cover title (serif)
T_DIVIDER_TITLE = 48     # section_divider title (serif)
T_HEADLINE = 40          # content headline, <=2 lines (serif bold)
T_HEADLINE_DENSE = 32    # content headline, 3 lines (serif bold)
T_STATEMENT = 32         # quote text (serif); KPI-like big statements
T_KPI_NUM = 44           # kpi_scorecard main numbers (the hero layer)
T_SUBLINE = 24           # headline subline; cover/divider/end_cover subtitle
T_BODY = 26              # bullets, claims, takeaways, actions, agenda item
                         # titles, process step titles, benchmark row labels
T_LABEL = 22             # reading labels: sub-bullets, proofs/implications,
                         # agenda details, owner-timing metas, chart
                         # category/axis/value labels, gantt row labels,
                         # small-multiples labels, rail items on dividers
T_NUM_AGENDA = 28        # agenda numbers (serif navy)
T_NUM_CLOSING = 26       # closing takeaway numbers (serif navy)
T_TICK = 16              # axis ticks, min/max range numerals, funnel
                         # conversion %; heatmap/benchmark cell values may
                         # hold a size between this and T_LABEL when cells
                         # are tight, but never drop below this floor
T_KICKER_LABEL = 16      # structural small-caps labels (SECTION NN, KEY
                         # TAKEAWAYS, NEXT STEPS), letter-spaced
T_ANNOTATION = 24        # footer takeaway/annotation line (weight 600, BLUE)
T_CHROME = 13            # source line, footnotes, page number,
                         # classification — deliberately the smallest text
                         # on the slide; do not raise it

# Multi-line leading, derived once per token so every wrapped paragraph using
# a given text role reads at the same leading across the whole deck (rather
# than each renderer inventing its own). HALF_LINE_* is exactly half the
# advance, used to vertically center an N-line block within a fixed row: a
# 1-line block gets no offset, a 2-line block is nudged up by one half-step,
# and so on — see render_gap/render_funnel/render_heatmap/render_gantt.
LINE_H_BODY = 35           # T_BODY paragraphs; readable at room-projection scale
LINE_H_LABEL = 29          # T_LABEL paragraphs; readable at room-projection scale
HALF_LINE_BODY = LINE_H_BODY // 2
HALF_LINE_LABEL = LINE_H_LABEL // 2
NUDGE_BODY = 11            # baseline nudge centering one T_BODY line in a row
NUDGE_LABEL = 7            # baseline nudge centering one T_LABEL line in a row
X_AXIS_LABEL_LEAD = 22     # gap from CHART_BOTTOM to a below-axis category
                           # label's first line (waterfall/before_after/
                           # distribution): keeps a 2-line label's descender
                           # clear of the footer annotation band (y=630) —
                           # verified by scripts/render_slide_spec.py's
                           # renderers against real specs with both a 2-line
                           # label and an annotation present

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
        kata = ""
        for char in chunk:
            if _is_katakana(char):
                # Katakana loanwords never break mid-word (「オンボーディ/ング」
                # is a typographic defect) — a run wraps as one token.
                if run:
                    tokens.append((run, first_in_chunk))
                    run, first_in_chunk = "", False
                kata += char
                continue
            if kata:
                tokens.append((kata, first_in_chunk))
                kata, first_in_chunk = "", False
            if _char_width(char) == 2:
                if run:
                    tokens.append((run, first_in_chunk))
                    run, first_in_chunk = "", False
                tokens.append((char, first_in_chunk))
                first_in_chunk = False
            else:
                run += char
        if kata:
            tokens.append((kata, first_in_chunk))
        elif run:
            tokens.append((run, first_in_chunk))
    return tokens


def _is_katakana(char: str) -> bool:
    """Fullwidth katakana and the long-vowel mark; the middle dot (・)
    stays out so it remains a legitimate break point between words."""
    return ("ァ" <= char <= "ヺ") or char == "ー"


# Line-start kinsoku (行頭禁則): closing punctuation that must not begin a
# line. Resolved by hanging it off the previous line (ぶら下がり組) — a
# one-character overhang reads better than orphaned punctuation.
KINSOKU_HEAD = "。、．，）」』】〉》〕！？"
# Line-end kinsoku (行末禁則): opening brackets that must not end a line —
# they move down to rejoin what they open.
KINSOKU_TAIL = "（「『【〈《〔"
# Bunsetsu-ish break preference: when a Japanese line has to break, breaking
# right after one of these (punctuation or a particle) reads as a phrase
# boundary; breaking mid-word (「規定す/る」) is a defect. Heuristic, not
# morphology — but particles ARE where Japanese phrases end, and the
# backtrack is capped so a boundary-poor line still fills its width.
_BREAK_AFTER = "、。．，）」』】〉》〕！？：；・のはがをにへとでも"


def _prefer_boundary(line: str, min_width: int) -> tuple[str, str]:
    """Split a full line at the rightmost phrase boundary that keeps the
    line at least min_width wide. Returns (line, carry-to-next-line);
    carry is empty when no acceptable boundary exists (line stays as-is)."""
    for k in range(len(line) - 1, 0, -1):
        if line[k - 1] in _BREAK_AFTER and _text_width(line[:k]) >= min_width:
            return line[:k], line[k:]
    return line, ""


def _apply_kinsoku(lines: list[str]) -> list[str]:
    # Tail pass first: an opener at a line end moves down to what it opens.
    for i in range(len(lines) - 1):
        while lines[i] and lines[i][-1] in KINSOKU_TAIL:
            lines[i + 1] = lines[i][-1] + lines[i + 1]
            lines[i] = lines[i][:-1]
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
    if width < 1:
        raise RenderSpecError("wrap width must be at least 1")
    lines: list[str] = []
    current = ""
    for token, needs_space in _tokens(text):
        candidate = f"{current} {token}" if (current and needs_space) else f"{current}{token}"
        if _text_width(candidate) > width and current:
            # Break at a phrase boundary when one exists in the last 40% of
            # the line (bunsetsu-ish wrapping); the carry rejoins the next
            # line so no character is lost.
            head, carry = _prefer_boundary(current, max(int(width * 0.6), 1))
            lines.append(head)
            current = f"{carry} {token}" if (carry and needs_space) else f"{carry}{token}"
        else:
            current = candidate
        while _text_width(current) > width:
            # Hard-break tokens with no break opportunity (URLs, codes, IDs)
            # instead of letting them overflow the canvas.
            head, rest = current, ""
            while head and _text_width(head) > width:
                head, rest = head[:-1], head[-1] + rest
            if not head and rest:
                head, rest = rest[0], rest[1:]
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


PALETTES = {"navy": (BLUE, BLUE2), "red": ("#B4232D", "#D96A72"),
            "green": ("#176B50", "#439F7A"), "mono": ("#202124", "#686B70")}


def apply_palette(svg: str, spec: dict) -> str:
    primary, secondary = PALETTES[spec.get("palette", "navy")]
    # Replace paint attributes only; never change user text containing a hex code.
    for attr in ("fill", "stroke"):
        svg = svg.replace(f'{attr}="{BLUE}"', f'{attr}="{primary}"')
        svg = svg.replace(f'{attr}="{BLUE2}"', f'{attr}="{secondary}"')
    return svg


def analytical_header(spec: dict) -> list[str]:
    parts = []
    if spec.get("exhibit_label"):
        parts.append(text_el(ML, 40, spec["exhibit_label"], size=T_CHROME, fill=GREY_DARK, weight="600"))
    if spec.get("classification"):
        parts.append(text_el(W-MR, 40, spec["classification"], size=T_CHROME, fill=GREY_MED, anchor="end"))
    for i, line in enumerate(wrap(spec.get("headline", ""), 64)):
        parts.append(text_el(ML, 88+i*40, line, size=T_HEADLINE_DENSE, weight="bold", family=SANS))
    if spec.get("subline"):
        parts.append(text_el(ML, 163, spec["subline"], size=T_LABEL, fill=GREY_DARK))
    return parts


def _standard_header_layout(spec: dict) -> tuple[list[str], int, int, int]:
    headline = spec.get("headline", "")
    lines = wrap(headline, 48)  # 64 * 30/40 (old size 30 -> T_HEADLINE)
    size, line_h, subline_gap = T_HEADLINE, 52, 40
    if len(lines) > 2:
        lines = wrap(headline, 60, max_lines=3)  # 80 * 24/32 (old size 24 -> T_HEADLINE_DENSE)
        if len(lines) > 2 and spec.get("subline"):
            raise RenderSpecError(
                "three-line headline cannot include a subline; shorten the action title or remove the subline"
            )
        size, line_h, subline_gap = T_HEADLINE_DENSE, 42, 40
    return lines, size, line_h, subline_gap


def _captioned_chart_top(spec: dict) -> float:
    """Leave a full text row between a subline and a chart-top caption."""
    if not spec.get("subline") or spec.get("layout") == "analytical":
        return float(CHART_TOP)
    lines, _, line_h, subline_gap = _standard_header_layout(spec)
    last_line_y = 96 + max(len(lines) - 1, 0) * line_h
    subline_y = last_line_y + subline_gap
    return float(max(CHART_TOP, subline_y + 40))


def header(spec: dict) -> list[str]:
    if spec.get("layout") == "analytical":
        return analytical_header(spec)
    # No decorative marks: the headline itself anchors the slide (the former
    # navy kicker bar above it carried no information and was removed —
    # data-ink rule, see style-system.md Ink Discipline).
    parts: list[str] = []
    headline = spec.get("headline", "")
    executive = spec.get("theme") == "executive"
    lines, size, line_h, subline_gap = _standard_header_layout(spec)
    y = 96
    last_line_y = y
    for line in lines:
        parts.append(text_el(ML, y, line, size=size, weight="bold", family=SANS if executive else SERIF, title=headline if len(lines) > 2 else ""))
        last_line_y = y
        y += line_h
    subline = spec.get("subline", "")
    if subline:
        # Anchored to the last *drawn* headline line, not the post-loop `y`
        # (which already carries one unused extra line_h). The 40px baseline
        # gap leaves visible whitespace between the 40px headline and 24px
        # subline. At 28px, the glyph boxes were nearly touching, making the
        # subline read as an accidental
        # third title line. Three-line headlines with sublines are rejected
        # above because their combined stack cannot clear the fixed content
        # band without shrinking the slide's evidence area.
        parts.append(text_el(ML, last_line_y + subline_gap, subline, size=T_SUBLINE, fill=GREY_MED))
    classification = spec.get("classification", "")
    if classification:
        # Chrome: deliberately the smallest text on the slide, not scaled up.
        parts.append(text_el(W - MR, 40, classification.upper(), size=T_CHROME, fill=GREY_MED, weight="600", anchor="end"))
    return parts


def footer(spec: dict) -> list[str]:
    parts: list[str] = []
    annotation = spec.get("annotation", "")
    if spec.get("model_context", {}).get("kind") == "linear_model" and spec.get("interactive_result"):
        # The authored annotation remains the semantic fallback record. The
        # model exhibit already labels the value and hurdle directly, so the
        # reading surface uses its decision and recommendation only.
        result = spec["interactive_result"]
        annotation = " · ".join(str(result[key]) for key in ("decision_status", "recommendation") if result.get(key)) or annotation
    if annotation:
        # Emphasis through typography only — no decorative accent bar (data-ink rule).
        y = 630
        for line in wrap(annotation, 74, max_lines=2):  # 112 * 16/24 (old size 16 -> T_ANNOTATION)
            parts.append(text_el(ML, y, line, size=T_ANNOTATION, fill=BLUE, weight="600", title=annotation))
            y += 30  # 22 * 22/16, scaled with T_ANNOTATION
    footnotes = spec.get("footnotes", [])[:2]
    source = spec.get("source", "")
    note_y = 692 - 18 * len(footnotes)  # 16 * 13/11, scaled with T_CHROME
    for i, note in enumerate(footnotes):
        marker = "¹²"[i]
        parts.append(
            text_el(ML, note_y, f"{marker} {wrap(note, 126, max_lines=1)[0]}", size=T_CHROME, fill=GREY_MED, title=note)  # 150 * 11/13
        )
        note_y += 18
    if source:
        # Chrome: source/footnotes/page number stay the smallest text on the slide.
        parts.append(text_el(ML, 692, source, size=T_CHROME, fill=GREY_MED))
    page_number = spec.get("page_number", "")
    if page_number != "":
        parts.append(text_el(W - MR, 692, str(page_number), size=T_CHROME, fill=GREY_MED, anchor="end"))
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
    bar_w = min(88.0, span / n * 0.38) if spec.get("theme") == "executive" else min(110.0, span / n * 0.62)
    step = span / n

    def x_at(i: int) -> float:
        return ML + step * i + (step - bar_w) / 2

    def y_at(value: float) -> float:
        return CHART_BOTTOM - ((value - bottom) / (top - bottom)) * (CHART_BOTTOM - CHART_TOP)

    zero_y = y_at(0)
    parts = [
        line_el(ML, zero_y, W - MR, zero_y, GREY_BORDER if spec.get("theme") == "executive" else GREY_DARK),
        text_el(ML - 10, zero_y + 4, "0", size=T_TICK, fill=GREY_MED, anchor="end"),
    ]

    # Category-label wrap width scales with the column pitch (step), not the
    # bar width (bar_w is capped at 110px purely for visual bar weight — the
    # label sits in the full step gutter below it and only risks touching a
    # neighboring column's label, never the bar edge). Same step-based sizing
    # already used by render_distribution below; a flat bar_w-sized budget
    # here clamped real driver labels ("Enterprise new customers", "Existing
    # customer expansion") to 2 lines of 11 half-width units and silently
    # dropped the last word behind the ellipsis once bar count was low enough
    # to leave a wide step. floor 6 matches the other step-derived wraps.
    label_width = max(int(step / 11), 6)

    def bar(i: int, base: float, value_top: float, fill: str, label: str, value_text: str) -> None:
        x = x_at(i)
        y1, y2 = y_at(max(base, value_top)), y_at(min(base, value_top))
        parts.append(rect_el(x, y1, bar_w, max(y2 - y1, 2), fill))
        parts.append(text_el(x + bar_w / 2, y1 - 10, value_text, size=T_BODY if spec.get("theme") == "executive" else T_LABEL, weight="bold", anchor="middle"))
        for j, line in enumerate(wrap(label, label_width, max_lines=2)):
            parts.append(
                text_el(x + bar_w / 2, CHART_BOTTOM + X_AXIS_LABEL_LEAD + j * LINE_H_LABEL, line, size=T_LABEL, fill=GREY_DARK, anchor="middle", title=label)
            )

    bar(0, 0, start["value"], GREY_BORDER if spec.get("theme") == "executive" else BLUE, start["label"], fmt(start["value"], unit))
    running = start["value"]
    for i, driver in enumerate(drivers, start=1):
        value = driver["value"]
        fill = (GREY_MED if spec.get("theme") == "executive" else BLUE2) if value >= 0 else RED
        sign = "+" if value >= 0 else "−"
        bar(i, running, running + value, fill, driver["label"], f"{sign}{fmt(abs(value), unit)}")
        parts.append(line_el(x_at(i - 1) + bar_w, y_at(running), x_at(i), y_at(running), GREY_BORDER, "" if spec.get("theme") == "executive" else "4 3"))
        running += value
    parts.append(line_el(x_at(n - 2) + bar_w, y_at(running), x_at(n - 1), y_at(running), GREY_BORDER, "" if spec.get("theme") == "executive" else "4 3"))
    bar(n - 1, 0, end_value, BLUE, end_label, fmt(end_value, unit))
    return parts


def render_gap(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    items = spec["items"]
    explicit_scale = "value_domain" in spec
    if explicit_scale:
        domain_min, domain_max = spec["value_domain"]
        baseline = spec["baseline"]
    else:
        top = max(item["value"] for item in items) or 1
    span = W - ML - MR - 280
    # No row-height cap: like render_agenda, divide the full chart band by
    # item count so a short list fills the band instead of stopping short.
    row_h = (CHART_BOTTOM - CHART_TOP - 30) / len(items)
    bar_h = min(28.0, row_h * 0.32) if spec.get("theme") == "executive" else row_h * 0.52

    parts: list[str] = []
    for i, item in enumerate(items):
        y = CHART_TOP + 30 + i * row_h
        if explicit_scale:
            baseline_x = ML + 220 + span * _domain_fraction(baseline, domain_min, domain_max, "baseline")
            value_x = ML + 220 + span * _domain_fraction(
                item["value"], domain_min, domain_max, f"items[{i}].value"
            )
            x, width = min(baseline_x, value_x), abs(value_x - baseline_x)
        else:
            x = ML + 220
            width = span * item["value"] / top
        fill = BLUE if item.get("emphasis") else (GREY_BORDER if spec.get("theme") == "executive" else GREY_FILL)
        # Flat fill only — grey reference bars never carry a border; the
        # fill/no-fill contrast alone marks emphasis vs. context.
        label = item["label"]
        if "item_id" in item and item.get("removed"):
            label += " · " + ("除外" if spec.get("lang") == "ja" else "Removed")
        label_lines = wrap(label, 22, max_lines=2)  # 25 * 16/18
        label_y = y + bar_h / 2 + NUDGE_LABEL - (len(label_lines) - 1) * HALF_LINE_LABEL
        for line in label_lines:
            parts.append(text_el(ML, label_y, line, size=T_LABEL, fill=GREY_DARK))
            label_y += LINE_H_LABEL
        if explicit_scale:
            parts.append(rect_el(x, y, width, bar_h, fill))
        else:
            parts.append(rect_el(ML + 220, y, width, bar_h, fill))
        value_fill = BLUE if item.get("emphasis") else GREY_DARK
        value_label_x = (max(baseline_x, value_x) + 12) if explicit_scale else ML + 232 + width
        parts.append(
            text_el(value_label_x, y + bar_h / 2 + NUDGE_LABEL + 1, item.get("value_text", fmt(item["value"], unit)), size=T_LABEL, fill=value_fill, weight="bold")
        )
    gap_label = spec.get("gap_label", "")
    if gap_label:
        parts.append(text_el(W - MR, CHART_TOP + 6, gap_label, size=T_LABEL, fill=BLUE, weight="bold", anchor="end"))
    return parts


def render_before_after(spec: dict) -> list[str]:
    pairs = spec["pairs"]
    explicit_scale = "value_domain" in spec
    if explicit_scale:
        domain_min, domain_max = spec["value_domain"]
        baseline = spec["baseline"]
    else:
        top = max(max(p["before"], p["after"]) for p in pairs) * 1.15 or 1
    span = W - ML - MR
    step = span / len(pairs)
    bar_w = min(72.0, step * 0.24)

    def y_at(value: float) -> float:
        if explicit_scale:
            return CHART_BOTTOM - _domain_fraction(value, domain_min, domain_max, "value_domain") * (CHART_BOTTOM - CHART_TOP)
        return CHART_BOTTOM - (value / top) * (CHART_BOTTOM - CHART_TOP)

    baseline_y = y_at(baseline) if explicit_scale else CHART_BOTTOM
    parts = [
        line_el(ML, baseline_y, W - MR, baseline_y, GREY_DARK),
        text_el(ML - 10, baseline_y + 4, fmt(baseline, spec.get("unit", "")) if explicit_scale else "0", size=T_TICK, fill=GREY_MED, anchor="end"),
    ]
    before_label = spec.get("before_label", "Before")
    after_label = spec.get("after_label", "After")
    for i, pair in enumerate(pairs):
        unit = pair.get("unit", spec.get("unit", ""))
        cx = ML + step * i + step / 2
        bx, ax = cx - bar_w - 8, cx + 8
        by, ay = y_at(pair["before"]), y_at(pair["after"])
        # Flat fill only — the grey "before" bar never carries a border.
        if explicit_scale:
            parts.append(rect_el(bx, min(by, baseline_y), bar_w, abs(baseline_y - by), GREY_FILL))
            parts.append(rect_el(ax, min(ay, baseline_y), bar_w, abs(baseline_y - ay), BLUE))
        else:
            parts.append(rect_el(bx, by, bar_w, CHART_BOTTOM - by, GREY_FILL))
            parts.append(rect_el(ax, ay, bar_w, CHART_BOTTOM - ay, BLUE))
        # Value/legend/delta stack above the bar top by one LINE_H_LABEL
        # step each — not a flat scale of the old offsets, which pushed the
        # stack high enough to collide with the subline on a tall bar (the
        # chart's fixed 15% headroom above the tallest value didn't grow
        # just because the font did; see collision check in the type-scale
        # brief's acceptance criteria).
        parts.append(text_el(bx + bar_w / 2, by - 10, pair.get("before_text", fmt(pair["before"], unit)), size=T_LABEL, fill=GREY_MED, anchor="middle"))
        parts.append(text_el(ax + bar_w / 2, ay - 10, pair.get("after_text", fmt(pair["after"], unit)), size=T_LABEL, weight="bold", anchor="middle"))
        delta = pair["after"] - pair["before"]
        sign = "+" if delta >= 0 else "−"
        delta_y = min(by, ay) - (58 if i == 0 else 34)
        parts.append(
            text_el(cx, delta_y, pair.get("delta_text", f"{sign}{fmt(abs(delta), unit)}"), size=T_LABEL, fill=BLUE2, weight="bold", anchor="middle")
        )
        if i == 0:
            # Direct labels on the first pair replace a legend (style rule:
            # avoid legend hunting).
            parts.append(text_el(bx + bar_w / 2, by - 34, before_label, size=T_LABEL, fill=GREY_MED, anchor="middle"))
            parts.append(text_el(ax + bar_w / 2, ay - 34, after_label, size=T_LABEL, fill=GREY_DARK, weight="600", anchor="middle"))
        for j, line in enumerate(wrap(pair["label"], 17, max_lines=2)):  # 22 * 14/18
            parts.append(
                text_el(cx, CHART_BOTTOM + X_AXIS_LABEL_LEAD + j * LINE_H_LABEL, line, size=T_LABEL, fill=GREY_DARK, anchor="middle", title=pair["label"])
            )
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
        text_el(ML - 10, CHART_BOTTOM + 4, "0", size=T_TICK, fill=GREY_MED, anchor="end"),
    ]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i) for i in range(len(values))))
    parts.append(f'<polyline points="{points}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
    for i, value in enumerate(values):
        x, y = pt(i)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{BLUE}"/>')
        parts.append(text_el(x, y - 18, fmt(value, unit), size=T_LABEL, weight="bold", anchor="middle"))
        parts.append(text_el(x, CHART_BOTTOM + X_AXIS_LABEL_LEAD, labels[i], size=T_LABEL, fill=GREY_DARK, anchor="middle"))
    parts.append(text_el(ML, CHART_TOP - 12, spec["series"][0].get("label", ""), size=T_LABEL, fill=GREY_MED))
    return parts


def render_benchmark_table(spec: dict) -> list[str]:
    columns = spec["columns"]
    rows = spec["rows"]
    leaders = {tuple(pair) for pair in spec.get("leaders", [])}
    label_w = 230.0
    col_w = (W - ML - MR - label_w) / len(columns)
    executive = spec.get("theme") == "executive"
    row_h = min(96.0 if executive else 64.0, (CHART_BOTTOM + 40 - CHART_TOP) / (len(rows) + 1))
    top_y = CHART_TOP - 10
    header_h = 64.0 if executive else row_h
    if executive:
        row_h = min(96.0, (CHART_BOTTOM + 24 - top_y - header_h) / len(rows))

    parts: list[str] = []
    for j, column in enumerate(columns):
        cx = ML + label_w + col_w * j + col_w / 2
        for k, line in enumerate(wrap(column, 13, max_lines=2)):  # 18 * 13/18
            parts.append(text_el(cx, top_y + 28 + k * LINE_H_LABEL, line, size=T_LABEL, fill=GREY_MED, weight="600", anchor="middle"))
    parts.append(line_el(ML, top_y + header_h, W - MR, top_y + header_h, GREY_DARK))
    # Dense fallback (>6 columns) stays above the T_TICK floor (16px) — see
    # references/style-system.md Typography.
    value_size = (T_BODY if executive else T_LABEL) if len(columns) <= 6 else 16
    cell_width_units = max(int(col_w / (value_size * 0.62)), 6)
    value_line_h = value_size + 2
    value_nudge = round(value_size / 3)
    value_half = value_line_h / 2
    for i, row in enumerate(rows):
        y = top_y + header_h + row_h * i
        if executive and i % 2 == 0:
            parts.append(rect_el(ML, y, W - ML - MR, row_h, GREY_FILL))
        label_lines = wrap(row["label"], 16, max_lines=2)  # 28 * 15/26 (old size 15 -> T_BODY)
        ly = y + row_h / 2 + NUDGE_BODY - (len(label_lines) - 1) * HALF_LINE_BODY
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=T_BODY, fill=BLACK, weight="600", title=row["label"]))
            ly += LINE_H_BODY
        for j, value in enumerate(row["values"]):
            cx = ML + label_w + col_w * j + col_w / 2
            cell_lines = wrap(str(value), cell_width_units, max_lines=2)
            cy = y + row_h / 2 + value_nudge - (len(cell_lines) - 1) * value_half
            if (i, j) in leaders:
                if not executive:
                    parts.append(rect_el(ML + label_w + col_w * j + 6, y + 7, col_w - 12, row_h - 14, BLUE))
                for line in cell_lines:
                    parts.append(text_el(cx, cy, line, size=value_size, fill=BLUE if executive else "#FFFFFF", weight="bold", anchor="middle", title=str(value)))
                    cy += value_line_h
            else:
                for line in cell_lines:
                    parts.append(text_el(cx, cy, line, size=value_size, fill=GREY_DARK, anchor="middle", title=str(value)))
                    cy += value_line_h
        parts.append(line_el(ML, y + row_h, W - MR, y + row_h, GREY_BORDER))
    return parts


def render_summary_strip(spec: dict) -> list[str]:
    if spec.get("model_context", {}).get("kind") == "score_breakdown":
        return render_score_breakdown(spec)
    if spec.get("presentation") == "editorial":
        return render_editorial_summary(spec)
    blocks = spec["blocks"]
    span = W - ML - MR
    col_w = span / len(blocks)
    # Columns are separated by whitespace only — no vertical divider rule
    # (ink discipline: organization comes from spacing/alignment, not marks).
    # Equal 28px inner margin on every column keeps the gutter symmetric.
    pad = 28.0
    claim_width = max(1, int((col_w - pad * 2) / (T_BODY * 0.62)))
    label_width = max(1, int((col_w - pad * 2) / (T_LABEL * 0.62)))
    claim_gap, proof_gap = 10.0, 13.0  # 8 * 18/14, 10 * 18/14 (old label size 14 -> T_LABEL)

    # 2026-08-02 panel round 3: a whole-block vertical center here (matching
    # process_flow's box_h/y technique) fixed the 44% dead-space complaint
    # but overshot into a different offense — it opened a 135-205px gap
    # between the subhead and the claim line that no other text pattern on
    # the deck has. The subhead directly above this band (e.g. "Board
    # takeaways for the Q4 decision") functions as the same kind of
    # immediately-preceding label that "KEY TAKEAWAYS" is for `closing` and
    # the headline is for `bullet_list`, so it gets the same fixed top anchor
    # instead of being centered away from its content: band_start =
    # CHART_TOP + 20, identical to bullet_list's band_start. Column start
    # position no longer depends on content height, so per-block height no
    # longer needs computing here — height differences between columns show
    # up only at each column's end, not at its shared start.
    strip_top = CHART_TOP + 20

    parts: list[str] = []
    focus = spec.get("focus_block")
    has_metrics = any("metric" in block for block in blocks)
    if has_metrics:
        max_claim_lines = max(len(wrap(b["claim"], claim_width, max_lines=3)) for b in blocks)
        max_proof_lines = max(len(wrap(b["proof"], label_width, max_lines=4)) for b in blocks)
    for i, block in enumerate(blocks):
        x = ML + col_w * i
        inner_x = x + pad
        focused = i == focus
        light_focus = focused and spec.get("theme") == "executive"
        reversed_text = focused and not light_focus
        if focused:
            parts.append(rect_el(x + 8, CHART_TOP, col_w - 16, CHART_BOTTOM + 24 - CHART_TOP, "#F3F5FA" if light_focus else BLUE))
            if light_focus:
                parts.append(rect_el(x + 8, CHART_TOP, col_w - 16, 3, BLUE))
        y = strip_top + 28  # 18 * 26/17, scaled with T_BODY (claim role)
        if has_metrics:
            metric = block.get("metric", "")
            # Reserve nearly a full em per Latin glyph, including wide bold W/M.
            if not isinstance(metric, str) or _text_width(metric) * T_KPI_NUM > col_w - pad * 2:
                raise RenderSpecError("summary_strip metric must be a short string that fits its column")
            if metric:
                parts.append(text_el(inner_x, strip_top + T_KPI_NUM, metric,
                                     size=T_KPI_NUM, fill=WHITE if reversed_text else (BLUE if light_focus or focus is None else BLACK), weight="bold"))
            y = strip_top + T_KPI_NUM + 48
        for line in wrap(block["claim"], claim_width, max_lines=3):
            parts.append(text_el(inner_x, y, line, size=T_BODY, fill=WHITE if reversed_text else BLACK, weight="bold"))
            y += LINE_H_BODY
        y += claim_gap
        if has_metrics:
            y = strip_top + T_KPI_NUM + 48 + max_claim_lines * LINE_H_BODY + claim_gap
        for line in wrap(block["proof"], label_width, max_lines=4):
            parts.append(text_el(inner_x, y, line, size=T_LABEL, fill="#E5E7EB" if reversed_text else (GREY_DARK if spec.get("theme") == "executive" else GREY_MED)))
            y += LINE_H_LABEL
        y += proof_gap
        if has_metrics:
            y = strip_top + T_KPI_NUM + 48 + max_claim_lines * LINE_H_BODY + claim_gap + max_proof_lines * LINE_H_LABEL + proof_gap
        for line in wrap(block["implication"], label_width, max_lines=3):
            parts.append(text_el(inner_x, y, line, size=T_LABEL, fill=WHITE if reversed_text else BLUE, weight="600"))
            y += LINE_H_LABEL
        if focused and y - LINE_H_LABEL + 8 > CHART_BOTTOM + 24:
            raise RenderSpecError("focused summary block is too dense; shorten its text or split the slide")
    return parts


def _complete_lines(value: object, width: float, size: int, limit: int, path: str) -> list[str]:
    """Fit authored text without an ellipsis or silent loss of content."""
    if not isinstance(value, str) or not value.strip():
        raise RenderSpecError(f"{path} must be nonempty text")
    units = max(1, int(width / (size * .62)))
    lines = wrap(value, units)
    if len(lines) > limit or any(_text_width(line) > units for line in lines):
        raise RenderSpecError(f"{path} is too dense; shorten the content or split the slide")
    return lines


def _text_lines(parts: list[str], x: float, y: float, lines: list[str], *, size: int = T_LABEL,
                fill: str = GREY_DARK, weight: str = "normal", leading: float = LINE_H_LABEL) -> None:
    for index, line in enumerate(lines):
        parts.append(text_el(x, y + index * leading, line, size=size, fill=fill, weight=weight))


def render_editorial_summary(spec: dict) -> list[str]:
    blocks = spec["blocks"]
    gap = 48
    width = (W - ML - MR - gap * (len(blocks) - 1)) / len(blocks)
    parts: list[str] = []
    for index, block in enumerate(blocks):
        x = ML + index * (width + gap)
        size = 84 if index == 0 else 64
        metric = _complete_lines(block["metric"], width, size, 1, f"blocks[{index}].metric")
        _text_lines(parts, x, 294, metric, size=size, fill=BLUE, weight="bold")
        _text_lines(parts, x, 352, _complete_lines(block["claim"], width, T_BODY, 2, f"blocks[{index}].claim"),
                    size=T_BODY, fill=BLACK, weight="600", leading=LINE_H_BODY)
        _text_lines(parts, x, 430, _complete_lines(block["proof"], width, T_LABEL, 2, f"blocks[{index}].proof"))
        _text_lines(parts, x, 516, _complete_lines(block["implication"], width, T_LABEL, 2, f"blocks[{index}].implication"),
                    fill=BLUE, weight="600")
    return parts


def render_score_breakdown(spec: dict) -> list[str]:
    context = spec["model_context"]
    components, comparison = context["components"], context["comparison"]
    block = spec["blocks"][0]
    total = sum(component["value"] for component in components)
    counterfactual = total - components[comparison["remove_index"]]["value"]
    threshold = spec["interactive_result"]["threshold"]
    scale = max(total, threshold) * 1.25
    parts = [text_el(ML, 224, "Readiness contributions", size=T_LABEL, fill=GREY_DARK, weight="600")]
    row_h = 65
    bar_x, bar_w = 330, 320
    maximum = max(component["value"] for component in components) or 1
    for index, component in enumerate(components):
        y = 267 + index * row_h
        removed = index == comparison["remove_index"]
        fill = BLUE if removed else GREY_MED
        _text_lines(parts, ML, y + 5, _complete_lines(component["label"], 250, T_LABEL, 2, f"components[{index}].label"),
                    fill=BLACK if removed else GREY_DARK, weight="600" if removed else "normal")
        width = bar_w * component["value"] / maximum
        parts.append(rect_el(bar_x, y - 18, width, 26, fill))
        parts.append(text_el(bar_x + width + 12, y + 3, fmt(component["value"], ""), size=T_LABEL, fill=fill, weight="600"))
    _text_lines(parts, ML, 554, _complete_lines(block["proof"], 650, T_LABEL, 1, "blocks[0].proof"))

    right_x, total_w = 800, 352
    _text_lines(parts, right_x, 224, _complete_lines(block["claim"], 400, T_BODY, 1, "blocks[0].claim"),
                size=T_BODY, fill=BLUE, weight="600")
    _text_lines(parts, right_x, 281, _complete_lines(block["metric"], 400, T_KPI_NUM, 1, "blocks[0].metric"),
                size=T_KPI_NUM, fill=BLUE, weight="bold")
    parts.append(rect_el(right_x, 299, total_w * total / scale, 23, BLUE).replace("<rect ", '<rect id="score-total-base" ', 1))
    recommendation = _complete_lines(block["implication"], 400, T_LABEL, 2, "blocks[0].implication")
    _text_lines(parts, right_x, 350, recommendation, fill=BLUE, weight="600")
    compare_y = 402 + (len(recommendation) - 1) * LINE_H_LABEL
    _text_lines(parts, right_x, compare_y, _complete_lines(comparison["label"], 400, T_LABEL, 1, "comparison.label"))
    parts.append(text_el(right_x, compare_y + 54, fmt(counterfactual, " points"), size=T_KPI_NUM, fill=GREY_DARK, weight="bold"))
    parts.append(rect_el(right_x, compare_y + 72, total_w * counterfactual / scale, 23, GREY_MED).replace("<rect ", '<rect id="score-total-comparison" ', 1))
    gate_x = right_x + total_w * threshold / scale
    parts.append(line_el(gate_x, 289, gate_x, 332, GREY_DARK, "4 5").replace("<line ", '<line id="decision-threshold" ', 1))
    parts.append(line_el(gate_x, compare_y + 62, gate_x, compare_y + 105, GREY_DARK, "4 5")
                 .replace("<line ", '<line id="decision-threshold-comparison" ', 1))
    parts.append(text_el(gate_x, compare_y + 126, f"{fmt(threshold, '')} gate", size=T_TICK, fill=GREY_DARK, anchor="middle"))
    return parts


def render_executive_process(spec: dict) -> list[str]:
    steps = spec['steps']
    gap = 24
    width = (W - ML - MR - gap * (len(steps) - 1)) / len(steps)
    top, height = CHART_TOP + 16, 320
    parts = []
    for i, step in enumerate(steps):
        x = ML + i * (width + gap)
        hot = i == spec.get('highlight')
        title_color, detail_color = BLACK, GREY_DARK
        if hot:
            parts.append(rect_el(x, top, width, height, '#F3F5FA'))
        parts.append(rect_el(x, top, width, 3, BLUE if hot else GREY_BORDER))
        parts.append(text_el(x + 18, top + 34, f'{i + 1:02d}', size=T_NUM_AGENDA, fill=title_color))
        for field, baseline, size, limit in [('label', 84, T_BODY, 2), ('detail', 168, T_LABEL, 3)]:
            budget = max(6, int((width - 36) / (size * .62)))
            lines = wrap(str(step.get(field, '')), budget)
            if len(lines) > limit:
                raise RenderSpecError(f'executive process {field} is too long; shorten it or split the flow')
            for j, line in enumerate(lines):
                parts.append(text_el(x + 18, top + baseline + j * (LINE_H_BODY if field == 'label' else LINE_H_LABEL), line,
                                     size=size, fill=title_color if field == 'label' else detail_color,
                                     weight='600' if field == 'label' else 'normal'))
        meta = ' · '.join(str(step[k]) for k in ('owner','duration') if step.get(k))
        lines = wrap(meta, max(6, int((width - 36) / (T_LABEL * .62))))
        if len(lines) > 2:
            raise RenderSpecError('executive process owner/duration is too long; shorten it or split the flow')
        for j, line in enumerate(lines):
            parts.append(text_el(x + 18, top + 270 + j * LINE_H_LABEL, line, size=T_LABEL, fill=detail_color))
        if i < len(steps) - 1:
            cx, cy = x + width + gap / 2, top + height / 2
            parts.append(f'<path d="M {cx-4} {cy-6} L {cx+3} {cy} L {cx-4} {cy+6}" fill="none" stroke="{GREY_MED}" stroke-width="2"/>')
    return parts


def render_executive_matrix(spec: dict) -> list[str]:
    x, y, width, height = ML + 32, CHART_TOP + 16, 640, 320
    mid_x, mid_y = x + width/2, y + height/2
    parts = [rect_el(x, y, width, height, WHITE, GREY_BORDER)]
    focus = spec.get('focus_quadrant')
    if focus is not None:
        parts.append(rect_el(x + (width/2 if focus % 2 else 0), y + (height/2 if focus >= 2 else 0), width/2, height/2, '#EFF3FB'))
    parts.extend([line_el(mid_x,y,mid_x,y+height), line_el(x,mid_y,x+width,mid_y)])
    for (qx,qy,anchor),label in zip([(x+12,y+24,'start'),(x+width-12,y+24,'end'),(x+12,y+height-12,'start'),(x+width-12,y+height-12,'end')], spec.get('quadrants',[])):
        lines = wrap(str(label), 24)
        if len(lines)>1:
            raise RenderSpecError('executive matrix quadrant label is too long; shorten it')
        parts.append(text_el(qx,qy,label,size=T_TICK,fill=GREY_MED,anchor=anchor))
    xa, ya = spec['x_axis'], spec['y_axis']
    parts.extend([text_el(mid_x,y+height+48,xa['label'],size=T_LABEL,anchor='middle',weight='600'),
                  text_el(ML,y-10,ya['label'],size=T_LABEL,weight='600'),
                  text_el(x,y+height+24,xa.get('low','Low'),size=T_TICK,fill=GREY_MED),
                  text_el(x+width,y+height+24,xa.get('high','High'),size=T_TICK,fill=GREY_MED,anchor='end'),
                  text_el(x-10,y+16,ya.get('high','High'),size=T_TICK,fill=GREY_MED,anchor='end'),
                  text_el(x-10,y+height,ya.get('low','Low'),size=T_TICK,fill=GREY_MED,anchor='end')])
    legend_x = x + width + 44
    parts.append(text_el(legend_x,y+12,spec.get('legend_title','Options'),size=T_KICKER_LABEL,fill=GREY_MED,weight='600'))
    for i, point in enumerate(spec['points']):
        px,py=x+width*point['x']/100,y+height*(1-point['y']/100)
        emphasized = point.get('emphasis')
        color = BLUE if emphasized else GREY_DARK
        fill = BLUE if emphasized else WHITE
        stroke = BLUE if emphasized else GREY_BORDER
        parts.append(f'<circle cx="{px}" cy="{py}" r="15" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        parts.append(text_el(px,py+5,f'{i+1:02d}',size=T_TICK,fill=WHITE if emphasized else GREY_DARK,anchor='middle',weight='600'))
        baseline=y+54+i*48
        parts.append(text_el(legend_x,baseline,f'{i+1:02d}',size=T_LABEL,fill=color,weight='600'))
        lines=wrap(point['label'],max(6,int((W-MR-legend_x-40)/(T_LABEL*.62))))
        if len(lines)>2:
            raise RenderSpecError('executive matrix option label is too long; shorten it or split the diagram')
        for j,line in enumerate(lines):
            parts.append(text_el(legend_x+40,baseline+j*LINE_H_LABEL,line,size=T_LABEL,fill=color,weight='600' if point.get('emphasis') else 'normal'))
    return parts


def render_process_flow(spec: dict) -> list[str]:
    if spec.get("theme") == "executive":
        return render_executive_process(spec)
    steps = spec["steps"]
    highlight = spec.get("highlight", -1)
    span = W - ML - MR
    gap = 26.0
    box_w = (span - gap * (len(steps) - 1)) / len(steps)
    # 152px — grown from 104 to hold the same worst-case content (2-line
    # title, 2-line detail) at T_BODY/T_LABEL instead of a hollow box with
    # leftover whitespace below (see examples/render-specs and templates/decks
    # for the longest step content actually seen).
    box_h = 152.0
    y = (CHART_TOP + CHART_BOTTOM) / 2 - box_h / 2

    parts: list[str] = []
    for i, step in enumerate(steps):
        x = ML + i * (box_w + gap)
        is_hot = i == highlight
        # Flat fill only — grey step boxes never carry a border.
        parts.append(rect_el(x, y, box_w, box_h, BLUE if is_hot else GREY_FILL))
        title_fill = "#FFFFFF" if is_hot else BLACK
        detail_fill = "#E5E7EB" if is_hot else GREY_MED
        ty, text_width = y + 38, int(box_w / (T_BODY * 0.62))
        parts.append(text_el(x + 16, ty - 16, f"{i + 1:02d}", size=T_LABEL, fill=BLUE2 if not is_hot else "#E5E7EB", weight="bold"))
        for line in wrap(step["label"], text_width, max_lines=2):
            parts.append(text_el(x + 16, ty + 8, line, size=T_BODY, fill=title_fill, weight="bold"))
            ty += LINE_H_BODY
        detail_width = int(box_w / (T_LABEL * 0.62))
        for line in wrap(step.get("detail", ""), detail_width, max_lines=3):
            parts.append(text_el(x + 16, ty + 14, line, size=T_LABEL, fill=detail_fill))
            ty += LINE_H_LABEL
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
    executive = spec.get("theme") == "executive"
    bar_h = min(28.0, row_h * 0.4) if executive else min(row_h * 0.66, 60.0)
    span = W - ML - MR - 330
    cx = ML + 210 + span / 2

    parts: list[str] = []
    for i, stage in enumerate(stages):
        y = CHART_TOP + row_h * i + (row_h - bar_h) / 2
        bw = max(span * stage["value"] / top_value, 6)
        parts.append(rect_el(cx - bw / 2, y, bw, bar_h, BLUE if not executive or i == len(stages) - 1 else GREY_BORDER))
        label_lines = wrap(stage["label"], 20, max_lines=2)  # 24 * 15/18
        ly = y + bar_h / 2 + NUDGE_LABEL - (len(label_lines) - 1) * HALF_LINE_LABEL
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=T_LABEL, fill=GREY_DARK))
            ly += LINE_H_LABEL
        value_text = fmt(stage["value"], unit)
        if bw > 110 and not executive:
            parts.append(text_el(cx, y + bar_h / 2 + NUDGE_LABEL + 1, value_text, size=T_LABEL, fill="#FFFFFF", weight="bold", anchor="middle"))
        else:
            parts.append(text_el(cx + bw / 2 + 11, y + bar_h / 2 + NUDGE_LABEL + 1, value_text, size=T_LABEL, weight="bold"))
        if i > 0:
            previous_value = stages[i - 1]["value"]
            conversion = "n/a" if previous_value == 0 else f"{stage['value'] / previous_value * 100:.0f}%"
            # Funnel conversion % is explicitly a T_TICK role (referenced, not read at length).
            parts.append(
                text_el(cx + span / 2 + 28, CHART_TOP + row_h * i + 5, f"↓ {conversion}", size=T_TICK, fill=BLUE2, weight="600")
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


def _heatmap_value_size(cell_w: float, cell_h: float) -> int:
    """Pick the largest size in the T_LABEL..T_TICK range that comfortably
    fits a short value string in the cell — never below the T_TICK floor
    (16px) even for a dense grid (see references/style-system.md Typography:
    "heatmap cell values may hold a size between this and T_LABEL when cells
    are tight, but never drop below this floor")."""
    for candidate in (T_LABEL, 20, 18, T_TICK):
        if cell_w >= candidate * 3.5 and cell_h >= candidate * 1.6:
            return candidate
    return T_TICK


def render_heatmap(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    rows, columns, values = spec["rows"], spec["columns"], spec["values"]
    flat = [v for row in values for v in row]
    vmin, vmax = min(flat), max(flat)
    diverging = bool(spec.get("diverging", vmin < 0 < vmax))
    label_w = 210.0
    cell_w = (W - ML - MR - label_w) / len(columns)
    cell_h = min(72.0, (CHART_BOTTOM - CHART_TOP - 30) / len(rows))
    value_size = _heatmap_value_size(cell_w, cell_h)
    value_nudge = round(value_size * 0.36)

    parts: list[str] = []
    for j, column in enumerate(columns):
        cx = ML + label_w + cell_w * j + cell_w / 2
        parts.append(text_el(cx, CHART_TOP + 15, column, size=T_LABEL, fill=GREY_MED, weight="600", anchor="middle"))  # 12 * 18/14
    for i, row_label in enumerate(rows):
        y = CHART_TOP + 26 + cell_h * i
        label_lines = wrap(row_label, 18, max_lines=2)  # 24 * 14/18
        ly = y + cell_h / 2 + NUDGE_LABEL - (len(label_lines) - 1) * HALF_LINE_LABEL
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=T_LABEL, fill=GREY_DARK, title=row_label))
            ly += LINE_H_LABEL
        for j, value in enumerate(values[i]):
            x = ML + label_w + cell_w * j
            fill = _heatmap_cell_fill(value, vmin, vmax, diverging)
            parts.append(rect_el(x + 2, y + 2, cell_w - 4, cell_h - 4, fill))
            # Pick the value color by measured contrast so mid-tone cells stay
            # WCAG-readable instead of trusting a fixed threshold.
            parts.append(
                text_el(
                    x + cell_w / 2,
                    y + cell_h / 2 + value_nudge,
                    fmt(value, unit),
                    size=value_size,
                    fill=_cell_text_color(fill),
                    weight="600",
                    anchor="middle",
                )
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
        parts.append(text_el(x + col_w / 2, CHART_TOP, period, size=T_LABEL, fill=GREY_MED, weight="600", anchor="middle"))
        parts.append(line_el(x, grid_top, x, grid_bottom, GREY_BORDER))
    parts.append(line_el(W - MR, grid_top, W - MR, grid_bottom, GREY_BORDER))
    parts.append(line_el(ML, grid_top, W - MR, grid_top, GREY_DARK))
    for i, bar in enumerate(bars):
        y = grid_top + row_h * i
        label_lines = wrap(bar["label"], 21, max_lines=2)  # 28 * 14/18
        ly = y + row_h / 2 + NUDGE_LABEL - (len(label_lines) - 1) * HALF_LINE_LABEL
        for line in label_lines:
            parts.append(text_el(ML, ly, line, size=T_LABEL, fill=GREY_DARK))
            ly += LINE_H_LABEL
        bx = ML + label_w + col_w * bar["start"] + 3
        bw = col_w * (bar["end"] - bar["start"] + 1) - 6
        hot = bar.get("highlight")
        # Flat fill only — the grey reference bar never carries a border.
        parts.append(rect_el(bx, y + (row_h - 24) / 2, bw, 24, BLUE if hot else (GREY_BORDER if spec.get("theme") == "executive" else GREY_FILL)))
        note = bar.get("note", "")
        if note and spec.get("theme") == "executive":
            if _text_width(note) * T_LABEL * .62 > bw - 16:
                raise RenderSpecError("gantt note does not fit its bar; shorten it or move it to the annotation")
            parts.append(text_el(bx + 8, y + row_h / 2 + NUDGE_LABEL, note, size=T_LABEL, fill=WHITE if hot else GREY_DARK))
        elif note:
            # Clamp to whatever room remains between the bar and the right
            # margin — a bar late in the timeline leaves little room, and
            # T_LABEL is wide enough now that an unclamped note can run well
            # past the canvas edge.
            note_x = bx + bw + 10
            note_width_units = max(int((W - MR - note_x) / (T_LABEL * 0.62)), 6)
            note_text = wrap(note, note_width_units, max_lines=1)[0]
            parts.append(
                text_el(note_x, y + row_h / 2 + NUDGE_LABEL, note_text, size=T_LABEL, fill=GREY_MED, title=note if note_text.endswith(ELLIPSIS) else "")
            )
        parts.append(line_el(ML, y + row_h, W - MR, y + row_h, GREY_BORDER))
    for gate in gates:
        gx = ML + label_w + col_w * (gate["period"] + 1)
        gy = grid_bottom + 12
        parts.append(f'<path d="M {gx:.1f} {gy - 8:.1f} L {gx + 8:.1f} {gy:.1f} L {gx:.1f} {gy + 8:.1f} L {gx - 8:.1f} {gy:.1f} Z" fill="{BLUE}"/>')
        parts.append(text_el(gx, gy + 36, gate["label"], size=T_LABEL, fill=BLUE, weight="600", anchor="middle"))  # 24 * 18/12
    return parts


def render_kpi_scorecard(spec: dict) -> list[str]:
    metrics = spec["metrics"]
    cols = spec.get("columns", 3)
    gap = 24.0
    card_w = (W - ML - MR - gap * (cols - 1)) / cols
    n_rows = -(-len(metrics) // cols)
    card_h = min(150.0, (CHART_BOTTOM - CHART_TOP) / n_rows - 14)
    # Label/value baselines are proportional to card_h (not fixed pixel
    # offsets), so a taller grid (more metric rows, smaller card_h) still
    # clears T_KPI_NUM's larger hero number instead of the value baseline
    # colliding with the target line beneath it. At the common card_h=150
    # this reproduces the previous fixed offsets (30, 88) exactly.
    label_y_offset = round(card_h * 0.2)
    value_y_offset = round(card_h * 88 / 150)

    parts: list[str] = []
    for i, metric in enumerate(metrics):
        x = ML + (i % cols) * (card_w + gap)
        y = CHART_TOP + (i // cols) * (card_h + 18)
        # Flat fill only — no border, no status accent bar (ink discipline: the
        # no accent-bar motif on cards). Status still reads
        # through the trend color below and the value/target text itself.
        parts.append(rect_el(x, y, card_w, card_h, "#FFFFFF"))
        parts.append(text_el(x + 24, y + label_y_offset, metric["label"], size=T_LABEL, fill=GREY_MED, weight="600"))
        parts.append(text_el(x + 24, y + value_y_offset, str(metric["value"]), size=T_KPI_NUM, weight="bold"))
        trend = metric.get("trend", "")
        if trend:
            trend_fill = RED if metric.get("status") == "risk" else BLUE2
            parts.append(text_el(x + card_w - 18, y + value_y_offset, trend, size=T_LABEL, fill=trend_fill, weight="600", anchor="end"))
        target = metric.get("target", "")
        if target:
            parts.append(text_el(x + 24, y + card_h - 16, f"{'目標：' if spec.get('lang') == 'ja' else 'Target: '}{target}", size=T_LABEL, fill=GREY_MED))
    return parts


def render_two_by_two(spec: dict) -> list[str]:
    if spec.get("theme") == "executive":
        return render_executive_matrix(spec)
    plot_x = ML + 50
    plot_w = W - MR - plot_x - 50
    plot_y = _captioned_chart_top(spec)
    plot_h = float(CHART_BOTTOM - plot_y)
    mid_x, mid_y = plot_x + plot_w / 2, plot_y + plot_h / 2
    x_axis, y_axis = spec["x_axis"], spec["y_axis"]
    quadrants = spec.get("quadrants", [])

    parts = [
        rect_el(plot_x, plot_y, plot_w, plot_h, "#FFFFFF", GREY_BORDER),
        line_el(mid_x, plot_y, mid_x, plot_y + plot_h, GREY_BORDER),
        line_el(plot_x, mid_y, plot_x + plot_w, mid_y, GREY_BORDER),
    ]
    corners = [
        (plot_x + 21, plot_y + 36, "start"),
        (plot_x + plot_w - 21, plot_y + 36, "end"),
        (plot_x + 21, plot_y + plot_h - 18, "start"),
        (plot_x + plot_w - 21, plot_y + plot_h - 18, "end"),
    ]
    for (qx, qy, anchor), label in zip(corners, quadrants):
        parts.append(text_el(qx, qy, label.upper(), size=T_LABEL, fill=GREY_MED, weight="600", anchor=anchor))  # 12 * 18/12
    # Axis title and its min/max range numerals share one baseline row —
    # the title (T_LABEL) sets the offset; the T_TICK range numbers ride
    # the same row rather than sitting on their own slightly-different one.
    parts.append(text_el(mid_x, plot_y + plot_h + 39, x_axis["label"], size=T_LABEL, fill=GREY_DARK, weight="600", anchor="middle"))
    parts.append(text_el(plot_x, plot_y + plot_h + 39, x_axis.get("low", "Low"), size=T_TICK, fill=GREY_MED))
    parts.append(text_el(plot_x + plot_w, plot_y + plot_h + 39, x_axis.get("high", "High"), size=T_TICK, fill=GREY_MED, anchor="end"))
    parts.append(text_el(plot_x - 14, plot_y + 10, y_axis.get("high", "High"), size=T_TICK, fill=GREY_MED, anchor="end"))
    parts.append(text_el(plot_x - 14, plot_y + plot_h, y_axis.get("low", "Low"), size=T_TICK, fill=GREY_MED, anchor="end"))
    # Keep the caption close to its plot. _captioned_chart_top() moves the
    # complete plot down only when a multi-line header needs the clearance.
    parts.append(text_el(ML, plot_y - 9, y_axis["label"], size=T_LABEL, fill=GREY_DARK, weight="600"))
    for point in spec["points"]:
        px = plot_x + plot_w * point["x"] / 100
        py = plot_y + plot_h * (1 - point["y"] / 100)
        emphasis = point.get("emphasis")
        radius = 9 if emphasis else 7
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius}" fill="{BLUE if emphasis else GREY_MED}"/>')
        # Flip the label to the point's left when it would otherwise run
        # past the right margin — T_LABEL is wide enough now that a point
        # near the plot's right edge could push its label off the canvas.
        label_w = _text_width(point["label"]) * T_LABEL * 0.62
        if px + radius + 8 + label_w > W - MR:
            label_x, anchor = px - radius - 8, "end"
        else:
            label_x, anchor = px + radius + 8, "start"
        parts.append(
            text_el(
                label_x,
                py + 6,
                point["label"],
                size=T_LABEL,
                fill=BLACK if emphasis else GREY_DARK,
                weight="600" if emphasis else "normal",
                anchor=anchor,
            )
        )
    return parts


def render_cover(spec: dict) -> list[str]:
    """Navy cover slide. Bypasses the standard white header/footer chrome."""
    if spec.get("presentation") == "editorial":
        parts = [rect_el(0, 0, W, H, NAVY_COVER)]
        if spec.get("classification"):
            parts.append(text_el(ML, 96, spec["classification"].upper(), size=T_KICKER_LABEL, fill="#D1DAEF", weight="600"))
        _text_lines(parts, ML, 282, _complete_lines(spec["title"], W - ML - MR, 80, 2, "title"),
                    size=80, fill=WHITE, weight="600", leading=90)
        title_lines = len(_complete_lines(spec["title"], W - ML - MR, 80, 2, "title"))
        if spec.get("subtitle"):
            _text_lines(parts, ML, 355 + (title_lines - 1) * 90,
                        _complete_lines(spec["subtitle"], 1020, T_STATEMENT, 2, "subtitle"),
                        size=T_STATEMENT, fill="#E5E7EB", leading=43)
        if spec.get("presenter"):
            _text_lines(parts, ML, 616, _complete_lines(spec["presenter"], 1120, T_BODY, 1, "presenter"),
                        size=T_BODY, fill=WHITE)
        if spec.get("date"):
            _text_lines(parts, ML, 652, _complete_lines(spec["date"], 1120, T_LABEL, 1, "date"), fill="#D1DAEF")
        return parts
    parts = [
        rect_el(0, 0, W, H, NAVY_COVER),
    ]
    y = 264
    for line in wrap(spec.get("title", ""), 38, max_lines=3):  # 40 * 52/54
        parts.append(text_el(ML, y, line, size=T_COVER_TITLE, fill=WHITE, family=SANS if spec.get("theme") == "executive" else SERIF, weight="600" if spec.get("theme") == "executive" else "normal"))
        y += 66  # 64 * 54/52
    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 70, max_lines=2):
            parts.append(text_el(ML, y, line, size=T_SUBLINE, fill="#E5E7EB"))
            y += 32
    meta = " · ".join(str(spec[k]) for k in ("presenter", "date") if spec.get(k))
    if meta:
        parts.append(text_el(ML, 640, meta, size=T_LABEL, fill="#E5E7EB"))
    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 640, classification.upper(), size=T_CHROME, fill="#E5E7EB", anchor="end"))
    return parts


def render_scatter(spec: dict) -> list[str]:
    if spec.get("model_context", {}).get("kind") == "linear_model":
        return render_model_scatter(spec)
    points = spec["points"]
    x_axis, y_axis = spec["x_axis"], spec["y_axis"]
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    x_explicit = "domain" in x_axis
    y_explicit = "domain" in y_axis
    if x_explicit:
        x_min, x_max = x_axis["domain"]
        x_pad = 0
    else:
        x_min, x_max = min(xs + [0]) if spec.get("x_zero", False) else min(xs), max(xs)
        x_pad = (x_max - x_min) * 0.08 or 1
        x_min, x_max = x_min - x_pad, x_max + x_pad
    if y_explicit:
        y_min, y_max = y_axis["domain"]
        y_pad = 0
    else:
        y_min, y_max = min(ys + [0]) if spec.get("y_zero", False) else min(ys), max(ys)
        y_pad = (y_max - y_min) * 0.08 or 1
        y_min, y_max = y_min - y_pad, y_max + y_pad
    plot_x, plot_w = ML + 50, W - ML - MR - 100
    plot_y = _captioned_chart_top(spec)
    plot_h = float(CHART_BOTTOM - plot_y)

    def px(value: float) -> float:
        if x_explicit:
            return plot_x + plot_w * _domain_fraction(value, x_min, x_max, "x_axis.domain")
        return plot_x + plot_w * (value - x_min) / (x_max - x_min)

    def py(value: float) -> float:
        if y_explicit:
            return plot_y + plot_h * (1 - _domain_fraction(value, y_min, y_max, "y_axis.domain"))
        return plot_y + plot_h * (1 - (value - y_min) / (y_max - y_min))

    parts = [
        line_el(plot_x, plot_y + plot_h, plot_x + plot_w, plot_y + plot_h, GREY_DARK),
        line_el(plot_x, plot_y, plot_x, plot_y + plot_h, GREY_DARK),
        text_el((plot_x + plot_x + plot_w) / 2, plot_y + plot_h + 44, x_axis["label"], size=T_LABEL, fill=GREY_DARK, weight="600", anchor="middle"),
        # Keep the caption close to its plot. _captioned_chart_top() provides
        # the clearance from a multi-line header when one is present.
        text_el(ML, plot_y - 9, y_axis["label"], size=T_LABEL, fill=GREY_DARK, weight="600"),
        # Disclosed axis ranges keep non-zero baselines honest (chart rule).
        text_el(plot_x, plot_y + plot_h + 23, x_axis["tick_labels"][0] if "tick_labels" in x_axis else fmt(x_min + x_pad, x_axis.get("unit", "")), size=T_TICK, fill=GREY_MED),
        text_el(plot_x + plot_w, plot_y + plot_h + 23, x_axis["tick_labels"][1] if "tick_labels" in x_axis else fmt(x_max - x_pad, x_axis.get("unit", "")), size=T_TICK, fill=GREY_MED, anchor="end"),
        text_el(plot_x - 10, plot_y + 10, y_axis["tick_labels"][1] if "tick_labels" in y_axis else fmt(y_max - y_pad, y_axis.get("unit", "")), size=T_TICK, fill=GREY_MED, anchor="end"),
        text_el(plot_x - 10, plot_y + plot_h, y_axis["tick_labels"][0] if "tick_labels" in y_axis else fmt(y_min + y_pad, y_axis.get("unit", "")), size=T_TICK, fill=GREY_MED, anchor="end"),
    ]
    for point in points:
        cx, cy = px(point["x"]), py(point["y"])
        emphasis = point.get("emphasis")
        radius = 9 if emphasis else 7
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="{BLUE if emphasis else GREY_MED}"/>')
        label = point.get("label", "")
        if "item_id" in point and point.get("removed"):
            label += " · " + ("除外" if spec.get("lang") == "ja" else "Removed")
        if label:
            # Decide the flip side off the label's *raw* (unclamped) width —
            # T_LABEL is wide enough now that a point near the plot's right
            # edge could push an unflipped label off the canvas — then clamp
            # to whichever side's actual margin budget was chosen, not a
            # fixed char count. A flat 17-unit clamp truncated legitimate
            # short labels ("Guided, enterprise", 18 units) that had ample
            # room on either side; this reuses the same px-per-unit constant
            # (T_LABEL * 0.62) already used below for the margin check itself.
            raw_w = _text_width(label) * T_LABEL * 0.62
            if cx + radius + 8 + raw_w > W - MR:
                label_x, anchor = cx - radius - 8, "end"
                avail_px = label_x - ML
            else:
                label_x, anchor = cx + radius + 8, "start"
                avail_px = (W - MR) - label_x
            label_w_units = max(int(avail_px / (T_LABEL * 0.62)), 6)
            clamped = wrap(label, label_w_units, max_lines=1)[0]
            parts.append(
                text_el(
                    label_x,
                    cy + 7,
                    clamped,
                    size=T_LABEL,
                    fill=BLACK if emphasis else GREY_DARK,
                    weight="600" if emphasis else "normal",
                    anchor=anchor,
                    title=label,
                )
            )
    return parts


def render_model_scatter(spec: dict) -> list[str]:
    context, x_axis, y_axis = spec["model_context"], spec["x_axis"], spec["y_axis"]
    x_min, x_max = x_axis["domain"]
    y_min, y_max = y_axis["domain"]
    left, right, top, bottom = ML + 70, W - MR - 20, CHART_TOP + 20, CHART_BOTTOM
    px = lambda x: left + (right - left) * _domain_fraction(x, x_min, x_max, "x_axis.domain")
    py = lambda y: bottom - (bottom - top) * _domain_fraction(y, y_min, y_max, "y_axis.domain")
    parts = [text_el(ML, CHART_TOP, y_axis["label"], size=T_LABEL, fill=GREY_DARK, weight="600")]
    for index in range(5):
        value = y_min + (y_max - y_min) * index / 4
        y = py(value)
        parts.append(line_el(left, y, right, y, GREY_BORDER))
        parts.append(text_el(left - 15, y + 5, fmt(value, y_axis.get("unit", "")), size=T_TICK, fill=GREY_MED, anchor="end"))
    for index in range(6):
        value = x_min + (x_max - x_min) * index / 5
        x = px(value)
        parts.append(text_el(x, bottom + 27, fmt(value, x_axis.get("unit", "")), size=T_TICK, fill=GREY_MED, anchor="middle"))
    # Keep the axis caption above the footer's 630px annotation baseline.
    # Tick labels sit to either side of the centered caption, so this tighter
    # baseline does not squeeze either text role into the footer.
    parts.append(text_el((left + right) / 2, bottom + 39, x_axis["label"], size=T_LABEL, fill=GREY_DARK, anchor="middle", weight="600"))
    intercept, coefficient = context["intercept"], context["coefficient"]
    start, end = x_min, x_max
    if coefficient:
        crossings = sorted(((y_min - intercept) / coefficient, (y_max - intercept) / coefficient))
        start, end = max(start, crossings[0]), min(end, crossings[1])
    if start <= end and y_min <= intercept + coefficient * start <= y_max:
        parts.append(line_el(px(start), py(intercept + coefficient * start), px(end), py(intercept + coefficient * end), BLUE)
                     .replace("<line ", '<line id="model-relationship" stroke-width="3" ', 1))
    result = spec.get("interactive_result", {})
    if result.get("quantity") == y_axis.get("quantity") and "threshold" in result:
        threshold = result["threshold"]
        if y_min <= threshold <= y_max:
            y = py(threshold)
            parts.append(line_el(left, y, right, y, BLUE2, "6 6").replace("<line ", '<line id="decision-threshold" ', 1))
            parts.append(text_el(right, y - 12, "Hurdle " + fmt(threshold, y_axis.get("unit", "")), size=T_LABEL, fill=BLUE2, anchor="end", weight="600"))
    for point in spec["points"]:
        x, y = px(point["x"]), py(point["y"])
        parts.append(line_el(x, y, x, bottom, GREY_MED, "3 5"))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{BLUE}" stroke="{WHITE}" stroke-width="3"/>')
        label = f"{fmt(point['x'], x_axis.get('unit', ''))} · {fmt(point['y'], y_axis.get('unit', ''))}"
        label_width = _text_width(label) * T_BODY * .62
        anchor, text_x = ("end", x - 18) if x + 18 + label_width > right else ("start", x + 18)
        baseline = y + 38 if y + 72 < bottom else y - 52
        parts.append(text_el(text_x, baseline, label, size=T_BODY, fill=BLUE, weight="bold", anchor=anchor))
        # When the point repeats the named y quantity, the axis caption is
        # already its visible label. Avoid a duplicate line over the grid.
        if point.get("label") and point["label"] != y_axis["label"]:
            parts.append(text_el(text_x, baseline + 30, point["label"], size=T_LABEL, fill=GREY_DARK, anchor=anchor))
    return parts


def render_distribution(spec: dict) -> list[str]:
    unit = spec.get("unit", "")
    bins = spec["bins"]
    highlight = spec.get("highlight", -1)
    top = max(b["value"] for b in bins) * 1.15 or 1
    span = 748 if spec.get("commentary") else W - ML - MR
    step = span / len(bins)
    executive = spec.get("theme") == "executive"
    bar_w = min(88.0, step * 0.38) if executive else step * 0.82
    label_size = 24 if executive else T_LABEL

    parts = [
        line_el(ML, CHART_BOTTOM, ML + span, CHART_BOTTOM, GREY_BORDER if executive else GREY_DARK),
        text_el(ML - 10, CHART_BOTTOM + 4, "0", size=T_TICK, fill=GREY_MED, anchor="end"),
    ]
    for i, bucket in enumerate(bins):
        x = ML + step * i + (step - bar_w) / 2
        h = (bucket["value"] / top) * (CHART_BOTTOM - CHART_TOP)
        y = CHART_BOTTOM - h
        is_hot = i == highlight
        # Flat fill only — grey context bars never carry a border.
        parts.append(rect_el(x, y, bar_w, max(h, 1), BLUE if is_hot else (GREY_BORDER if spec.get("layout") == "analytical" else GREY_FILL)))
        parts.append(
            text_el(x + bar_w / 2, y - 11, fmt(bucket["value"], unit), size=24 if executive else T_LABEL, weight="bold" if is_hot else "normal", fill=BLACK if is_hot else GREY_MED, anchor="middle")
        )
        for j, line in enumerate(wrap(bucket["label"], max(int((step - 16) / (label_size * .62)), 6) if executive else max(int(step / 11), 6), max_lines=2)):  # divisor 8 * 18/12
            parts.append(text_el(x + bar_w / 2, CHART_BOTTOM + X_AXIS_LABEL_LEAD + j * (24 if executive else LINE_H_LABEL), line, size=label_size, fill=GREY_DARK, anchor="middle", title=bucket["label"]))
    if spec.get("commentary"):
        rail = spec["commentary"]
        parts.append(line_el(868, CHART_TOP, 868, CHART_BOTTOM))
        y = CHART_TOP + 20
        for line in wrap(rail["title"], 27):
            parts.append(text_el(896, y, line, size=T_LABEL, weight="bold", fill=BLUE))
            y += LINE_H_LABEL
        y += 24
        for point in rail["points"]:
            for line in wrap(point, 27):
                parts.append(text_el(896, y, line, size=T_LABEL, fill=GREY_DARK))
                y += LINE_H_LABEL
            y += 20
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
        parts.append(
            text_el(
                x,
                y + 18,  # 14 * 18/14
                wrap(chart["label"], int(panel_w / (T_LABEL * 0.62)), max_lines=1)[0],
                size=T_LABEL,
                fill=BLACK if emphasis else GREY_DARK,
                weight="600",
                title=chart["label"],
            )
        )
        spark_top, spark_h = y + 33, panel_h - 62  # label clearance + value-line clearance scaled with T_LABEL
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
        parts.append(text_el(x + panel_w, y + panel_h - 6, fmt(values[-1], unit), size=T_LABEL, weight="bold", fill=BLUE if emphasis else GREY_DARK, anchor="end"))
        parts.append(text_el(x, y + panel_h - 6, fmt(values[0], unit), size=T_LABEL, fill=GREY_MED))
    return parts


def render_section_divider(spec: dict) -> list[str]:
    """Navy full-bleed section divider (小扉). Bypasses header/footer chrome,
    mirroring render_cover's geometry (see CHROMELESS)."""
    parts = [rect_el(0, 0, W, H, NAVY_COVER)]
    section_number = spec["section_number"]
    parts.append(
        text_el(ML, 236, f"SECTION {section_number:02d}", size=T_KICKER_LABEL, fill="#E5E7EB", weight="600")
    )

    title = spec.get("title", "")
    y = 284
    lines = wrap(title, 33, max_lines=2)  # 40 * 40/48
    truncated = bool(lines) and lines[-1].endswith(ELLIPSIS)
    for line in lines:
        parts.append(text_el(ML, y, line, size=T_DIVIDER_TITLE, fill=WHITE, family=SANS if spec.get("theme") == "executive" else SERIF, title=title if truncated else ""))
        y += 60  # 50 * 48/40

    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 63, max_lines=2):  # 70 * 18/20
            parts.append(text_el(ML, y, line, size=T_SUBLINE, fill="#E5E7EB"))
            y += 29  # 26 * 20/18

    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 40, classification.upper(), size=T_CHROME, fill="#E5E7EB", weight="600", anchor="end"))

    # Section rail: skip entirely rather than overlap or overflow (measured in
    # the same half-width character units `wrap`/`_text_width` already use).
    sections = spec.get("sections", [])
    if sections:
        rail_y = 604
        px_per_unit = T_LABEL * 0.62
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
                    parts.append(text_el(x, rail_y, item, size=T_LABEL, fill=WHITE, weight="600"))
                else:
                    parts.append(
                        f'<text x="{x:.1f}" y="{rail_y:.1f}" font-family="{SANS}" font-size="{T_LABEL}" '
                        f'fill="#E5E7EB" opacity="0.55">{esc(item)}</text>'
                    )
                x += item_w + gap_units * px_per_unit
    return parts


def render_end_cover(spec: dict) -> list[str]:
    """Navy full-bleed back cover. Mirrors render_cover geometry exactly, with
    a contact block and a default title so a bare {"pattern": "end_cover"}
    still renders."""
    parts = [rect_el(0, 0, W, H, NAVY_COVER)]
    y = 264
    for line in wrap(spec.get("title") or "Thank you", 38, max_lines=3):  # 40 * 52/54
        parts.append(text_el(ML, y, line, size=T_COVER_TITLE, fill=WHITE, family=SANS if spec.get("theme") == "executive" else SERIF, weight="600" if spec.get("theme") == "executive" else "normal"))
        y += 66  # 64 * 54/52
    subtitle = spec.get("subtitle", "")
    if subtitle:
        y += 8
        for line in wrap(subtitle, 70, max_lines=2):
            parts.append(text_el(ML, y, line, size=T_SUBLINE, fill="#E5E7EB"))
            y += 32
    contact = (spec.get("contact") or [])[:4]
    cy = 560
    for line in contact:
        parts.append(text_el(ML, cy, str(line), size=T_LABEL, fill="#E5E7EB"))
        cy += 29
    meta = " · ".join(str(spec[k]) for k in ("presenter", "date") if spec.get(k))
    if meta:
        parts.append(text_el(ML, 640, meta, size=T_LABEL, fill="#E5E7EB"))
    classification = spec.get("classification", "")
    if classification:
        parts.append(text_el(W - MR, 640, classification.upper(), size=T_CHROME, fill="#E5E7EB", anchor="end"))
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
    detail_width_units = max(int((col_w - detail_offset) / (T_LABEL * 0.62)), 8)
    title_width_units = max(int((detail_offset - 54) / (T_BODY * 0.62)), 8)  # 46 * 28/24, scaled with T_NUM_AGENDA

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
            baseline = y + row_h / 2 + 8  # 6 * 22/17, scaled with T_BODY (title role)
            emphasized = current == index
            if emphasized:
                parts.append(rect_el(col_x, y, col_w, row_h, BLUE_TINT))
            parts.append(text_el(col_x, baseline, f"{index:02d}", size=T_NUM_AGENDA, fill=BLUE, family=SERIF))
            title_lines = wrap(item["title"], title_width_units, max_lines=1)
            title_text = title_lines[0] if title_lines else ""
            parts.append(
                text_el(
                    col_x + 54,  # 46 * 28/24, scaled with T_NUM_AGENDA
                    baseline,
                    title_text,
                    size=T_BODY,
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
                        size=T_LABEL,
                        fill=GREY_MED,
                        title=detail if detail_text.endswith(ELLIPSIS) else "",
                    )
                )
    return parts


def _center_block_start(start: float, end: float, heights: list[float], gap: float) -> float:
    """Return the y at which to begin drawing a stack of items so the whole
    block sits vertically centered within [start, end], rather than
    expanding the inter-item gap to chase the band's bottom edge.

    No renderer currently calls this — `summary_strip` was the last one
    (removed 2026-08-02 panel round 3: it centered the claim/proof/
    implication stack as a block, but the subhead directly above the band
    functions as the same kind of content-introducing label `bullet_list`
    and `closing` have, so centering-as-a-block detached it from that label
    the same way it once did for those two — see their fixed band_start
    anchors instead). Kept as a tested helper for a future pattern whose
    content band truly has no preceding label to stay anchored under.

    When the band is too tight to hold the block at all (natural height >=
    available height), there is no slack to distribute: the block starts at
    `start` and is left to overflow toward `end`, same as before.
    """
    n = len(heights)
    if n == 0:
        return start
    natural_height = sum(heights) + gap * max(n - 1, 0)
    slack = max(0.0, (end - start) - natural_height)
    return start + slack / 2


def render_bullet_list(spec: dict) -> list[str]:
    """Action-title bullet slide. One marker family (square bullets, en-dash
    subs) — no accent bars, per the single-motif ink-discipline rule."""
    if _ranked_bullets(spec):
        return render_ranked_bullets(spec)
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
    text_width_units = max(int((col_w - text_indent) / (T_BODY * 0.62)), 10)
    sub_width_units = max(int((col_w - sub_indent) / (T_LABEL * 0.62)), 10)
    band_start = float(CHART_TOP) + 20

    parts: list[str] = []
    for c, group in enumerate(column_bullets):
        col_x = ML + c * (col_w + gap)
        # Pre-wrap every bullet once so its rendered height is known before
        # laying out rows.
        rendered: list[tuple[dict, list[str], list[list[str]]]] = []
        for bullet in group:
            lines = wrap(bullet["text"], text_width_units)
            subs = bullet.get("sub", [])[:3]
            sub_lines = [wrap(str(sub), sub_width_units) for sub in subs]
            rendered.append((bullet, lines, sub_lines))
        # Divide [band_start, CHART_BOTTOM] into one row per bullet — the
        # same "fill the band by row count" technique render_gap and
        # render_agenda use — instead of centering the whole column as one
        # block (that shifted bullet 1 away from band_start by however much
        # slack a short list left, per column count). 2026-08-02 panel round
        # 3: centering each item *within* its own row degenerated to the
        # same whole-block bug whenever a row was much taller than its
        # content (e.g. a single-bullet list, where row_h == the entire
        # band) — bullets[0] measured 154px below band_start instead of
        # sitting under the headline. Each item now anchors to its row's top
        # edge instead, so item 1 always starts at band_start regardless of
        # bullet count; leftover space collects after the last item, same
        # as every other row-divided pattern (gap, agenda, gantt).
        row_h = (CHART_BOTTOM - band_start) / len(group)
        for i, (bullet, lines, sub_lines) in enumerate(rendered):
            row_top = band_start + i * row_h
            y = row_top
            emphasized = bool(bullet.get("emphasis"))
            text_fill = BLUE if emphasized else BLACK
            weight = "600" if emphasized else "normal"
            marker_y = y
            parts.append(rect_el(col_x, marker_y - 14, 6, 6, BLUE))  # -10 * 22/16, scaled with T_BODY
            for line in lines:
                parts.append(text_el(col_x + text_indent, y, line, size=T_BODY, fill=text_fill, weight=weight))
                y += LINE_H_BODY
            if sub_lines:
                y += 6
                for sl in sub_lines:
                    for j, line in enumerate(sl):
                        prefix = f"– {line}" if j == 0 else f"  {line}"
                        parts.append(text_el(col_x + sub_indent, y, prefix, size=T_LABEL, fill=GREY_DARK))
                        y += LINE_H_LABEL
    return parts


def _ranked_bullets(spec: dict) -> bool:
    return "value_domain" in spec and bool(spec.get("bullets")) and all(
        isinstance(bullet, dict) and "metric" in bullet and "rank" in bullet for bullet in spec["bullets"]
    )


def render_ranked_bullets(spec: dict) -> list[str]:
    domain_min, domain_max = spec["value_domain"]
    comparison = spec.get("model_context")
    if comparison and comparison.get("kind") == "scenario_compare" and 2 <= len(spec["bullets"]) <= 3:
        return render_rank_bridge(spec)
    compared = {value["item_id"]: value for value in comparison["values"]} if comparison else {}
    parts: list[str] = []
    bar_x, bar_w = 350, 710
    parts.append(text_el(bar_x, 218, "Base case", size=T_LABEL, fill=BLUE, weight="600"))
    if comparison:
        parts.append(text_el(bar_x + 270, 218, comparison["label"], size=T_LABEL, fill=BLUE2, weight="600"))
    row_h = 300 / len(spec["bullets"])
    for index, bullet in enumerate(spec["bullets"]):
        y = 258 + index * row_h
        _text_lines(parts, ML, y + 16, _complete_lines(bullet["text"], 240, T_BODY, 1, f"bullets[{index}].text"),
                    size=T_BODY, fill=BLUE if bullet.get("emphasis") else BLACK, weight="600")
        for sub_index, sub in enumerate(bullet.get("sub", [])):
            _text_lines(parts, ML, y + 47 + sub_index * LINE_H_LABEL,
                        _complete_lines(sub, 240, T_LABEL, 1, f"bullets[{index}].sub[{sub_index}]"))
        rows = [(bullet["metric"], bullet["rank"], BLUE)]
        if comparison:
            alternate = compared[bullet["item_id"]]
            rows.append((alternate["value"], alternate["rank"], BLUE2))
        for state_index, (value, rank, fill) in enumerate(rows):
            bar_y = y + state_index * 29
            width = bar_w * _domain_fraction(value, domain_min, domain_max, "value_domain")
            parts.append(rect_el(bar_x, bar_y, width, 18, fill).replace("<rect ", f'<rect id="rank-bar-{index}-{state_index}" ', 1))
            parts.append(text_el(bar_x + width + 12, bar_y + 17, f"{fmt(value, '')} · #{rank}", size=T_LABEL, fill=fill, weight="600"))
    parts.append(line_el(bar_x, 558, bar_x + bar_w, 558, GREY_BORDER))
    for index in range(5):
        value = domain_min + (domain_max - domain_min) * index / 4
        parts.append(text_el(bar_x + bar_w * index / 4, 582, fmt(value, ""), size=T_TICK, fill=GREY_MED, anchor="middle"))
    return parts


def render_rank_bridge(spec: dict) -> list[str]:
    """Compare categorical ranks without using line slopes as metric changes."""
    comparison = spec["model_context"]
    compared = {item["item_id"]: item for item in comparison["values"]}
    bullets = spec["bullets"]
    gains = [(item["rank"] - compared[item["item_id"]]["rank"], index)
             for index, item in enumerate(bullets)]
    gain, focus = max(gains, key=lambda entry: (entry[0], -entry[1]))
    focus = focus if gain > 0 else None
    row_gap = min(110, 330 / max(1, len(bullets) - 1))
    row_y = lambda rank: 300 + (rank - 1) * row_gap
    ja = spec.get("lang") == "ja"
    domain_min, domain_max = spec["value_domain"]
    caption = ("優先順位・スコア " if ja else "Priority rank · score ") + f"{fmt(domain_min, '')}–{fmt(domain_max, '')}"
    parts = [text_el(100, 202, "通常" if ja else "Base", size=T_BODY, fill=GREY_DARK, weight="600"),
             text_el(900, 202, comparison["label"], size=T_LABEL, fill=GREY_DARK, weight="600"),
             text_el(100, 238, caption, size=20, fill=GREY_MED)]
    # Draw the highlighted bridge last, with white clearance at crossings.
    order = [index for index in range(len(bullets)) if index != focus]
    if focus is not None:
        order.append(focus)
    for index in order:
        item = bullets[index]
        alternate = compared[item["item_id"]]
        y1, y2 = row_y(item["rank"]), row_y(alternate["rank"])
        active = index == focus
        if active:
            parts.append(line_el(420, y1, 860, y2, WHITE).replace("<line ", '<line stroke-width="12" ', 1))
        parts.append(line_el(420, y1, 860, y2, BLUE if active else GREY_BORDER)
                     .replace("<line ", f'<line id="rank-bridge-{index}" stroke-width="{5 if active else 2}" ', 1))
    for index, item in enumerate(bullets):
        active = index == focus
        color = BLUE if active else GREY_DARK
        for side, x, rank_x, score_x, value, rank in (
            ("base", 148, 100, 392, item["metric"], item["rank"]),
            ("current", 948, 900, 1192, compared[item["item_id"]]["value"], compared[item["item_id"]]["rank"]),
        ):
            y = row_y(rank)
            if active:
                parts.append(rect_el(x - 12, y - 38, 284, 76, "#EDF2FA"))
            parts.append(text_el(rank_x, y + 9, str(rank), size=T_LABEL, fill=GREY_MED, anchor="end"))
            label = item["text"].removesuffix(" route") if not ja else item["text"]
            parts.append(text_el(x, y + 10, label, size=30, fill=color, weight="600" if active else "normal", title=item["text"])
                         .replace("<text ", f'<text id="rank-{side}-label-{index}" ', 1))
            parts.append(text_el(score_x, y + 13, fmt(value, ""), size=40, fill=color, weight="600", anchor="end")
                         .replace("<text ", f'<text id="rank-{side}-score-{index}" ', 1))
    if focus is not None:
        item = bullets[focus]
        alternate = compared[item["item_id"]]
        delta = alternate["value"] - item["metric"]
        change = ("+" if delta > 0 else "") + fmt(delta, "")
        unit = spec.get("unit", "points")
        statement = (f'{item["text"]}: {item["rank"]}位 → {alternate["rank"]}位（{change} {unit}）' if ja else
                     f'{item["text"].removesuffix(" route")}: #{item["rank"]} → #{alternate["rank"]} · {change} {unit}')
        parts.append(text_el(100, 620, statement, size=T_BODY, fill=BLUE, weight="600"))
    return parts


def render_closing(spec: dict) -> list[str]:
    """Key-takeaways / next-steps closing slide. call_to_action rides the
    existing footer "annotation" slot mechanics (blue 600) instead of a new
    motif — this mutates `spec` in place so the render() dispatch's later
    footer(spec) call picks it up, without touching footer() itself."""
    call_to_action = spec.get("call_to_action", "")
    if call_to_action:
        spec.setdefault("annotation", call_to_action)

    if spec.get("presentation") == "editorial":
        return render_editorial_closing(spec)

    takeaways = (spec.get("takeaways") or [])[:4]
    next_steps = spec["next_steps"][:5]
    parts: list[str] = []

    if takeaways:
        left_w = (W - ML - MR) * 0.45
        col_gap = 40.0
        right_x = ML + left_w + col_gap
        right_w = (W - ML - MR) - left_w - col_gap
        text_indent = 42.0  # 32 * 26/20, scaled with T_NUM_CLOSING so the takeaway text clears the bigger number
        text_width_units = max(int((left_w - text_indent) / (T_BODY * 0.62)), 10)
        detail_width_units = max(int(right_w / (T_BODY * 0.62)), 10)

        band_start = float(CHART_TOP) + 34

        parts.append(text_el(ML, CHART_TOP, "要点" if spec.get("lang") == "ja" else "KEY TAKEAWAYS", size=T_KICKER_LABEL, fill=GREY_MED, weight="600"))
        # Divide [band_start, CHART_BOTTOM] into one row per takeaway (the
        # render_gap/render_agenda "fill the band by row count" technique)
        # instead of centering the whole list as one block — that shifted
        # item 1 away from the label by however much slack a short list left
        # (worse the fewer items there are). 2026-08-02 panel round 3:
        # centering each item *within* its own row reintroduced the same
        # degeneration whenever the row itself is most of the band — a
        # single takeaway measured 182px below the "KEY TAKEAWAYS" label
        # instead of sitting right under it. Each item now anchors to its
        # row's top edge instead, so item 1 always starts at band_start
        # regardless of list length; leftover space collects after the last
        # item, same as every other row-divided pattern.
        takeaway_lines = [wrap(str(t), text_width_units, max_lines=3) for t in takeaways]
        takeaway_row_h = (CHART_BOTTOM - band_start) / len(takeaways)
        for i, (takeaway, lines) in enumerate(zip(takeaways, takeaway_lines)):
            row_top = band_start + i * takeaway_row_h
            y = row_top
            parts.append(text_el(ML, y, str(i + 1), size=T_NUM_CLOSING, fill=BLUE, family=SERIF, weight="bold"))
            ly = y
            for line in lines:
                parts.append(
                    text_el(ML + text_indent, ly, line, size=T_BODY, fill=BLACK, title=str(takeaway) if line.endswith(ELLIPSIS) else "")
                )
                ly += LINE_H_BODY

        parts.append(text_el(right_x, CHART_TOP, "実行事項" if spec.get("lang") == "ja" else "NEXT STEPS", size=T_KICKER_LABEL, fill=GREY_MED, weight="600"))
        step_lines = [wrap(step["action"], detail_width_units, max_lines=2) for step in next_steps]
        step_metas = [" · ".join(str(step[k]) for k in ("owner", "timing") if step.get(k)) for step in next_steps]
        step_row_h = (CHART_BOTTOM - band_start) / len(next_steps)
        for i, (step, lines, meta) in enumerate(zip(next_steps, step_lines, step_metas)):
            row_top = band_start + i * step_row_h
            y = row_top
            for line in lines:
                parts.append(
                    text_el(right_x, y, line, size=T_BODY, fill=BLACK, weight="600", title=step["action"] if line.endswith(ELLIPSIS) else "")
                )
                y += LINE_H_BODY
            if meta:
                y += 4
                parts.append(text_el(right_x, y, meta, size=T_LABEL, fill=GREY_MED))
    else:
        row_h = min(64.0, (CHART_BOTTOM - CHART_TOP) / len(next_steps))
        # 260 reserved the right-aligned "Owner · Timing" meta's column at
        # the old T_LABEL size (13px); scaled to 440 by 22/13 so a full-width
        # action line no longer runs into the bigger meta text at the row's
        # right edge.
        action_width_units = max(int((W - ML - MR - 440) / (T_BODY * 0.62)), 10)
        for r in range(len(next_steps) + 1):
            ry = CHART_TOP + row_h * r
            parts.append(line_el(ML, ry, W - MR, ry, GREY_BORDER))
        for i, step in enumerate(next_steps):
            row_y = CHART_TOP + row_h * i
            lines = wrap(step["action"], action_width_units, max_lines=2)
            baseline = row_y + row_h / 2 - (len(lines) - 1) * HALF_LINE_BODY + NUDGE_BODY
            ay = baseline
            for line in lines:
                parts.append(
                    text_el(ML, ay, line, size=T_BODY, fill=BLACK, weight="600", title=step["action"] if line.endswith(ELLIPSIS) else "")
                )
                ay += LINE_H_BODY
            meta = " · ".join(str(step[k]) for k in ("owner", "timing") if step.get(k))
            if meta:
                parts.append(text_el(W - MR, row_y + row_h / 2 + NUDGE_LABEL, meta, size=T_LABEL, fill=GREY_MED, anchor="end"))
    return parts


def render_editorial_closing(spec: dict) -> list[str]:
    takeaways, steps = spec["takeaways"], spec["next_steps"]
    gap = 48
    width = (W - ML - MR - gap * (len(steps) - 1)) / len(steps)
    parts: list[str] = []
    for index, (takeaway, step) in enumerate(zip(takeaways, steps)):
        x = ML + index * (width + gap)
        if step.get("timing"):
            _text_lines(parts, x, 218, _complete_lines(step["timing"], width, T_LABEL, 1, f"next_steps[{index}].timing"), fill=GREY_MED, weight="600")
        _text_lines(parts, x, 266, _complete_lines(takeaway, width, T_STATEMENT, 2, f"takeaways[{index}]"),
                    size=T_STATEMENT, fill=BLUE, weight="600", leading=42)
        parts.append(line_el(x, 343, x + width, 343, GREY_BORDER))
        _text_lines(parts, x, 390, _complete_lines(step["action"], width, T_BODY, 3, f"next_steps[{index}].action"),
                    size=T_BODY, fill=BLACK, weight="600", leading=LINE_H_BODY)
        if step.get("owner"):
            _text_lines(parts, x, 523, _complete_lines(step["owner"], width, T_LABEL, 1, f"next_steps[{index}].owner"))
    return parts


T_QUOTE_MARK = 103  # decorative opening mark, not a reading role; scaled with
                     # T_STATEMENT's growth (90px mark : 28px quote text before)


def render_quote(spec: dict) -> list[str]:
    """Pull-quote slide: one oversized opening quotation mark (structural
    motif, no closing mark) plus attributed text."""
    text = spec["text"]
    parts = [text_el(ML, CHART_TOP + 70, "“", size=T_QUOTE_MARK, fill=BLUE_TINT, family=SERIF)]
    x = ML + 60
    y = CHART_TOP + 160
    lines = wrap(text, 50, max_lines=4)  # 58 * 28/32
    truncated = bool(lines) and lines[-1].endswith(ELLIPSIS)
    for line in lines:
        parts.append(text_el(x, y, line, size=T_STATEMENT, fill=BLACK, family=SERIF, title=text if truncated else ""))
        y += 46  # 40 * 32/28
    attribution = spec.get("attribution", "")
    if attribution:
        y += 29  # 20 * 22/15, scaled with T_LABEL
        parts.append(text_el(x, y, f"— {attribution}", size=T_LABEL, fill=GREY_DARK, weight="600"))
        y += 32
    context = spec.get("context", "")
    if context:
        parts.append(text_el(x, y, context, size=T_LABEL, fill=GREY_MED))
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
    if spec.get("theme") == "executive" and (len(rows) > 5 or len(columns) > 6):
        raise RenderSpecError("executive benchmark tables support at most 5 rows and 6 criteria; split the comparison across slides")
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


def _explicit_domain(domain: object, field_path: str) -> tuple[float, float]:
    if not isinstance(domain, list) or len(domain) != 2:
        raise RenderSpecError(f"{field_path} must be a two-number domain")
    for index, value in enumerate(domain):
        try:
            finite = math.isfinite(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else False
        except OverflowError:
            finite = False
        if not finite:
            raise RenderSpecError(f"{field_path}[{index}] must be finite")
    if domain[0] >= domain[1]:
        raise RenderSpecError(f"{field_path} must be strictly increasing")
    return domain[0], domain[1]


def _inside_domain(value: object, field_path: str, domain: tuple[float, float]) -> None:
    try:
        finite = math.isfinite(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else False
    except OverflowError:
        finite = False
    if not finite:
        raise RenderSpecError(f"{field_path} must be finite")
    if not domain[0] <= value <= domain[1]:
        raise RenderSpecError(f"{field_path} must be inside its declared domain")


def _domain_fraction(value: float, domain_min: float, domain_max: float, field_path: str) -> float:
    """Return a stable [0, 1] ratio without collapsing distinct endpoints."""
    try:
        span = domain_max - domain_min
        offset = value - domain_min
        try:
            finite_span = math.isfinite(span)
        except OverflowError:
            finite_span = False
        if span != 0 and finite_span:
            fraction = offset / span
            if math.isfinite(fraction):
                return fraction

        # Subtracting opposite-sign finite floats can overflow. Normalize only
        # for that case; ordinary subtraction preserves adjacent large ints.
        scale = max(abs(domain_min), abs(domain_max))
        normalized_min = domain_min / scale
        normalized_max = domain_max / scale
        normalized_value = value / scale
        normalized_span = normalized_max - normalized_min
        if normalized_span == 0:
            raise RenderSpecError(f"{field_path} has a numerically unrepresentable span")
        fraction = (normalized_value - normalized_min) / normalized_span
        if not math.isfinite(fraction):
            raise RenderSpecError(f"{field_path} cannot be mapped to finite coordinates")
        return fraction
    except RenderSpecError:
        raise
    except (OverflowError, ZeroDivisionError, TypeError) as exc:
        raise RenderSpecError(f"{field_path} cannot be mapped to finite coordinates") from exc


def _validate_explicit_domain(spec: dict) -> None:
    pattern = spec.get("pattern")
    if pattern in ("gap", "before_after") and "value_domain" in spec:
        domain = _explicit_domain(spec["value_domain"], "value_domain")
        if "baseline" not in spec:
            raise RenderSpecError("baseline is required with value_domain")
        _inside_domain(spec["baseline"], "baseline", domain)
        if pattern == "gap":
            for index, item in enumerate(spec.get("items", [])):
                value = item.get("value") if isinstance(item, dict) else None
                _inside_domain(value, f"items[{index}].value", domain)
        else:
            for index, pair in enumerate(spec.get("pairs", [])):
                before = pair.get("before") if isinstance(pair, dict) else None
                after = pair.get("after") if isinstance(pair, dict) else None
                _inside_domain(before, f"pairs[{index}].before", domain)
                _inside_domain(after, f"pairs[{index}].after", domain)
    elif pattern == "scatter":
        domains: dict[str, tuple[float, float]] = {}
        for axis_key, coordinate in (("x_axis", "x"), ("y_axis", "y")):
            axis = spec.get(axis_key, {})
            if "domain" not in axis:
                continue
            domains[coordinate] = _explicit_domain(axis["domain"], f"{axis_key}.domain")
            zero_flag = f"{coordinate}_zero"
            if spec.get(zero_flag) is True and not domains[coordinate][0] <= 0 <= domains[coordinate][1]:
                raise RenderSpecError(f"{zero_flag} conflicts with {axis_key}.domain")
        for index, point in enumerate(spec.get("points", [])):
            for coordinate, domain in domains.items():
                _inside_domain(point.get(coordinate), f"points[{index}].{coordinate}", domain)


def _validate_distribution(spec: dict) -> None:
    bins = _as_sequence(spec, "bins")
    for index, bucket in enumerate(bins):
        if not isinstance(bucket, dict) or "label" not in bucket or "value" not in bucket:
            raise RenderSpecError(f"bins[{index}] must include label and value")
        if not isinstance(bucket["value"], (int, float)):
            raise RenderSpecError(f"bins[{index}].value must be numeric")
        if spec.get("layout") == "analytical" and (not math.isfinite(bucket["value"]) or bucket["value"] < 0):
            raise RenderSpecError("analytical bar values must be finite and nonnegative")


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
    columns = spec.get("columns", 1)
    if columns not in (1, 2):
        raise RenderSpecError(f"bullet_list columns must be 1 or 2; found {columns!r}")
    maximum = 12 if columns == 2 else 6
    if len(bullets) > maximum:
        raise RenderSpecError(
            f"bullet_list supports at most {maximum} bullets; found {len(bullets)}"
        )
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
    if _ranked_bullets(spec):
        if columns != 1 or len(bullets) > 4:
            raise RenderSpecError("ranked bullet evidence requires one column and at most four items")
        domain = _explicit_domain(spec["value_domain"], "value_domain")
        if domain[0] != 0:
            raise RenderSpecError("ranked bars require a zero baseline")
        ranks = []
        for index, bullet in enumerate(bullets):
            _inside_domain(bullet["metric"], f"bullets[{index}].metric", domain)
            if type(bullet["rank"]) is not int or not 1 <= bullet["rank"] <= len(bullets):
                raise RenderSpecError("rank must be an integer within the displayed items")
            ranks.append(bullet["rank"])
            if len(bullet.get("sub", [])) > 1:
                raise RenderSpecError("ranked bars support one supporting line per item")
        if len(set(ranks)) != len(ranks):
            raise RenderSpecError("ranked bars require distinct ranks")
        return

    # Count wrapped lines against the same per-row geometry used by the
    # renderer. Larger reading type must never be "solved" by letting a
    # legal-looking spec paint into the next row; the author must split or
    # simplify the slide instead.
    if columns == 2:
        half = -(-len(bullets) // 2)
        column_bullets = [bullets[:half], bullets[half:]]
    else:
        column_bullets = [bullets]
    gap = 60.0
    col_w = (W - ML - MR - gap) / 2 if columns == 2 else float(W - ML - MR)
    text_indent = 22.0
    sub_indent = text_indent + 24.0
    text_width_units = max(int((col_w - text_indent) / (T_BODY * 0.62)), 10)
    sub_width_units = max(int((col_w - sub_indent) / (T_LABEL * 0.62)), 10)
    band_start = float(CHART_TOP) + 20
    source_index = 0
    for group in column_bullets:
        row_h = (CHART_BOTTOM - band_start) / len(group)
        for bullet in group:
            body_lines = wrap(bullet["text"], text_width_units)
            sub_lines = [wrap(str(sub), sub_width_units) for sub in bullet.get("sub", [])]
            content_h = len(body_lines) * LINE_H_BODY
            if sub_lines:
                content_h += 6 + sum(len(lines) for lines in sub_lines) * LINE_H_LABEL
            if content_h > row_h:
                raise RenderSpecError(
                    f"bullets[{source_index}] needs {content_h}px but its row allows "
                    f"{row_h:.1f}px; shorten the content or split the slide"
                )
            source_index += 1


def _validate_closing(spec: dict) -> None:
    next_steps = _as_sequence(spec, "next_steps")
    for index, step in enumerate(next_steps):
        if not isinstance(step, dict) or not step.get("action"):
            raise RenderSpecError(f"next_steps[{index}] must be an object with an action")
    takeaways = spec.get("takeaways")
    if takeaways is not None and not isinstance(takeaways, list):
        raise RenderSpecError("takeaways must be a list")
    if spec.get("presentation") == "editorial":
        if not takeaways or len(takeaways) != len(next_steps) or not 2 <= len(next_steps) <= 3:
            raise RenderSpecError("editorial closing requires two or three matched takeaways and next steps")
        return
    if not takeaways:
        return

    # The two-column closing layout uses equal row budgets in each column.
    # Validate the rendered line counts before drawing so 26px actions and
    # 22px metadata cannot collide when the input is too dense.
    visible_takeaways = takeaways[:4]
    visible_steps = next_steps[:5]
    left_w = (W - ML - MR) * 0.45
    col_gap = 40.0
    right_w = (W - ML - MR) - left_w - col_gap
    text_indent = 42.0
    takeaway_width_units = max(int((left_w - text_indent) / (T_BODY * 0.62)), 10)
    step_width_units = max(int(right_w / (T_BODY * 0.62)), 10)
    band_start = float(CHART_TOP) + 34

    takeaway_row_h = (CHART_BOTTOM - band_start) / len(visible_takeaways)
    for index, takeaway in enumerate(visible_takeaways):
        lines = wrap(str(takeaway), takeaway_width_units, max_lines=3)
        content_h = len(lines) * LINE_H_BODY
        if content_h > takeaway_row_h:
            raise RenderSpecError(
                f"takeaways[{index}] needs {content_h}px but its row allows "
                f"{takeaway_row_h:.1f}px; shorten the content or split the slide"
            )

    step_row_h = (CHART_BOTTOM - band_start) / len(visible_steps)
    for index, step in enumerate(visible_steps):
        lines = wrap(step["action"], step_width_units, max_lines=2)
        meta = " · ".join(str(step[key]) for key in ("owner", "timing") if step.get(key))
        content_h = len(lines) * LINE_H_BODY + (4 + LINE_H_LABEL if meta else 0)
        if content_h > step_row_h:
            raise RenderSpecError(
                f"next_steps[{index}] needs {content_h}px but its row allows "
                f"{step_row_h:.1f}px; shorten the content or split the slide"
            )


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
    if spec.get("theme", "classic") not in ("classic", "executive"):
        raise RenderSpecError("theme must be classic or executive")
    if spec.get("layout", "standard") not in ("standard", "analytical"):
        raise RenderSpecError("layout must be standard or analytical")
    if spec.get("palette", "navy") not in PALETTES:
        raise RenderSpecError("palette must be navy, red, green, or mono")
    if "presentation" in spec:
        if spec["presentation"] != "editorial" or pattern not in ("cover", "summary_strip", "closing"):
            raise RenderSpecError("editorial presentation is supported on cover, summary_strip, and closing only")
        if pattern == "summary_strip":
            blocks = _as_sequence(spec, "blocks")
            if not 2 <= len(blocks) <= 3 or any(not isinstance(block, dict) or any(key not in block for key in ("metric", "claim", "proof", "implication")) for block in blocks):
                raise RenderSpecError("editorial summary requires two or three complete metric blocks")
    if spec.get("layout") == "analytical":
        if pattern in CHROMELESS:
            raise RenderSpecError("analytical layout requires a content slide")
        if len(wrap(spec.get("headline", ""), 64)) > 2:
            raise RenderSpecError("analytical headline exceeds two lines; shorten it")
        if len(wrap(spec.get("subline", ""), 96)) > 1:
            raise RenderSpecError("analytical subline is too long")
    if "commentary" in spec:
        rail = spec["commentary"]
        if pattern != "distribution" or not isinstance(rail, dict):
            raise RenderSpecError("commentary is supported on distribution slides only")
        if not isinstance(rail.get("title"), str) or not isinstance(rail.get("points"), list) or not 1 <= len(rail["points"]) <= 3 or not all(isinstance(x,str) and x.strip() for x in rail["points"]):
            raise RenderSpecError("commentary needs a title and one to three text points")
        lines = len(wrap(rail["title"], 27)) + sum(len(wrap(x,27)) for x in rail["points"])
        if lines*LINE_H_LABEL + len(rail["points"])*20 + 44 > CHART_BOTTOM-CHART_TOP:
            raise RenderSpecError("commentary is too dense; shorten or split it")
        if len(spec.get("bins", [])) > 6:
            raise RenderSpecError("commentary charts allow up to six bars")
    if "focus_block" in spec:
        focus = spec["focus_block"]
        if pattern != "summary_strip" or type(focus) is not int or not 0 <= focus < len(spec.get("blocks", [])):
            raise RenderSpecError("focus_block must identify one summary_strip block")
    if spec.get("theme") == "executive" and pattern in ("process_flow", "two_by_two"):
        key = "steps" if pattern == "process_flow" else "points"
        entries = _as_sequence(spec, key)
        if len(entries) > (5 if pattern == "process_flow" else 6):
            raise RenderSpecError("too many items for an executive diagram; split it across slides")
        if pattern == "two_by_two":
            for point in entries:
                for axis in ("x", "y"):
                    if not isinstance(point.get(axis), (int,float)) or not 0 <= point[axis] <= 100:
                        raise RenderSpecError("matrix coordinates must be between 0 and 100")
            if "focus_quadrant" in spec and (type(spec["focus_quadrant"]) is not int or not 0 <= spec["focus_quadrant"] <= 3):
                raise RenderSpecError("focus_quadrant must be 0, 1, 2, or 3")
    validator = VALIDATORS.get(pattern)
    if validator:
        validator(spec)
    _validate_explicit_domain(spec)
    _validate_interactive_exact_text(spec)
    _validate_model_context(spec)


def _finite_number(value: object, path: str) -> float:
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise RenderSpecError(f"{path} must be a finite number")
    return value


def _strict_fields(value: object, required: set[str], path: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise RenderSpecError(f"{path} requires exactly {', '.join(sorted(required))}")
    return value


def _validate_model_context(spec: dict) -> None:
    if "model_context" not in spec:
        return
    context = spec["model_context"]
    if not isinstance(context, dict):
        raise RenderSpecError("model_context must be an object")
    kind, pattern = context.get("kind"), spec["pattern"]
    if kind == "linear_model" and pattern == "scatter":
        _strict_fields(context, {"kind", "intercept", "coefficient"}, "model_context")
        intercept = _finite_number(context["intercept"], "model_context.intercept")
        coefficient = _finite_number(context["coefficient"], "model_context.coefficient")
        for axis in ("x_axis", "y_axis"):
            _explicit_domain(spec[axis].get("domain"), f"{axis}.domain")
        for x in spec["x_axis"]["domain"]:
            _finite_number(intercept + coefficient * x, "model endpoint")
        for index, point in enumerate(spec["points"]):
            predicted = intercept + coefficient * point["x"]
            if not math.isclose(predicted, point["y"], rel_tol=1e-9, abs_tol=1e-9):
                raise RenderSpecError(f"points[{index}] does not agree with its model_context")
        result = spec.get("interactive_result", {})
        if result.get("quantity") == spec["y_axis"].get("quantity") and "threshold" in result:
            _finite_number(result["threshold"], "interactive_result.threshold")
    elif kind == "score_breakdown" and pattern == "summary_strip":
        _strict_fields(context, {"kind", "components", "comparison"}, "model_context")
        components = context["components"]
        if not isinstance(components, list) or not 1 <= len(components) <= 4:
            raise RenderSpecError("model_context.components requires one to four components")
        for index, component in enumerate(components):
            _strict_fields(component, {"label", "value"}, f"components[{index}]")
            if not isinstance(component["label"], str) or not component["label"].strip():
                raise RenderSpecError("component label must be nonempty text")
            if _finite_number(component["value"], f"components[{index}].value") < 0:
                raise RenderSpecError("score contribution cannot be negative")
        comparison = _strict_fields(context["comparison"], {"label", "remove_index"}, "model_context.comparison")
        if not isinstance(comparison["label"], str) or not comparison["label"].strip():
            raise RenderSpecError("comparison label must be nonempty text")
        if type(comparison["remove_index"]) is not int or not 0 <= comparison["remove_index"] < len(components):
            raise RenderSpecError("comparison.remove_index must identify a component")
        blocks = _as_sequence(spec, "blocks")
        if len(blocks) != 1 or any(key not in blocks[0] for key in ("metric", "claim", "proof", "implication")):
            raise RenderSpecError("score_breakdown requires one complete score block")
        result = spec.get("interactive_result", {})
        total = _finite_number(sum(item["value"] for item in components), "score total")
        if total <= 0 or not math.isclose(total, _finite_number(result.get("value"), "interactive_result.value"), rel_tol=1e-9, abs_tol=1e-9):
            raise RenderSpecError("score contributions must sum to interactive_result.value")
        if _finite_number(result.get("threshold"), "interactive_result.threshold") < 0:
            raise RenderSpecError("score threshold cannot be negative")
    elif kind == "scenario_compare" and pattern == "bullet_list" and _ranked_bullets(spec):
        _strict_fields(context, {"kind", "label", "values"}, "model_context")
        if not isinstance(context["label"], str) or not context["label"].strip():
            raise RenderSpecError("scenario comparison label must be nonempty text")
        values = context["values"]
        if not isinstance(values, list) or len(values) != len(spec["bullets"]):
            raise RenderSpecError("scenario values must cover every ranked item")
        identifiers, ranks = [], []
        for index, value in enumerate(values):
            _strict_fields(value, {"item_id", "value", "rank"}, f"model_context.values[{index}]")
            if not isinstance(value["item_id"], str) or not value["item_id"]:
                raise RenderSpecError("scenario item_id must be nonempty text")
            identifiers.append(value["item_id"])
            _inside_domain(value["value"], f"model_context.values[{index}].value", tuple(spec["value_domain"]))
            if type(value["rank"]) is not int or not 1 <= value["rank"] <= len(values):
                raise RenderSpecError("scenario rank must be within the displayed items")
            ranks.append(value["rank"])
        base_ids = [item.get("item_id") for item in spec["bullets"]]
        if len(set(identifiers)) != len(identifiers) or set(identifiers) != set(base_ids) or len(set(base_ids)) != len(base_ids):
            raise RenderSpecError("scenario values must match each unique base item_id exactly once")
        if len(set(ranks)) != len(ranks):
            raise RenderSpecError("scenario ranks must be distinct")
    else:
        raise RenderSpecError("model_context kind does not match a supported evidence pattern")


def _validate_interactive_exact_text(spec: dict) -> None:
    """Opt-in display hooks. Absent metadata leaves legacy output unchanged."""
    def text(value: object, path: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 500 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise RenderSpecError(f"{path} must be nonempty Unicode text (at most 500 scalars)")

    pattern = spec.get("pattern")
    if pattern in ("gap", "before_after"):
        collection = "items" if pattern == "gap" else "pairs"
        keys = ("value_text",) if pattern == "gap" else ("before_text", "after_text", "delta_text")
        for i, row in enumerate(spec.get(collection, [])):
            for key in keys:
                if key in row:
                    text(row[key], f"{collection}[{i}].{key}")
    if pattern == "scatter":
        for name in ("x_axis", "y_axis"):
            axis = spec[name]
            if "tick_labels" in axis:
                labels = axis["tick_labels"]
                if "domain" not in axis or not isinstance(labels, list) or len(labels) != 2:
                    raise RenderSpecError(f"{name}.tick_labels requires two labels and an explicit domain")
                for i, label in enumerate(labels):
                    text(label, f"{name}.tick_labels[{i}]")


def render(spec: dict) -> str:
    validate_spec(spec)
    pattern = spec.get("pattern", "")
    if pattern in CHROMELESS:
        body = RENDERERS[pattern](spec)
        aria = spec.get("title", "")
    else:
        body = header(spec) + RENDERERS[pattern](spec) + footer(spec)
        aria = spec.get("headline", "")
    content = apply_palette("\n  ".join(body), spec)
    background = "" if pattern in CHROMELESS else f'  <rect width="{W}" height="{H}" fill="#FFFFFF"/>\n'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{esc(aria)}">\n'
        f"{background}"
        f"  {content}\n"
        f"</svg>\n"
    )



EXHIBIT_PATTERNS = {"waterfall", "gap", "before_after", "time_series", "benchmark_table",
                    "process_flow", "funnel", "heatmap", "gantt", "kpi_scorecard",
                    "two_by_two", "scatter", "distribution", "small_multiples"}


def render_exhibit(spec: dict) -> str:
    """Render a chart body for reports. Caption, units and sources belong to the document."""
    validate_spec(spec)
    if spec["pattern"] not in EXHIBIT_PATTERNS:
        raise RenderSpecError("compact exhibits require a chart or diagram pattern")
    chart_spec = {k:v for k,v in spec.items() if k != "commentary"}
    content = apply_palette("\n".join(RENDERERS[spec["pattern"]](chart_spec)), spec)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="40 180 1200 432" '
            'width="1200" height="432" role="img" aria-label="Chart exhibit">'
            + content + '</svg>')

def main() -> None:
    parser = argparse.ArgumentParser(description="Render a slide spec JSON into an SVG slide.")
    parser.add_argument("--exhibit", action="store_true", help="Render chart body for a document")
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
        svg = render_exhibit(spec) if args.exhibit else render(spec)
    except (RenderSpecError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: invalid spec: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output) if args.output else spec_path.with_suffix(".svg")
    output_path.write_text(svg, encoding="utf-8")
    print(f"OK: rendered {spec.get('pattern')} slide to {output_path}")


if __name__ == "__main__":
    main()
