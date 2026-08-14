"""The 🐴 prefix the harness puts on the tab it drives.

It exists for the user watching the browser, so it lives in document.title —
the one channel the page also writes to. The programs below are derived from
MARKER rather than spelling it again: a marker the JS writes but Python does
not recognise is exactly the leak this module exists to prevent.
"""

MARKER = "\U0001F434 "


def strip_title(title):
    """The page's own title: our prefix removed, anything else left alone."""
    title = title or ""
    return title[len(MARKER):] if title.startswith(MARKER) else title


MARK_JS = (
    "(function(){var M='" + MARKER + "';"
    "if(!document.title.startsWith(M))document.title=M+document.title})()"
)

UNMARK_JS = (
    "(function(){var M='" + MARKER + "';"
    "if(document.title.startsWith(M))document.title=document.title.slice(M.length)})()"
)
