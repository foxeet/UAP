"""HTML parsing helpers (standard-library html.parser only)."""
from __future__ import annotations

import os
import re
import urllib.parse
from html.parser import HTMLParser
from typing import Optional

from .config import EXT_KIND
from .models import MediaItem

_WS = re.compile(r"\s+")


def clean(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip()


def absolute_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, (href or "").strip())


def kind_for_url(url: str) -> Optional[str]:
    path = urllib.parse.urlparse(url).path.lower()
    ext = os.path.splitext(path)[1]
    return EXT_KIND.get(ext)


class _Collector(HTMLParser):
    """Collects links, media tags, the page title and meta description, and
    keeps the text that surrounds each link so we can use it as a caption.
    """

    MEDIA_TAGS = {"a", "video", "audio", "source", "img", "iframe"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.links: list[dict] = []          # {url, text, tag}
        self._in_title = False
        self._open_link: Optional[dict] = None
        self._text_buf: list[str] = []

    # text capture ------------------------------------------------------
    def handle_data(self, data):
        if self._in_title:
            self.title += data
        self._text_buf.append(data)
        if self._open_link is not None:
            self._open_link["text"] += data

    def _recent_text(self, n: int = 160) -> str:
        return clean("".join(self._text_buf))[-n:]

    # tags --------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("description", "og:description") and a.get("content"):
                if not self.meta_description:
                    self.meta_description = clean(a["content"])
            return
        if tag not in self.MEDIA_TAGS:
            return

        url = a.get("href") or a.get("src") or a.get("data-src") or ""
        if not url:
            return
        rec = {
            "tag": tag,
            "url": url,
            "text": "",
            "title_attr": clean(a.get("title") or a.get("alt") or a.get("aria-label") or ""),
            "context": self._recent_text(),
        }
        if tag == "a":
            # capture text until the closing </a>
            self._open_link = rec
        self.links.append(rec)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._open_link is not None:
            self._open_link["text"] = clean(self._open_link["text"])
            self._open_link = None


def parse_page(base_url: str, html: str) -> dict:
    """Returns {title, meta_description, links:[...]} with absolute URLs."""
    c = _Collector()
    c.feed(html)
    for rec in c.links:
        rec["url"] = absolute_url(base_url, rec["url"])
        rec["text"] = clean(rec["text"]) or rec["title_attr"]
    return {
        "title": clean(c.title),
        "meta_description": c.meta_description,
        "links": c.links,
    }


def extract_media(source: str, page_url: str, html: str,
                  same_host_only: bool = False) -> list[MediaItem]:
    """Turn a page into MediaItems for downloadable artifacts (by extension)
    plus a single `page` item carrying the page title/description.
    """
    parsed = parse_page(page_url, html)
    page_host = urllib.parse.urlparse(page_url).hostname or ""
    items: list[MediaItem] = []
    seen: set[str] = set()

    # The page itself (useful even when it has no direct media links).
    items.append(MediaItem(
        source=source, kind="page", url=page_url,
        title=parsed["title"] or page_url, page_url=page_url,
        description=parsed["meta_description"],
    ))

    for rec in parsed["links"]:
        url = rec["url"]
        if not url.startswith(("http://", "https://")):
            continue
        kind = kind_for_url(url)
        if not kind:
            continue  # only keep real media/documents, not nav links
        if same_host_only and (urllib.parse.urlparse(url).hostname or "") != page_host:
            continue
        if url in seen:
            continue
        seen.add(url)
        title = rec["text"] or rec["title_attr"] or os.path.basename(
            urllib.parse.urlparse(url).path)
        items.append(MediaItem(
            source=source, kind=kind, url=url, title=title,
            page_url=page_url, description=rec.get("context", ""),
        ))
    return items
