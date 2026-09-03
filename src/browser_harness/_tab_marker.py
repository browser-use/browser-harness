"""Shared JavaScript for marking the tab attached to a daemon."""
import json


def marker(name):
    return f"🐴 [{name}]"


def marker_suffix(name):
    return f" | {marker(name)}"


def expression(name):
    suffix = json.dumps(marker_suffix(name), ensure_ascii=False)
    return f'''(()=>{{
        const suffix = {suffix};
        if (document.title.endsWith(suffix)) return;
        const clean = document.title
            .replace(/\\s*\\|\\s*🐴\\s*\\[[^\\]]+\\]\\s*$/, "")
            .replace(/^🐴(?:\\s*\\[[^\\]]+\\])?\\s*/, "");
        document.title = clean + suffix;
    }})()'''


def unmarker_expression():
    return r'''document.title = document.title
        .replace(/\s*\|\s*🐴\s*\[[^\]]+\]\s*$/, "")
        .replace(/^🐴(?:\s*\[[^\]]+\])?\s*/, "")'''
