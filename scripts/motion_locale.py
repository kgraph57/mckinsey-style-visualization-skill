"""Strict, build-time English catalog for the shared motion renderer.

Translate the presentation shell and runtime templates, never the input data.
Unknown Japanese UI copy fails the English build rather than leaking to readers.
The exact integer monetary model remains unchanged; only display units change.
"""
import re


CATALOG = {
    '${fmt(item.base)} → ${fmt(item[selected])}点（${delta >= 0 ? \'＋\' : \'−\'}${fmt(Math.abs(delta))}）': '${fmt(item.base)} → ${fmt(item[selected])} pts (${delta >= 0 ? \'+\' : \'−\'}${fmt(Math.abs(delta))})',
    '${item.label} ${index+1}位 ${item[selected]}点。押すと根拠を表示': '${item.label}, rank ${index+1}, ${item[selected]} points. Select to view evidence',
    '${selected === \'base\' ? \'通常時\' : \'人員制約下\'}での${focus.label}の順位': '${focus.label} rank: ${selected === \'base\' ? \'base case\' : \'staffing constrained\'}',
    '通常時の第2候補は${order[1].label}。人員制約を加え、地域の順位を確かめる。': '${order[1].label} is second. Apply staffing constraints to test the ranking.',
    '${order[0].label}は1位のまま、第2候補が${baseOrder[1].label}から${order[1].label}へ変わる。': '${order[0].label} stays first; ${order[1].label} replaces ${baseOrder[1].label} in second.',
    '通常時の第2候補は${order[1].label}。人員制約の影響を確認してから、地域の組合せを決める。': '${order[1].label} is second in the base case. Test staffing constraints before selecting the pair.',
    '${focus.label}は${before}位から${rank}位へ。北部を先行し、東部の追加は6週目の条件判定で決める。': '${focus.label} moves from rank ${before} to ${rank}. Start North; review adding East at Week 6.',
    '${focus.base} → ${focus[selected]}点': '${focus.base} → ${focus[selected]} pts',
    '${focus[selected]} − ${focus.base} = ${focus[selected]-focus.base >= 0 ? \'＋\' : \'−\'}${Math.abs(focus[selected]-focus.base)}点': '${focus[selected]} − ${focus.base} = ${focus[selected]-focus.base >= 0 ? \'+\' : \'−\'}${Math.abs(focus[selected]-focus.base)} pts',
    '${fmt(annual)}万ドル': '$${money(annual)}m',
    '採用率${adoption}%での年間便益': 'Annual value at ${adoption}% adoption',
    '${m.threshold}万ドル／年': '$${money(m.threshold)}m/year',
    '${fmt(annual)} − ${m.threshold} = ${difference > 0 ? \'＋\' : \'\'}${fmt(difference)}万ドル': '${money(annual)} − ${money(m.threshold)} = ${difference > 0 ? \'+\' : \'\'}${money(difference)} ($m/year)',
    '試算：${m.intercept} ＋ ${m.coefficient} × ${adoption} = ${fmt(annual)}（万ドル／年）': 'Model: ${money(m.intercept)} + ${m.coefficient/100} × ${adoption} = ${money(annual)} ($m/year)',
    '基準を満たす：年間便益${fmt(annual)}万ドル。東部の追加には、準備度と人員制約の確認も必要。': 'Value gate passed: $${money(annual)}m/year. Readiness and staffing must also pass before adding East.',
    '基準まで${fmt(-difference)}万ドル不足。採用率を上げるか、実証の条件を見直す。': '$${money(-difference)}m/year below the gate. Increase adoption or revisit the pilot conditions.',
    '基準を${total-p.threshold}点上回る': '${total-p.threshold} points above the gate',
    '基準まで${p.threshold-total}点不足': '${p.threshold-total} points below the gate',
    '${p.threshold}点以上': 'At least ${p.threshold} pts',
    '${total} − ${p.threshold} = ${total-p.threshold > 0 ? \'＋\' : \'\'}${total-p.threshold}点': '${total} − ${p.threshold} = ${total-p.threshold > 0 ? \'+\' : \'\'}${total-p.threshold} pts',
    '試算：${values.join(\' ＋ \')} = ${total}点': 'Model: ${values.join(\' + \')} = ${total} pts',
    '準備度は${total}点。管理者の対応枠を確保してから、東部の追加を判断する。': 'Readiness: ${total} points. Secure manager capacity before deciding whether to add East.',
    '${p.threshold-total}点が不足。管理者枠や連携の条件を見直し、実行できる水準まで整える。': '${p.threshold-total} points short. Revisit manager capacity and integration before proceeding.',
    'いま W${step.week}': 'Now W${step.week}',
    '現在の条件では東部を追加できません。北部の実証を続け、全体展開は別に判断します。': 'Do not add East under current conditions. Continue North; decide on network-wide scale separately.',
    '${current+1}ページ。${pageTitle(current)}': 'Page ${current+1}. ${pageTitle(current)}',
    '${index+1}ページ ${pageTitle(index)}': 'Page ${index+1}: ${pageTitle(index)}',
    '${p.source}。${data.disclosure}。': '${p.source}. ${data.disclosure}.',
    '選択した項目：${escape(evidenceItem.label)}': 'Selected: ${escape(evidenceItem.label)}',
    '現在：採用率${state[p.id].input}% → ${fmt(value(p))}万ドル／年': 'Current: ${state[p.id].input}% adoption → $${money(value(p))}m/year',
    '現在の準備度：${score(p)}点／基準${p.threshold}点': 'Current readiness: ${score(p)} pts / gate: ${p.threshold} pts',
    '${c.label}のページへ ›': 'Explore ${c.label} ›',
    '採用率${state[p.id].input}%。年間便益${fmt(value(p))}万ドル。': 'Adoption ${state[p.id].input}%. Annual value $${money(value(p))}m.',
    '準備度${score(p)}点。': 'Readiness: ${score(p)} points.',
    '内訳と出所を見る ›': 'Explore the evidence ›',
    '大きな数字を押して内訳と出所を表示': 'Select the headline number to view the breakdown and source',
    '押すと根拠を表示': 'Select to view evidence',
    '地域を比較する条件': 'Regional comparison scenario',
    '破線：同じ地域の通常時の点数': 'Dashed outline: the same region in the base case',
    '棒を押すと、その項目の内訳と前提を表示します ›': 'Select a bar to explore its evidence and assumptions ›',
    '採用率と年間便益の固定尺度グラフ': 'Adoption and annual value on a fixed scale',
    '万ドル／年': '$m/year',
    '実行基準': 'Execution gate:',
    '12週間の実証工程': '12-week pilot timeline',
    'いま W1': 'Now W1',
    'はじめに戻す': 'Reset',
    '次の工程へ ›': 'Next milestone ›',
    '詳しく見る p.': 'Explore p.',
    '改善の起点から、実行の判断まで': 'From improvement opportunity to execution decision',
    '計画全体の前提を見る ›': 'Explore the pilot assumptions ›',
    '資料へ進む': 'Skip to presentation',
    '資料の操作': 'Presentation controls',
    '前のページ': 'Previous page',
    '次のページ': 'Next page',
    '全体像 → 根拠 → 実行の判断': 'Overview → Evidence → Decision',
    '一覧を閉じる': 'Close overview',
    '根拠の種類': 'Evidence type',
    '出所と前提': 'Sources & assumptions',
    'この資料は、JavaScriptを有効にしたブラウザで開いてください。': 'Open this presentation in a browser with JavaScript enabled.',
    '東部の優先度': 'East priority',
    '通常時との差': 'Change from base',
    '投資判断の基準': 'Investment gate',
    '基準との差': 'Gap to gate',
    '実行準備度は基準を上回る': 'Readiness clears the gate',
    '実行準備度は基準に届かない': 'Readiness falls below the gate',
    '実行判断の基準': 'Execution gate',
    '条件を満たす': 'Pass',
    '条件に届かない': 'Below gate',
    '12週目まで確認済み': 'Week 12 reached',
    '判断の根拠': 'Decision evidence',
    'この表示環境では全画面を利用できません。': 'Fullscreen is unavailable in this environment.',
    'この資料の操作': 'Presentation controls',
    '図や数字を押して、判断の根拠を確かめる': 'Select charts and numbers to explore the evidence',
    'ページを送る': 'Move between pages',
    '指定のページへ移動': 'Jump to a page',
    '全ページの一覧': 'Show all pages',
    '自動デモを開始／停止': 'Start or stop the guided demo',
    '根拠や一覧を閉じる': 'Close evidence or overview',
    '動きを止め、判断が見える状態にする': 'Stop motion and display the conclusion states',
    '入力の操作中はページ送りのキーを取りません。': 'Navigation keys do not change pages while editing inputs.',
    '根拠パネルは×、Esc、背景のクリックで閉じます。': 'Close the evidence drawer with ×, Escape, or a click outside it.',
    '自動デモ中 · D またはクリックで停止': 'Guided demo · Press D or click to stop',
    '自動デモが完了しました。全ページの一覧です。': 'Guided demo complete. All pages are shown in the overview.',
    'デモを停止しました。': 'Demo stopped.',
    'デモを停止': 'Stop demo',
    '操作方法': 'Help',
    '自動デモ': 'Guided demo',
    '静止表示': 'Static view',
    '全画面': 'Fullscreen',
    '一覧': 'Overview',
    '内訳': 'Breakdown',
    '閉じる': 'Close',
    '操作': 'Key / control',
    '動作': 'Action',
    '基準': 'Gate',
    '未達': 'Not met',
    '可': 'Pass',
    '点': ' pts',
    '位': 'rank',
    'ページ': 'Page',
    '＋': '+',
    '：': ': ',
    '。': '. ',
    '　／　': ' / ',
    '1〜6': '1–6',
    '・': ' / ',
}


def english_ui(text):
    # Long templates precede their constituent words; translation order is stable.
    for source in sorted(CATALOG, key=len, reverse=True):
        text = text.replace(source, CATALOG[source])
    remaining = re.findall(r'[\u3040-\u30ff\u3400-\u9fff]+', text)
    if remaining:
        raise ValueError(f"Untranslated English UI: {sorted(set(remaining))}")
    return text


def english_runtime(js):
    js = english_ui(js)
    js = js.replace("const fmt =", "const money = n => (n / 100).toFixed(1);\n  const fmt =", 1)
    return js.replace("setText(p, '[data-hero]', fmt(annual));", "setText(p, '[data-hero]', money(annual));")
