"""VIS-01 та VIS-02: дерево виводу, AST і їх порівняння."""

import json
import re
import xml.etree.ElementTree as ET

import pytest
from conftest import VALID

from sipl import build_ast, parse_tree
from sipl.visualization import (
    from_ast,
    from_parse_tree,
    to_compare_html,
    to_dot,
    to_json_dict,
    to_svg,
    to_text,
)


@pytest.fixture
def trees(power_source):
    tree = parse_tree(power_source)
    return from_parse_tree(tree), from_ast(build_ast(tree))


def test_parse_tree_is_larger_than_ast(trees):
    parse_root, ast_root = trees
    assert len(parse_root.walk()) > 2 * len(ast_root.walk())
    assert {n.category for n in parse_root.walk()} == {"rule", "token"}
    assert {n.category for n in ast_root.walk()} == {"stmt", "expr", "cond"}


def test_ids_are_unique(trees):
    for root in trees:
        ids = [n.id for n in root.walk()]
        assert len(ids) == len(set(ids))


def test_text_tree(trees, power_source):
    parse_root, ast_root = trees
    text = to_text(parse_root)
    assert text.splitlines()[0] == "program  [1:1-8:4]"
    assert '├── BEGIN "begin"  [1:1-1:6]' in text
    assert len(text.splitlines()) == len(parse_root.walk())
    assert to_text(ast_root, spans=False).splitlines()[:3] == [
        "Program",
        "└── Seq",
        "    ├── Assign",
    ]


def test_json_nodes_are_linked_to_source(trees, power_source):
    parse_root, _ = trees
    data = to_json_dict(parse_root, power_source)
    json.dumps(data)  # серіалізується

    def walk(node):
        start, end = node["span"]["start"]["offset"], node["span"]["end"]["offset"]
        assert node["source"] == power_source[start:end]
        for child in node["children"]:
            assert start <= child["span"]["start"]["offset"]
            assert child["span"]["end"]["offset"] <= end
            walk(child)

    walk(data)
    assert data["source"] == power_source.strip()


def test_dot_has_all_nodes_and_edges(trees, power_source):
    for root in trees:
        dot = to_dot(root, power_source)
        nodes = root.walk()
        assert dot.count(" -> ") == len(nodes) - 1
        assert len(re.findall(r"^  \w+ \[label=", dot, flags=re.M)) == len(nodes)
        assert "tooltip=" in dot


def test_dot_escapes_quotes():
    from sipl.visualization.exporters import _dot_escape

    assert _dot_escape('a"b\\c\nd') == 'a\\"b\\\\c\\nd'


def test_svg_is_wellformed_and_carries_spans(trees, power_source):
    for root in trees:
        svg = to_svg(root, power_source)
        doc = ET.fromstring(svg)
        ns = "{http://www.w3.org/2000/svg}"
        groups = doc.findall(f"{ns}g")
        assert len(groups) == len(root.walk())
        assert len(doc.findall(f"{ns}line")) == len(root.walk()) - 1
        for group, node in zip(groups, root.walk()):
            assert int(group.get("data-start")) == node.span.start_offset
            assert int(group.get("data-end")) == node.span.end_offset
            assert group.find(f"{ns}title") is not None


def test_svg_nodes_do_not_overlap(trees, power_source):
    svg = to_svg(trees[0], power_source)
    rows: dict[float, list[tuple[float, float]]] = {}
    for x, y, w in re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)"', svg):
        rows.setdefault(float(y), []).append((float(x), float(x) + float(w)))
    for boxes in rows.values():
        boxes.sort()
        for (_, right), (left, _) in zip(boxes, boxes[1:]):
            assert left >= right


def test_compare_page(trees, power_source):
    parse_root, ast_root = trees
    page = to_compare_html(parse_root, ast_root, power_source, "power.sipl")
    assert page.count("<svg") == 2
    assert "power.sipl" in page
    assert f"вузлів: {len(parse_root.walk())}" in page
    assert f"вузлів: {len(ast_root.walk())}" in page
    assert "__" not in re.sub(r"<script>.*</script>", "", page, flags=re.S)


def test_compare_page_escapes_source():
    source = "begin X := 1 end // </script><b>"
    tree = parse_tree(source)
    page = to_compare_html(from_parse_tree(tree), from_ast(build_ast(tree)), source)
    assert "</script><b>" not in page


def test_every_ast_node_has_a_parse_tree_counterpart(trees):
    # основа порівняння Parse Tree ↔ AST: той самий фрагмент коду
    parse_root, ast_root = trees
    parse_spans = {(n.span.start_offset, n.span.end_offset) for n in parse_root.walk()}
    for node in ast_root.walk():
        assert (node.span.start_offset, node.span.end_offset) in parse_spans


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_all_examples_render(path):
    source = path.read_text(encoding="utf-8")
    tree = parse_tree(source)
    for root in (from_parse_tree(tree), from_ast(build_ast(tree))):
        assert to_text(root)
        ET.fromstring(to_svg(root, source))
        assert to_dot(root, source).rstrip().endswith("}")
