# richless

A LESSOPEN filter for automatically rendering Markdown files and syntax highlighting source code when using `less`. View your Markdown documents with beautiful formatting and programming language files with syntax highlighting directly in the terminal, without changing how you use `less`.

## Quick Start

```bash
# 1. Install richless via Homebrew (macOS or Linux)
brew install DavidJBianco/tools/richless

# 2. Add shell integration to your ~/.bashrc or ~/.zshrc
# (brew will print the exact path after install)
source $(brew --prefix)/share/richless/richless-init.sh

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

### Homebrew (Preferred — macOS and Linux)

```bash
brew install DavidJBianco/tools/richless
```

After installation, add the shell integration to your `~/.bashrc` or `~/.zshrc`:

```bash
source $(brew --prefix)/share/richless/richless-init.sh
```

Then reload your shell:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

### pip / uv (Alternative)

If you prefer not to use Homebrew, you can install from [PyPI](https://pypi.org/project/richless/):

```bash
# With uv
uv tool install richless

# Or with pip
pip install richless
```

Then copy the shell integration script and source it:

```bash
# Download the init script
curl -o ~/.richless-init.sh https://raw.githubusercontent.com/DavidJBianco/richless/main/richless-init.sh

# Add to your ~/.bashrc or ~/.zshrc
echo 'source ~/.richless-init.sh' >> ~/.bashrc  # or ~/.zshrc

# Reload your shell
source ~/.bashrc  # or source ~/.zshrc
```

**Note:** If you see a warning about PATH after `uv tool install`, run:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add this line to your ~/.bashrc or ~/.zshrc to make it permanent
```

### Shell Integration Options

The shell integration script (sourced above) provides the full-featured **transparent wrapper** around `less`. This is the recommended setup and what Quick Start uses.

**What you get:**
- ✅ Automatic Markdown rendering when you run `less file.md`
- ✅ Syntax highlighting for programming language source files (Python, JavaScript, etc.)
- ✅ Works with wildcards: `less *.md` or `less *.py`
- ✅ Piped input works: `cat file.md | less` renders markdown
- ✅ Force markdown flag: `less --md document.txt` forces rendering
- ✅ Auto-detection: Intelligently detects markdown in piped content
- ✅ Backward compatible: Acts like normal `less` when not needed

**Note:** The shell integration file is compatible with sh, bash, and zsh.

#### Minimal Setup (without shell wrapper)

If you prefer not to use the shell wrapper, you can manually set two environment variables instead. Add these lines to your `~/.bashrc`, `~/.zshrc`, or `~/.profile`:

```bash
export LESSOPEN="|richless %s"
export LESS="-R"
```

This gives you automatic Markdown rendering and syntax highlighting for files, but piped input (`cat file.md | less`) and the `--md` flag won't work.

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
# Homebrew
brew upgrade richless

# uv
uv tool upgrade richless
```

## Uninstalling

```bash
# Homebrew
brew uninstall richless

# uv
uv tool uninstall richless
rm ~/.richless-init.sh
```

After uninstalling, remove the `source ...richless-init.sh` line from your `~/.bashrc` or `~/.zshrc`.

## Development

```bash
# Clone the repository
git clone https://github.com/DavidJBianco/richless.git
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
