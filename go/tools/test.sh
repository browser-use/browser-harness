#!/bin/sh
# Same toolchain pin as the Browser Use Go backend; tests always run with the race detector.
set -eu
module=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export GOTOOLCHAIN=go1.26.0 GORACE=atexit_sleep_ms=0
cd "$module"
go vet -mod=readonly ./...
go test -mod=readonly -race -count=1 -parallel=8 -timeout=5m ./...
