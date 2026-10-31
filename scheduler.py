"""
Continuous Queue Scheduler.
Picks the next oldest post from @zane_reps, applies anti-flagging modifications,
and auto-posts it to your TikTok profile on your chosen interval.
"""

import sys
import time
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
QUEUE_FILE = BASE_DIR / "queue.json"
OUTPUT_DIR = BASE_DIR / "processed_output"
STATE_FILE = BASE_DIR / "scheduler_state.json"

from build_queue import build_chronological_queue
from anti_reposter import (
    load_config,
    process_video_anti_flag,
    process_image_anti_flag,
    spin_caption
)
from playwright_uploader import upload_to_tiktok


def stitch_carousel_to_slideshow(slides: list, audio_path: Optional[Path], out_mp4: Path) -> bool:
    """Stitches carousel slides into a vertical 1080x1920 MP4 with background music."""
    concat_file = out_mp4.parent / "slides_concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for s in slides:
            f.write(f"file '{s.name}'\nduration 2.5\n")
        f.write(f"file '{slides[-1].name}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
    ]

    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
    else:
        # Generate silent audio if no music track
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

    cmd.extend([
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4)
    ])

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    concat_file.unlink(missing_ok=True)
    return res.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 1000


def get_last_post_timestamp() -> Optional[float]:
    """Retrieves the timestamp of the most recent successful post from state file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                ts = float(data.get("last_post_timestamp", 0))
                if ts > 0:
                    return ts
        except Exception:
            pass
    return None


def set_last_post_timestamp(post_id: str, ts: Optional[float] = None):
    """Persists the post timestamp to disk so timers survive closing cmd or PC restart."""
    if ts is None:
        ts = time.time()
    data = {
        "last_post_timestamp": ts,
        "last_post_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
        "last_post_id": post_id
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def wait_with_countdown(total_seconds: float):
    """Counts down second-by-second in real time without drifting, updating the terminal."""
    target_time = time.time() + total_seconds
    while True:
        remaining = int(target_time - time.time())
        if remaining <= 0:
            break
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            time_str = f"{hours}h {mins:02d}m {secs:02d}s"
        else:
            time_str = f"{mins}m {secs:02d}s"
        sys.stdout.write(f"\r[*] Next post in: {time_str} remaining...   ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r[*] Cooldown finished! Proceeding to next post...          \n\n")
    sys.stdout.flush()


def run_scheduler():
    config = load_config()
    target_user = config.get("source_username", "zane_reps")
    interval_minutes = config.get("check_interval_minutes", 60)
    headless = config.get("headless_browser", False)

    print("==========================================================")
    print("      TikTok Auto-Reposter: Chronological Queue Runner     ")
    print("==========================================================")
    print(f"[*] Target Profile:    @{target_user}")
    print(f"[*] Post Interval:     Every {interval_minutes} minutes")
    print(f"[*] Starting From:     Beginning (Oldest -> Newest)")
    print(f"[*] Persistent Timer:  Enabled (retains cooldown across restarts)\n")

    # 1. Ensure queue exists
    if not QUEUE_FILE.exists():
        print("[*] No queue.json found. Building initial queue from @zane_reps...")
        build_chronological_queue(target_user)

    while True:
        # 2. Check if persistent cooldown from previous session is still running
        last_post_ts = get_last_post_timestamp()
        if last_post_ts:
            elapsed_sec = time.time() - last_post_ts
            required_sec = interval_minutes * 60
            remaining_sec = required_sec - elapsed_sec
            if remaining_sec > 0:
                last_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_post_ts))
                print(f"[*] Detected previous post from: {last_str}")
                print(f"[*] Persistent timer active. Resuming remaining cooldown without resetting...")
                wait_with_countdown(remaining_sec)

        # Reload queue
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)

        # Find next pending item (chronological order)
        pending_items = [p for p in queue if p.get("status") == "pending"]
        if not pending_items:
            print("\n[OK] All posts from @zane_reps have been reposted!")
            print("[*] Queue is empty. Re-checking for new posts in 60 minutes...")
            wait_with_countdown(3600)
            build_chronological_queue(target_user)
            continue

        item = pending_items[0]
        post_id = item["postId"]

        # Skip avatar or empty metadata items
        if not item.get("desc") and len(item.get("files", [])) <= 1:
            item["status"] = "skipped"
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
            continue

        is_carousel = item.get("isCarousel", False)

        print(f"\n{'='*60}")
        print(f"[>] NEXT IN QUEUE: Post ID {post_id}")
        print(f"    Original Date: {item.get('date')}")
        print(f"    Type:          {'Photo Carousel' if is_carousel else 'Video'}")
        print(f"    Original Desc: {item.get('desc')[:60]}...")

        post_dir = OUTPUT_DIR / post_id
        post_dir.mkdir(parents=True, exist_ok=True)

        # Prepare transformed media
        media_to_upload = []
        spun_caption = spin_caption(item.get("desc", ""), item.get("author", target_user), config)

        if is_carousel:
            # Transform carousel images to anti-flagged JPGs
            slides = [Path(f) for f in item.get("files", []) if Path(f).exists()]
            clean_slides = []
            for idx, s in enumerate(slides, 1):
                clean_s = post_dir / f"slide_{idx:02d}_anti_flagged.jpg"
                if process_image_anti_flag(s, clean_s, config):
                    clean_slides.append(clean_s)

            if clean_slides:
                print(f"[OK] Prepared {len(clean_slides)} native anti-flagged carousel slides!")
                media_to_upload = clean_slides
        else:
            # Transform standard video
            raw_vids = [Path(f) for f in item.get("files", []) if Path(f).exists() and Path(f).suffix.lower() in [".mp4", ".mov"]]
            if raw_vids:
                clean_vid = post_dir / f"{post_id}_anti_flagged.mp4"
                if process_video_anti_flag(raw_vids[0], clean_vid, config):
                    media_to_upload = [clean_vid]

        if not media_to_upload:
            print(f"[!] Could not prepare media for post {post_id}. Skipping to next.")
            item["status"] = "failed"
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
            wait_with_countdown(60)
        else:
            print(f"[*] Media ready ({len(media_to_upload)} files). Uploading as {'Photo Carousel' if is_carousel else 'Video'}...")
            success = upload_to_tiktok(media_to_upload, spun_caption, is_carousel=is_carousel, headless=headless, post_id=post_id)
            if success:
                item["status"] = "posted"
                now_ts = time.time()
                item["posted_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
                item["posted_timestamp"] = now_ts
                set_last_post_timestamp(post_id, now_ts)
                print(f"[OK] Post {post_id} published successfully to your profile!")

                # Update queue file
                with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                    json.dump(queue, f, indent=2)

                # Wait with persistent countdown until next post
                print(f"\n[*] Waiting {interval_minutes} minutes before posting the next item...")
                wait_with_countdown(interval_minutes * 60)
            else:
                print(f"[!] Upload failed for post {post_id}. Retrying in 5 minutes...")
                item["status"] = "pending"
                with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                    json.dump(queue, f, indent=2)
                wait_with_countdown(300)


if __name__ == "__main__":
    run_scheduler()
