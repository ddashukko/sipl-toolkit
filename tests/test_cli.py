"""CORE-05: команди CLI, коди завершення та JSON-контракт (інтеграційні тести)."""

import json
import subprocess
import sys

import pytest
from conftest import ROOT

from sipl.cli import main

POWER = str(ROOT / "examples" / "valid" / "power.sipl")
BROKEN = str(ROOT / "examples" / "invalid" / "trailing_semicolon.sipl")
ENVELOPE = {"schema_version", "command", "ok", "diagnostics"}


def cli(capsys, *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def cli_json(capsys, *argv: str) -> tuple[int, dict]:
    code, out, _ = cli(capsys, *argv)
    return code, json.loads(out)


# ---------- текстовий режим ----------


def test_check_ok(capsys):
    code, out, err = cli(capsys, "check", POWER)
    assert code == 0 and "коректна" in out and err == ""


def test_check_error_goes_to_stderr_with_location(capsys):
    code, out, err = cli(capsys, "check", BROKEN)
    assert code == 1 and out == ""
    assert "trailing_semicolon.sipl:3:1: error[E002]" in err
    assert "підказка" in err


def test_parse_prints_ast_tree(capsys):
    code, out, _ = cli(capsys, "parse", POWER)
    assert code == 0
    assert out.splitlines()[0].startswith("Program")
    assert "While" in out and "BinOp *" in out


def test_run_prints_final_state(capsys):
    code, out, _ = cli(capsys, "run", POWER, "-s", "X=2", "-s", "Y=10")
    assert code == 0
    assert "R = 1024" in out and "Кроків: 32" in out


def test_state_can_be_comma_separated(capsys):
    code, out, _ = cli(capsys, "run", POWER, "--set", "X=2,Y=3")
    assert code == 0 and "R = 8" in out


def test_trace_text(capsys):
    code, out, _ = cli(capsys, "trace", POWER, "-s", "X=2,Y=1")
    assert code == 0
    assert "R: ⊥ → 1" in out
    assert "умова Y > 0 → true" in out and "умова Y > 0 → false" in out


def test_runtime_error_exit_code(capsys):
    code, out, err = cli(capsys, "run", POWER)
    assert code == 3
    assert "error[E101]" in err and "Стан на момент зупинки" in out


def test_step_limit_exit_code(capsys):
    code, _, err = cli(capsys, "run", POWER, "-s", "X=1,Y=1000", "--max-steps", "20")
    assert code == 4 and "error[E102]" in err


def test_missing_file_exit_code(capsys):
    code, _, err = cli(capsys, "check", "no_such_file.sipl")
    assert code == 2 and "не вдалося прочитати" in err


@pytest.mark.parametrize("bad", ["X", "X=abc", "1X=2", "=3"])
def test_bad_state_argument_is_usage_error(capsys, bad):
    with pytest.raises(SystemExit) as info:
        main(["run", POWER, "-s", bad])
    assert info.value.code == 2
    assert "ЗМІННА=ЦІЛЕ" in capsys.readouterr().err


def test_unknown_command_is_usage_error():
    with pytest.raises(SystemExit) as info:
        main(["frobnicate", POWER])
    assert info.value.code == 2


# ---------- JSON-режим ----------


def test_parse_json_schema(capsys):
    code, data = cli_json(capsys, "parse", "--json", POWER)
    assert code == 0
    assert set(data) == ENVELOPE | {"ast"}
    assert data["schema_version"] == 1 and data["command"] == "parse" and data["ok"] is True
    assert data["ast"]["type"] == "Program"
    assert set(data["ast"]["span"]) == {"start", "end"}
    assert set(data["ast"]["span"]["start"]) == {"line", "column", "offset"}


def test_check_json_error_schema(capsys):
    code, data = cli_json(capsys, "check", "--json", BROKEN)
    assert code == 1
    assert set(data) == ENVELOPE and data["ok"] is False
    (diagnostic,) = data["diagnostics"]
    assert set(diagnostic) == {"code", "kind", "severity", "message", "hint", "span"}
    assert diagnostic["code"] == "E002" and diagnostic["kind"] == "syntax"
    assert diagnostic["span"]["start"]["line"] == 3


def test_run_json_schema(capsys):
    code, data = cli_json(capsys, "run", "--json", POWER, "-s", "X=2,Y=10")
    assert code == 0
    assert set(data) == ENVELOPE | {"status", "steps", "initial_state", "final_state"}
    assert data["status"] == "ok"
    assert data["initial_state"] == {"X": 2, "Y": 10}
    assert data["final_state"] == {"R": 1024, "X": 2, "Y": 0}


def test_run_json_runtime_error(capsys):
    code, data = cli_json(capsys, "run", "--json", POWER)
    assert code == 3
    assert data["ok"] is False and data["status"] == "runtime_error"
    assert data["diagnostics"][0]["code"] == "E101"
    assert data["final_state"] == {"R": 1}


def test_trace_json_schema(capsys):
    code, data = cli_json(capsys, "trace", "--json", POWER, "-s", "X=2,Y=1")
    assert code == 0
    assert set(data) == ENVELOPE | {"status", "steps", "initial_state", "final_state", "events"}
    kinds = {e["event"] for e in data["events"]}
    assert kinds == {
        "before_statement",
        "after_statement",
        "variable_changed",
        "condition_evaluated",
        "finished",
    }
    assert data["events"][-1]["event"] == "finished"
    assert data["events"][-1]["state"] == data["final_state"]


def test_json_syntax_error_for_run(capsys):
    code, data = cli_json(capsys, "run", "--json", BROKEN)
    assert code == 1 and data["command"] == "run" and data["ok"] is False


# ---------- tree / compare ----------


@pytest.mark.parametrize("kind", ["parse", "ast"])
def test_tree_formats(capsys, kind):
    code, out, _ = cli(capsys, "tree", POWER, "--kind", kind)
    assert code == 0 and ("program" if kind == "parse" else "Program") in out.splitlines()[0]

    code, data = cli_json(capsys, "tree", POWER, "--kind", kind, "--format", "json")
    assert code == 0 and data["kind"] == kind
    assert set(data["tree"]) == {"id", "label", "title", "category", "span", "source", "children"}

    code, out, _ = cli(capsys, "tree", POWER, "--kind", kind, "--format", "dot")
    assert code == 0 and out.startswith("digraph") and "->" in out

    code, out, _ = cli(capsys, "tree", POWER, "--kind", kind, "--format", "svg")
    assert code == 0 and out.startswith("<svg") and out.rstrip().endswith("</svg>")


def test_tree_writes_file(capsys, tmp_path):
    target = tmp_path / "tree.svg"
    code, out, err = cli(capsys, "tree", POWER, "--format", "svg", "-o", str(target))
    assert code == 0 and out == "" and "Записано" in err
    assert target.read_text(encoding="utf-8").startswith("<svg")


def test_tree_syntax_error(capsys):
    code, _, err = cli(capsys, "tree", BROKEN)
    assert code == 1 and "error[E002]" in err
    code, data = cli_json(capsys, "tree", BROKEN, "--format", "json")
    assert code == 1 and data["ok"] is False


def test_compare_writes_html(capsys, tmp_path):
    target = tmp_path / "compare.html"
    code, _, _ = cli(capsys, "compare", POWER, "-o", str(target))
    assert code == 0
    page = target.read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE html>") and page.count("<svg") == 2
    assert cli(capsys, "compare", BROKEN)[0] == 1


# ---------- справжній процес ----------


def run_process(*argv: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sipl", *argv],
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )


def test_module_entry_point_and_stdin():
    proc = run_process("run", "-", "--json", "-s", "N=5", stdin="begin F := N * N end")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["final_state"] == {"F": 25, "N": 5}


def test_exit_codes_in_real_process():
    assert run_process("check", POWER).returncode == 0
    assert run_process("check", BROKEN).returncode == 1
    assert run_process("check").returncode == 2
    assert run_process("run", POWER).returncode == 3
    assert run_process("run", POWER, "-s", "X=1,Y=99", "--max-steps", "5").returncode == 4


def test_version():
    proc = run_process("--version")
    assert proc.returncode == 0 and proc.stdout.startswith("sipl ")
