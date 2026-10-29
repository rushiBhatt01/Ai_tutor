import io
import json
import html
import os
import re
import random
import unicodedata
from urllib.parse import quote_plus, urlparse
from typing import List, Dict, Any

import requests
from PIL import Image, ImageDraw, ImageFont


def rank_images(query: str, image_paths: list[str]) -> list[tuple[str, float]]:
    """Load the optional CLIP ranker only for explicit image-search use."""
    from functions.semantic_visual_matcher import rank_images as clip_rank_images

    return clip_rank_images(query, image_paths)


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

IMAGE_SEARCH_URL = "https://www.bing.com/images/search?q={}"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
COMMONS_USER_AGENT = "VideoTutorialGenerator/1.0 (scene image search)"
MAX_IMAGE_CANDIDATES = 20
DEFAULT_MIN_IMAGE_SIMILARITY = 0.16
SCRAPLING_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
)


def _letterbox_image(source_path: str, output_path: str, background_color=(15, 23, 42)) -> str:
    """Save an image as a non-distorted 1280x720 JPEG."""
    with Image.open(source_path) as source:
        image = source.convert("RGB")
        image.thumbnail((SLIDE_WIDTH, SLIDE_HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), background_color)
        canvas.paste(image, ((SLIDE_WIDTH - image.width) // 2, (SLIDE_HEIGHT - image.height) // 2))
        canvas.save(output_path, "JPEG", quality=95)
    return output_path


def _scrapling_image_urls(query: str, limit: int) -> list[str]:
    """Use Scrapling to fetch Bing Images results and extract direct image URLs."""
    from scrapling import Fetcher

    response = Fetcher.get(
        IMAGE_SEARCH_URL.format(quote_plus(query)),
        timeout=15,
        retries=1,
        stealthy_headers=True,
        headers={"User-Agent": random.choice(SCRAPLING_USER_AGENTS)},
    )
    if response.status < 200 or response.status >= 300:
        return []
    urls: list[str] = []
    for result in response.css("a.iusc"):
        try:
            metadata = json.loads(result.attrib.get("m", "{}"))
        except (TypeError, ValueError):
            continue
        image_url = metadata.get("murl", "")
        extension = os.path.splitext(urlparse(image_url).path)[1].lower()
        if urlparse(image_url).scheme == "https" and extension in {".jpg", ".jpeg", ".png", ".webp"} and image_url not in urls:
            urls.append(image_url)
        if len(urls) >= limit:
            break
    return urls


def _commons_image_candidates(query: str, limit: int) -> list[dict[str, str]]:
    """Search Wikimedia Commons and retain file pages and reuse attribution."""
    response = requests.get(
        COMMONS_API_URL,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(max(limit, 1), 50),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 1280,
            "iiextmetadatalanguage": "en",
            "iiextmetadatafilter": "Artist|Credit|LicenseShortName|LicenseUrl|AttributionRequired",
            "format": "json",
            "formatversion": 2,
        },
        headers={"User-Agent": COMMONS_USER_AGENT},
        timeout=(5, 15),
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    candidates = []
    for page in pages:
        image_info = (page.get("imageinfo") or [{}])[0]
        metadata = image_info.get("extmetadata", {})

        def metadata_value(name: str) -> str:
            value = str(metadata.get(name, {}).get("value", ""))
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip()

        image_url = image_info.get("thumburl") or image_info.get("url")
        if not image_url:
            continue
        candidates.append({
            "url": image_url,
            "title": page.get("title", ""),
            "source_page": image_info.get("descriptionurl", ""),
            "artist": metadata_value("Artist"),
            "credit": metadata_value("Credit"),
            "license": metadata_value("LicenseShortName"),
            "license_url": metadata_value("LicenseUrl"),
        })
    return candidates[:limit]


def retrieve_candidate_images(query: str, limit: int, temp_dir: str) -> list[str]:
    """Download Commons and Bing candidates into a scene-local temporary directory."""
    limit = max(1, min(limit, MAX_IMAGE_CANDIDATES))
    os.makedirs(temp_dir, exist_ok=True)
    paths: list[str] = []
    candidates: list[tuple[str, str, dict[str, str]]] = []

    # Search the no-key Commons catalog first, then supplement with broader Bing
    # results. Either provider can fail independently.
    commons_limit = min(10, max(1, limit // 2))
    try:
        candidates.extend(
            (item["url"], "wikimedia_commons", item)
            for item in _commons_image_candidates(query, commons_limit)
        )
    except Exception as error:
        print(f"  [WARN] Wikimedia Commons image search failed: {error}")

    remaining = limit - len(candidates)
    if remaining:
        try:
            candidates.extend(
                (url, "bing_images", {"url": url})
                for url in _scrapling_image_urls(query, remaining)
            )
        except Exception as error:
            print(f"  [WARN] Bing image search failed: {error}")

    seen_urls: set[str] = set()
    metadata_by_filename: dict[str, dict[str, str]] = {}
    for index, (url, source, candidate_metadata) in enumerate(candidates[:limit]):
        try:
            if urlparse(url).scheme != "https" or url in seen_urls:
                continue
            seen_urls.add(url)
            if source == "wikimedia_commons":
                response = requests.get(
                    url,
                    headers={"User-Agent": COMMONS_USER_AGENT},
                    timeout=(5, 15),
                )
                response.raise_for_status()
                content = response.content
            else:
                from scrapling import Fetcher

                response = Fetcher.get(
                    url,
                    timeout=15,
                    retries=1,
                    stealthy_headers=True,
                    headers={"User-Agent": random.choice(SCRAPLING_USER_AGENTS)},
                )
                if response.status < 200 or response.status >= 300:
                    continue
                content = response.body
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            path = os.path.join(temp_dir, f"candidate_{source}_{index}.jpg")
            with Image.open(io.BytesIO(content)) as image:
                image.convert("RGB").save(path, "JPEG", quality=95)
            paths.append(path)
            metadata_by_filename[os.path.basename(path)] = {
                key: value for key, value in candidate_metadata.items() if value
            }
        except Exception:
            continue
    with open(os.path.join(temp_dir, "candidate_metadata.json"), "w", encoding="utf-8") as metadata_file:
        json.dump(metadata_by_filename, metadata_file, indent=2)
    return paths


def choose_best_image(query: str, candidate_paths: list[str], output_path: str, background_color=(15, 23, 42)) -> dict:
    """Rank candidates, write the winner, and return visual-manifest metadata."""
    fallback_reason = "no_usable_candidates"
    try:
        ranked = rank_images(query, candidate_paths)
    except Exception as error:  # CLIP/network/model errors must not stop rendering.
        print(f"  [WARN] CLIP ranking failed: {error}")
        ranked = []
        fallback_reason = "ranking_error"
    if ranked:
        selected_path, score = ranked[0]
        try:
            minimum_score = float(os.environ.get("IMAGE_MIN_RELEVANCE_SCORE", DEFAULT_MIN_IMAGE_SIMILARITY))
        except (TypeError, ValueError):
            minimum_score = DEFAULT_MIN_IMAGE_SIMILARITY
        if score >= minimum_score:
            _letterbox_image(selected_path, output_path, background_color)
            source = "wikimedia_commons" if "candidate_wikimedia_commons_" in os.path.basename(selected_path) else "bing_images"
            return {
                "selected_image_path": selected_path,
                "selected_image_source": source,
                "similarity_score": score,
                "fallback_used": False,
            }
        print(f"  [INFO] Best image match ({score:.3f}) is below threshold ({minimum_score:.3f}).")
        return {
            "selected_image_path": None,
            "similarity_score": score,
            "fallback_used": True,
            "fallback_reason": "below_similarity_threshold",
        }
    return {
        "selected_image_path": None,
        "similarity_score": None,
        "fallback_used": True,
        "fallback_reason": fallback_reason,
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

        # ── 1. Category Header Pill Badge ──
        cat_text = category.replace("_", " ").upper()
        # Measure text width for dynamic badge sizing
        cat_bbox = draw.textbbox((0, 0), cat_text, font=self.cat_font)
        cat_w = cat_bbox[2] - cat_bbox[0] + 36
        draw.rounded_rectangle([60, 35, 60 + cat_w, 68], radius=6,
                               fill=theme["badge_bg"], outline=theme["accent"], width=1)
        draw.text((78, 43), cat_text, fill=theme["accent"], font=self.cat_font)

        # ── 2. Slide Main Title ──
        draw.text((60, 85), title, fill=theme["text_white"], font=self.title_font)

        # ── 2b. Accent Separator Line ──
        draw.line([(60, 135), (400, 135)], fill=theme["accent"], width=3)
        # Fading tail
        for i in range(80):
            fade = max(0, 255 - i * 3)
            r = int(theme["accent"][0] * fade / 255 + bg_r * (255 - fade) / 255)
            g = int(theme["accent"][1] * fade / 255 + bg_g * (255 - fade) / 255)
            b = int(theme["accent"][2] * fade / 255 + bg_b * (255 - fade) / 255)
            draw.line([(400 + i, 135), (400 + i, 137)], fill=(r, g, b))

        # ── 3. Content Layout Cards ──
        has_code = bool(code_snippet and str(code_snippet).strip() and str(code_snippet).strip().lower() != "null")

        has_visual_map = bool((visual_query or diagram_nodes) and not has_code)
        left_card_width = 640 if has_code or has_visual_map else 1160
        # Card with subtle glow effect
        draw.rounded_rectangle([56, 146, 64 + left_card_width, 664], radius=16,
                               fill=theme["card_bg"], outline=None)
        draw.rounded_rectangle([60, 150, 60 + left_card_width, 660], radius=14,
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
        bullet_y = 185
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

        # Render the slide planner's structured diagram without external images.
        if has_visual_map:
            panel = (730, 150, 1220, 660)
            draw.rounded_rectangle(panel, radius=14, fill=theme["card_bg"], outline=(51, 65, 85), width=1)
            draw.text((760, 175), layout_type.replace("_", " ").upper(), fill=theme["accent"], font=self.cat_font)
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
                draw.rounded_rectangle(box, radius=12, fill=theme["badge_bg"], outline=theme["accent"], width=2)
                lines = [label[i:i + 22] for i in range(0, len(label), 22)][:2]
                text_y = (box[1] + box[3]) / 2 - len(lines) * 10
                for line in lines:
                    bounds = draw.textbbox((0, 0), line, font=self.cat_font)
                    draw.text(((box[0] + box[2] - bounds[2] + bounds[0]) / 2, text_y), line,
                              fill=theme["text_white"], font=self.cat_font)
                    text_y += 20

            if layout_type == "flowchart":
                boxes = [(825, 240 + i * 94, 1075, 292 + i * 94) for i in range(min(len(labels), 4))]
                for previous, current in zip(boxes, boxes[1:]):
                    x = (previous[0] + previous[2]) // 2
                    draw.line((x, previous[3], x, current[1] - 6), fill=theme["accent"], width=3)
                    draw.polygon([(x - 6, current[1] - 12), (x + 6, current[1] - 12), (x, current[1] - 4)], fill=theme["accent"])
                for box, label in zip(boxes, labels):
                    draw_node(box, label)
            elif layout_type == "cycle":
                positions = [(850, 330), (1100, 330), (975, 520), (975, 270)]
                positions = positions[:len(labels)]
                for start, end in zip(positions, positions[1:] + positions[:1]):
                    draw.line((start[0], start[1], end[0], end[1]), fill=theme["accent"], width=3)
                for (cx, cy), label in zip(positions, labels):
                    draw_node((cx - 72, cy - 30, cx + 72, cy + 30), label)
            else:
                center = (975, 410)
                satellites = [(830, 300), (1120, 300), (830, 520), (1120, 520)][:max(0, len(labels) - 1)]
                for position in satellites:
                    draw.line((*center, *position), fill=theme["accent"], width=3)
                draw_node((center[0] - 88, center[1] - 38, center[0] + 88, center[1] + 38), labels[0])
                for (cx, cy), label in zip(satellites, labels[1:]):
                    draw_node((cx - 72, cy - 30, cx + 72, cy + 30), label)

        # ── 4. Code Block Card (Right Column) ──
        if has_code:
            right_x = 730
            draw.rounded_rectangle([right_x, 150, 1220, 660], radius=14,
                                   fill=theme["card_bg"], outline=(51, 65, 85), width=1)

            # Code Header Badge
            code_badge_text = "CODE EXAMPLE"
            draw.rounded_rectangle([right_x + 20, 168, right_x + 180, 195], radius=4,
                                   fill=theme["badge_bg"], outline=theme["accent"], width=1)
            draw.text((right_x + 30, 173), code_badge_text, fill=theme["accent"], font=self.cat_font)

            # Monospace Code Container Box
            draw.rounded_rectangle([right_x + 20, 210, 1200, 635], radius=8,
                                   fill=theme["code_bg"], outline=(30, 41, 59), width=1)

            # Line numbers + Code Text
            code_lines = str(code_snippet).strip().split("\n")
            code_y = 232
            for line_num, line in enumerate(code_lines[:11], 1):  # Limit to 11 lines
                # Line number in muted color
                draw.text((right_x + 28, code_y), str(line_num).rjust(2),
                          fill=theme["text_muted"], font=self.code_font)
                # Code text
                draw.text((right_x + 60, code_y), line[:42],
                          fill=(226, 232, 240), font=self.code_font)
                code_y += 34

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


def get_image(chunk_queries: List[Dict[str, Any]] | Dict[str, Dict[str, Any]], timestamp: str, topic_name: str = "") -> List[str]:
    """
    Render one locally generated visual slide per chunk spec; no image search is performed.
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
        )

        scene_id = entry.get("scene_id")
        if scene_id is None:
            match = re.search(r"(\d+)$", str(chunk_id))
            scene_id = int(match.group(1)) if match else idx
        visual_manifest.append({
            "scene_id": int(scene_id),
            "visual_query": visual_query,
            "candidate_count": 0,
            "selected_image_path": file_path,
            "selected_image_source": "generated_diagram",
            "similarity_score": None,
            "fallback_used": entry.get("content_source") == "deterministic_fallback",
            "fallback_reason": "slide_planner_unavailable" if entry.get("content_source") == "deterministic_fallback" else None,
            "layout_type": layout_type,
            "diagram_nodes": diagram_nodes,
            "content_source": entry.get("content_source", "provided_slide_spec"),
            "image_search_used": False,
        })

        print(f"  [OK] Saved slide [{chunk_id}]: {file_path}")
        all_images.append(file_path)

    with open(os.path.join(timestamp, "visual_manifest.json"), "w", encoding="utf-8") as manifest_file:
        json.dump(visual_manifest, manifest_file, indent=2)

    print(f"\n[OK] Total {len(all_images)} HD slides generated in {save_dir}")
    return all_images
