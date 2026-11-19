"""SIPL Language Toolkit: граматика, парсер, AST, інтерпретатор, trace, візуалізація."""

from .ast import Program, SourceSpan
from .diagnostics import Diagnostic, SiplError, SiplRuntimeError, SiplSyntaxError
from .interpreter import ExecutionResult, Interpreter, run, trace
from .parse_tree import ParseNode
from .parser import build_ast, check, grammar_text, parse, parse_tree

__version__ = "0.5.0"

__all__ = [
    "Diagnostic",
    "ExecutionResult",
    "Interpreter",
    "ParseNode",
    "Program",
    "SiplError",
    "SiplRuntimeError",
    "SiplSyntaxError",
    "SourceSpan",
    "__version__",
    "build_ast",
    "check",
    "grammar_text",
    "parse",
    "parse_tree",
    "run",
    "trace",
]
