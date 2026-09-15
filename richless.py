#!/usr/bin/env python3
"""
richless - A LESSOPEN filter for Markdown rendering and syntax highlighting.

This utility works as a preprocessor for 'less', automatically rendering
Markdown files and syntax highlighting code using the rich library.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import select
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, BinaryIO

from pygments.formatters import TerminalTrueColorFormatter
from pygments.lexers import ClassNotFound, get_lexer_by_name, get_lexer_for_filename

if TYPE_CHECKING:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.segment import Segment, Segments


def markdown_dependencies() -> None:
    """Load Markdown rendering only when needed, keeping pager startup small."""
    if "Markdown" in globals():
        return
    from markdown_it import MarkdownIt
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.segment import Segment, Segments

    globals().update(
        MarkdownIt=MarkdownIt,
        Console=Console,
        Markdown=Markdown,
        Segment=Segment,
        Segments=Segments,
    )


def __getattr__(name: str) -> Any:
    """Retain access to lazily loaded rendering objects for existing callers."""
    if name in {"MarkdownIt", "Console", "Markdown", "Segment", "Segments"}:
        markdown_dependencies()
        return globals()[name]
    raise AttributeError(name)


MIN_SYNTAX_WIDTH = 80
MAX_SYNTAX_WIDTH = 16384


def is_markdown_file(filepath: str) -> bool:
    """Check if the file has a Markdown extension."""
    ext = Path(filepath).suffix.lower()
    return ext in [".md", ".markdown"]


def detect_syntax_from_content(content: str) -> str:
    """Detect file type from content when extension is unknown."""
    if not content:
        return "text"

    lines = content.split("\n", 20)  # Check first 20 lines
    first_line = lines[0].strip() if lines else ""

    # YAML detection: starts with --- or %YAML
    if first_line == "---" or first_line.startswith("%YAML"):
        return "yaml"

    # JSON detection: starts with { or [
    # But exclude TOML section headers like [section] or [[array]]
    if first_line.startswith("{"):
        return "json"
    if first_line.startswith("[") and not re.match(
        r"^\[{1,2}[a-zA-Z_][a-zA-Z0-9_.-]*\]{1,2}\s*$", first_line
    ):
        return "json"

    # Shebang detection
    if first_line.startswith("#!"):
        if "python" in first_line:
            return "python"
        elif "bash" in first_line or "/sh" in first_line:
            return "bash"
        elif "node" in first_line:
            return "javascript"
        elif "ruby" in first_line:
            return "ruby"
        elif "perl" in first_line:
            return "perl"

    # XML/HTML detection
    if first_line.startswith("<?xml") or first_line.startswith("<!DOCTYPE"):
        return "xml"

    # TOML detection: look for key = value patterns or [section] headers
    toml_score = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # TOML section header: [section] or [[array]]
        if re.match(r"^\[{1,2}[a-zA-Z_][a-zA-Z0-9_.-]*\]{1,2}\s*$", stripped):
            return "toml"
        # TOML key = value (with equals sign, not colon)
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*\s*=\s*", stripped):
            toml_score += 1
            if toml_score >= 2:
                return "toml"
            continue
        break

    if toml_score > 0:
        return "toml"

    # YAML detection: look for key: value patterns (possibly after # comments)
    # Skip comment lines and look for YAML structure
    for line in lines:
        stripped = line.strip()
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        # Check for YAML key: value pattern (word followed by colon)
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*:\s*", stripped):
            return "yaml"
        # If first non-comment line doesn't look like YAML, stop checking
        break

    return "text"


def get_terminal_width() -> int:
    """Get terminal width, even when stdout is piped."""
    # Try stderr since stdout is piped through LESSOPEN
    try:
        return os.get_terminal_size(sys.stderr.fileno()).columns
    except (OSError, ValueError):
        pass
    # Fall back to shutil (checks COLUMNS env var, then defaults to 80)
    return shutil.get_terminal_size().columns


SAMPLE_BYTES = 65536
PENDING_BYTES = 1048576
PENDING_SECONDS = 5.0
RESET = b"\x1b[0m"


def report(message: str, fatal: bool = False) -> None:
    """Report diagnostics separately from document content."""
    print(f"richless: {message}", file=sys.stderr, flush=True)
    if fatal and os.environ.get("RICHLESS_STATUS_FD") and not os.environ.get("RICHLESS_READY_FD"):
        try:
            os.write(int(os.environ["RICHLESS_STATUS_FD"]), b"E")
        except OSError:
            pass


def choose_format(filename: str, sample: bytes, forced: str | None = None) -> str:
    """Prefer explicit formats and extensions, then conservative content markers."""
    if forced:
        return forced
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError as exc:
        if exc.reason != "unexpected end of data":
            return "text"
        text = sample[: exc.start].decode("utf-8")
    if "\x00" in text or "\x1b" in text:
        return "text"
    if is_markdown_file(filename.rstrip()):
        return "markdown"
    suffix = Path(filename.rstrip()).suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix and not re.fullmatch(r"richless\.[A-Za-z0-9]{6}", Path(filename).name):
        try:
            lexer = get_lexer_for_filename("input" + suffix)
            if lexer.aliases[0] not in ("text",):
                return str(lexer.aliases[0])
        except ClassNotFound:
            pass
    detected = detect_syntax_from_content(text)
    if detected != "text":
        return detected
    # A heading plus another Markdown construct is stronger evidence than a
    # standalone comment, bullet, or underline in otherwise ambiguous prose.
    if re.search(r"^#{1,6}\s+\S", text, re.M) and re.search(
        r"^```|^> |^[-*] |\*\*[^*]+\*\*|\[[^]]+\]\([^)]+\)", text, re.M
    ):
        return "markdown"
    return "text"


def input_chunks(
    source: BinaryIO,
    initial: bytes = b"",
    remaining: int | None = None,
    output: BinaryIO | None = None,
) -> Iterator[bytes | None]:
    """Read bounded chunks and expose idle ticks for live parser deadlines."""
    if initial:
        yield initial
    fd = source.fileno()
    consumer = select.poll()
    if output is not None:
        try:
            consumer.register(output.fileno(), select.POLLERR | select.POLLHUP)
        except io.UnsupportedOperation:
            pass  # In-memory callers have no consumer descriptor to monitor.
    while remaining is None or remaining > 0:
        if output is not None and consumer.poll(0):
            raise BrokenPipeError("output consumer closed while input was idle")
        if not select.select([fd], [], [], 0.1)[0]:
            yield None
            continue
        chunk = os.read(fd, SAMPLE_BYTES if remaining is None else min(SAMPLE_BYTES, remaining))
        if not chunk:
            return
        if remaining is not None:
            remaining -= len(chunk)
        yield chunk


def sample_input(source: BinaryIO, regular: bool, size: int | None = None) -> tuple[bytes, bool]:
    """Sample without consuming beyond a bounded first-byte detection interval."""
    fd = source.fileno()
    if regular:
        return os.read(fd, min(SAMPLE_BYTES, size) if size is not None else SAMPLE_BYTES), False
    first = os.read(fd, SAMPLE_BYTES)
    if not first:
        return first, True
    sample = bytearray(first)
    deadline = time.monotonic() + 0.1
    while len(sample) < SAMPLE_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            break
        chunk = os.read(fd, SAMPLE_BYTES - len(sample))
        if not chunk:
            return bytes(sample), True
        sample.extend(chunk)
    return bytes(sample), False


def signal_ready() -> None:
    """Acknowledge a successfully prepared follow view to its owner."""
    descriptor = os.environ.pop("RICHLESS_READY_FD", None)
    if descriptor is not None:
        try:
            os.write(int(descriptor), b"R")
        finally:
            os.close(int(descriptor))


def write_bytes(output: BinaryIO, content: bytes) -> None:
    """Publish a prepared unit without adding layout or newline bytes."""
    remaining = memoryview(content)
    while remaining:
        count = output.write(remaining)
        if count is None or count <= 0:
            raise OSError("output stopped accepting rendered content")
        remaining = remaining[count:]
    output.flush()
    if content:
        signal_ready()


@lru_cache(maxsize=32)
def syntax_tools(syntax: str) -> tuple[Any, TerminalTrueColorFormatter]:
    """Reuse immutable lexer configuration and ANSI style tables."""
    return get_lexer_by_name("json" if syntax == "jsonl" else syntax), TerminalTrueColorFormatter(
        style="monokai"
    )


def style_source(content: bytes, syntax: str) -> bytes:
    """Add ANSI around original lexer spans without Pygments preprocessing."""
    text = content.decode("utf-8")
    lexer, formatter = syntax_tools(syntax)
    tokens = list(lexer.get_tokens_unprocessed(text))
    if "".join(value for _, _, value in tokens) != text:
        raise ValueError("lexer did not preserve source spans")
    target = io.StringIO()
    formatter.format(((kind, value) for _, kind, value in tokens), target)
    return target.getvalue().encode("utf-8")


def markdown_parser() -> MarkdownIt:
    """Use the Markdown features supported by the pinned Rich renderer."""
    markdown_dependencies()
    return MarkdownIt().enable("strikethrough").enable("table")


def unresolved(tokens: list[Token]) -> bool:
    """Hold possible unresolved references, accepting conservative false positives."""
    return any(
        (t.type == "text" and "[" in t.content)
        or (t.children is not None and unresolved(t.children))
        for t in tokens
    )


def markdown_blocks(tokens: list[Token]) -> list[list[Token]]:
    """Group complete top-level blocks while retaining nested token context."""
    starts = [i for i, t in enumerate(tokens) if t.level == 0 and t.nesting >= 0 and t.map]
    return [tokens[start:end] for start, end in zip(starts, starts[1:] + [len(tokens)])]


def markdown_output(batches: Iterator[tuple[list[Token], Any]], output: BinaryIO) -> None:
    """Keep Rich context across blocks and publish each block transactionally."""
    markdown_dependencies()
    console = Console(force_terminal=True, color_system="truecolor", width=get_terminal_width())
    document = Markdown("")
    segments: list[Segment] = []

    def tokens() -> Iterator[Token]:
        for block, commit in batches:
            yield from block
            target = io.StringIO()
            sink = Console(
                file=target, force_terminal=True, color_system="truecolor", width=console.width
            )
            sink.print(Segments(segments), end="")
            write_bytes(output, target.getvalue().encode("utf-8"))
            segments.clear()
            commit()

    document.parsed = tokens()  # type: ignore[assignment]
    for segment in console.render(document):
        segments.append(segment)


def render_finite_markdown(content: bytes, output: BinaryIO) -> None:
    """Parse references once, then publish complete blocks progressively."""
    committed = 0
    try:
        text = content.decode("utf-8")
        lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)[:-1]
        ends = [0]
        for line in lines:
            ends.append(ends[-1] + len(line.encode("utf-8")))
        blocks = markdown_blocks(markdown_parser().parse(text))

        def batches() -> Iterator[tuple[list[Token], Any]]:
            for block in blocks:
                assert block[0].map is not None
                end = ends[block[0].map[1]]

                def commit(end: int = end) -> None:
                    nonlocal committed
                    committed = end

                yield block, commit

        markdown_output(batches(), output)
    except (BrokenPipeError, OSError):
        raise
    except Exception as exc:
        report(f"Markdown rendering failed; continuing with source: {exc}")
        write_bytes(output, RESET + content[committed:])


def render_live_markdown(chunks: Iterator[bytes | None], output: BinaryIO) -> None:
    """Render stable live blocks with bounded ambiguity and raw continuation."""
    pending = bytearray()
    arrivals: list[tuple[int, float]] = []
    oldest: float | None = None
    raw = False
    environment: dict[str, Any] = {}
    next_parse = 256

    def batches() -> Iterator[tuple[list[Token], Any]]:
        nonlocal oldest, raw, next_parse
        # Parsing at geometric sizes or structural boundaries avoids reparsing
        # an ever-growing single paragraph after every received line.
        for chunk in chunks:
            if raw:
                if chunk:
                    write_bytes(output, chunk)
                continue
            if chunk:
                if not pending:
                    oldest = time.monotonic()
                pending.extend(chunk)
                arrivals.append((len(chunk), time.monotonic()))
            if pending and (
                len(pending) >= PENDING_BYTES
                or (oldest is not None and time.monotonic() - oldest >= PENDING_SECONDS)
            ):
                report("live Markdown limit reached; remaining input is shown as source")
                write_bytes(output, RESET + bytes(pending))
                pending.clear()
                raw = True
                continue
            if not chunk or (len(pending) < next_parse and b"\n\n" not in chunk):
                continue
            next_parse = max(next_parse * 2, len(pending) * 2)
            try:
                text = pending.decode("utf-8")
            except UnicodeDecodeError as exc:
                if exc.reason == "unexpected end of data":
                    continue
                raise
            blocks = markdown_blocks(parser.parse(text, deepcopy(environment)))
            if len(blocks) < 2:
                continue
            # Reparse only the committed prefix. Definitions in an unfinished
            # suffix must not affect already-published reference links.
            assert blocks[-1][0].map is not None
            cut = blocks[-1][0].map[0]
            prefix = "".join(re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)[:cut])
            trial = deepcopy(environment)
            ready = parser.parse(prefix, trial)
            if unresolved(ready):
                continue
            consumed = len(prefix.encode("utf-8"))

            def commit() -> None:
                nonlocal oldest, next_parse
                del pending[:consumed]
                environment.clear()
                environment.update(trial)
                remaining = consumed
                while arrivals and remaining >= arrivals[0][0]:
                    count, _ = arrivals.pop(0)
                    remaining -= count
                if arrivals and remaining:
                    count, when = arrivals[0]
                    arrivals[0] = (count - remaining, when)
                oldest = arrivals[0][1] if arrivals else None
                next_parse = 256

            yield ready, commit
        if pending and not raw:
            tokens = parser.parse(pending.decode("utf-8"), environment)
            yield tokens, pending.clear

    try:
        parser = markdown_parser()
        markdown_output(batches(), output)
    except (BrokenPipeError, OSError):
        raise
    except Exception as exc:
        report(f"live Markdown rendering failed; continuing with source: {exc}")
        write_bytes(output, RESET + bytes(pending))
        for chunk in chunks:
            if chunk:
                write_bytes(output, chunk)


def render_stream(
    source: BinaryIO,
    output: BinaryIO,
    filename: str,
    forced: str | None = None,
    regular: bool = False,
) -> None:
    """Render a byte stream, preserving sampled input and raw recovery."""
    size = max(0, os.fstat(source.fileno()).st_size - source.tell()) if regular else None
    sample, complete = sample_input(source, regular, size)
    regular = regular or complete
    syntax = choose_format(filename, sample, forced)
    chunks = input_chunks(source, sample, None if size is None else size - len(sample), output)
    if syntax == "markdown":
        if regular:
            content = b"".join(chunk for chunk in chunks if chunk)
            render_finite_markdown(content, output)
        else:
            render_live_markdown(chunks, output)
        return
    if syntax == "text":
        for chunk in chunks:
            if chunk:
                write_bytes(output, chunk)
        return
    # JSONL records are independent lexical units. Other live languages may
    # contain multiline tokens; use source rather than reset their lexer per line.
    if not regular and syntax not in ("json", "jsonl"):
        for chunk in chunks:
            if chunk:
                write_bytes(output, chunk)
        return
    if regular and syntax != "jsonl":
        content = b"".join(chunk for chunk in chunks if chunk)
        # Tokenize once without the layout/padding overhead of Rich Syntax.
        if any(len(line) > MAX_SYNTAX_WIDTH for line in content.splitlines()):
            write_bytes(output, content)
            return
        committed = 0
        staged_source = 0
        staged = bytearray()
        text: str | None = None
        try:
            text = content.decode("utf-8")
            lexer = get_lexer_by_name(syntax)
            formatter = TerminalTrueColorFormatter(style="monokai")
            for position, kind, value in lexer.get_tokens_unprocessed(text):
                raw_unit = value.encode("utf-8")
                if (
                    content[committed + staged_source : committed + staged_source + len(raw_unit)]
                    != raw_unit
                ):
                    raise ValueError("lexer changed source spans")
                target = io.StringIO()
                formatter.format([(kind, value)], target)
                staged.extend(target.getvalue().encode("utf-8"))
                staged_source += len(raw_unit)
                if len(staged) >= (32768 if committed else 1024):
                    write_bytes(output, bytes(staged))
                    committed += staged_source
                    staged_source = 0
                    staged.clear()
            if staged:
                write_bytes(output, bytes(staged))
                committed += staged_source
            if committed != len(content):
                raise ValueError("lexer omitted source bytes")
        except (BrokenPipeError, OSError):
            raise
        except Exception as exc:
            report(f"syntax rendering failed; continuing with source: {exc}")
            write_bytes(output, RESET + content[committed:])
        return
    pending = bytearray()
    raw = False
    for chunk in chunks:
        if not chunk:
            continue
        if raw:
            write_bytes(output, chunk)
            continue
        pending.extend(chunk)
        while b"\n" in pending:
            end = pending.index(b"\n") + 1
            unit = bytes(pending[:end])
            try:
                # A JSON document split over lines is not a JSONL stream.
                prepared = style_source(unit, "json")
            except Exception:
                raw = True
                write_bytes(output, RESET + bytes(pending))
                pending.clear()
                break
            write_bytes(output, prepared)
            del pending[:end]
        if len(pending) >= PENDING_BYTES:
            write_bytes(output, RESET + bytes(pending))
            pending.clear()
            raw = True
    if pending:
        try:
            prepared = style_source(bytes(pending), "json") if not raw else bytes(pending)
        except Exception:
            prepared = RESET + bytes(pending)
        write_bytes(output, prepared)


def render_markdown(content: str) -> None:
    """Render finite Markdown progressively to standard output."""
    render_finite_markdown(content.encode("utf-8"), sys.stdout.buffer)


def get_syntax_width_and_overflow(content: str) -> tuple[int, bool]:
    """Retain the legacy width helper for existing callers."""
    width = max(MIN_SYNTAX_WIDTH, max((len(line) + 1 for line in content.splitlines()), default=0))
    if not content:
        width = MIN_SYNTAX_WIDTH + 1
    return min(width, MAX_SYNTAX_WIDTH), width > MAX_SYNTAX_WIDTH


def render_syntax(filepath: str, content: str) -> None:
    """Render a finite source string without changing source bytes."""
    syntax = choose_format(filepath, content.encode("utf-8"))
    write_bytes(
        sys.stdout.buffer,
        content.encode("utf-8")
        if syntax == "text"
        else style_source(content.encode("utf-8"), syntax),
    )


SHORT_OPERANDS = "bDhjkoOpPtTxyz"
LONG_OPERANDS = {
    "--buffers",
    "--color",
    "--max-back-scroll",
    "--jump-target",
    "--lesskey-file",
    "--log-file",
    "--LOG-FILE",
    "--pattern",
    "--prompt",
    "--PROMPT",
    "--tag",
    "--tag-file",
    "--shift",
    "--max-forw-scroll",
    "--window",
    "--header",
    "--rscroll",
    "--quotes",
    "--tabs",
    "--lesskey-src",
    "--intr",
}


def takes_native_operand(arg: str) -> bool:
    """Identify a separate native less option operand, including abbreviations."""
    if arg.startswith("--"):
        return "=" not in arg and any(option.startswith(arg) for option in LONG_OPERANDS)
    if arg.startswith("-"):
        for index, letter in enumerate(arg[1:]):
            if letter in SHORT_OPERANDS:
                return index == len(arg) - 2
    return False


def file_operands(arguments: list[str]) -> list[str]:
    """Find explicit source operands without interpreting native option values."""
    files: list[str] = []
    literal = False
    operand = False
    for arg in arguments:
        if operand:
            operand = False
        elif literal:
            files.append(arg)
        elif arg == "--":
            literal = True
        elif arg == "-" or not arg.startswith(("-", "+")):
            files.append(arg)
        else:
            operand = takes_native_operand(arg)
    return files


def native_options(arguments: list[str]) -> Iterator[str]:
    """Yield native option tokens outside operands and the literal-file suffix."""
    operand = False
    for arg in arguments:
        if operand:
            operand = False
        elif arg == "--":
            return
        elif arg.startswith("-") and arg != "-":
            yield arg
            operand = takes_native_operand(arg)


def color_override(options: list[str]) -> bool:
    """Respect explicit raw-control settings in the existing LESS environment."""
    for arg in native_options(options):
        if arg.lower() == "--raw-control-chars":
            return True
        if arg.startswith("--"):
            continue
        for letter in arg[1:]:
            if letter in "rR":
                return True
            if letter in SHORT_OPERANDS:
                break
    return False


def pager_arguments(arguments: list[str]) -> tuple[list[str], str | None, bool]:
    """Remove richless options without consuming native option operands."""
    result: list[str] = []
    forced: str | None = None
    follow = False
    operand = False
    literal = False
    i = 0
    while i < len(arguments):
        arg = arguments[i]
        i += 1
        if literal or operand:
            result.append(arg)
            operand = False
            continue
        if arg == "--":
            literal = True
        elif arg in ("--md", "--markdown") or arg == "--syntax" or arg.startswith("--syntax="):
            if arg in ("--md", "--markdown"):
                chosen = "markdown"
            elif arg.startswith("--syntax="):
                chosen = arg.partition("=")[2]
            else:
                if i == len(arguments):
                    raise ValueError("--syntax requires a language")
                chosen = arguments[i]
                i += 1
            if forced and forced != chosen:
                raise ValueError("conflicting format selections")
            if chosen != "markdown":
                get_lexer_by_name("json" if chosen == "jsonl" else chosen)
            forced = chosen
            continue
        elif arg == "+F":
            follow = True
        else:
            operand = takes_native_operand(arg)
        result.append(arg)
    return result, forced, follow


def command_prefix() -> list[str]:
    """Use the current interpreter and module across source and installed layouts."""
    return [sys.executable, str(Path(__file__).resolve())]


def follow_worker(filename: str, replacement: str, forced: str | None, by_name: bool) -> int:
    """Maintain a rendered snapshot and appended generations until terminated."""
    with (
        open(filename, "rb", buffering=0) as source,
        open(replacement, "wb", buffering=0) as output,
    ):
        sample = source.read(SAMPLE_BYTES)
        syntax = choose_format(filename, sample, forced)
        source.seek(0)
        render_stream(source, output, filename, syntax, regular=True)
        signal_ready()
        position = source.tell()
        identity = os.fstat(source.fileno())
        while os.getppid() == int(os.environ.get("RICHLESS_OWNER_PID", os.getppid())):
            time.sleep(0.1)
            current = os.fstat(source.fileno())
            replaced = False
            if by_name:
                try:
                    named = os.stat(filename)
                    replaced = (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino)
                except FileNotFoundError:
                    continue
            if replaced:
                source.close()
                source = open(filename, "rb", buffering=0)
                identity = os.fstat(source.fileno())
                current = identity
            if replaced or current.st_size < position:
                source.seek(0)
                output.seek(0)
                output.truncate()
                render_stream(source, output, filename, syntax, regular=True)
                position = source.tell()
            elif current.st_size > position:
                # The initial snapshot is immutable. Appends constitute a live
                # generation; the live renderer sees idle ticks until rotation.
                def appended() -> Iterator[bytes | None]:
                    nonlocal position
                    while os.getppid() == int(os.environ.get("RICHLESS_OWNER_PID", os.getppid())):
                        state = os.fstat(source.fileno())
                        if state.st_size < position:
                            return
                        if by_name:
                            try:
                                named = os.stat(filename)
                            except FileNotFoundError:
                                return
                            if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
                                return
                        chunk = source.read(SAMPLE_BYTES)
                        if chunk:
                            position += len(chunk)
                            yield chunk
                        else:
                            time.sleep(0.1)
                            yield None

                if syntax == "markdown":
                    render_live_markdown(appended(), output)
                else:
                    pending = bytearray()
                    raw = syntax not in ("jsonl", "json")
                    for chunk in appended():
                        if not chunk:
                            continue
                        if raw:
                            write_bytes(output, chunk)
                            continue
                        pending.extend(chunk)
                        while b"\n" in pending:
                            end = pending.index(b"\n") + 1
                            unit = bytes(pending[:end])
                            try:
                                prepared = style_source(unit, "json")
                            except Exception:
                                raw = True
                                write_bytes(output, RESET + bytes(pending))
                                pending.clear()
                                break
                            write_bytes(output, prepared)
                            del pending[:end]
                        if len(pending) >= PENDING_BYTES:
                            write_bytes(output, RESET + bytes(pending))
                            pending.clear()
                            raw = True
                    if pending:
                        write_bytes(output, bytes(pending))
    return 0


def follow_open(filename: str, close_path: str | None = None) -> int:
    """Ask the owning pager session for a native replacement pathname."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(os.environ["RICHLESS_SESSION_SOCKET"])
        request = {"file": filename}
        if close_path is not None:
            request["close"] = close_path
        connection.sendall(json.dumps(request).encode() + b"\n")
        response = connection.makefile("rb").readline()
        result = json.loads(response)
        if result.get("path"):
            print(result["path"], flush=True)
    return 0


def launch_pager(arguments: list[str]) -> int:
    """Launch one native pager and own its renderers and temporary follow files."""
    try:
        native, forced, follow = pager_arguments(arguments)
    except (ValueError, ClassNotFound) as exc:
        report(str(exc))
        return 2
    follow = follow and sys.stdout.isatty()
    files = file_operands(native)
    if follow:
        rendered_named = False
        for filename in files:
            try:
                if stat.S_ISREG(os.stat(filename).st_mode):
                    with open(filename, "rb") as source:
                        rendered_named |= (
                            choose_format(filename, source.read(SAMPLE_BYTES), forced) != "text"
                        )
            except OSError:
                pass
        follow = rendered_named
    pager = shutil.which("less")
    if not pager:
        report("less was not found")
        return 127
    environment = os.environ.copy()
    prefix = command_prefix()
    render_options = ["--md"] if forced == "markdown" else ["--syntax", forced] if forced else []
    # Defaults precede explicit command-line overrides. Existing LESS is intact.
    try:
        existing_options = shlex.split(environment.get("LESS", ""))
    except ValueError:
        existing_options = []
    command = [pager, *([] if color_override(existing_options) else ["-R"]), *native]
    by_name = any(
        arg.startswith("--follow-n") and "--follow-name".startswith(arg)
        for arg in native_options(native)
    )
    environment.pop("LESSCLOSE", None)
    environment["LESSOPEN"] = "|-" + shlex.join(prefix + ["--filter"] + render_options) + " -- %s"
    status_read, status_write = os.pipe()
    os.set_blocking(status_read, False)
    os.set_inheritable(status_write, True)
    environment["RICHLESS_STATUS_FD"] = str(status_write)
    children: list[subprocess.Popen[bytes]] = []
    owned_files: dict[str, str] = {}
    workers: dict[str, subprocess.Popen[bytes]] = {}
    retired: set[subprocess.Popen[bytes]] = set()
    stream_files: dict[str, str] = {}
    inherited = [status_write]
    stream_readers: list[IO[bytes]] = []
    pager_input: IO[bytes] | None = None
    stop = threading.Event()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    socket_temporary: tempfile.TemporaryDirectory[str] | None = None
    server: socket.socket | None = None
    server_thread: threading.Thread | None = None
    process: subprocess.Popen[bytes] | None = None
    old_term = signal.getsignal(signal.SIGTERM)
    old_hup = signal.getsignal(signal.SIGHUP)
    old_int = signal.getsignal(signal.SIGINT)

    def terminate(signum: int, frame: Any) -> None:
        if process is not None:
            process.terminate()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    # Native less owns terminal interrupts. A callable handler is reset by exec
    # in the child, unlike SIG_IGN, and also covers gaps between wait() calls.
    signal.signal(signal.SIGINT, lambda signum, frame: None)
    try:
        if follow:
            temporary = tempfile.TemporaryDirectory(prefix="richless-follow-")
            directory = Path(temporary.name)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            socket_path = str(directory / "control")
            if len(os.fsencode(socket_path)) >= 100:
                socket_temporary = tempfile.TemporaryDirectory(prefix="rl-", dir="/tmp")
                socket_path = str(Path(socket_temporary.name) / "control")
            server.bind(socket_path)
            server.listen()
            server.settimeout(0.1)
            environment["RICHLESS_SESSION_SOCKET"] = socket_path
            environment["LESSOPEN"] = shlex.join(prefix + ["--follow-open"]) + " -- %s"
            environment["LESSCLOSE"] = shlex.join(prefix + ["--follow-close"]) + " -- %s %s"
            environment["RICHLESS_OWNER_PID"] = str(os.getpid())

            def serve() -> None:
                assert server is not None
                while not stop.is_set():
                    try:
                        connection, _ = server.accept()
                    except TimeoutError:
                        continue
                    except OSError:
                        return
                    with connection:
                        try:
                            request = json.loads(connection.makefile("rb").readline(65536))
                            filename = request["file"]
                            alternate = stream_files.get(filename, "")
                            if "close" in request:
                                if owned_files.get(filename) == request["close"]:
                                    worker = workers.pop(filename)
                                    retired.add(worker)
                                    worker.terminate()
                                    worker.wait(timeout=2)
                                    os.unlink(owned_files.pop(filename))
                                connection.sendall(b'{"path": ""}\n')
                                continue
                            info = os.stat(filename)
                            if stat.S_ISREG(info.st_mode):
                                with open(filename, "rb") as source:
                                    syntax = choose_format(
                                        filename, source.read(SAMPLE_BYTES), forced
                                    )
                                if syntax != "text":
                                    if filename not in owned_files:
                                        fd, alternate = tempfile.mkstemp(
                                            prefix="view-", dir=directory
                                        )
                                        os.close(fd)
                                        ready_read, ready_write = os.pipe()
                                        worker_environment = environment | {
                                            "RICHLESS_READY_FD": str(ready_write)
                                        }
                                        worker = subprocess.Popen(
                                            prefix
                                            + [
                                                "--follow-worker",
                                                filename,
                                                alternate,
                                                syntax,
                                                "name" if by_name else "descriptor",
                                            ],
                                            stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL,
                                            env=worker_environment,
                                            pass_fds=(status_write, ready_write),
                                            start_new_session=True,
                                        )
                                        os.close(ready_write)
                                        children.append(worker)
                                        ready = False
                                        try:
                                            while not stop.is_set():
                                                if select.select([ready_read], [], [], 0.05)[0]:
                                                    ready = os.read(ready_read, 1) == b"R"
                                                    break
                                                if worker.poll() is not None:
                                                    break
                                        finally:
                                            os.close(ready_read)
                                        if not ready:
                                            retired.add(worker)
                                            worker.terminate()
                                            worker.wait(timeout=2)
                                            os.unlink(alternate)
                                            connection.sendall(b'{"path": ""}\n')
                                            report("follow preparation failed; using original file")
                                            continue
                                        workers[filename] = worker
                                        owned_files[filename] = alternate
                                    alternate = owned_files[filename]
                            connection.sendall(json.dumps({"path": alternate}).encode() + b"\n")
                        except (OSError, ValueError, KeyError) as exc:
                            report(f"cannot prepare follow view; using original file: {exc}")
                            try:
                                connection.sendall(b'{"path": ""}\n')
                            except OSError:
                                pass

            # A non-pipe LESSOPEN handles named replacement files. Feed stdin and
            # startup FIFOs through inherited OS pipes instead of disk spools.
            streaming = []
            if not sys.stdin.isatty() and (not files or "-" in files):
                streaming.append("-")
            for filename in files:
                try:
                    if filename != "-" and stat.S_ISFIFO(os.stat(filename).st_mode):
                        streaming.append(filename)
                except OSError:
                    pass
            for filename in dict.fromkeys(streaming):
                child = subprocess.Popen(
                    prefix + render_options + ["--", filename],
                    stdout=subprocess.PIPE,
                    env=environment,
                    pass_fds=(status_write,),
                    start_new_session=True,
                )
                children.append(child)
                assert child.stdout is not None
                stream_readers.append(child.stdout)
                if filename == "-":
                    pager_input = child.stdout
                else:
                    descriptor = child.stdout.fileno()
                    os.set_inheritable(descriptor, True)
                    inherited.append(descriptor)
                    stream_files[filename] = f"/dev/fd/{descriptor}"

            server_thread = threading.Thread(target=serve, daemon=True)
            server_thread.start()
        process = subprocess.Popen(
            command, stdin=pager_input, env=environment, pass_fds=tuple(inherited)
        )
        for reader in stream_readers:
            reader.close()
        stream_readers.clear()
        notified: set[subprocess.Popen[bytes]] = set()
        while True:
            try:
                result = process.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                failed_children = {
                    child
                    for child in children
                    if child not in retired
                    and child not in notified
                    and child.poll() not in (None, 0)
                }
                if failed_children:
                    notified.update(failed_children)
                    report(
                        "a follow renderer stopped; reopen the original file with command less",
                        fatal=True,
                    )
        try:
            failed = bool(os.read(status_read, 4096))
        except BlockingIOError:
            failed = False
        return result if result else int(failed)
    except OSError as exc:
        if process is None and not children:
            report(f"follow setup failed; using original input: {exc}")
            return subprocess.call(command, env=environment | {"LESSOPEN": "", "LESSCLOSE": ""})
        report(str(exc), fatal=True)
        return 1
    finally:
        stop.set()
        for reader in stream_readers:
            reader.close()
        if server_thread:
            server_thread.join(timeout=3)
        if server:
            server.close()
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        for child in children:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if temporary:
            temporary.cleanup()
        if socket_temporary:
            socket_temporary.cleanup()
        os.close(status_read)
        os.close(status_write)
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGHUP, old_hup)
        signal.signal(signal.SIGINT, old_int)


def main() -> int:
    """Render files or launch the native pager with richless integration."""
    if len(sys.argv) > 1 and sys.argv[1] in ("--follow-open", "--follow-close"):
        try:
            return (
                follow_open(sys.argv[-2], sys.argv[-1])
                if sys.argv[1] == "--follow-close"
                else follow_open(sys.argv[-1])
            )
        except KeyboardInterrupt:
            return 130
        except (OSError, ValueError, KeyError) as exc:
            report(f"follow integration unavailable: {exc}")
            return 1
    if len(sys.argv) > 1 and sys.argv[1] == "--follow-worker":
        try:
            return follow_worker(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "name")
        except OSError as exc:
            report(f"follow renderer failed: {exc}", fatal=True)
            return 1
    if len(sys.argv) > 1 and sys.argv[1] == "--pager":
        try:
            return launch_pager(sys.argv[2:])
        except KeyboardInterrupt:
            return 130
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filter", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--md", "--markdown", action="store_true")
    parser.add_argument("--syntax")
    parser.add_argument("--init-path", action="store_true")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args()
    if args.init_path:
        candidates = [
            Path(__file__).with_name("richless-init.sh"),
            Path(sys.prefix) / "share" / "richless" / "richless-init.sh",
        ]
        for candidate in candidates:
            if candidate.is_file():
                print(candidate)
                return 0
        parser.error("installed integration script was not found")
    if args.file is None:
        parser.error("a file or - is required")
    if args.md and args.syntax:
        parser.error("--md and --syntax cannot be combined")
    forced = "markdown" if args.md else args.syntax
    if forced and forced != "markdown":
        try:
            get_lexer_by_name("json" if forced == "jsonl" else forced)
        except ClassNotFound as exc:
            parser.error(str(exc))
    try:
        if args.file in ("-", "/dev/stdin"):
            render_stream(sys.stdin.buffer, sys.stdout.buffer, args.file, forced)
        else:
            with open(args.file, "rb", buffering=0) as source:
                regular = stat.S_ISREG(os.fstat(source.fileno()).st_mode)
                if regular and args.filter:
                    sample = source.read(SAMPLE_BYTES)
                    if choose_format(args.file, sample, forced) == "text":
                        return 0
                    source.seek(0)
                render_stream(source, sys.stdout.buffer, args.file, forced, regular)
        return 0
    except BrokenPipeError:
        os._exit(0)
    except KeyboardInterrupt:
        os._exit(130)
    except FileNotFoundError:
        report(f"File not found: {args.file}", fatal=True)
        return 1
    except OSError as exc:
        report(str(exc), fatal=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
