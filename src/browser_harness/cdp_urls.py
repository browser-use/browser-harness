"""Derive URLs from a CDP URL without text joins, so its ?token= access query stays."""
from urllib.parse import urlsplit, urlunsplit


def cdp_path(url, path, scheme=None):
    """Return `url` with `path` after its path, the same query, no fragment, and `scheme` when given."""
    u = urlsplit(url)
    return urlunsplit((scheme or u.scheme, u.netloc, u.path.rstrip("/") + path, u.query, ""))
