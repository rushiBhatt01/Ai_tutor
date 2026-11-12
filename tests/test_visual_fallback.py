from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from functions import create_image_videos_function as slides
from functions import manim_renderer as renderer


def test_failed_conversion_does_not_accept_preexisting_video(tmp_path, monkeypatch):
    (tmp_path / "images").mkdir()
    (tmp_path / "audio").mkdir()
    (tmp_path / "image_videos").mkdir()
    (tmp_path / "images/seg_0.jpg").write_bytes(b"image")
    (tmp_path / "audio/seg_0.wav").write_bytes(b"audio")
    previous_video = tmp_path / "image_videos/seg_0.mp4"
    previous_video.write_bytes(b"stale video from an earlier run")

    fake_input = MagicMock()
    fake_input.filter.return_value = fake_input
    fake_ffmpeg = MagicMock()
    fake_ffmpeg.input.return_value = fake_input
    fake_ffmpeg.output.return_value.run.side_effect = RuntimeError("encoder failed")
    monkeypatch.setattr(slides, "ffmpeg", fake_ffmpeg)

    with pytest.raises(RuntimeError, match="seg_0"):
        slides.create_image_videos(str(tmp_path), chunk_ids=["seg_0"])

    assert previous_video.read_bytes() == b"stale video from an earlier run"
    fake_ffmpeg.output.return_value.run.assert_called_once_with(
        overwrite_output=True, quiet=False, timeout=30,
    )


def test_manim_fallback_keeps_canvas_dimensions_when_fonts_are_unavailable(tmp_path, monkeypatch):
    from PIL import Image

    def missing_font(*args, **kwargs):
        raise OSError("font unavailable")

    monkeypatch.setattr(renderer.ImageFont, "truetype", missing_font)
    output = tmp_path / "fallback.jpg"
    renderer.create_manim_fallback_slide(
        "A long lesson title that needs to wrap safely when custom fonts are missing",
        ["A detailed explanation that still fits within the fallback slide row."],
        str(output),
    )

    with Image.open(output) as image:
        assert image.size == (1280, 720)
