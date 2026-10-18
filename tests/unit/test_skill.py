from importlib import resources
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Every copy of the skill text that has to be a real file on disk: the wheel
# ships src/, the Claude Code plugin loads skills/, and the root file is what
# the docs link to. They were symlinks, which Windows checkouts turn into a
# one-line text file containing the link target.
SKILL_COPIES = (
    "SKILL.md",
    "src/browser_harness/SKILL.md",
    "skills/browser-harness/SKILL.md",
)


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end != -1
    return text[4:end]


def test_packaged_skill_frontmatter_is_valid_simple_yaml():
    text = resources.files("browser_harness").joinpath("SKILL.md").read_text(encoding="utf-8")
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
        "description": "Control a real browser via CDP: clicking, typing, navigation, logged-in sessions, JS-rendered or bot-protected pages. Not for plain HTTP fetches of public content - use curl for those.",
    }


def test_skill_copies_are_real_files_with_identical_content():
    """Guards the three on-disk copies against drift and against symlink regressions.

    A symlink here is checked out as a plain file holding "../../SKILL.md" on any
    Windows clone without Developer Mode, which silently breaks
    `browser-harness skill` and the plugin's skill body.
    """
    # Text, not bytes: git normalizes to LF in the object store but hands
    # Windows checkouts CRLF, so a byte comparison would only be testing
    # core.autocrlf. Universal newlines compare what actually matters.
    contents = {}
    for relative in SKILL_COPIES:
        path = REPO_ROOT / relative
        assert path.is_file(), f"{relative} is missing"
        assert not path.is_symlink(), (
            f"{relative} is a symlink; commit it as a regular file so Windows "
            f"checkouts get the real text"
        )
        contents[relative] = path.read_text(encoding="utf-8")

    canonical = contents["SKILL.md"]
    assert canonical.startswith("---\n"), "SKILL.md lost its frontmatter"
    for relative, text in contents.items():
        assert text == canonical, (
            f"{relative} has drifted from SKILL.md; resync with:\n"
            f"  cp SKILL.md src/browser_harness/SKILL.md\n"
            f"  cp SKILL.md skills/browser-harness/SKILL.md"
        )
