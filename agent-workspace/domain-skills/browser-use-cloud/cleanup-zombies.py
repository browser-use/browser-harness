"""Stop active Browser Use cloud browsers older than `--older-than` minutes.

Designed to be the live regression artefact for the cloud.md skill in this
folder — running it exercises GET /browsers + PATCH /browsers/{id}/stop on
the public API and surfaces every wire-shape gotcha the skill documents.

Usage:
    BROWSER_USE_API_KEY=... python cleanup-zombies.py
        # stop browsers running longer than 30 minutes (default)

    BROWSER_USE_API_KEY=... python cleanup-zombies.py --older-than 5 --dry-run
        # preview only; no PATCH /stop sent

    BROWSER_USE_API_KEY=... python cleanup-zombies.py --json
        # machine-readable output (one record per browser inspected)

Exit codes:
    0  any zombies stopped (or none needed)
    1  API error (auth, network, etc.)
    2  bad CLI args
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.browser-use.com/api/v3"


def _headers() -> dict[str, str]:
    key = os.environ.get("BROWSER_USE_API_KEY")
    if not key:
        sys.exit("BROWSER_USE_API_KEY is not set")
    return {
        "X-Browser-Use-API-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _call(method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=(json.dumps(body).encode() if body is not None else None),
        headers=_headers(),
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def list_active_browsers() -> list[dict]:
    """Return only sessions that are still alive (no `finishedAt`)."""
    out, page = [], 1
    while True:
        listing = _call("GET", f"/browsers?pageSize=100&pageNumber={page}")
        items = listing.get("items") or []
        if not items:
            break
        out.extend(b for b in items if not b.get("finishedAt"))
        if len(out) + sum(1 for b in items if b.get("finishedAt")) >= listing.get("totalItems", len(items)):
            break
        page += 1
    return out


def _parse_started(b: dict) -> datetime.datetime:
    """`startedAt` is ISO 8601 UTC with a trailing `Z`. Python <3.11 needs the swap."""
    return datetime.datetime.fromisoformat(b["startedAt"].replace("Z", "+00:00"))


def _to_float(v: str | None) -> float:
    """Cost / proxy fields come back as strings; tolerate `None` and empty."""
    return float(v) if v else 0.0


def stop_browser(browser_id: str) -> dict:
    return _call("PATCH", f"/browsers/{browser_id}", {"action": "stop"})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stop Browser Use cloud browsers older than N minutes.",
    )
    parser.add_argument("--older-than", type=int, default=30, metavar="MIN",
                        help="age threshold in minutes (default: 30)")
    parser.add_argument("--dry-run", action="store_true",
                        help="list zombies but do not call PATCH /stop")
    parser.add_argument("--json", action="store_true",
                        help="emit one JSON object per inspected browser")
    args = parser.parse_args()

    if args.older_than < 0:
        parser.error("--older-than must be non-negative")

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=args.older_than)

    try:
        active = list_active_browsers()
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"GET /browsers failed: HTTP {e.code} -- {e.read().decode('utf-8', 'replace')[:200]}\n")
        return 1
    except urllib.error.URLError as e:
        sys.stderr.write(f"GET /browsers network error: {e}\n")
        return 1

    stopped = 0
    for b in active:
        started = _parse_started(b)
        age_min = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds() / 60
        is_zombie = started < cutoff
        record = {
            "id": b["id"],
            "started_at": b["startedAt"],
            "age_minutes": round(age_min, 1),
            "browser_cost": _to_float(b.get("browserCost")),
            "proxy_cost": _to_float(b.get("proxyCost")),
            "proxy_used_mb": _to_float(b.get("proxyUsedMb")),
            "is_zombie": is_zombie,
            "action": "skipped",
        }
        if is_zombie:
            if args.dry_run:
                record["action"] = "would_stop"
            else:
                try:
                    final = stop_browser(b["id"])
                    record["action"] = "stopped"
                    record["final_browser_cost"] = _to_float(final.get("browserCost"))
                    record["final_proxy_cost"] = _to_float(final.get("proxyCost"))
                    stopped += 1
                except urllib.error.HTTPError as e:
                    record["action"] = f"stop_failed: HTTP {e.code}"
                except urllib.error.URLError as e:
                    record["action"] = f"stop_failed: {e.reason}"

        if args.json:
            print(json.dumps(record))
        else:
            tag = {
                "skipped": "OK",
                "would_stop": "DRY",
                "stopped": "STOP",
            }.get(record["action"], record["action"])
            print(
                f"[{tag}] {record['id']}  age={record['age_minutes']:5.1f}min  "
                f"cost=${record['browser_cost']+record['proxy_cost']:.4f}"
            )

    if not args.json:
        verb = "would stop" if args.dry_run else "stopped"
        print(f"summary: {len(active)} active session(s), {verb} {stopped if not args.dry_run else sum(1 for b in active if _parse_started(b) < cutoff)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
