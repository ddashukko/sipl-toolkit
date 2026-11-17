"""Діагностика: повідомлення про помилки, прив'язані до SourceSpan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast import SourceSpan

# Стабільні коди діагностик (частина JSON-контракту)
UNEXPECTED_CHARACTER = "E001"
UNEXPECTED_TOKEN = "E002"
UNEXPECTED_END = "E003"
UNDEFINED_VARIABLE = "E101"
STEP_LIMIT = "E102"

_KIND = {"E0": "syntax", "E1": "runtime"}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    span: SourceSpan
    hint: str | None = None
    severity: str = "error"

    @property
    def kind(self) -> str:
        """'syntax' або 'runtime' (для E102 — 'step_limit')."""
        if self.code == STEP_LIMIT:
            return "step_limit"
        return _KIND.get(self.code[:2], "other")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
            "span": self.span.to_dict(),
        }

    def format(self, source: str, filename: str = "<input>") -> str:
        """Текст для людини: місце, повідомлення, рядок коду з позначкою."""
        s = self.span
        lines = [
            f"{filename}:{s.start_line}:{s.start_column}: "
            f"{self.severity}[{self.code}]: {self.message}"
        ]
        src_lines = source.splitlines()
        if 1 <= s.start_line <= len(src_lines):
            text = src_lines[s.start_line - 1].replace("\t", " ")
            if s.end_line == s.start_line:
                width = max(1, s.end_column - s.start_column)
            else:
                width = max(1, len(text) - s.start_column + 1)
            gutter = f"{s.start_line:>4} | "
            lines.append(gutter + text)
            lines.append(" " * (len(gutter) - 2) + "| " + " " * (s.start_column - 1) + "^" * width)
        if self.hint:
            lines.append(f"  підказка: {self.hint}")
        return "\n".join(lines)


class SiplError(Exception):
    """Базова помилка SIPL; завжди несе діагностику."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class SiplSyntaxError(SiplError):
    pass


class SiplRuntimeError(SiplError):
    pass
