from browser_harness import _tab_marker


def test_marker_uses_exact_daemon_name():
    assert _tab_marker.marker("research-7f3a") == "🐴 [research-7f3a]"
    assert _tab_marker.marker_suffix("research-7f3a") == " | 🐴 [research-7f3a]"


def test_marker_expression_is_suffix_idempotent_for_empty_titles():
    assert _tab_marker.expression("research-7f3a") == '''(()=>{
        const suffix = " | 🐴 [research-7f3a]";
        if (document.title.endsWith(suffix)) return;
        const clean = document.title
            .replace(/\\s*\\|\\s*🐴\\s*\\[[^\\]]+\\]\\s*$/, "")
            .replace(/^🐴(?:\\s*\\[[^\\]]+\\])?\\s*/, "");
        document.title = clean + suffix;
    })()'''


def test_unmarker_expression_removes_suffix_and_legacy_prefix():
    assert _tab_marker.unmarker_expression() == '''document.title = document.title
        .replace(/\\s*\\|\\s*🐴\\s*\\[[^\\]]+\\]\\s*$/, "")
        .replace(/^🐴(?:\\s*\\[[^\\]]+\\])?\\s*/, "")'''
