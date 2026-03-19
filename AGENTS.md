# AGENTS.md

## Project Overview

richless is a LESSOPEN filter that transparently renders Markdown and syntax-highlights source code when viewing files with `less`. It consists of two components:

1. **`richless.py`** -- A single-module Python CLI that acts as the LESSOPEN preprocessor. It detects file types by extension or content and renders output using the `rich` library (Markdown) and Pygments (syntax highlighting).
2. **`richless-init.sh`** -- A POSIX-compatible shell wrapper around `less` that handles piped input, auto-detection of content type, and the `--md` flag to force Markdown rendering.

The full PRD is at `/PRD.md`. Refer to it for detailed requirements, workflows, and edge cases.

## Tech Stack

| Component            | Technology   | Version     |
|----------------------|-------------|-------------|
| Language             | Python       | >= 3.12     |
| Terminal rendering   | rich         | >= 13.8.0   |
| Syntax highlighting  | Pygments     | >= 2.0.0    |
| Build system         | hatchling    | latest      |
| Package manager      | uv           | latest      |
| Test framework       | pytest       | >= 7.0.0    |
| Linter & formatter   | ruff         | latest      |
| Type checker         | mypy         | latest      |
| Distribution         | Homebrew (DavidJBianco/tools tap), PyPI | -- |

## Project Structure

```
richless/
  richless.py              # ALL application logic lives here -- single module
  richless-init.sh         # Shell integration (sh/bash/zsh)
  pyproject.toml           # Project metadata, dependencies, build config, tool config
  LICENSE
  README.md
  PRD.md                   # Product requirements (dev only)
  AGENTS.md                # This file (dev only)
  TODO.md                  # Task tracking (dev only)
  tests/
    test_richless.py       # All tests -- unit, integration, and LESSOPEN
    fixtures/              # Test input files (Markdown, YAML, JSON, code, etc.)
      test.md
      test.yaml
      test-with-comments.yaml
      test-mcp-config.yaml
      test.json
      test.jsonl
      test.py
      test.sh
```

**Distributed files** (included in sdist/wheel): `richless.py`, `richless-init.sh`, `LICENSE`, `README.md`. Everything else is dev-only.

## Dependency Management

- Use `uv` for all dependency operations. Do not use `pip` directly.
- Runtime dependencies go in `[project.dependencies]` in `pyproject.toml`.
- Dev-only dependencies go in `[project.optional-dependencies] dev`.
- Install dev dependencies: `uv sync --extra dev`
- Add a runtime dependency: add it to the `dependencies` list in `pyproject.toml`, then `uv sync`.
- ruff and mypy should be configured via `[tool.ruff]` and `[tool.mypy]` sections in `pyproject.toml` (not yet configured -- add these when introducing those tools).

## Code Style & Standards

### Python (`richless.py`)

- **Type hints on all function signatures.** The codebase already uses them; maintain this.
- **Docstrings on all public functions.** Use imperative mood ("Check if the file..." not "Checks if the file...").
- **Formatting and linting:** ruff (being added). When configured, run `uv run ruff check .` and `uv run ruff format .` before committing.
- **Type checking:** mypy (being added). When configured, run `uv run mypy richless.py`.
- **Imports:** Standard library first, then third-party (`rich`, `pygments`), then local. No relative imports (single module, so there are none).
- **No classes.** The codebase uses module-level functions. Keep it that way unless complexity demands otherwise.
- **Error handling philosophy:** richless must never prevent the user from viewing a file. On any rendering error, fall back to printing raw content to stdout. Print errors to stderr only. See `main()` for the existing pattern.
- **Console creation:** Always use `Console(force_terminal=True, ...)` so ANSI output is produced even when stdout is piped (which it always is via LESSOPEN).
- **Width handling differs by render type:**
  - Markdown: use `get_terminal_width()` (adapts to terminal).
  - Syntax: use the longest line length (minimum 80) to enable horizontal scrolling in `less`.

### Shell (`richless-init.sh`)

- Must remain compatible with **sh, bash, and zsh**. No bashisms except inside `[ -n "$BASH_VERSION" ]` guards.
- Uses `local` keyword, which is a widely-supported non-POSIX extension that works in bash, zsh, dash, and common `/bin/sh` implementations.
- The `less()` function overrides the command; use `command less` when calling the real `less` binary.
- The shell wrapper and the Python CLI have **independent content detection implementations**. They use different pattern sets. Do not assume they are in sync -- changes to detection logic may need to be made in both places.

### General Principles

- **Simplicity is a core value.** richless must remain a single Python module (`richless.py`) unless complexity clearly demands a package structure. Resist the urge to split into multiple files.
- **Stateless.** No persistent data, no config files, no disk writes except temp files that are cleaned up immediately.
- **Zero configuration.** richless works out of the box with no config file. Any future configuration must be optional.
- **Graceful degradation.** If anything goes wrong, the user still sees the raw file in `less`.

## Configuration & Secrets

There are no secrets. There is no configuration file.

**Environment variables used:**

| Variable   | Purpose                                              | Default              |
|-----------|------------------------------------------------------|----------------------|
| `LESSOPEN` | Set by `richless-init.sh` to `\|richless %s`         | Not set              |
| `LESS`     | Set by `richless-init.sh` to include `-R` for ANSI   | Preserves if already set |
| `COLUMNS`  | Fallback for terminal width detection                 | Auto-detected        |

## Key Patterns

### Adding support for a new file extension

1. If the extension maps to a non-standard Pygments lexer name, add it to the `ext_map` dict in `render_syntax()`. Example: `'jsonl': 'json'`.
2. If Pygments already recognizes the extension, no code change is needed -- it will be auto-detected.
3. Add a test fixture in `tests/fixtures/` and add integration tests in `TestIntegration` and `TestLessOpenIntegration`.

### Adding content detection for a new format

1. Add detection logic to `detect_syntax_from_content()` in `richless.py`. Follow the existing priority order: specific markers first, then structural patterns, then fallback to "text".
2. If piped input should also be detected, add corresponding `grep` patterns to the detection cascade in `richless-init.sh`. Remember: the shell and Python detection logic are independent.
3. Add unit tests in `TestDetectSyntaxFromContent` and piped input tests in `TestPipedInputDetection`.

### Adding a new CLI flag

1. Add the argument to `argparse` in `main()`.
2. If the flag should also work with piped input via the shell wrapper, add handling in the `less()` function in `richless-init.sh`. The shell wrapper strips custom flags before passing remaining args to `command less`.
3. Add integration tests that exercise the flag via subprocess.

### Modifying rendering behavior

- Markdown rendering: modify `render_markdown()`. Uses `rich.markdown.Markdown`.
- Syntax highlighting: modify `render_syntax()`. Uses `rich.syntax.Syntax` with Monokai theme, no line numbers, default background.
- Both functions create their own `Console` instance with appropriate width settings.

## Testing

### Running Tests

```bash
# Run all tests (verbose)
uv run pytest tests/test_richless.py -v

# Run a specific test class
uv run pytest tests/test_richless.py::TestIntegration -v

# Run a single test
uv run pytest tests/test_richless.py::TestDetectSyntaxFromContent::test_yaml_document_start -v

# Lint and format (once ruff is configured)
uv run ruff check .
uv run ruff format .

# Type check (once mypy is configured)
uv run mypy richless.py
```

### Test Architecture

Tests live in a single file: `tests/test_richless.py`. Test categories:

| Class                       | Type        | What It Tests                                      |
|-----------------------------|-------------|---------------------------------------------------|
| `TestIsMarkdownFile`        | Unit        | `is_markdown_file()` with various extensions       |
| `TestDetectSyntaxFromContent` | Unit      | Content detection heuristics (YAML, JSON, shebangs, XML, plain text) |
| `TestIntegration`           | Integration | `richless` CLI as subprocess with fixture files    |
| `TestTempFileDetection`     | Integration | Content detection on temp files (simulates shell wrapper behavior) |
| `TestLessOpenIntegration`   | Integration | End-to-end with `less -R` and custom `LESSOPEN` env var |
| `TestPipedInputDetection`   | Integration | Replicates shell wrapper's piped input detection logic in Python |

### Writing Tests

- **Unit tests** import functions directly: `from richless import is_markdown_file, detect_syntax_from_content`
- **Integration tests** invoke `richless` as a subprocess via `subprocess.run()`. Use `capture_output=True, text=True`.
- **Fixture files** go in `tests/fixtures/`. Keep them minimal -- just enough content to trigger the detection/rendering path being tested.
- **Detecting ANSI output:** Use `re.search(r'\x1b\[\d+', output)` to check for ANSI color codes.
- **Detecting Markdown rendering:** Check for Rich box-drawing characters: `"┃", "┏", "┗", "━", "┓", "┛", "─", "•"`.
- **Temp files** in tests: use pytest's `tmp_path` fixture. Name temp files `richless.XXXXXX` to match the shell wrapper's naming convention, which triggers content detection instead of extension-based detection.

## Common Pitfalls

### Do

- Test both the Python CLI (`richless <file>`) and the LESSOPEN path (`less -R` with `LESSOPEN` env var) -- they exercise different code paths.
- Use `command less` (not bare `less`) inside `richless-init.sh` to call the real binary, not the wrapper recursively.
- Use `Console(force_terminal=True)` when creating Rich consoles -- stdout is always piped in LESSOPEN context.
- Keep shell wrapper detection patterns and Python detection patterns as two independent concerns. Update both when adding new format support.
- Run the full test suite before committing: `uv run pytest tests/test_richless.py -v`
- Use `uv run` to execute Python tools (pytest, ruff, mypy) so they run within the project's virtual environment.

### Do Not

- Do not split `richless.py` into a package with multiple modules unless complexity clearly demands it.
- Do not add configuration files (TOML, YAML, INI). richless is zero-config by design.
- Do not use `-m` as a short flag for `--md` -- it conflicts with `less`'s built-in `-m` flag. The existing `-m` handling in the shell wrapper must be removed (see TODO.md).
- Do not write to disk except for temp files that are cleaned up immediately.
- Do not block the user from viewing a file. If rendering fails, fall back to raw content.
- Do not use `pip install` -- use `uv` for all dependency management.
- Do not assume the shell wrapper and Python CLI share detection logic -- they have independent implementations.
- Do not add bashisms to `richless-init.sh` outside of `$BASH_VERSION` guards.

## Distribution

- **Homebrew:** Distributed via the `DavidJBianco/tools` tap. The formula is generated from `pyproject.toml` using `poet`. Changes to dependencies require regenerating the formula.
- **PyPI:** Standard Python package. Build with `uv build`, publish with `uv publish` (or twine).
- **Version:** Defined in `pyproject.toml` under `[project] version`. Bump it there for releases.

## Task Tracking with TODO.md

AI agents working on this project must use a `TODO.md` file for persistent task tracking:

- **Read `TODO.md` at the start of every session** to understand current project state
- **Write tasks to `TODO.md` before starting work** as a durable record alongside any in-session tracking
- **Update `TODO.md` immediately** when tasks are added, changed, completed, or removed
- Use markdown checkboxes for task status:
  - `- [ ]` for pending tasks
  - `- [ ] **IN PROGRESS**` for actively worked tasks
  - `- [x]` for completed tasks
- **Never delete completed items during a session** -- keep them checked off for visibility
- Treat `TODO.md` as the **recovery mechanism for interrupted sessions** -- the next agent must be able to pick up exactly where the last one left off
- Group tasks by feature area or phase
