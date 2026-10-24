"""Shared JavaScript for the cosmetic title marker on the daemon's tab.

The default daemon keeps the bare horse prefix. A named daemon puts its
BU_NAME in the prefix (``🐴 [name] Title``) so parallel daemons stay
distinguishable even when Chrome truncates long titles in the tab strip.
Callers decide whether to apply it (BH_TAB_MARKER=0 disables it).
"""
import json

HORSE = "\U0001F434"
# Matches any harness prefix: the bare horse or a horse plus a BU_NAME tag.
# BU_NAME is validated to [A-Za-z0-9_-]{1,64} in _ipc.
_STRIP_RE = r"/^\u{1F434}(?: \[[A-Za-z0-9_-]{1,64}\])? ?/u"


def marker(name):
    return HORSE if name == "default" else f"{HORSE} [{name}]"


def expression(name):
    """JS that sets this daemon's prefix, replacing any other harness prefix."""
    prefix = json.dumps(marker(name) + " ")
    return (
        "(()=>{const t=document.title;"
        f"const n={prefix}+t.replace({_STRIP_RE},'');"
        "if(n!==t)document.title=n})()"
    )


def unmark_expression():
    """JS that removes any harness prefix from the title."""
    return (
        "(()=>{const t=document.title;"
        f"const n=t.replace({_STRIP_RE},'');"
        "if(n!==t)document.title=n})()"
    )
