"""CORE-06: conformance suite проходить на еталонній реалізації та ловить розбіжності."""

import importlib.util
import json
import sys

from conftest import ROOT

RUNNER = ROOT / "conformance" / "run.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("sipl_conformance_run", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_suite_has_all_three_kinds_of_cases():
    cases = [
        json.loads(p.read_text(encoding="utf-8")) for p in (RUNNER.parent / "cases").glob("*.json")
    ]
    assert len(cases) >= 30
    assert any("ast" in c["expect"] for c in cases)
    assert any("final_state" in c["expect"] for c in cases)
    assert any(c["expect"]["syntax"] == "error" for c in cases)
    assert any(c["expect"].get("status") == "runtime_error" for c in cases)
    assert any(c["expect"].get("status") == "step_limit" for c in cases)


def test_reference_implementation_passes(capsys):
    assert load_runner().main([]) == 0
    assert "Пройдено" in capsys.readouterr().out


def test_runner_does_not_import_sipl():
    assert "import sipl" not in RUNNER.read_text(encoding="utf-8")
    assert "from sipl" not in RUNNER.read_text(encoding="utf-8")


def test_runner_detects_wrong_expectations(tmp_path, capsys):
    (tmp_path / "wrong.sipl").write_text("begin X := 1 end", encoding="utf-8")
    case = {"expect": {"syntax": "ok", "status": "ok", "final_state": {"X": 2}}}
    (tmp_path / "wrong.json").write_text(json.dumps(case), encoding="utf-8")
    (tmp_path / "accepted.sipl").write_text("begin skip end", encoding="utf-8")
    case = {"expect": {"syntax": "error"}}
    (tmp_path / "accepted.json").write_text(json.dumps(case), encoding="utf-8")

    assert load_runner().main(["--cases", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL wrong" in out and "кінцевий стан" in out
    assert "FAIL accepted" in out
    assert "Пройдено 0 з 2" in out


def test_runner_reports_broken_implementation(tmp_path, capsys):
    (tmp_path / "a.sipl").write_text("begin skip end", encoding="utf-8")
    (tmp_path / "a.json").write_text('{"expect": {"syntax": "ok"}}', encoding="utf-8")
    impl = f'"{sys.executable}" -c "print(42)"'
    assert load_runner().main(["--cases", str(tmp_path), "--impl", impl]) == 1
    assert "FAIL a" in capsys.readouterr().out


def test_empty_directory(tmp_path):
    assert load_runner().main(["--cases", str(tmp_path)]) == 2
