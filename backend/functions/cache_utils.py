import os
import re

def get_cache_dirs():
    """Returns candidate directories where previously generated videos are stored."""
    base_dir = os.path.dirname(__file__)
    dirs = [
        # Primary location: frontend static assets folder
        os.path.abspath(os.path.join(base_dir, "../../frontend/topic2explanation/public/prev_videos")),
        # Secondary/fallback location: backend local storage
        os.path.abspath(os.path.join(base_dir, "../prev_videos")),
    ]
    return dirs

def normalize_topic_name(topic: str) -> str:
    """Normalize topic string for comparison (lowercase, trimmed, strip .mp4 extension)."""
    if not topic:
        return ""
    cleaned = topic.strip().lower()
    if cleaned.endswith(".mp4"):
        cleaned = cleaned[:-4].strip()
    return " ".join(cleaned.split())

def alphanumeric_key(text: str) -> str:
    """Strip all non-alphanumeric characters for fuzzy matching across punctuation variations."""
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())

def find_cached_video(topic_name: str) -> dict:
    """
    Look for an existing video file in prev_videos matching topic_name.
    Matches case-insensitively and tolerates minor punctuation/extension differences.
    """
    if not topic_name or not topic_name.strip():
        return {"exists": False, "filename": None, "path": None, "url": None}

    target_clean = normalize_topic_name(topic_name)
    target_alpha = alphanumeric_key(topic_name)
    cache_dirs = get_cache_dirs()

    # Keep exact matches ahead of fuzzy matches across all cache directories.
    for key, target in ((normalize_topic_name, target_clean), (alphanumeric_key, target_alpha)):
        if key is alphanumeric_key and not target:
            continue
        for cdir in cache_dirs:
            if not os.path.isdir(cdir):
                continue
            try:
                for fname in os.listdir(cdir):
                    if fname.startswith(".") or not fname.lower().endswith(".mp4"):
                        continue
                    stem = fname[:-4].strip()
                    if key(stem) == target:
                        return {
                            "exists": True,
                            "topic": stem,
                            "filename": fname,
                            "path": os.path.join(cdir, fname),
                            "url": f"/prev_videos/{fname}"
                        }
            except Exception as e:
                print(f"Warning: error reading cache dir {cdir}: {e}")

    return {"exists": False, "filename": None, "path": None, "url": None}

def list_all_cached_videos() -> list:
    """Return a list of all existing videos in prev_videos cache."""
    cache_dirs = get_cache_dirs()
    videos = []
    seen_names = set()

    for cdir in cache_dirs:
        if not os.path.isdir(cdir):
            continue
        try:
            for fname in sorted(os.listdir(cdir)):
                if fname.startswith("."):
                    continue
                if fname.lower().endswith(".mp4"):
                    stem = fname[:-4].strip()
                    clean_key = normalize_topic_name(stem)
                    if clean_key not in seen_names:
                        seen_names.add(clean_key)
                        full_path = os.path.join(cdir, fname)
                        videos.append({
                            "topic": stem,
                            "filename": fname,
                            "path": full_path,
                            "url": f"/prev_videos/{fname}",
                            "size_bytes": os.path.getsize(full_path) if os.path.exists(full_path) else 0
                        })
        except Exception as e:
            print(f"Warning: error reading cache dir {cdir}: {e}")

    return videos

