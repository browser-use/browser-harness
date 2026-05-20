"""Load and query the model-compatibility.json registry (issue #329)."""

from __future__ import annotations

import json
import re
import sys
from importlib import resources
from pathlib import Path
from typing import Any

VALID_STATUSES = frozenset({"verified", "works", "unknown", "broken"})

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([bB])\b")


def _registry_bytes() -> bytes:
    """Load registry JSON: repo root when developing from a src/ checkout (#329), else bundled copy."""
    here = Path(__file__).resolve().parent
    if here.name == "browser_harness" and here.parent.name == "src":
        root = here.parents[2] / "model-compatibility.json"
        if root.is_file():
            return root.read_bytes()
    bundled = here / "model-compatibility.json"
    if bundled.is_file():
        return bundled.read_bytes()
    return resources.files(__package__).joinpath("model-compatibility.json").read_bytes()


def load_registry() -> list[dict[str, Any]]:
    raw = json.loads(_registry_bytes().decode("utf-8"))
    if not isinstance(raw, list):
        raise ValueError("registry must be a JSON array")
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"entry {i} must be an object")
        for key in ("model", "provider", "status", "notes", "last_tested"):
            if key not in row:
                raise ValueError(f"entry {i} missing required field {key!r}")
            if not isinstance(row[key], str):
                raise ValueError(f"entry {i} field {key!r} must be a string")
        if row["status"] not in VALID_STATUSES:
            raise ValueError(
                f"entry {i} invalid status {row['status']!r}; "
                f"expected one of {sorted(VALID_STATUSES)}"
            )
        ps = row.get("parameter_size_b")
        if ps is not None and not isinstance(ps, (int, float)):
            raise ValueError(f"entry {i} parameter_size_b must be a number or omitted")
        out.append(row)
    return out


def parse_size_b(token: str) -> float:
    """Parse values like '35b', '8.9B', '70' (treated as billions)."""
    t = token.strip().lower()
    if not t:
        raise ValueError("empty size")
    m = _SIZE_RE.search(t)
    if m:
        return float(m.group(1))
    if t.endswith("b") and t[:-1].replace(".", "", 1).isdigit():
        return float(t[:-1])
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        return float(t)
    raise ValueError(f"unrecognized size token: {token!r}")


def infer_parameter_size_b(entry: dict[str, Any]) -> float | None:
    ps = entry.get("parameter_size_b")
    if isinstance(ps, (int, float)):
        return float(ps)
    name = entry.get("model", "")
    if not isinstance(name, str):
        return None
    m = _SIZE_RE.search(name)
    if m:
        return float(m.group(1))
    return None


def _format_row(entry: dict[str, Any]) -> str:
    sz = infer_parameter_size_b(entry)
    sz_s = f"{sz:g}B" if sz is not None else "—"
    return f"{entry['model']}\t{entry['provider']}\t{entry['status']}\t{sz_s}\t{entry['last_tested']}"


def models_list(subargs: list[str]) -> int:
    if not subargs or subargs[0] != "list":
        print("usage: browser-harness models list [--min-size <n>b] [--status <status>]", file=sys.stderr)
        return 2

    i = 1
    min_b: float | None = None
    status_filter: str | None = None
    while i < len(subargs):
        a = subargs[i]
        if a == "--min-size":
            if i + 1 >= len(subargs):
                print("error: --min-size requires a value (e.g. 35b)", file=sys.stderr)
                return 2
            try:
                min_b = parse_size_b(subargs[i + 1])
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
            i += 2
            continue
        if a == "--status":
            if i + 1 >= len(subargs):
                print("error: --status requires a value", file=sys.stderr)
                return 2
            status_filter = subargs[i + 1].strip().lower()
            if status_filter not in VALID_STATUSES:
                print(
                    f"error: unknown status {subargs[i + 1]!r}; "
                    f"expected one of {sorted(VALID_STATUSES)}",
                    file=sys.stderr,
                )
                return 2
            i += 2
            continue
        print(f"error: unexpected argument {a!r}", file=sys.stderr)
        return 2

    try:
        rows = load_registry()
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"error: failed to load model registry: {e}", file=sys.stderr)
        return 1

    filtered: list[dict[str, Any]] = []
    for row in rows:
        if status_filter is not None and row["status"] != status_filter:
            continue
        if min_b is not None:
            sz = infer_parameter_size_b(row)
            if sz is None or sz < min_b:
                continue
        filtered.append(row)

    print("model\tprovider\tstatus\tsize\tlast_tested")
    for row in filtered:
        print(_format_row(row))
    return 0


def resolve_model(query: str, rows: list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    exact = [r for r in rows if r["model"].lower() == q]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return exact
    substr = [r for r in rows if q in r["model"].lower()]
    if len(substr) == 1:
        return substr[0]
    return substr


def print_model_info(name: str) -> int:
    try:
        rows = load_registry()
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"error: failed to load model registry: {e}", file=sys.stderr)
        return 1

    hit = resolve_model(name, rows)
    if isinstance(hit, list) and not hit:
        print(f"no model matched {name!r}", file=sys.stderr)
        return 1
    if isinstance(hit, list):
        names = ", ".join(repr(r["model"]) for r in hit)
        print(f"ambiguous query {name!r}; matches: {names}", file=sys.stderr)
        return 1

    entry = hit
    sz = infer_parameter_size_b(entry)
    print(f"model:          {entry['model']}")
    print(f"provider:       {entry['provider']}")
    print(f"status:         {entry['status']}")
    print(f"last_tested:    {entry['last_tested']}")
    if sz is not None:
        print(f"parameter_size: {sz:g}B")
    print(f"notes:\n{entry['notes']}")
    return 0


def models_main(argv: list[str]) -> int:
    if not argv:
        print("usage: browser-harness models list [options]", file=sys.stderr)
        return 2
    if argv[0] == "list":
        return models_list(argv)
    print("usage: browser-harness models list [--min-size <n>b] [--status <s>]", file=sys.stderr)
    return 2
