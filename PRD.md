# PRD: richless

## 1. Overview

richless is a LESSOPEN filter that transparently renders Markdown files and syntax-highlights source code when using `less`. It integrates seamlessly with the user's existing terminal workflow — no new commands to learn, no behavior changes required. Users simply run `less` as they always have, and Markdown files are beautifully rendered while code files get syntax highlighting automatically.

The project consists of two components:
1. **`richless` (Python CLI)** — The LESSOPEN preprocessor that detects file types and renders output using the `rich` library and Pygments.
2. **`richless-init.sh` (Shell integration)** — A shell function wrapper around `less` that adds support for piped input, auto-detection of content type, and a `--md` flag to force Markdown rendering.

## 2. Goals & Non-Goals

### Goals
- Provide transparent Markdown rendering and syntax highlighting through `less` with zero workflow change
- Support the following data formats: Markdown, JSON, JSONL, YAML, XML
- Syntax-highlight 500+ programming languages via Pygments
- Work with piped input (`cat file.md | less`) via the shell wrapper
- Auto-detect content type for piped input and extensionless files
- Dynamically adapt to terminal width
- Install easily via Homebrew (preferred) or pip/uv
- Support sh, bash, and zsh shells

### Non-Goals
- Replacing `less` — richless augments it, never overrides core `less` behavior
- Rendering formats beyond text (e.g., images, PDFs)
- Providing a standalone viewer — richless is always used through `less`
- Supporting non-POSIX shells (fish, nushell, PowerShell) in MVP

## 3. Target Users

Developers, sysadmins, security analysts, and anyone who spends significant time in the terminal and regularly works with Markdown, JSON, YAML, or source code files. These users already know and use `less` and want richer output without changing their habits.

## 4. Functional Requirements

### 4.1 Core Workflows

#### Workflow 1: View a Markdown file
1. User runs `less README.md`
2. `LESSOPEN` invokes `richless README.md`
3. richless detects `.md`/`.markdown` extension via `is_markdown_file()`
4. richless renders content using `rich.markdown.Markdown` with dynamic terminal width
5. Rendered ANSI output is displayed in `less` with full pager controls

#### Workflow 2: View a source code file
1. User runs `less script.py`
2. `LESSOPEN` invokes `richless script.py`
3. richless determines the lexer from file extension, falling back to content detection
4. richless renders with `rich.syntax.Syntax` using the Monokai theme
5. Console width is set to the longest line in the file (minimum 80) to allow horizontal scrolling in `less`

#### Workflow 3: View piped input (shell wrapper only)
1. User runs `cat file.md | less`
2. Shell wrapper detects stdin is a pipe
3. Content is saved to a temp file (`/tmp/richless.XXXXXX`)
4. Shell wrapper runs content detection heuristics:
   - First line starts with `---`, `%YAML`, `{`, or `[` → syntax highlighting
   - First non-comment line matches YAML `key:` pattern → syntax highlighting
   - Content matches markdown patterns (headers, lists, links, code fences, bold, blockquotes, tables, horizontal rules) → Markdown rendering
   - Otherwise → plain passthrough to `less`
5. Rendered output is piped to `less -R`
6. Temp file is cleaned up

#### Workflow 4: Force Markdown rendering
1. User runs `less --md document.txt`
2. Shell wrapper strips the `--md` flag and passes the file to `richless --md`
3. richless renders as Markdown regardless of file extension

#### Workflow 5: Unsupported or binary file
1. User runs `less somefile.bin`
2. richless attempts to read the file as UTF-8
3. If the file cannot be decoded as UTF-8 (binary or non-UTF-8 encoding), richless exits cleanly with no output
4. `less` falls back to reading the file directly (its normal behavior), so the user sees the file exactly as plain `less` would show it

### 4.2 Data Model

richless is stateless with no persistent data. The key data structures are:

| Concept | Description |
|---|---|
| **File extension map** | `ext_map` dict in `render_syntax()` mapping non-standard extensions to Pygments lexer names. Currently: `{'jsonl': 'json'}` |
| **Markdown extensions** | List `['.md', '.markdown']` checked by `is_markdown_file()` |
| **Content detection rules** | Ordered heuristics in `detect_syntax_from_content()`: YAML document start → JSON object/array → shebang lines → XML/DOCTYPE → YAML key:value pattern → fallback to "text" |
| **Shell detection patterns** | Regex patterns in `richless-init.sh` for piped input: YAML/JSON first-line check → YAML key pattern → markdown pattern matching. Note: the shell-level heuristics and Python-level heuristics are independent implementations with different pattern sets. Piped input uses shell detection; file input uses Python detection. |

### 4.3 CLI Interface

```
richless [-h] [--md | --markdown] file

Positional arguments:
  file              File to process. Use "-" for stdin.

Optional arguments:
  -h, --help        Show help message and exit
  --md, --markdown  Force Markdown rendering even for non-.md files
```

**Exit codes:**
- `0` — Success (including fallback to raw output on error)
- `1` — File not found, or unrecoverable error

**Shell wrapper flags (via `richless-init.sh`):**
- `--md` — Force Markdown rendering (stripped before passing to `less`). Note: the `-m` short flag was removed because it conflicts with `less`'s built-in `-m` flag (verbose prompt).
- All other flags are passed through to `less` unchanged

### 4.4 Supported File Types

| Category | Extensions / Detection | Rendering |
|---|---|---|
| Markdown | `.md`, `.markdown` | Rich Markdown rendering with headers, lists, tables, code blocks, blockquotes |
| JSON | `.json`, content starting with `{` or `[` | Syntax highlighting (JSON lexer) |
| JSONL | `.jsonl` | Syntax highlighting (JSON lexer via ext_map) |
| YAML | `.yaml`, `.yml`, content starting with `---` or `%YAML`, or key:value pattern | Syntax highlighting (YAML lexer) |
| XML | `.xml`, content starting with `<?xml` or `<!DOCTYPE` | Syntax highlighting (XML lexer) |
| Python | `.py`, shebang with `python` | Syntax highlighting (Python lexer) |
| Shell | `.sh`, `.bash`, shebang with `bash` or `/sh` | Syntax highlighting (Bash lexer) |
| JavaScript | `.js`, shebang with `node` | Syntax highlighting (JavaScript lexer) |
| Ruby | `.rb`, shebang with `ruby` | Syntax highlighting (Ruby lexer) |
| Perl | `.pl`, shebang with `perl` | Syntax highlighting (Perl lexer) |
| All others | Any extension recognized by Pygments | Syntax highlighting via Pygments lexer auto-detection |
| Unknown | No recognized extension, no content match | Plain text passthrough |

## 5. Non-Functional Requirements

| Requirement | Specification |
|---|---|
| **Startup latency** | richless should add < 300ms wall-clock time for files under 10,000 lines on a modern machine. |
| **Encoding** | Only UTF-8 encoded files are fully supported. Non-UTF-8 files are passed through to `less` unprocessed (see Workflow 5). |
| **Terminal width** | Markdown rendering must use the current terminal width dynamically (detected via stderr fd, falling back to `shutil.get_terminal_size()`). Syntax highlighting uses the width of the longest line (minimum 80 columns) to enable horizontal scrolling. |
| **Compatibility** | Python 3.12+. Shell integration works with sh, bash, and zsh on macOS, Linux, and Windows (WSL). Note: the shell wrapper uses `local` (a widely-supported but non-POSIX extension); this works in bash, zsh, dash, and all common `/bin/sh` implementations on supported platforms. |
| **Graceful degradation** | If richless fails for any reason, the user must still see the raw file content in `less`. Never block the user from viewing a file. |
| **No side effects** | richless must not modify any files, write to disk (except temp files cleaned up immediately), or produce persistent state. |

## 6. Technical Architecture

### 6.1 Tech Stack

| Component | Technology | Version |
|---|---|---|
| Language | Python | >= 3.12 |
| Terminal rendering | rich | >= 13.8.0 |
| Syntax highlighting | Pygments | >= 2.0.0 |
| Build system | hatchling | latest |
| Package manager (dev) | uv | latest |
| Test framework | pytest | >= 7.0.0 |
| Linter & formatter | ruff | latest |
| Type checker | mypy | latest |
| Distribution | Homebrew (DavidJBianco/tools tap), PyPI | — |

### 6.2 Project Structure

```
richless/
├── richless.py              # Main module — all application logic
├── richless-init.sh         # Shell integration script (sh/bash/zsh)
├── pyproject.toml           # Project metadata, dependencies, build config
├── LICENSE
├── README.md
├── PRD.md                   # This document (dev only)
├── AGENTS.md                # AI agent coding guidelines (dev only)
├── TODO.md                  # Task tracking for current/future work (dev only)
├── tests/                   # Test suite (dev only)
│   ├── test_richless.py     # Unit, integration, and LESSOPEN tests
│   └── fixtures/            # Test input files (Markdown, YAML, JSON, code, etc.)
│       ├── test.md
│       ├── test.yaml
│       ├── test-with-comments.yaml
│       ├── test-mcp-config.yaml
│       ├── test.json
│       ├── test.jsonl
│       ├── test.py
│       └── test.sh
├── build/                   # Build artifacts (generated)
├── richless.egg-info/       # Egg info (generated)
└── .venv/                   # Virtual environment (local dev)
```

Files included in the distributed package (sdist/wheel): `richless.py`, `richless-init.sh`, `LICENSE`, `README.md`. All other files are development-only.

### 6.3 Configuration & Secrets

richless has no configuration file and no secrets.

**Environment variables:**
| Variable | Purpose | Default |
|---|---|---|
| `LESSOPEN` | Set by `richless-init.sh` to `\|richless %s` | Not set |
| `LESS` | Set by `richless-init.sh` to include `-R` for ANSI color support | Preserves existing value if set |
| `COLUMNS` | Fallback for terminal width detection | Detected automatically |

## 7. UI/UX

richless has no UI of its own. All output is rendered ANSI text displayed within `less`.

**Markdown rendering** uses Rich's `Markdown` class, which produces:
- Styled headers (bold, colored)
- Bullet and numbered lists with proper indentation
- Code blocks with syntax highlighting
- Tables with box-drawing characters
- Blockquotes with vertical bar indicators
- Bold, italic, and inline code formatting
- Horizontal rules

**Syntax highlighting** uses Rich's `Syntax` class with:
- Monokai color theme
- No line numbers (user can use `less -N` for that)
- Default background color (no padding/background fill)
- Width set to longest line to enable horizontal scrolling

**Empty state:** An empty file produces no output — `less` shows an empty screen.

**Error state:** On rendering errors for UTF-8 files, raw file content is printed to stdout so `less` shows the unformatted file. For non-UTF-8/binary files, richless exits with no output so `less` handles the file natively. Errors are printed to stderr (visible after exiting `less`).

## 8. Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| File not found | Print error to stderr, exit with code 1 |
| Binary / non-UTF-8 file | Attempt to read as UTF-8; on decode error, exit cleanly with no output so `less` handles the file directly via its normal path |
| Empty file | Render produces no output; `less` shows empty screen |
| Very large file | No special handling — rich renders the full file. May be slow for very large files. |
| No terminal (e.g., cron) | `get_terminal_width()` falls back to `shutil.get_terminal_size()` which defaults to 80 columns |
| File with no extension | Content detection via `detect_syntax_from_content()` attempts to identify type; falls back to plain text |
| Temp file from shell wrapper | Files named `richless.*` trigger content detection instead of extension-based detection |
| Piped input with `--md` flag | Shell wrapper forces Markdown rendering via `richless --md` |
| Piped input without `--md` | Shell wrapper runs auto-detection heuristics (YAML/JSON → syntax; markdown patterns → render; otherwise → plain) |
| Filename contains `-m` | Shell wrapper uses `case` exact matching so `-m` in filenames (e.g., `test-mcp-config.yaml`) does not trigger the `--md` flag |
| `richless` command not found | `richless-init.sh` prints a warning to stderr and returns/exits with code 1 |

### Known Issues
- **Zeek JSONL logs:** Files in Zeek's JSONL format (e.g., `conn.log`) do not get syntax highlighting. Additionally, piping through `jq` and into `less` (`cat conn.log | jq | less`) shows a blank screen.

## 9. Testing Strategy

### Test Framework
- **pytest** (>= 7.0.0), run via `uv run pytest tests/test_richless.py -v`

### Test Categories

| Category | What to Test | Approach |
|---|---|---|
| **Unit tests** | `is_markdown_file()`, `detect_syntax_from_content()`, `get_terminal_width()` | Direct function calls with assertions |
| **Snapshot tests** *(planned, not yet implemented)* | Markdown rendering output for known input files | Render to string via `Console(record=True)`, compare against golden files stored in `tests/fixtures/` |
| **Assertion-based rendering tests** | Syntax highlighting produces ANSI escape codes for each supported format | Render file, assert ANSI color codes are present and markdown box-drawing characters are absent (or vice versa) |
| **Integration tests** | `richless` CLI invoked as subprocess with various file types | `subprocess.run()` with fixture files, check stdout for expected formatting |
| **LESSOPEN integration tests** | End-to-end with `less` using `LESSOPEN` env var | `subprocess.run()` with `less -R` and custom `LESSOPEN`, verify output |
| **Piped input simulation** | Content detection and rendering for piped input scenarios | Replicate shell wrapper logic in Python, verify correct detection and rendering |
| **Edge case tests** | Empty files, binary files, files with no extension, temp file naming, filenames with `-m` | Targeted tests for each scenario in the error handling table |

### Code Quality Tools

| Tool | Purpose | Configuration |
|---|---|---|
| **ruff** | Linting and formatting | `[tool.ruff]` section in `pyproject.toml` |
| **mypy** | Static type checking | `[tool.mypy]` section in `pyproject.toml` |

### Running Tests
```bash
# Run all tests
uv run pytest tests/test_richless.py -v

# Run with coverage (future)
uv run pytest tests/test_richless.py -v --cov=richless

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy richless.py
```

## 10. MVP Scope & Future Considerations

### MVP (Current — v0.2.x)
- Markdown rendering for `.md` / `.markdown` files
- Syntax highlighting for all Pygments-supported languages
- Data format highlighting for JSON, JSONL, YAML, XML
- Content detection for extensionless files and piped input
- Shell wrapper with piped input support, auto-detection, and `--md` flag
- sh/bash/zsh compatibility
- Dynamic terminal width for Markdown rendering
- Horizontal scroll support for syntax-highlighted code
- Homebrew and PyPI distribution
- Silent fallback to raw content on errors
- Test suite with unit, integration, and LESSOPEN tests
- ruff linting/formatting and mypy type checking

### Future Enhancements

| Enhancement | Description | Priority |
|---|---|---|
| **Remove `-m` short flag** | Remove `-m` as a short form for `--md` in the shell wrapper — it conflicts with `less`'s built-in `-m` flag (verbose prompt). This is a breaking change for users who relied on `-m`. | High |
| **Fix binary/non-UTF-8 file handling** | When a file cannot be decoded as UTF-8, richless should exit cleanly with no output so `less` handles the file natively. Currently the fallback path also tries UTF-8 and fails. | High |
| **Fix Zeek JSONL handling** | Investigate and fix syntax highlighting for Zeek-format JSONL logs and blank screen when piping through `jq` | High |
| **Add signal trap for temp file cleanup** | Add `trap` on EXIT/INT/TERM in the shell wrapper to clean up temp files when user presses Ctrl+C or the process is killed | High |
| **Fix `LESS` env var handling** | If the user has a custom `LESS` variable that doesn't include `-R`, ANSI colors won't render. The init script should append `-R` if not already present, rather than only setting it when `LESS` is unset. | Medium |
| **Fix multi-file behavior with `--md`** | `less --md file1.txt file2.txt` currently opens each file in a separate `less` instance, losing `:n`/`:p` multi-file navigation. Should concatenate into a single `less` invocation. | Medium |
| **Debug logging** | Implement `RICHLESS_DEBUG=1` environment variable to log rendering failures to `~/.richless/debug.log` | Medium |
| **Git diff markers** | Show git change indicators (added/modified/deleted lines) in the gutter, similar to `bat` | Medium |
| **Snapshot test suite** | Add golden-file snapshot tests for Markdown rendering to catch visual regressions | Medium |
| **Theming / configuration** | Allow users to customize color themes, toggle line numbers, or set other rendering preferences. Requires design work on configuration format and scope. | Low |
| **Fish shell integration** | `richless-init.fish` for Fish shell users | Low |
| **Nushell integration** | Shell integration for Nushell | Low |
| **Test coverage reporting** | Add pytest-cov and coverage thresholds | Low |

### Architectural Constraints for Future Work
- richless must remain a single Python module (`richless.py`) unless complexity clearly demands a package structure. Simplicity is a core value.
- The shell wrapper must remain compatible with sh, bash, and zsh. New shell integrations should be separate files.
- Any configuration system must be optional — richless must work with zero configuration.
- Future features must not increase startup latency noticeably.
