import tomllib
from pathlib import Path


def test_fetch_use_is_only_in_the_cloud_extra():
    pyproject = tomllib.loads(
        (Path(__file__).parents[2] / "pyproject.toml").read_text()
    )
    project = pyproject["project"]

    assert "fetch-use==0.4.0" not in project["dependencies"]
    assert project["optional-dependencies"]["cloud"] == ["fetch-use==0.4.0"]
