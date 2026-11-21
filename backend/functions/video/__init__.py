"""Video generation, Manim rendering, avatar lip-sync, and clip stitching."""
from functions.video.combine_videos_function import combine_videos
from functions.video.create_image_videos_function import create_image_videos
from functions.video.create_video_from_audio_function import create_video_from_audio
from functions.video import manim_worker
from functions.video.manim_renderer import (
    render_scene_manim,
    render_all_visual_scenes,
    generate_dynamic_manim_code,
)

__all__ = [
    "combine_videos",
    "create_image_videos",
    "create_video_from_audio",
    "manim_worker",
    "render_scene_manim",
    "render_all_visual_scenes",
    "generate_dynamic_manim_code",
]
