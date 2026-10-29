"""
Pydantic v2 contracts for AI Lesson Storyboard planning.

Scene  – one pedagogical unit (narration + visual intent + timing).
Storyboard – validated ordered collection of scenes with contiguous IDs.

Used by create_storyboard_function.py to parse and validate LLM output
before it enters the audio/video pipeline.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List


class Scene(BaseModel):
    """A single pedagogical scene in a video tutorial storyboard."""

    scene_id: int = Field(
        ge=0,
        description="Sequential 0-indexed scene ID. Must be contiguous across the storyboard."
    )
    key_concept: str = Field(
        min_length=2,
        max_length=160,
        description="Core educational takeaway for this scene."
    )
    narration: str = Field(
        min_length=20,
        max_length=1200,
        description="Spoken narration text for Edge-TTS synthesis."
    )
    visual_query: str = Field(
        min_length=3,
        max_length=180,
        description="Visual description for image search and CLIP reranking."
    )
    on_screen_text: str = Field(
        max_length=120,
        description="Brief slide headline or subtitle displayed on-screen."
    )
    estimated_seconds: int = Field(
        ge=3,
        le=90,
        description="Estimated spoken duration in seconds."
    )


class Storyboard(BaseModel):
    """Validated ordered collection of scenes for a video tutorial."""

    title: str = Field(
        min_length=2,
        max_length=120,
        description="Tutorial title."
    )
    scenes: List[Scene] = Field(
        min_length=1,
        max_length=12,
        description="Ordered list of scenes (1–12)."
    )

    @model_validator(mode="after")
    def verify_contiguous_scene_ids(self):
        """Ensure scene_id values are strictly sequential starting from 0."""
        for idx, scene in enumerate(self.scenes):
            if scene.scene_id != idx:
                raise ValueError(
                    f"scene_id must be contiguous starting from 0, "
                    f"found {scene.scene_id} at index {idx}"
                )
        return self
