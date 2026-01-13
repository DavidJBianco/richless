#!/bin/sh
# mdless-init.sh
#
# Shell integration for mdless - transparent Markdown rendering in less
#
# Usage: Add this line to your ~/.bashrc, ~/.zshrc, or ~/.profile:
#   source /path/to/mdless-init.sh
#
# This will override the 'less' command to automatically render Markdown files
# and support additional features like piped input and force-markdown mode.
#
# Compatible with: sh, bash, zsh

# Only initialize if mdless is available
if ! command -v mdless >/dev/null 2>&1; then
    echo "Warning: mdless command not found. Please install mdless first." >&2
    return 1 2>/dev/null || exit 1
fi

# Configure LESSOPEN for automatic Markdown detection
export LESSOPEN="|mdless %s"
export LESS="${LESS:--R}"  # Add -R flag if LESS not already set, otherwise preserve existing

# Transparent wrapper function for less
# This handles cases where LESSOPEN doesn't work (piped input, force markdown)
less() {
    # Check if stdin is a pipe (not a terminal)
    if [ ! -t 0 ]; then
        # Reading from pipe - check for --md flag (must be exact match, not substring)
        local force_markdown=0
        for arg in "$@"; do
            case "$arg" in
                --md|-m) force_markdown=1; break ;;
            esac
        done

        # Save piped input to temp file
        local tmpfile
        tmpfile=$(mktemp "${TMPDIR:-/tmp}/mdless.XXXXXX") || return 1
        cat > "$tmpfile"

        # Collect non --md/--m arguments for less
        local clean_args=""
        for arg in "$@"; do
            case "$arg" in
                --md|-m)
                    # Skip our custom flag
                    ;;
                *)
                    clean_args="${clean_args} ${arg}"
                    ;;
            esac
        done

        # Check if we should render as markdown
        if [ $force_markdown -eq 1 ]; then
            mdless --md "$tmpfile" | command less -R ${clean_args}
        else
            # Check for YAML/JSON first - these should use syntax highlighting, not markdown
            first_line=$(head -1 "$tmpfile" 2>/dev/null)
            if printf '%s\n' "$first_line" | grep -qE '^---$|^%YAML|^[[:space:]]*[{[]'; then
                # Looks like YAML or JSON - use syntax highlighting
                mdless "$tmpfile" | command less -R ${clean_args}
            # Check for YAML with comments: first non-comment line has key: pattern
            elif grep -m1 -vE '^[[:space:]]*#|^[[:space:]]*$' "$tmpfile" 2>/dev/null | grep -qE '^[a-zA-Z_][a-zA-Z0-9_-]*:'; then
                # Looks like YAML with comments - use syntax highlighting
                mdless "$tmpfile" | command less -R ${clean_args}
            # Auto-detect: check if piped content looks like markdown
            elif grep -qE '^#{1,6} |^\* |^- |^[0-9]+\. |^\[.*\]\(.*\)|^```|\*\*.*\*\*|^>|^\||^-{3,}|^={3,}' "$tmpfile" 2>/dev/null; then
                mdless --md "$tmpfile" | command less -R ${clean_args}
            else
                command less -R ${clean_args} "$tmpfile"
            fi
        fi

        # Clean up temp file
        rm -f "$tmpfile"
    else
        # No pipe - check for --md flag among arguments (must be exact match, not substring)
        local force_markdown=0
        local has_md_flag=0

        for arg in "$@"; do
            case "$arg" in
                --md|-m) has_md_flag=1; break ;;
            esac
        done

        if [ $has_md_flag -eq 1 ]; then
            # Build arrays for files and options
            local files=""
            local opts=""

            for arg in "$@"; do
                case "$arg" in
                    --md|-m)
                        force_markdown=1
                        ;;
                    -*)
                        opts="${opts} ${arg}"
                        ;;
                    *)
                        files="${files} ${arg}"
                        ;;
                esac
            done

            # Render each file with markdown
            for file in ${files}; do
                if [ -n "$file" ]; then
                    mdless --md "$file" | command less -R ${opts}
                fi
            done
        else
            # Normal less operation - let LESSOPEN handle it
            command less "$@"
        fi
    fi
}

# Export the function so it's available in subshells (bash only)
# Note: zsh doesn't support 'export -f', but functions are automatically available in subshells
if [ -n "$BASH_VERSION" ]; then
    export -f less 2>/dev/null || true
fi

# Suppress any function output
: # null command to ensure clean sourcing
