#!/usr/bin/env python3
"""
mdless - A LESSOPEN filter for Markdown rendering and syntax highlighting.

This utility works as a preprocessor for 'less', automatically rendering
Markdown files and syntax highlighting code using the rich library.
"""

import argparse
import re
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax


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
    if first_line.startswith('{') or first_line.startswith('['):
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


def render_markdown(content: str, console: Console) -> None:
    """Render Markdown content using rich."""
    md = Markdown(content)
    console.print(md, soft_wrap=True)


def render_syntax(filepath: str, content: str) -> None:
    """Render code with syntax highlighting using rich."""
    # Determine lexer from file extension
    path = Path(filepath)
    ext = path.suffix.lstrip('.')

    # If no recognizable extension, try to detect from content
    if not ext or ext.startswith('mdless'):
        ext = detect_syntax_from_content(content)

    # Calculate width needed to avoid truncating long lines
    # This allows 'less' to handle horizontal scrolling
    lines = content.splitlines()
    max_line_length = max((len(line) for line in lines), default=80)
    width = max(max_line_length + 1, 80)

    # Create console with width to accommodate longest line
    console = Console(force_terminal=True, width=width)

    # Create Syntax object - use default background to avoid padding
    syntax = Syntax(content, ext or "text", theme="monokai", line_numbers=False,
                    background_color="default")
    console.print(syntax)


def main():
    """Main entry point for mdless."""
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

        # Create console with force_terminal to ensure colors work in pipes
        console = Console(force_terminal=True)

        # Determine if we should render as markdown
        is_markdown = args.force_markdown or is_markdown_file(input_file)

        if is_markdown:
            render_markdown(content, console)
        else:
            # Syntax highlighting for code files
            render_syntax(input_file, content)

        return 0

    except FileNotFoundError:
        print(f"mdless: File not found: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"mdless: Error: {e}", file=sys.stderr)
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
