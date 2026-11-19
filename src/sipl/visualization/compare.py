"""Інтерактивна HTML-сторінка: вихідний код, дерево виводу та AST поруч.

Наведення або клік на вузол підсвічує відповідний фрагмент коду
і вузли іншого дерева, що покривають той самий фрагмент.
"""

from __future__ import annotations

import json
from html import escape

from .exporters import SVG_STYLE, to_svg
from .model import VisNode

_PAGE = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<title>SIPL: Parse Tree ↔ AST — __TITLE__</title>
<style>
body { margin: 0; font: 14px system-ui, sans-serif; color: #1c2430; background: #f6f7f9; }
header { padding: 12px 20px; background: #fff; border-bottom: 1px solid #d8dde3; }
h1 { font-size: 16px; margin: 0 0 4px; }
header p { margin: 0; color: #55606d; }
#source { margin: 12px 20px; padding: 12px 14px; background: #fff; border: 1px solid #d8dde3;
  border-radius: 6px; font: 13px ui-monospace, Menlo, Consolas, monospace; white-space: pre-wrap; }
#source mark { background: #ffd95a; border-radius: 2px; }
#info { margin: 0 20px 8px; min-height: 20px; font: 13px ui-monospace, Menlo, Consolas, monospace; }
.panes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 0 20px 20px; }
.pane { background: #fff; border: 1px solid #d8dde3; border-radius: 6px; min-width: 0; }
.pane h2 { font-size: 13px; margin: 0; padding: 8px 12px; border-bottom: 1px solid #d8dde3; }
.pane h2 span { font-weight: normal; color: #55606d; }
.scroll { overflow: auto; max-height: 70vh; padding: 6px; }
.node { cursor: pointer; }
__SVG_STYLE__
.sipl-tree g.node.match rect { stroke: #b36b00 !important; stroke-width: 2.5; }
.sipl-tree g.node.inside rect { stroke: #b36b00 !important; stroke-dasharray: 3 2; }
.sipl-tree g.node.active rect { fill: #ffd95a !important; }
.sipl-tree g.cat-rule.match rect, .sipl-tree g.cat-token.match rect { fill: #fff1c2 !important; }
</style>
</head>
<body>
<header>
<h1>Parse Tree ↔ AST: __TITLE__</h1>
<p>Наведіть на вузол, щоб побачити його фрагмент коду та відповідники в іншому дереві. Клік закріплює вибір.</p>
</header>
<pre id="source"></pre>
<div id="info"></div>
<div class="panes">
<div class="pane"><h2>Дерево виводу (конкретний синтаксис) <span>— вузлів: __PARSE_COUNT__</span></h2>
<div class="scroll" id="parse">__PARSE_SVG__</div></div>
<div class="pane"><h2>AST (абстрактний синтаксис) <span>— вузлів: __AST_COUNT__</span></h2>
<div class="scroll" id="ast">__AST_SVG__</div></div>
</div>
<script>
const SOURCE = Array.from(__SOURCE_JSON__);
const pre = document.getElementById('source');
const info = document.getElementById('info');
const nodes = Array.from(document.querySelectorAll('g.node'));
let pinned = null;
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
function showSource(a, b) {
  const cut = (i, j) => esc(SOURCE.slice(i, j).join(''));
  pre.innerHTML = a === null ? cut(0, SOURCE.length)
    : cut(0, a) + '<mark>' + cut(a, b) + '</mark>' + cut(b, SOURCE.length);
}
function select(g) {
  nodes.forEach(n => n.classList.remove('match', 'inside', 'active'));
  if (!g) { showSource(null); info.textContent = ''; return; }
  const a = +g.dataset.start, b = +g.dataset.end;
  const same = [], labels = {parse: [], ast: []};
  nodes.forEach(n => {
    const s = +n.dataset.start, e = +n.dataset.end;
    if (s === a && e === b) {
      n.classList.add('match');
      labels[n.closest('.scroll').id].push(n.dataset.title);
    } else if (s >= a && e <= b) { n.classList.add('inside'); }
  });
  g.classList.add('active');
  showSource(a, b);
  info.textContent = 'Parse tree: ' + (labels.parse.join(' → ') || '—')
    + '   ⇔   AST: ' + (labels.ast.join(' → ') || '— (немає окремого вузла)');
}
nodes.forEach(g => {
  g.addEventListener('mouseenter', () => { if (!pinned) select(g); });
  g.addEventListener('mouseleave', () => { if (!pinned) select(null); });
  g.addEventListener('click', ev => {
    ev.stopPropagation();
    pinned = pinned === g ? null : g;
    select(g);
  });
});
document.body.addEventListener('click', () => { pinned = null; select(null); });
showSource(null);
</script>
</body>
</html>
"""


def to_compare_html(parse_root: VisNode, ast_root: VisNode, source: str, title: str = "") -> str:
    """Самодостатня HTML-сторінка порівняння дерева виводу та AST."""
    source_json = json.dumps(source, ensure_ascii=False).replace("</", "<\\/")
    replacements = {
        "__TITLE__": escape(title or "програма"),
        "__SVG_STYLE__": SVG_STYLE,
        "__PARSE_COUNT__": str(len(parse_root.walk())),
        "__AST_COUNT__": str(len(ast_root.walk())),
        "__PARSE_SVG__": to_svg(parse_root, source, standalone=False),
        "__AST_SVG__": to_svg(ast_root, source, standalone=False),
        "__SOURCE_JSON__": source_json,
    }
    page = _PAGE
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page
