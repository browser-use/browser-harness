import os


BROWSER_FAMILIES = {"any", "chrome", "chromium", "brave", "edge", "helium"}


def normalize_browser_family(raw):
    value = (raw or "any").strip().lower().replace("_", "-")
    aliases = {
        "": "any",
        "all": "any",
        "chromium-based": "any",
        "google": "chrome",
        "google-chrome": "chrome",
        "google chrome": "chrome",
        "chrome-canary": "chrome",
        "chrome canary": "chrome",
        "brave-browser": "brave",
        "brave browser": "brave",
        "microsoft-edge": "edge",
        "microsoft edge": "edge",
        "msedge": "edge",
    }
    value = aliases.get(value, value)
    return value if value in BROWSER_FAMILIES else "any"


def browser_family_mode(env=None):
    env = os.environ if env is None else env
    return normalize_browser_family(env.get("BH_BROWSER_FAMILY") or env.get("BH_BROWSER"))


def browser_family_label(family=None):
    family = browser_family_mode() if family is None else normalize_browser_family(family)
    return {
        "any": "Chrome/Chromium",
        "chrome": "Google Chrome",
        "chromium": "Chromium",
        "brave": "Brave",
        "edge": "Microsoft Edge",
        "helium": "Helium",
    }[family]


def browser_family_for_path(path):
    normalized = str(path or "").replace("\\", "/").strip().lower().rstrip("/")
    if not normalized:
        return None
    name = normalized.rsplit("/", 1)[-1]
    if (
        "bravesoftware" in normalized
        or "brave-browser" in normalized
        or "brave browser.app" in normalized
        or name in {"brave", "brave.exe", "brave-browser"}
    ):
        return "brave"
    if (
        "microsoft/edge" in normalized
        or "microsoft edge.app" in normalized
        or name in {"msedge", "msedge.exe", "microsoft-edge"}
    ):
        return "edge"
    if (
        "google/chrome" in normalized
        or "google chrome.app" in normalized
        or name in {"chrome", "chrome.exe", "google-chrome", "google-chrome-stable"}
    ):
        return "chrome"
    if "chromium" in normalized or name in {"chromium", "chromium.exe", "chromium-browser"}:
        return "chromium"
    if "helium" in normalized or name in {"helium", "helium.exe"}:
        return "helium"
    return None


def browser_path_allowed(path, env=None):
    mode = browser_family_mode(env)
    if mode == "any":
        return True
    return browser_family_for_path(path) == mode


def browser_family_filter_active(env=None):
    return browser_family_mode(env) != "any"


def process_names_for_browser_family(system, env=None):
    mode = browser_family_mode(env)
    windows = {
        "chrome": ("chrome.exe",),
        "chromium": ("chromium.exe",),
        "brave": ("brave.exe",),
        "edge": ("msedge.exe",),
        "helium": ("helium.exe",),
    }
    posix = {
        "chrome": ("Google Chrome", "chrome", "google-chrome", "google-chrome-stable"),
        "chromium": ("chromium", "chromium-browser"),
        "brave": ("Brave Browser", "brave", "brave-browser"),
        "edge": ("Microsoft Edge", "msedge", "microsoft-edge"),
        "helium": ("helium",),
    }
    table = windows if system == "Windows" else posix
    if mode != "any":
        return table.get(mode, ())
    return tuple(name for names in table.values() for name in names)
