#!/usr/bin/env python3
"""
mdless - A LESSOPEN filter for Markdown rendering and syntax highlighting.

This utility works as a preprocessor for 'less', automatically rendering
Markdown files and syntax highlighting code using the rich library.
"""

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax


def is_markdown_file(filepath: str) -> bool:
    """Check if the file has a Markdown extension."""
    ext = Path(filepath).suffix.lower()
    return ext in ['.md', '.markdown']


def render_markdown(content: str, console: Console) -> None:
    """Render Markdown content using rich."""
    md = Markdown(content)
    console.print(md, soft_wrap=True)


def render_syntax(filepath: str, content: str) -> None:
    """Render code with syntax highlighting using rich."""
    # Determine lexer from file extension
    path = Path(filepath)
    ext = path.suffix.lstrip('.')

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

    # Handle stdin input
    input_file = args.file
    temp_file = None
    content = None

    try:
        if args.file == '-' or args.file == '/dev/stdin':
            # Read from stdin
            content = sys.stdin.read()
            input_file = 'stdin.md' if args.force_markdown else 'stdin.txt'
        else:
            # Read from file
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
            input_file = args.file

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
            elif args.file not in ['-', '/dev/stdin']:
                with open(args.file, 'r', encoding='utf-8') as f:
                    print(f.read(), end='')
            return 0
        except Exception:
            return 1


if __name__ == "__main__":
    sys.exit(main())
