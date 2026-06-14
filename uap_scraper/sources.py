"""Per-source fetchers. Each returns a list[MediaItem] and never raises for
ordinary HTTP errors except EgressBlocked (so the CLI can report it once).
"""
from __future__ import annotations

import os
import urllib.parse
from typing import Callable

from .config import SOURCES
from .http import EgressBlocked, HttpClient
from .models import MediaItem
from .parse import clean, extract_media


def _crawl_pages(client: HttpClient, source: str, pages: list[str]) -> list[MediaItem]:
    out: list[MediaItem] = []
    for page in pages:
        try:
            html = client.get_text(page)
        except EgressBlocked:
            raise
        except Exception as e:  # noqa: BLE001
            out.append(MediaItem(source=source, kind="page", url=page,
                                 title=f"[fetch failed] {page}",
                                 description=str(e)))
            continue
        out.extend(extract_media(source, page, html))
    return out


def fetch_pursue(client: HttpClient) -> list[MediaItem]:
    """PURSUE portal at war.gov/UFO — documents, photos, videos, audio."""
    items = _crawl_pages(client, "pursue", SOURCES["pursue"]["pages"])
    for it in items:
        it.release = it.release or "PURSUE"
    return items


def fetch_aaro(client: HttpClient) -> list[MediaItem]:
    """AARO official imagery — each video/image carries an assessment."""
    return _crawl_pages(client, "aaro", SOURCES["aaro"]["pages"])


def fetch_nasa(client: HttpClient) -> list[MediaItem]:
    """NASA UAP science page + the 2023 independent study report PDF."""
    return _crawl_pages(client, "nasa", SOURCES["nasa"]["pages"])


# ---- National Archives: catalog API v2 --------------------------------
def _walk_json(node, found: list, depth: int = 0):
    """Defensively collect strings that look like titles/naIds/object URLs
    from NARA's nested API response, which changes shape over time.
    """
    if depth > 8:
        return
    if isinstance(node, dict):
        rec = {}
        for k, v in node.items():
            lk = k.lower()
            if lk in ("title", "officialtitle") and isinstance(v, str):
                rec["title"] = v
            elif lk in ("naid", "naId".lower()) and isinstance(v, (str, int)):
                rec["naId"] = str(v)
            elif lk in ("objecturl", "url", "downloadurl", "objectfilename") and isinstance(v, str):
                rec.setdefault("urls", []).append(v)
            _walk_json(v, found, depth + 1)
        if rec.get("title") or rec.get("naId"):
            found.append(rec)
    elif isinstance(node, list):
        for v in node:
            _walk_json(v, found, depth + 1)


def fetch_nara(client: HttpClient, limit: int = 50,
               api_key: str | None = None) -> list[MediaItem]:
    """Query the NARA catalog API v2 for RG 615 records.

    A free API key (from api.data.gov) improves access; pass via the
    NARA_API_KEY env var. Without it the API may rate-limit or 403 (that is
    the server talking, not the egress proxy).
    """
    cfg = SOURCES["nara"]
    params = {
        "q": cfg["query"],
        "recordGroupNumber": str(cfg["record_group"]),
        "limit": str(limit),
    }
    url = cfg["api"] + "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json"}
    api_key = api_key or os.environ.get("NARA_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    items: list[MediaItem] = [MediaItem(
        source="nara", kind="page", url=cfg["topic_page"],
        title="National Archives — UAP Records Collection (RG 615)",
        release="RG 615",
    )]
    try:
        data = client.get_json(url, extra_headers=headers)
    except EgressBlocked:
        raise
    except Exception as e:  # noqa: BLE001
        items[0].description = f"[catalog API fetch failed] {e}"
        return items

    found: list[dict] = []
    _walk_json(data, found)
    for rec in found:
        naid = rec.get("naId", "")
        title = clean(rec.get("title", "")) or f"NARA record {naid}"
        record_url = f"https://catalog.archives.gov/id/{naid}" if naid else cfg["topic_page"]
        items.append(MediaItem(
            source="nara", kind="record", url=record_url, title=title,
            release="RG 615", extra={"naId": naid, "objects": rec.get("urls", [])},
        ))
    return items


FETCHERS: dict[str, Callable[[HttpClient], list[MediaItem]]] = {
    "pursue": fetch_pursue,
    "aaro": fetch_aaro,
    "nasa": fetch_nasa,
    "nara": fetch_nara,
}


def fetch_source(client: HttpClient, name: str) -> list[MediaItem]:
    return FETCHERS[name](client)
