# Project instructions

## Branches and releases

- Never work directly on `main`.
- Create feature and bug-fix branches from `dev`. Keep the current redesign on
  `codex/incremental-markdown-investigation` until all required checks pass.
- Documentation fixes and trivial changes may be made directly on `dev`.
- Promoting `dev` to `main` is a release: update the SemVer version in
  `pyproject.toml`, pass local tests and GitHub CI, and publish only the validated
  revision. Keep the repository owner's override available for required checks.
- Preserve unrelated working-tree changes. Do not hide correctness failures with
  expected-failure markers or skips merely to make CI green.

## Architecture and behavior

- Retain native `less` for terminal ownership, navigation, search, and file identity.
- Keep production logic in `richless.py`; do not create a package structure without
  a demonstrated need. Prefer module-level functions; use classes only when needed.
- `richless-init.sh` is a sh/bash/zsh-compatible argument-preserving shim. Detection
  and option handling belong in Python. Do not duplicate detection in shell/tests.
- Preserve existing CLI and integration-script entry points.
- Ordinary rendering uses progressive LESSOPEN output, without replacement files.
  Only explicit startup `+F` on rendered named files uses temporary replacements.
- Plain files use native access. Piped input must appear before EOF, without a
  complete disk spool. Unsupported streaming lexical state falls back to raw input.
- Preserve source bytes apart from inserted ANSI: tabs, CRLF, invalid UTF-8,
  existing ANSI, and missing final newlines must not be lost or normalized.
- Markdown intentionally transforms presentation. Parse finite documents once;
  retain context while publishing blocks. Live pending content is limited to five
  seconds or 1 MiB, followed by raw continuation without repeating committed input.
- Use forced-terminal Rich consoles where rendering ANSI. Never use Rich Syntax's
  padding/layout behavior for byte-preserving source highlighting.
- Keep diagnostics on stderr. Prepare rendering units transactionally before
  publication. Rendering failure must preserve the uncommitted raw input whenever
  recovery is possible; report unrecoverable failures with nonzero status.
- Own and clean up renderer processes and temporary follow files. Do not terminate
  unrelated producers or change the user's persistent shell environment.
- No persistent application state or mandatory configuration files. Progress
  indicators and new shell families are deferred.

## Tools and style

- Use `uv` for dependency operations and Python tools, never standalone pip.
- Runtime dependencies belong in `[project.dependencies]`; development tools in
  `[project.optional-dependencies].dev`. Keep the lockfile synchronized.
- Use type hints on all production function signatures and imperative docstrings
  on public functions. Use standard-library, third-party, then local import order.
- Run `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy richless.py`, and `uv run pytest tests/ -q` before committing.
- Build with `uv build`; verify installed distributions include the shell shim.
- Rich token integration uses an internal extension point: constrain dependencies
  and run rendering-equivalence tests when changing dependency versions.

## Tests and evidence

- Keep tests in `tests/test_richless.py`; use small deterministic fixtures.
- Exercise the real CLI, filter, and sourced wrapper through real shells. Use PTYs
  for interactive behavior and captured bytes for content integrity.
- Synchronize on observable output with bounded deadlines. Keep stdout, stderr,
  exit status, transcripts, and resolved environment versions separate.
- Mandatory coverage includes macOS/Linux, Python 3.12/3.13, bash/zsh/platform sh.
  Missing environments are gaps, not passes. Benchmarks/probes may be opt-in;
  ordinary correctness checks must run by default.
- Preserve historical audit results. Put new evidence in separately named paths.
- Homebrew formula changes live in DavidJBianco/homebrew-tools. Prepare upgrade
  caveats from `packaging/homebrew-caveats.txt`; use the validated release artifact
  and dependencies when updating the formula.

## Persistent task tracking

- Read TODO.md at the start of every session.
- Record tasks before starting work and update them immediately as status changes.
- Use `- [ ]`, `- [ ] **IN PROGRESS**`, and `- [x]` under phase headings.
- Never delete completed items during a session. Keep enough detail for another
  session to resume interrupted work accurately.
