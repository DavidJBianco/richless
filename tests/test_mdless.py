"""
Unit tests for mdless.

Run with: uv run pytest tests/test_mdless.py -v
"""

import os
import pytest
import subprocess
import sys
from pathlib import Path

# Add parent directory to path so we can import mdless
sys.path.insert(0, str(Path(__file__).parent.parent))

from mdless import is_markdown_file, detect_syntax_from_content


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

    # Plain text fallback
    def test_plain_text(self):
        assert detect_syntax_from_content("Just some plain text") == "text"

    def test_empty_content(self):
        assert detect_syntax_from_content("") == "text"

    def test_whitespace_only(self):
        assert detect_syntax_from_content("   \n\n   ") == "text"


class TestIntegration:
    """Integration tests that run mdless as a subprocess."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def has_ansi_colors(self, output: str) -> bool:
        """Check if output contains ANSI color codes (syntax highlighting)."""
        # Rich uses 24-bit colors: \x1b[38;2;R;G;Bm
        return "\x1b[38;2;" in output or "[38;2;" in output

    def has_markdown_formatting(self, output: str) -> bool:
        """Check if output contains Rich markdown formatting."""
        # Rich markdown uses box-drawing characters, bullets, or horizontal rules
        indicators = ["┃", "┏", "┗", "━", "┓", "┛", "─", "•", " • "]
        return any(ind in output for ind in indicators)

    def run_mdless(self, *args) -> str:
        """Run mdless command and return output."""
        result = subprocess.run(
            ["mdless", *args],
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr

    # Markdown tests
    def test_markdown_file_renders_as_markdown(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.md"))
        assert self.has_markdown_formatting(output), "Markdown file should have Rich formatting"

    def test_force_markdown_flag(self):
        output = self.run_mdless("--md", str(self.FIXTURES_DIR / "test.yaml"))
        assert self.has_markdown_formatting(output), "--md flag should force markdown rendering"

    # YAML tests
    def test_yaml_file_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.yaml"))
        assert self.has_ansi_colors(output), "YAML file should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "YAML file should NOT have markdown formatting"

    def test_yaml_with_comments_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert self.has_ansi_colors(output), "YAML with comments should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "YAML with comments should NOT have markdown formatting"

    def test_yaml_filename_with_dash_m(self):
        """Filenames containing -m should not trigger --md flag."""
        output = self.run_mdless(str(self.FIXTURES_DIR / "test-mcp-config.yaml"))
        assert self.has_ansi_colors(output), "File with -m in name should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "File with -m in name should NOT trigger markdown"

    # JSON tests
    def test_json_file_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.json"))
        assert self.has_ansi_colors(output), "JSON file should have syntax highlighting"

    def test_jsonl_file_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.jsonl"))
        assert self.has_ansi_colors(output), "JSONL file should have syntax highlighting"

    # Code file tests
    def test_python_file_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.py"))
        assert self.has_ansi_colors(output), "Python file should have syntax highlighting"

    def test_shell_file_syntax_highlighting(self):
        output = self.run_mdless(str(self.FIXTURES_DIR / "test.sh"))
        assert self.has_ansi_colors(output), "Shell file should have syntax highlighting"


class TestTempFileDetection:
    """Tests for content detection on temp files (like from shell wrapper)."""

    def test_temp_file_with_json_content(self, tmp_path):
        """Temp files named mdless.XXXXX should use content detection."""
        temp_file = tmp_path / "mdless.abc123"
        temp_file.write_text('{"key": "value"}\n')

        result = subprocess.run(
            ["mdless", str(temp_file)],
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr

        # Should have JSON syntax highlighting
        assert "\x1b[38;2;" in output or "[38;2;" in output

    def test_temp_file_with_yaml_content(self, tmp_path):
        """Temp files with YAML content should be detected."""
        temp_file = tmp_path / "mdless.xyz789"
        temp_file.write_text("---\nname: test\nvalue: 123\n")

        result = subprocess.run(
            ["mdless", str(temp_file)],
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr

        # Should have YAML syntax highlighting
        assert "\x1b[38;2;" in output or "[38;2;" in output


class TestLessOpenIntegration:
    """Tests for LESSOPEN integration (less <file>)."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    def has_ansi_colors(self, output: str) -> bool:
        """Check if output contains ANSI color codes."""
        return "\x1b[38;2;" in output or "[38;2;" in output

    def has_markdown_formatting(self, output: str) -> bool:
        """Check if output contains Rich markdown formatting."""
        indicators = ["┃", "┏", "┗", "━", "┓", "┛", "─", "•", " • "]
        return any(ind in output for ind in indicators)

    def run_less_with_lessopen(self, filepath: str) -> str:
        """Run less with LESSOPEN set to use mdless."""
        result = subprocess.run(
            ["less", "-R", filepath],
            capture_output=True,
            text=True,
            env={**os.environ, "LESSOPEN": "|mdless %s"},
        )
        return result.stdout + result.stderr

    def test_yaml_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.yaml"))
        assert self.has_ansi_colors(output), "YAML should have syntax highlighting via LESSOPEN"
        assert not self.has_markdown_formatting(output), "YAML should not have markdown formatting"

    def test_yaml_with_comments_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test-with-comments.yaml"))
        assert self.has_ansi_colors(output), "YAML with comments should have syntax highlighting"

    def test_json_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.json"))
        assert self.has_ansi_colors(output), "JSON should have syntax highlighting via LESSOPEN"

    def test_jsonl_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.jsonl"))
        assert self.has_ansi_colors(output), "JSONL should have syntax highlighting via LESSOPEN"

    def test_markdown_via_lessopen(self):
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test.md"))
        assert self.has_markdown_formatting(output), "Markdown should have Rich formatting via LESSOPEN"

    def test_filename_with_dash_m_via_lessopen(self):
        """Filenames containing -m should not trigger --md flag."""
        output = self.run_less_with_lessopen(str(self.FIXTURES_DIR / "test-mcp-config.yaml"))
        assert self.has_ansi_colors(output), "File with -m in name should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "File with -m should NOT trigger markdown"


class TestPipedInputDetection:
    """Tests for piped input content detection (simulates cat <file> | less)."""

    FIXTURES_DIR = Path(__file__).parent / "fixtures"
    PROJECT_DIR = Path(__file__).parent.parent

    def has_ansi_colors(self, output: str) -> bool:
        """Check if output contains ANSI color codes."""
        return "\x1b[38;2;" in output or "[38;2;" in output

    def has_markdown_formatting(self, output: str) -> bool:
        """Check if output contains Rich markdown formatting."""
        indicators = ["┃", "┏", "┗", "━", "┓", "┛", "─", "•", " • "]
        return any(ind in output for ind in indicators)

    def simulate_piped_detection(self, filepath: str, tmp_path: Path) -> str:
        """
        Simulate what the shell less() wrapper does for piped input.

        This replicates the detection logic from mdless-init.sh:
        1. Save content to temp file named mdless.XXXXXX
        2. Check first line for YAML/JSON markers
        3. Check for YAML key: pattern after comments
        4. Check for markdown patterns
        5. Call mdless appropriately
        """
        # Read source file
        content = Path(filepath).read_text()

        # Create temp file like shell wrapper does
        temp_file = tmp_path / "mdless.testXXX"
        temp_file.write_text(content)

        lines = content.split('\n')
        first_line = lines[0] if lines else ""

        # Detection logic matching mdless-init.sh
        import re

        # Check for YAML document start or JSON
        if re.match(r'^---$|^%YAML|^\s*[{\[]', first_line):
            # YAML or JSON - use syntax highlighting
            result = subprocess.run(
                ["mdless", str(temp_file)],
                capture_output=True,
                text=True,
            )
        # Check for YAML with comments (first non-comment line has key: pattern)
        elif self._has_yaml_key_pattern(content):
            result = subprocess.run(
                ["mdless", str(temp_file)],
                capture_output=True,
                text=True,
            )
        # Check for markdown patterns
        elif re.search(r'^#{1,6} |^\* |^- |^[0-9]+\. |^\[.*\]\(.*\)|^```|\*\*.*\*\*|^>|^\||^-{3,}|^={3,}', content, re.MULTILINE):
            result = subprocess.run(
                ["mdless", "--md", str(temp_file)],
                capture_output=True,
                text=True,
            )
        else:
            # Plain text fallback
            return content

        return result.stdout + result.stderr

    def _has_yaml_key_pattern(self, content: str) -> bool:
        """Check if first non-comment line has YAML key: pattern."""
        import re
        for line in content.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*:', stripped):
                return True
            break
        return False

    def test_piped_yaml(self, tmp_path):
        output = self.simulate_piped_detection(str(self.FIXTURES_DIR / "test.yaml"), tmp_path)
        assert self.has_ansi_colors(output), "Piped YAML should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "Piped YAML should not have markdown formatting"

    def test_piped_yaml_with_comments(self, tmp_path):
        output = self.simulate_piped_detection(str(self.FIXTURES_DIR / "test-with-comments.yaml"), tmp_path)
        assert self.has_ansi_colors(output), "Piped YAML with comments should have syntax highlighting"
        assert not self.has_markdown_formatting(output), "Piped YAML with comments should not be markdown"

    def test_piped_json(self, tmp_path):
        output = self.simulate_piped_detection(str(self.FIXTURES_DIR / "test.json"), tmp_path)
        assert self.has_ansi_colors(output), "Piped JSON should have syntax highlighting"

    def test_piped_jsonl(self, tmp_path):
        output = self.simulate_piped_detection(str(self.FIXTURES_DIR / "test.jsonl"), tmp_path)
        assert self.has_ansi_colors(output), "Piped JSONL should have syntax highlighting"

    def test_piped_markdown(self, tmp_path):
        output = self.simulate_piped_detection(str(self.FIXTURES_DIR / "test.md"), tmp_path)
        assert self.has_markdown_formatting(output), "Piped Markdown should have Rich formatting"
