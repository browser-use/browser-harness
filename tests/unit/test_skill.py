import inspect
from importlib import resources

from browser_harness import helpers


CORE_HELPERS = (
    "new_tab",
    "page_info",
    "page_state",
    "wait_for_load",
    "wait",
    "ensure_real_tab",
    "js",
    "cdp",
    "click_at_xy",
    "click_backend_node",
    "type_text",
    "press_key",
    "capture_screenshot",
    "http_get",
    "network_events",
    "browser_fetch_to_file",
)


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end != -1
    return text[4:end]


def test_packaged_skill_frontmatter_is_valid_simple_yaml():
    text = resources.files("browser_harness").joinpath("SKILL.md").read_text()
    metadata = {}

    for line in _frontmatter(text).splitlines():
        key, separator, value = line.partition(":")
        assert separator == ":", line
        assert key in {"name", "description"}
        assert key.strip() == key
        value = value.strip()
        assert value, key

        if value[0] in {"'", '"'}:
            assert value[-1] == value[0], line
            parsed = value[1:-1]
        else:
            parsed = value
            assert ": " not in parsed, line

        metadata[key] = parsed

    assert metadata == {
        "name": "browser-harness",
        "description": "Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.",
    }


def test_packaged_skill_documents_exact_core_helper_signatures():
    text = resources.files("browser_harness").joinpath("SKILL.md").read_text()

    for name in CORE_HELPERS:
        helper = getattr(helpers, name)
        assert f"{name}{inspect.signature(helper)}" in text

    assert "`screenshot(...)`" in text
