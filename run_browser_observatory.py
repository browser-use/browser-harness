#!/usr/bin/env python3
from __future__ import annotations

import argparse
from public_site_audit import SITE_PROFILES, audit_profile


def main() -> int:
    parser = argparse.ArgumentParser(description='Run Cathedral browser observatory public-site audits.')
    parser.add_argument('--profile', action='append', dest='profiles', help='Profile name to audit; repeatable')
    parser.add_argument('--all', action='store_true', help='Audit all known profiles')
    parser.add_argument('--lane', default='deploy', help='Browser lane name')
    parser.add_argument('--workflow', default='public-site-smoke', help='Workflow label for packets')
    args = parser.parse_args()

    profiles = args.profiles or []
    if args.all:
        profiles = list(SITE_PROFILES.keys())
    if not profiles:
        parser.error('provide --profile NAME or --all')

    for name in profiles:
        if name not in SITE_PROFILES:
            parser.error(f'unknown profile: {name}')
        outdir, packet = audit_profile(name, workflow=args.workflow, lane=args.lane)
        print(f'{name} -> {outdir} risk={packet["risk_level"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
