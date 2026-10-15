"""A deliberately limited Safari adapter; it does not emulate Chrome CDP."""
import json
import math
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

__version__ = "0.1.0"


class SafariError(RuntimeError):
    pass


def _bridge(action, **kwargs):
    payload = json.dumps({"action": action, **kwargs}, ensure_ascii=True)
    # Keep page expressions and form values out of process argument listings.
    source = Path(__file__).with_name("bridge.js").read_text()
    source += "\nfunction run() { return dispatch(" + payload + "); }\n"
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-l", "JavaScript", "-"],
            input=source, capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError as e:
        raise SafariError("Safari automation requires macOS and /usr/bin/osascript.") from e
    except subprocess.TimeoutExpired as e:
        raise SafariError("Safari automation timed out. Check the macOS Automation permission prompt; do not blindly repeat a mutation.") from e
    if result.returncode:
        raise SafariError(result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except ValueError as e:
        raise SafariError("Safari returned an invalid response") from e


def _url(url):
    if not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https", "file", "about"}:
        raise ValueError("Use an http, https, file, or about URL")
    return url


class Safari:
    def __init__(self, transport=_bridge):
        self._call = transport
        self._target = None

    def list_tabs(self):
        return self._call("list")

    def switch_tab(self, target):
        """Select a fresh list_tabs() reference without foregrounding Safari."""
        self._target = None
        if not isinstance(target, dict) or not {"window", "index", "url", "title"} <= target.keys():
            raise ValueError("Pass a tab dictionary returned by list_tabs()")
        if (type(target['window']) is not int or type(target['index']) is not int
                or target['index'] < 0 or not isinstance(target['url'], str)
                or not isinstance(target['title'], str)):
            raise ValueError("Invalid tab reference; use list_tabs()")
        self._target = self._call("info", target=target)
        return self._target.copy()

    def current_tab(self):
        if self._target is None:
            raise SafariError("No tab selected. Use list_tabs()/switch_tab() or new_tab(url).")
        return self._target.copy()

    def page_info(self):
        return self._call("info", target=self.current_tab())

    def new_tab(self, url):
        """Open a normal Safari window and select its tab. May move foreground focus."""
        self._target = None
        self._target = self._call("new", url=_url(url))
        return self.current_tab()

    def goto_url(self, url):
        self._target = self._call("navigate", target=self.current_tab(), url=_url(url))
        return self.current_tab()

    def js(self, expression):
        """Evaluate a synchronous expression. Promises are explicitly unsupported."""
        code = "JSON.stringify((function(){const value=(" + expression + ");if(value && typeof value.then==='function')throw Error('Promises are unsupported');return value===undefined?null:value;})())"
        raw = self._call("js", target=self.current_tab(), code=code)["result"]
        return json.loads(raw) if raw is not None else None

    def get_page_content(self):
        return self.js("document.body ? document.body.innerText : ''")

    def click(self, selector):
        return self.js("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)throw Error('Element not found');e.click();return true;})()")

    def fill(self, selector, value):
        return self.js("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)throw Error('Element not found');if(e.disabled||e.readOnly)throw Error('Element is not editable');if(e.type==='file')throw Error('File uploads require a native interface');if(!(e instanceof HTMLInputElement || e instanceof HTMLTextAreaElement)||['checkbox','radio','button','submit','reset','image','hidden'].includes(e.type))throw Error('fill requires an editable text input or textarea');const p=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const s=Object.getOwnPropertyDescriptor(p,'value').set;s.call(e," + json.dumps(str(value)) + ");e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()")

    def scroll(self, x=0, y=600):
        if not math.isfinite(float(x)) or not math.isfinite(float(y)):
            raise ValueError("Scroll coordinates must be finite")
        return self.js("(()=>{window.scrollBy(" + json.dumps(float(x)) + "," + json.dumps(float(y)) + ");return {x:scrollX,y:scrollY};})()")

    def cdp(self, *args, **kwargs):
        raise NotImplementedError("Safari does not implement Chrome CDP. Use the Safari helpers; CDP scripts are not compatible.")


def main():
    args = sys.argv[1:]
    if args == ["--version"]:
        print(__version__)
        return
    if args == ["skill"]:
        print(Path(__file__).with_name("SKILL.md").read_text(), end="")
        return
    if args in (["--help"], ["-h"]):
        print("safari-harness [skill|doctor|--version]\nOr pipe Python code on stdin. Start with list_tabs()/switch_tab() or new_tab(url).\nNo recordings are collected.")
        return
    safari = Safari()
    try:
        if args in (["doctor"], ["--doctor"]):
            tabs = safari.list_tabs()
            print(json.dumps({"automation": "connected", "tabs": len(tabs), "javascript": "unverified; requires Allow JavaScript from Apple Events", "recordings": "off"}))
            return
        if args:
            raise SafariError("Unknown command; use --help")
        if sys.stdin.isatty():
            raise SafariError("Supply a Python script on stdin")
        namespace = {name: getattr(safari, name) for name in ("list_tabs", "switch_tab", "current_tab", "page_info", "new_tab", "goto_url", "js", "get_page_content", "click", "fill", "scroll", "cdp")}
        namespace["__name__"] = "__main__"
        exec(compile(sys.stdin.read(), "<safari-harness>", "exec"), namespace)
    except (SafariError, NotImplementedError) as e:
        print(f"safari-harness: {e}", file=sys.stderr)
        raise SystemExit(1)
