# richless workflow audit: architectural decision report

## Recommendation

**Retain `less` and redesign the integration and rendering path before considering
an independent pager.** The evidence supports more than a collection of wrapper
repairs: progressive input, follow mode, failure recovery, and formatting semantics
need explicit design. It does not establish a need to own terminal navigation,
search, multi-file sessions, and the rest of a pager.

Three experiments demonstrate useful capabilities with the existing pager:

1. An isolated line-by-line JSON renderer, connected through native
   `LESSOPEN=|-… %s` stdin preprocessing, displays colored content before EOF,
   displays later records through follow mode, and exits after interrupt/quit
   while the original input remains open. It needs no shell spool.
2. Passing forced Markdown through `LESSOPEN` preserves real filenames, forward
   and backward file navigation, and a single quit for the whole session.
3. A named-file filter that emits nothing delegates to the original file; once it
   emits partial output, native fallback no longer replaces it with the original.

The stdin-enabled `|-` form is documented in the local `less(1)` manual and is
not used by the current wrapper. The first experiment is deliberately narrow. It does not solve full Markdown
streaming, lexer state across chunks, detection without consuming input, or robust
producer cancellation. The native incremental prototype emits a Python
`KeyboardInterrupt` diagnostic on Ctrl+C; successful exit is not a claim of polished
interruption behavior. The third identifies a real boundary: recovery after
committing transformed output needs an explicit policy. Neither warrants assuming
that a standalone pager would make rendering state or recovery simple.

## Evidence and execution

The baseline leaves `richless.py`, `richless-init.sh`, project dependencies, and
application behavior unchanged. Tests use an isolated HOME/TMPDIR, the checkout's
renderer, real shells, and a controlling pseudo-terminal. Positive controls use
plain `less` and filter-only integration. Existing tests are run separately.

See the generated ledgers under `results/` for individual expectations, exact
commands, return codes, diagnostics, and terminal transcripts. Scenarios that fail
remain ordinary pytest failures; skipped measurements/probes are recorded as
blocked, not passed. Reproduce a finding using its pytest ID and the instructions
in [README.md](README.md).

Linux runs execute inside Docker Desktop's Linux VM on this Mac, using Debian
Bookworm containers and an unprivileged account. They exercise Linux binaries and
system behavior, not native Linux hardware performance. Sources are mounted
read-only and copied into a temporary container worktree; only audit results are
written back. macOS Python 3.13 uses a separate temporary environment.

### Final execution matrix

| Environment | Python | less | Shells | Pass | Fail | Policy observations |
|---|---|---|---|---:|---:|---:|
| [macOS 26.6.2](results/macos-final/ledger.md) | 3.12.9 | 668 | bash 3.2.57, zsh 5.9, sh/bash 3.2.57 | 231 | 99 | 5 |
| [macOS 26.6.2](results/macos-3.13/ledger.md) | 3.13.15 | 668 | bash 3.2.57, zsh 5.9, sh/bash 3.2.57 | 231 | 99 | 5 |
| [Debian Bookworm container](results/linux-3.12/ledger.md) | 3.12.12 | 590 | bash 5.2.15, zsh 5.9, dash 0.5.12 | 231 | 99 | 5 |
| [Debian Bookworm container](results/linux-3.13/ledger.md) | 3.13.11 | 590 | bash 5.2.15, zsh 5.9, dash 0.5.12 | 231 | 99 | 5 |

That is **335 baseline scenarios per environment, 1,340 baseline observations**.
Each baseline ledger additionally lists 27 intentionally unrun optional cases
(three probes and 24 performance combinations) as blocked. These were executed
separately on macOS/Python 3.12: [three probes passed](results/probes/ledger.md);
[21 performance cases completed and three hit their deadline](results/performance/ledger.md).
This does not represent 99 independent bugs per platform: many cases repeat the
same defect across paths and shells. Outcome classifications match across all four
baseline environments after the final focused reruns.

The original test suite remains green: **85 passed**, with **362 audit cases
skipped** in the ordinary opt-out run. No lint/type-check configuration was added.
Syntax compilation and `git diff --check` also passed. Runtime packages in all
recorded environments were Rich 14.2.0 and Pygments 2.19.2; pytest was 9.0.2.

### Performance findings

The [full measurement table](results/performance/performance.md) contains three
repetitions per completed combination, including both named files and finite
pipelines. Inputs are deterministic synthetic JSONL, not the original reported
Zeek dataset. Measurements were made on the Mac with 64 GiB RAM; Linux containers
were used for behavioral compatibility, not these timings.

| Generated input | Rendered paths: first useful display | Reported max RSS | Plain less: first display |
|---|---:|---:|---:|
| 100 lines | 0.105–0.483 s | about 31–32 MiB | about 0.05 s |
| 10,000 lines | 1.84–2.01 s | about 361–365 MiB | about 0.05 s |
| 166,000 lines | 30.46–30.85 s | about 5.45 GiB | about 0.05 s |
| 500,000 lines | no useful display within 45 s | unavailable after forced termination | about 0.05 s |

The three rendered paths are filter-only named files, wrapper named files, and
wrapper pipelines. The filter-only pipeline control behaves like plain less
because the existing `|richless %s` form does not preprocess stdin.

These results do **not** demonstrate the PRD's under-300-ms goal consistently:
even the 100-line case exceeded it in some repetitions. Small cases were rerun
without other audit jobs active to check an initial overlap concern; startup still
varied. First-display measurement resolution is about 50 ms, and end-of-file times
include command synchronization overhead. This is an exploratory desktop
measurement, not a calibrated isolated-host benchmark.

The large completed cases reveal substantial time and memory growth. At 500,000
lines, the harness terminated each rendered path after its first 45-second miss
and cancelled further repetitions. Those observations are censored lower bounds,
not measured completion times. `wait4` reports maximum child resource accounting,
not aggregate concurrent process-tree RSS; killed sessions cannot reliably account
for renderer memory and are intentionally marked unavailable.

## Reducing latency and making waiting understandable

### Substantial first-display improvement is demonstrated

The incremental probe was extended to the **same 166,000 generated JSONL records**
used in the baseline. Through native stdin-enabled LESSOPEN, three repetitions
showed highlighted content in **0.110–0.111 seconds**, compared with about
**30–31 seconds** for the current renderer. Early quit returned in about
**0.030–0.035 seconds**. See the latest incremental entry in the
[probe ledger](results/probes/ledger.md), including `large_input_measurements`.

This measures first display and early quit, not complete-file throughput. The
prototype renders independent JSON lines at a fixed 100-column width. It does not
preserve all current width/horizontal-scroll semantics, establish multiline lexer
state, implement incremental Markdown, or polish interruption diagnostics. Its
reported parent RSS does not establish the renderer's memory use on early exit.

Nevertheless, the experiment answers the main latency question for this workload:
**we can avoid the long wait while retaining less**. Full-file processing before
first output is not required by the pager. This result strengthens the integration
redesign recommendation; it does not claim that the prototype is ready to ship.

### Feedback is a separate requirement

A 45-second delay is a failed usability case, not an acceptable performance target
because the harness eventually stopped it. Even a good progress message would not
make the current large-file behavior satisfactory. Prioritize useful early content
and responsive cancellation, then provide feedback for unavoidable preparation.

For the next design, consider these explicit feedback requirements:

- If useful content is not ready after roughly 300 ms, show an honest activity
  message with elapsed time, for example `Preparing Markdown… 2.1 s elapsed`.
- Show counts or percentages only when they reflect completed work and a known
  total. An open stream has no completion percentage; bytes read do not measure
  rendering completion. Distinguish reading, rendering, and waiting for input.
- Keep cancellation responsive and define a safe raw-view option where original
  input can be retained. Do not promise recoverable stdin after discarding bytes.
- Remove feedback when content becomes available. It must not become searchable
  document text, change line navigation, obscure errors, or damage terminal state.

The current shell/less boundary matters here. The tracker records an earlier stderr
progress attempt that less hid; this audit has **not** demonstrated a reliable
persistent feedback surface. Writing a “please wait” line to renderer stdout is
not a sound workaround because less treats that line as file content. Arbitrary
stderr redraws can conflict with the pager's display.

A finite-document preparation stage could own the terminal and show progress before
launching less, but that postpones content and does not by itself solve progress
when switching files inside an existing pager session. Persistent in-pager feedback
would require a validated integration or explicit terminal ownership. These are
implementation choices to test, not reasons to assume an entire pager replacement
is already necessary.

Before shipping a redesign, add PTY acceptance tests for slow startup, active-pager
file changes, resize, redirected stderr, cancellation, transition to first content,
and absence of status text in searches. Incremental Markdown and feedback ownership
are the main remaining design uncertainties; progress feedback was assessed here
but no fourth architectural prototype was added.

## Findings and likely remedies

Effort labels are relative engineering judgments, not delivery estimates: **small**
means a localized repair, **medium** means coordinated behavior changes and tests,
and **large** means architecture or product-contract work. Confidence concerns
cause attribution, not coverage of every possible input.

| Finding | Evidence / impact | Cause and confidence | Likely remedy / effort | Would a new pager remove it? |
|---|---|---|---|---|
| Continuing streams wait for EOF | `test_audit_stream`: wrapper cannot show the first screen while stdin stays open; plain/filter controls can. | Wrapper copies all stdin with `cat` before launching the renderer; Python also reads complete input. High. | Bounded detection plus progressive rendering or explicit raw streaming route; large. | It still needs progressive input and rendering. |
| Follow mode sees a snapshot | `test_audit_follow_file`: appended named-file records do not appear through the filter/wrapper. | Renderer reads once and exits; pager sees transformed output rather than a live file. High. | Design follow-aware rendering or native passthrough for following; large. | Removes the interface but still requires file monitoring and incremental formatting. |
| Named pipes block before display | `test_audit_fifo`: filter/wrapper wait on a still-open FIFO. | Full-file read in the preprocessor. High. | Share progressive-input design; medium/large. | Same input-processing requirement remains. |
| Forced Markdown breaks multi-file sessions | `test_audit_mixed[forced-wrapper-*]`; automatic mixed-format sessions provide a passing control. | Wrapper invokes a separate pipeline/pager per file and rebuilds arguments in strings. High. | Pass the rendering preference through a per-invocation filter while keeping one `less` command; medium. Probe demonstrates the central mechanism. | Avoidable with existing `less`; replacement is unnecessary for this issue. |
| Valid filenames can show the wrong content | `test_audit_arguments[whitespace-collision-*]` shows a whitespace-padded filename resolving to its unpadded neighbor through filter/wrapper, across all shells. Plain controls show the intended file. | `main()` calls `.strip()` on the filename. High. | Preserve the exact pathname; small but high-priority integrity repair. | Pure implementation bug; no new pager needed. |
| Leading-dash filenames lose highlighting | `test_audit_arguments[leading-dash-*]`: native file access survives but preprocessing does not. | The LESSOPEN template does not put `--` before the filename passed to argparse. High. | Preserve the option boundary in the preprocessor invocation; small. | Pure integration bug. |
| zsh pipeline options become filenames | `test_audit_routes[*-wrapper-zsh]`: diagnostic such as ` -R: No such file or directory`. | Unquoted scalar argument reconstruction assumes shell word splitting that default zsh does not perform. High. | Preserve argument boundaries using portable positional parameters; medium. | A direct CLI would avoid the shell bug; so would a repaired wrapper. |
| Quoted pipeline search arguments split | `test_audit_initial_position[phrase-pipe-*]` distinguishes this from zsh-only behavior. | String reconstruction loses the original argument boundaries. High when controls pass. | Same argument-preservation repair; medium. | No need to replace the pager. |
| `-m` conflicts with native prompt behavior | `test_audit_arguments[dash-m-wrapper-*]`. | Wrapper consumes an existing `less` flag as forced Markdown. High. | Remove the conflicting shortcut; small. | Pure integration bug. |
| Existing LESS options expose ANSI escapes | `test_audit_environment[less-options-*]`. | Init preserves a nonempty `LESS` without ensuring `-R`. High. | Define and enforce color-option precedence while retaining other options; small. | Pure integration bug. |
| Temporary-file failure loses piped input | `test_audit_environment[temp-failure-*]`. | `mktemp` failure returns before providing a viewing path. High. | Preserve native stdin fallback or eliminate the spool requirement; medium. | A new implementation must still handle resource failure. |
| Signals leak temporary files | `test_audit_failures[interrupt-copy-*]` and `[terminate-copy-*]` inspect leftovers before harness cleanup. | No cleanup traps. High. | Scope cleanup and preserve shell signal behavior and exit status; medium. | Removes this particular spool only if the new design avoids it. |
| Undecodable pipeline content disappears | `test_audit_integrity[invalid-wrapper]` and `[binary-wrapper]`; named-file filter controls retain bytes. | UTF-8 read and fallback both fail; wrapper's pipeline has no original-file fallback. High. | Delegate named files cleanly; preserve raw bytes and consumption state for pipes; medium. | Encoding and byte-preserving recovery still need design. |
| Failed renderer pipelines can report success | Injected executable failures in `test_audit_failures[render-*]`. | Wrapper loses rendered content and ultimately returns cleanup status. High. | Preserve meaningful status and an actual raw-input path; medium. | Process/error ownership persists in any design. |
| Late rendering failure contaminates fallback | `test_audit_python_render_failure[after]`; before-output control succeeds. | `main()` appends raw content after already-emitted partial output. High. | Choose transactional output, chunk-level guarantees, or explicit partial-output diagnostics; medium/large. | This is a renderer/recovery problem, not solely a pager interface problem. |
| Content formatting is not source-exact | Integrity cases show added newlines, tab expansion, and CRLF normalization. Unicode characters survive the sampled case; its failure is an extra newline, not Unicode corruption. | Text-mode reading and Rich Syntax/Console output semantics. High. | Define source fidelity versus presentation rules, avoid incidental text changes; medium. | Persists if the same rendering strategy is reused. |
| Unmarked piped source code lacks highlighting | `test_audit_formats[code.c-pipe]`, `[code.py-pipe]`, and `[code.PY-pipe]`; corresponding named files are highlighted. | Extension information disappears in pipes and content heuristics recognize shebangs rather than arbitrary code. High. | Decide how much inference to promise and consider bounded lexer guessing or an explicit format option; medium. | Ambiguity remains in a replacement too. |
| Markdown detection differs by route | Heading-only/list-only pipes and extensionless Markdown fail automatic-rendering expectations. | Shell requires multiple Markdown signals; Python has no equivalent Markdown content detection. High. | Define detection precedence and acceptable ambiguity; consolidate where practical; medium. | Format ambiguity remains either way. |

Failures are grouped by cause. Do not count every shell, input route, and parameter
combination as an independent defect. Detection ambiguity and exact preservation
of tabs/line endings also involve product choices: the ledger applies explicit
strict expectations to expose differences, not to imply identical severity.

### Behaviors that work and narrow the decision

Automatic mixed sessions cover C, Python, Markdown, JSON, and plain text, including
real glob expansion, reversed order, spaces in filenames, and revisiting files.
These controls are important: loss of multi-file behavior is concentrated in the
forced-rendering path, not intrinsic to preprocessing. Native and filtered search,
page movement, horizontal scrolling, and quitting are tested separately.

The Linux shell matrix gives `/bin/sh` a separate implementation (dash); macOS
`/bin/sh` is bash-derived. Shared renderer defects are reported separately from
bash/zsh/dash argument or signal behavior. Targeted integrity and format matrices
use bash for the wrapper route; this is explicitly not exhaustive shell coverage
for those categories.

### Product decisions exposed

- Should arbitrary extensionless Markdown render automatically, despite ambiguous
  text, comments, and data structures?
- Must source viewers preserve tabs and line endings exactly, or only their visual
  interpretation? Extra blank output and lost bytes are separate concerns.
- Should an existing `LESSOPEN` preprocessor be replaced, composed, or bypassed?
- Should producer failure affect the wrapper exit status? Default shell pipelines
  report the last command; that native policy differs from losing a renderer error.
- What must follow/stream mode promise for Markdown that can change meaning when
  later lines arrive? A responsive raw route could satisfy access requirements,
  but it is not equivalent to progressive rich formatting.

These decisions are not silently resolved by changing the implementation.

## Coverage limits

The audit is broad, bounded evidence—not a proof of universal `less` compatibility.

- PTY transcripts verify content, commands, prompts, selected styling, and terminal
  settings. They are not a full screen emulator: exact cell placement, all color
  reset state, and Markdown reflow after resize need visual/emulator validation.
- Follow covers append-only files, not rotation, truncation, rename/replacement,
  remote filesystems, or reconnecting producers.
- Performance inputs are generated JSONL. Markdown-heavy, giant single-paragraph,
  memory-pressure, and large multiline-lexer workloads remain unmeasured.
- Hard power loss and SIGKILL cannot be handled by ordinary shell traps. Cleanup
  checks cover interrupt and termination, not a guarantee after uncatchable death.
- Tests do not comprehensively cover custom lesskey files, global shell startup
  customizations, every locale/terminal, NO_COLOR policy, editor/shell escapes,
  persistent search history, symlink races, or every historical `less` version.
- Peak-memory numbers use `wait4` resource accounting and are not a sampled sum of
  all concurrently running processes. Treat them as bounded observations, not a
  capacity-sizing model. Linux container startup is excluded from macOS benchmarks.
- The incremental probe handles independent JSON lines. Full incremental Markdown,
  bounded lookahead, cross-chunk lexer state, and interrupted search with an absent
  match on an unbounded stream remain explicit architectural validation gaps.

## Decision gate for the next phase

Pursue integration redesign if it can preserve native multi-file/search behavior,
provide useful output before EOF, and keep content accessible on renderer failure.
Start with the demonstrated forced-filter mechanism, argument preservation, and a
separate progressive/raw-input design. Reuse failing audit IDs as acceptance tests.

Reconsider a standalone pager if required rich streaming/follow/reflow behavior
cannot be delivered reliably through a bounded integration design, or if a
consciously narrower pager contract is preferable to native `less` compatibility.
The current evidence does not establish that boundary has been reached.

Reference: the local `less(1)` INPUT PREPROCESSOR section describes the native
empty-output fallback contract. The upstream [less FAQ](https://www.greenwoodsoftware.com/less/faq.html)
also documents multi-file navigation, follow mode, initial-position commands, and
`-R`/`-m` behavior. Behavioral conclusions above come from retained audit results.
