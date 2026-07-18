from fastkit_core.sanitize import sanitize_html


def test_keeps_allowed_tags():
    result = sanitize_html("<p>Hello <strong>world</strong></p>")

    assert result == "<p>Hello <strong>world</strong></p>"


def test_strips_script_and_content():
    result = sanitize_html("<p>ok</p><script>alert('xss')</script>")

    assert "script" not in result
    assert "alert" not in result
    assert "<p>ok</p>" in result


def test_strips_style_content():
    result = sanitize_html("<style>body{color:red}</style><p>x</p>")

    assert "color" not in result
    assert "<p>x</p>" in result


def test_removes_event_handlers():
    result = sanitize_html('<img src="/a.png" onerror="alert(1)" alt="a">')

    assert "onerror" not in result
    assert "alert" not in result
    assert 'src="/a.png"' in result


def test_blocks_javascript_href():
    result = sanitize_html('<a href="javascript:alert(1)">click</a>')

    assert "javascript" not in result
    assert "<a>click</a>" in result


def test_allows_safe_href_and_rel():
    result = sanitize_html('<a href="https://example.com" rel="noopener">link</a>')

    assert 'href="https://example.com"' in result
    assert 'rel="noopener"' in result


def test_drops_unknown_tags_keeping_text():
    result = sanitize_html("<iframe src='evil'></iframe><marquee>text</marquee>")

    assert "iframe" not in result
    assert "marquee" not in result
    assert "text" in result


def test_blocks_data_uri_except_images():
    dangerous = sanitize_html('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>')
    assert "data:text/html" not in dangerous

    safe = sanitize_html('<img src="data:image/png;base64,iVBOR" alt="a">')
    assert "data:image/png" in safe


def test_keeps_asset_reference():
    result = sanitize_html('<img data-file-id="01J" src="/media/x.png" alt="a">')

    assert 'data-file-id="01J"' in result


def test_escapes_text_content():
    result = sanitize_html("<p>1 < 2 & 3 > 0</p>")

    assert "&lt;" in result
    assert "&amp;" in result


def test_drops_disallowed_attributes():
    result = sanitize_html('<p class="ok" style="x" data-evil="1">t</p>')

    assert 'class="ok"' in result
    assert "style" not in result
    assert "data-evil" not in result


def test_self_closing_image():
    result = sanitize_html('<img src="/a.png" alt="a" />')

    assert result.count("<img") == 1
    assert "</img>" not in result


def test_anchor_without_href_is_kept_clean():
    result = sanitize_html("<a>bare</a>")

    assert result == "<a>bare</a>"


def test_relative_url_without_scheme_is_allowed():
    result = sanitize_html('<a href="page.html">x</a>')

    assert 'href="page.html"' in result


def test_valueless_url_attribute_is_dropped():
    result = sanitize_html('<img src alt="a">')

    assert "src" not in result
    assert 'alt="a"' in result


def test_stray_closing_script_is_ignored():
    result = sanitize_html("<p>x</p></script>")

    assert result == "<p>x</p>"


def test_self_closing_drop_tag_does_not_truncate_following_content():
    result = sanitize_html("<p>a</p><script/><p>b</p>")

    assert result == "<p>a</p><p>b</p>"
