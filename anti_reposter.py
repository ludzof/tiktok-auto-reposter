import os
import sys
import json
import time
import shutil
import subprocess
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageEnhance

# Reconfigure console output for Windows UTF-8 support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "processed_history.json"
RAW_DOWNLOADS_DIR = BASE_DIR / "raw_downloads"
PROCESSED_OUTPUT_DIR = BASE_DIR / "processed_output"

DEFAULT_CONFIG = {
    "source_username": "zane_reps",
    "download_count": 5,
    "video_modifications": {
        "crop_percent": 1.5,
        "speed_multiplier": 1.02,
        "contrast": 1.03,
        "saturation": 1.04,
        "brightness": 0.01
    },
    "carousel_modifications": {
        "crop_percent": 1.5,
        "contrast": 1.03,
        "saturation": 1.04,
        "strip_exif": True,
        "jpeg_quality": 95
    },
    "caption_settings": {
        "strip_original_hashtags": True,
        "include_credit": False,
        "new_hashtags": "#fyp #viral #trending #reps #explore"
    }
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception:
        return DEFAULT_CONFIG


def load_history() -> List[str]:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: List[str]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-1000:], f, indent=2)


# ---------------------------------------------------------------------------
# 1. Transform Carousel Image (Pillow Anti-Flag)
# ---------------------------------------------------------------------------
def process_image_anti_flag(input_path: Path, output_path: Path, config: Dict[str, Any]) -> bool:
    cm = config.get("carousel_modifications", {})
    crop_pct = cm.get("crop_percent", 1.5) / 100.0
    contrast_boost = cm.get("contrast", 1.03)
    saturation_boost = cm.get("saturation", 1.04)
    quality = cm.get("jpeg_quality", 95)

    try:
        with Image.open(input_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Micro-crop 1.5% off borders
            width, height = img.size
            dx = int(width * crop_pct / 2)
            dy = int(height * crop_pct / 2)
            left = dx
            top = dy
            right = width - dx
            bottom = height - dy
            img = img.crop((left, top, right, bottom))

            # Alter pixel color histograms
            img = ImageEnhance.Color(img).enhance(saturation_boost)
            img = ImageEnhance.Contrast(img).enhance(contrast_boost)

            # Strip EXIF & save fresh
            clean_img = Image.new("RGB", img.size)
            clean_img.paste(img)
            clean_img.save(output_path, "JPEG", quality=quality, optimize=True)

        return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:
        print(f"[!] Pillow error on {input_path.name}: {e}")
        return False


# ---------------------------------------------------------------------------
# 2. Transform Video (FFmpeg Anti-Flag)
# ---------------------------------------------------------------------------
def process_video_anti_flag(input_path: Path, output_path: Path, config: Dict[str, Any]) -> bool:
    vm = config.get("video_modifications", {})
    crop_pct = vm.get("crop_percent", 1.5) / 100.0
    speed = vm.get("speed_multiplier", 1.02)
    contrast = vm.get("contrast", 1.03)
    saturation = vm.get("saturation", 1.04)
    brightness = vm.get("brightness", 0.01)

    crop_factor = 1.0 - crop_pct
    vf_crop = f"crop=in_w*{crop_factor:.4f}:in_h*{crop_factor:.4f}:(in_w-out_w)/2:(in_h-out_h)/2"
    vf_color = f"eq=contrast={contrast:.2f}:saturation={saturation:.2f}:brightness={brightness:.2f}"
    vf_speed = f"setpts=PTS/{speed:.4f}"
    video_filter = f"{vf_crop},{vf_color},{vf_speed}"
    audio_filter = f"atempo={speed:.4f}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", video_filter,
        "-af", audio_filter,
        "-map_metadata", "-1",
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:
        print(f"[!] FFmpeg error on {input_path.name}: {e}")
        return False


# ---------------------------------------------------------------------------
# 3. Caption Spinner
# ---------------------------------------------------------------------------
def spin_caption(raw_title: str, author: str, config: Dict[str, Any]) -> str:
    cs = config.get("caption_settings", {})
    words = (raw_title or "").split()

    if cs.get("strip_original_hashtags", True):
        words = [w for w in words if not w.startswith("#")]

    cleaned_text = " ".join(words).strip()
    new_hashtags = cs.get("new_hashtags", "#fyp #viral #trending")

    parts = [cleaned_text]
    if cs.get("include_credit", False) and author:
        parts.append(f"(Credit: @{author})")

    parts.append(new_hashtags)
    return "\n\n".join([p for p in parts if p])


# ---------------------------------------------------------------------------
# 4. Native Scraper & Downloader (via gallery-dl, 0 API keys required)
# ---------------------------------------------------------------------------
def download_profile_posts(username: str, count: int = 5) -> List[Dict[str, Any]]:
    clean_user = username.lstrip("@").strip()
    url = f"https://www.tiktok.com/@{clean_user}"
    RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[*] Fetching up to {count} latest posts from @{clean_user}...")
    cmd = [
        "python", "-m", "gallery_dl",
        "--range", f"1-{count}",
        "--write-metadata",
        "-D", str(RAW_DOWNLOADS_DIR),
        url
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Parse downloaded files & metadata
    grouped_posts = {}
    for meta_file in RAW_DOWNLOADS_DIR.glob("*.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            post_id = str(meta.get("id") or "")
            if not post_id or post_id == clean_user:
                continue

            if post_id not in grouped_posts:
                grouped_posts[post_id] = {
                    "id": post_id,
                    "desc": meta.get("desc", ""),
                    "author": meta.get("author", {}).get("uniqueId", clean_user),
                    "music": meta.get("music", {}),
                    "isCarousel": "imagePost" in meta or bool(meta.get("imagePostInfo")),
                    "files": []
                }
            
            # Find the corresponding media file
            base_name = meta_file.name[:-5] # strip .json
            media_cand = meta_file.parent / base_name
            if media_cand.exists() and media_cand not in grouped_posts[post_id]["files"]:
                grouped_posts[post_id]["files"].append(media_cand)
        except Exception:
            continue

    # Also sort files for each post (slide_01, slide_02 etc.)
    for pid in grouped_posts:
        grouped_posts[pid]["files"].sort(key=lambda p: p.name)

    return list(grouped_posts.values())


# ---------------------------------------------------------------------------
# 5. Main Processing Flow
# ---------------------------------------------------------------------------
def run_anti_flag_processor():
    print("=============================================================")
    print("  TikTok Anti-Flagging Reposter (Direct @zane_reps Engine)   ")
    print("=============================================================\n")

    config = load_config()
    history = load_history()
    target_user = config.get("source_username", "zane_reps")
    count = config.get("download_count", 5)

    PROCESSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    posts = download_profile_posts(target_user, count=count)
    if not posts:
        print("[!] No posts extracted. Check internet connection or username.")
        return

    print(f"[*] Found {len(posts)} posts from @{target_user}.")

    for post in posts:
        post_id = post["id"]
        if post_id in history:
            print(f"[-] Post {post_id} was already processed previously. Skipping.")
            continue

        is_carousel = post["isCarousel"]
        post_dir = PROCESSED_OUTPUT_DIR / post_id
        post_dir.mkdir(parents=True, exist_ok=True)

        spun_caption = spin_caption(post["desc"], post["author"], config)

        print(f"\n[>] Processing Post {post_id} [{'Photo Carousel' if is_carousel else 'Video'}]")
        print(f"    Original Caption: {post['desc'][:60]}...")
        print(f"    Spun Caption:     {spun_caption[:60]}...")

        manifest = {
            "postId": post_id,
            "isCarousel": is_carousel,
            "originalAuthor": post["author"],
            "caption": spun_caption,
            "files": [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Handle Background Music
        music_url = post["music"].get("playUrl")
        if music_url:
            clean_audio = post_dir / "audio_anti_flagged.mp3"
            try:
                r = requests.get(music_url, timeout=20)
                if r.status_code == 200:
                    raw_audio = post_dir / "audio_raw.mp3"
                    with open(raw_audio, "wb") as f:
                        f.write(r.content)
                    # Shift audio tempo
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(raw_audio),
                        "-af", "atempo=1.02",
                        "-map_metadata", "-1",
                        str(clean_audio)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if clean_audio.exists():
                        manifest["audio"] = str(clean_audio)
                    raw_audio.unlink(missing_ok=True)
            except Exception:
                pass

        if is_carousel:
            # Process each photo carousel slide
            slide_count = 0
            for idx, raw_file in enumerate(post["files"], start=1):
                if raw_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    slide_count += 1
                    clean_slide = post_dir / f"slide_{slide_count:02d}_anti_flagged.jpg"
                    if process_image_anti_flag(raw_file, clean_slide, config):
                        manifest["files"].append(str(clean_slide))

            print(f"[OK] Transformed {len(manifest['files'])} carousel slides (EXIF stripped + cropped + color shifted)")

        else:
            # Process video
            for raw_file in post["files"]:
                if raw_file.suffix.lower() in [".mp4", ".mov", ".webm"]:
                    clean_vid = post_dir / f"{post_id}_anti_flagged.mp4"
                    if process_video_anti_flag(raw_file, clean_vid, config):
                        manifest["files"].append(str(clean_vid))
                        print(f"[OK] Transformed video with FFmpeg multi-layer anti-flagging.")

        # Save manifest
        with open(post_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        history.append(post_id)
        save_history(history)

    # Clean raw downloads folder
    shutil.rmtree(RAW_DOWNLOADS_DIR, ignore_errors=True)

    print(f"\n[OK] Done! All processed posts and photo carousels are in:")
    print(f"    {PROCESSED_OUTPUT_DIR}")


if __name__ == "__main__":
    run_anti_flag_processor()
