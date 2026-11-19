"""Deterministic, per-scene visual strategy selection."""

import os
import re
from dataclasses import dataclass
from typing import Literal


VisualStrategy = Literal["manim", "web_image", "pillow", "hybrid_image", "hybrid_gif"]

SUPPORTED_ANIMATIONS = {"bfs", "dfs", "binary_search", "linear_search"}
ALGORITHM_CUES = re.compile(
    r"\b(?:bfs|breadth[ -]first(?: search)?|dfs|depth[ -]first(?: search)?|"
    r"binary search|linear search|breadth[ -]first traversal|depth[ -]first traversal|"
    r"sorting algorithms?|sorting|graph traversal|tree traversal)\b",
    re.IGNORECASE,
)
REAL_WORLD_CUES = re.compile(
    r"\b(?:photosynthesis|cell(?:s| division)?|organism|ecosystem|plant|animal|"
    r"human body|heart|lung|brain|bacteria|microbe|mountain|ocean|river|volcano|"
    r"planet|moon|solar system|weather|cloud|rock formation|fossil|microscope)\b",
    re.IGNORECASE,
)
PHYSICAL_TECH_CUES = re.compile(
    r"\b(?:virtual reality|vr|augmented reality|ar|mixed reality|mr|xr|headset|"
    r"oculus|hmd|hololens|robot(?:ics|ic)?|drone|uav|autonomous vehicle|"
    r"self[- ]driving|sensor|lidar|camera|display|hardware|gpu|server rack|"
    r"quantum comput(?:er|ing)|circuit|microcontroller|arduino|raspberry pi|"
    r"wearable|controller|3d tracking|spatial audio|optics|holograph(?:y|ic)|"
    r"3d print(?:er|ing)|iot|internet of things|smart (?:home|device|watch)|"
    r"fpga|chip|semiconductor|radar)\b",
    re.IGNORECASE,
)
MOTION_ANIMATION_CUES = re.compile(
    r"\b(?:movement|immersion|tracking|interaction|gameplay|simulation|"
    r"rotating|navigating|walking|demonstration|wearing|gestures|locomotion|"
    r"haptic|hand[- ]tracking|eye[- ]tracking|motion capture|flying|"
    r"teleoperation|assembly|manufacturing|swarming)\b",
    re.IGNORECASE,
)
TECHNICAL_DIAGRAM_CUES = re.compile(
    r"\b(?:architecture|pipeline|diagram|knowledge graph|graph|database|"
    r"schema|triples?|rdf|sparql|system design|data model|api|network|protocol|"
    r"cloud|framework|microservices?|ontology|entity)\b",
    re.IGNORECASE,
)
KNOWN_REQUESTS = {"slide", "pillow", "manim", "web_image", "hybrid_image", "hybrid_gif"}


@dataclass(frozen=True)
class VisualRoute:
    strategy: VisualStrategy
    rationale: str


def _value(scene, name, default=None):
    if isinstance(scene, dict):
        return scene.get(name, default)
    return getattr(scene, name, default)


def _enabled(name, default=True):
    return os.environ.get(name, str(default)).strip().casefold() not in {"0", "false", "no", "off"}


def route_scene(scene, capabilities=None) -> VisualRoute:
    """Choose one primary strategy from lesson intent and declared capabilities."""
    capabilities = capabilities or {}
    requested = str(_value(scene, "visual_type", "slide") or "slide").strip().casefold()[:80]
    narration = str(_value(scene, "narration", "") or "")
    concept = str(_value(scene, "key_concept", "") or "")
    objective = str(_value(scene, "learning_objective", "") or "")
    query = str(_value(scene, "visual_query", "") or "")
    headline = str(_value(scene, "on_screen_text", "") or "")
    lesson_text = " ".join((objective, concept, narration, query, headline))
    spec = _value(scene, "manim_spec")
    topic_type = str((spec or {}).get("topic_type", "")).strip().casefold()[:80] if isinstance(spec, dict) else ""
    has_algorithm_intent = bool(ALGORITHM_CUES.search(lesson_text))
    has_real_world_subject = bool(REAL_WORLD_CUES.search(lesson_text))
    has_physical_tech = bool(PHYSICAL_TECH_CUES.search(lesson_text))
    has_technical_diagram = bool(TECHNICAL_DIAGRAM_CUES.search(lesson_text))
    has_motion_cues = bool(MOTION_ANIMATION_CUES.search(lesson_text))
    manim_available = capabilities.get("manim", _enabled("MANIM_ENABLED"))
    web_images_available = capabilities.get("web_image", _enabled("IMAGE_SEARCH_ENABLED"))
    giphy_available = capabilities.get("giphy", _enabled("GIPHY_ENABLED", default=bool(os.environ.get("giphy", ""))))

    if requested not in KNOWN_REQUESTS:
        return VisualRoute("pillow", f"Unrecognized requested strategy '{requested}'; using Pillow.")

    if has_algorithm_intent and requested == "manim":
        if not isinstance(spec, dict) or not topic_type:
            return VisualRoute("pillow", "Algorithm animation has no valid specification; using Pillow.")
        if topic_type not in SUPPORTED_ANIMATIONS:
            if web_images_available:
                return VisualRoute("hybrid_image", f"Unsupported animation '{topic_type}'; using a hybrid slide with architectural diagram.")
            return VisualRoute("pillow", f"Unsupported animation '{topic_type}'; using Pillow.")
        if not manim_available:
            return VisualRoute("pillow", "Manim is disabled; using Pillow.")
        return VisualRoute("manim", f"{topic_type} animation supports the scene's algorithm walkthrough.")

    # A valid algorithm spec may upgrade a generic storyboard slide to animation.
    if has_algorithm_intent and isinstance(spec, dict) and topic_type in SUPPORTED_ANIMATIONS:
        if manim_available:
            return VisualRoute("manim", f"{topic_type} animation supports the scene's algorithm walkthrough.")
        return VisualRoute("pillow", "Manim is disabled; using a Pillow explanation slide.")

    if has_real_world_subject and web_images_available:
        return VisualRoute("web_image", "A real-world subject benefits from a relevant educational image.")

    if requested == "web_image" and not web_images_available:
        return VisualRoute("pillow", "Web image retrieval is disabled; using Pillow.")
    if requested == "manim":
        if topic_type and topic_type not in SUPPORTED_ANIMATIONS:
            if web_images_available:
                return VisualRoute("hybrid_image", f"Unsupported animation '{topic_type}'; using a hybrid slide with architectural diagram.")
            return VisualRoute("pillow", f"Unsupported animation '{topic_type}'; using Pillow.")
        if web_images_available:
            return VisualRoute("hybrid_image", "The scene is explanatory rather than algorithmic; using a hybrid slide with architectural diagram.")
        return VisualRoute("pillow", "The scene is explanatory rather than algorithmic; animation is not needed.")
    if requested == "web_image" and not has_real_world_subject:
        return VisualRoute("pillow", "No clear real-world image subject was identified; using Pillow.")

    # ── Hybrid visual routing for physical/tech topics ──
    if requested in {"hybrid_gif", "hybrid_image"}:
        # Respect explicit hybrid requests from the storyboard LLM
        if requested == "hybrid_gif" and giphy_available:
            return VisualRoute("hybrid_gif", "Storyboard requested animated hybrid visual for this tech scene.")
        if web_images_available:
            return VisualRoute("hybrid_image", "Storyboard requested hybrid image visual for this tech scene.")
        return VisualRoute("pillow", "Hybrid visual requested but image retrieval is disabled; using Pillow.")

    if has_physical_tech and has_motion_cues and giphy_available:
        return VisualRoute("hybrid_gif", "Physical technology scene with motion cues benefits from an animated GIF overlay.")
    if has_physical_tech and web_images_available:
        return VisualRoute("hybrid_image", "Physical technology scene benefits from a contextual photo overlay on the slide.")
    if has_technical_diagram and web_images_available:
        return VisualRoute("hybrid_image", "Technical architecture scene benefits from a relevant diagram on the slide.")

    return VisualRoute("pillow", "A readable Pillow slide is the best fit for this scene.")


def route_storyboard(storyboard, capabilities=None):
    """Apply routing to every scene; a router error degrades only that scene."""
    for scene in getattr(storyboard, "scenes", []) or []:
        try:
            route = route_scene(scene, capabilities)
        except Exception:
            route = VisualRoute("pillow", "Visual routing failed; using the safe Pillow fallback.")
        if isinstance(scene, dict):
            scene["visual_type"] = route.strategy
            scene["visual_rationale"] = route.rationale
        else:
            scene.visual_type = route.strategy
            scene.visual_rationale = route.rationale
    return storyboard
