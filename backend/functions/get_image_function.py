import os
import re
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

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
        topic_name: str = ""
    ) -> str:
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

        left_card_width = 640 if has_code else 1160
        # Card with subtle glow effect
        draw.rounded_rectangle([56, 146, 64 + left_card_width, 664], radius=16,
                               fill=theme["card_bg"], outline=None)
        draw.rounded_rectangle([60, 150, 60 + left_card_width, 660], radius=14,
                               fill=theme["card_bg"], outline=(51, 65, 85), width=1)

        # Category-specific bullet icon
        BULLET_ICONS = {
            "INTRO_OVERVIEW": "▸",
            "KEY_CONCEPTS": "◆",
            "ARCHITECTURE_STRUCTURE": "◈",
            "WORKFLOW_PROCESS": "►",
            "PRACTICAL_EXAMPLE": "✦",
            "BENEFITS_COMPARISON": "◇",
            "SUMMARY_CONCLUSION": "★"
        }
        bullet_icon = BULLET_ICONS.get(category, "▸")

        # Render Bullet Points with word wrapping
        bullet_y = 185
        max_bullet_w = left_card_width - 80

        for b_idx, bullet in enumerate(bullets[:4]):  # Limit to max 4 bullet points per slide
            bullet_clean = re.sub(r'[*`_~]', '', str(bullet)).strip()
            if not bullet_clean:
                continue

            # Draw accent bullet icon instead of plain dot
            draw.text((85, bullet_y - 2), bullet_icon, fill=theme["accent"], font=self.body_font)

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
        draw.rectangle([0, 708, SLIDE_WIDTH, SLIDE_HEIGHT], fill=theme["accent"])

        # ── 6. Progress Indicator (bottom-right) ──
        if total_slides > 0:
            progress_text = f"{slide_number} / {total_slides}"
            progress_bbox = draw.textbbox((0, 0), progress_text, font=self.cat_font)
            pw = progress_bbox[2] - progress_bbox[0]
            # Draw on the accent bar
            draw.text((SLIDE_WIDTH - pw - 30, 711), progress_text,
                      fill=theme["bg"], font=self.cat_font)

        # ── 7. Topic Footer Watermark ──
        if topic_name:
            footer_text = topic_name.upper()
            footer_bbox = draw.textbbox((0, 0), footer_text, font=self.cat_font)
            draw.text((30, 711), footer_text, fill=theme["bg"], font=self.cat_font)

        # Save slide image file
        img.save(save_path, "JPEG", quality=95)
        return save_path


def get_image(chunk_queries: List[Dict[str, Any]], timestamp: str, topic_name: str = "") -> List[str]:
    """
    Orchestrates dynamic HD slide generation for each chunk spec.
    Produces 1280x720 JPEG slide images in <timestamp>/images/seg_X.jpg.
    """
    save_dir = os.path.join(timestamp, "images")
    os.makedirs(save_dir, exist_ok=True)

    renderer = SlideCanvasRenderer()
    all_images: List[str] = []
    total_slides = len(chunk_queries)

    # Extract topic_name from chunk_queries if not provided
    if not topic_name and chunk_queries:
        topic_name = chunk_queries[0].get("chunk_text", "")[:30] if chunk_queries[0].get("chunk_text") else ""

    print(f"\nGenerating {total_slides} dynamic 1280x720 slide(s)...")

    for idx, entry in enumerate(chunk_queries):
        chunk_id = entry["chunk_id"]
        category = entry.get("category", "INTRO_OVERVIEW")
        title = entry.get("title", "Tutorial Slide")
        bullets = entry.get("bullets", [])
        code_snippet = entry.get("code_snippet")

        file_path = os.path.join(save_dir, f"{chunk_id}.jpg")

        renderer.render_slide(
            title=title,
            category=category,
            bullets=bullets,
            code_snippet=code_snippet,
            save_path=file_path,
            slide_number=idx + 1,
            total_slides=total_slides,
            topic_name=topic_name
        )

        print(f"  [OK] Saved slide [{chunk_id}]: {file_path}")
        all_images.append(file_path)

    print(f"\n[OK] Total {len(all_images)} HD slides generated in {save_dir}")
    return all_images
