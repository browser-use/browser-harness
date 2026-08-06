"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import urlparse


# --- Invicti Enterprise API helpers (netsparkercloud.com) ---
# These helpers are intentionally read-oriented: they make it easy for an agent to
# answer questions about websites, schedules, vulnerabilities/issues, etc.

_INVICTI_DEFAULT_BASE_URL = "https://www.netsparkercloud.com"


def _invicti_repo_root() -> Path:
    # agent-workspace/agent_helpers.py -> repo_root/agent-workspace
    return Path(__file__).resolve().parents[1]


def _invicti_maybe_load_env() -> None:
    """Best-effort load of INVICTI_* variables from common .env locations.

    browser_harness.helpers already loads REPO_ROOT/.env and agent-workspace/.env.
    This additionally supports a domain-scoped env file at domain-skills/invicti/.env.
    """

    if os.environ.get("INVICTI_USER_ID") and os.environ.get("INVICTI_TOKEN"):
        return

    candidates = [
        _invicti_repo_root() / ".env",
        _invicti_repo_root() / "agent-workspace" / ".env",
        _invicti_repo_root() / "domain-skills" / "invicti" / ".env",
    ]
    wanted = {"INVICTI_BASE_URL", "INVICTI_USER_ID", "INVICTI_TOKEN"}

    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k not in wanted:
                continue
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k, v)


def invicti_creds() -> tuple[str, str, str]:
    """Return (base_url, user_id, token). Raises if missing."""

    _invicti_maybe_load_env()

    base = (os.environ.get("INVICTI_BASE_URL") or _INVICTI_DEFAULT_BASE_URL).rstrip("/")
    uid = (os.environ.get("INVICTI_USER_ID") or "").strip()
    tok = (os.environ.get("INVICTI_TOKEN") or "").strip()

    if not uid or not tok:
        raise RuntimeError(
            "Missing Invicti API credentials. Set INVICTI_USER_ID and INVICTI_TOKEN "
            "(recommended: repo .env or agent-workspace/.env)."
        )

    return base, uid, tok


@contextmanager
def invicti_client(timeout: float = 60.0) -> Iterator["httpx.Client"]:
    """Context-managed httpx client authenticated with Invicti Basic Auth."""

    import httpx

    base, uid, tok = invicti_creds()
    with httpx.Client(base_url=base, auth=(uid, tok), timeout=timeout) as c:
        yield c


def invicti_request(
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json: Any = None,
    timeout: float = 60.0,
    allow_404: bool = False,
) -> Any:
    """Call the Invicti API.

    - Returns decoded JSON when content-type is application/json.
    - Returns text otherwise.
    - If allow_404=True and the API returns 404, returns None.
    """

    method = method.upper().strip()

    with invicti_client(timeout=timeout) as c:
        r = c.request(method, path, params=params, json=json)
        if allow_404 and r.status_code == 404:
            return None
        r.raise_for_status()

        ct = (r.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if ct == "application/json":
            return r.json()
        return r.text


def invicti_get(
    path: str,
    params: Optional[dict[str, Any]] = None,
    *,
    timeout: float = 60.0,
    allow_404: bool = False,
) -> Any:
    return invicti_request("GET", path, params=params, timeout=timeout, allow_404=allow_404)


def invicti_paged_list(
    path: str,
    params: Optional[dict[str, Any]] = None,
    *,
    page_size: int = 200,
    max_pages: Optional[int] = None,
    timeout: float = 60.0,
) -> tuple[list[Any], dict[str, Any]]:
    """Fetch a list endpoint.

    Supports both shapes:
    - Paged wrapper dict with a "List" field
    - Raw JSON arrays

    max_pages limits the number of pages fetched (not the page index).
    """

    items: list[Any] = []
    meta: dict[str, Any] = {}

    p0 = dict(params or {})
    page = int(p0.get("page") or 1)
    pages_fetched = 0

    while True:
        pages_fetched += 1

        p = dict(params or {})
        p["page"] = page
        p.setdefault("pageSize", page_size)

        data = invicti_get(path, params=p, timeout=timeout)

        if isinstance(data, dict) and "List" in data:
            items.extend(data.get("List") or [])
            meta = {
                k: data.get(k)
                for k in (
                    "TotalItemCount",
                    "PageNumber",
                    "PageSize",
                    "PageCount",
                    "HasNextPage",
                    "HasPreviousPage",
                )
                if k in data
            }

            if not data.get("HasNextPage"):
                break
            if max_pages is not None and pages_fetched >= max_pages:
                break

            page += 1
            continue

        if isinstance(data, list):
            items = data
            meta = {"TotalItemCount": len(items), "nonPaged": True}
            break

        meta = {"shape": type(data).__name__}
        break

    return items, meta


def invicti_website_get(query: str) -> Optional[dict[str, Any]]:
    """Get a website by name or URL. Returns None if not found."""

    data = invicti_get("/api/1.0/websites/get", params={"query": query}, allow_404=True)
    return data if isinstance(data, dict) else None


def invicti_website_search(search_term: str, *, page_size: int = 20) -> list[dict[str, Any]]:
    """Search websites by term (first page only)."""

    items, _ = invicti_paged_list(
        "/api/1.0/websites/searchlist",
        params={"searchTerm": search_term},
        page_size=page_size,
        max_pages=1,
    )
    return [x for x in items if isinstance(x, dict)]


def invicti_resolve_website(query: str, *, max_results: int = 10) -> list[dict[str, Any]]:
    """Return 0..N candidate website dicts for a name/URL query."""

    w = invicti_website_get(query)
    if w:
        return [w]

    term = query.strip()

    # If URL-ish, search by host first (often more stable).
    try:
        u = term if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", term) else "https://" + term
        host = urlparse(u).netloc
        if host:
            term = host
    except Exception:
        pass

    return invicti_website_search(term, page_size=max_results)[:max_results]


def _invicti_norm_urlish(value: str) -> str:
    """Normalize URL-ish strings for comparisons (ignore scheme, trim trailing '/')."""

    if not value:
        return ""

    v = value.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", v):
        v = "https://" + v

    p = urlparse(v)
    host = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/")
    return f"{host}{path}"


def invicti_list_scheduled_scans(
    *,
    page_size: int = 200,
    max_pages: Optional[int] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items, meta = invicti_paged_list(
        "/api/1.0/scans/list-scheduled",
        page_size=page_size,
        max_pages=max_pages,
    )
    return [x for x in items if isinstance(x, dict)], meta


def invicti_schedules_for_website(query: str) -> list[dict[str, Any]]:
    """Return scheduled scan entries whose TargetUrl matches a website query."""

    candidates = {_invicti_norm_urlish(query)}

    for w in invicti_resolve_website(query, max_results=3):
        candidates.add(_invicti_norm_urlish(w.get("RootUrl") or ""))
        candidates.add(_invicti_norm_urlish(w.get("Name") or ""))

    candidates = {c for c in candidates if c}

    schedules, _ = invicti_list_scheduled_scans(page_size=200, max_pages=None)

    out: list[dict[str, Any]] = []
    for s in schedules:
        targets: list[str] = []

        if isinstance(s.get("TargetUrl"), str) and s.get("TargetUrl"):
            targets.append(s["TargetUrl"])

        addl = s.get("AdditionalWebsites")
        if isinstance(addl, list):
            for x in addl:
                if isinstance(x, str):
                    targets.append(x)
                elif isinstance(x, dict):
                    for k in ("TargetUrl", "Url", "RootUrl"):
                        if isinstance(x.get(k), str) and x.get(k):
                            targets.append(x[k])
                            break

        if any(_invicti_norm_urlish(t) in candidates for t in targets if t):
            out.append(s)

    return out


def invicti_issue_counts(
    website_name: str,
    *,
    severities: Optional[list[str]] = None,
) -> dict[str, int]:
    """Return TotalItemCount per severity for /issues/allissues (rawDetails=false)."""

    severities = severities or [
        "Critical",
        "High",
        "Medium",
        "Low",
        "Information",
        "BestPractice",
    ]

    counts: dict[str, int] = {}
    for sev in severities:
        data = invicti_get(
            "/api/1.0/issues/allissues",
            params={
                "webSiteName": website_name,
                "severity": sev,
                "page": 1,
                "pageSize": 1,
                "rawDetails": False,
            },
        )
        total = data.get("TotalItemCount") if isinstance(data, dict) else None
        counts[sev] = int(total or 0)

    return counts


def invicti_issues_sample(
    website_name: str,
    *,
    severity: str = "Critical",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch up to `limit` issues for a website+severity (rawDetails=false)."""

    page_size = min(200, max(1, limit))
    max_pages = (limit + page_size - 1) // page_size

    items, _ = invicti_paged_list(
        "/api/1.0/issues/allissues",
        params={
            "webSiteName": website_name,
            "severity": severity,
            "rawDetails": False,
        },
        page_size=page_size,
        max_pages=max_pages,
    )

    out = [x for x in items if isinstance(x, dict)]
    return out[:limit]

