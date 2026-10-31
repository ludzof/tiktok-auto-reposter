import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
queue_file = BASE_DIR / "queue.json"
state_file = BASE_DIR / "scheduler_state.json"
state_file.unlink(missing_ok=True)

with open(queue_file, "r", encoding="utf-8") as f:
    queue = json.load(f)

# Filter out avatars / placeholder non-posts
real_posts = [p for p in queue if p.get("desc") or len(p.get("files", [])) > 1]

# Reset status of every post to pending
for p in real_posts:
    p["status"] = "pending"
    p.pop("posted_at", None)

# Sort chronologically (oldest first)
real_posts.sort(key=lambda x: x.get("createTime", 0))

with open(queue_file, "w", encoding="utf-8") as f:
    json.dump(real_posts, f, indent=2)

print(f"[OK] Queue reset successfully! Total items: {len(real_posts)}")
print(f"[*] First post (oldest): ID {real_posts[0]['postId']} ({real_posts[0]['date']})")
print(f"    Carousel: {real_posts[0].get('isCarousel')}, Files: {len(real_posts[0].get('files', []))}")
print(f"    Description: {real_posts[0].get('desc')}")
print(f"[*] Last post (newest):  ID {real_posts[-1]['postId']} ({real_posts[-1]['date']})")
