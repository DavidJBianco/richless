# TODO

## Bugs & Fixes (High Priority)

- [ ] Remove `-m` short flag from shell wrapper -- conflicts with `less`'s built-in `-m` (verbose prompt)
- [ ] Fix binary/non-UTF-8 file handling -- exit cleanly with no output so `less` handles natively (currently fallback also tries UTF-8 and fails)
- [ ] Fix Zeek JSONL log handling -- no syntax highlighting, and `cat conn.log | jq | less` shows blank screen
- [ ] Add `trap` on EXIT/INT/TERM in shell wrapper to clean up temp files on Ctrl+C or kill

## Bugs & Fixes (Medium Priority)

- [ ] Fix `LESS` env var handling -- append `-R` if not already present, instead of only setting when `LESS` is unset
- [ ] Fix multi-file behavior with `--md` -- currently opens each file in separate `less` instance, losing `:n`/`:p` navigation

## Tooling & Quality

- [ ] Add ruff configuration to `pyproject.toml` and fix any lint issues
- [ ] Add mypy configuration to `pyproject.toml` and fix any type errors
- [ ] Add `.yml` test fixture and verify Pygments handles it correctly

## Future Enhancements

- [ ] Implement `RICHLESS_DEBUG=1` env var for debug logging to `~/.richless/debug.log`
- [ ] Git diff markers in the gutter (similar to `bat`)
- [ ] Snapshot/golden-file tests for Markdown rendering
- [ ] Theming / user configuration (requires design work)
- [ ] Fish shell integration (`richless-init.fish`)
- [ ] Nushell shell integration
- [ ] Test coverage reporting (pytest-cov)
