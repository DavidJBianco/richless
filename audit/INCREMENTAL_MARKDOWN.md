# Incremental Markdown investigation

## Conclusion

Incremental Markdown display through native `less` is feasible for completed,
stable blocks. It does not require replacing the pager. An isolated prototype
displayed formatted content before input ended and matched whole-document Rich
output in 50 fixture/width comparisons. This is feasibility evidence, not a
complete or production-ready streaming parser.

There are two useful implementation paths:

1. **Finite files:** parse the document once, resolve references, and publish
   rendered output progressively. This retains full-document semantics while
   avoiding the wait for all rendering to finish. Reading and parsing still
   precede first display; memory still includes the source and parsed document.
2. **Continuing input:** parse and render completed blocks as they become stable.
   Hold unfinished constructs and unresolved references. This needs a deliberate
   buffering/fallback policy and a parser that does not repeatedly reparse an
   ever-growing suffix.

Keep these paths in the integration redesign plan. Do not promise bounded display
latency for arbitrary Markdown under unchanged whole-document semantics.

## Reproduction and scope

Run from the repository root:

```sh
UV_CACHE_DIR=/private/tmp/richless-uv-cache uv run --frozen python audit/incremental_markdown.py investigate audit/results/markdown
```

The standalone research script leaves production rendering and the shell wrapper
unchanged. It reuses the audit PTY harness and invokes real `less` with a native
stdin-enabled LESSOPEN preprocessor. Results, source examples, rendered ANSI,
token-commit traces, and PTY transcripts are retained under `results/markdown/`.

This investigation ran on macOS arm64, Python 3.12.9, Rich 14.2.0, and
markdown-it-py 4.0.0. The four live cases used bash; this additional experiment has
not run on Linux, zsh, or `/bin/sh`. The earlier compatibility audit's broader
platform/shell coverage does not establish portability of this new prototype.

## Evidence

| Experiment | Result | Interpretation |
|---|---|---|
| 25 Markdown examples at widths 40 and 80 | 50/50 byte-identical to whole-document rendering | Preserving renderer state and holding ambiguous blocks works for these examples. |
| Render each blank-line-separated chunk independently | 2/50 identical | Simple chunk splitting loses document context and spacing; differences are not all semantic errors. |
| Commit blocks without reference protection | 46/50 identical | Future reference definitions require additional handling. |
| Completed formatted block, live input | Visible at about 0.110 s, before EOF | Native LESSOPEN can deliver incremental Markdown. This is a single timing observation. |
| Unresolved reference, live input | Held initially; displayed after definition arrived while input remained open | Waiting need not last until EOF when the ambiguity resolves sooner. |
| Unfinished paragraph, live input | No display during the 0.6 s observation; displayed at EOF | The conservative prototype waits for a stable boundary. |
| Lazy tokens passed to normal `Console.print(Markdown(...))` | No display during the 0.6 s observation; displayed at EOF | Token streaming alone does not bypass Console's output buffering. |

Examples include headings, nested and continuing lists, quotes, fenced and
indented code, tables, forward/backward/duplicate references, images, multiline
inline markup, Unicode, missing final newline, and empty input. All four PTY cases
met their explicit expectations and quit normally. Negative controls demonstrate
limitations, not usable early display in every case.

### Finite-document performance

For a generated 1,368,943-byte document with 20,000 sections and a first-paragraph
reference defined at EOF, three in-process repetitions measured:

| Measurement | Range |
|---|---:|
| Whole-document parse and render | 2.25–2.41 s |
| Parse once, then publish first rendered line | 0.63–0.70 s |
| Parse once, then publish complete output in batches | 2.34–2.38 s |

All three complete outputs matched exactly, and the first line contained the
resolved reference. This improves availability of initial output without a clear
throughput penalty in this sample. It still exceeds the 300 ms target. These
measurements exclude process startup, file reading, and actual pager display;
they are not directly comparable to the earlier JSONL PTY measurements. Output
was captured in memory for comparison, so this experiment does not demonstrate
a peak-memory reduction.

### Why arbitrary Markdown cannot always appear immediately

Later input can change earlier presentation:

- `Title` followed by `=====` becomes a heading.
- `Read [manual].` becomes a link if a later definition supplies its destination.
- A wider later table cell changes the widths of already-received rows.

The experiments confirmed that rendering those prefixes immediately produces
output that is not a prefix of the final rendering. These are consequences of
Markdown grammar and layout; see the [CommonMark specification](https://spec.commonmark.org/0.31.2/)
for heading and reference rules. Table layout is an additional Rich behavior.
The tested list-spacing and ordered-number examples did *not* change previous
output; they should not be cited as demonstrated counterexamples.

With append-only output into `less`, we cannot simultaneously guarantee exact
whole-document presentation, arbitrary continuing input, and bounded delay for
every construct. We must sometimes wait, adopt a defined presentation compromise,
or use a mechanism capable of revising previously displayed content. This does
not establish that a standalone pager is necessary.

## Prototype mechanism and remaining work

The prototype reparses the pending suffix and commits all but its last top-level
block. It retains reference definitions and conservatively holds inline text
containing unresolved brackets. One Rich renderer consumes the token iterator,
preserving document rendering context. Rendered lines are published explicitly;
normal whole-document Console printing buffers them. Finite-document throughput
uses batches of 32 lines after publishing the first line.

Important limits:

- Repeated suffix parsing has poor scaling: one unfinished paragraph took about
  0.035/0.139/0.556/2.252 s at 100/200/400/800 lines. A production implementation
  needs incremental parser state or another bounded strategy. Completed short
  paragraphs scaled much better, but do not remove this worst case.
- Unfinished paragraphs, lists, code fences, tables, or unresolved references can
  retain arbitrarily much input. Literal or escaped brackets can falsely trigger
  the conservative reference hold. Size/time limits and the behavior on reaching
  them remain product decisions; silently changing already-rendered semantics is
  not an acceptable implicit policy.
- Retaining definitions from an uncommitted suffix needs adversarial validation;
  future context may change how that suffix is parsed. The commit algorithm has
  no completeness proof and has not passed a full CommonMark corpus.
- Assigning an iterator to Rich's `Markdown.parsed` uses an internal extension
  point, not a supported streaming API. The production design must account for
  dependency changes and avoid assuming this hook is stable.
- Comparisons disable OSC hyperlinks for deterministic output. Production link
  behavior, resizing, growing-file follow semantics, mixed-file navigation, and
  failure after partial output remain to be validated for this mechanism.
- Live output uses a fixed width of 80. Cancellation was only checked by normal
  quitting after EOF here; robust interruption and cleanup remain implementation
  work covered by the broader audit requirements.

The next design should separate progressive *rendering of a parsed finite
document* from progressive *parsing of a live document*. The former has a smaller
correctness burden and a demonstrated latency benefit. The latter is promising,
but requires a clear contract for unresolved and indefinitely growing constructs
before it can satisfy the required continuing-stream workflow.
