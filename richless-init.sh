#!/bin/sh
# Source this file from sh, bash, or zsh. No input is consumed during setup.
less() {
    if command -v richless >/dev/null 2>&1; then
        command richless --pager "$@"
    else
        command less "$@"
    fi
}
if [ -n "${BASH_VERSION-}" ]; then
    export -f less 2>/dev/null || true
fi
:
