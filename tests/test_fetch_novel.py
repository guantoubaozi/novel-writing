import io
import json
import zipfile
import os
from pathlib import Path

import pytest

from scripts import fetch_novel


def test_slug_is_stable_and_safe():
    assert fetch_novel.slugify("Pride & Prejudice", "Jane Austen") == "pride-prejudice--jane-austen"
    assert "/" not in fetch_novel.slugify("../秘密", "作者")
    assert fetch_novel.slugify("", "") == "untitled"


def test_clean_html_removes_scripts_and_source_regexes():
    html = "<html><body><div class='ad'>广告</div><p>第一段</p><script>x()</script><p>第二段</p></body></html>"
    assert fetch_novel.clean_text(html, [r"广告"]) == "第一段\n第二段"


def test_parse_search_results_returns_stable_candidates():
    config = {
        "name": "Fixture",
        "kind": "html",
        "search": {
            "item_selector": ".book",
            "title_selector": ".title",
            "author_selector": ".author",
            "url_selector": "a",
        },
    }
    html = """<div class='book'><a href='/book/1'>Book One</a><span class='title'>Book One</span><span class='author'>A</span></div>"""
    candidates = fetch_novel.parse_search_results(config, html, "book")
    assert candidates[0]["id"].startswith("fixture:1~")
    assert candidates[0]["url"] == "https://fixture.invalid/book/1"


def test_parse_toc_and_chapter_content():
    config = {
        "name": "Fixture",
        "host": "https://fixture.invalid",
        "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"},
        "content": {"selector": ".content", "remove_selectors": [".ad"]},
    }
    toc = "<div class='chapter'><a href='/c1'><span class='ct'>第一章</span></a></div>"
    assert fetch_novel.parse_toc(config, toc) == [{"index": 1, "title": "第一章", "url": "https://fixture.invalid/c1"}]
    assert fetch_novel.parse_chapter(config, "<div class='content'><p>正文</p><p class='ad'>广告</p></div>") == "正文"


def test_chapter_range_is_inclusive_and_validates():
    assert fetch_novel.parse_chapter_range("1-3", 8) == [1, 2, 3]
    assert fetch_novel.parse_chapter_range("2", 8) == [2]
    with pytest.raises(ValueError):
        fetch_novel.parse_chapter_range("3-1", 8)
    with pytest.raises(ValueError):
        fetch_novel.parse_chapter_range("0-2", 8)


def test_write_chapters_refuses_overwrite_unless_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = Path("raw")
    fetch_novel.write_chapters(out, [(1, "第一章", "正文")])
    with pytest.raises(FileExistsError):
        fetch_novel.write_chapters(out, [(1, "第一章", "新正文")])
    fetch_novel.write_chapters(out, [(1, "第一章", "新正文")], force=True)
    assert (out / "001-第一章.txt").read_text() == "新正文\n"


def test_file_inputs_txt_md_and_epub(tmp_path):
    txt = tmp_path / "book.txt"
    txt.write_text("第一章\n甲\n\n第二章\n乙", encoding="utf-8")
    assert fetch_novel.load_input_file(txt) == [(1, "第一章", "甲"), (2, "第二章", "乙")]
    md = tmp_path / "book.md"
    md.write_text("# 第一章\n甲\n## 第二章\n乙", encoding="utf-8")
    assert fetch_novel.load_input_file(md) == [(1, "第一章", "甲"), (2, "第二章", "乙")]
    epub = tmp_path / "book.epub"
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr("OEBPS/ch1.xhtml", "<h1>第一章</h1><p>甲</p>")
        zf.writestr("OEBPS/ch2.xhtml", "<h1>第二章</h1><p>乙</p>")
    assert fetch_novel.load_input_file(epub) == [(1, "第一章", "甲"), (2, "第二章", "乙")]


def test_paste_stdin_is_chapterized(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("第一章\n甲\n\n第二章\n乙"))
    assert fetch_novel.load_paste() == [(1, "第一章", "甲"), (2, "第二章", "乙")]


def test_url_candidate_requires_explicit_identity_and_fetches(monkeypatch):
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        return "<h1>第一章</h1><div class='content'>正文</div>"

    monkeypatch.setattr(fetch_novel, "fetch_url", fake_get)
    chapters = fetch_novel.load_url("https://example.test/chapter", selector=".content", title="第一章")
    assert chapters == [(1, "第一章", "正文")]
    assert seen["url"].startswith("https://")


def test_validate_source_schema_and_builtin_sources():
    sources = fetch_novel.load_sources(Path("scripts/booksources"))
    assert [source["name"] for source in sources] == []
    for source in sources:
        fetch_novel.validate_source(source)


def test_validate_api_source_schema_requires_endpoint_fields():
    gutendex = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.test"}
    fetch_novel.validate_source(gutendex)
    assert gutendex["search_url"]
    with pytest.raises(ValueError, match="gutendex source requires non-empty host"):
        fetch_novel.validate_source({"name": "g", "kind": "gutendex", "search_url": "https://example.test/?search={keyword}"})
    with pytest.raises(ValueError, match="gutendex source requires non-empty search_url"):
        fetch_novel.validate_source({"name": "g", "kind": "gutendex", "host": "https://example.test", "search_url": " "})
    with pytest.raises(ValueError, match="mediawiki source requires non-empty api_url"):
        fetch_novel.validate_source({"name": "m", "kind": "mediawiki", "host": "https://example.test"})


def test_mediawiki_search_marks_author_for_manual_confirmation(monkeypatch):
    source = {"name": "zh-wikisource", "kind": "mediawiki", "host": "https://zh.example", "api_url": "https://zh.example/w/api.php"}
    payload = {"query": {"search": [{"title": "红楼梦"}]}}
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda *args, **kwargs: json.dumps(payload))
    result = fetch_novel._search_mediawiki(source, "红楼梦")
    assert result[0]["author"] == ""
    assert result[0]["author_status"] == "needs_manual_confirmation"


def test_candidate_identity_and_fallback_only_same_book():
    candidates = [
        {"id": "a:1", "title": "Same", "author": "Author", "url": "https://a/1", "source": "a"},
        {"id": "b:2", "title": "Same", "author": "Author", "url": "https://b/2", "source": "b"},
        {"id": "c:3", "title": "Other", "author": "Author", "url": "https://c/3", "source": "c"},
    ]
    assert fetch_novel.same_identity(candidates[0], candidates[1])
    assert not fetch_novel.same_identity(candidates[0], candidates[2])
    assert not fetch_novel.same_identity({"title": "Same", "author": ""}, {"title": "Same", "author": ""})


def test_download_falls_back_only_to_confirmed_identity(monkeypatch):
    source_a = {"name": "a", "kind": "html"}
    source_b = {"name": "b", "kind": "html"}
    candidate = {"id": "a:1", "title": "Same", "author": "Author", "url": "https://a/1", "source": "a"}
    alternative = {"id": "b:2", "title": "Same", "author": "Author", "url": "https://b/2", "source": "b"}
    calls = []

    def fake_download(url, source):
        calls.append(url)
        if source is source_a:
            raise RuntimeError("source unavailable")
        return "Same", "Author", [(1, "Chapter 1", "fallback")]

    monkeypatch.setattr(fetch_novel, "_download_html", fake_download)
    monkeypatch.setattr(fetch_novel, "search_sources", lambda title, sources: [alternative])
    assert fetch_novel.download_candidate(candidate, source_a, [source_a, source_b])[2][0][2] == "fallback"
    assert calls == ["https://a/1", "https://b/2"]


def test_download_fallback_from_gutendex_to_html_keeps_range_metadata(monkeypatch):
    gutendex = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.test", "search_url": "https://gutendex.test/?search={keyword}"}
    html = {"name": "fixture", "kind": "html", "host": "https://fixture.test"}
    candidate = {"id": "gutendex:1", "title": "Same", "author": "Author", "url": "https://gutendex.test/books/1", "source": "gutendex"}
    alternative = {"id": "fixture:1", "title": "Same", "author": "Author", "url": "https://fixture.test/book/1", "source": "fixture"}

    monkeypatch.setattr(fetch_novel, "_download_gutendex", lambda *args: (_ for _ in ()).throw(RuntimeError("unavailable")))
    monkeypatch.setattr(fetch_novel, "_download_html", lambda url, source, chapter_range=None: ("Same", "Author", [(2, "第二章", "正文")]))
    monkeypatch.setattr(fetch_novel, "search_sources", lambda title, sources: [alternative])

    result = fetch_novel.download_candidate(candidate, gutendex, [gutendex, html], "2-2")
    assert result[2] == [(2, "第二章", "正文")]
    assert result.range_applied is True
    assert result.source_kind == "html"


def test_download_fallback_from_html_to_gutendex_keeps_full_range_metadata(monkeypatch):
    html = {"name": "fixture", "kind": "html", "host": "https://fixture.test"}
    gutendex = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.test", "search_url": "https://gutendex.test/?search={keyword}"}
    candidate = {"id": "fixture:1", "title": "Same", "author": "Author", "url": "https://fixture.test/book/1", "source": "fixture"}
    alternative = {"id": "gutendex:1", "title": "Same", "author": "Author", "url": "https://gutendex.test/books/1", "source": "gutendex"}

    monkeypatch.setattr(fetch_novel, "_download_html", lambda *args: (_ for _ in ()).throw(RuntimeError("unavailable")))
    monkeypatch.setattr(fetch_novel, "_download_gutendex", lambda *args: ("Same", "Author", [(1, "第一章", "正文"), (2, "第二章", "正文")]))
    monkeypatch.setattr(fetch_novel, "search_sources", lambda title, sources: [alternative])

    result = fetch_novel.download_candidate(candidate, html, [html, gutendex], "2-2")
    assert result[2] == [(1, "第一章", "正文"), (2, "第二章", "正文")]
    assert result.range_applied is False
    assert result.source_kind == "gutendex"


def test_gutenberg_url_is_resolved_as_gutendex_candidate(monkeypatch):
    called = {}
    source = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.com"}
    monkeypatch.setattr(fetch_novel, "_download_gutendex", lambda candidate_id, config: called.update(id=candidate_id) or ("Book", "Author", [(1, "Chapter 1", "Text")]))
    assert fetch_novel.resolve_book_url("https://www.gutenberg.org/ebooks/1342", [source]) == (source, "gutendex:1342")
    assert fetch_novel.resolve_book_url("https://gutendex.com/books/1342/", [source]) == (source, "gutendex:1342")
    fetch_novel.download_candidate({"id": "gutendex:1342", "title": "Book", "author": "Author", "url": "https://www.gutenberg.org/ebooks/1342"}, source, [source])
    assert called["id"] == "gutendex:1342"


def test_html_download_fetches_only_requested_toc_range(monkeypatch):
    source = {"name": "Fixture", "kind": "html", "host": "https://fixture.invalid", "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"}, "content": {"selector": ".content"}}
    landing = "".join(f"<div class='chapter'><a href='/c{i}'><span class='ct'>第{i}章</span></a></div>" for i in range(1, 4))
    calls = []
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda url, **kwargs: (calls.append(url) or (landing if url == "https://fixture.invalid/book" else "<div class='content'>正文</div>")))
    assert len(fetch_novel._download_html("https://fixture.invalid/book", source, "2-2")[2]) == 1
    assert calls == ["https://fixture.invalid/book", "https://fixture.invalid/c2"]


def test_html_candidate_id_retains_search_url_without_template():
    config = {"name": "Fixture", "host": "https://fixture.invalid", "kind": "html", "search": {"item_selector": ".book", "title_selector": ".title", "url_selector": "a"}, "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"}, "content": {"selector": ".content"}}
    candidate = fetch_novel.parse_search_results(config, "<div class='book'><a href='/novel/1'>Book</a><span class='title'>Book</span></div>", "Book")[0]
    assert fetch_novel.decode_candidate_url(candidate["id"]) == candidate["url"]


def test_main_does_not_apply_html_range_twice(tmp_path, monkeypatch):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "fixture.json").write_text(json.dumps({"name": "Fixture", "kind": "html", "host": "https://fixture.invalid", "search": {"item_selector": ".book", "title_selector": ".title", "url_selector": "a"}, "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"}, "content": {"selector": ".content"}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen = {}
    monkeypatch.setattr(fetch_novel, "_download_html", lambda url, source, chapter_range=None: (seen.update(url=url) or ("Book", "Author", [(2, "第二章", "正文")])) )
    candidate_id = "fixture:1~" + fetch_novel._encode_candidate_url("https://fixture.invalid/novel/1")
    assert fetch_novel.main(["--book", candidate_id, "--chapters", "2-2", "--sources", str(source_dir)]) == 0
    assert seen["url"] == "https://fixture.invalid/novel/1"
    assert (tmp_path / "styles/book--author/raw/002-第二章.txt").exists()


def test_main_mixed_kind_fallback_uses_download_range_metadata(tmp_path, monkeypatch):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "gutendex.json").write_text(json.dumps({
        "name": "gutendex", "kind": "gutendex", "host": "https://gutendex.test",
        "search_url": "https://gutendex.test/books/?search={keyword}",
    }), encoding="utf-8")
    (source_dir / "fixture.json").write_text(json.dumps({
        "name": "Fixture", "kind": "html", "host": "https://fixture.test",
        "search": {"item_selector": ".book", "title_selector": ".title", "url_selector": "a"},
        "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"},
        "content": {"selector": ".content"},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    alternative = {"id": "fixture:1", "title": "Same", "author": "Author", "url": "https://fixture.test/book/1", "source": "Fixture"}
    seen = {}
    monkeypatch.setattr(fetch_novel, "_download_gutendex", lambda *args: (_ for _ in ()).throw(RuntimeError("unavailable")))
    monkeypatch.setattr(fetch_novel, "search_sources", lambda title, sources: [alternative])
    monkeypatch.setattr(fetch_novel, "_download_html", lambda url, source, chapter_range=None: (seen.update(range=chapter_range) or ("Same", "Author", [(2, "第二章", "正文")])))

    assert fetch_novel.main(["--book", "gutendex:1", "--title", "Same", "--author", "Author", "--chapters", "2-2", "--sources", str(source_dir)]) == 0
    assert seen["range"] == "2-2"
    assert (tmp_path / "styles/same--author/raw/002-第二章.txt").exists()


def test_main_html_book_url_uses_download_result_range_metadata(tmp_path, monkeypatch):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "fixture.json").write_text(json.dumps({
        "name": "Fixture", "kind": "html", "host": "https://fixture.test",
        "search": {"item_selector": ".book", "title_selector": ".title", "url_selector": "a"},
        "toc": {"chapter_selector": ".chapter", "title_selector": ".ct", "url_selector": "a"},
        "content": {"selector": ".content"},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen = {}
    monkeypatch.setattr(fetch_novel, "_download_html", lambda url, source, chapter_range=None: (seen.update(range=chapter_range) or ("Same", "Author", [(2, "第二章", "正文")])))

    assert fetch_novel.main(["--book", "https://fixture.test/book/1", "--chapters", "2-2", "--sources", str(source_dir)]) == 0
    assert seen["range"] == "2-2"
    assert (tmp_path / "styles/same--author/raw/002-第二章.txt").exists()


def test_main_mediawiki_book_url_requires_author_confirmation(tmp_path, monkeypatch):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    (source_dir / "wiki.json").write_text(json.dumps({
        "name": "wiki", "kind": "mediawiki", "host": "https://wiki.test",
        "api_url": "https://wiki.test/w/api.php",
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit, match="author"):
        fetch_novel.main(["--book", "https://wiki.test/wiki/Book", "--sources", str(source_dir)])


def test_force_refuses_target_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = Path("raw")
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    link = target / "001-Chapter.txt"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        fetch_novel.write_chapters(target, [(1, "Chapter", "overwrite")], force=True)
    assert outside.read_text(encoding="utf-8") == "keep"


def test_write_chapters_rejects_dangling_output_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("dangling").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        fetch_novel.write_chapters("dangling", [(1, "Chapter", "正文")], force=True)


def test_mediawiki_encoded_url_is_unquoted_before_api(monkeypatch):
    source = {"name": "zh-wikisource", "kind": "mediawiki", "host": "https://zh.wikisource.org", "api_url": "https://zh.wikisource.org/w/api.php"}
    seen = {}
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda url, **kwargs: seen.update(url=url) or '{"parse":{"text":"<h1>第一章</h1><p>正文</p>"}}')
    fetch_novel.download_mediawiki_url("https://zh.wikisource.org/wiki/%E7%BA%A2%E6%A5%BC%E6%A2%A6", source)
    assert "%25" not in seen["url"]
    assert "%E7%BA%A2" in seen["url"]


def test_gutendex_applies_clean_regex(monkeypatch):
    source = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.com", "clean_regex": [r"ADMARK"]}
    responses = iter(['{"title":"Book","authors":[{"name":"Author"}],"formats":{"text/plain":"https://gutenberg.test/book.txt"}}', "Chapter 1\nADMARK\n正文"])
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda url, **kwargs: next(responses))
    assert "ADMARK" not in fetch_novel._download_gutendex("gutendex:1", source)[2][0][2]


def test_cli_search_aggregates_failures_without_downloading(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    for name, kind in (("one", "gutendex"), ("two", "mediawiki")):
        (source_dir / f"{name}.json").write_text(json.dumps({"name": name, "kind": kind, "host": "https://example.test", "api_url": "https://example.test/api"}), encoding="utf-8")
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    assert fetch_novel.main(["--search", "Book", "--sources", str(source_dir)]) == 0
    assert capsys.readouterr().out.strip() == "[]"
    assert not (tmp_path / "styles").exists()


def test_cli_from_file_writes_utf8_raw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book = tmp_path / "book.txt"
    book.write_text("第一章\n甲\n\n第二章\n乙", encoding="utf-8")
    assert fetch_novel.main(["--from-file", str(book), "--title", "书", "--author", "作者", "--chapters", "1-2"]) == 0
    assert (tmp_path / "styles/书--作者/raw/001-第一章.txt").read_text(encoding="utf-8") == "甲\n"


def test_epub_uses_opf_spine_order(tmp_path):
    epub = tmp_path / "spine.epub"
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr("META-INF/container.xml", "<container><rootfile full-path='OPS/package.opf'/></container>")
        zf.writestr("OPS/package.opf", "<package><manifest><item id='b' href='b.xhtml'/><item id='a' href='a.xhtml'/></manifest><spine><itemref idref='a'/><itemref idref='b'/></spine></package>")
        zf.writestr("OPS/a.xhtml", "<h1>第一章</h1><p>甲</p>")
        zf.writestr("OPS/b.xhtml", "<h1>第二章</h1><p>乙</p>")
    assert [chapter[1] for chapter in fetch_novel.load_input_file(epub)] == ["第一章", "第二章"]


def test_write_chapters_rejects_absolute_and_symlink_escape(tmp_path):
    with pytest.raises(ValueError):
        fetch_novel.write_chapters(tmp_path / "raw", [(1, "x", "y")])
    outside = tmp_path / "outside"
    outside.mkdir()
    link = Path.cwd() / "tests" / "_escape-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError):
            fetch_novel.write_chapters("tests/_escape-link", [(1, "x", "y")])
    finally:
        if link.is_symlink():
            link.unlink()


def test_mediawiki_and_gutendex_download_adapters(monkeypatch):
    mediawiki = {"name": "zh-wikisource", "kind": "mediawiki", "api_url": "https://zh.wikisource.org/w/api.php", "clean_regex": [r"MARKER"]}
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda url, **kwargs: json.dumps({"parse": {"text": "<h1>第一章</h1><p>MARKER正文</p>"}}))
    assert fetch_novel._download_mediawiki({"id": "zh-wikisource:page:%E7%89%88", "title": "版"}, mediawiki)[2][0][2] == "正文"
    gutendex = {"name": "gutendex", "kind": "gutendex", "host": "https://gutendex.com"}
    responses = iter([json.dumps({"title": "Book", "authors": [{"name": "Author"}], "formats": {"text/plain": "https://gutenberg.test/book.txt"}}), "Chapter 1\n正文"])
    monkeypatch.setattr(fetch_novel, "fetch_url", lambda url, **kwargs: next(responses))
    assert fetch_novel._download_gutendex("gutendex:1", gutendex)[1] == "Author"


def test_fetch_url_sets_user_agent_and_delay(monkeypatch):
    seen = {}

    class Response:
        headers = {"content-type": "text/plain; charset=utf-8"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b"ok"

    monkeypatch.setattr(fetch_novel.time, "sleep", lambda seconds: seen.update(delay=seconds))
    monkeypatch.setattr(fetch_novel.urllib.request, "urlopen", lambda request, timeout: seen.update(request=request, timeout=timeout) or Response())
    assert fetch_novel.fetch_url("https://example.test", delay=0.25) == "ok"
    assert seen["delay"] == 0.25
    assert seen["request"].headers["User-agent"] == fetch_novel.USER_AGENT
