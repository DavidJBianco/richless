"""
Unit tests for richless.

Run with: uv run pytest tests/test_richless.py -v
"""

import os
import pytest
import subprocess
import sys
from pathlib import Path

# Add parent directory to path so we can import richless
sys.path.insert(0, str(Path(__file__).parent.parent))

from richless import is_markdown_file, detect_syntax_from_content
from conftest import has_ansi_colors, has_multiple_colors, has_markdown_formatting


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
        assert detect_syntax_from_content('[1, 2, 3]') == "json"

    def test_json_array_with_whitespace(self):
        assert detect_syntax_from_content('  [1, 2, 3]') == "json"

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
        assert detect_syntax_from_content('<!DOCTYPE html>\n<html>') == "xml"

    # TOML detection
    def test_toml_section_header(self):
        assert detect_syntax_from_content("[server]\nhost = \"localhost\"\n") == "toml"

    def test_toml_array_header(self):
        assert detect_syntax_from_content("[[users]]\nname = \"alice\"\n") == "toml"

    def test_toml_key_value(self):
        content = "name = \"myapp\"\nversion = \"1.0\"\n"
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
        assert detect_syntax_from_content("name = \"test\"\n") == "toml"

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


class TestIntegration:
    """Integration tests that run richless as a subprocess."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def run_richless(self, *args) -> str:
        """Run richless command and return output."""
        result = subprocess.run(
            ["richless", *args],
            capture_output=True,
            text=True,
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
        assert not has_markdown_formatting(output), "YAML with comments should NOT have markdown formatting"

    def test_yaml_filename_with_dash_m(self):
        """Filenames containing -m should not trigger --md flag."""
        output = self.run_richless(str(self.FIXTURES_DIR / "test-mcp-config.yaml"))
        assert has_multiple_colors(output), "File with -m in name should have syntax highlighting"
        assert not has_markdown_formatting(output), "File with -m in name should NOT trigger markdown"

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
        assert has_multiple_colors(output), ".log file with JSONL content should have syntax highlighting"
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
        )
        output = result.stdout + result.stderr
        assert has_multiple_colors(output), "YAML temp file should have syntax highlighting"

    def test_temp_file_with_toml_content(self, tmp_path):
        """Temp files with TOML content should be detected."""
        temp_file = tmp_path / "richless.toml42"
        temp_file.write_text("[server]\nhost = \"localhost\"\nport = 8080\n")

        result = subprocess.run(
            ["richless", str(temp_file)],
            capture_output=True,
            text=True,
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
            env={**os.environ, "LESSOPEN": "|richless %s"},
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
        assert has_multiple_colors(output), "JavaScript should have syntax highlighting via LESSOPEN"


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
            ["bash", "-c",
             f'source "{self.PROJECT_DIR}/richless-init.sh" && cat "{filepath}" | less'],
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr

    def test_piped_yaml(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test.yaml"))
        assert has_multiple_colors(output), "Piped YAML should have syntax highlighting"
        assert not has_markdown_formatting(output), "Piped YAML should not have markdown formatting"

    def test_piped_yaml_with_comments(self):
        output = self.run_piped(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert has_multiple_colors(output), "Piped YAML with comments should have syntax highlighting"
        assert not has_markdown_formatting(output), "Piped YAML with comments should not be markdown"

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
        )
        assert result.returncode == 0

    def test_binary_file_does_not_crash(self, tmp_path):
        binfile = tmp_path / "data.bin"
        binfile.write_bytes(b'\x00\x01\x02\xff\xfe\xfd')
        result = subprocess.run(
            ["richless", str(binfile)],
            capture_output=True,
            text=True,
        )
        # Should not crash -- either returns 0 (fallback) or 1 (error handled)
        assert result.returncode in (0, 1)

    def test_successful_render_returns_exit_code_0(self):
        result = subprocess.run(
            ["richless", str(self.FIXTURES_DIR / "test.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


class TestStdinInput:
    """Tests for reading from stdin via - or /dev/stdin."""

    def test_stdin_dash_with_python_content(self):
        result = subprocess.run(
            ["richless", "-"],
            input='def hello():\n    return "world"\n',
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert has_multiple_colors(result.stdout), "Python via stdin should have syntax highlighting"

    def test_stdin_dash_with_force_markdown(self):
        result = subprocess.run(
            ["richless", "--md", "-"],
            input="# Hello\n\nThis is **bold** text.\n\n- item 1\n- item 2\n",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Rich renders bold as \x1b[1m and headings with underline
        assert has_markdown_formatting(result.stdout) or "\x1b[1m" in result.stdout, \
            "Markdown via --md stdin should have formatting"

    def test_stdin_dev_stdin(self):
        result = subprocess.run(
            ["richless", "/dev/stdin"],
            input='{"key": "value"}\n',
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert has_multiple_colors(result.stdout), "JSON via /dev/stdin should have syntax highlighting"
