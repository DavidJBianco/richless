# richless

View Markdown and syntax-highlighted source files in native `less`. Keep its search,
scrolling, filenames, and multi-file navigation while richless prepares the content.

Requires Python 3.12 or newer and `less`. Shell integration supports bash, zsh,
and the platform's `/bin/sh` (including dash on Linux).

## Install and enable

### Homebrew

```sh
brew install DavidJBianco/tools/richless
```

Add this line to your shell startup file (`~/.bashrc`, `~/.zshrc`, or `~/.profile`):

```sh
. "$(brew --prefix)/share/richless/richless-init.sh"
```

Open a new shell or run that line in the current shell.

### Python distribution

```sh
uv tool install richless
```

The package includes the integration script. Locate and source it with:

```sh
richless --init-path
. "$(richless --init-path)"
```

Add the source command to your shell startup file. If your installation uses a
virtual environment, its `richless` executable must be on PATH in that shell.

## Use

```sh
less README.md
less *.c *.py *.md
less --md notes.txt other.txt
less --syntax python extensionless-file
producer | less
producer | less --syntax json
less +F events.jsonl
less --follow-name +F events.jsonl
```

- `--md` / `--markdown` forces Markdown for every file in the session.
- `--syntax LANGUAGE` selects a Pygments language (`jsonl` is also supported).
- `-m` belongs to native `less` and controls its prompt.
- `--` ends option processing, including richless's options.
- Original argument boundaries, file order, and `:n`/`:p` navigation are retained.
- `command less ...` bypasses the wrapper and uses your original environment.

Recognized extensions take precedence over content detection. Detection without an
extension uses a bounded sample and conservative markers; ambiguous text stays
plain. Use `--syntax` or `--md` when you know the intended format.

## Progressive output and following

Ordinary rendered files are sent progressively through LESSOPEN without temporary
replacement files. Code highlighting adds ANSI styling without changing source
bytes, tabs, line endings, or the final newline. Existing ANSI/binary content is
passed through safely. Markdown intentionally changes presentation.

Finite Markdown files are parsed once to resolve references, then rendered blocks
are published progressively. The initial read and parse still precede first output.

Live Markdown publishes completed stable blocks. Unfinished constructs and possible
forward-reference links may wait for more input. After **five seconds or 1 MiB** of
pending source, the unresolved remainder and subsequent input are shown raw. Earlier
formatted blocks remain visible; source is not repeated. Literal brackets can cause
conservative waiting. Diagnostics go to stderr, never into the document.

Start with **`+F` for formatted following of a named file**. These sessions use
private temporary replacement files that grow as rendered content arrives and are
cleaned up when no longer needed. Long-running following can consume disk space.
Plain files are followed directly. By default following retains the opened file;
`--follow-name` selects pathname-based following across replacement.

If you open a rendered file normally and later press `F`, new changes to its source
will **not** appear. Quit and reopen with `+F`. Interactive following still works
for native plain files and continuing input pipelines.

The initial Markdown follow snapshot is rendered as a complete document. Appended
Markdown starts a live rendering generation; later text does not retroactively
change the published snapshot. Reload after truncation as required by your native
`less`. Automatic Markdown reflow after terminal resizing is not provided.

For live syntax whose cross-chunk lexer state cannot safely be retained, richless
continues with raw source. This preserves access and content integrity. JSON/JSONL
can be highlighted progressively across complete lines.

## Upgrade to 0.4.0

This release changes integration internally while preserving the `richless`
executable and `richless-init.sh` entry point.

- **Homebrew, stable source path:** new shells load the updated wrapper. Existing
  shells need to source the installed script again using the command above.
  If an older installation put a version-specific Cellar path in your startup
  file, replace that line with the stable source command above.
- **Copied integration script:** replace your copy with the file reported by
  `richless --init-path`, then re-source the copy. Do not keep sourcing an old
  version-specific installation directory.
- **Already-loaded old wrapper:** it can still call the new renderer, but retains
  its old buffering and argument-handling limitations until replaced/re-sourced.
- **Direct LESSOPEN users:** existing `|richless %s` templates remain usable.
  For current ordinary filtering, including stdin and leading-dash filenames, use
  `LESSOPEN='|-richless --filter -- %s'` together with `less -R`. Use the sourced
  wrapper for managed formatted following.
- **Intentional changes:** `-m` is no longer forced Markdown; use `--md`.
  Formatted file following requires startup `+F`. Ambiguous input may stay plain.
  Unresolved live Markdown may switch to source after the stated limit.

richless does not edit startup files automatically. When rolling back, restore the
matching older wrapper as well as the older executable, then start a new shell or
re-source that wrapper; an old executable does not implement the new pager mode.

The wrapper overrides existing preprocessing only for its own pager invocation.
It does not compose another LESSOPEN filter with richless or overwrite your shell's
LESS/LESSOPEN settings. It enables ANSI support by default; explicit native color settings in LESS and command-line
`less` options retain their usual precedence.

## Development

```sh
uv sync --extra dev
uv run pytest tests/ -q
uv run ruff check .
uv run ruff format --check .
uv run mypy richless.py
uv build
uv run python audit/verify-distributions.py
```

Correctness and compatibility tests run by default, including real terminal tests.
Set `RICHLESS_AUDIT_DIR` to retain evidence outside pytest's temporary directories.
Historical baseline reports and optional performance/probe instructions are under
`audit/`. Timing benchmarks are separate from ordinary CI gates.

Never develop on `main`. Features and fixes branch from `dev`; `dev` to `main` is a
versioned release requiring successful local and GitHub checks.
