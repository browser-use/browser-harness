#!/bin/sh
set -eu
mode=${1:---check}
case "$mode" in
    --check|--write) ;;
    *) echo "Usage: sh tools/go-lint/format.sh [--check|--write]" >&2; exit 2 ;;
esac
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
cd "$root"
export GOTOOLCHAIN=go1.26.0
gofmt="$(go env GOROOT)/bin/gofmt"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
# Include tests and new source files; generators own their marked output.
git ls-files --cached --others --exclude-standard -z -- ':(glob)go/**/*.go' >"$work/all"
xargs -0 -r sh -c '
    for file do
        if ! grep -Eq "^// Code generated .* DO NOT EDIT\.$" "$file"; then
            printf "%s\000" "$file"
        fi
    done
' sh <"$work/all" >"$work/files"
if [ "$mode" = --write ]; then
    xargs -0 -r "$gofmt" -w <"$work/files"
    echo 'Go formatting applied'
else
    xargs -0 -r "$gofmt" -l <"$work/files" >"$work/dirty"
    if [ -s "$work/dirty" ]; then
        cat "$work/dirty"
        echo 'Run sh tools/go-lint/format.sh --write to format these files' >&2
        exit 1
    fi
    echo 'Go formatting PASS'
fi
