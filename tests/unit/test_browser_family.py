from browser_harness import browser_family


def test_edge_family_recognizes_linux_stable_binary_name():
    assert browser_family.browser_family_for_path("/usr/bin/microsoft-edge-stable") == "edge"
    assert "microsoft-edge-stable" in browser_family.process_names_for_browser_family(
        "Linux",
        {"BH_BROWSER_FAMILY": "edge"},
    )


def test_browser_product_allowed_matches_selected_family():
    env = {"BH_BROWSER_FAMILY": "chrome"}

    assert browser_family.browser_product_allowed("Chrome/149.0.0.0", env)
    assert browser_family.browser_product_allowed("HeadlessChrome/149.0.0.0", env)
    assert not browser_family.browser_product_allowed("Brave/1.92.0", env)
