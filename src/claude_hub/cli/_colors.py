"""Tiny ANSI color helpers; no-op if stdout is not a tty or NO_COLOR is set."""
from __future__ import annotations
import os
import sys

_ENABLED = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

def _wrap(code: str, text: str) -> str:
    if not _ENABLED:
        return text
    return f"\033[{code}m{text}\033[0m"

def green(t): return _wrap("32", t)
def red(t): return _wrap("31", t)
def yellow(t): return _wrap("33", t)
def bold(t): return _wrap("1", t)
