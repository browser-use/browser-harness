#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
export GOTOOLCHAIN=go1.26.0
binary=$(sh "$root/tools/go-lint/install.sh")
report=${GO_LINT_REPORT_DIR:-$(mktemp -d)}
mkdir -p "$report"
report=$(CDPATH= cd -- "$report" && pwd)
result=0
if sh "$root/tools/go-lint/format.sh" --check >"$report/format.log" 2>&1; then
    printf 'Go formatting PASS\n'
    echo 0 >"$report/format.exit"
else
    code=$?
    echo "$code" >"$report/format.exit"
    printf 'Go formatting FAIL (see %s)\n' "$report/format.log"
    result=1
fi
# The backend's cloudlint guards only apply to the cloud modules, so they are not run here.
if (cd "$root/go" && "$binary" run --config "$root/tools/go-lint/.golangci.yml" --max-issues-per-linter 0 --max-same-issues 0 --output.json.path "$report/go.json") >"$report/go.log" 2>&1; then
    printf 'go: standard lint PASS\n'
    echo 0 >"$report/go.exit"
else
    code=$?
    echo "$code" >"$report/go.exit"
    printf 'go: standard lint FAIL (see %s)\n' "$report/go.log"
    result=1
fi
printf 'Lint reports: %s\n' "$report"
exit "$result"
