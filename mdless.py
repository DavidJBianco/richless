#!/usr/bin/env python3
"""
mdless - A LESSOPEN filter for Markdown rendering and syntax highlighting.

This utility works as a preprocessor for 'less', automatically rendering
Markdown files and syntax highlighting code using rich-cli.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def is_markdown_file(filepath: str) -> bool:
    """Check if the file has a Markdown extension."""
    ext = Path(filepath).suffix.lower()
    return ext in ['.md', '.markdown']


def find_rich_executable() -> str:
    """
    Find the rich executable in the same virtualenv as this script.

    When installed via 'uv tool install', both mdless and rich-cli are in
    the same virtualenv, so we need to locate the rich executable relative
    to the Python interpreter running this script.
    """
    # Get the directory containing the Python executable
    python_bin = Path(sys.executable).parent

    # The rich executable should be in the same bin directory
    rich_path = python_bin / 'rich'

    if rich_path.exists():
        return str(rich_path)

    # Fallback: try to find rich in PATH
    import shutil
    rich_in_path = shutil.which('rich')
    if rich_in_path:
        return rich_in_path

    # Last resort: try python -m rich_cli
    return None


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

    if args.file == '-' or args.file == '/dev/stdin':
        # Read from stdin and create a temp file
        import tempfile
        temp_fd, temp_file = tempfile.mkstemp(suffix='.md' if args.force_markdown else '.txt')
        try:
            with open(temp_fd, 'w', encoding='utf-8') as f:
                f.write(sys.stdin.read())
            input_file = temp_file
        except Exception as e:
            print(f"mdless: Error reading from stdin: {e}", file=sys.stderr)
            if temp_file:
                import os
                os.unlink(temp_file)
            return 1

    # Find the rich executable
    rich_executable = find_rich_executable()

    if not rich_executable:
        # Try using python -m rich_cli as fallback
        rich_cmd = [sys.executable, '-m', 'rich_cli', input_file, '--force-terminal']
    else:
        # Build the rich-cli command
        rich_cmd = [rich_executable, input_file, '--force-terminal']

    # Force markdown mode if requested or if file is .md
    if args.force_markdown or is_markdown_file(input_file):
        rich_cmd.append('--markdown')

    # Run rich-cli to process the file
    exit_code = 0
    try:
        result = subprocess.run(
            rich_cmd,
            check=True,
            capture_output=False,  # Let output go directly to stdout
        )
        exit_code = result.returncode
    except subprocess.CalledProcessError as e:
        # If rich fails, fall back to plain cat
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                print(f.read(), end='')
            exit_code = 0
        except Exception:
            print(f"mdless: Error reading {input_file}", file=sys.stderr)
            exit_code = 1
    except (FileNotFoundError, ModuleNotFoundError):
        print("mdless: rich-cli not found. Please reinstall mdless.", file=sys.stderr)
        exit_code = 1
    finally:
        # Clean up temp file if we created one
        if temp_file:
            import os
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
