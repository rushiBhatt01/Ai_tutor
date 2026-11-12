"""Giphy API provider for animated GIF/MP4 retrieval in hybrid visual scenes.

Fetches short looping animations from Giphy's search endpoint, preferring
the ``fixed_height`` MP4 rendition (faster FFmpeg decode) with GIF fallback.
Results are cached locally per query to avoid redundant API calls.

This provider is intentionally separate from the static-image
``ImageSearchService`` since it returns video/animation assets, not photos.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class GiphyResult:
    """A single Giphy search result with download metadata."""
    gif_id: str
    title: str
    mp4_url: Optional[str]
    gif_url: str
    width: int
    height: int
    local_path: Optional[str] = None
    media_type: str = "mp4"  # "mp4" or "gif"
    attribution: str = "Powered By GIPHY"


_SAFE_FILENAME = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize_query(raw_query: str) -> str:
    """Extract 1-3 core subject keywords, strip prompt artifacts and noise, limit to 50 chars."""
    from functions.visual_routing import PHYSICAL_TECH_CUES

    # First attempt: check for physical tech cues in the query (e.g. VR headset, robotics)
    matches = PHYSICAL_TECH_CUES.findall(raw_query)
    if matches:
        unique_matches = []
        for m in matches:
            if m.lower() not in [u.lower() for u in unique_matches]:
                unique_matches.append(m)
        if unique_matches:
            return " ".join(unique_matches[:3])[:50]

    words = re.sub(r"[^a-zA-Z0-9\s]", " ", raw_query).split()
    # Remove stop-words and visual prompt meta-words that hurt Giphy tag matching
    stop = {
        "the", "a", "an", "of", "in", "for", "and", "or", "is", "to", "with", "on", "at", "by",
        "this", "that", "it", "its", "how", "what", "why", "are", "was", "from", "as", "be",
        "illustration", "graphic", "diagram", "slide", "showing", "represented", "representing",
        "demonstrating", "view", "picture", "image", "concept", "embedded", "arrows", "indicating",
        "think", "like", "step", "part", "side", "person", "scene", "overview", "split", "screen",
        "digital", "simulated", "around", "about", "into", "over", "under", "through",
    }
    keywords = [w for w in words if w.lower() not in stop][:3]
    query = " ".join(keywords)
    return query[:50] if query else raw_query[:50]


class GiphyProvider:
    """Search Giphy for looping animated visuals suitable for tech-topic overlays."""

    ENDPOINT = "https://api.giphy.com/v1/gifs/search"

    def __init__(self, api_key: str | None = None, cache_dir: str | None = None):
        self.api_key = api_key or os.environ.get("giphy", "")
        if not self.api_key:
            raise ValueError("Giphy API key not configured. Set 'giphy' in environment.")
        self.cache_dir = Path(cache_dir) if cache_dir else Path(os.environ.get(
            "GIPHY_CACHE_DIR", os.path.join("cache", "giphy")))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 3) -> list[GiphyResult]:
        """Search Giphy API and return structured results with MP4/GIF URLs.

        Args:
            query: Raw visual query from the storyboard scene.
            limit: Maximum number of results (1-10).

        Returns:
            List of GiphyResult dataclass instances.
        """
        clean_query = _sanitize_query(query)
        limit = max(1, min(limit, 10))

        try:
            resp = requests.get(
                self.ENDPOINT,
                params={
                    "api_key": self.api_key,
                    "q": clean_query,
                    "limit": limit,
                    "rating": "g",
                    "lang": "en",
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  ⚠️ Giphy search failed: {exc}")
            return []

        data = resp.json().get("data", [])
        results = []
        for item in data:
            images = item.get("images", {})
            fixed = images.get("fixed_height", {})
            mp4_url = fixed.get("mp4") or images.get("original_mp4", {}).get("mp4")
            gif_url = fixed.get("url", "")
            try:
                width = int(fixed.get("width", 0))
                height = int(fixed.get("height", 0))
            except (TypeError, ValueError):
                width, height = 0, 0

            results.append(GiphyResult(
                gif_id=item.get("id", ""),
                title=item.get("title", ""),
                mp4_url=mp4_url,
                gif_url=gif_url,
                width=width,
                height=height,
                media_type="mp4" if mp4_url else "gif",
            ))

        print(f"  🎞️ Giphy returned {len(results)} result(s) for '{clean_query}'")
        return results

    def download(self, result: GiphyResult) -> Optional[str]:
        """Download the best rendition (MP4 preferred) and cache locally.

        Args:
            result: A GiphyResult from search().

        Returns:
            Local file path to cached MP4/GIF, or None on failure.
        """
        url = result.mp4_url or result.gif_url
        if not url:
            return None

        ext = "mp4" if result.mp4_url else "gif"
        safe_id = _SAFE_FILENAME.sub("_", result.gif_id)[:40]
        cache_key = hashlib.md5(url.encode()).hexdigest()[:10]
        filename = f"{safe_id}_{cache_key}.{ext}"
        local_path = self.cache_dir / filename

        if local_path.exists() and local_path.stat().st_size > 0:
            result.local_path = str(local_path)
            result.media_type = ext
            return str(local_path)

        try:
            resp = requests.get(url, timeout=15, stream=True)
            resp.raise_for_status()
            with open(local_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
            result.local_path = str(local_path)
            result.media_type = ext
            print(f"  ✅ Cached Giphy {ext.upper()}: {local_path.name} ({local_path.stat().st_size // 1024}KB)")
            return str(local_path)
        except Exception as exc:
            print(f"  ⚠️ Giphy download failed: {exc}")
            if local_path.exists():
                local_path.unlink(missing_ok=True)
            return None

    def find_best(self, query: str) -> Optional[GiphyResult]:
        """Convenience: search + download the top result in one call.

        Args:
            query: Visual query string.

        Returns:
            A GiphyResult with local_path populated, or None.
        """
        results = self.search(query, limit=3)
        for result in results:
            path = self.download(result)
            if path:
                return result
        return None

