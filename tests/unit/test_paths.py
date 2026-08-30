from browser_harness import paths


def test_load_env_seeds_missing_variables_only(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_TEST_SET", "kept")
    monkeypatch.delenv("BH_TEST_NEW", raising=False)
    monkeypatch.delenv("BH_TEST_QUOTED", raising=False)
    (tmp_path / ".env").write_text(
        "# comment\n\nBH_TEST_SET=overridden\nBH_TEST_NEW = fresh\nBH_TEST_QUOTED='q'\nnot a pair\n"
    )

    paths.load_env(tmp_path / ".env", tmp_path / "missing.env")

    assert paths.os.environ["BH_TEST_SET"] == "kept"
    assert paths.os.environ["BH_TEST_NEW"] == "fresh"
    assert paths.os.environ["BH_TEST_QUOTED"] == "q"
