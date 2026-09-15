"""Investigate incremental Markdown; not a production renderer or supported API.

Run with uv run python audit/incremental_markdown.py investigate OUTPUT_DIR.
The stream subcommand is an isolated LESSOPEN prototype reading stdin.
"""

import argparse
from collections.abc import Iterable, Iterator
from copy import deepcopy
import importlib.metadata
import platform
import io
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace

from markdown_it import MarkdownIt
from markdown_it.token import Token
from rich.console import Console
from rich.markdown import Markdown
from rich.segment import Segment, Segments

ROOT = Path(__file__).resolve().parents[1]

CASES = {
    'paragraphs': 'First paragraph.\n\nSecond **bold** paragraph.\n\nLast paragraph.\n',
    'headings': '# Opening\n\nParagraph.\n\n## Next\n\nTail.\n',
    'setext': 'Opening\n=======\n\nParagraph\n---------\n\nTail.\n',
    'list-loosening': '- First\n- Second\n\n- Third\n\nOutside paragraph.\n',
    'list-continuation': '- First\n\n  Continuation **inside**.\n\n- Second\n\nOutside.\n',
    'nested-list': '- Outer\n  - Inner\n\n    Continued inner.\n- Next\n\nOutside.\n',
    'ordered-list': '98. First\n99. Second\n100. Third\n\nOutside.\n',
    'blockquote': '> Quoted paragraph\n> continued\n\n> Another quoted paragraph\n\nOutside.\n',
    'fenced-code': 'Before.\n\n```python\nx = "value"\n\n# not a heading\n```\n\nAfter.\n',
    'unclosed-fence': 'Before.\n\n```python\nx = "value"\n',
    'indented-code': 'Before.\n\n    first\n\n    second\n\nAfter.\n',
    'table-growing-width': '| Key | Value |\n| --- | --- |\n| a | b |\n| wider-key | a much longer value |\n\nAfter.\n',
    'future-reference': 'See [manual][guide].\n\nAn unrelated paragraph.\n\n[guide]: https://example.com/manual\n',
    'future-shortcut': 'See [guide].\n\nAnother paragraph.\n\n[guide]: https://example.com/manual\n',
    'backward-reference': '[guide]: https://example.com/manual\n\nSee [guide].\n\nTail.\n',
    'reference-in-container': 'See [guide].\n\n> [guide]: https://example.com/manual\n\nTail.\n',
    'duplicate-reference': '[guide]: https://example.com/first\n\nSee [guide].\n\n[guide]: https://example.com/second\n',
    'inline-reference-brackets': 'An [inline link](https://example.com) and literal [brackets].\n\nTail.\n',
    'multiline-inline': 'Opening **bold\ncontinued** and `code\nspan`.\n\nTail.\n',
    'html-block': '<div>\n# inside HTML\n</div>\n\nAfter.\n',
    'thematic-break': 'Before.\n\n---\n\nAfter.\n',
    'image': 'Before.\n\n![alt text](image.png)\n\nAfter.\n',
    'unicode': '# 世界\n\ncafé e\u0301 **text**.\n\nTail.\n',
    'no-final-newline': '# Header\n\nFinal paragraph',
    'empty': '',
}


def parser() -> MarkdownIt:
    """Match the block features enabled by the installed Rich Markdown renderer."""
    return MarkdownIt().enable('strikethrough').enable('table')


def possible_unresolved_reference(tokens: Iterable[Token]) -> bool:
    """Conservatively hold brackets remaining as inline text, including false positives."""
    for token in tokens:
        if token.type == 'text' and '[' in token.content:
            return True
        if token.children and possible_unresolved_reference(token.children):
            return True
    return False


def committed_tokens(lines: Iterable[str], trace: list[dict], conservative: bool = True) -> Iterator[Token]:
    """Emit all but the trailing top-level block; conservatively hold possible references.

    Reparse the pending suffix after each complete input line. This deliberately
    prioritizes a simple feasibility experiment over asymptotic efficiency.
    Retain definition context across committed prefixes. Brackets still present
    as inline text block publication until resolved or EOF. Literal/escaped brackets
    can cause false positives. This is NOT a proven complete commit algorithm.
    """
    pending: list[str] = []
    environment: dict = {}
    source_lines = 0
    p = parser()
    for line in lines:
        pending.append(line)
        source_lines += 1
        if not line.endswith(('\n', '\r')):
            continue
        text = ''.join(pending)
        trial_environment = deepcopy(environment)
        tokens = p.parse(text, trial_environment)
        starts = [i for i, token in enumerate(tokens)
                  if token.level == 0 and token.nesting >= 0 and token.map is not None]
        if len(starts) < 2:
            continue
        cut_index = starts[-1]
        cut_line = tokens[cut_index].map[0]
        if conservative and possible_unresolved_reference(tokens[:cut_index]):
            trace.append({'at_source_line': source_lines, 'held': 'possible reference', 'pending_chars': len(text)})
            continue
        if cut_line:
            trace.append({'at_source_line': source_lines, 'committed_lines': cut_line,
                          'pending_chars': len(text), 'token_types': [t.type for t in tokens[:cut_index]]})
            yield from tokens[:cut_index]
            # Retain all parsed definitions, including any in the pending suffix.
            # CommonMark's first definition wins; adversarial context needs more validation.
            environment = trial_environment
            pending = pending[cut_line:]
    trace.append({'eof': True, 'remaining_lines': len(pending)})
    yield from p.parse(''.join(pending), environment)


def progressive_segments(lines: Iterable[str], trace: list[dict], width: int,
                         conservative: bool = True, hyperlinks: bool = False) -> Iterator[Segment]:
    """Preserve Rich's renderer state while supplying tokens incrementally."""
    console = Console(force_terminal=True, color_system='truecolor', width=width)
    markdown = Markdown('', hyperlinks=hyperlinks)
    # Rich currently iterates parsed tokens lazily. Assigning an iterator here is
    # an internal extension point, not a stable public streaming API.
    markdown.parsed = committed_tokens(lines, trace, conservative)  # type: ignore[assignment]
    yield from console.render(markdown)


def rendered(text: str, width: int = 80) -> str:
    """Capture normal whole-document Rich output using stable non-OSC links."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, color_system='truecolor', width=width)
    console.print(Markdown(text, hyperlinks=False), end='')
    return buffer.getvalue()


def streamed(text: str, trace: list[dict], width: int = 80, conservative: bool = True) -> str:
    """Capture incremental segment output without whole-document Console.print buffering."""
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, color_system='truecolor', width=width)
    publish(progressive_segments(text.splitlines(keepends=True), trace, width, conservative), console)
    return buffer.getvalue()


def publish(segments: Iterable[Segment], console: Console, batch_lines: int = 1) -> None:
    """Flush complete rendered lines while preserving Console's normal width crop."""
    line: list[Segment] = []
    completed = 0
    for segment in segments:
        line.append(segment)
        if segment.text.endswith('\n'):
            completed += 1
        if completed >= batch_lines:
            console.print(Segments(line), end='')
            console.file.flush()
            line = []
            completed = 0
    if line:
        console.print(Segments(line), end='')
        console.file.flush()


def stream_stdout(buffered: bool = False) -> None:
    """Feed a live pager, optionally demonstrating Console.print's buffering."""
    console = Console(force_terminal=True, color_system='truecolor', width=80)
    trace: list[dict] = []
    if buffered:
        markdown = Markdown('', hyperlinks=False)
        markdown.parsed = committed_tokens(sys.stdin, trace)  # type: ignore[assignment]
        console.print(markdown, end='')
    else:
        publish(progressive_segments(sys.stdin, trace, 80), console)


def investigate(out: Path) -> None:
    """Write rendering comparisons, counterexamples, and live-terminal evidence."""
    out.mkdir(parents=True, exist_ok=True)
    os.environ['TERM'] = 'xterm-256color'
    results: dict = {'cases': [], 'counterexamples': [], 'pty': [], 'scaling': [],
                     'environment': {'platform': platform.platform(), 'python': sys.version,
                                     'packages': {p: importlib.metadata.version(p) for p in ['rich', 'markdown-it-py']}}}
    for name, text in CASES.items():
        for width in [40, 80]:
            trace: list[dict] = []
            full = rendered(text, width)
            incremental = streamed(text, trace, width)
            chunks = re.split(r'(?<=\n)\s*\n', text)
            naive = ''.join(rendered(chunk, width) for chunk in chunks if chunk)
            unsafe = streamed(text, [], width, conservative=False)
            results['cases'].append({'name': name, 'width': width, 'source': text,
                'equivalent': full == incremental, 'naive_blank_split_equivalent': full == naive,
                'without_reference_hold_equivalent': full == unsafe,
                'whole': full, 'incremental': incremental, 'naive': naive,
                'unsafe': unsafe, 'trace': trace})
    # Equal received prefixes can require different earlier output after a suffix.
    for name, prefix, suffix in [
        ('setext', 'Title\n', '=====\n'),
        ('reference', 'Read [manual].\n\n', '[manual]: https://example.com\n'),
        ('list-spacing', '- one\n- two\n', '\n- three\n'),
        ('ordered-alignment', '9. first\n', '10. second\n'),
        ('table-width', '| a | b |\n| - | - |\n| c | d |\n', '| a very long cell | another |\n')]:
        before = rendered(prefix)
        after = rendered(prefix + suffix)
        results['counterexamples'].append({'name': name, 'prefix': prefix, 'suffix': suffix,
            'earlier_render_is_prefix_of_final': after.startswith(before), 'before': before, 'after': after})
    for size in [100, 200, 400, 800]:
        for shape in ['paragraph', 'many-blocks']:
            text = ('a long unfinished paragraph line\n' * size if shape == 'paragraph' else 'Paragraph.\n\n' * size)
            start = time.monotonic()
            trace = []
            list(committed_tokens(text.splitlines(keepends=True), trace))
            results['scaling'].append({'shape': shape, 'lines_or_blocks': size,
                                      'seconds': time.monotonic() - start})
    # Finite documents can resolve the full AST/reference environment once, then
    # start output without buffering all rendered segments in Console.print.
    results['finite_document'] = []
    finite = 'Read [manual].\n\n' + ''.join(
        f'## Section {i}\n\nParagraph **bold** and `code` with ordinary text.\n\n'
        for i in range(20000)) + '[manual]: https://example.com/manual\n'
    for repetition in range(3):
        start = time.monotonic()
        whole = rendered(finite)
        whole_seconds = time.monotonic() - start
        start = time.monotonic()
        markdown = Markdown(finite, hyperlinks=False)
        parse_seconds = time.monotonic() - start
        target = io.StringIO()
        console = Console(file=target, force_terminal=True, color_system='truecolor', width=80)
        segments = console.render(markdown)
        first_line = []
        for segment in segments:
            first_line.append(segment)
            if segment.text.endswith('\n'):
                break
        console.print(Segments(first_line), end='')
        first_seconds = time.monotonic() - start
        publish(segments, console, batch_lines=32)
        results['finite_document'].append({'repetition': repetition, 'bytes': len(finite.encode()),
            'sections': 20000, 'whole_render_seconds': whole_seconds,
            'parse_seconds': parse_seconds, 'first_line_seconds': first_seconds,
            'stream_total_seconds': time.monotonic() - start,
            'identical_complete_output': target.getvalue() == whole,
            'forward_reference_resolved_on_first_line': 'https://example.com/manual' in target.getvalue().splitlines()[0]})
    # Reuse the established audit PTY harness; no duplicated terminal driver.
    sys.path.insert(0, str(ROOT / 'tests'))
    import test_richless as harness
    os.environ['RICHLESS_AUDIT_DIR'] = str(out / 'pty')
    for scenario in ['complete-block', 'reference-hold', 'unfinished-paragraph', 'console-buffered']:
        with TemporaryDirectory(prefix='richless-md-probe-') as temporary:
            request = SimpleNamespace(node=SimpleNamespace(name='test_audit_markdown_' + scenario))
            fixture = harness.workflow_audit.__wrapped__(Path(temporary), request)
            item = next(fixture)
            try:
                import shlex
                command = shlex.join([sys.executable, str(Path(__file__).resolve()), 'stream'])
                if scenario == 'console-buffered':
                    command += ' --buffered'
                item['env']['LESSOPEN'] = '|-' + command + ' %s'
                with harness.audit_terminal(item, harness.audit_command(item, 'bash', 'plain', 'less -R'), piped=True) as session:
                    payload = ('EARLY **MARKER**.\n\n# Next\n' if scenario in ['complete-block', 'console-buffered'] else
                               'EARLY [MARKER].\n\n# Next\n' if scenario == 'reference-hold' else
                               'EARLY **MARKER** still unfinished\n')
                    os.write(session['writer'], payload.encode())
                    visible = harness.audit_expect(session, 'EARLY', timeout=0.6)
                    expect_early = scenario == 'complete-block'
                    harness.audit_check(item, visible == expect_early,
                                        'Only a committed block with direct segment output appears before EOF')
                    if scenario == 'reference-hold':
                        os.write(session['writer'], b'\n[MARKER]: https://example.com\n')
                        harness.audit_check(item, harness.audit_expect(session, 'https://example.com'),
                                            'Held reference renders once its definition arrives, before EOF')
                    os.close(session['writer'])
                    session['writer'] = -1
                    harness.audit_check(item, harness.audit_expect(session, 'EARLY'), 'Buffered content appears at EOF')
                    harness.audit_send(session, b'q')
                    harness.audit_check(item, harness.audit_exited(session), 'Pager quits normally')
                    results['pty'].append({'scenario': scenario, 'visible_before_eof': visible,
                                          'checks': item['checks'], 'events': session['events']})
                harness.audit_finish(item)
            finally:
                try:
                    next(fixture)
                except StopIteration:
                    pass
    (out / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps({'comparisons': len(results['cases']),
                      'equivalent': sum(r['equivalent'] for r in results['cases']),
                      'naive_equivalent': sum(r['naive_blank_split_equivalent'] for r in results['cases']),
                      'unsafe_equivalent': sum(r['without_reference_hold_equivalent'] for r in results['cases']),
                      'pty_scenarios': len(results['pty'])}, indent=2))


def main() -> None:
    """Run the investigation or its isolated stdin preprocessor."""
    arguments = argparse.ArgumentParser(description=__doc__)
    sub = arguments.add_subparsers(dest='mode', required=True)
    examine = sub.add_parser('investigate')
    examine.add_argument('output', type=Path)
    live = sub.add_parser('stream')
    live.add_argument('--buffered', action='store_true')
    live.add_argument('file', nargs='?', default='-')
    args = arguments.parse_args()
    if args.mode == 'investigate':
        investigate(args.output.resolve())
    else:
        try:
            stream_stdout(args.buffered)
        except (BrokenPipeError, KeyboardInterrupt):
            os._exit(0)


if __name__ == '__main__':
    main()
