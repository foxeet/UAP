"""Static configuration: target endpoints and the hosts that must be
allowlisted in the environment's network egress settings.
"""
from __future__ import annotations

# A realistic browser User-Agent. Government WAFs frequently reject the
# default urllib agent, so we present as a normal browser.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Each source: the page(s) to crawl for media/links.
SOURCES = {
    "pursue": {
        "label": "PURSUE — Presidential Unsealing and Reporting System for UAP Encounters",
        "pages": [
            "https://www.war.gov/UFO/",
        ],
    },
    "aaro": {
        "label": "AARO — Official UAP Imagery",
        "pages": [
            "https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/",
            "https://www.aaro.mil/UAP-Records/",
        ],
    },
    "nasa": {
        "label": "NASA — UAP science page",
        "pages": [
            "https://science.nasa.gov/uap/",
        ],
    },
    "nara": {
        "label": "National Archives — UAP Records Collection (RG 615)",
        # NARA exposes a public catalog API; far more reliable than HTML.
        "api": "https://catalog.archives.gov/api/v2/records/search",
        "topic_page": "https://www.archives.gov/research/topics/uaps",
        # Record group for the UAP Records Collection (2024 NDAA, §1841-1843).
        "record_group": 615,
        "query": "unidentified anomalous phenomena",
    },
}

# Hosts that must appear in the environment's egress allowlist for the
# scraper to reach anything. `doctor` probes each of these.
REQUIRED_HOSTS = {
    "www.war.gov": "PURSUE portal (HTML + media)",
    "www.aaro.mil": "AARO imagery pages",
    "science.nasa.gov": "NASA UAP page",
    "www.archives.gov": "National Archives topic page",
    "catalog.archives.gov": "National Archives catalog API + media",
}

# Media for the .gov sites is frequently hosted on these CDNs. Allowlist
# them too if downloads 403 even after the primary hosts are permitted.
OPTIONAL_HOSTS = {
    "media.defense.gov": "DoD/AARO video & image CDN",
    "www.dvidshub.net": "DVIDS military media (AARO videos)",
    "www.nasa.gov": "NASA report PDFs / press releases",
    "images-assets.nasa.gov": "NASA imagery CDN",
    "s3.amazonaws.com": "NARA digital object storage",
}

# File extension -> media kind.
EXT_KIND = {
    ".mp4": "video", ".mov": "video", ".m4v": "video", ".webm": "video", ".avi": "video",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".tif": "image",
    ".tiff": "image", ".bmp": "image", ".webp": "image",
    ".pdf": "document", ".doc": "document", ".docx": "document", ".txt": "document",
    ".xls": "document", ".xlsx": "document", ".csv": "document", ".zip": "document",
}
