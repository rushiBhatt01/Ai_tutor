"""CPU-only CLIP utilities for selecting the most relevant scene image."""

from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

_MODEL_NAME = "openai/clip-vit-base-patch32"
_device = "cpu"
_model: CLIPModel | None = None
_processor: CLIPProcessor | None = None


def _load_model() -> tuple[CLIPModel, CLIPProcessor]:
    """Load CLIP once on CPU, leaving GPU memory available for Wav2Lip."""
    global _model, _processor
    if _model is None or _processor is None:
        _processor = CLIPProcessor.from_pretrained(_MODEL_NAME)
        _model = CLIPModel.from_pretrained(_MODEL_NAME).to(_device)
        _model.eval()
    return _model, _processor


def rank_images(query: str, image_paths: list[str]) -> list[tuple[str, float]]:
    """Return readable images ordered by CLIP text-image cosine similarity."""
    valid_paths: list[str] = []
    images: list[Image.Image] = []
    for image_path in image_paths:
        try:
            with Image.open(image_path) as image:
                images.append(image.convert("RGB"))
            valid_paths.append(image_path)
        except (OSError, ValueError):
            continue

    if not valid_paths:
        return []

    model, processor = _load_model()
    inputs = processor(text=[query], images=images, return_tensors="pt", padding=True)
    inputs = {name: value.to(_device) for name, value in inputs.items()}
    with torch.inference_mode():
        text_features = model.get_text_features(**{
            name: value for name, value in inputs.items() if name in {"input_ids", "attention_mask"}
        })
        image_features = model.get_image_features(**{
            name: value for name, value in inputs.items() if name == "pixel_values"
        })
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        scores = (image_features @ text_features.T).squeeze(1).cpu().tolist()

    return sorted(zip(valid_paths, (float(score) for score in scores)), key=lambda item: item[1], reverse=True)
