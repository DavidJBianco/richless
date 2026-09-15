# 0.4.0 redesign validation

## Outcome

The native-pager integration can support the required workflows without building
another pager. Ordinary views stream through stdin-enabled LESSOPEN; only rendered
named files in explicit startup `+F` sessions allocate replacement files. Native
less retains file identity, navigation, search, and terminal ownership.

This report supplements the historical [audit](REPORT.md); it does not replace or
reinterpret the baseline results. The historical decision observations have become
explicit assertions for the agreed 0.4 contracts in the required regression suite.

## Implemented contracts

- One argument-preserving Python launcher and a sh/bash/zsh shim. No shell detection
  cascade or stdin spool. Existing renderer CLI and LESSOPEN entry points remain.
- Conservative detection, exact original source bytes around inserted ANSI, safe
  raw continuation when a live lexer cannot retain its state.
- Finite Markdown parses once for references and publishes complete rendered
  blocks. Live blocks retain context, with five-second/1 MiB unresolved-source
  limits and transactional raw recovery.
- Follow replacements are private, lazy, supervised, and released on file close
  or session end. Allocation and prepublication write failures recover native
  viewing; postpublication failures report stopped following and nonzero status.
- Descriptor and pathname following, truncation/reload, mixed stdin/FIFO sessions,
  backward navigation, active-producer quit, and SIGTERM/SIGHUP cleanup are tested.
- Wheel and sdist include the shim. Installation tests cover old loaded wrappers,
  replacing copied scripts, both direct Markdown aliases, and matching rollback.

## Performance: macOS, Python 3.12, native less 668

Final release refresh: 11 scenarios passed, with [retained measurements](results/redesign/release-performance/ledger.md).
Three trials per case, using the same deterministic log records as the baseline.
First display is terminal-observable useful content; completion means reaching the
end with `G`. These are measurements, not CI timing gates.

| JSONL records | Route | First display | End reached |
|---:|---|---:|---:|
| 100 | file | 0.175–0.412 s | 0.266–0.495 s |
| 100 | pipeline | 0.171–0.340 s | 0.262–0.431 s |
| 10,000 | file | 0.167–0.284 s | 0.673–0.771 s |
| 10,000 | pipeline | 0.107–0.278 s | 0.493–0.657 s |
| 166,000 | file | 0.166–0.357 s | 7.266–7.635 s |
| 166,000 | pipeline | 0.103–0.264 s | 5.647–5.826 s |
| 500,000 | file | 0.236–0.407 s | 22.143–22.201 s |
| 500,000 | pipeline | 0.101–0.342 s | 16.740–16.998 s |

Large Markdown (10,000 paragraphs, roughly 330 KiB) first displayed in 0.356–0.631 s,
reached the end in 1.074–1.348 s, and quit in 0.041–0.068 s. An unfinished live
1 MiB fenced block switched to raw, displayed in 0.164–0.337 s, and quit in
0.042–0.066 s. Follow appends completed in 0.531–0.674 s from session launch;
quitting took 0.187–0.197 s.

**The under-300-ms target is not universally met.** Cold log runs reached 412 ms;
large finite Markdown must read and parse before publication. This is substantially
better than the former tens-of-seconds blank screen. Progress feedback remains
deferred as agreed.

Completed-log throughput was about 21,000–22,000 records/s for named files and
28,000–30,000 records/s for pipelines in these measurements.

Memory remains material: `wait4` child resource accounting peaked at about 632 MiB
for a completed 500,000-record view, versus about 71 MiB for large Markdown. This
is not aggregate simultaneous process-tree RSS. Native less retains viewing
history, and finite syntax currently retains its source snapshot for lexer state.
No bounded-memory claim is made for an entire indefinitely growing pager session.

Follow storage grew from 9,800 to 2,409,948 bytes for a 261,269-byte source in the
recorded case (ANSI expansion is substantial). Tests verify cleanup; storage is
not bounded for an indefinitely growing rendered file.

## Release-gate interruption repair

A later promotion run exposed intermittent SIGINT failures on both hosted macOS
Python versions. The supervisor caught KeyboardInterrupt only around `wait()`;
interrupts at the loop boundary or inside timeout handling escaped and destroyed
the session. [Saved failure transcripts and a deterministic before/after test](results/redesign/interruption-race/)
confirm the cause. A session-wide callable SIGINT handler now leaves terminal
interrupt ownership with native less while keeping its supervisor alive. No
required behavior was dropped and no failure was hidden by a retry.

The same failure-path review added complete handling of short output writes:
finish the unit or report that output stopped accepting bytes. Tests cover both
successful partial writes and an output that stops after a prefix. The current
four-environment local matrix includes these regressions (479 passes each).
[Release PR checks](https://github.com/DavidJBianco/richless/pull/9/checks) track the
final hosted validation and promotion; initial feature CI alone is insufficient.

## Correctness results

| Platform | Python | Required tests |
|---|---|---:|
| macOS 26.6.2 arm64 / less 668 | 3.12.9 | 479 passed |
| macOS 26.6.2 arm64 / less 668 | 3.13.15 | 479 passed |
| Debian Linux container / less 590 | 3.12 | 479 passed |
| Debian Linux container / less 590 | 3.13 | 479 passed |

Each run exercises bash, zsh, and `/bin/sh`. Ruff, formatting, mypy, wheel/sdist
builds, and installed upgrade/rollback checks also pass. The 27 optional current
performance cases passed separately (three measurements each). Historical probes
remain preserved rather than being mistaken for current correctness gates.

[Raw records and per-platform ledgers](results/redesign/) retain environment
versions, production-file hashes, commands, terminal transcripts, and outcomes.
The ledger’s blocked optional cases correspond to excluded measurements/probes,
not hidden correctness failures. Unit tests without PTY sessions are counted in
the test logs, not duplicated as terminal scenario records.

## Evidence and release record

Platform correctness runs exercise bash, zsh, and platform `/bin/sh` on macOS and
actual Debian Linux containers, with Python 3.12 and 3.13. Containers run under
Docker on the Mac; they are Linux userspace/kernel environments, not claims of
native Linux hardware performance. Linux timing comparisons are not repeated.

The required suite excludes only explicitly optional historical probes and noisy
performance measurements. No known correctness failure is converted to xfail.
Follow resource exhaustion is injected at actual allocation/write boundaries;
these tests do not fill the host disk. Sudden SIGKILL cannot guarantee filesystem
cleanup and is outside the supported graceful-termination contract.

Feature revision `0cbc9aa` passed all four hosted correctness jobs and the quality /
installed-distribution job in [GitHub CI](https://github.com/DavidJBianco/richless/actions/runs/35012771548).
The first packaging run exposed a missing zsh installation in that separate job;
installing all three supported shells resolved it. PR #8 merged into dev only after
the aggregate required check passed. The final release validation passed all jobs in
[the publication run](https://github.com/DavidJBianco/richless/actions/runs/35019015462).
The immutable `v0.4.0` tag identifies `6a115092dc2c6b65e1cdbb2da386e500df9636dd`.
A subsequent workflow-only repair added current metadata validation and an exact-tag
publication retry; it did not move the tag or change application code.

PyPI wheel SHA-256: `4dbeb00d4eeee3046b04ef60f4fd7bef79e1a5efe0885fb71510ca178b73d248`.
PyPI source SHA-256: `f3402d1080bc6fcddf4ac2a013cbae9876b3ec7025644bc1339d9747de6d05b5`.
The downloaded wheel matches the local build byte-for-byte. Source archive contents
match except that the local build included unrelated untracked `.claude` worktree
files; the published archive correctly excludes them. Published artifacts are the
release downloads. Future release builds should continue using clean CI checkouts.

[Homebrew PR #1](https://github.com/DavidJBianco/homebrew-tools/pull/1) updates the
formula, tested dependency pins, generator tests, and upgrade caveats. Three generator
tests, Ruby syntax, and published/locked source checksums pass. A global Homebrew
installation was not performed; isolated distribution and upgrade tests passed.
The finished formula is also retained in `packaging/richless.rb`.
