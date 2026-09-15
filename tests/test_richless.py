"""
Unit tests for richless.

Run with: uv run pytest tests/test_richless.py -v
"""

import contextlib
import errno
import fcntl
import hashlib
import importlib.metadata
import json
import os
import platform
import pty
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import has_ansi_colors, has_markdown_formatting, has_multiple_colors

from richless import (
    MAX_SYNTAX_WIDTH,
    MIN_SYNTAX_WIDTH,
    detect_syntax_from_content,
    get_syntax_width_and_overflow,
    is_markdown_file,
)


def ansi_test_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build test subprocess environment with ANSI colors enabled."""
    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    env.setdefault("TERM", "xterm-256color")
    if extra:
        env.update(extra)
    return env


class TestIsMarkdownFile:
    """Tests for is_markdown_file() function."""

    def test_md_extension(self):
        assert is_markdown_file("test.md") is True
        assert is_markdown_file("README.md") is True

    def test_md_extension_case_insensitive(self):
        assert is_markdown_file("TEST.MD") is True
        assert is_markdown_file("test.Md") is True

    def test_markdown_extension(self):
        assert is_markdown_file("test.markdown") is True
        assert is_markdown_file("TEST.MARKDOWN") is True

    def test_yaml_not_markdown(self):
        assert is_markdown_file("test.yaml") is False
        assert is_markdown_file("test.yml") is False

    def test_json_not_markdown(self):
        assert is_markdown_file("test.json") is False
        assert is_markdown_file("test.jsonl") is False

    def test_code_not_markdown(self):
        assert is_markdown_file("test.py") is False
        assert is_markdown_file("test.js") is False
        assert is_markdown_file("test.sh") is False

    def test_no_extension(self):
        assert is_markdown_file("README") is False
        assert is_markdown_file("Makefile") is False


class TestDetectSyntaxFromContent:
    """Tests for detect_syntax_from_content() function."""

    # YAML detection
    def test_yaml_document_start(self):
        assert detect_syntax_from_content("---\nname: test\n") == "yaml"

    def test_yaml_explicit_tag(self):
        assert detect_syntax_from_content("%YAML 1.2\n---\nname: test") == "yaml"

    def test_yaml_with_comments(self):
        content = """#
# This is a comment header
# More comments
#

name: test-config
version: 1.0
"""
        assert detect_syntax_from_content(content) == "yaml"

    def test_yaml_key_value(self):
        content = "name: test\nversion: 1.0\n"
        assert detect_syntax_from_content(content) == "yaml"

    # JSON detection
    def test_json_object(self):
        assert detect_syntax_from_content('{"key": "value"}') == "json"

    def test_json_object_with_whitespace(self):
        assert detect_syntax_from_content('  {"key": "value"}') == "json"

    def test_json_array(self):
        assert detect_syntax_from_content("[1, 2, 3]") == "json"

    def test_json_array_with_whitespace(self):
        assert detect_syntax_from_content("  [1, 2, 3]") == "json"

    # Shebang detection
    def test_python_shebang(self):
        assert detect_syntax_from_content("#!/usr/bin/env python3\nprint('hi')") == "python"
        assert detect_syntax_from_content("#!/usr/bin/python\nprint('hi')") == "python"

    def test_bash_shebang(self):
        assert detect_syntax_from_content("#!/bin/bash\necho hi") == "bash"
        assert detect_syntax_from_content("#!/usr/bin/env bash\necho hi") == "bash"

    def test_sh_shebang(self):
        assert detect_syntax_from_content("#!/bin/sh\necho hi") == "bash"

    def test_node_shebang(self):
        assert detect_syntax_from_content("#!/usr/bin/env node\nconsole.log('hi')") == "javascript"

    def test_ruby_shebang(self):
        assert detect_syntax_from_content("#!/usr/bin/env ruby\nputs 'hi'") == "ruby"

    def test_perl_shebang(self):
        assert detect_syntax_from_content("#!/usr/bin/perl\nprint 'hi'") == "perl"

    # XML detection
    def test_xml_declaration(self):
        assert detect_syntax_from_content('<?xml version="1.0"?>\n<root/>') == "xml"

    def test_doctype(self):
        assert detect_syntax_from_content("<!DOCTYPE html>\n<html>") == "xml"

    # TOML detection
    def test_toml_section_header(self):
        assert detect_syntax_from_content('[server]\nhost = "localhost"\n') == "toml"

    def test_toml_array_header(self):
        assert detect_syntax_from_content('[[users]]\nname = "alice"\n') == "toml"

    def test_toml_key_value(self):
        content = 'name = "myapp"\nversion = "1.0"\n'
        assert detect_syntax_from_content(content) == "toml"

    def test_toml_with_comments(self):
        content = """# Configuration file
# for the application

[server]
host = "localhost"
port = 8080
"""
        assert detect_syntax_from_content(content) == "toml"

    def test_toml_single_key_value(self):
        """Even a single key = value line should detect as TOML."""
        assert detect_syntax_from_content('name = "test"\n') == "toml"

    # JSONL detection (single-line JSON objects)
    def test_jsonl_content(self):
        content = '{"ts":1427846411.876987,"uid":"C1ck9l41y7i2i3gGo2"}\n{"ts":1427846411.877008}\n'
        assert detect_syntax_from_content(content) == "json"

    # Plain text fallback
    def test_plain_text(self):
        assert detect_syntax_from_content("Just some plain text") == "text"

    def test_empty_content(self):
        assert detect_syntax_from_content("") == "text"

    def test_whitespace_only(self):
        assert detect_syntax_from_content("   \n\n   ") == "text"


class TestSyntaxWidthSafety:
    """Tests for syntax width clamp and overflow behavior."""

    def test_width_uses_minimum_for_empty_content(self):
        width, exceeds_cap = get_syntax_width_and_overflow("")
        assert width == MIN_SYNTAX_WIDTH + 1
        assert exceeds_cap is False

    def test_width_is_based_on_longest_line_when_under_cap(self):
        content = "short\n" + ("x" * 200)
        width, exceeds_cap = get_syntax_width_and_overflow(content)
        assert width == 201
        assert exceeds_cap is False

    def test_width_clamps_at_upper_bound(self):
        content = "x" * MAX_SYNTAX_WIDTH
        width, exceeds_cap = get_syntax_width_and_overflow(content)
        assert width == MAX_SYNTAX_WIDTH
        assert exceeds_cap is True

    def test_width_clamps_when_line_exceeds_upper_bound(self):
        content = "x" * (MAX_SYNTAX_WIDTH + 1000)
        width, exceeds_cap = get_syntax_width_and_overflow(content)
        assert width == MAX_SYNTAX_WIDTH
        assert exceeds_cap is True


class TestIntegration:
    """Integration tests that run richless as a subprocess."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def run_richless(self, *args) -> str:
        """Run richless command and return output."""
        result = subprocess.run(
            ["richless", *args],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        return result.stdout + result.stderr

    # Markdown tests
    def test_markdown_file_renders_as_markdown(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.md"))
        assert has_markdown_formatting(output), "Markdown file should have Rich formatting"

    def test_force_markdown_flag(self):
        output = self.run_richless("--md", str(self.FIXTURES_DIR / "test.yaml"))
        assert has_markdown_formatting(output), "--md flag should force markdown rendering"

    # YAML tests
    def test_yaml_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.yaml"))
        assert has_multiple_colors(output), "YAML file should have syntax highlighting"
        assert not has_markdown_formatting(output), "YAML file should NOT have markdown formatting"

    def test_yaml_with_comments_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert has_multiple_colors(output), "YAML with comments should have syntax highlighting"
        assert not has_markdown_formatting(output), (
            "YAML with comments should NOT have markdown formatting"
        )

    def test_yaml_filename_with_dash_m(self):
        """Filenames containing -m should not trigger --md flag."""
        output = self.run_richless(str(self.FIXTURES_DIR / "test-mcp-config.yaml"))
        assert has_multiple_colors(output), "File with -m in name should have syntax highlighting"
        assert not has_markdown_formatting(output), (
            "File with -m in name should NOT trigger markdown"
        )

    # JSON tests
    def test_json_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.json"))
        assert has_multiple_colors(output), "JSON file should have syntax highlighting"

    def test_jsonl_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.jsonl"))
        assert has_multiple_colors(output), "JSONL file should have syntax highlighting"

    # Code file tests
    def test_python_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.py"))
        assert has_multiple_colors(output), "Python file should have syntax highlighting"

    def test_shell_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.sh"))
        assert has_multiple_colors(output), "Shell file should have syntax highlighting"

    def test_toml_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.toml"))
        assert has_multiple_colors(output), "TOML file should have syntax highlighting"
        assert not has_markdown_formatting(output), "TOML file should NOT have markdown formatting"

    def test_xml_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.xml"))
        assert has_multiple_colors(output), "XML file should have syntax highlighting"

    def test_js_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.js"))
        assert has_multiple_colors(output), "JavaScript file should have syntax highlighting"

    def test_ruby_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.rb"))
        assert has_multiple_colors(output), "Ruby file should have syntax highlighting"

    def test_perl_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.pl"))
        assert has_multiple_colors(output), "Perl file should have syntax highlighting"

    def test_html_file_syntax_highlighting(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.html"))
        assert has_multiple_colors(output), "HTML file should have syntax highlighting"

    def test_txt_file_no_crash(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.txt"))
        assert "This is just plain text" in output, "Plain text file should pass through content"

    # Log file tests (unrecognized extension, falls back to content detection)
    def test_log_file_with_jsonl_content(self):
        output = self.run_richless(str(self.FIXTURES_DIR / "test.log"))
        assert has_multiple_colors(output), (
            ".log file with JSONL content should have syntax highlighting"
        )
        assert not has_markdown_formatting(output), ".log file should NOT have markdown formatting"


class TestTempFileDetection:
    """Tests for content detection on temp files (like from shell wrapper)."""

    def test_temp_file_with_json_content(self, tmp_path):
        """Temp files named richless.XXXXX should use content detection."""
        temp_file = tmp_path / "richless.abc123"
        temp_file.write_text('{"key": "value"}\n')

        result = subprocess.run(
            ["richless", str(temp_file)],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        output = result.stdout + result.stderr
        assert has_multiple_colors(output), "JSON temp file should have syntax highlighting"

    def test_temp_file_with_yaml_content(self, tmp_path):
        """Temp files with YAML content should be detected."""
        temp_file = tmp_path / "richless.xyz789"
        temp_file.write_text("---\nname: test\nvalue: 123\n")

        result = subprocess.run(
            ["richless", str(temp_file)],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        output = result.stdout + result.stderr
        assert has_multiple_colors(output), "YAML temp file should have syntax highlighting"

    def test_temp_file_with_toml_content(self, tmp_path):
        """Temp files with TOML content should be detected."""
        temp_file = tmp_path / "richless.toml42"
        temp_file.write_text('[server]\nhost = "localhost"\nport = 8080\n')

        result = subprocess.run(
            ["richless", str(temp_file)],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        output = result.stdout + result.stderr
        assert has_multiple_colors(output), "TOML temp file should have syntax highlighting"


class TestLessOpenIntegration:
    """Tests for LESSOPEN integration (less <file>)."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def run_less_with_lessopen(self, filepath: str) -> str:
        """Run less with LESSOPEN set to use richless."""
        result = subprocess.run(
            ["less", "-R", filepath],
            capture_output=True,
            text=True,
            env=ansi_test_env({"LESSOPEN": "|richless %s"}),
        )
        return result.stdout + result.stderr

    def test_markdown_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.md"))
        assert has_markdown_formatting(output), "Markdown should have Rich formatting via LESSOPEN"

    def test_yaml_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.yaml"))
        assert has_multiple_colors(output), "YAML should have syntax highlighting via LESSOPEN"
        assert not has_markdown_formatting(output), "YAML should not have markdown formatting"

    def test_yaml_with_comments_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert has_multiple_colors(output), "YAML with comments should have syntax highlighting"

    def test_json_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.json"))
        assert has_multiple_colors(output), "JSON should have syntax highlighting via LESSOPEN"

    def test_jsonl_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.jsonl"))
        assert has_multiple_colors(output), "JSONL should have syntax highlighting via LESSOPEN"

    def test_filename_with_dash_m_via_lessopen(self):
        """Filenames containing -m should not trigger --md flag."""
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test-mcp-config.yaml"))
        assert has_multiple_colors(output), "File with -m in name should have syntax highlighting"
        assert not has_markdown_formatting(output), "File with -m should NOT trigger markdown"

    def test_toml_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.toml"))
        assert has_multiple_colors(output), "TOML should have syntax highlighting via LESSOPEN"
        assert not has_markdown_formatting(output), "TOML should not have markdown formatting"

    def test_xml_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.xml"))
        assert has_multiple_colors(output), "XML should have syntax highlighting via LESSOPEN"

    def test_python_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.py"))
        assert has_multiple_colors(output), "Python should have syntax highlighting via LESSOPEN"

    def test_shell_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.sh"))
        assert has_multiple_colors(output), "Shell should have syntax highlighting via LESSOPEN"

    def test_js_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.js"))
        assert has_multiple_colors(output), (
            "JavaScript should have syntax highlighting via LESSOPEN"
        )


class TestPipedInputDetection:
    """Tests for piped input content detection (simulates cat <file> | less).

    These tests invoke the actual shell wrapper from richless-init.sh to ensure
    the detection logic is tested end-to-end rather than reimplemented in Python.
    """

    FIXTURES_DIR = Path(__file__).parent / "fixtures"
    PROJECT_DIR = Path(__file__).parent.parent

    def run_piped(self, filepath: str) -> str:
        """Pipe file content through the actual shell wrapper."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{self.PROJECT_DIR}/richless-init.sh" && cat "{filepath}" | less',
            ],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        return result.stdout + result.stderr

    def test_piped_yaml(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.yaml"))
        assert has_multiple_colors(output), "Piped YAML should have syntax highlighting"
        assert not has_markdown_formatting(output), "Piped YAML should not have markdown formatting"

    def test_piped_yaml_with_comments(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert has_multiple_colors(output), (
            "Piped YAML with comments should have syntax highlighting"
        )
        assert not has_markdown_formatting(output), (
            "Piped YAML with comments should not be markdown"
        )

    def test_piped_json(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.json"))
        assert has_multiple_colors(output), "Piped JSON should have syntax highlighting"

    def test_piped_jsonl(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.jsonl"))
        assert has_multiple_colors(output), "Piped JSONL should have syntax highlighting"

    def test_piped_markdown(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.md"))
        assert has_markdown_formatting(output), "Piped Markdown should have Rich formatting"

    def test_piped_toml(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.toml"))
        assert has_multiple_colors(output), "Piped TOML should have syntax highlighting"
        assert not has_markdown_formatting(output), "Piped TOML should not have markdown formatting"

    def test_piped_python(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.py"))
        assert has_multiple_colors(output), "Piped Python should have syntax highlighting"

    def test_piped_shell(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.sh"))
        assert has_multiple_colors(output), "Piped Shell should have syntax highlighting"

    def test_piped_xml(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.xml"))
        assert has_multiple_colors(output), "Piped XML should have syntax highlighting"

    def test_piped_plain_text(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.txt"))
        assert "This is just plain text" in output, "Piped plain text should pass through"


class TestErrorHandling:
    """Tests for error handling and exit codes."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def test_missing_file_returns_exit_code_1(self):
        result = subprocess.run(
            ["richless", "/nonexistent/file.py"],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 1
        assert "File not found" in result.stderr

    def test_empty_file_does_not_crash(self, tmp_path):
        empty = tmp_path / "empty.py"
        empty.write_text("")
        result = subprocess.run(
            ["richless", str(empty)],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0

    def test_binary_file_does_not_crash(self, tmp_path):
        binfile = tmp_path / "data.bin"
        binfile.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")
        result = subprocess.run(
            ["richless", str(binfile)],
            capture_output=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0
        assert result.stdout == binfile.read_bytes()

    def test_successful_render_returns_exit_code_0(self):
        result = subprocess.run(
            ["richless", str(self.FIXTURES_DIR / "test.py")],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0

    def test_extremely_long_line_falls_back_to_raw_output(self, tmp_path):
        long_line_file = tmp_path / "longline.py"
        long_line = "x" * (MAX_SYNTAX_WIDTH + 1000)
        long_line_file.write_text(long_line + "\n")

        result = subprocess.run(
            ["richless", str(long_line_file)],
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )

        assert result.returncode == 0
        assert result.stdout == long_line + "\n"
        assert not has_ansi_colors(result.stdout), (
            "Fallback output should be raw text without ANSI codes"
        )


class TestStdinInput:
    """Tests for reading from stdin via - or /dev/stdin."""

    def test_stdin_dash_with_python_content(self):
        result = subprocess.run(
            ["richless", "-"],
            input='def hello():\n    return "world"\n',
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0
        assert result.stdout == 'def hello():\n    return "world"\n', (
            "Unmarked ambiguous source remains raw"
        )

    def test_stdin_dash_with_force_markdown(self):
        result = subprocess.run(
            ["richless", "--md", "-"],
            input="# Hello\n\nThis is **bold** text.\n\n- item 1\n- item 2\n",
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0
        # Rich renders bold as \x1b[1m and headings with underline
        assert has_markdown_formatting(result.stdout) or "\x1b[1m" in result.stdout, (
            "Markdown via --md stdin should have formatting"
        )

    def test_stdin_dev_stdin(self):
        result = subprocess.run(
            ["richless", "/dev/stdin"],
            input='{"key": "value"}\n',
            capture_output=True,
            text=True,
            env=ansi_test_env(),
        )
        assert result.returncode == 0
        assert has_multiple_colors(result.stdout), (
            "JSON via /dev/stdin should have syntax highlighting"
        )


# Required workflow regressions; historical results remain under audit/results.
AUDIT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SHELLS = ["bash", "zsh", "sh"]
AUDIT_MODES = ["plain", "filter", "wrapper"]


def audit_text(data: bytes) -> str:
    """Remove terminal control sequences for content assertions, not screen emulation."""
    return re.sub(
        r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07)|[()][A-Z0-9]|[=>])",
        "",
        data.decode("utf-8", "replace"),
    ).replace("\r", "")


def audit_has_syntax_colors(output: str) -> bool:
    """Require multiple foreground colors, excluding the pager's bold/inverse UI."""
    colors = set()
    for sgr in re.findall(r"\x1b\[([0-9;]+)m", output):
        match = re.search(r"(?:^|;)38;(?:2;\d+;\d+;\d+|5;\d+)", sgr)
        if match:
            colors.add(match.group(0).lstrip(";"))
    return len(colors) >= 2


@pytest.fixture
def workflow_audit(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[dict]:
    """Create an isolated environment and persist checks even when assertions fail."""
    destination = os.environ.get("RICHLESS_AUDIT_DIR", str(tmp_path / "evidence"))
    out = Path(destination).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    launcher = bindir / "richless"
    launcher.write_text(
        "#!/bin/sh\nexec "
        + shlex.quote(sys.executable)
        + " "
        + shlex.quote(str(AUDIT_ROOT / "richless.py"))
        + ' "$@"\n'
    )
    launcher.chmod(0o755)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = {
        "PATH": str(bindir) + os.pathsep + "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
        "HOME": str(tmp_path),
        "TMPDIR": str(scratch),
        "TERM": "xterm-256color",
        "LC_ALL": "C",
        "LESSCHARSET": "utf-8",
        "LESSHISTFILE": "-",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    item = {
        "id": request.node.name,
        "checks": [],
        "observations": [],
        "commands": [],
        "sessions": [],
        "env": env,
        "cwd": str(tmp_path),
        "root": str(AUDIT_ROOT),
    }
    metadata = {
        "platform": platform.platform(),
        "python": sys.version,
        "packages": {p: importlib.metadata.version(p) for p in ["rich", "pygments", "pytest"]},
        "shells": {
            s: {
                "path": shutil.which(s),
                "resolved": os.path.realpath(shutil.which(s) or s),
                "version": subprocess.run(
                    [
                        shutil.which(s),
                        "-c",
                        'printf "%s %s\\n" "${BASH_VERSION-}" "${ZSH_VERSION-}"',
                    ],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                if shutil.which(s)
                else None,
            }
            for s in AUDIT_SHELLS
        },
        "shell_package_versions": subprocess.run(
            ["dpkg-query", "-W", "bash", "zsh", "dash", "less"], capture_output=True, text=True
        ).stdout
        if shutil.which("dpkg-query")
        else None,
        "less": subprocess.run(["less", "--version"], capture_output=True, text=True).stdout,
        "source_sha256": {
            p: hashlib.sha256((AUDIT_ROOT / p).read_bytes()).hexdigest()
            for p in ["richless.py", "richless-init.sh", "tests/test_richless.py"]
        },
    }
    (out / "environment.json").write_text(json.dumps(metadata, indent=2))
    try:
        yield item
    except BaseException as exc:
        item["exception"] = repr(exc)
        raise
    finally:
        item["status"] = (
            "fail"
            if any(not c["pass"] for c in item["checks"])
            else "blocked"
            if "exception" in item or not item["checks"]
            else "pass"
        )
        if "product_decision" in item and item["status"] == "pass":
            item["status"] = "needs product decision"
        name = re.sub(r"[^a-zA-Z0-9_.-]", "_", item["id"])
        # Keep case-distinct scenario IDs distinct on case-insensitive filesystems.
        name += "-" + hashlib.sha256(item["id"].encode()).hexdigest()[:12]
        (out / (name + ".json")).write_text(json.dumps(item, indent=2, ensure_ascii=True))


def audit_check(item: dict, condition: bool, expectation: str) -> None:
    """Record an expectation without suppressing subsequent evidence collection."""
    item["checks"].append({"expectation": expectation, "pass": bool(condition)})


def audit_finish(item: dict) -> None:
    """Fail the scenario if any of its recorded expectations were unmet."""
    assert all(c["pass"] for c in item["checks"]), [
        c["expectation"] for c in item["checks"] if not c["pass"]
    ]


def audit_command(item: dict, shell: str, mode: str, invocation: str) -> list[str]:
    """Build a real shell invocation with an explicitly selected integration path."""
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} unavailable")
    prefix = ""
    if mode == "filter":
        prefix = "export LESSOPEN='|-richless --filter -- %s'; "
    elif mode == "wrapper":
        prefix = ". " + shlex.quote(str(AUDIT_ROOT / "richless-init.sh")) + "; "
    command = [executable, "-c", prefix + invocation]
    item["commands"].append(command)
    return command


def audit_capture(
    item: dict, command: list[str], data: bytes | None = None, timeout: float = 15
) -> subprocess.CompletedProcess:
    """Capture channels separately and terminate the process group on timeout."""
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=item["cwd"],
        env=item["env"],
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(data, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
        item["observations"].append({"timeout": timeout})
    result = subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    item["observations"].append(
        {
            "command": command,
            "returncode": proc.returncode,
            "seconds": time.monotonic() - started,
            "stdout": stdout.decode("utf-8", "replace")[:20000],
            "stderr": stderr.decode("utf-8", "replace")[:20000],
            "stdout_bytes": len(stdout),
        }
    )
    return result


@contextlib.contextmanager
def audit_terminal(item: dict, command: list[str], piped: bool = False) -> Iterator[dict]:
    """Run a controlling PTY with optional independently writable piped stdin."""
    read_fd, write_fd = os.pipe() if piped else (-1, -1)
    pid, fd = pty.fork()
    if pid == 0:
        try:
            if piped:
                os.close(write_fd)
                os.dup2(read_fd, 0)
                os.close(read_fd)
            os.chdir(item["cwd"])
            os.execvpe(command[0], command, item["env"])
        finally:
            os._exit(127)
    if piped:
        os.close(read_fd)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
    original = termios.tcgetattr(fd)
    session = {
        "pid": pid,
        "fd": fd,
        "writer": write_fd,
        "data": b"",
        "events": [],
        "started": time.monotonic(),
        "reaped": False,
        "original_termios": original,
    }
    try:
        yield session
    finally:
        if session["writer"] >= 0:
            os.close(session["writer"])
            session["writer"] = -1
        # Retain terminal settings before forcibly cleaning up any failed session.
        session["terminal_restored"] = termios.tcgetattr(fd) == original
        audit_drain(session, 0.05)
        audit_exited(session, 0.05)
        if not session["reaped"]:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if not session["reaped"]:
            _, status, usage = os.wait4(pid, 0)
            session["exitcode"] = os.waitstatus_to_exitcode(status)
            session["maxrss_native"] = usage.ru_maxrss
        os.close(fd)
        item["sessions"].append(
            {
                k: v
                for k, v in session.items()
                if k not in ["fd", "writer", "pid", "data", "original_termios"]
            }
        )
        item["sessions"][-1]["transcript"] = session["data"].decode("utf-8", "replace")[:200000]
        item["sessions"][-1]["transcript_bytes"] = len(session["data"])
        if len(session["data"]) > 200000:
            item["sessions"][-1]["transcript_tail"] = session["data"][-20000:].decode(
                "utf-8", "replace"
            )


def audit_drain(session: dict, timeout: float) -> None:
    """Read all currently available terminal output within a bounded interval."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([session["fd"]], [], [], max(0, deadline - time.monotonic()))
        if not ready:
            break
        try:
            chunk = os.read(session["fd"], 65536)
        except OSError as exc:
            if exc.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        session["data"] += chunk


def audit_expect(session: dict, token: str, since: int = 0, timeout: float = 3) -> bool:
    """Wait for a content marker in fresh terminal output."""
    deadline = time.monotonic() + timeout
    while token not in audit_text(session["data"][since:]) and time.monotonic() < deadline:
        audit_drain(session, min(0.05, max(0, deadline - time.monotonic())))
    found = token in audit_text(session["data"][since:])
    session["events"].append(
        {"expect": token, "found": found, "seconds": time.monotonic() - session["started"]}
    )
    return found


def audit_send(session: dict, keys: bytes) -> int:
    """Send terminal keys and return the offset for subsequent output assertions."""
    audit_drain(session, 0.02)
    cursor = len(session["data"])
    session["events"].append({"keys": repr(keys)})
    try:
        os.write(session["fd"], keys)
    except OSError as exc:
        if exc.errno != errno.EIO:
            raise
        session["events"].append({"write_after_exit": repr(keys)})
    return cursor


def audit_exited(session: dict, timeout: float = 2) -> bool:
    """Wait for natural termination and retain process resource usage."""
    if session["reaped"]:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pid, status, usage = os.wait4(session["pid"], os.WNOHANG)
        if pid:
            session.update(
                reaped=True,
                exitcode=os.waitstatus_to_exitcode(status),
                maxrss_native=usage.ru_maxrss,
            )
            return True
        audit_drain(session, 0.02)
    return False


AUDIT_FORMATS = [
    ("code.c", b"int main(void) { return 42; } // SENTINEL\n", "color"),
    ("code.py", b'def sample():\n    return "SENTINEL"\n', "color"),
    ("code.PY", b'def sample():\n    return "SENTINEL"\n', "color"),
    ("doc.md", b"# SENTINEL\n\n- one\n- two\n", "markdown"),
    ("heading.md", b"# SENTINEL\n", "markdown"),
    ("list.md", b"- SENTINEL\n- two\n", "markdown"),
    ("conn.log", b'{"message":"SENTINEL","n":42}\n', "color"),
    ("data.jsonl", b'{"message":"SENTINEL","n":42}\n', "color"),
    ("config.yml", b"name: SENTINEL\ncount: 42\n", "color"),
    ("config.toml", b'# comment\n[server]\nname = "SENTINEL"\n', "color"),
    ("README", b"# SENTINEL\n\n- one\n", "markdown"),
    ("unknown", b"#!/bin/sh\necho SENTINEL\n", "color"),
    ("data.xml", b'<?xml version="1.0"?><root>SENTINEL</root>\n', "color"),
    ("misleading.md", b'{"message":"SENTINEL","n":42}\n', "content"),
    ("plain.txt", b"SENTINEL ordinary prose.\n", "content"),
]


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("route", ["file", "pipe", "redirect", "dash"])
def test_audit_routes(workflow_audit: dict, shell: str, mode: str, route: str) -> None:
    """Preserve input across named files, pipelines, redirected stdin, and dash."""
    a = workflow_audit
    path = Path(a["cwd"]) / "route.py"
    path.write_text('print("ROUTE_SENTINEL")\n')
    invocation = {
        "file": "less -R route.py",
        "pipe": "cat route.py | less -R",
        "redirect": "less -R < route.py",
        "dash": "cat route.py | less -R -",
    }[route]
    with audit_terminal(a, audit_command(a, shell, mode, invocation)) as s:
        audit_check(a, audit_expect(s, "ROUTE_SENTINEL"), "Input is visible")
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "Quit returns control")
        audit_check(
            a, termios.tcgetattr(s["fd"]) == s["original_termios"], "Terminal settings restored"
        )
    audit_finish(a)


@pytest.mark.parametrize("route", ["file", "pipe", "cli"])
@pytest.mark.parametrize("filename,payload,style", AUDIT_FORMATS, ids=[x[0] for x in AUDIT_FORMATS])
def test_audit_formats(
    workflow_audit: dict, route: str, filename: str, payload: bytes, style: str
) -> None:
    """Check format rendering and marker preservation through the real entrypoints."""
    a = workflow_audit
    (Path(a["cwd"]) / filename).write_bytes(payload)
    invocation = (
        "cat " + shlex.quote(filename) + " | less -R"
        if route == "pipe"
        else "richless " + shlex.quote(filename)
        if route == "cli"
        else "less -R " + shlex.quote(filename)
    )
    command = audit_command(a, "bash", "wrapper" if route == "pipe" else "filter", invocation)
    r = audit_capture(a, command)
    text = audit_text(r.stdout)
    audit_check(a, "SENTINEL" in text, "Content marker survives rendering")
    output = r.stdout.decode("utf-8", "replace")
    ambiguous_pipe = route == "pipe" and filename in {
        "code.c",
        "code.py",
        "code.PY",
        "heading.md",
        "list.md",
    }
    if ambiguous_pipe:
        audit_check(
            a, r.stdout == payload, "Ambiguous input without its extension remains source-exact"
        )
    if style == "color" and not ambiguous_pipe:
        audit_check(a, audit_has_syntax_colors(output), "Recognized code/data has syntax colors")
    if style == "markdown" and not ambiguous_pipe:
        audit_check(a, has_markdown_formatting(output), "Markdown is rendered automatically")
    audit_check(a, r.returncode == 0, "Successful invocation returns zero")
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("variant", ["glob", "reverse", "spaces", "forced", "data-plain"])
def test_audit_mixed(workflow_audit: dict, shell: str, mode: str, variant: str) -> None:
    """Navigate mixed formats forward and backward without losing identity or style."""
    a = workflow_audit
    names = (
        ["a.c", "b.py", "c.md"] if variant != "spaces" else ["a code.c", "b code.py", "c doc.md"]
    )
    payloads = [
        "int main(void) { return 7; } // C_MARKER\n",
        'def sample():\n    return "PY_MARKER"\n',
        "# MD_MARKER\n\n- item\n",
    ]
    markers = ["C_MARKER", "PY_MARKER", "MD_MARKER"]
    if variant == "data-plain":
        names = ["a.json", "b.txt", "c.md"]
        payloads[:2] = ['{"message":"C_MARKER","n":42}\n', "PY_MARKER ordinary text\n"]
    for name, content in zip(names, payloads):
        (Path(a["cwd"]) / name).write_text(content)
    if variant == "reverse":
        names.reverse()
        markers.reverse()
    args = "*.c *.py *.md" if variant == "glob" else shlex.join(names)
    if variant == "forced" and mode != "plain":
        # Filter-only control can force Markdown without giving less custom flags.
        if mode == "filter":
            a["env"]["LESSOPEN"] = "|richless --md %s"
            command = audit_command(a, shell, "plain", "less -R " + args)
        else:
            command = audit_command(a, shell, mode, "less -R --md " + args)
    else:
        command = audit_command(a, shell, mode, "less -R " + args)
    with audit_terminal(a, command) as s:
        cursor = 0
        for index in [0, 1, 2, 1, 0]:
            found = audit_expect(s, markers[index], since=cursor, timeout=1.5)
            audit_check(a, found, f"Visit {names[index]} in requested navigation order")
            audit_check(
                a,
                audit_expect(s, names[index], cursor, timeout=0.5),
                f"Display identity {names[index]}",
            )
            segment = s["data"][cursor:].decode("utf-8", "replace")
            if found and mode != "plain":
                if names[index].endswith(".md") or variant == "forced":
                    # C/Python forced Markdown may have no box characters; require source semantics only there.
                    if names[index].endswith(".md"):
                        audit_check(
                            a, has_markdown_formatting(segment), "Markdown formatting on this visit"
                        )
                else:
                    if not names[index].endswith(".txt"):
                        audit_check(
                            a, audit_has_syntax_colors(segment), "Syntax styling on this visit"
                        )
                    audit_check(
                        a,
                        not has_markdown_formatting(segment),
                        "No Markdown formatting leaks into code",
                    )
            step = len([e for e in s["events"] if "keys" in e])
            if step < 4:
                cursor = audit_send(s, b":n\n" if step < 2 else b":p\n")
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "One quit exits the multi-file session")
    audit_finish(a)


AUDIT_BYTES = [
    ("empty", b""),
    ("no-newline", b"ENDMARK"),
    ("blank-lines", b"\nFIRST\n\nLAST\n\n"),
    ("tabs", b"A\tB\n"),
    ("crlf", b"FIRST\r\nLAST\r\n"),
    ("unicode", "café 世界 e\u0301 END\n".encode()),
    ("invalid", b"FIRST\xffLAST\n"),
    ("binary", b"FIRST\x00\xfeLAST\n"),
    ("ansi", b"\x1b[31mRED\x1b[0m\n"),
    ("long", b"x" * 17000 + b"END\n"),
]


@pytest.mark.parametrize("route", ["cli", "filter", "wrapper"])
@pytest.mark.parametrize("case,payload", AUDIT_BYTES, ids=[x[0] for x in AUDIT_BYTES])
def test_audit_integrity(workflow_audit: dict, route: str, case: str, payload: bytes) -> None:
    """Apply a strict source-preservation oracle to non-Markdown text."""
    a = workflow_audit
    (Path(a["cwd"]) / "bytes.txt").write_bytes(payload)
    invocation = (
        "richless bytes.txt"
        if route == "cli"
        else ("less -R bytes.txt" if route == "filter" else "cat bytes.txt | less -R")
    )
    r = audit_capture(a, audit_command(a, "bash", route if route != "cli" else "plain", invocation))
    if case in ["invalid", "binary"]:
        expected = payload
        audit_check(
            a,
            r.stdout == expected,
            "Undecodable input delegates cleanly or remains byte-exact through pager",
        )
        audit_check(a, r.returncode == 0, "Undecodable input is handled successfully")
    else:
        # Strip only generated SGR, preserving newlines/tabs and all other bytes.
        stripped = re.sub(rb"\x1b\[[0-9;]*m", b"", r.stdout)
        expected = re.sub(rb"\x1b\[[0-9;]*m", b"", payload)
        audit_check(
            a, stripped == expected, "Non-Markdown text content is exact after removing color codes"
        )
    a["observations"].append({"input_hex": payload[:200].hex(), "output_hex": r.stdout[:200].hex()})
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize(
    "case",
    [
        "spaces",
        "quotes",
        "metacharacters",
        "whitespace",
        "whitespace-collision",
        "leading-dash",
        "dash-m",
    ],
)
def test_audit_arguments(workflow_audit: dict, shell: str, mode: str, case: str) -> None:
    """Preserve valid file arguments and the standard verbose-prompt option."""
    a = workflow_audit
    filename = {
        "spaces": "two words.py",
        "quotes": "one'\"two.py",
        "metacharacters": "$(touch SHOULD_NOT_EXIST);file.py",
        "whitespace": " file.py ",
        "whitespace-collision": " file.py ",
        "leading-dash": "-file.py",
        "dash-m": "file.py",
    }[case]
    (Path(a["cwd"]) / filename).write_text('def sample():\n    return "ARG_MARKER"\n')
    if case == "whitespace-collision":
        (Path(a["cwd"]) / "file.py").write_text('print("WRONG_FILE_MARKER")\n')
    invocation = "less -R " + ("-m " if case == "dash-m" else "") + "-- " + shlex.quote(filename)
    with audit_terminal(a, audit_command(a, shell, mode, invocation)) as s:
        audit_check(a, audit_expect(s, "ARG_MARKER"), "Filename resolves to the requested content")
        audit_check(
            a,
            "WRONG_FILE_MARKER" not in audit_text(s["data"]),
            "Never substitute a different similarly named file",
        )
        if mode != "plain":
            audit_check(
                a,
                audit_has_syntax_colors(s["data"].decode("utf-8", "replace")),
                "Valid code filename retains syntax highlighting",
            )
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "Quit exits normally")
    audit_check(
        a,
        not (Path(a["cwd"]) / "SHOULD_NOT_EXIST").exists(),
        "Filename metacharacters are never executed",
    )
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize(
    "case",
    [
        "less-options",
        "lessopen",
        "twice",
        "pipe-search",
        "redirected-file",
        "temp-failure",
        "missing",
    ],
)
def test_audit_environment(workflow_audit: dict, shell: str, case: str) -> None:
    """Check wrapper behavior under existing settings and common error conditions."""
    a = workflow_audit
    (Path(a["cwd"]) / "file.py").write_text('print("ENV_MARKER")\n')
    invocation = "less file.py"
    if case == "less-options":
        a["env"]["LESS"] = "-N"
    if case == "lessopen":
        a["env"]["LESSOPEN"] = "|printf EXISTING_FILTER"
        a["observations"].append(
            {"contract": "Richless takes precedence for wrapped invocations only"}
        )
    if case == "twice":
        invocation = ". " + shlex.quote(str(AUDIT_ROOT / "richless-init.sh")) + "; less file.py"
    if case == "pipe-search":
        invocation = "cat file.py | less -R -p 'ENV_MARKER'"
    if case == "redirected-file":
        invocation = "less -R file.py < /dev/null"
    if case == "temp-failure":
        a["env"]["TMPDIR"] = str(Path(a["cwd"]) / "does-not-exist")
        invocation = "cat file.py | less -R"
    if case == "missing":
        invocation = "less -R missing.py"
    with audit_terminal(a, audit_command(a, shell, "wrapper", invocation)) as s:
        if case == "missing":
            audit_check(
                a, audit_expect(s, "missing.py"), "Missing file produces a useful diagnostic"
            )
        else:
            audit_check(
                a,
                audit_expect(s, "ENV_MARKER"),
                "Settings/failure do not make valid content inaccessible",
            )
        if case == "less-options":
            audit_check(
                a,
                "ESC[" not in audit_text(s["data"]),
                "Existing LESS options still allow rendered ANSI colors",
            )
        audit_send(s, b"q")
        audit_exited(s)
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
def test_audit_stream(workflow_audit: dict, shell: str, mode: str) -> None:
    """Display and update piped input before EOF, then quit with producer still open."""
    a = workflow_audit
    with audit_terminal(a, audit_command(a, shell, mode, "less -R"), piped=True) as s:
        os.write(s["writer"], b"STREAM_FIRST\n" + b"padding\n" * 30)
        visible = audit_expect(s, "STREAM_FIRST", timeout=1.5)
        audit_check(a, visible, "First screen visible while producer remains open")
        if visible:
            audit_send(s, b"F")
            os.write(s["writer"], b"STREAM_SECOND\n")
            audit_check(
                a, audit_expect(s, "STREAM_SECOND", timeout=2), "Follow displays later pipe input"
            )
            audit_send(s, b"\x03")
            audit_send(s, b"q")
            audit_check(a, audit_exited(s), "Can quit without waiting for producer EOF")
        else:
            audit_send(s, b"\x03")
        audit_drain(s, 0.1)
        a["observations"].append(
            {
                "temp_files_before_harness_cleanup": [
                    p.name for p in Path(a["env"]["TMPDIR"]).glob("richless.*")
                ]
            }
        )
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
def test_audit_follow_file(workflow_audit: dict, mode: str, shell: str) -> None:
    """Follow new records appended to a named file."""
    a = workflow_audit
    path = Path(a["cwd"]) / "growing.log"
    path.write_text("FILE_FIRST\n" + "padding\n" * 30)
    with audit_terminal(a, audit_command(a, shell, mode, "less -R growing.log")) as s:
        audit_check(a, audit_expect(s, "FILE_FIRST"), "Initial file visible")
        audit_send(s, b"F")
        with path.open("a") as writer:
            writer.write("FILE_APPENDED\n")
        audit_check(
            a,
            audit_expect(s, "FILE_APPENDED", timeout=2),
            "Appended file data becomes visible in follow mode",
        )
        audit_send(s, b"\x03")
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "Interrupt follow then quit")
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
def test_audit_interaction(workflow_audit: dict, mode: str, shell: str) -> None:
    """Exercise search, movement, long lines, resize, and terminal restoration."""
    a = workflow_audit
    lines = [f"ROW_{i:03d} " + ("NEEDLE" if i in [60, 120] else "value") for i in range(180)]
    lines[150] += "x" * 150 + "RIGHT_EDGE"
    (Path(a["cwd"]) / "navigation.txt").write_text("\n".join(lines) + "\n")
    with audit_terminal(a, audit_command(a, shell, mode, "less -R -N -S navigation.txt")) as s:
        audit_check(a, audit_expect(s, "ROW_000"), "Initial viewport")
        offset = audit_send(s, b"/NEEDLE\n")
        audit_check(a, audit_expect(s, "ROW_060", offset), "Forward search")
        offset = audit_send(s, b"n")
        audit_check(a, audit_expect(s, "ROW_120", offset), "Repeat search")
        offset = audit_send(s, b"N")
        audit_check(a, audit_expect(s, "ROW_060", offset), "Reverse repeat search")
        offset = audit_send(s, b"G?NEEDLE\n")
        audit_check(a, audit_expect(s, "ROW_120", offset), "Backward search")
        offset = audit_send(s, b"g")
        audit_check(a, audit_expect(s, "ROW_000", offset), "Go to start")
        offset = audit_send(s, b" ")
        audit_check(a, audit_expect(s, "ROW_030", offset), "Page forward")
        offset = audit_send(s, b"151g100\x1b)")
        audit_check(
            a,
            audit_expect(s, "RIGHT_EDGE", offset),
            "Horizontal navigation reaches long-line suffix",
        )
        fcntl.ioctl(s["fd"], termios.TIOCSWINSZ, struct.pack("HHHH", 18, 60, 0, 0))
        offset = audit_send(s, b"\x1b{g")
        audit_check(a, audit_expect(s, "ROW_000", offset), "Content survives terminal resize")
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "Quit after resizing")
        audit_check(
            a,
            termios.tcgetattr(s["fd"]) == s["original_termios"],
            "Restore terminal after interactive commands",
        )
    audit_finish(a)


@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("obstacle", ["empty", "binary", "unreadable"])
def test_audit_mixed_obstacle(workflow_audit: dict, mode: str, obstacle: str) -> None:
    """Keep good files accessible on both sides of a problematic mixed-session member."""
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "first.md").write_text("# BEFORE_MARKER\n\n- item\n")
    middle = root / "middle.txt"
    middle.write_bytes(
        b"" if obstacle == "empty" else b"\xff\x00" if obstacle == "binary" else b"HIDDEN\n"
    )
    if obstacle == "unreadable":
        middle.chmod(0)
        if os.access(middle, os.R_OK):
            pytest.skip("Current credentials bypass file read permissions")
    (root / "last.py").write_text('print("AFTER_MARKER")\n')
    with audit_terminal(
        a, audit_command(a, "bash", mode, "less -R first.md middle.txt last.py")
    ) as s:
        audit_check(a, audit_expect(s, "BEFORE_MARKER"), "First file accessible")
        offset = audit_send(s, b":n\n")
        if obstacle == "unreadable":
            audit_expect(s, "press RETURN", offset, timeout=1)
            audit_send(s, b"\n")
            # less removes an unreadable member and advances automatically.
        else:
            audit_expect(s, "middle.txt", offset, timeout=1)
            if obstacle == "binary":
                audit_send(s, b"y\n")
            offset = audit_send(s, b":n\n")
        audit_check(a, audit_expect(s, "AFTER_MARKER", offset), "Later file remains accessible")
        offset = audit_send(s, b":p\n")
        if obstacle != "unreadable":
            if obstacle == "binary":
                audit_send(s, b"y\n")
            offset = audit_send(s, b":p\n")
        audit_check(
            a,
            audit_expect(s, "BEFORE_MARKER", offset),
            "Backward navigation returns to initial file",
        )
        audit_send(s, b"q")
        audit_exited(s)
    middle.chmod(0o600)
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
def test_audit_fifo(workflow_audit: dict, mode: str, shell: str) -> None:
    """Read a named pipe while its writer remains open."""
    a = workflow_audit
    fifo = Path(a["cwd"]) / "events"
    os.mkfifo(fifo)
    with audit_terminal(a, audit_command(a, shell, mode, "less -R -f events")) as s:
        deadline = time.monotonic() + 3
        writer = -1
        while time.monotonic() < deadline:
            try:
                writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError as exc:
                if exc.errno != errno.ENXIO:
                    raise
                audit_drain(s, 0.02)
        audit_check(a, writer >= 0, "Pager opens the named pipe")
        if writer >= 0:
            try:
                os.write(writer, b"FIFO_MARKER\n" + b"padding\n" * 30)
                audit_check(
                    a,
                    audit_expect(s, "FIFO_MARKER", timeout=1.5),
                    "FIFO content visible before writer closes",
                )
            finally:
                os.close(writer)
        audit_send(s, b"q")
        audit_exited(s)
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize(
    "case",
    [
        "normal",
        "interrupt-copy",
        "terminate-copy",
        "producer-fails",
        "missing-renderer",
        "render-before",
        "render-after",
    ],
)
def test_audit_failures(workflow_audit: dict, case: str, shell: str) -> None:
    """Observe fallback, status propagation, and temporary-file cleanup."""
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "input.txt").write_text("FAILURE_MARKER\n")
    if case == "missing-renderer":
        (root / "bin" / "richless").unlink()
        a["env"]["PATH"] = "/usr/bin:/bin"
    if case in ["render-before", "render-after"]:
        launcher = root / "bin" / "richless"
        launcher.write_text(
            "#!/bin/sh\n"
            + ("printf PARTIAL\n" if case == "render-after" else "")
            + "echo INJECTED_RENDER_FAILURE >&2\nexit 7\n"
        )
    if case in ["interrupt-copy", "terminate-copy"]:
        with audit_terminal(a, audit_command(a, shell, "wrapper", "less -R"), piped=True) as s:
            os.write(s["writer"], b"FAILURE_MARKER\n")
            audit_check(a, audit_expect(s, "FAILURE_MARKER"), "Streaming has started before signal")
            audit_check(
                a,
                not list(Path(a["env"]["TMPDIR"]).glob("richless*")),
                "Ordinary streaming creates no temporary files",
            )
            if case == "interrupt-copy":
                audit_send(s, b"\x03")
            else:
                os.killpg(s["pid"], signal.SIGTERM)
            os.close(s["writer"])
            s["writer"] = -1
            audit_exited(s)
            leftovers = [p.name for p in Path(a["env"]["TMPDIR"]).glob("richless.*")]
            a["observations"].append({"leftovers_before_harness_cleanup": leftovers})
            audit_check(a, not leftovers, "Interrupted wrapper cleans its temporary file")
    else:
        invocation = (
            "(cat input.txt; exit 7) | less -R"
            if case == "producer-fails"
            else "cat input.txt | less -R"
        )
        result = audit_capture(a, audit_command(a, shell, "wrapper", invocation))
        if not case.startswith("render-"):
            audit_check(
                a,
                b"FAILURE_MARKER" in result.stdout,
                "Raw content remains available despite failure",
            )
        else:
            audit_check(
                a,
                (root / "input.txt").read_bytes() == b"FAILURE_MARKER\n",
                "Fatal launcher failure leaves the source intact",
            )
        audit_check(
            a,
            not list(Path(a["env"]["TMPDIR"]).glob("richless.*")),
            "No temporary files remain after completion",
        )
        if case.startswith("render-"):
            audit_check(
                a, result.returncode != 0, "Unrecovered rendering error is not reported as success"
            )
        if case == "producer-fails":
            audit_check(
                a, result.returncode == 0, "Default pipeline status is the native pager status"
            )
    audit_finish(a)


@pytest.mark.parametrize("stage", ["before", "after"])
def test_audit_python_render_failure(workflow_audit: dict, stage: str) -> None:
    """Inject an exception in-process without editing the renderer on disk."""
    a = workflow_audit
    payload = b"first = 1\nRAW_MARKER\n"
    (Path(a["cwd"]) / "file.py").write_bytes(payload)
    failure_at = 1 if stage == "before" else 3
    script = (
        "import sys; sys.path.insert(0, " + repr(str(AUDIT_ROOT)) + "); import richless\n"
        "original = richless.TerminalTrueColorFormatter.format\ncalls = 0\n"
        "def broken(self, tokens, output):\n"
        "    global calls\n    calls += 1\n"
        f"    if calls == {failure_at}:\n"
        '        output.write("PARTIAL")\n        raise RuntimeError("INJECTED")\n'
        "    return original(self, tokens, output)\n"
        "richless.TerminalTrueColorFormatter.format = broken\n"
        'sys.argv = ["richless", "file.py"]; sys.exit(richless.main())\n'
    )
    result = audit_capture(a, [sys.executable, "-c", script])
    stripped = re.sub(rb"\x1b\[[0-9;]*m", b"", result.stdout)
    audit_check(
        a,
        stripped == payload,
        "Transactional fallback preserves source without partial-output contamination",
    )
    audit_check(a, b"INJECTED" in result.stderr, "Diagnostic stays on stderr")
    audit_finish(a)


@pytest.mark.parametrize("probe", ["incremental", "force-filter", "empty-fallback"])
def test_audit_probe(workflow_audit: dict, probe: str) -> None:
    """Test three isolated integration hypotheses without modifying production files."""
    if not os.environ.get("RICHLESS_AUDIT_PROBES"):
        pytest.skip("Enable probes after baseline classification with RICHLESS_AUDIT_PROBES=1")
    a = workflow_audit
    root = Path(a["cwd"])
    if probe == "incremental":
        a["hypothesis"] = (
            "An incremental ANSI producer can feed less before EOF while preserving interactive controls."
        )
        script = root / "incremental.py"
        script.write_text(
            "import sys\nfrom rich.console import Console\nfrom rich.syntax import Syntax\n"
            "console = Console(force_terminal=True, width=100)\n"
            "for line in sys.stdin:\n"
            '    console.print(Syntax(line.rstrip("\\n"), "json", background_color="default"))\n'
            "    sys.stdout.flush()\n"
        )
        a["env"]["LESSOPEN"] = (
            "|-" + shlex.quote(sys.executable) + " " + shlex.quote(str(script)) + " %s"
        )
        a["mechanism"] = "Native stdin-enabled LESSOPEN input pipe (|-), no shell spool"
        invocation = "command less -R"
        with audit_terminal(a, audit_command(a, "bash", "plain", invocation), piped=True) as s:
            os.write(s["writer"], b'{"message":"PROBE_FIRST"}\n' + b'{"padding":1}\n' * 30)
            audit_check(
                a,
                audit_expect(s, "PROBE_FIRST"),
                "Incrementally rendered screen appears before EOF",
            )
            audit_check(
                a,
                audit_has_syntax_colors(s["data"].decode("utf-8", "replace")),
                "Incremental output has syntax styling",
            )
            audit_send(s, b"F")
            os.write(s["writer"], b'{"message":"PROBE_SECOND"}\n')
            audit_check(
                a, audit_expect(s, "PROBE_SECOND"), "Incremental updates appear in follow mode"
            )
            audit_send(s, b"\x03")
            audit_send(s, b"q")
            audit_check(
                a,
                audit_exited(s, 1),
                "Native pager exits while original input remains open after interrupt",
            )
        # Use the same records as the baseline performance scenario, but stop
        # after first display to isolate latency and early-quit resource usage.
        large = root / "conn.log"
        with large.open("w") as writer:
            for index in range(166000):
                writer.write(
                    json.dumps(
                        {
                            "ts": index,
                            "uid": "PERF_MARKER",
                            "id.orig_h": "192.0.2.1",
                            "id.resp_h": "198.51.100.2",
                            "proto": "tcp",
                            "orig_bytes": index,
                        }
                    )
                    + "\n"
                )
        a["large_input_measurements"] = []
        for iteration in range(3):
            command = audit_command(a, "bash", "plain", "cat conn.log | command less -R")
            with audit_terminal(a, command) as s:
                visible = audit_expect(s, "PERF_MARKER", timeout=5)
                first = time.monotonic() - s["started"]
                audit_check(
                    a, visible, "Incremental 166,000-line JSONL first display within five seconds"
                )
                audit_check(
                    a,
                    audit_has_syntax_colors(s["data"].decode("utf-8", "replace")),
                    "Large-input first screen is highlighted",
                )
                quit_started = time.monotonic()
                audit_send(s, b"q")
                exited = audit_exited(s, 3)
                audit_check(
                    a, exited, "Early quit does not wait for complete large-input rendering"
                )
                a["large_input_measurements"].append(
                    {
                        "iteration": iteration,
                        "first_display_seconds": first,
                        "quit_seconds": time.monotonic() - quit_started,
                        "maxrss_native": s.get("maxrss_native"),
                        "rss_units": "bytes" if sys.platform == "darwin" else "KiB",
                        "full_input_rendered": False,
                    }
                )
        a["limitations"] = (
            "Line-local JSON and fixed 100-column width only; does not prove multiline lexer state, "
            "Markdown streaming, full-file throughput, production width semantics, or polished cancellation. "
            "The prototype can emit KeyboardInterrupt/BrokenPipe diagnostics on interruption/early quit."
        )
    elif probe == "force-filter":
        a["hypothesis"] = (
            "Passing --md through LESSOPEN preserves one pager session and real filenames."
        )
        for name, marker in [("a.txt", "FORCE_FIRST"), ("b.txt", "FORCE_SECOND")]:
            (root / name).write_text("# " + marker + "\n\n- item\n")
        a["env"]["LESSOPEN"] = "|richless --md %s"
        with audit_terminal(a, audit_command(a, "bash", "plain", "less -R a.txt b.txt")) as s:
            audit_check(a, audit_expect(s, "FORCE_FIRST"), "First forced Markdown file visible")
            offset = audit_send(s, b":n\n")
            audit_check(
                a, audit_expect(s, "FORCE_SECOND", offset), "Next forced Markdown file visible"
            )
            audit_check(a, "b.txt" in audit_text(s["data"][offset:]), "Real filename preserved")
            audit_check(
                a,
                has_markdown_formatting(s["data"][offset:].decode()),
                "Second file rendered as Markdown",
            )
            offset = audit_send(s, b":p\n")
            audit_check(a, audit_expect(s, "FORCE_FIRST", offset), "Backward navigation works")
            audit_send(s, b"q")
            audit_check(a, audit_exited(s), "One quit exits the whole session")
    else:
        a["hypothesis"] = (
            "A failed filter can delegate named files by emitting nothing; partial output prevents transparent fallback."
        )
        (root / "raw.txt").write_text("FALLBACK_MARKER\n")
        launcher = root / "bin" / "richless"
        for partial in [False, True]:
            launcher.write_text(
                "#!/bin/sh\n" + ("printf PARTIAL\n" if partial else "") + "exit 7\n"
            )
            r = audit_capture(a, audit_command(a, "bash", "filter", "less -R raw.txt"))
            audit_check(
                a,
                r.stdout == (b"PARTIAL" if partial else b"FALLBACK_MARKER\n"),
                "Confirm fallback boundary: "
                + (
                    "partial output commits replacement"
                    if partial
                    else "empty output delegates original"
                ),
            )
    audit_finish(a)


@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("route", ["file", "pipe"])
@pytest.mark.parametrize("line_count", [100, 10000, 166000, 500000])
def test_audit_performance(workflow_audit: dict, mode: str, line_count: int, route: str) -> None:
    """Measure repeated startup/completion without turning latency into a CI gate."""
    if not os.environ.get("RICHLESS_AUDIT_PERFORMANCE"):
        pytest.skip("Set RICHLESS_AUDIT_PERFORMANCE=1 for resource measurements")
    a = workflow_audit
    path = Path(a["cwd"]) / "conn.log"
    with path.open("w") as writer:
        for index in range(line_count):
            writer.write(
                json.dumps(
                    {
                        "ts": index,
                        "uid": "PERF_MARKER",
                        "id.orig_h": "192.0.2.1",
                        "id.resp_h": "198.51.100.2",
                        "proto": "tcp",
                        "orig_bytes": index,
                    }
                )
                + "\n"
            )
    a["measurements"] = []
    for iteration in range(3):
        command = audit_command(
            a, "bash", mode, "less -R conn.log" if route == "file" else "cat conn.log | less -R"
        )
        with audit_terminal(a, command) as s:
            visible = audit_expect(s, "PERF_MARKER", timeout=45)
            first = time.monotonic() - s["started"]
            if not visible:
                a["measurements"].append(
                    {
                        "iteration": iteration,
                        "first_display_seconds_lower_bound": first,
                        "censored": True,
                    }
                )
                audit_check(
                    a,
                    False,
                    "No useful display before 45-second safety deadline; remaining repetitions cancelled",
                )
                break
            audit_check(a, visible, "First useful display within 45-second safety deadline")
            audit_send(s, b"G")
            completed = audit_expect(s, "(END)", timeout=45)
            finish = time.monotonic() - s["started"]
            audit_check(a, completed, "Can reach end of generated file within safety deadline")
            audit_send(s, b"q")
            quit_ok = audit_exited(s, 5)
            audit_check(a, quit_ok, "Quit after complete rendering")
            a["measurements"].append(
                {
                    "iteration": iteration,
                    "first_display_seconds": first,
                    "end_seconds": finish,
                    "maxrss_native": s.get("maxrss_native"),
                    "rss_units": "bytes" if sys.platform == "darwin" else "KiB",
                    "rss_scope": "wait4 shell child resource accounting; not aggregate concurrent RSS",
                    "under_300ms": first < 0.3,
                }
            )
    audit_finish(a)


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
@pytest.mark.parametrize("mode", AUDIT_MODES)
@pytest.mark.parametrize("option", ["line", "search", "phrase-pipe"])
def test_audit_initial_position(workflow_audit: dict, shell: str, mode: str, option: str) -> None:
    """Preserve initial line/search commands, including a quoted pipeline pattern."""
    a = workflow_audit
    lines = [f"POSITION_{i:03d}" for i in range(150)]
    lines[80] = "two words POSITION_TARGET"
    (Path(a["cwd"]) / "positions.txt").write_text("\n".join(lines) + "\n")
    invocation = {
        "line": "less -R +81 positions.txt",
        "search": "less -R +/POSITION_TARGET positions.txt",
        "phrase-pipe": "cat positions.txt | less -R -p 'two words'",
    }[option]
    with audit_terminal(a, audit_command(a, shell, mode, invocation)) as s:
        audit_check(
            a,
            audit_expect(s, "POSITION_TARGET"),
            "Initial viewport reaches requested line or search match",
        )
        audit_send(s, b"q")
        audit_check(a, audit_exited(s), "Initial-position invocation quits normally")
    audit_finish(a)


@pytest.mark.parametrize("replacement", [False, True], ids=["native", "replacement"])
@pytest.mark.parametrize("change", ["append", "truncate", "rename-descriptor", "replace-name"])
def test_follow_transport_gate(workflow_audit: dict, replacement: bool, change: str) -> None:
    """Compare a growing replacement file with native startup following."""
    a = workflow_audit
    root = Path(a["cwd"])
    original = root / "watched.log"
    rendered = root / "rendered.txt"
    initial = b"".join(f"INITIAL_{i:03d}\n".encode() for i in range(60))
    original.write_bytes(initial)
    rendered.write_bytes(initial)
    if replacement:
        a["env"]["LESSOPEN"] = "printf " + shlex.quote(str(rendered)) + " # %s"
    options = "--follow-name " if change == "replace-name" else ""
    with audit_terminal(
        a, audit_command(a, "bash", "plain", f"less -R {options}+F watched.log")
    ) as session:
        audit_check(a, audit_expect(session, "INITIAL_059"), "Startup follow reaches current tail")
        offset = len(session["data"])
        if change in ["rename-descriptor", "replace-name"]:
            original.rename(root / "old.log")
            original.write_bytes(b"REPLACEMENT_MARKER\n")
        if change == "truncate":
            original.write_bytes(b"CHANGED_MARKER\n")
            if replacement:
                rendered.write_bytes(b"CHANGED_MARKER\n")
        elif change == "replace-name":
            if replacement:
                rendered.write_bytes(b"REPLACEMENT_MARKER\n")
        else:
            target = root / "old.log" if change == "rename-descriptor" else original
            with target.open("ab") as writer:
                writer.write(b"CHANGED_MARKER\n")
            if replacement:
                with rendered.open("ab") as writer:
                    writer.write(b"CHANGED_MARKER\n")
        expected = "REPLACEMENT_MARKER" if change == "replace-name" else "CHANGED_MARKER"
        visible = audit_expect(session, expected, offset, timeout=1 if change == "truncate" else 5)
        if change == "truncate":
            a["observations"].append({"automatic_truncation_display": visible})
            audit_send(session, b"\x03")
            offset = audit_send(session, b"Rg")
            audit_check(
                a, audit_expect(session, expected, offset), "Reload displays truncated generation"
            )
        else:
            audit_check(a, visible, "Changed source generation becomes visible")
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Interrupt following and quit normally")
    audit_finish(a)


@pytest.mark.parametrize(
    "arguments,expected,forced,follow",
    [
        (["--md", "+F", "one.md", "two.py"], ["+F", "one.md", "two.py"], "markdown", True),
        (["-P", "--md", "file"], ["-P", "--md", "file"], None, False),
        (["--prompt", "+F", "file"], ["--prompt", "+F", "file"], None, False),
        (["--prom", "--md", "file"], ["--prom", "--md", "file"], None, False),
        (["-o", "--md", "file"], ["-o", "--md", "file"], None, False),
        (["--", "--md", "+F"], ["--", "--md", "+F"], None, False),
        (["--syntax=python", "-m", " a.py "], ["-m", " a.py "], "python", False),
        (["-F", "file"], ["-F", "file"], None, False),
    ],
)
def test_redesign_arguments(arguments, expected, forced, follow):
    import richless

    assert richless.pager_arguments(arguments) == (expected, forced, follow)


@pytest.mark.parametrize(
    "arguments", [["--md", "--syntax", "python"], ["--syntax"], ["--syntax", "not-a-lexer"]]
)
def test_redesign_rejects_format_errors_before_input(arguments):
    result = subprocess.run(
        ["richless", "--pager", *arguments], input=b"UNCONSUMED", capture_output=True
    )
    assert result.returncode == 2
    assert result.stdout == b""


@pytest.mark.parametrize("width", [40, 80])
@pytest.mark.parametrize("live", [False, True])
def test_redesign_markdown_equivalence(width, live, monkeypatch):
    import io

    from rich.console import Console
    from rich.markdown import Markdown

    import richless
    from audit.incremental_markdown import CASES

    monkeypatch.setattr(richless, "get_terminal_width", lambda: width)
    monkeypatch.setenv("TERM", "xterm-256color")
    # OSC hyperlink identifiers are intentionally nondeterministic. Exercise the
    # normal link presentation separately; compare layouts with links disabled.
    monkeypatch.setattr(richless, "Markdown", lambda text: Markdown(text, hyperlinks=False))
    for name, source in CASES.items():
        expected = io.StringIO()
        Console(file=expected, force_terminal=True, color_system="truecolor", width=width).print(
            Markdown(source, hyperlinks=False), end=""
        )
        actual = io.BytesIO()
        if live:
            richless.render_live_markdown(iter(source.encode().splitlines(keepends=True)), actual)
        else:
            richless.render_finite_markdown(source.encode(), actual)
        assert actual.getvalue() == expected.getvalue().encode(), name


@pytest.mark.parametrize(
    "payload", [b"x\t= 1\r\n", b"\n\nx=1", b'x="caf\xc3\xa9"\n', b"\xff\x00BAD"]
)
def test_redesign_source_integrity(tmp_path, payload):
    source = tmp_path / "source.py"
    source.write_bytes(payload)
    result = subprocess.run(["richless", str(source)], capture_output=True)
    assert result.returncode == 0
    assert re.sub(rb"\x1b\[[0-9;]*m", b"", result.stdout) == payload


def test_redesign_live_markdown_deadline(monkeypatch):
    import io

    import richless

    clock = [0.0]
    monkeypatch.setattr(richless.time, "monotonic", lambda: clock[0])

    def chunks():
        yield b"EARLY **bold**.\n\n# Next\n"
        yield b"\nRead [future].\n"
        clock[0] = 6.0
        yield None
        yield b"AFTER_FALLBACK\n"

    output = io.BytesIO()
    richless.render_live_markdown(chunks(), output)
    actual = re.sub(rb"\x1b\[[0-9;]*m", b"", output.getvalue())
    assert b"EARLY bold." in actual
    assert b"EARLY **bold**" not in actual
    assert actual.count(b"Read [future].") == 1
    assert actual.endswith(b"AFTER_FALLBACK\n")


@pytest.mark.parametrize("shell", AUDIT_SHELLS)
def test_redesign_formatted_follow(workflow_audit, shell):
    a = workflow_audit
    root = Path(a["cwd"])
    source = root / "records.jsonl"
    source.write_bytes(b'{"marker":"FOLLOW_FIRST","count":1}\n')
    with audit_terminal(a, audit_command(a, shell, "wrapper", "less +F records.jsonl")) as session:
        audit_check(
            a, audit_expect(session, "FOLLOW_FIRST"), "Initial rendered follow output appears"
        )
        offset = len(session["data"])
        with source.open("ab") as writer:
            writer.write(b'{"marker":"FOLLOW_SECOND","count":2}\n')
        audit_check(
            a, audit_expect(session, "FOLLOW_SECOND", offset), "Appended rendered record appears"
        )
        audit_check(
            a, audit_has_syntax_colors(session["data"].decode()), "Follow output is highlighted"
        )
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Follow quits normally")
    audit_check(
        a,
        not list(Path(a["env"]["TMPDIR"]).glob("richless*")),
        "Follow session cleans replacements",
    )
    audit_finish(a)


@pytest.mark.parametrize("change", ["truncate", "rename-descriptor", "replace-name"])
def test_redesign_follow_generations(workflow_audit, change):
    a = workflow_audit
    root = Path(a["cwd"])
    source = root / "records.jsonl"
    source.write_bytes(b'{"marker":"GENERATION_FIRST","count":1}\n' * 30)
    option = "--follow-name " if change == "replace-name" else ""
    with audit_terminal(
        a, audit_command(a, "bash", "wrapper", f"less {option}+F records.jsonl")
    ) as session:
        audit_check(
            a, audit_expect(session, "GENERATION_FIRST"), "Initial formatted generation appears"
        )
        offset = len(session["data"])
        if change == "truncate":
            source.write_bytes(b'{"marker":"GENERATION_NEXT","count":2}\n')
            deadline = time.monotonic() + 3
            prepared = False
            while time.monotonic() < deadline:
                views = Path(a["env"]["TMPDIR"]).glob("richless-follow-*/view-*")
                prepared = any(b"GENERATION_NEXT" in view.read_bytes() for view in views)
                if prepared:
                    break
                audit_drain(session, 0.02)
            audit_check(
                a, prepared, "Worker publishes the truncated generation within the deadline"
            )
            audit_send(session, b"\x03")
            offset = audit_send(session, b"Rg")
        elif change == "replace-name":
            source.rename(root / "rotated.jsonl")
            source.write_bytes(b'{"marker":"GENERATION_NEXT","count":2}\n')
        else:
            source.rename(root / "rotated.jsonl")
            source.write_bytes(b'{"marker":"WRONG_GENERATION","count":3}\n')
            with (root / "rotated.jsonl").open("ab") as writer:
                writer.write(b'{"marker":"GENERATION_NEXT","count":2}\n')
        audit_check(
            a,
            audit_expect(session, "GENERATION_NEXT", offset, timeout=5),
            "Correct source generation appears",
        )
        audit_check(
            a,
            "WRONG_GENERATION" not in audit_text(session["data"]),
            "Descriptor following does not switch by name",
        )
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Session terminates after generation change")
    audit_check(
        a,
        not list(Path(a["env"]["TMPDIR"]).glob("richless*")),
        "Generation workers and replacements are released",
    )
    audit_finish(a)


def test_redesign_follow_mixed_navigation(workflow_audit):
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "one.md").write_text("# FIRST_MARKDOWN\n\n- item\n")
    (root / "two.md").write_text("# SECOND_MARKDOWN\n\n- item\n")
    with audit_terminal(
        a, audit_command(a, "bash", "wrapper", "less --md +F one.md two.md")
    ) as session:
        offset = 0
        for i, marker in enumerate(["FIRST_MARKDOWN", "SECOND_MARKDOWN", "FIRST_MARKDOWN"]):
            audit_check(
                a, audit_expect(session, marker, offset), "Correct file visible on each visit"
            )
            active = list(Path(a["env"]["TMPDIR"]).glob("richless-follow-*/view-*"))
            audit_check(a, len(active) == 1, "Only the current file retains a replacement")
            audit_send(session, b"\x03")
            if i < 2:
                offset = audit_send(session, b":n\n" if i == 0 else b":p\n")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "One quit releases the session")
    audit_finish(a)


def test_redesign_follow_mixed_stdin(workflow_audit):
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "one.jsonl").write_bytes(b'{"marker":"NAMED_FIRST","n":1}\n')
    with audit_terminal(
        a, audit_command(a, "bash", "wrapper", "less +F one.jsonl -"), piped=True
    ) as session:
        os.write(session["writer"], b'{"marker":"STDIN_SECOND","n":2}\n')
        audit_check(
            a, audit_expect(session, "NAMED_FIRST"), "Named input appears with redirected stdin"
        )
        audit_send(session, b"\x03")
        offset = audit_send(session, b":n\n")
        audit_check(
            a,
            audit_expect(session, "STDIN_SECOND", offset),
            "Explicit stdin streams in the same session",
        )
        audit_check(
            a,
            audit_has_syntax_colors(session["data"][offset:].decode()),
            "Stdin retains highlighting",
        )
        os.close(session["writer"])
        session["writer"] = -1
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Mixed stdin session quits")
    audit_finish(a)


def test_redesign_ordinary_render_does_not_follow(workflow_audit):
    a = workflow_audit
    source = Path(a["cwd"]) / "ordinary.jsonl"
    source.write_bytes(b'{"marker":"ORIGINAL_SNAPSHOT","n":1}\n')
    with audit_terminal(a, audit_command(a, "bash", "wrapper", "less ordinary.jsonl")) as session:
        audit_check(a, audit_expect(session, "ORIGINAL_SNAPSHOT"), "Ordinary snapshot appears")
        audit_check(
            a,
            not list(Path(a["env"]["TMPDIR"]).glob("richless*")),
            "Ordinary rendering does not create a replacement",
        )
        offset = audit_send(session, b"F")
        with source.open("ab") as writer:
            writer.write(b'{"marker":"LATER_SOURCE_CHANGE","n":2}\n')
        audit_check(
            a,
            not audit_expect(session, "LATER_SOURCE_CHANGE", offset, timeout=0.4),
            "Interactive F does not monitor a rendered snapshot",
        )
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Snapshot follow can be interrupted and quit")
    audit_finish(a)


def test_redesign_quit_active_producer_without_interrupt(workflow_audit):
    a = workflow_audit
    with audit_terminal(a, audit_command(a, "bash", "wrapper", "less"), piped=True) as session:
        os.write(session["writer"], b'{"marker":"ACTIVE_PRODUCER","n":1}\n' * 40)
        audit_check(a, audit_expect(session, "ACTIVE_PRODUCER"), "Initial stream display")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Quit does not require producer EOF or Ctrl+C")
    audit_finish(a)


def test_redesign_broken_output_while_input_idle():
    process = subprocess.Popen(
        ["richless", "--syntax", "json", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        process.stdin.write(b'{"marker":"READY","n":1}\n')
        process.stdin.flush()
        assert select.select([process.stdout], [], [], 2)[0]
        os.read(process.stdout.fileno(), 4096)
        process.stdout.close()
        assert process.wait(timeout=2) == 0
        assert b"Traceback" not in process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdin.close()
        process.stderr.close()


@pytest.mark.parametrize("failure", ["allocation", "before-write", "after-write"])
def test_redesign_follow_resource_failure(workflow_audit, failure):
    """Exercise real replacement publication with injected resource exhaustion."""
    a = workflow_audit
    root = Path(a["cwd"])
    source = root / "events.jsonl"
    source.write_bytes(b'{"marker":"INITIAL_RESOURCE","n":1}\n' * 40)
    injection = """
if "--pager" in sys.argv and os.environ["FAULT"] == "allocation":
    def deny(*args, **kwargs):
        raise OSError(28, "injected allocation exhaustion")
    tempfile.mkstemp = deny
if "--follow-worker" in sys.argv:
    original_write = write_bytes
    def failing_write(output, data):
        if os.environ["FAULT"] == "before-write" or b"APPENDED_RESOURCE" in data:
            raise OSError(28, "injected disk exhaustion")
        original_write(output, data)
    write_bytes = failing_write
"""
    module = root / "fault_renderer.py"
    module.write_text(
        (AUDIT_ROOT / "richless.py")
        .read_text()
        .replace('if __name__ == "__main__":', injection + '\nif __name__ == "__main__":')
    )
    (root / "bin" / "richless").write_text(
        "#!/bin/sh\nexec " + shlex.join([sys.executable, str(module)]) + ' "$@"\n'
    )
    a["env"]["FAULT"] = failure
    with audit_terminal(a, audit_command(a, "bash", "wrapper", "less +F events.jsonl")) as session:
        audit_check(
            a, audit_expect(session, "INITIAL_RESOURCE"), "Original content remains viewable"
        )
        if failure == "after-write":
            with source.open("ab") as writer:
                writer.write(b'{"marker":"APPENDED_RESOURCE"}\n')
            audit_check(
                a,
                audit_expect(session, "follow renderer stopped"),
                "Stopped follow is explicitly reported",
            )
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Failure session can quit")
        audit_check(
            a,
            session.get("exitcode") == (1 if failure == "after-write" else 0),
            "Recovered original viewing succeeds; published failure is nonzero",
        )
    audit_check(a, not list(root.rglob("view-*")), "Replacement files are removed")
    audit_check(a, b"Traceback" not in session["data"], "No traceback reaches terminal")
    audit_finish(a)


@pytest.mark.parametrize("failure", ["missing-parser", "pending-limit", "invalid-utf8"])
def test_redesign_live_raw_recovery(monkeypatch, failure):
    import io

    import richless

    payload = {
        "missing-parser": b"# intact\n\n**body**\n",
        "pending-limit": b"```\n" + b"x" * richless.PENDING_BYTES,
        "invalid-utf8": b"# intact\n\n\xffbody\n",
    }[failure]
    if failure == "missing-parser":

        def unavailable():
            raise ImportError("injected missing Markdown dependency")

        monkeypatch.setattr(richless, "markdown_parser", unavailable)
    output = io.BytesIO()
    richless.render_live_markdown(iter([payload, b"TAIL"]), output)
    assert re.sub(rb"\x1b\[[0-9;]*m", b"", output.getvalue()) == payload + b"TAIL"


def test_redesign_follow_mixed_fifo(workflow_audit):
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "first.jsonl").write_bytes(b'{"marker":"NAMED_FIRST"}\n' * 40)
    fifo = root / "events"
    os.mkfifo(fifo)
    with audit_terminal(
        a, audit_command(a, "bash", "wrapper", "less -f +F first.jsonl events")
    ) as session:
        audit_check(a, audit_expect(session, "NAMED_FIRST"), "Named follow file opens")
        writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(writer, b'{"marker":"MIXED_FIFO","n":1}\n' * 40)
            audit_send(session, b"\x03")
            cursor = audit_send(session, b":n\n")
            audit_check(
                a,
                audit_expect(session, "MIXED_FIFO", since=cursor),
                "FIFO displays without EOF in mixed follow session",
            )
            audit_send(session, b"\x03")
            audit_send(session, b"q")
            audit_check(a, audit_exited(session), "Mixed FIFO session quits with writer active")
        finally:
            os.close(writer)
    audit_check(a, not list(root.rglob("view-*")), "Mixed FIFO replacement cleanup")
    audit_finish(a)


@pytest.mark.parametrize("termination", [signal.SIGTERM, signal.SIGHUP])
def test_redesign_follow_signal_cleanup(workflow_audit, termination):
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "input.jsonl").write_bytes(b'{"marker":"OWNED_WORKER"}\n' * 40)
    module = root / "owned_renderer.py"
    injection = (
        '\nif "--follow-worker" in sys.argv:\n    Path("worker.pid").write_text(str(os.getpid()))\n'
    )
    module.write_text(
        (AUDIT_ROOT / "richless.py")
        .read_text()
        .replace('if __name__ == "__main__":', injection + '\nif __name__ == "__main__":')
    )
    command = [sys.executable, str(module), "--pager", "+F", "input.jsonl"]
    with audit_terminal(a, command) as session:
        audit_check(a, audit_expect(session, "OWNED_WORKER"), "Follow worker published")
        worker = int((root / "worker.pid").read_text())
        os.kill(session["pid"], termination)
        audit_check(a, audit_exited(session, 4), "Supervisor terminates promptly")
        with pytest.raises(ProcessLookupError):
            os.kill(worker, 0)
    audit_check(a, not list(root.rglob("view-*")), "Signal removes replacements")
    audit_check(a, session["terminal_restored"], "Native pager restores terminal")
    audit_finish(a)


@pytest.mark.parametrize(
    "options, expected",
    [
        (["-r"], True),
        (["-SR"], True),
        (["-+R"], True),
        (["--RAW-CONTROL-CHARS"], True),
        (["-P", "-R"], False),
        (["-PRich prompt"], False),
        (["-S"], False),
        (["--", "-R"], False),
    ],
)
def test_redesign_explicit_environment_color_options(options, expected):
    from richless import color_override

    assert color_override(options) is expected


@pytest.mark.parametrize("case", ["large-markdown", "unfinished-live", "follow-growth"])
def test_redesign_additional_performance(workflow_audit, case):
    """Record Markdown, cancellation, and follow storage without timing gates."""
    if not os.environ.get("RICHLESS_AUDIT_PERFORMANCE"):
        pytest.skip("Set RICHLESS_AUDIT_PERFORMANCE=1 for resource measurements")
    a = workflow_audit
    root = Path(a["cwd"])
    path = root / ("measure.jsonl" if case == "follow-growth" else "measure.md")
    payload = {
        "large-markdown": b"# PERF_MARKDOWN\n\n" + b"A **bold** paragraph with `code`.\n\n" * 10000,
        "unfinished-live": b"```\nPERF_UNFINISHED\n" + b"x" * (1024 * 1024) + b"\n",
        "follow-growth": b'{"marker":"PERF_FOLLOW","n":1}\n' * 40,
    }[case]
    a["measurements"] = []
    for iteration in range(3):
        path.write_bytes(payload)
        invocation = {
            "large-markdown": "less measure.md",
            "unfinished-live": "cat measure.md | less --md",
            "follow-growth": "less +F measure.jsonl",
        }[case]
        with audit_terminal(a, audit_command(a, "bash", "wrapper", invocation)) as session:
            marker = {
                "large-markdown": "PERF_MARKDOWN",
                "unfinished-live": "PERF_UNFINISHED",
                "follow-growth": "PERF_FOLLOW",
            }[case]
            audit_check(
                a,
                audit_expect(session, marker, timeout=30),
                "Useful display within safety deadline",
            )
            measurement = {
                "iteration": iteration,
                "first_display_seconds": time.monotonic() - session["started"],
            }
            if case == "follow-growth":
                replacement = next(Path(a["env"]["TMPDIR"]).glob("richless-follow-*/view-*"))
                measurement["initial_storage_bytes"] = replacement.stat().st_size
                with path.open("ab") as writer:
                    writer.write(
                        b'{"marker":"GROWTH","n":2}\n' * 10000 + b'{"marker":"APPEND_COMPLETE"}\n'
                    )
                audit_check(
                    a,
                    audit_expect(session, "APPEND_COMPLETE", timeout=15),
                    "Appends reach the active view",
                )
                measurement["final_storage_bytes"] = replacement.stat().st_size
                measurement["source_bytes"] = path.stat().st_size
                audit_send(session, b"\x03")
            else:
                audit_send(session, b"G")
                audit_check(
                    a, audit_expect(session, "(END)", timeout=30), "Complete output can be reached"
                )
            measurement["end_seconds"] = time.monotonic() - session["started"]
            quitting = time.monotonic()
            audit_send(session, b"q")
            audit_check(a, audit_exited(session, 5), "Cancellation finishes")
            measurement["quit_seconds"] = time.monotonic() - quitting
            measurement["maxrss_native"] = session.get("maxrss_native")
            measurement["rss_units"] = "bytes" if sys.platform == "darwin" else "KiB"
            a["measurements"].append(measurement)
    audit_finish(a)


def test_redesign_supervisor_sigint_between_waits(workflow_audit):
    """Deliver SIGINT at the loop boundary, outside the old narrow exception handler."""
    a = workflow_audit
    root = Path(a["cwd"])
    (root / "input.md").write_text("# SIGNAL_BOUNDARY\n\n- body\n")
    injection = """
if "--pager" in sys.argv:
    import linecache
    fired = False
    def at_loop(frame, event, arg):
        global fired
        if (not fired and event == "line" and frame.f_code.co_name == "launch_pager"
                and linecache.getline(__file__, frame.f_lineno).strip() == "while True:"):
            fired = True
            os.kill(os.getpid(), signal.SIGINT)
        return at_loop
    sys.settrace(at_loop)
"""
    module = root / "signal_renderer.py"
    module.write_text(
        (AUDIT_ROOT / "richless.py")
        .read_text()
        .replace('if __name__ == "__main__":', injection + '\nif __name__ == "__main__":')
    )
    with audit_terminal(a, [sys.executable, str(module), "--pager", "+F", "input.md"]) as session:
        audit_check(
            a,
            audit_expect(session, "SIGNAL_BOUNDARY"),
            "Parent-only SIGINT does not destroy the pager",
        )
        audit_send(session, b"\x03")
        audit_send(session, b"q")
        audit_check(a, audit_exited(session), "Pager still quits normally")
        audit_check(a, session.get("exitcode") == 0, "Normal viewing status after SIGINT")
    audit_check(a, b"Traceback" not in session["data"], "No supervisor traceback")
    audit_finish(a)


@pytest.mark.parametrize("stopped", [False, True])
def test_redesign_short_output_writes(monkeypatch, stopped):
    """Finish short writes or report failure instead of silently losing a unit."""
    import io

    from richless import write_bytes

    output = io.BytesIO()
    original = output.write

    def limited(data):
        if stopped and output.tell() >= 7:
            return 0
        return original(data[:7])

    monkeypatch.setattr(output, "write", limited)
    payload = b"A complete original source unit without a final newline"
    if stopped:
        with pytest.raises(OSError, match="stopped accepting"):
            write_bytes(output, payload)
        assert output.getvalue() == payload[:7]
    else:
        write_bytes(output, payload)
        assert output.getvalue() == payload
