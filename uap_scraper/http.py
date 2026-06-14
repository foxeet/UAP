"""Minimal HTTP client built on urllib, with:
  * browser-like headers
  * retry with exponential backoff
  * gzip/deflate handling
  * on-disk response cache
  * detection of the sandbox egress proxy's `host_not_allowed` 403
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Optional

from .config import DEFAULT_HEADERS


class EgressBlocked(Exception):
    """Raised when the environment's network egress allowlist blocks a host.

    The sandbox proxy replies 403 with header `x-deny-reason: host_not_allowed`
    and a body like: "Host not in allowlist: www.war.gov. Add this host ...".
    """

    def __init__(self, host: str, detail: str = ""):
        self.host = host
        self.detail = detail
        super().__init__(
            f"Network egress blocked for host '{host}'. "
            f"Add it to the environment's egress allowlist. {detail}".strip()
        )


def _looks_like_egress_block(status: int, headers, body: bytes) -> bool:
    if status != 403:
        return False
    try:
        if (headers.get("x-deny-reason") or "").strip() == "host_not_allowed":
            return True
    except Exception:
        pass
    return body[:64].lstrip().lower().startswith(b"host not in allowlist")


def _decompress(headers, body: bytes) -> bytes:
    enc = (headers.get("Content-Encoding") or "").lower()
    try:
        if enc == "gzip":
            return gzip.decompress(body)
        if enc == "deflate":
            return zlib.decompress(body)
    except Exception:
        return body
    return body


class HttpClient:
    def __init__(
        self,
        cache_dir: Optional[str] = ".cache",
        timeout: float = 30.0,
        retries: int = 4,
        delay: float = 1.0,
        verbose: bool = False,
    ):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.retries = retries
        self.delay = delay  # polite pause between live requests
        self.verbose = verbose
        self._last_request = 0.0
        # Tolerant TLS context (some .gov chains are picky); still verifies.
        self._ctx = ssl.create_default_context()
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    # ---- cache helpers -------------------------------------------------
    def _cache_path(self, url: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return os.path.join(self.cache_dir, h + ".bin")

    def _log(self, *a):
        if self.verbose:
            print("[http]", *a)

    def _throttle(self):
        wait = self.delay - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)

    # ---- core request --------------------------------------------------
    def get_bytes(self, url: str, use_cache: bool = True,
                  extra_headers: Optional[dict] = None) -> bytes:
        cache_path = self._cache_path(url) if use_cache else None
        if cache_path and os.path.exists(cache_path):
            self._log("cache hit", url)
            with open(cache_path, "rb") as fh:
                return fh.read()

        host = urllib.parse.urlparse(url).hostname or url
        headers = dict(DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        last_err: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            req = urllib.request.Request(url, headers=headers)
            try:
                self._log(f"GET {url} (attempt {attempt})")
                with urllib.request.urlopen(req, timeout=self.timeout,
                                            context=self._ctx) as resp:
                    body = _decompress(resp.headers, resp.read())
                self._last_request = time.time()
                if cache_path:
                    with open(cache_path, "wb") as fh:
                        fh.write(body)
                return body
            except urllib.error.HTTPError as e:
                self._last_request = time.time()
                body = b""
                try:
                    body = _decompress(e.headers, e.read())
                except Exception:
                    pass
                if _looks_like_egress_block(e.code, e.headers, body):
                    raise EgressBlocked(host, body.decode("utf-8", "replace").strip())
                last_err = e
                # 4xx other than 429 won't improve on retry.
                if e.code != 429 and 400 <= e.code < 500:
                    raise
            except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as e:
                last_err = e
            backoff = self.delay * (2 ** (attempt - 1))
            self._log(f"retry in {backoff:.1f}s ({last_err})")
            time.sleep(backoff)
        raise RuntimeError(f"GET failed after {self.retries} attempts: {url} ({last_err})")

    def get_text(self, url: str, **kw) -> str:
        return self.get_bytes(url, **kw).decode("utf-8", "replace")

    def get_json(self, url: str, **kw):
        return json.loads(self.get_bytes(url, **kw).decode("utf-8", "replace"))

    def download(self, url: str, dest: str, extra_headers: Optional[dict] = None) -> int:
        """Stream a file to dest. Returns bytes written."""
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        data = self.get_bytes(url, use_cache=False, extra_headers=extra_headers)
        with open(dest, "wb") as fh:
            fh.write(data)
        return len(data)

    def probe(self, url: str) -> dict:
        """Connectivity check for `doctor`. Never raises."""
        host = urllib.parse.urlparse(url).hostname or url
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS, method="GET")
        try:
            self._throttle()
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                self._last_request = time.time()
                return {"host": host, "status": resp.status, "ok": True, "reason": "reachable"}
        except urllib.error.HTTPError as e:
            self._last_request = time.time()
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            if _looks_like_egress_block(e.code, e.headers, body):
                return {"host": host, "status": 403, "ok": False, "reason": "egress_blocked"}
            # Reached the real server (even a 403/404 from it means egress is fine).
            return {"host": host, "status": e.code, "ok": True, "reason": f"http {e.code} from server"}
        except Exception as e:  # noqa: BLE001
            return {"host": host, "status": None, "ok": False, "reason": f"error: {e}"}
