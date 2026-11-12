import io
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import List, Dict, Any

from PIL import Image, ImageDraw, ImageFont, ImageOps
from functions.visual_artifacts import file_sha256


def _safe_slide_text(value: Any) -> str:
    """Replace decorative glyphs and unsupported punctuation before Pillow draws text."""
    text = str(value or "")
    mojibake = {
        "â€™": "'", "â€˜": "'", "â€œ": '"', "â€�": '"',
        "â€“": "-", "â€”": "-", "â€¦": "...",
    }
    for broken, replacement in mojibake.items():
        text = text.replace(broken, replacement)
    replacements = str.maketrans({
        "→": " to ", "➜": " to ", "←": " from ", "↔": " both ways ",
        "—": "-", "–": "-", "−": "-", "’": "'", "‘": "'",
        "“": '"', "”": '"', "…": "...", "•": "-", "×": " x ",
        "÷": "/", "≤": "<=", "≥": ">=", "≠": "!=", "±": "+/-",
    })
    text = unicodedata.normalize("NFKC", text).translate(replacements)
    cleaned = []
    allowed_punctuation = set(" _.,!?;:'\"()-+/=#%<>[]{}$&@\\|~^*`:")
    for char in text:
        category = unicodedata.category(char)
        if char.isascii() or category[0] in {"L", "N"} or char in allowed_punctuation:
            cleaned.append(char)
        elif char.isspace():
            cleaned.append(" ")
        else:
            cleaned.append(" ")
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()

# Target HD slide resolution & visual styling constants
SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720

# Category theme colors for slide canvas rendering
CATEGORY_THEMES = {
    "INTRO_OVERVIEW": {
        "bg": (15, 23, 42),          # Deep slate navy
        "card_bg": (30, 41, 59),     # Dark slate card
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (56, 189, 248),    # Sky blue accent
        "badge_bg": (30, 58, 138),
        "code_bg": (15, 23, 42),
    },
    "KEY_CONCEPTS": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (129, 140, 248),   # Indigo accent
        "badge_bg": (49, 46, 129),
        "code_bg": (15, 23, 42),
    },
    "ARCHITECTURE_STRUCTURE": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (45, 212, 191),    # Teal accent
        "badge_bg": (19, 78, 74),
        "code_bg": (15, 23, 42),
    },
    "WORKFLOW_PROCESS": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (251, 146, 60),    # Orange accent
        "badge_bg": (124, 45, 18),
        "code_bg": (15, 23, 42),
    },
    "PRACTICAL_EXAMPLE": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (74, 222, 128),    # Emerald green accent
        "badge_bg": (20, 83, 45),
        "code_bg": (15, 23, 42),
    },
    "BENEFITS_COMPARISON": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (244, 114, 182),   # Pink accent
        "badge_bg": (131, 24, 67),
        "code_bg": (15, 23, 42),
    },
    "SUMMARY_CONCLUSION": {
        "bg": (15, 23, 42),
        "card_bg": (30, 41, 59),
        "text_white": (248, 250, 252),
        "text_muted": (148, 163, 184),
        "accent": (52, 211, 153),    # Mint green accent
        "badge_bg": (6, 78, 59),
        "code_bg": (15, 23, 42),
    }
}


class SlideCanvasRenderer:
    """
    Renders high-definition, professional 1280x720 educational slides
    with dark-mode cards, clean bullet points, code syntax boxes, and category branding.
    """

    def __init__(self):
        self._load_fonts()

    def _load_fonts(self):
        font_names = ["arial.ttf", "segoeui.ttf", "dejavusans.ttf"]
        code_font_names = ["consola.ttf", "cour.ttf", "dejavusansmono.ttf"]

        self.title_font = None
        for name in font_names:
            try:
                self.title_font = ImageFont.truetype(name, 34)
                self.body_font = ImageFont.truetype(name, 21)
                self.cat_font = ImageFont.truetype(name, 15)
                break
            except OSError:
                continue

        if not self.title_font:
            self.title_font = ImageFont.load_default()
            self.body_font = ImageFont.load_default()
            self.cat_font = ImageFont.load_default()

        self.code_font = None
        for name in code_font_names:
            try:
                self.code_font = ImageFont.truetype(name, 19)
                break
            except OSError:
                continue

        if not self.code_font:
            self.code_font = ImageFont.load_default()

    def render_slide(
        self,
        title: str,
        category: str,
        bullets: List[str],
        code_snippet: str = None,
        save_path: str = "slide.jpg",
        slide_number: int = 0,
        total_slides: int = 0,
        topic_name: str = "",
        visual_query: str = "",
        layout_type: str = "concept_map",
        diagram_nodes: List[str] = None,
        reference_image: str = None,
    ) -> str:
        title = _safe_slide_text(title)
        category = _safe_slide_text(category).replace(" ", "_")
        bullets = [_safe_slide_text(bullet) for bullet in (bullets or [])]
        visual_query = _safe_slide_text(visual_query)
        diagram_nodes = [_safe_slide_text(node) for node in (diagram_nodes or [])]
        topic_name = _safe_slide_text(topic_name)
        code_snippet = _safe_slide_text(code_snippet)
        theme = CATEGORY_THEMES.get(category, CATEGORY_THEMES["INTRO_OVERVIEW"])

        img = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), theme["bg"])
        draw = ImageDraw.Draw(img)

        # ── 0. Gradient Background Overlay ──
        # Subtle diagonal gradient from bg color to a lighter shade
        bg_r, bg_g, bg_b = theme["bg"]
        accent_r, accent_g, accent_b = theme["accent"]
        for y in range(SLIDE_HEIGHT):
            # Blend factor: 0 at top → 0.08 at bottom (very subtle)
            blend = (y / SLIDE_HEIGHT) * 0.08
            r = int(bg_r + (accent_r - bg_r) * blend)
            g = int(bg_g + (accent_g - bg_g) * blend)
            b = int(bg_b + (accent_b - bg_b) * blend)
            draw.line([(0, y), (SLIDE_WIDTH, y)], fill=(r, g, b))

        # ── 0b. Decorative Corner Accent Circles ──
        # Top-right large soft circle
        circle_color = (accent_r, accent_g, accent_b, 25)
        draw.ellipse([1100, -60, 1380, 220], fill=(*theme["accent"][:3],), outline=None)
        # Make it subtle by overdrawing with semi-transparent bg
        for i in range(3):
            offset = i * 2
            blend_r = int(bg_r * 0.85 + accent_r * 0.15)
            blend_g = int(bg_g * 0.85 + accent_g * 0.15)
            blend_b = int(bg_b * 0.85 + accent_b * 0.15)
            draw.ellipse([1100 + offset, -60 + offset, 1380 - offset, 220 - offset],
                         fill=(blend_r, blend_g, blend_b))

        # Bottom-left small accent circle
        blend_r2 = int(bg_r * 0.9 + accent_r * 0.1)
        blend_g2 = int(bg_g * 0.9 + accent_g * 0.1)
        blend_b2 = int(bg_b * 0.9 + accent_b * 0.1)
        draw.ellipse([-40, 550, 140, 730], fill=(blend_r2, blend_g2, blend_b2))

        # ── 1. Slide Main Title (Category badge removed for cleaner visuals) ──
        draw.text((60, 42), title, fill=theme["text_white"], font=self.title_font)

        # ── 1b. Accent Separator Line ──
        draw.line([(60, 88), (420, 88)], fill=theme["accent"], width=3)
        # Fading tail
        for i in range(80):
            fade = max(0, 255 - i * 3)
            r = int(theme["accent"][0] * fade / 255 + bg_r * (255 - fade) / 255)
            g = int(theme["accent"][1] * fade / 255 + bg_g * (255 - fade) / 255)
            b = int(theme["accent"][2] * fade / 255 + bg_b * (255 - fade) / 255)
            draw.line([(420 + i, 88), (420 + i, 90)], fill=(r, g, b))

        # ── 2. Content Layout Cards ──
        has_code = bool(code_snippet and str(code_snippet).strip() and str(code_snippet).strip().lower() != "null")
        has_right_panel = bool(has_code or reference_image or visual_query or diagram_nodes)
        has_visual_map = bool((visual_query or diagram_nodes) and not has_code and not reference_image)
        left_card_width = 640 if has_right_panel else 900
        # Card with subtle glow effect
        draw.rounded_rectangle([56, 101, 64 + left_card_width, 664], radius=16,
                               fill=theme["card_bg"], outline=None)
        draw.rounded_rectangle([60, 105, 60 + left_card_width, 660], radius=14,
                               fill=theme["card_bg"], outline=(51, 65, 85), width=1)

        # Category-specific bullet icon
        BULLET_SHAPES = {
            "INTRO_OVERVIEW": "circle",
            "KEY_CONCEPTS": "diamond",
            "ARCHITECTURE_STRUCTURE": "square",
            "WORKFLOW_PROCESS": "triangle",
            "PRACTICAL_EXAMPLE": "diamond",
            "BENEFITS_COMPARISON": "square",
            "SUMMARY_CONCLUSION": "circle",
        }
        bullet_shape = BULLET_SHAPES.get(category, "circle")

        # Render Bullet Points with word wrapping
        bullet_y = 145
        max_bullet_w = left_card_width - 80

        for b_idx, bullet in enumerate(bullets[:4]):  # Limit to max 4 bullet points per slide
            bullet_clean = re.sub(r'[*`_~]', '', str(bullet)).strip()
            if not bullet_clean:
                continue

            # Draw the bullet with geometry, avoiding font-dependent symbol glyphs.
            icon_x, icon_y = 92, bullet_y + 12
            if bullet_shape == "diamond":
                draw.polygon([(icon_x, icon_y - 6), (icon_x + 6, icon_y), (icon_x, icon_y + 6), (icon_x - 6, icon_y)], fill=theme["accent"])
            elif bullet_shape == "square":
                draw.rectangle((icon_x - 5, icon_y - 5, icon_x + 5, icon_y + 5), fill=theme["accent"])
            elif bullet_shape == "triangle":
                draw.polygon([(icon_x, icon_y - 6), (icon_x + 6, icon_y + 5), (icon_x - 6, icon_y + 5)], fill=theme["accent"])
            else:
                draw.ellipse((icon_x - 5, icon_y - 5, icon_x + 5, icon_y + 5), fill=theme["accent"])

            # Word wrap long bullet strings
            words = bullet_clean.split()
            lines, current_line = [], ""
            for word in words:
                test_str = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_str, font=self.body_font)
                if bbox[2] - bbox[0] > max_bullet_w:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_str
            if current_line:
                lines.append(current_line)

            for line in lines[:3]:  # Max 3 wrapped lines per bullet
                draw.text((115, bullet_y), line, fill=theme["text_white"], font=self.body_font)
                bullet_y += 32
            bullet_y += 20

        # ── 3. Structured Diagram (Right Column, upper slot y=105..415) ──
        if has_visual_map:
            panel = (730, 105, 1220, 415)
            draw.rounded_rectangle(panel, radius=14, fill=theme["card_bg"], outline=(51, 65, 85), width=1)
            draw.text((750, 118), layout_type.replace("_", " ").upper(), fill=theme["accent"], font=self.cat_font)
            labels = [str(label)[:36] for label in (diagram_nodes or [])[:4] if str(label).strip()]
            if not labels:
                ignored = {"educational", "diagram", "image", "photo", "illustration", "show", "about", "with", "from", "the", "and"}
                title_terms = {word.lower().strip(".,:;!?()[]") for word in title.split()}
                labels = [
                    word for word in re.findall(r"[A-Za-z0-9+#.-]+", visual_query)
                    if len(word) > 2 and word.lower() not in ignored and word.lower() not in title_terms
                ][:4]
            labels = labels or [title[:24], "Key idea", "Result"]

            def draw_node(box, label):
                draw.rounded_rectangle(box, radius=10, fill=theme["badge_bg"], outline=theme["accent"], width=2)
                lines = [label[i:i + 22] for i in range(0, len(label), 22)][:2]
                text_y = (box[1] + box[3]) / 2 - len(lines) * 9
                for line in lines:
                    bounds = draw.textbbox((0, 0), line, font=self.cat_font)
                    draw.text(((box[0] + box[2] - bounds[2] + bounds[0]) / 2, text_y), line,
                              fill=theme["text_white"], font=self.cat_font)
                    text_y += 18

            if layout_type == "flowchart":
                boxes = [(800, 148 + i * 64, 1150, 198 + i * 64) for i in range(min(len(labels), 4))]
                for previous, current in zip(boxes, boxes[1:]):
                    x = (previous[0] + previous[2]) // 2
                    draw.line((x, previous[3], x, current[1] - 4), fill=theme["accent"], width=2)
                    draw.polygon([(x - 5, current[1] - 8), (x + 5, current[1] - 8), (x, current[1] - 2)], fill=theme["accent"])
                for box, label in zip(boxes, labels):
                    draw_node(box, label)
            elif layout_type == "cycle":
                positions = [(840, 210), (1110, 210), (1110, 335), (840, 335)]
                positions = positions[:len(labels)]
                for start, end in zip(positions, positions[1:] + positions[:1]):
                    draw.line((start[0], start[1], end[0], end[1]), fill=theme["accent"], width=2)
                for (cx, cy), label in zip(positions, labels):
                    draw_node((cx - 65, cy - 25, cx + 65, cy + 25), label)
            else:
                center = (975, 275)
                satellites = [(840, 205), (1110, 205), (840, 345), (1110, 345)][:max(0, len(labels) - 1)]
                for position in satellites:
                    draw.line((*center, *position), fill=theme["accent"], width=2)
                draw_node((center[0] - 80, center[1] - 32, center[0] + 80, center[1] + 32), labels[0])
                for (cx, cy), label in zip(satellites, labels[1:]):
                    draw_node((cx - 65, cy - 25, cx + 65, cy + 25), label)

        # ── 3b. Reference Image / Photo Slot (Right Column, upper slot y=105..415) ──
        if reference_image:
            try:
                with Image.open(reference_image) as source:
                    source = ImageOps.fit(source.convert("RGB"), (490, 310))
                    mask = Image.new("L", source.size, 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 489, 309), radius=14, fill=255)
                    img.paste(source, (730, 105), mask)
            except (OSError, ValueError):
                pass

        # ── 4. Code Block Card (Right Column, upper slot y=105..415) ──
        if has_code:
            right_x = 730
            draw.rounded_rectangle([right_x, 105, 1220, 415], radius=14,
                                   fill=theme["card_bg"], outline=(51, 65, 85), width=1)

            # Code Header Badge
            code_badge_text = "CODE EXAMPLE"
            draw.rounded_rectangle([right_x + 20, 118, right_x + 160, 144], radius=4,
                                   fill=theme["badge_bg"], outline=theme["accent"], width=1)
            draw.text((right_x + 28, 123), code_badge_text, fill=theme["accent"], font=self.cat_font)

            # Monospace Code Container Box
            draw.rounded_rectangle([right_x + 20, 154, 1200, 400], radius=8,
                                   fill=theme["code_bg"], outline=(30, 41, 59), width=1)

            # Line numbers + Code Text
            code_lines = str(code_snippet).strip().split("\n")
            code_y = 168
            for line_num, line in enumerate(code_lines[:7], 1):  # Limit to 7 lines
                # Line number in muted color
                draw.text((right_x + 28, code_y), str(line_num).rjust(2),
                          fill=theme["text_muted"], font=self.code_font)
                # Code text
                draw.text((right_x + 60, code_y), line[:42],
                          fill=(226, 232, 240), font=self.code_font)
                code_y += 30

        # ── 5. Presenter Video Frame Slot (Bottom-Right, y=435..660, non-overlapping) ──
        draw.rounded_rectangle([965, 435, 1220, 660], radius=14,
                               fill=theme["card_bg"], outline=(51, 65, 85), width=1)

        # ── 5. Bottom Accent Branding Bar ──
        draw.rectangle([0, 696, SLIDE_WIDTH, SLIDE_HEIGHT], fill=theme["accent"])

        # ── 6. Progress Indicator (bottom-right) ──
        if total_slides > 0:
            progress_text = f"{slide_number} / {total_slides}"
            progress_bbox = draw.textbbox((0, 0), progress_text, font=self.cat_font)
            pw = progress_bbox[2] - progress_bbox[0]
            # Draw on the accent bar
            draw.text((SLIDE_WIDTH - pw - 30, 699), progress_text,
                      fill=theme["bg"], font=self.cat_font)

        # ── 7. Topic Footer Watermark ──
        if topic_name:
            footer_text = topic_name.upper()
            footer_bbox = draw.textbbox((0, 0), footer_text, font=self.cat_font)
            draw.text((30, 699), footer_text, fill=theme["bg"], font=self.cat_font)

        # Save slide image file
        img.save(save_path, "JPEG", quality=95)
        return save_path


def get_image(chunk_queries: List[Dict[str, Any]] | Dict[str, Dict[str, Any]], timestamp: str, topic_name: str = "", search_service=None) -> List[str]:
    """
    Retrieve a validated scene image when available, with a generated Pillow slide fallback.
    Produces 1280x720 JPEG slide images in <timestamp>/images/seg_X.jpg.
    """
    save_dir = os.path.join(timestamp, "images")
    os.makedirs(save_dir, exist_ok=True)

    if isinstance(chunk_queries, dict):
        entries = list(chunk_queries.values())
        for chunk_id, entry in zip(chunk_queries.keys(), entries):
            entry.setdefault("chunk_id", chunk_id)
    else:
        entries = chunk_queries

    renderer = SlideCanvasRenderer()
    all_images: List[str] = []
    visual_manifest: list[dict] = []
    total_slides = len(entries)
    if (search_service is None and any(entry.get("image_search_enabled", True) for entry in entries)
            and os.environ.get("IMAGE_SEARCH_ENABLED", "true").casefold() not in {"0", "false", "no"}):
        from functions.image_providers import ImageSearchService
        search_service = ImageSearchService()

    # ── Giphy provider for hybrid_gif scenes ──
    giphy_provider = None
    if any(entry.get("visual_type") == "hybrid_gif" for entry in entries):
        try:
            from functions.giphy_provider import GiphyProvider
            giphy_provider = GiphyProvider()
            print("  🎞️ Giphy provider initialized for hybrid_gif scenes")
        except Exception as giphy_err:
            print(f"  ⚠️ Giphy provider unavailable: {giphy_err}")

    # Extract topic_name from chunk_queries if not provided
    if not topic_name and entries:
        topic_name = entries[0].get("chunk_text", "")[:30] if entries[0].get("chunk_text") else ""

    print(f"\nGenerating {total_slides} dynamic 1280x720 slide(s)...")

    for idx, entry in enumerate(entries):
        chunk_id = entry["chunk_id"]
        category = entry.get("category", "INTRO_OVERVIEW")
        title = entry.get("title", "Tutorial Slide")
        bullets = entry.get("bullets", [])
        code_snippet = entry.get("code_snippet")
        visual_query = entry.get("visual_query") or f"{title} educational diagram"
        diagram_nodes = entry.get("diagram_nodes") or []
        layout_type = "flowchart" if category == "ARCHITECTURE_STRUCTURE" else entry.get("layout_type", "concept_map")

        file_path = os.path.join(save_dir, f"{chunk_id}.jpg")
        selected = None
        attribution = None
        search_data = {"query": visual_query, "candidate_count": 0, "attempt_count": 0,
                       "rejected": [], "source": None}
        search_started = time.monotonic()
        animated_media_path = None
        animated_media_type = None
        visual_type = entry.get("visual_type", "slide")

        # ── Giphy animated media retrieval for hybrid_gif scenes ──
        if visual_type == "hybrid_gif" and giphy_provider is not None:
            try:
                giphy_result = giphy_provider.find_best(visual_query)
                if giphy_result and giphy_result.local_path:
                    animated_media_path = giphy_result.local_path
                    animated_media_type = giphy_result.media_type
                    attribution = {
                        "provider": "giphy",
                        "search_query": visual_query,
                        "candidate_count": 1,
                        "page_url": giphy_result.gif_url,
                        "image_url": giphy_result.mp4_url or giphy_result.gif_url,
                        "creator": "GIPHY",
                        "license_id": "GIPHY User Terms",
                        "license_url": "https://giphy.com/terms",
                        "attribution": giphy_result.attribution,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "semantic_score": 1.0,
                        "quality_score": 1.0,
                    }
                    search_data.update(
                        query=visual_query,
                        candidate_count=1,
                        attempt_count=1,
                        source=attribution,
                    )
                    print(f"  🎞️ [{chunk_id}] Giphy animation: {giphy_result.title}")
                else:
                    print(f"  ⚠️ [{chunk_id}] No Giphy result; falling back to hybrid_image")
                    visual_type = "hybrid_image"  # graceful degradation
            except Exception as giphy_err:
                print(f"  ⚠️ [{chunk_id}] Giphy error: {giphy_err}; falling back to hybrid_image")
                visual_type = "hybrid_image"

        if search_service is not None and entry.get("image_search_enabled", True) and not animated_media_path:
            try:
                selected, attribution, query, attempts, rejected = search_service.find(
                    entry.get("chunk_text", ""), visual_query,
                    must_show=entry.get("must_show", ()),
                    must_not_show=entry.get("must_not_show", ()),
                )
                search_data.update(query=query, attempt_count=attempts, rejected=rejected,
                                   candidate_count=int(attribution.get("candidate_count", 1)) if selected and attribution else 0)
                if attribution:
                    search_data["source"] = attribution
            except Exception as error:
                search_data["rejected"].append(f"provider error: {error}")
        renderer.render_slide(
            title=title,
            category=category,
            bullets=bullets,
            code_snippet=code_snippet,
            save_path=file_path,
            slide_number=idx + 1,
            total_slides=total_slides,
            topic_name=topic_name,
            visual_query=visual_query,
            layout_type=layout_type,
            diagram_nodes=diagram_nodes,
            reference_image=str(selected) if selected else None,
        )

        scene_id = entry.get("scene_id")
        if scene_id is None:
            match = re.search(r"(\d+)$", str(chunk_id))
            scene_id = int(match.group(1)) if match else idx
        visual_manifest.append({
            "scene_id": int(scene_id),
            "scene_fingerprint": entry.get("scene_fingerprint"),
            "slide_sha256": file_sha256(file_path),
            "visual_type": visual_type,
            "media_type": "animated" if animated_media_path else "static",
            "animated_media_path": animated_media_path,
            "animated_media_type": animated_media_type,
            "visual_query": search_data["query"],
            "search_query_used": attribution.get("search_query") if attribution else None,
            "candidate_count": search_data["candidate_count"],
            "selected_image_path": file_path,
            "selected_image_source": attribution.get("provider") if (selected or animated_media_path) else "canvas",
            "similarity_score": attribution.get("semantic_score") if attribution else None,
            "quality_score": attribution.get("quality_score") if attribution else None,
            "required_feature_scores": attribution.get("required_feature_scores", {}) if attribution else {},
            "excluded_feature_scores": attribution.get("excluded_feature_scores", {}) if attribution else {},
            "source_url": attribution.get("page_url") if attribution else None,
            "asset_url": attribution.get("image_url") if attribution else None,
            "creator": attribution.get("creator") if attribution else None,
            "license_id": attribution.get("license_id") if attribution else None,
            "license_url": attribution.get("license_url") if attribution else None,
            "attribution": attribution.get("attribution") if attribution else None,
            "retrieved_at": attribution.get("retrieved_at") if attribution else None,
            "attempt_count": search_data["attempt_count"],
            "retrieval_latency_seconds": round(time.monotonic() - search_started, 3),
            "rejected_candidates": search_data["rejected"],
            "fallback_used": not bool(selected or animated_media_path),
            "fallback_reason": "; ".join(search_data["rejected"]) if not (selected or animated_media_path) and search_data["rejected"] else ("image_search_disabled_for_scene" if not (selected or animated_media_path) and not entry.get("image_search_enabled", True) else ("no_candidate_passed_validation" if not (selected or animated_media_path) else None)),
            "layout_type": layout_type,
            "diagram_nodes": diagram_nodes,
            "content_source": entry.get("content_source", "provided_slide_spec"),
            "image_search_used": bool(selected or animated_media_path),
        })

        print(f"  [OK] Saved slide [{chunk_id}]: {file_path}")
        all_images.append(file_path)

    with open(os.path.join(timestamp, "visual_manifest.json"), "w", encoding="utf-8") as manifest_file:
        json.dump(visual_manifest, manifest_file, indent=2)

    print(f"\n[OK] Total {len(all_images)} HD slides generated in {save_dir}")
    return all_images
