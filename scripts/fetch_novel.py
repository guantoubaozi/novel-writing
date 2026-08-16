"""Fetch public-domain novel chapters and normalize local inputs.

The command intentionally keeps samples local.  Respect copyright, robots.txt,
terms of service and the source's request limits; only retain material you are
permitted to use and do not redistribute downloaded prose.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html as html_lib
import json
import posixpath
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


USER_AGENT = "novel-style-import/1.0 (local style analysis; respectful fetch)"
BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr"}


@dataclass
class DownloadResult:
    title: str
    author: str
    chapters: list[tuple[int, str, str]]
    range_applied: bool = False
    source_kind: str | None = None

    def __iter__(self):
        yield self.title
        yield self.author
        yield self.chapters

    def __getitem__(self, index):
        return (self.title, self.author, self.chapters)[index]

    def __len__(self):
        return 3


class _Node:
    def __init__(self, tag: str = "root", attrs: dict[str, str] | None = None, parent: "_Node | None" = None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.children: list[_Node | str] = []


class _TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root, self.stack = _Node(), []

    def handle_starttag(self, tag, attrs):
        node = _Node(tag.lower(), {k.lower(): (v or "") for k, v in attrs}, self.stack[-1] if self.stack else self.root)
        (self.stack[-1] if self.stack else self.root).children.append(node)
        if tag.lower() not in {"br", "img", "hr", "meta", "link", "input"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag.lower():
                del self.stack[i:]
                break

    def handle_data(self, data):
        (self.stack[-1] if self.stack else self.root).children.append(data)


def _parse_html(source: str) -> _Node:
    parser = _TreeParser()
    parser.feed(source)
    return parser.root


def _matches(node: _Node, token: str) -> bool:
    token = token.strip()
    if not token or token == "*":
        return True
    tag = re.match(r"^[A-Za-z][\w-]*", token)
    if tag and node.tag != tag.group(0).lower():
        return False
    ident = re.search(r"#([\w-]+)", token)
    if ident and node.attrs.get("id") != ident.group(1):
        return False
    classes = re.findall(r"\.([\w-]+)", token)
    have = set(node.attrs.get("class", "").split())
    return all(item in have for item in classes)


def _descendants(node: _Node) -> Iterable[_Node]:
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _descendants(child)


def _select(root: _Node, selector: str) -> list[_Node]:
    current = [root]
    for token in selector.replace(",", " ").split():
        nxt = []
        for parent in current:
            nxt.extend(item for item in _descendants(parent) if _matches(item, token))
        current = nxt
    return current


def _select_with_self(root: _Node, selector: str) -> list[_Node]:
    return ([root] if selector and _matches(root, selector) else []) + _select(root, selector)


def _node_text(node: _Node) -> str:
    chunks: list[str] = []
    def visit(item: _Node | str):
        if isinstance(item, str):
            chunks.append(item)
            return
        if item.tag in {"script", "style", "noscript", "template"}:
            return
        for child in item.children:
            visit(child)
        if item.tag in BLOCK_TAGS:
            chunks.append("\n")
    visit(node)
    return re.sub(r"[ \t\f\r\v]+", " ", "".join(chunks).replace("\xa0", " ")).strip()


def _remove_nodes(root: _Node, selectors: Iterable[str]):
    doomed = {id(item) for selector in selectors for item in _select(root, selector)}
    def prune(node: _Node):
        node.children = [child for child in node.children if not isinstance(child, _Node) or id(child) not in doomed]
        for child in node.children:
            if isinstance(child, _Node):
                prune(child)
    prune(root)


def clean_text(value: str, clean_regex: Iterable[str] | None = None) -> str:
    root = _parse_html(value)
    _remove_nodes(root, ["script", "style", "noscript"])
    text = _node_text(root)
    for pattern in clean_regex or []:
        text = re.sub(pattern, "", text, flags=re.I)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def slugify(title: str, author: str = "") -> str:
    def part(value: str) -> str:
        value = html_lib.unescape(value).casefold().strip()
        value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value, flags=re.UNICODE)
        return re.sub(r"-+", "-", value).strip("-._")
    title_part, author_part = part(title), part(author)
    return (f"{title_part}--{author_part}" if author_part else title_part)[:120] or "untitled"


def _safe_name(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE).strip(".-")
    return value[:100] or "chapter"


def _source_key(value: str) -> str:
    return _safe_name(value).casefold()


def _encode_candidate_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")


def decode_candidate_url(candidate_id: str) -> str | None:
    if "~" not in candidate_id:
        return None
    encoded = candidate_id.rsplit("~", 1)[-1]
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def parse_search_results(config: dict[str, Any], document: str, keyword: str) -> list[dict[str, str]]:
    root = _parse_html(document)
    spec = config.get("search") or {
        "item_selector": config.get("search_result_selector", "article"),
        "title_selector": config.get("book_title_selector", "h1"),
        "author_selector": config.get("book_author_selector", ""),
        "url_selector": config.get("toc_url_selector", "a"),
    }
    result = []
    for item in _select(root, spec["item_selector"]):
        title_nodes = _select_with_self(item, spec["title_selector"])
        author_nodes = _select_with_self(item, spec.get("author_selector", "")) if spec.get("author_selector") else []
        link_nodes = _select_with_self(item, spec.get("url_selector", "a"))
        if not title_nodes or not link_nodes:
            continue
        title, author = _node_text(title_nodes[0]), _node_text(author_nodes[0]) if author_nodes else ""
        url = urllib.parse.urljoin(config.get("host", "https://fixture.invalid"), link_nodes[0].attrs.get("href", ""))
        parsed = urllib.parse.urlparse(url)
        key = parsed.path.rstrip("/").split("/")[-1] or hashlib.sha1(url.encode()).hexdigest()[:10]
        source = config["name"]
        result.append({"id": f"{_source_key(source)}:{key}~{_encode_candidate_url(url)}", "title": title, "author": author, "url": url, "source": source})
    return result


def parse_toc(config: dict[str, Any], document: str) -> list[dict[str, Any]]:
    root = _parse_html(document)
    if not config.get("toc") and config.get("chapter_link_selector"):
        result = []
        for index, link in enumerate(_select(root, config["chapter_link_selector"]), 1):
            title_nodes = _select_with_self(link, config.get("chapter_title_selector", "")) if config.get("chapter_title_selector") else []
            title = _node_text(title_nodes[0]) if title_nodes else _node_text(link)
            result.append({"index": index, "title": title, "url": urllib.parse.urljoin(config.get("host", ""), link.attrs.get("href", ""))})
        return result
    spec = config.get("toc") or {"chapter_selector": "a", "title_selector": "", "url_selector": "a"}
    result = []
    for index, item in enumerate(_select(root, spec["chapter_selector"]), 1):
        title_nodes = _select_with_self(item, spec.get("title_selector", "a"))
        link_nodes = _select_with_self(item, spec.get("url_selector", "a"))
        if not link_nodes:
            continue
        title = _node_text(title_nodes[0]) if title_nodes else _node_text(link_nodes[0])
        url = urllib.parse.urljoin(config.get("host", ""), link_nodes[0].attrs.get("href", ""))
        result.append({"index": index, "title": title, "url": url})
    return result


def parse_chapter(config: dict[str, Any], document: str) -> str:
    root = _parse_html(document)
    spec = config.get("content") or {"selector": config.get("content_selector", "body"), "remove_selectors": config.get("remove_selectors", [])}
    nodes = _select(root, spec.get("selector", "body")) if spec.get("selector") else [root]
    if not nodes:
        raise ValueError("content selector matched no nodes")
    _remove_nodes(nodes[0], spec.get("remove_selectors", []))
    return clean_text(_node_html(nodes[0]), config.get("clean_regex", []))


def _node_html(node: _Node) -> str:
    chunks = []
    def visit(item):
        if isinstance(item, str):
            chunks.append(html_lib.escape(item))
            return
        chunks.append(f"<{item.tag}>")
        for child in item.children:
            visit(child)
        chunks.append(f"</{item.tag}>")
    visit(node)
    return "".join(chunks)


def parse_chapter_range(value: str, total: int) -> list[int]:
    match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", value)
    if not match:
        raise ValueError("chapters must be N or N-M")
    start, end = int(match.group(1)), int(match.group(2) or match.group(1))
    if start < 1 or end < start or end > total:
        raise ValueError(f"chapter range outside 1-{total}")
    return list(range(start, end + 1))


def _requested_indices(value: str, total: int) -> list[int]:
    try:
        return parse_chapter_range(value, total)
    except ValueError:
        if value == "1-10":
            return list(range(1, min(10, total) + 1))
        raise


def _chapterize(text: str, clean_regex: Iterable[str] | None = None) -> list[tuple[int, str, str]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    pattern = re.compile(r"(?im)^(?:#{1,6}\s*)?((?:第\s*[0-9一二三四五六七八九十百千]+\s*[章节回卷].*)|(?:chapter\s+\w+.*))$")
    matches = list(pattern.finditer(text))
    if not matches:
        return [(1, "Chapter 1", clean_text(text, clean_regex))] if text else []
    chapters = []
    for i, match in enumerate(matches):
        body = text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)].strip()
        title = re.sub(r"^#+\s*", "", match.group(1)).strip()
        chapters.append((i + 1, title, clean_text(body, clean_regex)))
    return chapters


def load_input_file(path: str | Path) -> list[tuple[int, str, str]]:
    path = Path(path)
    if path.suffix.lower() in {".txt", ".md"}:
        return _chapterize(path.read_text(encoding="utf-8-sig"))
    if path.suffix.lower() == ".epub":
        chapters = []
        with zipfile.ZipFile(path) as archive:
            names = _epub_spine_names(archive)
            if not names:
                names = sorted(n for n in archive.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")) and "toc" not in n.lower() and "nav" not in n.lower())
            for index, name in enumerate(names, 1):
                document = archive.read(name).decode("utf-8", "replace")
                root = _parse_html(document)
                heading = next((_node_text(n) for sel in ("h1", "h2", "h3") for n in _select(root, sel) if _node_text(n)), Path(name).stem)
                body_lines = clean_text(document).splitlines()
                if body_lines and body_lines[0] == heading:
                    body_lines = body_lines[1:]
                body = "\n".join(body_lines)
                chapters.append((index, heading, body))
        return chapters
    raise ValueError("supported file types are .txt, .md and .epub")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _epub_spine_names(archive: zipfile.ZipFile) -> list[str]:
    try:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(node for node in container.iter() if _local_name(node.tag) == "rootfile")
        opf_path = rootfile.attrib["full-path"]
        opf = ElementTree.fromstring(archive.read(opf_path))
        manifest = {node.attrib["id"]: node.attrib["href"] for node in opf.iter() if _local_name(node.tag) == "item" and node.attrib.get("id")}
        base = posixpath.dirname(opf_path)
        names = []
        for ref in (node for node in opf.iter() if _local_name(node.tag) == "itemref"):
            href = manifest.get(ref.attrib.get("idref", ""))
            if href:
                href = href.split("#", 1)[0]
                names.append(posixpath.normpath(posixpath.join(base, urllib.parse.unquote(href))))
        return names
    except (KeyError, ElementTree.ParseError, StopIteration):
        return []


def load_paste() -> list[tuple[int, str, str]]:
    return _chapterize(sys.stdin.read())


def fetch_url(url: str, timeout: int = 30, delay: float = 0.0) -> str:
    if delay:
        time.sleep(delay)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
        headers = response.headers
        if hasattr(headers, "get_content_charset"):
            charset = headers.get_content_charset() or "utf-8"
        else:
            match = re.search(r"charset=([A-Za-z0-9_-]+)", str(headers.get("content-type", "")), flags=re.I)
            charset = match.group(1) if match else "utf-8"
    return data.decode(charset, "replace")


def load_url(url: str, selector: str | None = None, title: str | None = None) -> list[tuple[int, str, str]]:
    document = fetch_url(url)
    if selector:
        root = _parse_html(document)
        nodes = _select(root, selector)
        if not nodes:
            raise ValueError("URL selector matched no nodes")
        document = _node_html(nodes[0])
    heading = title
    if not heading:
        root = _parse_html(document)
        heading = next((_node_text(n) for sel in ("h1", "h2", "title") for n in _select(root, sel) if _node_text(n)), "Chapter 1")
    return [(1, heading, clean_text(document))]


def validate_source(source: dict[str, Any]) -> None:
    if not isinstance(source.get("name"), str) or not source["name"]:
        raise ValueError("source.name is required")
    kind = source.get("kind")
    if kind not in {"html", "gutendex", "mediawiki"}:
        raise ValueError("source.kind must be html, gutendex or mediawiki")
    host = source.get("host")
    if kind in {"gutendex", "mediawiki"} and (not isinstance(host, str) or not host.strip()):
        raise ValueError(f"{kind} source requires non-empty host")
    if kind == "gutendex":
        source.setdefault("search_url", "https://gutendex.com/books/?search={keyword}")
        search_url = source.get("search_url")
        if not isinstance(search_url, str) or not search_url.strip():
            raise ValueError("gutendex source requires non-empty search_url")
        try:
            parsed_search_url = urllib.parse.urlparse(search_url.format(keyword="style-import"))
        except (KeyError, ValueError) as exc:
            raise ValueError("gutendex source search_url must be a usable URL template") from exc
        if parsed_search_url.scheme not in {"http", "https"} or not parsed_search_url.netloc:
            raise ValueError("gutendex source search_url must be a usable URL template")
    if kind == "mediawiki":
        api_url = source.get("api_url")
        if not isinstance(api_url, str) or not api_url.strip():
            raise ValueError("mediawiki source requires non-empty api_url")
    has_search = "search" in source or (source.get("search_url") and source.get("search_result_selector"))
    has_toc = "toc" in source or source.get("chapter_link_selector")
    has_content = "content" in source or source.get("content_selector")
    if kind == "html" and (not host or not has_search or not has_toc or not has_content):
        raise ValueError("html source requires host/search/toc/content")


def load_sources(directory: str | Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(Path(directory).glob("*.json")):
        source = json.loads(path.read_text(encoding="utf-8"))
        validate_source(source)
        source["_path"] = str(path)
        result.append(source)
    return result


def same_identity(first: dict[str, Any], second: dict[str, Any]) -> bool:
    norm = lambda value: re.sub(r"\W+", "", (value or "").casefold(), flags=re.UNICODE)
    first_title, second_title = norm(first.get("title")), norm(second.get("title"))
    first_author, second_author = norm(first.get("author")), norm(second.get("author"))
    return bool(first_title and first_author and first_title == second_title and first_author == second_author)


def write_chapters(out: str | Path, chapters: Iterable[tuple[int, str, str]], force: bool = False) -> None:
    out = Path(out)
    if out.is_absolute() or any(part == ".." for part in out.parts):
        raise ValueError("output path must be a relative path without '..'")
    root = Path.cwd().resolve()
    resolved = out.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("output path must remain inside the current project") from exc
    if out.is_symlink():
        raise ValueError("output path may not be a symlink")
    out.mkdir(parents=True, exist_ok=True)
    chapters = list(chapters)
    targets = [(out / f"{number:03d}-{_safe_name(title)}.txt", body) for number, title, body in chapters]
    symlink_targets = [target for target, _ in targets if target.is_symlink()]
    if symlink_targets:
        raise ValueError(f"refusing to follow symlink target {symlink_targets[0]}")
    if not force:
        conflicts = [target for target, _ in targets if target.exists()]
        if conflicts:
            raise FileExistsError(f"refusing to overwrite {conflicts[0]}; pass --force")
    for target, body in targets:
        target.write_text(body.rstrip() + "\n", encoding="utf-8")


def _search_gutendex(source: dict[str, Any], keyword: str) -> list[dict[str, str]]:
    endpoint = source.get("search_url", "https://gutendex.com/books/?search={keyword}").format(keyword=urllib.parse.quote_plus(keyword))
    payload = json.loads(fetch_url(endpoint, delay=source.get("delay_ms", 1000) / 1000))
    result = []
    for book in payload.get("results", []):
        authors = book.get("authors") or [{}]
        author = authors[0].get("name", "")
        result.append({"id": f"{_source_key(source['name'])}:{book['id']}", "title": book.get("title", ""), "author": author, "url": f"https://www.gutenberg.org/ebooks/{book['id']}", "source": source["name"]})
    return result


def _search_mediawiki(source: dict[str, Any], keyword: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": keyword, "srlimit": 10, "format": "json"})
    payload = json.loads(fetch_url(source["api_url"] + "?" + query, delay=source.get("delay_ms", 1000) / 1000))
    result = []
    for item in payload.get("query", {}).get("search", []):
        title = item.get("title", "")
        page_url = source["host"] + "/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        key = urllib.parse.quote(title, safe="")
        result.append({"id": f"{_source_key(source['name'])}:page:{key}", "title": title, "author": "", "author_status": "needs_manual_confirmation", "url": page_url, "source": source["name"]})
    return result


def search_sources(keyword: str, sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for source in sources:
        try:
            if source["kind"] == "gutendex":
                result.extend(_search_gutendex(source, keyword))
            elif source["kind"] == "mediawiki":
                result.extend(_search_mediawiki(source, keyword))
            elif source["kind"] == "html":
                endpoint = source["search_url"].format(keyword=urllib.parse.quote_plus(keyword))
                result.extend(parse_search_results(source, fetch_url(endpoint, delay=source.get("delay_ms", 800) / 1000), keyword))
        except Exception as exc:
            print(f"warning: {source['name']} unavailable: {exc}", file=sys.stderr)
    seen = set()
    return [item for item in result if not (item["id"] in seen or seen.add(item["id"]))]


def _download_gutendex(candidate_id: str, source: dict[str, Any]) -> tuple[str, str, list[tuple[int, str, str]]]:
    book_id = candidate_id.rsplit(":", 1)[-1]
    payload = json.loads(fetch_url(f"{source.get('host', 'https://gutendex.com')}/books/{book_id}/", delay=source.get("delay_ms", 1000) / 1000))
    title = payload.get("title", "untitled")
    authors = payload.get("authors") or [{}]
    author = authors[0].get("name", "")
    formats = payload.get("formats", {})
    text_url = next((url for mime, url in formats.items() if mime.startswith("text/plain") and "zip" not in url), None)
    if not text_url:
        raise ValueError("Gutendex result has no plain-text format")
    chapters = _chapterize(fetch_url(text_url, delay=source.get("delay_ms", 1000) / 1000), source.get("clean_regex", []))
    return title, author, chapters


def _gutendex_identity(candidate_id: str, source: dict[str, Any]) -> tuple[str, str]:
    book_id = candidate_id.rsplit(":", 1)[-1]
    payload = json.loads(fetch_url(f"{source.get('host', 'https://gutendex.com')}/books/{book_id}/", delay=source.get("delay_ms", 1000) / 1000))
    authors = payload.get("authors") or [{}]
    return payload.get("title", ""), authors[0].get("name", "")


def _enrich_candidate(candidate: dict[str, Any], source: dict[str, Any]) -> None:
    if candidate.get("title") and candidate.get("author"):
        return
    if source["kind"] == "gutendex":
        title, author = _gutendex_identity(candidate["id"], source)
    elif source["kind"] == "mediawiki":
        title = urllib.parse.unquote(candidate["id"].split(":page:", 1)[-1])
        author = candidate.get("author", "")
    elif source["kind"] == "html" and candidate.get("url"):
        root = _parse_html(fetch_url(candidate["url"], delay=source.get("delay_ms", 800) / 1000))
        title_nodes = _select(root, source.get("book_title_selector", "h1"))
        author_nodes = _select(root, source.get("book_author_selector", "")) if source.get("book_author_selector") else []
        title = _node_text(title_nodes[0]) if title_nodes else ""
        author = _node_text(author_nodes[0]) if author_nodes else ""
    else:
        return
    candidate["title"], candidate["author"] = title, author


def _download_html(candidate_url: str, source: dict[str, Any], chapter_range: str | None = None) -> tuple[str, str, list[tuple[int, str, str]]]:
    landing = fetch_url(candidate_url, delay=source.get("delay_ms", 800) / 1000)
    root = _parse_html(landing)
    title_nodes = _select(root, source.get("book_title_selector", "h1"))
    author_nodes = _select(root, source.get("book_author_selector", "")) if source.get("book_author_selector") else []
    title = _node_text(title_nodes[0]) if title_nodes else "untitled"
    author = _node_text(author_nodes[0]) if author_nodes else ""
    toc = parse_toc(source, landing)
    if chapter_range:
        selected = _requested_indices(chapter_range, len(toc))
        toc = [toc[index - 1] for index in selected]
    chapters = []
    for chapter in toc:
        document = fetch_url(chapter["url"], delay=source.get("delay_ms", 800) / 1000)
        chapters.append((chapter["index"], chapter["title"], parse_chapter(source, document)))
    return title, author, chapters


def _download_mediawiki(candidate: dict[str, Any], source: dict[str, Any]) -> tuple[str, str, list[tuple[int, str, str]]]:
    title = candidate.get("title") or urllib.parse.unquote(candidate["id"].split(":page:", 1)[-1])
    query = urllib.parse.urlencode({"action": "parse", "page": title, "prop": "text", "format": "json", "formatversion": 2})
    payload = json.loads(fetch_url(source["api_url"] + "?" + query, delay=source.get("delay_ms", 1000) / 1000))
    document = payload.get("parse", {}).get("text", "")
    if isinstance(document, dict):
        document = document.get("*", "")
    if not document:
        raise ValueError("MediaWiki page has no parsed text")
    return title, candidate.get("author", ""), _chapterize(clean_text(document), source.get("clean_regex", []))


def download_mediawiki_url(url: str, source: dict[str, Any], author: str = "") -> tuple[str, str, list[tuple[int, str, str]]]:
    page_title = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    candidate = {"id": f"{_source_key(source['name'])}:page:{urllib.parse.quote(page_title)}", "title": page_title, "author": author}
    return _download_mediawiki(candidate, source)


def resolve_book_url(url: str, sources: list[dict[str, Any]]) -> tuple[dict[str, Any], str] | None:
    match = re.search(r"/(?:ebooks|books)/(\d+)(?:[/?#]|$)", url)
    if match:
        source = next((item for item in sources if item["kind"] == "gutendex"), None)
        if source:
            return source, f"{_source_key(source['name'])}:{match.group(1)}"
    parsed = urllib.parse.urlparse(url)
    source = next((item for item in sources if urllib.parse.urlparse(item.get("host", "")).netloc == parsed.netloc), None)
    return (source, url) if source else None


def _coerce_download_result(value: tuple[str, str, list[tuple[int, str, str]]] | DownloadResult, source_kind: str, range_applied: bool) -> DownloadResult:
    if isinstance(value, DownloadResult):
        return value
    title, author, chapters = value
    return DownloadResult(title, author, chapters, range_applied=range_applied, source_kind=source_kind)


def download_candidate(candidate: dict[str, Any], source: dict[str, Any], sources: list[dict[str, Any]], chapter_range: str | None = None) -> DownloadResult:
    """Download a confirmed candidate, trying only identity-equivalent sources."""
    try:
        if source["kind"] == "gutendex":
            return _coerce_download_result(_download_gutendex(candidate["id"], source), source["kind"], False)
        if source["kind"] == "html":
            result = _download_html(candidate["url"], source, chapter_range) if chapter_range else _download_html(candidate["url"], source)
            return _coerce_download_result(result, source["kind"], bool(chapter_range))
        if source["kind"] == "mediawiki":
            return _coerce_download_result(_download_mediawiki(candidate, source), source["kind"], False)
        raise ValueError("unsupported source kind")
    except Exception as exc:
        if not candidate.get("title") or not candidate.get("author"):
            try:
                _enrich_candidate(candidate, source)
            except Exception:
                pass
        if not candidate.get("title") or not candidate.get("author"):
            raise ValueError("download failed and fallback requires confirmed title and author") from exc
        alternatives = search_sources(candidate["title"], [item for item in sources if item is not source])
        for alternative in alternatives:
            if not same_identity(candidate, alternative):
                continue
            alt_source = next((item for item in sources if item["name"] == alternative["source"]), None)
            if not alt_source:
                continue
            try:
                remaining = [item for item in sources if item is not source and item is not alt_source]
                return download_candidate(alternative, alt_source, remaining, chapter_range)
            except Exception:
                continue
        raise


def _default_output(title: str, author: str) -> Path:
    return Path("styles") / slugify(title, author) / "raw"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch chapters for local style analysis only; respect copyright and website ToS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search")
    group.add_argument("--book")
    group.add_argument("--from-file")
    group.add_argument("--from-url")
    group.add_argument("--paste", action="store_true")
    parser.add_argument("--chapters", default="1-10")
    parser.add_argument("--out")
    parser.add_argument("--title")
    parser.add_argument("--author", default="")
    parser.add_argument("--selector")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sources", default=str(Path(__file__).parent / "booksources"))
    args = parser.parse_args(argv)
    author = args.author
    range_applied = False
    if args.search:
        print(json.dumps(search_sources(args.search, load_sources(args.sources)), ensure_ascii=False, indent=2))
        return 0
    if args.from_file:
        chapters = load_input_file(args.from_file)
        title = args.title or Path(args.from_file).stem
    elif args.from_url:
        chapters = load_url(args.from_url, args.selector, args.title)
        title = args.title or chapters[0][1]
    elif args.paste:
        chapters, title = load_paste(), (args.title or "pasted-text")
    else:
        sources = load_sources(args.sources)
        source_name, _, _ = args.book.partition(":")
        source = next((item for item in sources if _source_key(item["name"]) == source_name.casefold()), None)
        if args.book.startswith("http://") or args.book.startswith("https://"):
            resolved = resolve_book_url(args.book, sources)
            source = source or (resolved[0] if resolved else None)
            resolved_id = resolved[1] if resolved and source and source["kind"] == "gutendex" else None
            if resolved_id and source and source["kind"] == "gutendex":
                result = download_candidate({"id": resolved_id, "title": args.title or "", "author": args.author, "url": args.book, "source": source["name"]}, source, sources, args.chapters)
                title, author, chapters = result
                range_applied = result.range_applied
            elif source and source["kind"] == "html":
                candidate = {"id": args.book, "title": args.title or "", "author": args.author, "url": args.book, "source": source["name"]}
                result = download_candidate(candidate, source, sources, args.chapters)
                title, author, chapters = result
                range_applied = result.range_applied
            elif source and source["kind"] == "mediawiki":
                if not args.author:
                    raise SystemExit("MediaWiki URLs do not provide an author; pass --author after manual confirmation")
                page_title = urllib.parse.unquote(Path(urllib.parse.urlparse(args.book).path).name)
                candidate = {"id": f"{_source_key(source['name'])}:page:{urllib.parse.quote(page_title)}", "title": page_title, "author": args.author, "url": args.book, "source": source["name"]}
                result = download_candidate(candidate, source, sources, args.chapters)
                title, author, chapters = result
                range_applied = result.range_applied
            else:
                chapters = load_url(args.book, args.selector, args.title)
                title, author = args.title or chapters[0][1], args.author
        elif source:
            candidate_key = args.book.rsplit(":", 1)[-1].split("~", 1)[0]
            candidate_url = decode_candidate_url(args.book) or source.get("book_url_template", "").format(host=source.get("host", ""), id=candidate_key)
            if source["kind"] == "mediawiki" and not args.author:
                raise SystemExit("MediaWiki search candidates do not provide an author; pass --author after manual confirmation")
            candidate = {"id": args.book, "title": args.title or "", "author": args.author, "url": candidate_url, "source": source["name"]}
            result = download_candidate(candidate, source, sources, args.chapters)
            title, author, chapters = result
            range_applied = result.range_applied
        else:
            raise SystemExit("unknown candidate ID; run --search first and confirm its source/title/author")
    if not chapters:
        raise SystemExit("no chapters found")
    selected = list(range(1, len(chapters) + 1)) if range_applied else _requested_indices(args.chapters, len(chapters))
    chapters = [chapters[index - 1] for index in selected]
    write_chapters(args.out or _default_output(title, author), chapters, args.force)
    print("Saved local-only samples. Do not redistribute copyrighted source text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
