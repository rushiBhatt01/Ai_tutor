import os
import shutil
import requests
from duckduckgo_search import DDGS
from PIL import Image
from io import BytesIO
from icrawler.builtin import BingImageCrawler


def save_url_image(url, path):
    """Download image from URL and save safely."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            ext = url.split(".")[-1].split("?")[0].lower()
            if ext not in ["jpg", "jpeg", "png"]:
                ext = "jpg"
                try:
                    img = Image.open(BytesIO(response.content)).convert("RGB")
                    img.save(path, "JPEG")
                except Exception as e:
                    print(f"Conversion failed for {url}: {e}")
                    return False
            else:
                with open(path, "wb") as f:
                    f.write(response.content)
            if os.path.getsize(path) > 6000:
                return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
    return False


def get_image(queries, timestamp, retry_attempts=3):
    """
    Fetch 1 image for each specific query.
    Pipeline per query: DuckDuckGo → Bing → retry N times → backup.
    """
    save_dir = os.path.join(timestamp, "images")
    os.makedirs(save_dir, exist_ok=True)
    
    min_total = len(queries)

    count = 0
    all_images = []

    for idx, query in enumerate(queries, start=1):
        label = query
        print(f"\n📌 Processing Query[{idx}]: {label}")
        success = False
        file_path = os.path.join(save_dir, f"{count}.jpg")

        # ---------- Attempt 1: DuckDuckGo ----------
        try:
            with DDGS(timeout=3) as ddgs:
                results = ddgs.images(query, max_results=1)
                for r in results:
                    url = r.get("image")
                    if url and save_url_image(url, file_path):
                        success = True
                        break
            if success:
                print(f"✅ DuckDuckGo worked for {label}")
        except Exception as e:
            print(f"⚠️ DuckDuckGo failed for {label}: {e}")

        # ---------- Attempt 2: Bing ----------
        if not success:
            print("🔄 Falling back to BingImageCrawler...")
            try:
                bing_crawler = BingImageCrawler(storage={"root_dir": save_dir})
                bing_crawler.crawl(keyword=query, max_num=1)
                for file in sorted(os.listdir(save_dir)):
                    candidate = os.path.join(save_dir, file)
                    if os.path.getsize(candidate) > 6000 and candidate not in all_images:
                        shutil.move(candidate, file_path)  # rename consistently
                        success = True
                        break
                if success:
                    print(f"✅ Bing worked for {label}")
            except Exception as e:
                print(f"❌ Bing failed for {label}: {e}")

        # ---------- Attempt 3: Retry DuckDuckGo ----------
        if not success:
            print(f"🔄 Retrying DuckDuckGo ({retry_attempts} attempts)...")
            try:
                with DDGS(timeout=3) as ddgs:
                    results = ddgs.images(query, max_results=retry_attempts * 2)
                    retries = 0
                    for r in results:
                        if retries >= retry_attempts:
                            break
                        url = r.get("image")
                        if url and save_url_image(url, file_path):
                            success = True
                            break
                        retries += 1
                if success:
                    print(f"✅ Retry DuckDuckGo worked for {label}")
            except Exception as e:
                print(f"⚠️ Retry failed for {label}: {e}")

        # ---------- Fallback: Backup ----------
        if not success:
            print(f"⚠️ No valid image for {label}, using backup")
            backup_img = "src/backup.jpg"
            shutil.copy(backup_img, file_path)
            success = True

        # Save successful image
        if success:
            all_images.append(file_path)
            count += 1

    # ---------- Ensure global > min_total ----------
    if len(all_images) < min_total:
        print(f"\n⚠️ Only {len(all_images)} images collected. Adding backups to reach {min_total}...")
        while len(all_images) < min_total:
            backup_img = "src/backup.jpg"
            file_path = os.path.join(save_dir, f"{count}.jpg")
            shutil.copy(backup_img, file_path)
            all_images.append(file_path)
            count += 1

    print(f"\n✅ Total {len(all_images)} images saved in {save_dir} (sequentially)")
    return all_images
