from pathlib import Path
import subprocess
import sys


def test_packaged_skill_points_to_root_skill():
    repo = Path(__file__).resolve().parents[2]
    skill = repo / "skills" / "browser-harness" / "SKILL.md"

    assert skill.is_symlink()
    assert skill.readlink() == Path("../../SKILL.md")


def test_skill_materializer_writes_regular_file(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    script = repo / "scripts" / "materialize_browser_harness_skill.py"

    subprocess.run([sys.executable, str(script), str(tmp_path)], check=True)

    materialized = tmp_path / "skills" / "browser-harness" / "SKILL.md"
    assert materialized.is_file()
    assert not materialized.is_symlink()
    assert materialized.read_text() == (repo / "SKILL.md").read_text()
