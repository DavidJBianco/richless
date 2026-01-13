# richless

A LESSOPEN filter for automatically rendering Markdown files and syntax highlighting source code when using `less`. View your Markdown documents with beautiful formatting and programming language files with syntax highlighting directly in the terminal, without changing how you use `less`.

## Quick Start

```bash
# 1. Install richless
git clone <repository-url>
cd richless
uv tool install .

# 2. Copy init script and add to your ~/.bashrc or ~/.zshrc
cp richless-init.sh ~/.richless-init.sh
echo 'source ~/.richless-init.sh' >> ~/.bashrc  # or ~/.zshrc

# 3. Reload your shell
source ~/.bashrc  # or ~/.zshrc

# 4. Try it!
less README.md       # View rendered Markdown
less richless.py     # View syntax-highlighted Python
```

## Features

- **Seamless Integration**: Works transparently with `less` via LESSOPEN
- **Automatic Markdown Rendering**: Recognizes `.md` and `.markdown` files automatically and renders them beautifully
- **Rich Terminal Formatting**: Beautiful rendering with headers, lists, code blocks, tables, and more
- **Data Format Highlighting**: Syntax highlighting for JSON, JSONL, YAML, and XML files with automatic detection
- **Code Highlighting**: Syntax highlighting for 500+ programming languages (Python, JavaScript, Go, Rust, and more)
- **Works with Wildcards**: `less *.md` or `less *.py` just works
- **Correct Filenames**: Shows actual filenames in less, not temporary files
- **Powered by rich and Pygments**: Leverages [rich](https://github.com/Textualize/rich) for beautiful terminal output and [Pygments](https://pygments.org/) for syntax highlighting

## Installation

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** - Modern Python package manager
  ```bash
  # Install uv if you don't have it
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **less pager** (standard on macOS and most Linux distributions)

### Step 1: Install richless

Install richless in an isolated virtualenv using uv's tool install feature:

```bash
# Clone or download this repository
git clone <repository-url>
cd richless

# Install richless as a uv tool
uv tool install .

# Or install directly from git (once published)
# uv tool install git+https://github.com/yourusername/richless
```

This installs `richless` and all its dependencies in an isolated virtualenv, making the `richless` command available system-wide without polluting your project environments.

**Note:** If you see a warning about PATH, run:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add this line to your ~/.bashrc or ~/.zshrc to make it permanent
```

### Step 2: Configure Shell Integration

You have two configuration options depending on your needs:

#### Option 1: Basic LESSOPEN (Minimal setup)

If you prefer not to use the shell wrapper, you can manually set two environment variables. This is a lighter-weight alternative but lacks some features.

**Setup:**

Add these lines to your `~/.bashrc`, `~/.zshrc`, or `~/.profile`:

```bash
export LESSOPEN="|richless %s"
export LESS="-R"
```

Then reload your shell:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

**What you get:**
- ✅ Automatic Markdown rendering when you run `less file.md`
- ✅ Syntax highlighting for programming language source files (Python, JavaScript, etc.)
- ✅ Works with wildcards: `less *.md` or `less *.py`
- ✅ Fast and lightweight

**Limitations:**
- ❌ Doesn't work with piped input: `cat file.md | less` won't render
- ❌ Can't force markdown on non-.md files through `less`

#### Option 2: Transparent Wrapper (Recommended - used by Quick Start)

This is the recommended setup and what Quick Start uses. It provides a smart wrapper around `less` that handles edge cases like piped input and forcing markdown on arbitrary files.

**Setup:**

1. Copy the shell integration script to your home directory:
   ```bash
   # From the richless project directory
   cp richless-init.sh ~/.richless-init.sh
   ```

2. Source it in your shell configuration:
   ```bash
   # Add this line to ~/.bashrc, ~/.zshrc, or ~/.profile
   source ~/.richless-init.sh
   ```

3. Reload your shell:
   ```bash
   source ~/.bashrc  # or source ~/.zshrc
   ```

**What you get:**
- ✅ Everything from Option 1, plus:
- ✅ Piped input works: `cat file.md | less` renders markdown
- ✅ Force markdown flag: `less --md document.txt` forces rendering
- ✅ Auto-detection: Intelligently detects markdown in piped content
- ✅ Backward compatible: Acts like normal `less` when not needed

**Note:** The shell integration file is compatible with sh, bash, and zsh.

## Usage

Once configured, just use `less` normally! Markdown files will be automatically rendered, and source code files will be syntax highlighted.

### Basic Usage (Both Options)

```bash
# View a Markdown file (automatically rendered)
less README.md

# View multiple Markdown files
less *.md

# View with wildcards
less docs/**/*.md

# Source code files get syntax highlighting automatically
less script.py           # Python
less app.js              # JavaScript
less main.go             # Go
less config.json         # JSON
less styles.css          # CSS

# All standard less options work
less -N README.md        # Show line numbers
less -i script.py        # Case-insensitive search
less +50 README.md       # Start at line 50
```

### Additional Features (Option 2 / Quick Start)

If you followed the Quick Start or are using Option 2, you also get these features:

```bash
# Force Markdown rendering on non-.md files
less --md document.txt
less -m notes.txt

# Piped input works!
cat file.md | less
echo "# Hello\n**World**" | less --md

# Pipe from other commands
curl https://example.com/README.md | less --md
grep -A 50 "## Section" doc.md | less

# Auto-detection: if piped content looks like markdown, it renders automatically
cat file.md | less  # Detects markdown syntax and renders
```

### Direct richless Usage

You can also call `richless` directly if needed:

```bash
# Render and pipe to less
richless document.md | less -R

# Force markdown rendering
richless --md document.txt | less -R

# Read from stdin
cat file.md | richless --md - | less -R
echo "# Test" | richless --md - | less -R
```

### Standard less Commands

All standard `less` commands work normally inside the pager:

- `/pattern` - Search forward
- `?pattern` - Search backward
- `n` / `N` - Next/previous match
- `g` / `G` - Go to start/end
- `q` - Quit
- `h` - Help

## How It Works

**Basic Mode (Option 1):**
1. When you run `less file.md`, the `LESSOPEN` environment variable tells less to run `richless file.md` first
2. `richless` detects the `.md` extension and uses the `rich` library to render the Markdown
3. `rich` renders the Markdown to beautifully formatted ANSI text with proper table support
4. The formatted output is piped to `less` for viewing
5. For programming language source files (`.py`, `.js`, `.java`, etc.), `rich` automatically provides syntax highlighting using Pygments

**Transparent Wrapper (Option 2):**
- The shell function intercepts calls to `less` before they execute
- For regular files, it passes through to the basic LESSOPEN mechanism
- For piped input or when `--md` is specified, it saves the content to a temp file and renders it
- Auto-detection checks piped content for markdown patterns (headers, lists, links, etc.)

## Troubleshooting

### "richless: command not found"

Make sure `~/.local/bin` is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add this to your ~/.bashrc or ~/.zshrc
```

### Piped input doesn't work

If you're using Option 1 (Basic LESSOPEN), piped input won't work. Either:
- Switch to Option 2 / Quick Start for piped input support
- Or use: `cat file.md | richless --md - | less -R`

### Colors don't show up

If you're using Option 1 (manual setup), make sure you have the `-R` flag set:
```bash
export LESS="-R"
```
The init script (Option 2 / Quick Start) sets this automatically.

### Shell function not loading

Make sure you're sourcing the init script, not executing it:
```bash
source ~/.richless-init.sh  # Correct
./richless-init.sh          # Wrong - this won't define the function in your shell
```

### After sourcing, "less file.md" shows an error

Make sure you've reinstalled richless after any updates:
```bash
uv tool uninstall richless
uv tool install .
source ~/.richless-init.sh  # Re-source to pick up changes
```

## Updating

```bash
# Update to the latest version
cd /path/to/richless
git pull  # Get latest changes
uv tool upgrade richless

# Re-source the init script to pick up any changes
source ~/.richless-init.sh
```

## Uninstalling

```bash
# Remove the tool
uv tool uninstall richless

# Remove from your shell config (~/.bashrc or ~/.zshrc)
# Delete or comment out the source line:
# source ~/.richless-init.sh

# Remove the init script
rm ~/.richless-init.sh

# If using Option 1 instead, remove these lines:
# export LESSOPEN="|richless %s"
# export LESS="-R"
```

## Development

```bash
# Clone the repository
git clone <repository-url>
cd richless

# Install dependencies
uv sync

# Install in development mode
uv tool install --editable .

# Make changes, then reinstall
uv tool install --editable . --force

# Test it
less README.md

# Run tests
uv run pytest tests/test_richless.py -v
```

## Dependencies

- [rich](https://github.com/Textualize/rich) - Python library for rich terminal output, Markdown rendering, and syntax highlighting
- [Pygments](https://pygments.org/) - Syntax highlighting library
- Python 3.12+
- uv - Modern Python package manager

## Comparison to Alternatives

**vs. glow / mdcat / bat:**
- richless integrates directly with `less`, so you use your familiar pager commands
- Works transparently - no need to remember a different command
- Supports all standard `less` features (search, navigation, etc.)

**vs. vimpager:**
- Lighter weight, doesn't require Vim
- Uses rich library's excellent Markdown rendering with full table support
- Simple LESSOPEN integration

## License

See LICENSE file for details.
