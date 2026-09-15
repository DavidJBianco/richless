# Workflow and compatibility audit

The historical baseline and architecture experiments are preserved under `results/`
and described in `REPORT.md` and `INCREMENTAL_MARKDOWN.md`. Production behavior has
since been redesigned; deterministic correctness cases now run by default and are
required to pass. Their expectations reflect the approved 0.4.0 contracts.

All regression tests and the PTY harness live in `tests/test_richless.py`. Keep new
results in separately named directories; never overwrite the historical baseline.

## Run

From the repository root, with `less` installed:

```sh
uv run --frozen --extra dev pytest tests/test_richless.py -v
RICHLESS_AUDIT_DIR="$PWD/audit/results/local" \
  uv run --frozen --extra dev pytest tests/test_richless.py -k test_audit -v \
  --tb=short --junitxml=audit/results/local/junit.xml
```

Use a fresh output directory per baseline run. Focused reruns may share that directory; the ledger selects the latest record for each scenario ID. Nonzero pytest status blocks promotion when the
implementation violates the approved contract. Every scenario writes its
checks, exact commands, isolated environment, observations, and PTY transcript to
JSON even on assertion failure. Captured commands retain stdout/stderr separately;
PTY transcripts necessarily combine terminal-bound stdout/stderr. Fixture paths
are temporary: regenerate inputs by rerunning the scenario ID, rather than trying
to execute a saved command after pytest cleans its fixtures.

After baseline classification, run isolated probes and measurements:

```sh
RICHLESS_AUDIT_DIR="$PWD/audit/results/probes" RICHLESS_AUDIT_PROBES=1 \
  uv run --frozen --extra dev pytest tests/test_richless.py -k test_audit_probe -v
RICHLESS_AUDIT_DIR="$PWD/audit/results/performance" RICHLESS_AUDIT_PERFORMANCE=1 \
  uv run --frozen --extra dev pytest tests/test_richless.py -k test_audit_performance -v
uv run python audit/summarize.py audit/results/local
```

If the host restricts the usual uv cache, set `UV_CACHE_DIR` to a writable temporary
location. Correctness cases run without this variable; it selects a durable evidence directory.
Performance cases and historical architecture probes remain opt-in.

## Matrix and oracles

Repeat baseline commands on macOS and Linux with bash, zsh, and `/bin/sh` installed,
using Python 3.12 and 3.13. Missing shells become blocked ledger entries. `/bin/sh`
on macOS does not establish dash coverage. Performance runs use bash and the host
Python only. Record each OS/Python combination in a separate directory.

- `routes`, `mixed`, `arguments`, and `stream`: all three shells and integration paths.
- `formats`: named-file filter, actual bash wrapper pipeline, direct CLI.
- `integrity`: exact non-Markdown bytes after removing SGR colors; deviations such
  as tab expansion and added newlines are reported, then assessed for user impact.
- `mixed`: real glob expansion and explicit orders, fresh output on forward and
  backward visits, per-file identity and styling. `forced` uses native `less` as
  a navigation control, direct `LESSOPEN='|richless --md %s'` as a filter control,
  and the actual `less --md` wrapper.
- `mixed_obstacle`: empty, binary, and unreadable members between Markdown and Python.
- `environment`, `interaction`, `follow_file`, `fifo`, `failures`, and
  `python_render_failure`: targeted combinations instead of a Cartesian product.
- `probe`: three isolated hypotheses, enabled only after baseline review. The
  incremental JSON probe uses the native stdin-enabled `LESSOPEN=|-… %s` form,
  then measures first display and early quit on the baseline 166,000-line workload.
- `performance`: three repetitions per path/size; first display and end reached in
  the actual pager, resource usage from `wait4`. This is not aggregate process-tree
  peak memory. The safety deadlines detect hangs, not performance acceptability.

Input markers and expected rendering categories are declared before execution.
Plain less is an interaction control, not the rendering oracle. ANSI stripping is
used for content matching, not as a terminal screen emulator. Changes in cell
positions, exact color-state reset, and Markdown reflow require additional visual
or terminal-emulator coverage; they must not be inferred from marker checks.

The environment fixes terminal encoding and dimensions, disables history, uses a
fresh HOME/TMPDIR, and installs a temporary executable pointing at this checkout's
renderer. No installed `richless` is trusted. The PTY gives the pager a controlling
terminal even when stdin is a pipe. Sessions have bounded waits, process-group
cleanup, and transcript retention; terminal restoration is checked before cleanup.
Harness cleanup is separate from product cleanup assertions.

## Ledger and interpretation

Scenario IDs are pytest parameterized test names. `summarize.py` generates
`ledger.md` and `summary.json` from the JSON records. Statuses are pass, fail,
blocked, and needs product decision. A skipped optional probe is not a passed
probe. Review failures against the plain control before assigning a product defect.
See `REPORT.md` for actual findings, resource measurements, explicit coverage gaps,
and the architectural recommendation.

## Linux containers and recorded results

`sh audit/run-linux.sh 3.12` and `sh audit/run-linux.sh 3.13` build disposable
Debian Bookworm audit environments using Docker. They install less/bash/zsh, run
as a non-root user, mount only the required source files read-only, and write to
`audit/results/linux-<version>`. The host's checkout and `.venv` are not modified.
The optional second argument is a pytest `-k` selection for a focused rerun.
The base image tag is not an immutable dependency pin; the ledger records the
actual Python, less, shell, and locked package versions used.

The retained evidence includes initial full-run JUnit files and focused reruns
that strengthened color checks (foreground colors only) and added a filename
collision scenario. The generated ledger is the authoritative latest result per
scenario, rather than the counts from any single JUnit file. JSON artifact names
now include an ID hash so `.py` and `.PY` cases cannot overwrite each other on a
case-insensitive host filesystem, including a Docker bind mount. Older artifact
names are retained as history; the summarizer deduplicates by ID and timestamp.

Timing resolution is approximately 50 ms for observed first display, plus the
harness's command synchronization overhead for end-of-file observations. These
are observed interactive latencies, not profiler measurements of renderer CPU
time. Small-input cases were repeated after other audit work stopped; their latest
ranges are retained. Treat measurements as exploratory desktop observations, not
an isolated-machine certification of the PRD target.

For example, reproduce the whitespace-collision finding alone:

```sh
RICHLESS_AUDIT_DIR=/tmp/richless-repro \
  uv run --frozen --extra dev pytest \
  'tests/test_richless.py::test_audit_arguments[whitespace-collision-filter-bash]' -v
```

This intentionally fails against the audited implementation, regenerating the
correctly named file and its unpadded neighbor in a fresh temporary directory.
