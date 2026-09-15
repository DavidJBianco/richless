#!/usr/bin/env python3
"""
richless - A LESSOPEN filter for Markdown rendering and syntax highlighting.

This utility works as a preprocessor for 'less', automatically rendering
Markdown files and syntax highlighting code using the rich library.
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from pygments.lexers import get_lexer_by_name, ClassNotFound
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

MIN_SYNTAX_WIDTH = 80
MAX_SYNTAX_WIDTH = 16384


def is_markdown_file(filepath: str) -> bool:
    """Check if the file has a Markdown extension."""
    ext = Path(filepath).suffix.lower()
    return ext in ['.md', '.markdown']


def detect_syntax_from_content(content: str) -> str:
    """Detect file type from content when extension is unknown."""
    if not content:
        return "text"

    lines = content.split('\n', 20)  # Check first 20 lines
    first_line = lines[0].strip() if lines else ''

    # YAML detection: starts with --- or %YAML
    if first_line == '---' or first_line.startswith('%YAML'):
        return "yaml"

    # JSON detection: starts with { or [
    # But exclude TOML section headers like [section] or [[array]]
    if first_line.startswith('{'):
        return "json"
    if first_line.startswith('[') and not re.match(r'^\[{1,2}[a-zA-Z_][a-zA-Z0-9_.-]*\]{1,2}\s*$', first_line):
        return "json"

    # Shebang detection
    if first_line.startswith('#!'):
        if 'python' in first_line:
            return "python"
        elif 'bash' in first_line or '/sh' in first_line:
            return "bash"
        elif 'node' in first_line:
            return "javascript"
        elif 'ruby' in first_line:
            return "ruby"
        elif 'perl' in first_line:
            return "perl"

    # XML/HTML detection
    if first_line.startswith('<?xml') or first_line.startswith('<!DOCTYPE'):
        return "xml"

    # TOML detection: look for key = value patterns or [section] headers
    toml_score = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # TOML section header: [section] or [[array]]
        if re.match(r'^\[{1,2}[a-zA-Z_][a-zA-Z0-9_.-]*\]{1,2}\s*$', stripped):
            return "toml"
        # TOML key = value (with equals sign, not colon)
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*\s*=\s*', stripped):
            toml_score += 1
            if toml_score >= 2:
                return "toml"
            continue
        break

    if toml_score > 0:
        return "toml"

    # YAML detection: look for key: value patterns (possibly after # comments)
    # Skip comment lines and look for YAML structure
    for line in lines:
        stripped = line.strip()
        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            continue
        # Check for YAML key: value pattern (word followed by colon)
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*:\s*', stripped):
            return "yaml"
        # If first non-comment line doesn't look like YAML, stop checking
        break

    return "text"


def get_terminal_width() -> int:
    """Get terminal width, even when stdout is piped."""
    # Try stderr since stdout is piped through LESSOPEN
    try:
        return os.get_terminal_size(sys.stderr.fileno()).columns
    except (OSError, ValueError):
        pass
    # Fall back to shutil (checks COLUMNS env var, then defaults to 80)
    return shutil.get_terminal_size().columns


def render_markdown(content: str) -> None:
    """Render Markdown content using rich."""
    width = get_terminal_width()
    console = Console(force_terminal=True, color_system="truecolor", width=width)
    md = Markdown(content)
    console.print(md)


def get_syntax_width_and_overflow(content: str) -> tuple[int, bool]:
    """Calculate safe syntax render width and whether content exceeds safety cap."""
    max_line_length = max((len(line) for line in content.splitlines()), default=MIN_SYNTAX_WIDTH)
    desired_width = max(max_line_length + 1, MIN_SYNTAX_WIDTH)
    width = min(desired_width, MAX_SYNTAX_WIDTH)
    return width, desired_width > MAX_SYNTAX_WIDTH


def render_syntax(filepath: str, content: str) -> None:
    """Render code with syntax highlighting using rich."""
    # Determine lexer from file extension
    path = Path(filepath)
    ext = path.suffix.lstrip('.')

    # Map non-standard extensions to their lexer names
    ext_map = {
        'jsonl': 'json',  # JSON Lines uses JSON syntax
    }
    if ext in ext_map:
        ext = ext_map[ext]

    # If no recognizable extension, try to detect from content
    # Temp files from shell wrapper are named richless.XXXXXX (random suffix)
    if not ext or (path.stem == 'richless' and re.match(r'^\.[a-zA-Z0-9]{6}$', path.suffix)):
        ext = detect_syntax_from_content(content)
    elif ext:
        # Verify Pygments recognizes this extension; if not, try content detection
        try:
            get_lexer_by_name(ext)
        except ClassNotFound:
            ext = detect_syntax_from_content(content)

    # Calculate width needed to avoid truncating long lines.
    # Clamp width to protect against pathological single-line inputs.
    width, exceeds_width_cap = get_syntax_width_and_overflow(content)

    # If any line exceeds the safe rendering width, fall back to raw output.
    # This preserves file visibility without unbounded rendering cost.
    if exceeds_width_cap:
        print(content, end='')
        return

    # Create console with width to accommodate longest line
    console = Console(force_terminal=True, color_system="truecolor", width=width)

    # Create Syntax object - use default background to avoid padding
    syntax = Syntax(content, ext or "text", theme="monokai", line_numbers=False,
                    background_color="default")
    console.print(syntax)


def main():
    """Main entry point for richless."""
    parser = argparse.ArgumentParser(
        description='LESSOPEN filter for Markdown rendering and syntax highlighting',
        add_help=True,
    )

    parser.add_argument('file',
                       help='File to process (use "-" for stdin)')
    parser.add_argument('--md', '--markdown',
                       dest='force_markdown',
                       action='store_true',
                       help='Force Markdown rendering even for non-.md files')

    args = parser.parse_args()

    # Strip whitespace from filename (less adds leading space via LESSOPEN)
    filepath = args.file.strip()

    # Handle stdin input
    input_file = filepath
    temp_file = None
    content = None

    try:
        if filepath == '-' or filepath == '/dev/stdin':
            # Read from stdin
            content = sys.stdin.read()
            input_file = 'stdin.md' if args.force_markdown else 'stdin.txt'
        else:
            # Read from file
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            input_file = filepath

        # Determine if we should render as markdown
        is_markdown = args.force_markdown or is_markdown_file(input_file)

        if is_markdown:
            render_markdown(content)
        else:
            # Syntax highlighting for code files
            render_syntax(input_file, content)

        return 0

    except FileNotFoundError:
        print(f"richless: File not found: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"richless: Error: {e}", file=sys.stderr)
        # Fall back to plain output
        try:
            if content:
                print(content, end='')
            elif filepath not in ['-', '/dev/stdin']:
                with open(filepath, 'r', encoding='utf-8') as f:
                    print(f.read(), end='')
            return 0
        except Exception:
            return 1


if __name__ == "__main__":
    sys.exit(main())
