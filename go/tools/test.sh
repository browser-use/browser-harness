#!/bin/sh
# Same toolchain pin as the Browser Use Go backend; tests always run with the race detector.
# A local Chrome, when present, also runs the real-browser concurrency tests in internal/e2e.
set -eu
module=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export GOTOOLCHAIN=go1.26.0 GORACE=atexit_sleep_ms=0
cd "$module"
if [ -z "${BH_TEST_CDP_URL:-}" ]; then
	chrome=$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)
	if [ -n "$chrome" ]; then
		profile=$(mktemp -d)
		port=$(( 20000 + $$ % 20000 ))
		"$chrome" --headless=new --no-sandbox --remote-debugging-address=127.0.0.1 --remote-debugging-port="$port" \
			--user-data-dir="$profile" about:blank >/dev/null 2>&1 &
		chrome_pid=$!
		# Chrome helpers outlive the main process briefly; cleanup must never fail the run.
		trap 'status=$?; set +e; kill "$chrome_pid" 2>/dev/null; wait "$chrome_pid" 2>/dev/null; sleep 1; rm -rf "$profile" 2>/dev/null; exit "$status"' EXIT
		trap 'exit 129' HUP
		trap 'exit 130' INT
		trap 'exit 143' TERM
		export BH_TEST_CDP_URL="http://127.0.0.1:$port"
	else
		echo "no Chrome found: skipping real-browser tests" >&2
	fi
fi
go vet -mod=readonly ./...
go test -mod=readonly -race -count=1 -parallel=8 -timeout=5m ./...
