"""Shared test helpers for richless tests."""

import re


def has_ansi_colors(output: str) -> bool:
    """Check if output contains any ANSI color codes."""
    return bool(re.search(r'\x1b\[\d+', output))


def has_multiple_colors(output: str) -> bool:
    """Check that output contains multiple distinct ANSI color codes (real syntax highlighting).

    This catches the case where content is rendered in a single color —
    ANSI codes are present but there's no actual highlighting.
    """
    colors = set(re.findall(r'\x1b\[[\d;]+m', output))
    return len(colors) >= 2


def has_markdown_formatting(output: str) -> bool:
    """Check if output contains Rich markdown formatting."""
    indicators = ["\u2503", "\u250f", "\u2517", "\u2501", "\u2513", "\u251b", "\u2500", "\u2022", " \u2022 "]
    return any(ind in output for ind in indicators)
