# mdless

A LESSOPEN filter for automatically rendering Markdown files and syntax highlighting source code when using `less`. View your Markdown documents with beautiful formatting and programming language files with syntax highlighting directly in the terminal, without changing how you use `less`.

## Quick Start

```bash
# 1. Install mdless
uv tool install .

# 2. Add to your ~/.bashrc or ~/.zshrc
export LESSOPEN="|mdless %s"
export LESS="-R"

# 3. Reload your shell
source ~/.bashrc  # or ~/.zshrc

# 4. Try it!
less README.md     # View rendered Markdown
less mdless.py     # View syntax-highlighted Python
```

For advanced features (piped input, force markdown), see [Option 2: Transparent Wrapper](#option-2-transparent-wrapper-full-featured).

## Features

- **Seamless Integration**: Works transparently with `less` via LESSOPEN
- **Automatic Markdown Rendering**: Recognizes `.md` and `.markdown` files automatically and renders them beautifully
- **Rich Terminal Formatting**: Beautiful rendering with headers, lists, code blocks, tables, and more
- **Syntax Highlighting for Source Code**: Automatic syntax highlighting for Python, JavaScript, Java, C, Go, Rust, and many other programming languages
- **Works with Wildcards**: `less *.md` or `less *.py` just works
- **Correct Filenames**: Shows actual filenames in less, not temporary files
- **Powered by rich**: Leverages the excellent [rich](https://github.com/Textualize/rich) library for beautiful terminal output

## Installation

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** - Modern Python package manager
  ```bash
  # Install uv if you don't have it
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **less pager** (standard on macOS and most Linux distributions)

### Step 1: Install mdless

Install mdless in an isolated virtualenv using uv's tool install feature:

```bash
# Clone or download this repository
git clone <repository-url>
cd mdless

# Install mdless as a uv tool
uv tool install .

# Or install directly from git (once published)
# uv tool install git+https://github.com/yourusername/mdless
```

This installs `mdless` and all its dependencies (including rich-cli) in an isolated virtualenv, making the `mdless` command available system-wide without polluting your project environments.

**Note:** If you see a warning about PATH, run:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add this line to your ~/.bashrc or ~/.zshrc to make it permanent
```

### Step 2: Configure Shell Integration

You have two configuration options depending on your needs:

#### Option 1: Basic LESSOPEN (Simple - Recommended for most users)

This is the simplest setup. Just add two environment variables to your shell configuration.

**Setup:**

Add these lines to your `~/.bashrc`, `~/.zshrc`, or `~/.profile`:

```bash
export LESSOPEN="|mdless %s"
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

#### Option 2: Transparent Wrapper (Full-featured)

This option provides a smart wrapper around `less` that handles edge cases like piped input and forcing markdown on arbitrary files.

**Setup:**

1. Copy the shell integration script to your home directory:
   ```bash
   # From the mdless project directory
   cp mdless-init.sh ~/.mdless-init.sh
   ```

2. Source it in your shell configuration:
   ```bash
   # Add this line to ~/.bashrc, ~/.zshrc, or ~/.profile
   source ~/.mdless-init.sh
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

### Advanced Usage (Option 2 Only)

If you're using the transparent wrapper (Option 2), you get these additional features:

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

### Direct mdless Usage

You can also call `mdless` directly if needed:

```bash
# Render and pipe to less
mdless document.md | less -R

# Force markdown rendering
mdless --md document.txt | less -R

# Read from stdin
cat file.md | mdless --md - | less -R
echo "# Test" | mdless --md - | less -R
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
1. When you run `less file.md`, the `LESSOPEN` environment variable tells less to run `mdless file.md` first
2. `mdless` detects the `.md` extension and uses the `rich` library to render the Markdown
3. `rich` renders the Markdown to beautifully formatted ANSI text with proper table support
4. The formatted output is piped to `less` for viewing
5. For programming language source files (`.py`, `.js`, `.java`, etc.), `rich` automatically provides syntax highlighting using Pygments

**Transparent Wrapper (Option 2):**
- The shell function intercepts calls to `less` before they execute
- For regular files, it passes through to the basic LESSOPEN mechanism
- For piped input or when `--md` is specified, it saves the content to a temp file and renders it
- Auto-detection checks piped content for markdown patterns (headers, lists, links, etc.)

## Troubleshooting

### "mdless: command not found"

Make sure `~/.local/bin` is in your PATH:
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add this to your ~/.bashrc or ~/.zshrc
```

### Piped input doesn't work

You're using Option 1 (Basic LESSOPEN). Either:
- Switch to Option 2 (Transparent Wrapper) for piped input support
- Or use: `cat file.md | mdless --md - | less -R`

### Colors don't show up

Make sure you have the `-R` flag set:
```bash
export LESS="-R"
```

### Shell function not loading

Make sure you're sourcing the init script, not executing it:
```bash
source ~/.mdless-init.sh  # Correct
./mdless-init.sh          # Wrong - this won't define the function in your shell
```

### After sourcing, "less file.md" shows an error

Make sure you've reinstalled mdless after any updates:
```bash
uv tool uninstall mdless
uv tool install .
source ~/.mdless-init.sh  # Re-source if using Option 2
```

## Updating

```bash
# Update to the latest version
cd /path/to/mdless
git pull  # Get latest changes
uv tool upgrade mdless

# If using Option 2, re-source the init script
source ~/.mdless-init.sh
```

## Uninstalling

```bash
# Remove the tool
uv tool uninstall mdless

# Remove from your shell config
# Delete or comment out these lines from ~/.bashrc or ~/.zshrc:
# export LESSOPEN="|mdless %s"
# export LESS="-R"
# source ~/.mdless-init.sh  # If using Option 2

# Remove the init script (Option 2 only)
rm ~/.mdless-init.sh
```

## Development

```bash
# Clone the repository
git clone <repository-url>
cd mdless

# Install dependencies
uv sync

# Install in development mode
uv tool install --editable .

# Make changes, then reinstall
uv tool install --editable . --force

# Test it
less README.md

# Run tests
bash test-comprehensive.sh  # If available
```

## Dependencies

- [rich](https://github.com/Textualize/rich) - Python library for rich terminal output, Markdown rendering, and syntax highlighting
- [Pygments](https://pygments.org/) - Syntax highlighting library
- Python 3.12+
- uv - Modern Python package manager

## Comparison to Alternatives

**vs. glow / mdcat / bat:**
- mdless integrates directly with `less`, so you use your familiar pager commands
- Works transparently - no need to remember a different command
- Supports all standard `less` features (search, navigation, etc.)

**vs. vimpager:**
- Lighter weight, doesn't require Vim
- Uses rich library's excellent Markdown rendering with full table support
- Simple LESSOPEN integration

## License

See LICENSE file for details.
