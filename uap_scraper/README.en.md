<div align="right">

[简体中文](README.md) ｜ **English**

</div>

# uap_scraper — Scrape U.S. official UAP/UFO public materials

A **pure standard-library** (no `pip install` needed) Python tool for fetching the metadata and files of UAP/UFO materials from official U.S. entry points:

- **PURSUE** — `https://www.war.gov/UFO/`
- **AARO Official Imagery** — `https://www.aaro.mil/UAP-Cases/Official-UAP-Imagery/`
- **NASA UAP** — `https://science.nasa.gov/uap/`
- **National Archives RG 615** — `https://catalog.archives.gov/` (Catalog API v2)

> Requirements: Python 3.9+ (tested on 3.11). No third-party dependencies.

---

## ⚠️ About the network: this sandbox cannot reach these official sites by default

This remote container has an **egress allowlist** enabled. These `.gov / .mil / nasa.gov` hosts are **not on the allowlist**, so the proxy returns directly:

```
HTTP 403  x-deny-reason: host_not_allowed
Host not in allowlist: www.war.gov. Add this host to your network egress settings to allow access.
```

This is **not a problem with the websites, nor with the code**, and no custom UA / proxy can (or should) bypass it. Two ways to solve it:

1. **Add the target hosts to your environment's "network egress" settings**, then re-run.
   Docs: https://code.claude.com/docs/en/claude-code-on-the-web
   The hosts that need allowlisting can be listed in one command via `doctor` (see below).
2. **Run this tool locally (on an ordinary networked machine)** — the code works as-is.

---

## Usage

All commands are run from the repository root, in the form `python3 -m uap_scraper <subcommand>`.

### 1) doctor — first check which hosts are reachable

```bash
python3 -m uap_scraper doctor          # check required hosts
python3 -m uap_scraper doctor --all    # also check optional CDN hosts
```

The output marks each host as `OK` or `BLOCKED`, and lists the hosts that need to be added to the allowlist.

### 2) fetch — scrape metadata into JSON

```bash
python3 -m uap_scraper fetch --source all --out data/uap_items.json
# or scrape a single source: --source pursue|aaro|nasa|nara
```

Writes the discovered videos/images/audio/documents/archive records into structured JSON (with title, link, source page, description, etc.). Even if some sources are blocked, it writes out what was scraped and reports the blocked hosts.

### 3) download — download media files

```bash
python3 -m uap_scraper download data/uap_items.json --kind video --out media
# --kind options: video,audio,image,document (comma-separated); --source as above; --force to re-download
```

Saves files in a `source/type/filename` directory structure (e.g. `media/pursue/video/xxx.mp4`).

### 4) report — generate a Markdown index from the JSON

```bash
python3 -m uap_scraper report data/uap_items.json --out docs/index.md
```

### Global options

- `--no-cache` disable disk caching (default caches to `.cache/`)
- `--delay 1.0` seconds between requests (default 1s, polite scraping)
- `-v` verbose logging

---

## NARA (National Archives) API key (optional)

RG 615 is fetched via the NARA Catalog API v2. Anonymous access works, but it is recommended to apply for a free key at https://api.data.gov to raise your quota:

```bash
export NARA_API_KEY=your_key
python3 -m uap_scraper fetch --source nara --out data/nara.json
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The offline unit tests cover the core logic — HTML media extraction, URL classification, NARA JSON parsing, etc. (no network required).

---

## Design notes

- **Egress-aware**: recognizes the proxy's `host_not_allowed` response, raises `EgressBlocked` with actionable guidance instead of dumping an opaque 403.
- **Pure standard library**: `urllib` + `html.parser` + `json`, runnable with zero dependencies on any machine with Python (in the sandbox `pip` works, but the target hosts are still blocked, so we deliberately avoid third-party libraries).
- **Robust scraping**: browser UA, exponential-backoff retries, gzip handling, disk caching, polite rate limiting.
- **Structured output**: a unified `MediaItem` model, convenient for downstream translation / database building.

> Compliance note: this tool only scrapes **public** government materials. Please respect each site's `robots.txt` and terms of use, and keep scraping low-frequency and polite.
