"""
Builds a persistent chronological queue of all posts from the target TikTok user,
sorted from oldest to newest (beginning of the account).
"""

import sys
import json
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
QUEUE_FILE = BASE_DIR / "queue.json"
RAW_DIR = BASE_DIR / "queue_downloads_temp"


def build_chronological_queue(target_username: str = "zane_reps", max_posts: int = 300) -> List[Dict[str, Any]]:
    clean_user = target_username.lstrip("@").strip()
    url = f"https://www.tiktok.com/@{clean_user}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[*] Scanning all posts from @{clean_user} (up to {max_posts})...")
    print("[*] Please wait while posts are cataloged...")

    cmd = [
        "python", "-m", "gallery_dl",
        "--range", f"1-{max_posts}",
        "--write-metadata",
        "-D", str(RAW_DIR),
        url
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    posts_map = {}
    for meta_file in RAW_DIR.glob("*.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("type") == "avatar":
                continue
            post_id = str(meta.get("id") or "")
            if not post_id or post_id == clean_user:
                continue

            if post_id not in posts_map:
                create_time = int(meta.get("createTime") or 0)
                is_carousel = "imagePost" in meta or bool(meta.get("imagePostInfo"))
                posts_map[post_id] = {
                    "postId": post_id,
                    "createTime": create_time,
                    "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(create_time)) if create_time else "unknown",
                    "desc": meta.get("desc", ""),
                    "author": meta.get("author", {}).get("uniqueId", clean_user),
                    "music": meta.get("music", {}),
                    "isCarousel": is_carousel,
                    "files": [],
                    "status": "pending"  # pending | processing | posted | failed
                }

            # Find media file
            base_name = meta_file.name[:-5]
            media_cand = meta_file.parent / base_name
            if media_cand.exists() and media_cand not in posts_map[post_id]["files"]:
                posts_map[post_id]["files"].append(str(media_cand))
        except Exception:
            continue

    # Sort files inside each post
    for pid in posts_map:
        posts_map[pid]["files"].sort()

    # Sort ALL posts chronologically: OLDEST FIRST (beginning of account)
    sorted_posts = sorted(list(posts_map.values()), key=lambda x: x["createTime"])

    # Load existing queue to preserve statuses if updating
    existing_queue = {}
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    existing_queue[item["postId"]] = item
        except Exception:
            pass

    final_queue = []
    for p in sorted_posts:
        pid = p["postId"]
        if pid in existing_queue:
            final_queue.append(existing_queue[pid])
        else:
            final_queue.append(p)

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(final_queue, f, indent=2)

    pending_count = sum(1 for p in final_queue if p.get("status") == "pending")
    posted_count = sum(1 for p in final_queue if p.get("status") == "posted")

    print(f"\n[OK] Queue built successfully!")
    print(f"     Total posts:    {len(final_queue)}")
    print(f"     Pending:        {pending_count}")
    print(f"     Already posted: {posted_count}")
    if final_queue:
        print(f"     First post date (oldest): {final_queue[0].get('date')} [ID: {final_queue[0]['postId']}]")
        print(f"     Latest post date (newest): {final_queue[-1].get('date')} [ID: {final_queue[-1]['postId']}]")

    return final_queue


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "zane_reps"
    build_chronological_queue(target)
