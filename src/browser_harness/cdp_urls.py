"""Derive URLs from a CDP URL without text joins, so its ?token= access query stays."""
from urllib.parse import urlsplit, urlunsplit


def cdp_path(url, path, scheme=None):
    """`url` with `path` added after its own path, the query kept and the fragment dropped; `scheme` replaces the scheme when given."""
    u = urlsplit(url)
    return urlunsplit((scheme or u.scheme, u.netloc, u.path.rstrip("/") + path, u.query, ""))
