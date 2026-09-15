#!/bin/sh
# Run the current regression suite in an isolated Linux container.
set -eu
version=${1:-3.12}
selection=${2:-'not test_audit_probe and not test_audit_performance'}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out=${3:-"$root/audit/results/redesign-linux-$version"}
case "$version" in 3.12|3.13) ;; *) echo 'Use 3.12 or 3.13' >&2; exit 2 ;; esac
mkdir -p "$out"
docker build --build-arg "PYTHON_VERSION=$version" -t "richless-audit:$version" "$root/audit"
docker run --rm -e "AUDIT_SELECTION=$selection" \
  --mount "type=bind,source=$root,target=/source,readonly" \
  --mount "type=bind,source=$out,target=/results" \
  "richless-audit:$version" sh -c '
    mkdir -p /tmp/project/audit
    cp /source/richless.py /source/richless-init.sh /source/pyproject.toml /source/uv.lock /source/README.md /source/LICENSE /tmp/project/
    cp -R /source/tests /tmp/project/tests
    cp /source/audit/incremental_markdown.py /tmp/project/audit/
    cd /tmp/project
    RICHLESS_AUDIT_DIR=/results uv run --frozen --extra dev pytest tests/test_richless.py \
      -k "$AUDIT_SELECTION" -q --tb=short --junitxml=/results/junit.xml
  '
