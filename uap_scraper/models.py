"""Data model for a single scraped item."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class MediaItem:
    """One artifact discovered on a source: a video, image, audio clip,
    document, or a catalog record.
    """
    source: str                      # pursue | aaro | nasa | nara
    kind: str                        # video | image | audio | document | record | page
    url: str                         # absolute URL of the artifact
    title: str = ""                  # human-readable title / link text
    page_url: str = ""               # the page the artifact was found on
    release: str = ""                # release/batch label if known
    date: str = ""                   # event/publish date if known
    location: str = ""               # location if known
    description: str = ""            # caption / description
    assessment: str = ""             # official verdict (resolved/unresolved/...)
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        """Dedupe key."""
        return f"{self.source}|{self.kind}|{self.url}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
