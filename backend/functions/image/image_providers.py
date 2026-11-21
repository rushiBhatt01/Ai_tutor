"""Replaceable image search adapters, policy checks, and accepted-asset cache."""
import hashlib
import json
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import requests
from PIL import Image, ImageOps, ImageStat

from functions.visual.visual_artifacts import atomic_output


_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_STATE = {}


@dataclass
class Candidate:
    provider: str
    image_url: str
    page_url: str
    title: str
    creator: str | None
    license_id: str | None
    license_url: str | None
    attribution: str | None
    width: int
    height: int
    download_location: str | None = None


class ImageProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[Candidate]: ...


class RetryableProviderError(RuntimeError):
    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


def _retry_delay(response):
    raw = response.headers.get("Retry-After", "")
    try:
        return max(0.0, min(float(raw), 86400.0))
    except (TypeError, ValueError):
        try:
            until = parsedate_to_datetime(raw)
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            return max(0.0, min((until - datetime.now(timezone.utc)).total_seconds(), 86400.0))
        except (TypeError, ValueError, OverflowError):
            return 1.0


class HttpProvider:
    name = "abstract"

    def __init__(self, config: dict, session=None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = "AITutorVideoGenerator/2.0 (mailto:admin@aitutor.org; educational research)"
        self.last_request = 0.0
        self.cooldown_until = 0.0

    def get(self, url, **kwargs):
        headers = kwargs.get("headers") or {}
        authorization = headers.get("Authorization") or getattr(self, "access_key", None)
        if not authorization:
            authorization = self.session.headers.get("Authorization")
        if not isinstance(authorization, str) or not authorization:
            authorization = None
        credential_id = hashlib.sha256(str(authorization).encode()).hexdigest() if authorization else ""
        bucket = (self.name, urlparse(url).hostname or "", credential_id)
        spacing = max(0.0, float(self.config.get("min_request_interval_seconds", 1.0)))

        # Serialize requests in one quota bucket so separate service instances
        # cannot race through the same provider interval or a shared cooldown.
        with _RATE_LIMIT_LOCK:
            state = _RATE_LIMIT_STATE.setdefault(bucket, {
                "last_request": 0.0, "cooldown_until": 0.0, "min_interval": spacing,
            })
            state["min_interval"] = max(state["min_interval"], spacing)
            now = time.monotonic()
            cooldown_remaining = state["cooldown_until"] - now
            self.cooldown_until = state["cooldown_until"]
            if cooldown_remaining > 0:
                raise RetryableProviderError(
                    f"{self.name} is cooling down after rate limiting", cooldown_remaining,
                )
            remaining = max(0.0, state["min_interval"] - (now - state["last_request"]))
            if remaining > 0:
                time.sleep(remaining)
            state["last_request"] = time.monotonic()
            self.last_request = state["last_request"]
            response = self.session.get(url, timeout=(3.05, 12), **kwargs)
            if response.status_code == 429:
                delay = _retry_delay(response)
                state["cooldown_until"] = time.monotonic() + delay
                self.cooldown_until = state["cooldown_until"]
                raise RetryableProviderError(f"{self.name} rate limited the request", delay)
            response.raise_for_status()
            return response


class WikimediaCommonsProvider(HttpProvider):
    name = "wikimedia_commons"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def search(self, query, limit):
        stop_words = {"a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
                      "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
                      "illustration", "diagram", "showing"}
        words = [w for w in re.findall(r"[\w'-]+", str(query)) if w.casefold() not in stop_words]
        clean_query = " ".join(words[:5]) if words else str(query)
        response = self.get(self.config.get("endpoint", self.endpoint), params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"filetype:bitmap {clean_query}", "gsrnamespace": 6,
            "gsrlimit": min(limit, 20), "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "iiurlwidth": 1280,
        })
        pages = response.json().get("query", {}).get("pages", {}).values()
        output = []
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            def value(key):
                field = meta.get(key, {})
                return re.sub(r"<[^>]*>", "", str(field.get("value", ""))).strip() or None
            license_id, license_url = value("LicenseShortName"), value("LicenseUrl")
            if not info.get("thumburl") or not license_id or not license_url:
                continue
            creator = value("Artist")
            title = str(page.get("title", "")).removeprefix("File:")
            output.append(Candidate(self.name, info["thumburl"], info.get("descriptionurl", ""), title,
                                    creator, license_id, license_url,
                                    value("Attribution") or creator, int(info.get("width", 0)),
                                    int(info.get("height", 0))))
        return output


class PexelsProvider(HttpProvider):
    name = "pexels"
    endpoint = "https://api.pexels.com/v1/search"

    def search(self, query, limit):
        api_key = self.config.get("api_key") or os.environ.get(self.config.get("api_key_env", "PEXELS_API_KEY"))
        if not api_key:
            return []
        response = self.get(self.config.get("endpoint", self.endpoint),
                            headers={"Authorization": api_key},
                            params={"query": query, "per_page": min(limit, 20), "orientation": "landscape"})
        output = []
        for photo in response.json().get("photos", []):
            src = photo.get("src", {})
            image_url = src.get("large") or src.get("large2x")
            if not image_url:
                continue
            creator = photo.get("photographer")
            page_url = photo.get("url", "")
            output.append(Candidate(self.name, image_url, page_url, " ".join(filter(None, [photo.get("alt"), "photo"])),
                                    creator, "Pexels License", "https://www.pexels.com/license/",
                                    f"Photo by {creator} on Pexels" if creator else None,
                                    int(photo.get("width", 0)), int(photo.get("height", 0))))
        return output


class UnsplashProvider(HttpProvider):
    name = "unsplash"
    endpoint = "https://api.unsplash.com/search/photos"

    def __init__(self, config: dict, session=None):
        super().__init__(config, session)
        self.access_key = config.get("access_key") or os.environ.get(
            config.get("access_key_env", "UNSPLASH_ACCESS_KEY"))
        if self.access_key:
            self.session.headers["Authorization"] = f"Client-ID {self.access_key}"

    def search(self, query, limit):
        if not self.access_key:
            return []
        response = self.get(self.config.get("endpoint", self.endpoint), params={
            "query": query, "per_page": min(limit, 30), "orientation": "landscape",
            "content_filter": "high",
        })
        output = []
        for photo in response.json().get("results", []):
            urls, links, user = photo.get("urls", {}), photo.get("links", {}), photo.get("user", {})
            image_url = urls.get("regular")
            creator = user.get("name")
            page_url = links.get("html")
            download_location = links.get("download_location")
            if not image_url or not creator or not page_url or not download_location:
                continue
            # Unsplash photos are governed by the Unsplash License, not an open CC license.
            output.append(Candidate(self.name, image_url, page_url,
                photo.get("alt_description") or photo.get("description") or "Unsplash photo",
                creator, "Unsplash License", "https://unsplash.com/license",
                f"Photo by {creator} on Unsplash", int(photo.get("width", 0)),
                int(photo.get("height", 0)), download_location))
        return output


class PixabayProvider(HttpProvider):
    name = "pixabay"
    endpoint = "https://pixabay.com/api/"

    def __init__(self, config: dict, session=None):
        super().__init__(config, session)
        self.api_key = config.get("api_key") or os.environ.get(
            config.get("api_key_env", "PIXABAY_API_KEY")
        )

    def search(self, query: str, limit: int) -> list[Candidate]:
        if not self.api_key:
            return []
        # Pixabay API strictly restricts q to at most 100 characters
        clean_query = " ".join(query.split())
        if len(clean_query) > 100:
            parts = clean_query[:100].rsplit(" ", 1)
            clean_query = parts[0] if len(parts) > 1 and parts[0] else clean_query[:100]
        response = self.get(
            self.config.get("endpoint", self.endpoint),
            params={
                "key": self.api_key,
                "q": clean_query,
                "image_type": "photo",
                "per_page": min(max(limit, 3), 50),
                "safesearch": "true",
                "orientation": "horizontal",
            },
        )
        output = []
        for hit in response.json().get("hits", []):
            preview = hit.get("previewURL", "")
            image_url = None
            width = int(hit.get("imageWidth") or hit.get("webformatWidth") or 1280)
            height = int(hit.get("imageHeight") or hit.get("webformatHeight") or 720)
            if preview and "cdn.pixabay.com" in preview:
                if width >= 1280:
                    suffix = "_1280."
                elif width >= 960:
                    suffix = "_960_720."
                else:
                    suffix = "_640."
                image_url = re.sub(r"_(?:150|640)\.", suffix, preview)
            if not image_url:
                image_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if not image_url:
                continue

            creator = hit.get("user")
            page_url = hit.get("pageURL") or f"https://pixabay.com/photos/{hit.get('id', '')}/"
            title = hit.get("tags") or "Pixabay photo"
            attribution = f"Photo by {creator} on Pixabay" if creator else "Photo on Pixabay"

            output.append(Candidate(
                provider=self.name,
                image_url=image_url,
                page_url=page_url,
                title=title,
                creator=creator or "Pixabay Contributor",
                license_id="Pixabay License",
                license_url="https://pixabay.com/service/license-summary/",
                attribution=attribution,
                width=width,
                height=height,
            ))
        return output


@dataclass
class ImageProviderConfig:
    providers: tuple[str, ...] = ("pixabay", "wikimedia_commons", "unsplash")
    max_attempts: int = 2
    candidate_limit: int = 12
    min_semantic_score: float = 0.26
    min_required_feature_score: float = 0.20
    max_excluded_feature_score: float = 0.26
    min_width: int = 480
    min_height: int = 270
    max_download_bytes: int = 12_000_000
    min_quality_score: float = 0.035
    cache_dir: str = ""
    max_retry_after_seconds: int = 8
    semantic_evaluator_version: str = "clip-vit-base-patch32-v1"
    pixabay_endpoint: str = "https://pixabay.com/api/"
    commons_endpoint: str = "https://commons.wikimedia.org/w/api.php"
    pexels_endpoint: str = "https://api.pexels.com/v1/search"
    unsplash_endpoint: str = "https://api.unsplash.com/search/photos"
    min_request_interval_seconds: float = 1.0

    def __post_init__(self):
        self.providers = tuple(self.providers)
        supported = {"pixabay", "wikimedia_commons", "unsplash", "pexels"}
        if (not self.providers or len(set(self.providers)) != len(self.providers)
                or any(provider not in supported for provider in self.providers)):
            raise ValueError("Image provider list must contain unique supported providers")
        if not 1 <= self.max_attempts <= 3 or not 1 <= self.candidate_limit <= 20:
            raise ValueError("Image query attempts and candidate count must be within bounded limits")
        if (not math.isfinite(self.min_semantic_score)
                or not 0 <= self.min_semantic_score <= 1
                or not math.isfinite(self.min_required_feature_score)
                or not 0 <= self.min_required_feature_score <= 1
                or not math.isfinite(self.max_excluded_feature_score)
                or not 0 <= self.max_excluded_feature_score <= 1
                or not math.isfinite(self.min_quality_score)
                or not 0 <= self.min_quality_score <= 1):
            raise ValueError("Image semantic, feature, and quality thresholds must be between 0 and 1")
        if min(self.min_width, self.min_height, self.max_download_bytes) <= 0:
            raise ValueError("Image dimensions and download size limits must be positive")
        if not 0 <= self.max_retry_after_seconds <= 86400:
            raise ValueError("Retry-After limit must be between 0 and 86400 seconds")
        if (not math.isfinite(self.min_request_interval_seconds)
                or self.min_request_interval_seconds < 0):
            raise ValueError("Provider request interval must be a finite nonnegative number")
        if (not isinstance(self.semantic_evaluator_version, str)
                or not self.semantic_evaluator_version.strip()):
            raise ValueError("Semantic evaluator version must not be empty")

    @classmethod
    def from_env(cls):
        raw = os.environ.get("IMAGE_PROVIDERS", "pixabay,wikimedia_commons,unsplash")
        providers = tuple(x.strip() for x in raw.split(",") if x.strip())
        known = {"pixabay", "wikimedia_commons", "unsplash", "pexels"}
        if not providers or any(name not in known for name in providers):
            raise ValueError("IMAGE_PROVIDERS contains an unsupported provider")
        return cls(providers=providers,
                   max_attempts=max(1, min(int(os.environ.get("IMAGE_QUERY_ATTEMPTS", "2")), 3)),
                   candidate_limit=max(1, min(int(os.environ.get("IMAGE_CANDIDATE_LIMIT", "12")), 20)),
                   min_semantic_score=float(os.environ.get("IMAGE_MIN_SEMANTIC_SCORE", "0.26")),
                   min_required_feature_score=float(os.environ.get("IMAGE_MIN_REQUIRED_FEATURE_SCORE", "0.20")),
                   max_excluded_feature_score=float(os.environ.get("IMAGE_MAX_EXCLUDED_FEATURE_SCORE", "0.26")),
                   min_width=max(1, int(os.environ.get("IMAGE_MIN_WIDTH", "480"))),
                   min_height=max(1, int(os.environ.get("IMAGE_MIN_HEIGHT", "270"))),
                   min_quality_score=max(0.0, min(float(os.environ.get("IMAGE_MIN_QUALITY_SCORE", "0.035")), 1.0)),
                   max_retry_after_seconds=max(0, int(os.environ.get("IMAGE_MAX_RETRY_AFTER_SECONDS", "8"))),
                   semantic_evaluator_version=os.environ.get(
                       "IMAGE_SEMANTIC_EVALUATOR_VERSION", "clip-vit-base-patch32-v1"),
                   pixabay_endpoint=os.environ.get("PIXABAY_API_URL", "https://pixabay.com/api/"),
                   commons_endpoint=os.environ.get("WIKIMEDIA_API_URL", "https://commons.wikimedia.org/w/api.php"),
                   pexels_endpoint=os.environ.get("PEXELS_API_URL", "https://api.pexels.com/v1/search"),
                   unsplash_endpoint=os.environ.get("UNSPLASH_API_URL", "https://api.unsplash.com/search/photos"),
                   min_request_interval_seconds=max(0.0, float(os.environ.get("IMAGE_PROVIDER_INTERVAL_SECONDS", "1"))),
                   cache_dir=os.environ.get("IMAGE_CACHE_DIR", ""))


class ImageSearchService:
    def __init__(self, config=None, providers=None, ranker=None, feature_evaluator=None):
        self.config = config or ImageProviderConfig.from_env()
        provider_settings = {"min_request_interval_seconds": self.config.min_request_interval_seconds}
        self.providers = providers or {
            "pixabay": PixabayProvider({**provider_settings, "endpoint": self.config.pixabay_endpoint}),
            "wikimedia_commons": WikimediaCommonsProvider({**provider_settings, "endpoint": self.config.commons_endpoint}),
            "pexels": PexelsProvider({**provider_settings, "endpoint": self.config.pexels_endpoint}),
            "unsplash": UnsplashProvider({**provider_settings, "endpoint": self.config.unsplash_endpoint}),
        }
        self.ranker = ranker
        self.feature_evaluator = feature_evaluator

    META_PROMPT_WORDS = {
        "illustration", "illustrations", "depicting", "showing", "side", "comparison",
        "versus", "vs", "representation", "concept", "metaphor", "analogous", "analogy",
        "symbolic", "glowing", "hyper-realistic", "photorealistic", "image", "photo",
        "picture", "drawing", "diagram", "graphic", "render", "3d", "vector",
        "clipart", "wallpaper", "background", "style", "view", "labeled"
    }

    @staticmethod
    def _clean_keywords(text: str) -> list[str]:
        if not text:
            return []
        words = re.findall(r"[\w'-]+", str(text))
        stop_words = {"a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
                      "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "inside"}
        return [w for w in words if w.casefold() not in stop_words and w.casefold() not in ImageSearchService.META_PROMPT_WORDS and len(w) > 1]

    @staticmethod
    def build_query(narration, visual_goal, topic_name=None):
        goal_words = ImageSearchService._clean_keywords(visual_goal)
        topic_words = ImageSearchService._clean_keywords(topic_name) if topic_name else []
        combined = []
        for w in topic_words[:3]:
            if w.casefold() not in [x.casefold() for x in combined]:
                combined.append(w)
        for w in goal_words:
            if w.casefold() not in [x.casefold() for x in combined]:
                combined.append(w)
            if len(combined) >= 5:
                break
        if combined:
            return " ".join(combined[:5])
        narration_words = ImageSearchService._clean_keywords(narration)
        fallback = (topic_words[:2] + narration_words)[:5]
        return " ".join(fallback) if fallback else (str(topic_name or narration or "technology")[:30])

    @staticmethod
    def refine_query(narration, visual_goal, must_show=None, topic_name=None):
        stop_words = {"a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
                      "is", "it", "of", "on", "or", "that", "the", "this", "to", "with"}
        required = ImageSearchService._normalize_features(must_show)
        content_words = [word for word in re.findall(r"[\w'-]+", narration)
                         if word.casefold() not in stop_words and word.casefold() not in ImageSearchService.META_PROMPT_WORDS]
        focus = required or content_words[:5]
        refined = ImageSearchService.build_query(" ".join(focus), visual_goal, topic_name=topic_name)
        base = ImageSearchService.build_query(narration, visual_goal, topic_name=topic_name)
        if refined.casefold() == base.casefold():
            refined = f"{refined} hardware photo" if topic_name else f"{refined} educational photograph"
        return refined

    def _cache_paths(self, query, provider, constraints_key=""):
        root = Path(self.config.cache_dir or os.path.join(os.path.dirname(__file__), "..", "..", "cache", "images")).resolve()
        policy = {
            "cache_schema": 3,
            "providers": self.config.providers,
            "semantic_threshold": self.config.min_semantic_score,
            "required_feature_threshold": self.config.min_required_feature_score,
            "excluded_feature_threshold": self.config.max_excluded_feature_score,
            "quality_threshold": self.config.min_quality_score,
            "minimum_dimensions": [self.config.min_width, self.config.min_height],
            "semantic_evaluator": self.config.semantic_evaluator_version,
        }
        policy_key = json.dumps(policy, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(
            f"v3\0{provider}\0{query.casefold()}\0{constraints_key}\0{policy_key}".encode()
        ).hexdigest()
        image = root / f"{key}.jpg"
        return image, image.with_suffix(".json")

    @staticmethod
    def _normalize_features(features):
        if features is None:
            return []
        if not isinstance(features, (list, tuple)):
            raise ValueError("Visual features must be a list of strings")
        if len(features) > 8:
            raise ValueError("At most eight visual features are supported per constraint list")
        normalized = []
        for feature in features:
            if not isinstance(feature, str) or not feature.strip() or len(feature.strip()) > 160:
                raise ValueError("Visual features must contain 1 to 160 characters")
            value = " ".join(feature.split())
            if value.casefold() not in {item.casefold() for item in normalized}:
                normalized.append(value)
        return normalized

    def _validated_constraints(self, must_show=None, must_not_show=None):
        required = self._normalize_features(must_show)
        excluded = self._normalize_features(must_not_show)
        if {feature.casefold() for feature in required} & {feature.casefold() for feature in excluded}:
            raise ValueError("Required and excluded visual features conflict")
        return required, excluded

    @staticmethod
    def _constraints_key(must_show, must_not_show):
        return json.dumps({"must_show": must_show, "must_not_show": must_not_show},
                          sort_keys=True, separators=(",", ":"))

    def _feature_scores_pass(self, record, must_show, must_not_show):
        if record.get("visual_constraints") != {"must_show": must_show, "must_not_show": must_not_show}:
            return False
        required = record.get("required_feature_scores") or {}
        excluded = record.get("excluded_feature_scores") or {}
        return (
            all(isinstance(required.get(feature), (int, float))
                and math.isfinite(required[feature])
                and required[feature] >= self.config.min_required_feature_score
                for feature in must_show)
            and all(isinstance(excluded.get(feature), (int, float))
                    and math.isfinite(excluded[feature])
                    and excluded[feature] < self.config.max_excluded_feature_score
                    for feature in must_not_show)
        )

    def _accepted_paths(self, query, must_show=None, must_not_show=None):
        required, excluded = self._validated_constraints(must_show, must_not_show)
        return self._cache_paths(query, "accepted", self._constraints_key(required, excluded))

    def _cached(self, query, provider, must_show=None, must_not_show=None):
        required_features, excluded_features = self._validated_constraints(must_show, must_not_show)
        constraints_key = self._constraints_key(required_features, excluded_features)
        image, meta = self._cache_paths(query, provider, constraints_key)
        if not image.is_file() or not meta.is_file():
            return None
        try:
            record = json.loads(meta.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("Cached image metadata must be an object")
            with Image.open(image) as photo:
                photo.verify()
            with Image.open(image) as photo:
                if photo.width < self.config.min_width or photo.height < self.config.min_height:
                    raise ValueError("Cached image dimensions are below the current policy")
            provider_name = record.get("provider")
            candidate = Candidate(
                provider=provider_name,
                image_url=record.get("image_url"), page_url=record.get("page_url"),
                title=record.get("title") or "", creator=record.get("creator"),
                license_id=record.get("license_id"), license_url=record.get("license_url"),
                attribution=record.get("attribution"), width=int(record.get("width", 0)),
                height=int(record.get("height", 0)),
                download_location=record.get("download_location"),
            )
            image_url, page_url = urlparse(candidate.image_url or ""), urlparse(candidate.page_url or "")
            semantic_score = float(record.get("semantic_score"))
            quality_score = float(record.get("quality_score"))
            if (record.get("query") != query or provider_name not in self.config.providers
                    or image_url.scheme != "https" or page_url.scheme != "https"
                    or not self._host_allowed(provider_name, image_url.hostname or "")
                    or not self._page_host_allowed(provider_name, page_url.hostname or "")
                    or not self._license_allowed(candidate)
                    or candidate.width < self.config.min_width or candidate.height < self.config.min_height
                    or not math.isfinite(semantic_score)
                    or semantic_score < self.config.min_semantic_score
                    or not math.isfinite(quality_score)
                    or quality_score < self.config.min_quality_score
                    or not self._feature_scores_pass(record, required_features, excluded_features)
                    or record.get("asset_sha256") != hashlib.sha256(image.read_bytes()).hexdigest()):
                raise ValueError("Cached image metadata no longer passes the current acceptance policy")
            return image, record
        except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError):
            image.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
            return None

    @staticmethod
    def _license_allowed(candidate):
        if not candidate.creator or not candidate.attribution:
            return False
        name = (candidate.license_id or "").casefold().replace(" ", "-")
        url = (candidate.license_url or "").casefold()
        if name == "pexels-license":
            return url.rstrip("/") == "https://www.pexels.com/license"
        if name == "unsplash-license":
            return url.rstrip("/") == "https://unsplash.com/license"
        if name in {"pixabay-license", "pixabay-content-license"}:
            return "pixabay.com" in url
        if name.startswith("cc-by-sa"):
            return "creativecommons.org/licenses/by-sa/" in url
        if name.startswith("cc-by"):
            return "creativecommons.org/licenses/by/" in url
        if name.startswith("cc0"):
            return "creativecommons.org/publicdomain/zero/" in url
        if "public-domain" in name:
            return "creativecommons.org/publicdomain/" in url or "wikimedia.org" in url
        return False

    @staticmethod
    def _host_allowed(provider, hostname):
        return (
            (provider == "wikimedia_commons" and hostname.endswith(".wikimedia.org"))
            or (provider == "pexels" and hostname.endswith(".pexels.com"))
            or (provider == "unsplash" and hostname == "images.unsplash.com")
            or (provider == "pixabay" and (hostname.endswith(".pixabay.com") or hostname == "pixabay.com"))
        )

    @staticmethod
    def _page_host_allowed(provider, hostname):
        return (
            (provider == "wikimedia_commons" and hostname.endswith(".wikimedia.org"))
            or (provider == "pexels" and hostname.endswith(".pexels.com"))
            or (provider == "unsplash" and (hostname == "unsplash.com" or hostname.endswith(".unsplash.com")))
            or (provider == "pixabay" and (hostname.endswith(".pixabay.com") or hostname == "pixabay.com"))
        )

    def _download(self, provider, candidate, query):
        parsed = urlparse(candidate.image_url)
        if parsed.scheme != "https" or not parsed.hostname:
            return None
        if not self._host_allowed(provider.name, parsed.hostname):
            return None
        response = provider.get(candidate.image_url, stream=True, allow_redirects=False)
        if response.is_redirect:
            location = urlparse(response.headers.get("Location", ""))
            host = location.hostname or ""
            same_provider = host == parsed.hostname or (
                parsed.hostname.endswith(".wikimedia.org") and host.endswith(".wikimedia.org")
            ) or (parsed.hostname.endswith(".pexels.com") and host.endswith(".pexels.com")) or (
                parsed.hostname.endswith(".pixabay.com") and host.endswith(".pixabay.com")
            )
            if location.scheme != "https" or not same_provider:
                return None
            response = provider.get(response.headers["Location"], stream=True, allow_redirects=False)
            if response.is_redirect:
                return None
        if not response.headers.get("Content-Type", "").lower().startswith("image/"):
            return None
        max_bytes = self.config.max_download_bytes
        if int(response.headers.get("Content-Length", "0") or 0) > max_bytes:
            return None
        candidate_key = hashlib.sha256(candidate.image_url.encode()).hexdigest()[:16]
        image_path, meta_path = self._cache_paths(query, f"{provider.name}-{candidate_key}")
        image_path.parent.mkdir(parents=True, exist_ok=True)
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > max_bytes:
                return None
        try:
            with Image.open(__import__("io").BytesIO(data)) as image:
                image.verify()
            with Image.open(__import__("io").BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                if image.width < self.config.min_width or image.height < self.config.min_height:
                    return None
                quality_score = round(min(ImageStat.Stat(image.convert("L")).stddev[0] / 128.0, 1.0), 4)
                if quality_score < self.config.min_quality_score:
                    return None
                image.thumbnail((1920, 1080))
                with atomic_output(image_path) as temporary:
                    image.save(temporary, "JPEG", quality=90)
        except (OSError, ValueError):
            return None
        record = {**asdict(candidate), "query": query, "semantic_score": None,
                  "quality_score": quality_score,
                  "retrieved_at": datetime.now(timezone.utc).isoformat()}
        with atomic_output(meta_path) as temporary:
            Path(temporary).write_text(json.dumps(record, indent=2), encoding="utf-8")
        return image_path, record

    def find(self, narration, visual_goal, must_show=None, must_not_show=None, topic_name=None):
        query = self.build_query(narration, visual_goal, topic_name=topic_name)
        must_show, must_not_show = self._validated_constraints(must_show, must_not_show)
        visual_constraints = {"must_show": must_show, "must_not_show": must_not_show}
        attempts, rejected = 0, []
        refined_query = self.refine_query(narration, visual_goal, must_show, topic_name=topic_name)
        cached = self._cached(query, "accepted", must_show, must_not_show)
        if cached:
            return cached[0], cached[1], query, attempts, rejected
        for name in self.config.providers:
            provider = self.providers.get(name)
            if provider is None:
                continue
            refine_next = False
            for attempt in range(self.config.max_attempts):
                attempts += 1
                search_query = refined_query if refine_next else query
                try:
                    candidates = provider.search(search_query, self.config.candidate_limit)
                    local = []
                    for candidate in candidates:
                        page_url = urlparse(candidate.page_url or "")
                        if (page_url.scheme != "https"
                                or not self._page_host_allowed(name, page_url.hostname or "")
                                or not self._license_allowed(candidate)):
                            rejected.append(f"{name}: missing or incompatible license/attribution metadata")
                            continue
                        if candidate.width < self.config.min_width or candidate.height < self.config.min_height:
                            rejected.append(f"{name}: image dimensions below quality threshold")
                            continue
                        downloaded = self._download(provider, candidate, query)
                        if downloaded:
                            local.append(downloaded)
                    if not local:
                        rejected.append(f"{name}: no downloadable eligible candidates; refining within the attempt budget")
                        if attempt + 1 < self.config.max_attempts:
                            refine_next = True
                            continue
                        break
                    if self.ranker is None:
                        try:
                            from functions.image.semantic_visual_matcher import rank_images
                            ranked = rank_images
                        except Exception as error:
                            rejected.append(f"semantic evaluator unavailable: {error}")
                            break
                    else:
                        ranked = self.ranker
                    scores = ranked(query, [str(item[0]) for item in local])
                    score_map = dict(scores)
                    topic_anchor = f"{topic_name} technical educational photograph" if topic_name else None
                    topic_scores = dict(ranked(topic_anchor, [str(item[0]) for item in local])) if (topic_anchor and ranked) else {}
                    feature_map = {}
                    all_features = list(dict.fromkeys(must_show + must_not_show))
                    if all_features:
                        if self.feature_evaluator is None:
                            try:
                                from functions.image.semantic_visual_matcher import score_visual_features
                                feature_evaluator = score_visual_features
                            except Exception as error:
                                rejected.append(f"visual feature evaluator unavailable: {error}")
                                break
                        else:
                            feature_evaluator = self.feature_evaluator
                        try:
                            feature_map = feature_evaluator(
                                [str(item[0]) for item in local], all_features,
                            )
                        except Exception as error:
                            rejected.append(f"visual feature evaluator failed: {error}")
                            break
                    # Rank candidates by highest combined relevance score first
                    local.sort(
                        key=lambda item: (score_map.get(str(item[0]), 0.0) + topic_scores.get(str(item[0]), 0.0))
                        if topic_anchor else score_map.get(str(item[0]), 0.0),
                        reverse=True
                    )
                    min_topic = max(0.22, self.config.min_semantic_score - 0.04)
                    for path, record in local:
                        sem_score = score_map.get(str(path), 0.0)
                        top_score = topic_scores.get(str(path), 1.0) if topic_anchor else 1.0
                        record["semantic_score"] = sem_score
                        record["topic_score"] = top_score
                        record["search_query"] = search_query
                        scores_for_path = feature_map.get(str(path), {})
                        record["visual_constraints"] = visual_constraints
                        record["required_feature_scores"] = {
                            feature: scores_for_path.get(feature) for feature in must_show
                        }
                        record["excluded_feature_scores"] = {
                            feature: scores_for_path.get(feature) for feature in must_not_show
                        }
                        features_pass = self._feature_scores_pass(
                            record, must_show, must_not_show,
                        )
                        if sem_score >= self.config.min_semantic_score and (topic_anchor is None or top_score >= min_topic):
                            if not features_pass:
                                rejected.append(f"{name}: required or excluded visual feature check failed")
                                refine_next = True
                                continue
                            if name == "unsplash":
                                selected_provider = self.providers[name]
                                download_url = record.get("download_location")
                                parsed_download_url = urlparse(download_url or "")
                                if (parsed_download_url.scheme != "https"
                                        or parsed_download_url.hostname != "api.unsplash.com"):
                                    rejected.append("unsplash: missing required download tracking URL")
                                    continue
                                try:
                                    selected_provider.get(download_url)
                                except Exception as error:
                                    rejected.append(f"unsplash download tracking failed: {error}")
                                    continue
                            record["candidate_count"] = len(local)
                            record["asset_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                            accepted_image, meta_path = self._accepted_paths(
                                query, must_show, must_not_show,
                            )
                            with atomic_output(accepted_image) as temporary:
                                Path(temporary).write_bytes(Path(path).read_bytes())
                            with atomic_output(meta_path) as temporary:
                                Path(temporary).write_text(json.dumps(record, indent=2), encoding="utf-8")
                            return accepted_image, record, query, attempts, rejected
                        rejected.append(f"{name}: semantic or topic score below threshold (semantic={sem_score:.3f}, topic={top_score:.3f})")
                        refine_next = True
                        refine_next = True
                    if refine_next and attempt + 1 < self.config.max_attempts:
                        continue
                    break
                except RetryableProviderError as error:
                    rejected.append(str(error))
                    if attempt + 1 < self.config.max_attempts and error.retry_after <= self.config.max_retry_after_seconds:
                        time.sleep(error.retry_after)
                    else:
                        break
                except Exception as error:
                    rejected.append(f"{name}: {error}")
                    break
        return None, None, query, attempts, rejected
