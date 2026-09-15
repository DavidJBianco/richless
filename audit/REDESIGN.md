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

Three trials per case, using the same deterministic log records as the baseline.
First display is terminal-observable useful content; completion means reaching the
end with `G`. These are measurements, not CI timing gates.

| JSONL records | Route | First display | End reached |
|---:|---|---:|---:|
| 100 | file | 0.154–0.300 s | 0.242–0.383 s |
| 100 | pipeline | 0.109–0.286 s | 0.198–0.375 s |
| 10,000 | file | 0.171–0.286 s | 0.655–0.825 s |
| 10,000 | pipeline | 0.151–0.282 s | 0.520–0.653 s |
| 166,000 | file | 0.162–0.281 s | 7.560–7.687 s |
| 166,000 | pipeline | 0.107–0.297 s | 5.618–5.726 s |
| 500,000 | file | 0.234–0.345 s | 22.821–23.627 s |
| 500,000 | pipeline | 0.113–0.345 s | 15.440–16.420 s |

Large Markdown (10,000 paragraphs, roughly 330 KiB) first displayed in 0.423–0.655 s,
reached the end in 1.107–1.352 s, and quit in 0.045–0.067 s. An unfinished live
1 MiB fenced block switched to raw, displayed in 0.220–0.332 s, and quit in
0.037–0.049 s. Follow appends completed in 0.518–0.638 s from session launch;
quitting took 0.185–0.192 s.

**The under-300-ms target is not universally met.** Cold log runs reached 345 ms;
large finite Markdown must read and parse before publication. This is substantially
better than the former tens-of-seconds blank screen. Progress feedback remains
deferred as agreed.

Memory remains material: `wait4` child resource accounting peaked at about 632 MiB
for a completed 500,000-record view, versus about 71 MiB for large Markdown. This
is not aggregate simultaneous process-tree RSS. Native less retains viewing
history, and finite syntax currently retains its source snapshot for lexer state.
No bounded-memory claim is made for an entire indefinitely growing pager session.

Follow storage grew from 9,800 to 2,409,948 bytes for a 261,269-byte source in the
recorded case (ANSI expansion is substantial). Tests verify cleanup; storage is
not bounded for an indefinitely growing rendered file.

## Correctness results

| Platform | Python | Required tests |
|---|---|---:|
| macOS 26.6.2 arm64 / less 668 | 3.12.9 | 476 passed |
| macOS 26.6.2 arm64 / less 668 | 3.13.15 | 476 passed |
| Debian Linux container / less 590 | 3.12 | 476 passed |
| Debian Linux container / less 590 | 3.13 | 476 passed |

Each run exercises bash, zsh, and `/bin/sh`. Ruff, formatting, mypy, wheel/sdist
builds, and installed upgrade/rollback checks also pass. The 27 optional current
performance cases passed separately (three measurements each). Historical probes
remain preserved rather than being mistaken for current correctness gates.

[Raw records and per-platform ledgers](results/redesign/) retain environment
versions, production-file hashes, commands, terminal transcripts, and outcomes.
The ledger’s blocked optional cases correspond to excluded measurements/probes,
not hidden correctness failures. Unit tests without PTY sessions are counted in
the test logs, not duplicated as terminal scenario records.

## Evidence and remaining release work

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
the aggregate required check passed. Release promotion and Homebrew publication
remain separately gated. `packaging/richless.rb.in` pins tested runtime
resources and contains a deliberately unresolved release-sdist hash; it must never
be installed as a finished formula until the validated release artifact exists.
