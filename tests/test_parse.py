"""Offline tests for parsing/extraction logic (no network).

Run with:  python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uap_scraper.parse import extract_media, kind_for_url  # noqa: E402
from uap_scraper.sources import _walk_json  # noqa: E402

SAMPLE_HTML = """
<html><head>
  <title>PURSUE — Release 03</title>
  <meta name="description" content="Third batch of declassified UAP files.">
</head><body>
  <nav><a href="/about">About</a></nav>
  <h2>Videos</h2>
  <ul>
    <li><a href="/UFO/media/syrian-uap-instant-acceleration.mp4">Syrian UAP instant acceleration (2021)</a></li>
    <li><a href="https://media.defense.gov/2026/lake-huron-f16-shootdown.mp4">F-16 shoots down UAP over Lake Huron</a></li>
  </ul>
  <h2>Audio</h2>
  <a href="/UFO/media/apollo12-streaks.mp3" title="Apollo 12 streaks of light">Apollo 12 audio</a>
  <h2>Documents</h2>
  <a href="/UFO/docs/fbi-2023-encounter.pdf">FBI 2023 encounter report</a>
  <img src="/UFO/img/orb-rendering.jpg" alt="FBI orb digital rendering">
  <a href="/UFO/page/details">More details (not media)</a>
</body></html>
"""


class TestKindForUrl(unittest.TestCase):
    def test_extensions(self):
        self.assertEqual(kind_for_url("https://x/y/a.mp4"), "video")
        self.assertEqual(kind_for_url("https://x/y/a.MP3"), "audio")
        self.assertEqual(kind_for_url("https://x/y/a.pdf"), "document")
        self.assertEqual(kind_for_url("https://x/y/a.jpg"), "image")
        self.assertIsNone(kind_for_url("https://x/y/page"))


class TestExtractMedia(unittest.TestCase):
    def setUp(self):
        self.items = extract_media("pursue", "https://www.war.gov/UFO/", SAMPLE_HTML)
        self.by_url = {i.url: i for i in self.items}

    def test_page_item_has_title_and_description(self):
        page = next(i for i in self.items if i.kind == "page")
        self.assertEqual(page.title, "PURSUE — Release 03")
        self.assertIn("Third batch", page.description)

    def test_resolves_relative_urls_absolute(self):
        self.assertIn("https://www.war.gov/UFO/media/syrian-uap-instant-acceleration.mp4",
                      self.by_url)

    def test_keeps_offsite_cdn_video(self):
        self.assertIn("https://media.defense.gov/2026/lake-huron-f16-shootdown.mp4",
                      self.by_url)

    def test_classifies_kinds(self):
        kinds = {i.kind for i in self.items}
        self.assertEqual(kinds, {"page", "video", "audio", "image", "document"})

    def test_video_title_captured(self):
        v = self.by_url["https://www.war.gov/UFO/media/syrian-uap-instant-acceleration.mp4"]
        self.assertIn("Syrian UAP", v.title)

    def test_excludes_non_media_links(self):
        # /about and /UFO/page/details have no media extension -> dropped
        self.assertNotIn("https://www.war.gov/about", self.by_url)
        self.assertNotIn("https://www.war.gov/UFO/page/details", self.by_url)


class TestNaraWalker(unittest.TestCase):
    def test_walk_extracts_records(self):
        sample = {
            "body": {"hits": {"hits": [
                {"_source": {"record": {
                    "naId": 12345,
                    "title": "UAP incident report 1967",
                    "digitalObjects": [{"objectUrl": "https://catalog.archives.gov/x.pdf"}],
                }}},
                {"_source": {"record": {"naId": "67890", "title": "Project Blue Book card"}}},
            ]}}
        }
        found = []
        _walk_json(sample, found)
        titles = {f.get("title") for f in found}
        self.assertIn("UAP incident report 1967", titles)
        self.assertIn("Project Blue Book card", titles)


if __name__ == "__main__":
    unittest.main(verbosity=2)
