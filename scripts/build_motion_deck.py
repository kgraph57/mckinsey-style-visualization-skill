#!/usr/bin/env python3
"""Build a self-contained, story-led motion deck from plain JSON.

Six original presentation components share one navigation/evidence runtime.
No downloaded template or proprietary engine is included.
"""
import argparse
import html
import json
import math
from pathlib import Path
import re
import tempfile
try:
    from .motion_locale import english_ui, english_runtime
except ImportError:
    from motion_locale import english_ui, english_runtime

ROOT = Path(__file__).resolve().parent
KINDS = {"overview", "evidence", "ranking", "model", "gap", "sequence"}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A chart quantity must be a finite number")
    return value


def validate(data):
    if data.get("design") == "decision" and data.get("lang") != "en":
        raise ValueError("The decision presentation currently supports English copy")
    pages = data["pages"]
    if not 1 <= len(pages) <= 12:
        raise ValueError("A motion deck supports 1–12 pages")
    ids = [p["id"] for p in pages]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", p) for p in ids):
        raise ValueError("Page IDs must be unique short tokens")
    for p in pages:
        if p["kind"] not in KINDS or not p["title"] or not p["source"]:
            raise ValueError("Each page needs a supported kind, title and source")
        if not p.get("evidence", {}).get("rows"):
            raise ValueError("Each page needs evidence rows")
        if p["kind"] == "overview":
            if any(f["page"] not in ids for f in p["flow"]):
                raise ValueError("An overview destination does not exist")
        if p["kind"] in ("evidence", "ranking"):
            lo, hi = map(number, p["domain"])
            if lo != 0 or hi <= lo or not 1 <= len(p["items"]) <= 5:
                raise ValueError("Bar charts need a zero baseline and 1–5 items")
            keys = [r["id"] for r in p["items"]]
            if len(keys) != len(set(keys)):
                raise ValueError("Chart identities must be unique")
            fields = ["value"] if p["kind"] == "evidence" else [s["id"] for s in p["scenarios"]]
            for item in p["items"]:
                if any(not lo <= number(item[k]) <= hi for k in fields):
                    raise ValueError("A bar is outside its declared domain")
            if p["kind"] == "ranking" and p["initial"] not in fields:
                raise ValueError("Initial ranking scenario does not exist")
        if p["kind"] == "model":
            control, model = p["input"], p["model"]
            if not number(control["min"]) < number(control["max"]) or not control["min"] <= number(control["initial"]) <= control["max"] or number(control["step"]) <= 0:
                raise ValueError("Invalid slider domain")
            values = [number(model["intercept"]) + number(model["coefficient"]) * control[k] for k in ("min", "max")]
            if not model["domain"][0] <= min(values) <= max(values) <= model["domain"][1]:
                raise ValueError("The model escapes the fixed chart domain")
        if p["kind"] == "gap":
            if not 0 < number(p["threshold"]) <= p["domain"][1]:
                raise ValueError("Invalid readiness threshold")
            if sum(number(r["value"]) for r in p["components"]) > p["domain"][1]:
                raise ValueError("Readiness contributions escape the domain")
        if p["kind"] == "sequence":
            weeks = [number(s["week"]) for s in p["steps"]]
            if weeks != sorted(set(weeks)):
                raise ValueError("Timeline steps must advance in time")
            if any(not weeks[0] <= number(t["start"]) <= number(t["end"]) <= weeks[-1] for t in p["tasks"]):
                raise ValueError("A task escapes the timeline")
            for condition in p.get("conditions", []):
                parent = next((q for q in pages if q["id"] == condition["page"]), None)
                if parent is None or parent["kind"] not in {"model", "gap", "ranking"}:
                    raise ValueError("A timeline condition must reference a model, score or ranking page")
                if "scenario" in condition:
                    if parent["kind"] != "ranking" or condition["scenario"] not in [s["id"] for s in parent["scenarios"]]:
                        raise ValueError("A timeline scenario condition does not exist")
                elif parent["kind"] not in {"model", "gap"}:
                    raise ValueError("A numerical condition needs a numerical output")
                else:
                    number(condition["threshold"])
            if any(s.get("conditional") and not (s.get("holdLabel") and s.get("holdDetail")) for s in p["steps"]):
                raise ValueError("A conditional step needs an explicit hold label and explanation")
    return data


def button(label, attrs="", cls="text-button"):
    return f'<button type="button" class="{cls}" {attrs}>{esc(label)}</button>'


def panel(p):
    v = p["panel"]
    rows = "".join(f'<div><span>{esc(a)}</span><strong>{esc(b)}</strong></div>' for a, b in v["comparison"])
    evidence_button = button("内訳と出所を見る ›", f'data-evidence data-demo="{p["id"]}-evidence"', "evidence-button")
    return (f'<aside class="insight reveal" style="--delay:800ms"><button type="button" class="hero-number" data-evidence aria-label="大きな数字を押して内訳と出所を表示"><span data-hero>{esc(v["value"])}</span>'
            f'<span class="hero-unit">{esc(v["unit"])}</span></button><h2 data-panel-label>{esc(v["label"])}</h2>'
            f'<p class="panel-copy">{esc(v["text"])}</p><div class="comparison" data-comparison>{rows}</div>'
            f'{evidence_button}</aside>')


def bars(p):
    ranking = p["kind"] == "ranking"
    values = {r["id"]: r[p["initial"]] if ranking else r["value"] for r in p["items"]}
    order = sorted(p["items"], key=lambda r: -values[r["id"]])
    rows = []
    for item in p["items"]:
        index = order.index(item)
        value = values[item["id"]]
        baseline = item["base"] if ranking else value
        rows.append(f'<button type="button" class="bar-row {"focus" if item.get("focus") else ""}" '
                    f'data-item="{esc(item["id"])}" data-demo="{p["id"]}-{esc(item["id"])}" style="transform:translateY({index*165}px)" '
                    f'aria-label="{esc(item["label"])} {value}。押すと根拠を表示">'
                    f'<span class="bar-name"><small data-rank>{index+1 if ranking else ""}</small>{esc(item["label"])}</span>'
                    f'<span class="bar-track"><span class="bar-ghost" style="transform:scaleX({baseline/p["domain"][1]})"></span>'
                    f'<span class="bar-fill" style="transform:scaleX({value/p["domain"][1]})"></span></span>'
                    f'<strong class="bar-number" data-bar-value>{value}</strong><span class="bar-delta" data-bar-delta></span></button>')
    controls = ""
    if ranking:
        controls = '<div class="segmented" role="group" aria-label="地域を比較する条件">' + "".join(
            button(s["label"], f'data-scenario="{esc(s["id"])}" data-demo="{p["id"]}-{esc(s["id"])}" aria-pressed="{str(s["id"] == p["initial"]).lower()}"', "segment") for s in p["scenarios"]) + '</div>'
    return controls + f'<div class="bar-chart {"ranking-chart" if ranking else ""}" aria-label="{esc(p["scope"])}">' + "".join(rows) + f'<div class="bar-axis"><span>0</span><span>{p["domain"][1]}{"点" if ranking else "%"}</span></div></div>' + ('<p class="chart-note">破線：同じ地域の通常時の点数</p>' if ranking else '<p class="chart-note">棒を押すと、その項目の内訳と前提を表示します ›</p>')


def model(p):
    v, m = p["input"], p["model"]
    points = []
    for x in (v["min"], v["max"]):
        y = m["intercept"] + m["coefficient"] * x
        points.append(f'{100+(x-v["min"])/(v["max"]-v["min"])*850},{490-(y-m["domain"][0])/(m["domain"][1]-m["domain"][0])*420}')
    threshold_y = 490-(m["threshold"]-m["domain"][0])/(m["domain"][1]-m["domain"][0])*420
    svg = f'<svg class="model-chart" viewBox="0 0 1060 560" role="img" aria-label="採用率と年間便益の固定尺度グラフ"><path class="axis" d="M100 60V490H980"/><text x="100" y="38">万ドル／年</text>'
    for val in range(int(m["domain"][0]), int(m["domain"][1])+1, 100):
        y = 490-(val-m["domain"][0])/(m["domain"][1]-m["domain"][0])*420
        svg += f'<path class="grid" d="M100 {y}H980"/><text x="76" y="{y+10}" text-anchor="end">{val}</text>'
    for x in (v["min"], 55, v["max"]):
        px = 100+(x-v["min"])/(v["max"]-v["min"])*850
        svg += f'<text x="{px}" y="540" text-anchor="middle">{x}%</text>'
    svg += (f'<path class="threshold" d="M100 {threshold_y}H980"/><text class="threshold-label" x="970" y="{threshold_y-18}" text-anchor="end">基準 {m["threshold"]}</text>'
            f'<polyline class="model-line" points="{" ".join(points)}"/><circle data-model-point r="15" cx="525" cy="{threshold_y}"/>'
            '<path data-point-guide class="point-guide"/><text data-point-label class="point-label"></text></svg>')
    return svg + f'<div class="slider-box"><label for="input-{p["id"]}">{esc(v["label"])}<strong data-input-value>{v["initial"]}%</strong></label><input id="input-{p["id"]}" data-slider data-demo="{p["id"]}-slider" type="range" min="{v["min"]}" max="{v["max"]}" step="{v["step"]}" value="{v["initial"]}"/><div class="slider-ends"><span>{v["min"]}%</span><span>{v["max"]}%</span></div></div><p class="formula" data-formula></p>'


def gap(p):
    parts = []
    for index, c in enumerate(p["components"]):
        if c.get("toggle"):
            parts.append(f'<label class="contribution toggle"><input data-toggle="{c["id"]}" data-demo="{p["id"]}-{c["id"]}" type="checkbox" {"checked" if c.get("initial") else ""}/><span>{esc(c["label"])}</span><strong data-part-value="{c["id"]}">{c["value"]}<small>点</small></strong></label>')
        else:
            parts.append(f'<div class="contribution"><span>{esc(c["label"])}</span><strong>{c["value"]}<small>点</small></strong></div>')
    segments = "".join(f'<span class="score-part tone-{i}" data-score-part="{c["id"]}"></span>' for i, c in enumerate(p["components"]))
    return (f'<div class="score-chart"><div class="score-threshold" style="left:{p["threshold"]}%"><span>実行基準 {p["threshold"]}</span></div>'
            f'<div class="score-track"><div class="score-reference"></div>{segments}<span class="score-missing" data-missing></span></div>'
            f'<div class="score-axis"><span>0</span><span>{p["domain"][1]}点</span></div><p class="gap-message" data-gap-message></p></div>'
            '<div class="contributions">' + "".join(parts) + '</div><p class="formula" data-formula></p>')


def sequence(p):
    svg = '<svg class="timeline" viewBox="0 0 1080 580" role="img" aria-label="12週間の実証工程">'
    for week in (1, 2, 4, 6, 8, 10, 12):
        x = 260+(week-1)/11*750
        svg += f'<text x="{x}" y="65" text-anchor="middle">W{week}</text><path class="grid" d="M{x} 90V500"/>'
    for index, task in enumerate(p["tasks"]):
        x = 260+(task["start"]-1)/11*750
        width = max(20, (task["end"]-task["start"])/11*750)
        y = 125+index*100
        svg += (f'<text x="0" y="{y+34}">{esc(task["label"])}</text>'
                f'<rect class="planned" x="{x}" y="{y}" width="{width}" height="48"/>'
                f'<rect class="task-fill {"main-task" if task.get("focus") else ""}" data-task="{index}" x="{x}" y="{y}" width="{width}" height="48"/>')
    mobile = '<ol class="mobile-timeline">' + ''.join(f'<li data-mobile-step="{i}"><span class="mobile-week">W{s["week"]}</span><strong data-mobile-step-label>{esc(s["label"])}</strong><p data-mobile-step-detail>{esc(s["detail"])}</p></li>' for i,s in enumerate(p['steps'])) + '</ol>'
    return svg + '<g data-now-line><path class="now-line" d="M0 90V510"/><circle r="8" cy="90"/><text x="12" y="554" data-now-label>いま W1</text></g></svg>' + mobile + '<div class="sequence-controls">' + button('はじめに戻す', 'data-step-reset', 'reset-step') + button('次の工程へ ›', f'data-next-step data-demo="{p["id"]}-next"', 'primary-button') + '</div><p class="gate-status" data-gate-status></p>'


def render_page(p, index, data):
    head = (f'<section class="motion-page" id="p-{p["id"]}" data-page="{p["id"]}" data-kind="{p["kind"]}" aria-labelledby="h-{p["id"]}">'
            f'<header><div class="section-label reveal">{esc(p["section"])}</div><h1 class="reveal" style="--delay:80ms" id="h-{p["id"]}">{esc(p["title"])}</h1>'
            f'<div class="scope reveal" style="--delay:180ms">{esc(p["scope"])}</div></header>')
    if p["kind"] == "overview":
        kpis = "".join(f'<div class="kpi reveal" style="--delay:{250+i*80}ms"><strong>{esc(k["value"])}</strong><span class="kpi-unit">{esc(k["unit"])}</span><p>{esc(k["label"])}</p></div>' for i, k in enumerate(p["kpis"]))
        cards = "".join(f'<button class="flow-stop reveal" style="--delay:{550+i*70}ms" type="button" data-go="{f["page"]}" data-demo="overview-{f["page"]}"><span class="flow-label">{esc(f["label"])}</span><strong>{esc(f["value"])}</strong><span class="flow-detail">{esc(f["detail"])}</span><span class="flow-link">詳しく見る p.{next(j+1 for j,q in enumerate(data["pages"]) if q["id"]==f["page"])} ›</span></button>' for i, f in enumerate(p["flow"]))
        body = f'<div class="overview-body"><div class="kpi-band">{kpis}</div><div class="overview-path"><p>改善の起点から、実行の判断まで</p><div class="flow-stops">{cards}</div></div><p class="overview-takeaway">{esc(p["takeaway"])}</p>{button("計画全体の前提を見る ›", "data-evidence", "overview-evidence")}</div>'
    else:
        exhibit = {"evidence":bars,"ranking":bars,"model":model,"gap":gap,"sequence":sequence}[p["kind"]](p)
        body = f'<div class="page-body"><div class="exhibit reveal" style="--delay:300ms">{exhibit}</div>{panel(p)}</div><p class="takeaway reveal" style="--delay:950ms" data-takeaway>{esc(p["takeaway"])}</p>'
    if data.get("design") == "decision":
        if p["kind"] != "overview":
            body = body.replace('<button type="button" class="hero-number"', '<p class="decision-label" data-decision-status>DECISION CONTEXT</p><button type="button" class="hero-number"', 1)
        if p["kind"] == "model":
            body = body.replace('<circle data-model-point', '<circle data-baseline-point class="baseline-point" r="13"/><text data-baseline-label class="baseline-label"></text><circle data-model-point', 1)
            body = body.replace(f'<span>{p["input"]["max"]}%</span></div>', f'<button class="baseline-reset" type="button" data-model-reset>Reset to {p["input"]["initial"]}%</button><span>{p["input"]["max"]}%</span></div>', 1)
    return head + body + f'<footer><span>{esc(p["source"])}</span><span>{esc(data["disclosure"])}</span><span>{index+1} / {len(data["pages"])}</span></footer></section>'


def build(manifest, static=False):
    data = validate(json.loads(Path(manifest).read_text(encoding="utf-8")))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    css = (ROOT / "runtime/motion.css").read_text(encoding="utf-8")
    js = (ROOT / "runtime/motion.js").read_text(encoding="utf-8")
    if data.get("design") == "decision":
        css += "\n" + (ROOT / "runtime/motion-decision.css").read_text(encoding="utf-8")
        extension = (ROOT / "runtime/motion-decision.js").read_text(encoding="utf-8")
        js = js.replace('  function update(p) {', extension + '\n  function update(p) {', 1)
    english = data.get("lang") == "en"
    if english:
        js = english_runtime(js)
    pages = "\n".join(render_page(p, i, data) for i, p in enumerate(data["pages"]))
    if english:
        pages = english_ui(pages)
        # Monetary chart geometry stays in exact $10k units; labels use $m.
        for val in (0, 100, 200, 300, 400):
            pages = re.sub(r'(text-anchor="end">)' + str(val) + r'(</text>)', lambda m: m[1] + str(val // 100) + m[2], pages)
        pages = pages.replace('Gate 180</text>', 'Gate 1.8</text>')
    result = (f'<!doctype html><html lang="{esc(data.get("lang", "ja"))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{esc(data["title"])}</title><style>{css}</style></head><body {"data-static" if static else ""}>'
            f'<a class="skip" href="#stage">資料へ進む</a><main id="stage">{pages}</main>'
            '<nav class="deck-nav" aria-label="資料の操作"><button data-prev aria-label="前のページ">←</button><span data-page-count></span><button data-next aria-label="次のページ">→</button><span class="nav-rule"></span><button data-overview>一覧 <kbd>O</kbd></button><button data-demo-start>自動デモ <kbd>D</kbd></button><button data-static-toggle>静止表示</button><button data-fullscreen aria-label="全画面">全画面</button><button data-help aria-label="操作方法">?</button></nav>'
            '<dialog id="evidence-dialog" class="evidence-drawer" aria-labelledby="evidence-head"><button class="close-dialog" data-close aria-label="閉じる">×</button><div class="drawer-crumb"></div><h2 id="evidence-head"></h2><div class="drawer-tabs" role="tablist" aria-label="根拠の種類"><button role="tab" id="evidence-detail" aria-controls="drawer-content" aria-selected="true" data-tab="detail" data-demo="evidence-detail">内訳</button><button role="tab" id="evidence-source" aria-controls="drawer-content" aria-selected="false" tabindex="-1" data-tab="source" data-demo="evidence-source">出所と前提</button></div><div id="drawer-content" role="tabpanel" aria-labelledby="evidence-detail"></div><p class="drawer-source"></p></dialog>'
            '<dialog id="overview-dialog" class="overview-dialog" aria-labelledby="overview-head"><div class="overview-header"><h2 id="overview-head">全体像 → 根拠 → 実行の判断</h2><button data-close aria-label="一覧を閉じる">×</button></div><div class="overview-grid"></div></dialog>'
            '<div id="motion-tip" class="motion-tip" role="tooltip" hidden></div><div id="demo-cursor" aria-hidden="true"><svg viewBox="0 0 30 38"><path d="M3 2L4 30L11 23L17 35L23 32L17 20L28 19Z"/></svg><span></span></div><div id="demo-status" role="status" hidden></div><p id="live-status" class="sr-only" aria-live="polite"></p>'
            '<noscript><style>#stage,.deck-nav{display:none!important}</style><p>この資料は、JavaScriptを有効にしたブラウザで開いてください。</p></noscript>'
            f'<script type="application/json" id="motion-data">{payload}</script><script>{js}</script></body></html>')
    if english:
        # Only the shell is localized here. Input data is already authored in English.
        result = english_ui(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--static", action="store_true", help="Open all pages in their declared conclusion states")
    args = parser.parse_args()
    try:
        text = build(args.manifest, args.static)
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp") as stream:
            stream.write(text)
            pending = Path(stream.name)
        pending.replace(target)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Invalid motion deck: {exc}\n")
    print(f"OK: built {target} ({len(text.encode('utf-8')):,} bytes)")


if __name__ == "__main__":
    main()
