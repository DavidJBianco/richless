# mdless

A terminal paginator for Markdown files, built on `less`. View your Markdown documents with beautiful formatting directly in the terminal.

## Features

- **Automatic Markdown Detection**: Recognizes `.md` and `.MD` files automatically
- **Rich Terminal Rendering**: Beautiful formatting with headers, lists, code blocks, tables, and more
- **Syntax Highlighting**: Code blocks with language-specific syntax highlighting
- **Less Integration**: Uses the familiar `less` pager for navigation and searching
- **Pass-through Mode**: Non-Markdown files are passed directly to `less`
- **Less-Compatible**: Accepts all standard `less` command-line options

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for Python package management.

```bash
# Install in development mode
uv pip install -e .

# Or install from the project directory
pip install .
```

## Usage

### Basic Usage

View a Markdown file (automatically detected):
```bash
mdless README.md
```

View any file with Markdown rendering:
```bash
mdless --md document.txt
```

### Using Less Options

All `less` command-line options work with `mdless`:

```bash
# Show line numbers
mdless -N README.md

# Case-insensitive search
mdless -i README.md

# Start at a specific line
mdless +50 README.md

# Combine multiple options
mdless -N -i +50 README.md
```

### mdless-Specific Options

- `--md`, `--markdown`: Force Markdown rendering for any file
- `--width WIDTH`: Set the rendering width (default: terminal width)
- `--help-mdless`: Show mdless-specific help

## Examples

```bash
# View a Markdown file
mdless CHANGELOG.md

# Force Markdown rendering on a text file
mdless --md notes.txt

# View with custom width
mdless --width 100 README.md

# Search for a term (inside less, press '/')
mdless README.md
# Then type: /installation

# View from a specific pattern (less option)
mdless +/Features README.md
```

## How It Works

1. `mdless` checks if the input file has a `.md` or `.MD` extension, or if `--md` flag is provided
2. If yes, it renders the Markdown content using the [Rich](https://github.com/Textualize/rich) library
3. The rendered content (with ANSI color codes) is written to a temporary file
4. The `less` pager is launched with the `-R` flag (to interpret colors) and the temporary file
5. After `less` exits, the temporary file is cleaned up

For non-Markdown files, `mdless` simply passes the file directly to `less`.

## Requirements

- Python 3.12+
- macOS or Linux
- `less` command (standard on macOS and most Linux distributions)

## Dependencies

- [rich](https://github.com/Textualize/rich) - For beautiful terminal formatting and Markdown rendering

## Development

```bash
# Clone the repository
git clone <repository-url>
cd mdless

# Install dependencies
uv sync

# Install in development mode
uv pip install -e .

# Run tests
uv run python -m pytest  # (when tests are added)
```

## License

See LICENSE file for details.
