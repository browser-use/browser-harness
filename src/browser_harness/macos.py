"""macOS-only helpers for local Chrome automation."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .admin import daemon_browser_ready
from .daemon import remote_debugging_toggle_profiles

# Chrome localizes the per-connection sheet, so the AppleScript cannot match
# English literals. These are Chromium's own strings for
# IDS_DEV_TOOLS_CONNECTION_DIALOG_TITLE and IDS_DEV_TOOLS_CONNECTION_DIALOG_ALLOW_TEXT
# (chrome/app/generated_resources.grd and resources/generated_resources_<locale>.xtb).
# BH_ALLOW_SHEET_TITLES and BH_ALLOW_LABELS (comma-separated) extend the tables for
# a Chrome UI language that is not listed.
ALLOW_SHEET_TITLES = (
    "Allow remote debugging?",  # en
    "リモート デバッグを許可しますか？",  # ja
    "要允许远程调试吗？",  # zh-CN
    "允許遠端偵錯嗎？",  # zh-TW
    "원격 디버깅을 허용하시겠습니까?",  # ko
    "Remote-Fehlerbehebung zulassen?",  # de
    "Autoriser le débogage à distance ?",  # fr
    "¿Permitir depuración remota?",  # es
    "¿Deseas permitir la depuración remota?",  # es-419
    "Permitir a depuração remota?",  # pt-BR
    "Permitir depuração remota?",  # pt-PT
    "Vuoi consentire il debug remoto?",  # it
    "Foutopsporing op afstand toestaan?",  # nl
    "Czy zezwalać na debugowanie zdalne?",  # pl
    "Разрешить удаленную отладку?",  # ru
    "Дозволити дистанційне налагодження?",  # uk
    "Povolit vzdálené ladění?",  # cs
    "Uzaktan hata ayıklamaya izin verilsin mi?",  # tr
    "Cho phép gỡ lỗi từ xa?",  # vi
    "อนุญาตให้ใช้การแก้ไขข้อบกพร่องจากระยะไกลใช่ไหม",  # th
    "Izinkan proses debug jarak jauh?",  # id
    "السماح بتصحيح الأخطاء عن بُعد؟",  # ar
    "לאפשר ניפוי באגים מרחוק?",  # he
    "क्या आपको बाहरी ऐप्लिकेशन के ज़रिए डिबग करने की अनुमति देनी है?",  # hi
    "Vill du tillåta fjärrfelsökning?",  # sv
    "Vil du tillade ekstern fejlretning?",  # da
    "Vil du tillate ekstern feilsøking?",  # nb
    "Sallitaanko vianetsintä etänä?",  # fi
    "Να επιτρέπεται η απομακρυσμένη αποσφαλμάτωση;",  # el
)

ALLOW_BUTTON_LABELS = (
    "Allow",  # en
    "許可する",  # ja
    "允许",  # zh-CN
    "允許",  # zh-TW
    "허용",  # ko
    "Zulassen",  # de
    "Autoriser",  # fr
    "Permitir",  # es, es-419, pt-BR, pt-PT
    "Consenti",  # it
    "Toestaan",  # nl
    "Zezwalaj",  # pl
    "Разрешить",  # ru
    "Дозволити",  # uk
    "Povolit",  # cs
    "İzin ver",  # tr
    "Cho phép",  # vi
    "อนุญาต",  # th
    "Izinkan",  # id
    "سماح",  # ar
    "זה בסדר",  # he
    "अनुमति दें",  # hi
    "Tillåt",  # sv
    "Tillad",  # da
    "Tillat",  # nb
    "Salli",  # fi
    "Επιτρέπεται",  # el
)

# argv: <title count> <titles...> <labels...>. The sheet is chosen by its exact
# title and the button by its exact label; Cancel and "Turn off in settings" are
# never candidates. Chrome gives this dialog no default button and focuses
# Cancel, so pressing "the default button" would be unsafe.
_APPLESCRIPT = r'''using terms from application "System Events"
    on buttonLabel(nodeRef)
        try
            set d to (description of nodeRef as text)
            if d is not "" then return d
        end try
        try
            return (title of nodeRef as text)
        end try
        return ""
    end buttonLabel

    on pressAllow(nodeRef, labels)
        try
            if (role of nodeRef as text) is "AXButton" then
                if labels contains my buttonLabel(nodeRef) then
                    perform action "AXPress" of nodeRef
                    return true
                end if
                return false
            end if
        end try
        try
            repeat with childRef in UI elements of nodeRef
                if my pressAllow(childRef, labels) then return true
            end repeat
        end try
        return false
    end pressAllow

    on isAllowSheet(sheetRef, titles)
        try
            return titles contains (name of sheetRef as text)
        end try
        return false
    end isAllowSheet
end using terms from

on run argv
    set titleCount to (item 1 of argv) as integer
    set titles to items 2 thru (titleCount + 1) of argv
    set labels to items (titleCount + 2) thru -1 of argv
    set resultText to "not-found"
    tell application "System Events"
        if exists process "Google Chrome" then
            tell process "Google Chrome"
                repeat with w in windows
                    try
                        repeat with s in sheets of w
                            if my isAllowSheet(s, titles) and my pressAllow(s, labels) then
                                set resultText to "ready"
                                exit repeat
                            end if
                        end repeat
                    end try
                    if resultText is "ready" then exit repeat
                end repeat
            end tell
        end if
    end tell
    return resultText
end run
'''


_ACCESSIBILITY_DETAIL = (
    "allow the app launching browser-harness (for example Terminal, iTerm, or Codex) "
    "in System Settings > Privacy & Security > Accessibility"
)

# osascript localizes its error text; the OSStatus codes do not.
# -25211 kAXErrorAPIDisabled (assistive access), -1743 errAEEventNotPermitted.
_ACCESSIBILITY_ERROR_MARKERS = ("not authorized", "assistive", "-25211", "-1743")


def _extra_strings(env_name: str) -> tuple[str, ...]:
    raw = os.environ.get(env_name, "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def allow_sheet_titles() -> tuple[str, ...]:
    return ALLOW_SHEET_TITLES + _extra_strings("BH_ALLOW_SHEET_TITLES")


def allow_button_labels() -> tuple[str, ...]:
    return ALLOW_BUTTON_LABELS + _extra_strings("BH_ALLOW_LABELS")


def _osascript_command() -> list[str]:
    titles = allow_sheet_titles()
    return ["osascript", "-", str(len(titles)), *titles, *allow_button_labels()]


def _accessibility_denied(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in _ACCESSIBILITY_ERROR_MARKERS)


def _google_chrome_root() -> Path:
    return Path.home() / "Library/Application Support/Google/Chrome"


def _google_chrome_toggle_enabled() -> bool:
    """Only accept the toggle from the Google Chrome root used by the script."""
    return _google_chrome_root() in remote_debugging_toggle_profiles()


def approve_remote_debugging() -> tuple[str, str | None]:
    """Click Chrome's exact per-connection Allow sheet without activating Chrome."""
    if platform.system() != "Darwin":
        return "unsupported", "mac-approve is only available on macOS"

    if daemon_browser_ready():
        return "ready", None

    if not _google_chrome_toggle_enabled():
        return (
            "setup-required",
            'first enable "Allow remote debugging for this browser instance" at '
            "chrome://inspect/#remote-debugging, then run `browser-harness mac-approve` again",
        )

    try:
        completed = subprocess.run(
            _osascript_command(),
            input=_APPLESCRIPT,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "accessibility-required", _ACCESSIBILITY_DETAIL
    except (OSError, subprocess.SubprocessError) as exc:
        return "error", str(exc)

    if completed.returncode != 0:
        detail = completed.stderr.strip() or "osascript failed"
        if _accessibility_denied(detail):
            return (
                "accessibility-required",
                _ACCESSIBILITY_DETAIL,
            )
        return "error", detail

    status = completed.stdout.strip()
    if status == "ready":
        return "ready", None
    if status == "not-found":
        # The user may have accepted the sheet while AppleScript was looking.
        if daemon_browser_ready():
            return "ready", None
        return (
            "not-found",
            "retry the browser command and run `browser-harness mac-approve` when the prompt appears",
        )
    return "error", f"unexpected osascript result: {status or '<empty>'}"


def run_cli(args: list[str]) -> int:
    if args:
        print("usage: browser-harness mac-approve", flush=True)
        return 2

    status, detail = approve_remote_debugging()
    if detail:
        print(f"{status}: {detail}", flush=True)
    else:
        print(status, flush=True)
    return 0 if status == "ready" else 1
