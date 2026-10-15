# Epson — Linux Driver Downloads

Epson's driver hosts are **geo-fenced, not bot-fenced**. This is the single most
expensive thing to rediscover: driving a real browser at them does **not** help,
so don't reach for the harness first. Get the metadata from a third-party mirror
(below), and have a human on a US route fetch the binary.

## The block

Verified August 2026 from a Canadian IP, with both `curl` and a real (headless)
Chromium — identical result, which is what proves it is geography and not
fingerprinting:

| Host | Result |
|---|---|
| `download-center.epson.com` | HTTP 403, Akamai "Access Denied" |
| `download.ebz.epson.net` | HTTP 403, Akamai "Access Denied" |
| `support.epson.net` | HTTP 403, Akamai "Access Denied" |
| `epson.ca` (and other regional sites) | loads normally |

Those first three are Epson **America**. Regional sites are served fine — so a
403 here means "wrong country", not "you look like a robot".

Two traps in the error itself:

- The denial body echoes the URL back as `http://…` even for an HTTPS request.
  That is Akamai's template, not a protocol downgrade. Don't chase it.
- It returns 403 (not 451 or a redirect), which reads like a WAF/bot rule and
  baits you into UA spoofing, referer headers, and browser automation. None of
  it works.

To confirm a block is geographic rather than bot-driven, fetch the same path
twice — once with `http_get`, once through a real browser context. Same status
from both ⇒ geography. Stop escalating.

## Regional sites don't expose driver files

`epson.ca` (pattern: `/Support/Printers/All-In-Ones/ET-Series/Epson-<MODEL>/s/<SKU>`)
does carry a Linux section, and it is a dead end for automation:

- OS chooser is `select#review-filter`; setting `.value` + firing `change` is not
  enough, a sibling **GO** button must be clicked.
- It then navigates to `?review-filter=Linux` and renders a "Linux Drivers"
  heading.
- Every link in that section is an `href="…#"` accordion toggle. Expanding them
  yields **no** file URLs — the downloads themselves still live on the blocked
  America hosts.

Budget zero time here.

## Where the real metadata lives

A Gentoo overlay mirrors everything you need *except* the binary:
`gitlab.com/at.gentoo.repo/epson-inkjet-printer-escpr2` (GitLab is not blocked).

```python
from helpers import http_get
BASE = "https://gitlab.com/at.gentoo.repo/epson-inkjet-printer-escpr2/-/raw/master"

# 1. Is this model supported at all?  (282 entries as of 1.2.39)
models = http_get(f"{BASE}/SUPPORTED-PRINTERS")
assert "Epson ET-4950 Series" in models

# 2. Available versions + checksums to verify a download you didn't make yourself
manifest = http_get(f"{BASE}/net-print/epson-inkjet-printer-escpr2-bin/Manifest")
# DIST epson-inkjet-printer-escpr2-1.2.39-1.x86_64.rpm 5014785 BLAKE2B … SHA512 …
```

List the tree via the API (note the URL-encoded project path):

```
https://gitlab.com/api/v4/projects/at.gentoo.repo%2Fepson-inkjet-printer-escpr2/repository/tree?recursive=true&per_page=100
```

### The canonical download URL

Each ebuild carries a per-version `DL_UUID`:

```
https://download-center.epson.com/f/module/${DL_UUID}/epson-inkjet-printer-escpr2-${VER}-1.x86_64.rpm
```

`DL_UUID` changes with every release, so read it from that version's ebuild —
never reuse one. For 1.2.39 it is `89853441-b79f-4d67-a3b5-83eca1254b9f`.

Epson publishes a Debian build of the same version too, which the overlay does
not track: `epson-inkjet-printer-escpr2_${VER}-1_amd64.deb`. The Manifest's
SHA512 covers the **rpm only** — it will not match the deb. Verify a deb by its
control metadata instead (`Maintainer: Seiko Epson Corporation`) plus the
expected payload under `/opt/epson-inkjet-printer-escpr2/`.

## escpr vs escpr2 — check before you download

Two different drivers, and the distro one is old:

- `printer-driver-escpr` — in Debian/Ubuntu repos (1.8.7). Covers older models
  only. **No ET-4950.**
- `epson-inkjet-printer-escpr2` — Epson's own, not in any distro repo. Covers
  current models.

Enumerate what v1 actually supports without installing it:

```bash
apt-get download printer-driver-escpr        # no root needed
dpkg-deb -x printer-driver-escpr_*.deb escpr/
escpr/usr/lib/cups/driver/escpr list | grep -oiE "ET-[0-9]+" | sort -u
```

## After you have it: PPD vocabulary

escpr2 PPDs do not use IPP/driverless names, which breaks any code matching on
`PhotographicSemiGloss` / `cupsPrintQuality` / `ColorModel`:

| Intent | driverless PPD | escpr2 PPD |
|---|---|---|
| borderless size | `5x7.Borderless` | `T2L` (`T` prefix = borderless) |
| semi-gloss photo | `MediaType=PhotographicSemiGloss` | `MediaType=PSGLOS_HIGH` |
| high quality | `cupsPrintQuality=High` | folded into the `MediaType` choice |
| colour | `ColorModel=RGB` | `Ink=COLOR` |

Borderless page sizes are `T`-prefixed throughout (`T2L`, `TLetter`,
`T4X6FULL`, `TPostcard`). Match on intent, not keywords.

Also worth knowing: in **both** PPD families the borderless `ImageableArea`
equals `PaperDimension` exactly — no over-spray is declared anywhere. escpr2
performs the borderless expansion inside the `epson-escpr2` filter when it emits
ESC/P-R, so the CUPS raster still measures exactly the sheet. You cannot verify
expansion by reading the PPD or the raster; only a print shows it.
