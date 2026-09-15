# Changelog

## 0.4.0 (in preparation)

- Replace shell-side buffering and argument reconstruction with a Python-managed
  native pager invocation; preserve mixed-file sessions and exact filenames.
- Publish Markdown and syntax output progressively, with source-preserving raw
  recovery and bounded waiting for unresolved live Markdown.
- Support explicit formatted file following through `+F`, using temporary
  replacements only in those sessions.
- Restore native `-m`; add `--syntax` and `--init-path`.
- Include the integration script in Python distributions and document re-sourcing,
  copied-script upgrades, and rollback.
- Make audit correctness coverage part of local testing and cross-platform CI.

See README.md for intentional behavior changes and upgrade steps. This entry does
not indicate that the release has been published.
