from __future__ import annotations

import json
import re
import socket
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

SITE_PROFILES: dict[str, dict[str, Any]] = {
    "agm": {
        "url": "https://aquaguardmanagement.com",
        "markers": ["Aqua-Guard", "Pool Management", "Training", "Employment"],
        "routes": [
            {"path": "/", "slug": "root", "markers": ["Aqua-Guard", "Pool Management"]},
            {"path": "/services", "slug": "services", "markers": ["Services", "Pool Management"]},
            {"path": "/training", "slug": "training", "markers": ["Training", "Certification"]},
            {"path": "/employment", "slug": "employment", "markers": ["Employment", "Lifeguard"]},
            {"path": "/contact", "slug": "contact", "markers": ["Contact", "Quote"]},
        ],
    },
    "oee-oracle": {
        "url": "https://oracle.odinseyeenterprises.com",
        "markers": ["THE ORACLE", "LOGOS", "Grimoire", "Birth Chord"],
        "routes": [
            {"path": "/", "slug": "root", "markers": ["THE ORACLE", "LOGOS", "Grimoire"]},
            {"path": "/pricing", "slug": "pricing", "markers": ["Acolyte", "Architect", "Hermit"]},
            {"path": "/developers", "slug": "developers", "markers": ["API", "LOGOS", "Developers"]},
            {"path": "/free-chart", "slug": "free-chart", "markers": ["Free", "Chart"]},
            {"path": "/login", "slug": "login", "markers": ["Login", "Sanctum"]},
        ],
    },
}


class _SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.title_parts: list[str] = []
        self.current_h1: list[str] = []
        self.h1: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
            self.current_h1 = []
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False
            text = " ".join(part.strip() for part in self.current_h1 if part.strip()).strip()
            if text:
                self.h1.append(re.sub(r"\s+", " ", text))
            self.current_h1 = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self.current_h1.append(data)


def _normalize_links(base_url: str, links: list[str]) -> list[str]:
    base = urlparse(base_url)
    out: list[str] = []
    seen: set[str] = set()
    for href in links:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != base.netloc:
            continue
        normalized = parsed._replace(fragment="").geturl()
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def analyze_html(url: str, html: str) -> dict[str, Any]:
    parser = _SiteParser()
    parser.feed(html)
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    internal_links = _normalize_links(url, parser.links)
    issues: list[str] = []
    if not title:
        issues.append("missing_title")
    if not parser.h1:
        issues.append("missing_h1")
    return {
        "title": title,
        "h1": parser.h1,
        "internal_links": internal_links,
        "issues": issues,
    }


def evaluate_markers(text: str, markers: list[str]) -> dict[str, list[str]]:
    lowered = text.lower()
    present: list[str] = []
    missing: list[str] = []
    for marker in markers:
        if marker.lower() in lowered:
            present.append(marker)
        else:
            missing.append(marker)
    return {"present": present, "missing": missing}


def write_packet(outdir: Path, packet: dict[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "packet.json").write_text(json.dumps(packet, indent=2))
    lines = [
        "# Browser Evidence Packet",
        "",
        f"- **Packet ID:** {packet['packet_id']}",
        f"- **Created At:** {packet['created_at']}",
        f"- **Operator:** {packet['operator']}",
        f"- **Node:** {packet['node']}",
        f"- **Lane:** {packet['lane']}",
        f"- **Workflow:** {packet['workflow']}",
        f"- **Objective:** {packet['objective']}",
        "",
        "## Console Context",
        f"- **Console:** {packet['console']}",
        f"- **Page Title:** {packet['page_title']}",
        f"- **Page URL:** {packet['page_url']}",
        f"- **Object Under Inspection:** {packet['object_under_inspection']}",
        "",
        "## Findings",
        f"- **Observed State:** {packet['observed_state']}",
        f"- **Expected State:** {packet['expected_state']}",
        f"- **Drift / Issue:** {packet['drift_or_issue']}",
        f"- **Risk Level:** {packet['risk_level']}",
        "",
        "## Action",
        f"- **Recommended Next Action:** {packet['recommended_next_action']}",
        f"- **Approval Required:** {packet['approval_required']}",
        "",
        "## Evidence",
        f"- **Screenshot Paths:** {packet['screenshot_paths']}",
        f"- **Supporting Artifacts:** {packet['supporting_artifacts']}",
        "",
        "## Notes",
        str(packet.get("notes", "")),
        "",
    ]
    (outdir / "packet.md").write_text("\n".join(lines))


def fetch_html(url: str) -> tuple[str, dict[str, str]]:
    req = Request(url, headers={"User-Agent": "CathedralBrowserAudit/1.0"})
    with urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        body = resp.read().decode(charset, errors="replace")
        headers = {k.lower(): v for k, v in resp.headers.items()}
        headers[":status"] = str(resp.status)
    return body, headers


def _risk_from_issues(issues: list[str]) -> str:
    if not issues:
        return "low"
    if "missing_title" in issues and "missing_h1" in issues:
        return "high"
    if "missing_expected_markers" in issues:
        return "high"
    return "medium"


def _packet_root(stamp: datetime, packet_id: str) -> Path:
    return Path.home() / "Cathedral" / "state" / "browser-observatory" / "packets" / stamp.strftime("%Y") / stamp.strftime("%m") / stamp.strftime("%d") / packet_id


def _make_route_packet(url: str, workflow: str, lane: str, packet_id: str, outdir: Path, route_label: str, markers: list[str]) -> dict[str, Any]:
    html, headers = fetch_html(url)
    analysis = analyze_html(url, html)
    marker_result = evaluate_markers(html, markers)
    if marker_result["missing"]:
        analysis["issues"].append("missing_expected_markers")
    packet = {
        "packet_id": packet_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operator": Path.home().name,
        "node": socket.gethostname(),
        "lane": lane,
        "workflow": workflow,
        "objective": f"Audit {url}",
        "console": "public-web",
        "page_title": analysis["title"],
        "page_url": url,
        "object_under_inspection": route_label,
        "observed_state": f"status={headers.get(':status')} markers_present={marker_result['present']} markers_missing={marker_result['missing']} h1={analysis['h1'][:2]}",
        "expected_state": f"Route markers should be present: {markers}",
        "drift_or_issue": ", ".join(analysis["issues"]) if analysis["issues"] else "",
        "risk_level": _risk_from_issues(analysis["issues"]),
        "recommended_next_action": "Review route IA/content regression if markers are missing; otherwise keep as healthy.",
        "approval_required": "false",
        "screenshot_paths": [],
        "supporting_artifacts": [str(outdir / "analysis.json")],
        "notes": f"server={headers.get('server','')} content_type={headers.get('content-type','')} internal_link_count={len(analysis['internal_links'])}",
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "analysis.json").write_text(json.dumps({"headers": headers, **analysis, "markers": marker_result}, indent=2))
    write_packet(outdir, packet)
    return packet


def make_packet(url: str, workflow: str = "public-site-smoke", lane: str = "deploy") -> tuple[Path, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    hostname = urlparse(url).netloc.replace(":", "-")
    packet_id = f"{stamp}-{lane}-{hostname}"
    outdir = _packet_root(now, packet_id)
    packet = _make_route_packet(url, workflow, lane, packet_id, outdir, urlparse(url).path or "/", [])
    return outdir, packet


def audit_profile(profile_name: str, profile: dict[str, Any] | None = None, workflow: str = "public-site-smoke", lane: str = "deploy") -> tuple[Path, dict[str, Any]]:
    profile = profile or SITE_PROFILES[profile_name]
    base_url = profile["url"]
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    root = _packet_root(now, f"{stamp}-{lane}-{profile_name}")
    routes_root = root / "routes"
    route_summaries: list[dict[str, Any]] = []
    overall_issues: list[str] = []
    worst_risk = "low"
    risk_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for route in profile.get("routes", [{"path": "/", "slug": "root", "markers": profile.get("markers", [])}]):
        path = route["path"]
        slug = route.get("slug") or (path.strip("/").replace("/", "-") or "root")
        url = urljoin(base_url, path)
        packet = _make_route_packet(url, workflow, lane, f"{stamp}-{lane}-{profile_name}-{slug}", routes_root / slug, slug, route.get("markers", []))
        route_summaries.append({
            "slug": slug,
            "url": url,
            "risk_level": packet["risk_level"],
            "drift_or_issue": packet["drift_or_issue"],
            "page_title": packet["page_title"],
        })
        if packet["drift_or_issue"]:
            overall_issues.append(f"{slug}:{packet['drift_or_issue']}")
        if risk_rank[packet["risk_level"]] > risk_rank[worst_risk]:
            worst_risk = packet["risk_level"]
    summary = {
        "profile": profile_name,
        "base_url": base_url,
        "workflow": workflow,
        "lane": lane,
        "risk_level": worst_risk,
        "issues": overall_issues,
        "routes": route_summaries,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
    packet = {
        "packet_id": f"{stamp}-{lane}-{profile_name}",
        "created_at": now.isoformat(),
        "operator": Path.home().name,
        "node": socket.gethostname(),
        "lane": lane,
        "workflow": workflow,
        "objective": f"Profile audit {profile_name}",
        "console": "public-web",
        "page_title": profile_name,
        "page_url": base_url,
        "object_under_inspection": profile_name,
        "observed_state": f"routes_checked={len(route_summaries)} highest_risk={worst_risk}",
        "expected_state": "All profiled routes should load and satisfy expected content markers.",
        "drift_or_issue": "; ".join(overall_issues),
        "risk_level": worst_risk,
        "recommended_next_action": "Review flagged route packets if any route is medium/high risk; otherwise keep the profile healthy.",
        "approval_required": "false",
        "screenshot_paths": [],
        "supporting_artifacts": [str(root / "summary.json")],
        "notes": f"routes={[r['slug'] for r in route_summaries]}",
    }
    write_packet(root, packet)
    return root, packet


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: browser-site-audit <url> [url ...] | --profile <name> [--profile <name> ...]", file=sys.stderr)
        return 1
    args = sys.argv[1:]
    if args[0] == "--profile":
        names = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--profile"]
        for name in names:
            if name not in SITE_PROFILES:
                print(f"unknown profile: {name}", file=sys.stderr)
                return 2
            outdir, packet = audit_profile(name)
            print(f"profile:{name} -> {outdir} risk={packet['risk_level']}")
        return 0
    for url in args:
        outdir, packet = make_packet(url)
        print(f"{url} -> {outdir} risk={packet['risk_level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
