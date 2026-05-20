# Supplier Coupang — Coupang 1P Supplier Hub

Use this domain skill for `supplier.coupang.com` Coupang 1P browser-harness/CDP automation.

The canonical nc-tools agent skill lives at:

```text
/Users/lichard/nc-tools/.agents/skills/supplier-coupang/
```

This directory mirrors the same page and workflow knowledge in browser-harness `domain-skills` form so browser-harness agents can load Supplier Hub lessons directly.

## References

- `auth-session.md` — login, profile, manual handoff, and session-close rules.
- `milkrun-list.md` — list URL patterns and table extraction contract.
- `milkrun-transaction-statement.md` — transaction statement PDF download.
- `milkrun-pallet-attachment.md` — pallet attachment `window.open`/print/PDF path.
- `milkrun-bulk-register.md` — bulk registration, modal handling, save verification.
- `milkrun-split.md` — split order, location modal, pallet company save.
- `shipment-attachments.md` — shipment attachment downloads and remaining upload boundary.
- `failure-artifacts.md` — screenshot/DOM/JSON/selector probe evidence contract.
- `side-effect-boundaries.md` — no Selenium fallback and remaining legacy map.

## Prime Directive

Do not let hard-earned Supplier Hub behavior live only in Python retry code. If a selector, popup, jQuery handler, print path, or saved-state marker matters for reliability, record it in this domain skill.
