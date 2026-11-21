"""
Video Tutorial Generator - Functions Package
Categorized into domain-specific subpackages:
  - audio: TTS and speech generation
  - image: Slide rendering, diagram generation, image providers & ranking
  - video: Video rendering (Manim), video clip generation, avatar sync, video combining
  - script: Script generation, storyboard planning, schema, LLM providers
  - visual: Visual specs, routing, artifacts, acceptance testing
  - pipeline: Orchestration, caching, DAG evaluator, checkpointing
"""
import sys
import importlib

# Subpackage exports
from functions import audio, image, video, script, visual, pipeline

# Module backward-compatibility mapping
_LEGACY_MODULES = [
    ("create_speech_function", "functions.audio.create_speech_function"),
    ("get_image_function", "functions.image.get_image_function"),
    ("image_providers", "functions.image.image_providers"),
    ("semantic_visual_matcher", "functions.image.semantic_visual_matcher"),
    ("generate_queries_function", "functions.image.generate_queries_function"),
    ("manim_renderer", "functions.video.manim_renderer"),
    ("manim_worker", "functions.video.manim_worker"),
    ("create_image_videos_function", "functions.video.create_image_videos_function"),
    ("create_video_from_audio_function", "functions.video.create_video_from_audio_function"),
    ("combine_videos_function", "functions.video.combine_videos_function"),
    ("langgraph_pipeline", "functions.script.langgraph_pipeline"),
    ("create_script_function", "functions.script.create_script_function"),
    ("create_storyboard_function", "functions.script.create_storyboard_function"),
    ("storyboard_schema", "functions.script.storyboard_schema"),
    ("llm_providers", "functions.script.llm_providers"),
    ("cerebras_client", "functions.script.cerebras_client"),
    ("visual_routing", "functions.visual.visual_routing"),
    ("visual_spec", "functions.visual.visual_spec"),
    ("visual_artifacts", "functions.visual.visual_artifacts"),
    ("visual_acceptance", "functions.visual.visual_acceptance"),
    ("visual_pipeline_graph", "functions.visual.visual_pipeline_graph"),
    ("video_main_function", "functions.pipeline.video_main_function"),
    ("create_audio_image_function", "functions.pipeline.create_audio_image_function"),
    ("dag_evaluator", "functions.pipeline.dag_evaluator"),
    ("checkpoint_manager", "functions.pipeline.checkpoint_manager"),
    ("cache_utils", "functions.pipeline.cache_utils"),
]

for _name, _target in _LEGACY_MODULES:
    try:
        _mod = importlib.import_module(_target)
        sys.modules[f"functions.{_name}"] = _mod
        globals()[_name] = _mod
    except Exception:
        pass
