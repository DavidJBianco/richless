# TODO

## Release record promotion

- [x] Prepare promotion of the final 0.4.0 report, performance evidence, and formula record in PR #13: https://github.com/DavidJBianco/richless/pull/13 . Merge is gated on required GitHub CI; consult the PR for its authoritative check/merge status. Application code/version and the published tag remain unchanged.

## 0.4.0 Integration Redesign

- [x] Validate explicit +F replacement-file transport against native less on all platforms. Native transport and actual integration gates pass on macOS and Linux. Final local matrix passes 479 required tests in each macOS/Linux × Python 3.12/3.13 environment, including all three shells.
- [x] Implement centralized pager argument handling and an idempotent shell shim; preserve old CLI/template entry points. Explicit format options, native operands, exact paths, and mixed sessions have targeted passing checks.
- [x] Implement byte-preserving progressive syntax and finite/live Markdown rendering with transactional fallback (5 seconds / 1 MiB pending limit). Finite/live Markdown match 25 reference examples at two widths; formatter-failure and byte-integrity checks pass. Bounded unfinished-input and repeated performance checks also pass.
- [x] Implement supervised replacement files only for explicitly requested formatted named-file following, including ready-before-publication handshakes, file-close cleanup, and inherited streaming pipes for mixed stdin/FIFO sessions. Allocation/write failure, early quit, mixed FIFO input, and SIGTERM/SIGHUP cleanup checks pass.
- [x] Promote audit contracts into required tests. Final local platform runs passed 479 correctness cases per environment. Installed wheel/sdist, old wrappers, copied scripts, and matched rollback checks pass; allocation/write failures, SIGTERM/SIGHUP cleanup, and mixed FIFO follow have passing tests.
- [x] Configure Ruff, mypy, builds, installed upgrade/rollback tests, and GitHub CI. Feature revision 0cbc9aa passed every required job: https://github.com/DavidJBianco/richless/actions/runs/35012771548 . PR #8 merged into dev after green CI.
- [x] Configure required checks on main/dev with owner override. Preserve documentation/trivial work directly on dev and feature/fix branching from dev.
- [x] Complete local/platform checks (479 passes × four environments), 27 repeated performance cases, and installation validation. Record results in audit/REDESIGN.md and audit/results/redesign.
- [x] Fix the release-gate SIGINT race: CI transcripts show KeyboardInterrupt landing outside the supervisor wait try-block, terminating the pager and leaving a traceback. A deterministic loop-boundary test fails before and passes after the session-wide signal handler. Final local matrix passes 479 tests in all four environments; hosted revalidation and publication passed. Short-write completion/failure checks also pass.
- [x] Promote the documented 0.4.0 release through dev-to-main checks and create the immutable release tag. The immutable tag v0.4.0 resolves to 6a115092dc2c6b65e1cdbb2da386e500df9636dd. Release tests all passed, but the old publisher rejected metadata 2.5 before upload; publication subsequently succeeded as recorded below.
- [x] Fix release publication without moving v0.4.0: pin the current official publisher (Twine 7 / packaging 26.2), add metadata validation to quality CI, and support manual publication of an immutable tag after testing that exact revision. Local Twine 7 validation accepts both built artifacts. Exact-tag publication succeeded in run 35019015462; PyPI artifacts verified and Homebrew PR #1 merged. GitHub release uses those published artifacts.

- [x] Retain final performance refresh: 11 scenarios × three trials; report latency ranges, memory/storage costs, and the remaining 300-ms target gap. Preserve earlier comparisons separately.

## Incremental Markdown Investigation

- [x] Create local dev from main and investigate on codex/incremental-markdown-investigation, preserving uncommitted audit work.
- [x] Test Markdown block boundaries, future references, list/table/code context, rendering equivalence, and live display through native LESSOPEN; 50/50 fixture comparisons match, four PTY scenarios meet expectations, and finite-document progressive output improves first-line latency. Record feasibility, quadratic suffix-parsing limits, and coverage gaps in audit/INCREMENTAL_MARKDOWN.md; production rendering remains unchanged.
- [x] Approve the redesign plan: direct ordinary output, temporary replacements only for explicit +F rendered named files, five-second/1 MiB live Markdown fallback, upgrade compatibility, release rules, and mandatory local/CI audit coverage. Progress feedback remains deferred.

## Workflow and Compatibility Audit

- [x] Build reusable baseline audit cases and a real-terminal harness without changing production behavior.
- [x] Finish platform/shell comparisons and performance measurements: 335 baseline cases in each of four macOS/Debian and Python 3.12/3.13 environments; all share 231 passes, 99 failures, and 5 policy observations. Retain transcripts and ledgers in audit/results. Separately run 24 performance cases (21 complete, 3 censored at the 45-second deadline).
- [x] Conduct three isolated probes of incremental JSON display, forced-Markdown multi-file semantics, and the empty/partial-output fallback boundary; all three hypotheses demonstrated with limitations recorded.
- [x] Extend the native stdin-enabled LESSOPEN incremental probe to the same 166,000-line JSONL benchmark: first highlighted display about 0.11 s versus 30–31 s currently. Assess meaningful waiting/progress feedback and its unvalidated terminal-ownership requirements in the report; production behavior remains unchanged.
- [x] Finalize audit/REPORT.md and generated ledgers with reproducible findings, remediation estimates, performance measurements, and coverage limits. Recommend retaining less while redesigning integration/rendering. Existing 85 tests pass; audit remains opt-in.

## Project Orientation

- [x] Review requirements, implementation, and known issues; summarize the project's goals, motivation, and architecture for the owner.

## Bugs & Fixes (High Priority)

- [x] Pin GitHub Actions to immutable commit SHAs in CI/publish workflows to mitigate supply-chain risk
- [x] Stabilize test environment by ensuring `less` is available and test subprocesses run with ANSI color enabled
- [x] Add syntax width clamp and raw fallback for extremely long lines to prevent local DoS while preserving usability
- [x] Re-run security validation with real `less` now that internet access is enabled
- [x] Fix LESSOPEN command injection risk for unsafe filenames in shell wrapper -- relies on `less`'s built-in `LESSMETACHARS`/`LESSMETAESCAPE` shell-escaping of `%s` (verified injection-safe); the earlier custom filename guard was redundant and broke rendering for names with spaces, so it was removed
- [x] Remove `-m` short flag from shell wrapper -- conflicts with `less`'s built-in `-m` (verbose prompt)
- [x] Preserve binary/non-UTF-8 bytes in direct rendering and return native-file fallback from LESSOPEN when no transformation is appropriate.
- [x] Fix Zeek JSONL log handling -- `.log` files now fall back to content detection for syntax highlighting
- [x] Replace large-file blank-screen buffering. Repeated 166K log first display is 0.103–0.357 s; 500K first display is 0.101–0.407 s in the final refresh. Large finite Markdown still exceeds 300 ms; record this separately from correctness.
- [x] Replace shell temp-file ownership with Python session supervision and tested SIGTERM/SIGHUP cleanup.

## Bugs & Fixes (Medium Priority)

- [x] Apply default ANSI handling only to the launched pager, preserving existing LESS settings and explicit color overrides.
- [x] Fix multi-file behavior with `--md` -- currently opens each file in separate `less` instance, losing `:n`/`:p` navigation

## Tooling & Quality

- [x] Add ruff configuration to `pyproject.toml` and fix any lint issues
- [x] Add mypy configuration to `pyproject.toml` and fix any type errors
- [ ] Add `.yml` test fixture and verify Pygments handles it correctly

## Future Enhancements

- [ ] Implement `RICHLESS_DEBUG=1` env var for debug logging to `~/.richless/debug.log`
- [ ] Git diff markers in the gutter (similar to `bat`)
- [ ] Snapshot/golden-file tests for Markdown rendering
- [ ] Theming / user configuration (requires design work)
- [ ] Fish shell integration (`richless-init.fish`)
- [ ] Nushell shell integration
- [ ] Test coverage reporting (pytest-cov)
