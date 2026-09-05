import os
import requests
from dataclasses import dataclass
from typing import List, Dict, Any, Set, Optional
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from lxml import html

# Target slide resolution & quality constraints
SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720
MIN_IMAGE_WIDTH = 800
MIN_IMAGE_HEIGHT = 600
MIN_FILE_SIZE = 8000  # bytes

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Category theme colors for fallback canvas slides
CATEGORY_THEMES = {
    "INTRO_OVERVIEW": {"bg": (15, 23, 42), "text": (56, 189, 248), "accent": (14, 165, 233)},
    "KEY_CONCEPTS": {"bg": (30, 27, 75), "text": (165, 180, 252), "accent": (99, 102, 241)},
    "ARCHITECTURE_STRUCTURE": {"bg": (15, 32, 39), "text": (45, 212, 191), "accent": (20, 184, 166)},
    "WORKFLOW_PROCESS": {"bg": (24, 24, 27), "text": (251, 146, 60), "accent": (249, 115, 22)},
    "PRACTICAL_EXAMPLE": {"bg": (20, 20, 20), "text": (74, 222, 128), "accent": (34, 197, 94)},
    "BENEFITS_COMPARISON": {"bg": (40, 20, 30), "text": (244, 114, 182), "accent": (236, 72, 153)},
    "SUMMARY_CONCLUSION": {"bg": (6, 78, 59), "text": (110, 231, 183), "accent": (16, 185, 129)}
}

@dataclass
class ImageCandidate:
    """Represents a discovered image search result before downloading."""
    url: str
    source: str
    query: str
    category: str
    title: Optional[str] = None


class ImageSearcher:
    """
    Decoupled Searcher responsible for fetching search result HTML,
    parsing image tags, and extracting candidate image URLs.
    """

    def search_bing_hd(self, query: str, category: str, max_results: int = 5) -> List[ImageCandidate]:
        candidates: List[ImageCandidate] = []
        try:
            url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&qft=+filterui:imagesize-large&form=HDRSC2&first=1"
            resp = requests.get(url, timeout=8, headers=HEADERS)
            if resp.status_code == 200:
                tree = html.fromstring(resp.content)
                for a_tag in tree.cssselect("a.iusc"):
                    m_attr = a_tag.get("m", "")
                    if '"murl":"' in m_attr:
                        start = m_attr.index('"murl":"') + 8
                        end = m_attr.index('"', start)
                        murl = m_attr[start:end]
                        if murl.startswith("http"):
                            candidates.append(ImageCandidate(
                                url=murl,
                                source="bing_hd",
                                query=query,
                                category=category
                            ))
                            if len(candidates) >= max_results:
                                break
        except Exception as e:
            print(f"    ⚠️ ImageSearcher Bing HD failed: {e}")
        return candidates

    def search_duckduckgo(self, query: str, category: str, max_results: int = 5) -> List[ImageCandidate]:
        candidates: List[ImageCandidate] = []
        try:
            url = f"https://duckduckgo.com/?q={requests.utils.quote(query)}&iax=images&ia=images"
            resp = requests.get(url, timeout=8, headers=HEADERS)
            if resp.status_code == 200:
                tree = html.fromstring(resp.content)
                for img_tag in tree.cssselect("img"):
                    src = img_tag.get("src") or img_tag.get("data-src") or ""
                    if src.startswith("http"):
                        candidates.append(ImageCandidate(
                            url=src,
                            source="duckduckgo",
                            query=query,
                            category=category
                        ))
                        if len(candidates) >= max_results:
                            break
        except Exception as e:
            print(f"    ⚠️ ImageSearcher DuckDuckGo failed: {e}")
        return candidates

    def find_candidates(self, query: str, category: str, max_results: int = 5) -> List[ImageCandidate]:
        """Aggregate candidate image URLs from multiple search engines."""
        candidates = self.search_bing_hd(query, category, max_results)
        if len(candidates) < max_results:
            candidates.extend(self.search_duckduckgo(query, category, max_results - len(candidates)))
        return candidates


class ImageDownloader:
    """
    Decoupled Downloader responsible for downloading image candidates,
    validating container integrity & resolution (>800x600), letterboxing to 1280x720,
    and saving the validated image artifact.
    """

    def letterbox(self, img: Image.Image, w: int = SLIDE_WIDTH, h: int = SLIDE_HEIGHT) -> Image.Image:
        """Resize image to fit inside (w × h) with dark background padding."""
        img = img.convert("RGB")
        img.thumbnail((w, h), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (12, 12, 18))
        x = (w - img.width) // 2
        y = (h - img.height) // 2
        canvas.paste(img, (x, y))
        return canvas

    def download_and_validate(self, candidate: ImageCandidate, save_path: str, seen_urls: Set[str]) -> bool:
        """
        Download, validate resolution (>800x600), letterbox, and save.
        Returns True if image is valid and saved successfully.
        """
        if candidate.url in seen_urls:
            return False
        try:
            resp = requests.get(candidate.url, timeout=10, headers=HEADERS)
            if resp.status_code != 200 or len(resp.content) < MIN_FILE_SIZE:
                return False

            img = Image.open(BytesIO(resp.content))
            
            # Resolution check (>800x600 px)
            if img.width < MIN_IMAGE_WIDTH or img.height < MIN_IMAGE_HEIGHT:
                return False

            letterboxed_img = self.letterbox(img)
            letterboxed_img.save(save_path, "JPEG", quality=92)
            
            if os.path.getsize(save_path) >= MIN_FILE_SIZE:
                seen_urls.add(candidate.url)
                return True
        except Exception as e:
            print(f"    ⚠️ ImageDownloader failed for {candidate.url}: {e}")
        return False

    def generate_fallback_slide(self, query_text: str, category: str, save_path: str):
        """Generate a branded canvas slide if no web image passes validation."""
        theme = CATEGORY_THEMES.get(category, CATEGORY_THEMES["INTRO_OVERVIEW"])
        canvas = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), theme["bg"])
        draw = ImageDraw.Draw(canvas)

        try:
            title_font = ImageFont.truetype("arial.ttf", 32)
            body_font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        # Draw Category Header Badge
        cat_label = f"[{category.replace('_', ' ')}]"
        draw.text((60, 50), cat_label, fill=theme["accent"], font=title_font)

        # Word wrap main query text
        words = query_text.split()
        lines, line = [], ""
        for word in words:
            test = f"{line} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=body_font)
            if bbox[2] - bbox[0] > SLIDE_WIDTH - 160:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)

        y0 = 160
        for i, ln in enumerate(lines[:8]):
            draw.text((60, y0 + i * 40), ln, fill=theme["text"], font=body_font)

        canvas.save(save_path, "JPEG", quality=90)


# ── Pipeline Orchestrator Function ─────────────────────────────────────────

def get_image(chunk_queries: List[Dict[str, Any]], timestamp: str) -> List[str]:
    """
    Orchestrates candidate search -> download/validation -> slide output.
    Uses decoupled ImageSearcher and ImageDownloader components.
    """
    save_dir = os.path.join(timestamp, "images")
    os.makedirs(save_dir, exist_ok=True)

    searcher = ImageSearcher()
    downloader = ImageDownloader()

    all_images: List[str] = []
    seen_urls: Set[str] = set()

    for entry in chunk_queries:
        chunk_id = entry["chunk_id"]
        query = entry["query"]
        category = entry.get("category", "INTRO_OVERVIEW")
        file_path = os.path.join(save_dir, f"{chunk_id}.jpg")
        
        print(f"\n📌 [{chunk_id}] [{category}] Searching HD: {query}")

        success = False

        # 3-Level Query Relaxation Fallbacks
        fallback_queries = [
            query,
            f"{entry.get('query', '').split(' ')[0]} {category.replace('_', ' ')} diagram HD",
            f"{entry.get('query', '').split(' ')[0]} high resolution diagram"
        ]

        for current_query in fallback_queries:
            if success:
                break
            
            # Step 1: Search and extract candidate URLs
            candidates: List[ImageCandidate] = searcher.find_candidates(current_query, category, max_results=5)

            # Step 2: Download, validate, and letterbox candidate images
            for candidate in candidates:
                if downloader.download_and_validate(candidate, file_path, seen_urls):
                    print(f"    ✅ Saved validated HD image ({candidate.source}): {chunk_id}")
                    success = True
                    break

        if not success:
            # Fallback: Category-themed canvas slide
            print(f"    ⚠️ No valid HD image for [{chunk_id}], generating themed fallback slide")
            downloader.generate_fallback_slide(query, category, file_path)

        all_images.append(file_path)

    print(f"\n✅ Total {len(all_images)} HD images saved in {save_dir}")
    return all_images
