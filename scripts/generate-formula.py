#!/usr/bin/env python3
"""Generate the Homebrew formula for richless.

Fetches package metadata from the PyPI JSON API to build the formula
directly, then applies project-specific customizations (description,
license, shell script installation, caveats, and test block).

Usage:
    python scripts/generate-formula.py > Formula/richless.rb

No third-party dependencies required — uses only the standard library.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request

PACKAGE_NAME = "richless"

# Dependencies to include as resource blocks (transitive closure).
# Keep this in sync with what `pip install richless` actually pulls in.
DEPENDENCIES = [
    "markdown-it-py",
    "mdurl",
    "pygments",
    "rich",
]


def fetch_pypi_metadata(package: str) -> dict:
    """Fetch package metadata from the PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_sdist_info(meta: dict) -> tuple[str, str]:
    """Return (url, sha256) for the sdist from PyPI metadata."""
    for entry in meta["urls"]:
        if entry["packagetype"] == "sdist":
            return entry["url"], entry["digests"]["sha256"]
    raise RuntimeError(
        f"No sdist found for {meta['info']['name']} {meta['info']['version']}"
    )


def build_formula() -> str:
    """Build the complete Homebrew formula string."""
    # Fetch main package info
    main_meta = fetch_pypi_metadata(PACKAGE_NAME)
    main_url, main_sha256 = get_sdist_info(main_meta)
    version = main_meta["info"]["version"]

    # Fetch dependency info
    resources: list[str] = []
    for dep in DEPENDENCIES:
        dep_meta = fetch_pypi_metadata(dep)
        dep_url, dep_sha256 = get_sdist_info(dep_meta)
        # Use the canonical PyPI project name for the resource block
        dep_name = dep_meta["info"]["name"]
        resources.append(
            f'  resource "{dep_name}" do\n'
            f'    url "{dep_url}"\n'
            f'    sha256 "{dep_sha256}"\n'
            f"  end"
        )

    resource_block = "\n\n".join(resources)

    formula = f"""\
class Richless < Formula
  include Language::Python::Virtualenv

  desc "LESSOPEN filter for Markdown rendering and syntax highlighting with less"
  homepage "https://github.com/DavidJBianco/richless"
  url "{main_url}"
  sha256 "{main_sha256}"
  license "MIT"
  head "https://github.com/DavidJBianco/richless.git", branch: "main"

  depends_on "python@3.13"

{resource_block}

  def install
    virtualenv_install_with_resources

    # Install the shell integration script
    (share/"richless").install buildpath/"richless-init.sh"
  end

  def caveats
    <<~EOS
      To enable the shell integration (recommended), add this to your
      ~/.bashrc or ~/.zshrc:

        source #{{share}}/richless/richless-init.sh

      Or for basic LESSOPEN integration only:

        export LESSOPEN="|#{{bin}}/richless %s"
        export LESS="-R"
    EOS
  end

  test do
    (testpath/"test.md").write("# Hello\\n\\nThis is **bold** text.\\n")
    output = shell_output("#{{bin}}/richless #{{testpath}}/test.md")
    assert_match "Hello", output

    (testpath/"test.py").write("print('hello')\\n")
    output = shell_output("#{{bin}}/richless #{{testpath}}/test.py")
    assert_match "hello", output
  end
end
"""
    return formula


def main():
    try:
        formula = build_formula()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(formula, end="")


if __name__ == "__main__":
    main()
