"""Domain-scoped secrets: passwords + TOTP seeds for the embedded agent.

Model: { domain -> { placeholder -> value } }, mirroring browser-use Cloud's
`sensitiveData` — placeholder NAMES are visible to the agent, VALUES never are
(helpers.py gates access on the current page's domain). Everything, metadata
included, lives in one AES-256-GCM blob at <config>/secrets-encrypted.json,
keyed by a random 32-byte <config>/secrets.key (0600, temp file + atomic
rename). TOTP is pure-stdlib RFC 6238 (SHA-1, 30s period, 6 digits).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from . import paths

KINDS = ("password", "totp")


def _key_path() -> Path:
    return paths.config_dir() / "secrets.key"


def _data_path() -> Path:
    return paths.config_dir() / "secrets-encrypted.json"


def _norm_domain(domain) -> str:
    d = str(domain or "").strip().lower()
    if "//" in d:
        d = urlparse(d).hostname or ""
    return d.split("/")[0].lstrip("*").strip(".")


def domain_matches(host, stored) -> bool:
    """True when `host` is the stored domain or a subdomain of it
    (accounts.github.com matches github.com; notgithub.com does not)."""
    host = str(host or "").strip().lower().rstrip(".")
    stored = _norm_domain(stored)
    return bool(host and stored) and (host == stored or host.endswith("." + stored))


def _write_private(path: Path, data: bytes) -> None:
    # Temp file created 0600 (no world-readable window), then atomic rename.
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    os.replace(tmp, path)


def _key() -> bytes:
    path = _key_path()
    try:
        key = path.read_bytes()
    except FileNotFoundError:
        key = os.urandom(32)
        _write_private(path, key)
        return key
    # A wrong-size key decrypts nothing; regenerating would orphan every stored
    # secret, so refuse instead.
    if len(key) != 32:
        raise RuntimeError(f"key file {path} is corrupt ({len(key)} bytes, expected 32); not regenerating")
    return key


def _encrypt(plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext, None)


def _decrypt(blob: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(blob) < 13:
        raise ValueError("blob too short")
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None)


def _load() -> dict:
    """Decrypted { domain: { name: {"kind": k, "value": v} } }."""
    path = _data_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}
    # Corrupt data must error, not become {} — a later save would wipe every secret.
    try:
        blob = base64.b64decode(json.loads(raw)["blob"])
        return json.loads(_decrypt(blob))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"secrets file {path} is unreadable ({e}); refusing to touch it") from e


def _save(data: dict) -> None:
    blob = _encrypt(json.dumps(data).encode())
    _write_private(_data_path(), json.dumps({"v": 1, "blob": base64.b64encode(blob).decode()}).encode())


def set_secret(domain, name, value, kind="password") -> None:
    domain, name = _norm_domain(domain), str(name or "").strip()
    if not domain or not name:
        raise ValueError("domain and name are required")
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r} (expected 'password' or 'totp')")
    if not value:
        raise ValueError("empty value")
    if kind == "totp" and len(_b32(value)) < 10:  # 80-bit key is the practical minimum
        raise ValueError("TOTP seed decodes to fewer than 10 bytes")
    data = _load()
    data.setdefault(domain, {})[name] = {"kind": kind, "value": value}
    _save(data)


def remove_secret(domain, name) -> bool:
    domain, name = _norm_domain(domain), str(name or "").strip()
    data = _load()
    removed = data.get(domain, {}).pop(name, None) is not None
    if removed:
        if not data[domain]:
            del data[domain]
        _save(data)
    return removed


def list_secrets() -> dict:
    """Metadata only — { domain: [{"name": n, "kind": k}] }, never values."""
    return {
        domain: [{"name": n, "kind": e["kind"]} for n, e in sorted(entries.items())]
        for domain, entries in sorted(_load().items())
    }


def get_secret_value(domain, name):
    """Internal: raw stored value (the base32 seed for kind 'totp'), or None."""
    entry = _load().get(_norm_domain(domain), {}).get(str(name or "").strip())
    return entry["value"] if entry else None


# --- TOTP (RFC 6238, pure stdlib) ---
def _b32(seed) -> bytes:
    cleaned = "".join(str(seed).split()).rstrip("=")
    try:
        return base64.b32decode(cleaned + "=" * (-len(cleaned) % 8), casefold=True)
    except Exception:
        raise ValueError("TOTP seed is not valid base32") from None


def totp_now(seed, at=None, digits=6, period=30) -> str:
    """Live TOTP code from a base32 seed (SHA-1, 30s period, 6 digits).
    `at` overrides time.time() for tests."""
    key = _b32(seed)
    counter = int(time.time() if at is None else at) // period
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 10 ** digits).zfill(digits)


def run_secrets_cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="browser-harness secrets")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("set")
    p.add_argument("--domain", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--totp", action="store_true", help="value is a base32 TOTP seed, not a literal")
    p.add_argument("--stdin", action="store_true", help="read the value from stdin instead of prompting")
    sub.add_parser("list")
    p = sub.add_parser("remove")
    p.add_argument("--domain", required=True)
    p.add_argument("--name", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "set":
            if args.stdin:
                value = sys.stdin.read().rstrip("\n")
            else:
                import getpass
                what = "TOTP base32 seed" if args.totp else "value"
                value = getpass.getpass(f"{what} for {args.name} @ {args.domain}: ")
            kind = "totp" if args.totp else "password"
            set_secret(args.domain, args.name, value, kind=kind)
            # Metadata only — the value must never reach stdout (telemetry captures output).
            print(json.dumps({"status": "stored", "domain": _norm_domain(args.domain), "name": args.name.strip(), "kind": kind}))
            return 0
        if args.command == "list":
            print(json.dumps(list_secrets(), indent=2))
            return 0
        if args.command == "remove":
            removed = remove_secret(args.domain, args.name)
            print(json.dumps({"status": "removed" if removed else "missing", "domain": _norm_domain(args.domain), "name": args.name.strip()}))
            return 0
    except (ValueError, RuntimeError) as e:
        print(f"secrets: {e}", file=sys.stderr)
        return 1
    return 2
