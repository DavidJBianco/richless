#!/usr/bin/env python3
"""Generate the Homebrew formula for richless.

Runs homebrew-pypi-poet to generate the base formula, then patches in
project-specific customizations (description, license, shell script
installation, caveats, and test block).

Prerequisites:
    pip install richless homebrew-pypi-poet

Usage:
    python scripts/generate-formula.py > Formula/richless.rb

The script must be run in an environment where both richless and
homebrew-pypi-poet are installed (poet needs the package in sys.path
to resolve dependencies).
"""

import re
import subprocess
import sys


def generate_base_formula() -> str:
    """Run poet -f richless and return the output."""
    result = subprocess.run(
        ["poet", "-f", "richless"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error running poet: {result.stderr}", file=sys.stderr)
        print(
            "\nMake sure richless and homebrew-pypi-poet are installed in the "
            "current environment:\n  pip install richless homebrew-pypi-poet",
            file=sys.stderr,
        )
        sys.exit(1)
    return result.stdout


def patch_formula(formula: str) -> str:
    """Patch the poet-generated formula with project customizations."""

    # Replace the placeholder description
    formula = formula.replace(
        'desc "Shiny new formula"',
        'desc "LESSOPEN filter for Markdown rendering and syntax highlighting with less"',
    )

    # Add homepage and license after the sha256 line for the main package
    # (not the resource sha256 lines -- target the first one before any resource blocks)
    formula = re.sub(
        r'(  sha256 "[0-9a-f]+")\n(\n  resource)',
        r'\1\n  license "MIT"\n  head "https://github.com/DavidJBianco/richless.git", branch: "main"\n\2',
        formula,
        count=1,
    )

    # If that didn't match (e.g., no resources before the sha256),
    # try adding after the first sha256 line
    if "license" not in formula:
        formula = re.sub(
            r'(  sha256 "[0-9a-f]+")',
            r'\1\n  license "MIT"\n  head "https://github.com/DavidJBianco/richless.git", branch: "main"',
            formula,
            count=1,
        )

    # Add homepage after the desc line
    formula = re.sub(
        r'(  desc "[^"]+")',
        r'\1\n  homepage "https://github.com/DavidJBianco/richless"',
        formula,
    )

    # Replace the install block to include shell script installation
    formula = formula.replace(
        "  def install\n    virtualenv_install_with_resources\n  end",
        '  def install\n'
        '    virtualenv_install_with_resources\n'
        '\n'
        '    # Install the shell integration script\n'
        '    (share/"richless").install buildpath/"richless-init.sh"\n'
        '  end',
    )

    # Replace the test block and add caveats before it
    old_test = re.search(r"  test do.*?  end\nend", formula, re.DOTALL)
    if old_test:
        formula = formula[:old_test.start()] + CAVEATS_AND_TEST + "\nend\n"
    else:
        # If there's no test block, add before the final "end"
        formula = formula.rstrip()
        if formula.endswith("end"):
            formula = formula[:-3] + CAVEATS_AND_TEST + "\nend\n"

    return formula


CAVEATS_AND_TEST = """\
  def caveats
    <<~EOS
      To enable the shell integration (recommended), add this to your
      ~/.bashrc or ~/.zshrc:

        source #{share}/richless/richless-init.sh

      Or for basic LESSOPEN integration only:

        export LESSOPEN="|#{bin}/richless %s"
        export LESS="-R"
    EOS
  end

  test do
    (testpath/"test.md").write("# Hello\\n\\nThis is **bold** text.\\n")
    output = shell_output("#{bin}/richless #{testpath}/test.md")
    assert_match "Hello", output

    (testpath/"test.py").write("print('hello')\\n")
    output = shell_output("#{bin}/richless #{testpath}/test.py")
    assert_match "hello", output
  end
"""


def main():
    base = generate_base_formula()
    patched = patch_formula(base)
    print(patched, end="")


if __name__ == "__main__":
    main()
