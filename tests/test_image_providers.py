"""Provider contract, asset acceptance, caching, and Pillow fallback checks."""
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from functions.image_providers import (
    Candidate, HttpProvider, ImageProviderConfig, ImageSearchService,
    PexelsProvider, PixabayProvider, RetryableProviderError, WikimediaCommonsProvider,
)


def png_bytes(size=(640, 360)):
    buffer = io.BytesIO()
    image = Image.new("RGB", size, "teal")
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], 32):
        draw.rectangle((x, 0, x + 15, size[1]), fill=(220, 80, 30))
    image.save(buffer, "PNG")
    return buffer.getvalue()


class Provider:
    def __init__(self, name, candidates=(), failures=()):
        self.name, self.candidates, self.failures = name, list(candidates), list(failures)
        self.queries = []

    def search(self, query, limit):
        self.queries.append((query, limit))
        if self.failures:
            raise self.failures.pop(0)
        return self.candidates

    def get(self, url, **kwargs):
        response = MagicMock()
        response.is_redirect = False
        response.headers = {"Content-Type": "image/png", "Content-Length": str(len(png_bytes()))}
        response.iter_content.return_value = [png_bytes()]
        return response


def candidate(provider="wikimedia_commons", **changes):
    values = dict(provider=provider, image_url="https://upload.wikimedia.org/example.png",
                  page_url="https://commons.wikimedia.org/wiki/File:Example", title="Example image",
                  creator="Ada", license_id="CC BY-SA 4.0",
                  license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                  attribution="Ada, CC BY-SA 4.0", width=640, height=360)
    values.update(changes)
    return Candidate(**values)


def config(tmp_path, providers=("wikimedia_commons", "pexels"), **changes):
    values = dict(providers=providers, max_attempts=2, min_semantic_score=0.2,
                  min_width=480, min_height=270, cache_dir=str(tmp_path),
                  max_download_bytes=1_000_000, min_request_interval_seconds=0)
    values.update(changes)
    return ImageProviderConfig(**values)


def test_scene_query_uses_both_goal_and_narration():
    query = ImageSearchService.build_query(
        "The chlorophyll absorbs blue light in the leaf.", "Show leaf photosynthesis"
    )
    assert "Show leaf photosynthesis" in query
    assert "chlorophyll absorbs blue light" in query


@pytest.mark.parametrize("constraints", ["plant", [None], [""], ["x" * 161], [str(i) for i in range(9)]])
def test_invalid_exclusions_are_rejected_before_provider_search(tmp_path, constraints):
    provider = Provider("wikimedia_commons", [candidate()])
    service = ImageSearchService(config(tmp_path), {provider.name: provider})
    with pytest.raises(ValueError):
        service.find("A scene about plants", "Show a plant", must_not_show=constraints)
    assert provider.queries == []


def test_commons_adapter_requests_image_license_and_attribution_metadata():
    response = MagicMock()
    response.json.return_value = {"query": {"pages": {"3": {
        "title": "File:Cell.png", "imageinfo": [{"thumburl": "https://upload.wikimedia.org/cell.png",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cell.png", "width": 900,
            "height": 500, "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
            "Artist": {"value": "<a>Ada</a>"}}}]}}}}
    adapter = WikimediaCommonsProvider({"min_request_interval_seconds": 0})
    adapter.get = MagicMock(return_value=response)
    results = adapter.search("cell division", 10)
    assert results[0].creator == "Ada"
    assert results[0].license_id == "CC BY 4.0"
    assert adapter.get.call_args.kwargs["params"]["iiprop"] == "url|size|extmetadata"


def test_pexels_adapter_uses_key_and_returns_photographer_attribution(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-key")
    response = MagicMock()
    response.json.return_value = {"photos": [{"url": "https://www.pexels.com/photo/123",
        "photographer": "Kai", "alt": "mountain range", "width": 1200, "height": 800,
        "src": {"large": "https://images.pexels.com/photo.jpg"}}]}
    adapter = PexelsProvider({"min_request_interval_seconds": 0})
    adapter.get = MagicMock(return_value=response)
    photo = adapter.search("mountain range", 5)[0]
    assert photo.creator == "Kai" and photo.attribution == "Photo by Kai on Pexels"
    assert adapter.get.call_args.kwargs["headers"]["Authorization"] == "test-key"


def test_pixabay_adapter_uses_key_and_returns_cdn_url_and_attribution(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-pixabay-key")
    response = MagicMock()
    response.json.return_value = {
        "hits": [{
            "id": 9999,
            "user": "Alice",
            "tags": "binary tree, computer science",
            "pageURL": "https://pixabay.com/photos/binary-tree-9999/",
            "previewURL": "https://cdn.pixabay.com/photo/2026/01/01/00/00/tree-9999_150.jpg",
            "imageWidth": 1920,
            "imageHeight": 1080,
        }]
    }
    adapter = PixabayProvider({"min_request_interval_seconds": 0})
    adapter.get = MagicMock(return_value=response)
    results = adapter.search("binary tree", 5)
    assert len(results) == 1
    hit = results[0]
    assert hit.provider == "pixabay"
    assert hit.creator == "Alice"
    assert hit.attribution == "Photo by Alice on Pixabay"
    assert hit.license_id == "Pixabay License"
    assert hit.license_url == "https://pixabay.com/service/license-summary/"
    assert hit.image_url == "https://cdn.pixabay.com/photo/2026/01/01/00/00/tree-9999_1280.jpg"
    assert hit.page_url == "https://pixabay.com/photos/binary-tree-9999/"
    assert adapter.get.call_args.kwargs["params"]["key"] == "test-pixabay-key"


def test_pixabay_adapter_missing_key_returns_empty(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    adapter = PixabayProvider({"min_request_interval_seconds": 0})
    adapter.get = MagicMock()
    results = adapter.search("binary tree", 5)
    assert results == []
    adapter.get.assert_not_called()


def test_pixabay_top_priority_over_wikimedia(tmp_path):
    pixabay_photo = candidate(
        "pixabay",
        license_id="Pixabay License",
        page_url="https://pixabay.com/photos/tree-123/",
        license_url="https://pixabay.com/service/license-summary/",
        image_url="https://cdn.pixabay.com/photo/tree_1280.jpg",
        creator="Alice",
        attribution="Photo by Alice on Pixabay",
    )
    pixabay = Provider("pixabay", [pixabay_photo])
    commons = Provider("wikimedia_commons", [candidate("wikimedia_commons")])
    service = ImageSearchService(
        config(tmp_path, providers=("pixabay", "wikimedia_commons")),
        {pixabay.name: pixabay, commons.name: commons},
        ranker=lambda query, paths: [(path, 0.85) for path in paths],
    )
    image, metadata, query, attempts, rejected = service.find(
        "A detailed explanation of binary tree", "Show a binary tree diagram"
    )
    assert Path(image).is_file()
    assert metadata["provider"] == "pixabay"
    assert metadata["semantic_score"] == 0.85
    # Pixabay was queried and accepted
    assert len(pixabay.queries) == 1
    # Wikimedia was NOT queried because Pixabay succeeded on first priority!
    assert len(commons.queries) == 0


def test_commons_first_and_pexels_fallback_are_replaceable_and_cache_accepted(tmp_path):
    commons = Provider("wikimedia_commons", [candidate(license_id="Unknown")])
    pexels_photo = candidate("pexels", license_id="Pexels License",
                              page_url="https://www.pexels.com/photo/123",
                              license_url="https://www.pexels.com/license/",
                              image_url="https://images.pexels.com/landscape.png")
    pexels = Provider("pexels", [pexels_photo])
    service = ImageSearchService(config(tmp_path), {commons.name: commons, pexels.name: pexels},
                                 ranker=lambda query, paths: [(path, 0.8) for path in paths])
    image, metadata, query, attempts, rejected = service.find(
        "A detailed explanation about rock formations", "Show a geological cross section"
    )
    assert Path(image).is_file()
    assert metadata["provider"] == "pexels" and metadata["semantic_score"] == 0.8
    assert commons.queries[0][0] == query and len(pexels.queries) == 1
    assert attempts == 3 and rejected
    cached = service.find("A detailed explanation about rock formations", "Show a geological cross section")
    assert cached[0] == image and len(commons.queries) == 2 and len(pexels.queries) == 1
    assert json.loads(Path(image).with_suffix(".json").read_text())["attribution"] == "Ada, CC BY-SA 4.0"


def test_accepted_image_cache_is_invalidated_when_relevance_policy_changes(tmp_path):
    commons = Provider("wikimedia_commons", [candidate()])
    settings = config(tmp_path, providers=("wikimedia_commons",))
    service = ImageSearchService(settings, {commons.name: commons},
                                 ranker=lambda query, paths: [(path, 0.8) for path in paths])
    first = service.find("A narration about plant cells", "Show a plant cell")
    assert first[0] is not None

    settings.min_semantic_score = 0.9
    second = service.find("A narration about plant cells", "Show a plant cell")
    assert second[0] is None
    assert any("semantic score below threshold" in reason for reason in second[4])
    assert len(commons.queries) == 3
    assert commons.queries[-1][0] != commons.queries[-2][0]


def test_accepted_image_cache_revalidates_license_metadata(tmp_path):
    commons = Provider("wikimedia_commons", [candidate()])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",)),
                                 {commons.name: commons},
                                 ranker=lambda query, paths: [(path, 0.8) for path in paths])
    first = service.find("A narration about leaf anatomy", "Show a leaf")
    cached_image, cached_metadata = service._accepted_paths(first[2])
    record = json.loads(cached_metadata.read_text(encoding="utf-8"))
    record["attribution"] = None
    cached_metadata.write_text(json.dumps(record), encoding="utf-8")

    refreshed = service.find("A narration about leaf anatomy", "Show a leaf")
    assert refreshed[0] == cached_image
    assert len(commons.queries) == 2
    assert json.loads(cached_metadata.read_text(encoding="utf-8"))["attribution"]


@pytest.mark.parametrize("license_id,creator,attribution", [
    (None, "Ada", "Credit Ada"), ("All Rights Reserved", "Ada", "Credit Ada"),
    ("CC BY 4.0", None, "Credit author"), ("CC BY 4.0", "Ada", None),
])
def test_incompatible_or_incomplete_license_metadata_is_rejected(tmp_path, license_id, creator, attribution):
    commons = Provider("wikimedia_commons", [candidate(license_id=license_id,
                                creator=creator, attribution=attribution)])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",)),
                                 {commons.name: commons}, ranker=lambda *_: pytest.fail("must not rank ineligible source"))
    image, metadata, _, _, rejected = service.find("A scientific scene description", "Show a microscope")
    assert image is None and metadata is None and rejected


def test_low_semantic_score_rejects_keyword_match_and_does_not_cache(tmp_path):
    commons = Provider("wikimedia_commons", [candidate()])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",)),
                                 {commons.name: commons}, ranker=lambda q, paths: [(p, 0.01) for p in paths])
    result = service.find("Microscope narration mentions a cell", "A cell division diagram")
    assert result[0] is None and "semantic score below threshold" in result[4][0]
    assert service._cached(result[2], "accepted") is None


def test_missing_semantic_evaluator_fails_closed(tmp_path):
    commons = Provider("wikimedia_commons", [candidate()])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",)),
                                 {commons.name: commons})
    service.ranker = lambda *args: (_ for _ in ()).throw(RuntimeError("model unavailable"))
    assert service.find("A narration about a cell", "Cell under microscope")[0] is None


def test_provider_candidate_rejects_untrusted_attribution_page_host(tmp_path):
    commons = Provider("wikimedia_commons", [candidate(page_url="https://attacker.example/photo")])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",)),
                                 {commons.name: commons},
                                 ranker=lambda *_: pytest.fail("untrusted source page must not be ranked"))
    result = service.find("A narration about a cell", "Cell under microscope")
    assert result[0] is None
    assert any("license/attribution" in reason for reason in result[4])


def test_429_retry_after_is_recorded_and_bounded(tmp_path, monkeypatch):
    provider = Provider("wikimedia_commons", failures=[RetryableProviderError("429", 1.5), RetryableProviderError("429", 1.5)])
    service = ImageSearchService(config(tmp_path, providers=("wikimedia_commons",), max_attempts=2),
                                 {provider.name: provider}, ranker=lambda *_: [])
    sleeps = []
    monkeypatch.setattr("functions.image_providers.time.sleep", sleeps.append)
    result = service.find("A narration about anatomy", "anatomical diagram")
    assert result[0] is None and len(provider.queries) == 2
    assert sleeps == [1.5]


def test_http_provider_obeys_numeric_retry_after(monkeypatch):
    response = MagicMock(status_code=429, headers={"Retry-After": "3"})
    response.is_redirect = False
    session = MagicMock()
    session.get.return_value = response
    provider = HttpProvider({}, session)
    sleeps = []
    monkeypatch.setattr("functions.image_providers.time.sleep", sleeps.append)
    with pytest.raises(RetryableProviderError) as error:
        provider.get("https://provider.example/search")
    assert error.value.retry_after == 3
    assert provider.cooldown_until > 0


def test_http_provider_skips_requests_during_long_retry_after_without_blocking(monkeypatch):
    response = MagicMock(status_code=429, headers={"Retry-After": "3600"})
    response.is_redirect = False
    session = MagicMock()
    session.get.return_value = response
    provider = HttpProvider({"min_request_interval_seconds": 0}, session)
    sleeps = []
    monkeypatch.setattr("functions.image_providers.time.sleep", sleeps.append)

    with pytest.raises(RetryableProviderError) as first:
        provider.get("https://long-cooldown.example/search")
    other_session = MagicMock()
    other_provider = HttpProvider({"min_request_interval_seconds": 0}, other_session)
    with pytest.raises(RetryableProviderError, match="cooling down") as second:
        other_provider.get("https://long-cooldown.example/search")

    assert first.value.retry_after == 3600
    assert second.value.retry_after > 0
    assert session.get.call_count == 1
    other_session.get.assert_not_called()
    assert sleeps == []


def test_http_provider_interval_is_shared_across_service_instances(monkeypatch):
    sleeps = []
    monkeypatch.setattr("functions.image_providers.time.sleep", sleeps.append)
    first_session, second_session = MagicMock(), MagicMock()
    first_session.get.return_value = MagicMock(status_code=200)
    second_session.get.return_value = MagicMock(status_code=200)
    first = HttpProvider({"min_request_interval_seconds": 3}, first_session)
    second = HttpProvider({"min_request_interval_seconds": 0}, second_session)

    first.get("https://shared-instance-limit.example/search")
    second.get("https://shared-instance-limit.example/search")

    assert len(sleeps) == 1 and 2.9 <= sleeps[0] <= 3
    first_session.get.assert_called_once()
    second_session.get.assert_called_once()


def test_get_image_uses_accepted_photo_and_keeps_metadata(tmp_path, monkeypatch):
    from functions import get_image_function as image_module

    selected = tmp_path / "accepted.jpg"
    Image.new("RGB", (640, 360), "orange").save(selected)
    metadata = dict(provider="wikimedia_commons", page_url="https://commons.wikimedia.org/photo",
        image_url="https://upload.wikimedia.org/photo.jpg", creator="Ada", license_id="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/", attribution="Ada CC BY 4.0",
        retrieved_at="2026-01-01T00:00:00Z", semantic_score=0.77)
    service = MagicMock()
    service.find.return_value = selected, metadata, "scene query", 1, []
    captured = {}
    def fake_render(self, **kwargs):
        captured.update(kwargs)
        return Path(kwargs["save_path"]).write_bytes(b"slide")
    monkeypatch.setattr(image_module.SlideCanvasRenderer, "render_slide", fake_render)
    image_module.get_image([{"chunk_id": "seg_0", "scene_id": 0,
        "chunk_text": "The narration describes a scientific cell.", "visual_query": "Cell under microscope"}],
        str(tmp_path), search_service=service)
    manifest = json.loads((tmp_path / "visual_manifest.json").read_text())
    assert manifest[0]["image_search_used"] is True
    assert manifest[0]["license_id"] == "CC BY 4.0"
    assert manifest[0]["similarity_score"] == 0.77
    assert captured["reference_image"] == str(selected)


def test_get_image_falls_back_to_pillow_when_service_fails(tmp_path, monkeypatch):
    from functions import get_image_function as image_module

    service = MagicMock()
    service.find.side_effect = RuntimeError("offline")
    monkeypatch.setattr(image_module.SlideCanvasRenderer, "render_slide", lambda self, **kwargs: Path(kwargs["save_path"]).write_bytes(b"pillow"))
    image_module.get_image([{"chunk_id": "seg_0", "chunk_text": "lesson narration",
                             "visual_query": "educational image"}], str(tmp_path), search_service=service)
    manifest = json.loads((tmp_path / "visual_manifest.json").read_text())
    assert manifest[0]["selected_image_source"] == "canvas"
    assert manifest[0]["fallback_used"] is True
    assert "provider error" in manifest[0]["fallback_reason"]
    assert (tmp_path / "images/seg_0.jpg").is_file()


def test_get_image_skips_provider_for_pillow_routed_scene_and_records_fingerprint(tmp_path, monkeypatch):
    from functions import get_image_function as image_module

    fingerprint = "f" * 64
    service = MagicMock()
    monkeypatch.setattr(
        image_module.SlideCanvasRenderer, "render_slide",
        lambda self, **kwargs: Path(kwargs["save_path"]).write_bytes(b"pillow scene slide"),
    )
    image_module.get_image([{
        "chunk_id": "seg_0", "scene_id": 0, "scene_fingerprint": fingerprint,
        "chunk_text": "The narration describes plant cells.",
        "visual_query": "Plant cell diagram", "image_search_enabled": False,
    }], str(tmp_path), search_service=service)

    record = json.loads((tmp_path / "visual_manifest.json").read_text())[0]
    service.find.assert_not_called()
    assert record["scene_fingerprint"] == fingerprint
    assert len(record["slide_sha256"]) == 64
    assert record["fallback_reason"] == "image_search_disabled_for_scene"


def test_provider_order_and_attempts_can_be_configured_from_environment(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDERS", "pexels,wikimedia_commons")
    monkeypatch.setenv("IMAGE_QUERY_ATTEMPTS", "9")
    monkeypatch.setenv("IMAGE_CANDIDATE_LIMIT", "100")
    configured = ImageProviderConfig.from_env()
    assert configured.providers == ("pexels", "wikimedia_commons")
    assert configured.max_attempts == 3 and configured.candidate_limit == 20


def test_invalid_provider_configuration_fails_early(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDERS", "unsafe_provider")
    with pytest.raises(ValueError, match="unsupported provider"):
        ImageProviderConfig.from_env()


@pytest.mark.parametrize("settings, message", [
    ({"providers": ("wikimedia_commons", "wikimedia_commons")}, "unique supported providers"),
    ({"min_semantic_score": 1.1}, "thresholds must be between 0 and 1"),
    ({"max_attempts": 4}, "within bounded limits"),
    ({"min_request_interval_seconds": float("nan")}, "finite nonnegative number"),
])
def test_provider_configuration_rejects_unsafe_direct_values(settings, message):
    with pytest.raises(ValueError, match=message):
        ImageProviderConfig(**settings)


def test_video_manifest_receives_selected_image_license_source(tmp_path, monkeypatch):
    from functions import create_image_videos_function as slides
    from functions import manim_renderer
    from functions import visual_routing
    from functions.storyboard_schema import Scene, Storyboard
    from functions.visual_artifacts import file_sha256, visual_scene_fingerprint

    attribution = {"scene_id": 0, "source_url": "https://commons.wikimedia.org/file",
        "asset_url": "https://upload.wikimedia.org/photo.jpg", "creator": "Ada",
        "license_id": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Ada CC BY 4.0", "retrieved_at": "2026-01-01T00:00:00Z",
        "selected_image_source": "wikimedia_commons", "image_search_used": True}
    image_path = tmp_path / "images" / "seg_0.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"scene photo slide")
    scene = Scene(
        scene_id=0, key_concept="Plant cell structure",
        narration="A plant cell contains structures that perform specialized functions.",
        visual_query="A plant cell viewed through a microscope", on_screen_text="Plant cell",
        estimated_seconds=8, visual_type="web_image",
    )
    attribution["scene_fingerprint"] = visual_scene_fingerprint(scene)
    attribution["selected_image_path"] = str(image_path)
    attribution["slide_sha256"] = file_sha256(image_path)
    (tmp_path / "visual_manifest.json").write_text(json.dumps([attribution]))
    storyboard = Storyboard(title="Plant cell", scenes=[scene])
    monkeypatch.setattr(visual_routing, "route_storyboard", lambda _storyboard: None)
    monkeypatch.setattr(slides, "create_image_videos", lambda run_dir, **kwargs:
        ((Path(run_dir) / "image_videos").mkdir(exist_ok=True),
         (Path(run_dir) / "image_videos" / "seg_0.mp4").write_bytes(b"clip")))
    media = __import__("functions.visual_artifacts", fromlist=["MediaInfo"]).MediaInfo(
        duration_seconds=1, width=1280, height=720, fps=25, codec="h264", pixel_format="yuv420p")
    monkeypatch.setattr(manim_renderer, "probe_visual_video", lambda path: media)
    manim_renderer.render_all_visual_scenes(str(tmp_path), storyboard)
    from functions.visual_artifacts import load_visual_manifest
    artifact = load_visual_manifest(tmp_path).scenes[0]
    assert artifact.actual_strategy == "web_image"
    assert artifact.source.creator == "Ada" and artifact.source.license_id == "CC BY 4.0"
