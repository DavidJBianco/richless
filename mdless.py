#!/usr/bin/env python3
"""
mdless - A terminal paginator for Markdown files, built on less.

This utility works like 'less' but automatically renders Markdown files
in a terminal-friendly format.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown


def is_markdown_file(filepath: str) -> bool:
    """Check if the file has a Markdown extension."""
    ext = Path(filepath).suffix.lower()
    return ext in ['.md', '.markdown']


def render_markdown_to_ansi(markdown_content: str, width: Optional[int] = None) -> str:
    """Render Markdown content to ANSI-formatted text suitable for terminal display."""
    console = Console(width=width, force_terminal=True, color_system="auto")

    # Create a Markdown object
    md = Markdown(markdown_content)

    # Capture the rendered output
    with console.capture() as capture:
        console.print(md)

    return capture.get()


def run_less(content: str, less_args: list[str], original_filename: Optional[str] = None) -> int:
    """
    Write content to a temporary file and open it with less.

    Args:
        content: The content to display
        less_args: Additional arguments to pass to less
        original_filename: The original filename to display in less prompts

    Returns:
        The exit code from less
    """
    # Create a temporary file that persists until less is done reading it
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Build the less command
        # Add -R flag to interpret ANSI color codes
        less_cmd = ['less', '-R']

        # If we have an original filename, set the prompt to show it
        if original_filename:
            # Set the normal prompt (bottom of screen) to show the original filename
            # Escape the filename by replacing special characters
            escaped_filename = original_filename.replace('.', '\\.')
            less_cmd.append(f'-P{escaped_filename}')

        less_cmd.extend(less_args + [tmp_path])

        # Run less with the temporary file
        result = subprocess.run(less_cmd)
        return result.returncode
    finally:
        # Clean up the temporary file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    """Main entry point for mdless."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='A terminal paginator for Markdown files, built on less',
        add_help=False,  # We'll handle help ourselves to be compatible with less
        allow_abbrev=False
    )

    # Add mdless-specific options
    parser.add_argument('--md', '--markdown', dest='force_markdown', action='store_true',
                       help='Force Markdown rendering even for non-.md files')
    parser.add_argument('--width', type=int, default=None,
                       help='Set the width for Markdown rendering (default: terminal width)')
    parser.add_argument('--help-mdless', action='store_true',
                       help='Show mdless-specific help')

    # File argument
    parser.add_argument('file', nargs='?', default=None,
                       help='File to display')

    # Parse known args to allow passing through less options
    args, unknown_args = parser.parse_known_args()

    # Show mdless help if requested
    if args.help_mdless:
        print("""mdless - A terminal paginator for Markdown files

Usage: mdless [OPTIONS] [FILE]

mdless-specific options:
  --md, --markdown    Force Markdown rendering
  --width WIDTH       Set rendering width (default: terminal width)
  --help-mdless       Show this help

All other options are passed through to 'less'.

When displaying .md or .MD files (or with --md flag), mdless will render
the Markdown content before passing it to less for pagination.

For standard 'less' options, run: man less
""")
        return 0

    # Determine if we should render as Markdown
    should_render_markdown = False

    if args.force_markdown:
        should_render_markdown = True
    elif args.file and is_markdown_file(args.file):
        should_render_markdown = True

    # If no file specified and not forcing markdown, just run less
    if not args.file:
        # Pass through to less with stdin
        less_cmd = ['less'] + unknown_args
        result = subprocess.run(less_cmd)
        return result.returncode

    # Check if file exists
    if not os.path.exists(args.file):
        print(f"mdless: {args.file}: No such file or directory", file=sys.stderr)
        return 1

    # Read the file content
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # If we can't decode as UTF-8, just pass to less directly
        less_cmd = ['less'] + unknown_args + [args.file]
        result = subprocess.run(less_cmd)
        return result.returncode
    except Exception as e:
        print(f"mdless: Error reading {args.file}: {e}", file=sys.stderr)
        return 1

    # If we should render as Markdown, do so
    if should_render_markdown:
        try:
            rendered_content = render_markdown_to_ansi(content, width=args.width)
            return run_less(rendered_content, unknown_args, original_filename=args.file)
        except Exception as e:
            print(f"mdless: Error rendering Markdown: {e}", file=sys.stderr)
            return 1
    else:
        # Not a Markdown file, just pass to less
        less_cmd = ['less'] + unknown_args + [args.file]
        result = subprocess.run(less_cmd)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
