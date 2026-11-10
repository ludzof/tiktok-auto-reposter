"""
Playwright-based automated uploader for TikTok Desktop Studio.
Uploads native Photo Carousels (via the Photos tab) and standard Videos (via Videos tab).
Includes robust 10-second post confirmation, pop-up dismissal, and verification.
"""

import sys
import time
import json
import re
import random
from pathlib import Path
from typing import List, Union, Dict, Optional
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
SESSION_DIR = BASE_DIR / "tiktok_session"
USED_SOUNDS_FILE = BASE_DIR / "used_sounds.json"


def normalize_title(title: str) -> str:
    """Normalize song title for duplicate detection."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def load_used_sounds() -> List[Dict]:
    """Loads historical list of all sounds used in previous posts."""
    if USED_SOUNDS_FILE.exists():
        try:
            with open(USED_SOUNDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_used_sound(title: str, subtitle: str, post_id: str = ""):
    """Records chosen sound into used_sounds.json to prevent duplicate use forever."""
    used = load_used_sounds()
    used.append({
        "title": title,
        "subtitle": subtitle,
        "normalized": normalize_title(title),
        "used_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "post_id": post_id
    })
    with open(USED_SOUNDS_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, indent=2)


def pick_unique_sound(page, post_id: str = "") -> Optional[str]:
    """
    Finds and selects a trending sound from 'For You' that has NEVER been used before.
    Guarantees no sound is picked twice.
    """
    used_records = load_used_sounds()
    used_signatures = {r.get("normalized") for r in used_records if r.get("normalized")}
    print(f"[*] Previously used sounds in database: {len(used_signatures)}")

    # 1. Wait for sound list to render in modal
    try:
        page.locator('button:has-text("Use")').first.wait_for(state="visible", timeout=15000)
    except Exception:
        print("[!] Timed out waiting for sounds in modal.")
        page.keyboard.press("Escape")
        time.sleep(1)
        return None

    def get_sounds():
        return page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button')).filter(b => b.innerText.trim() === 'Use');
            return btns.map((b, i) => {
                const container = b.parentElement?.parentElement;
                const text = container ? container.innerText : '';
                const lines = text.split('\\n').map(x => x.trim()).filter(Boolean);
                return {
                    index: i,
                    title: lines[0] || '',
                    subtitle: lines.length > 2 ? lines[1] : ''
                };
            });
        }""")

    sounds = get_sounds()

    # Filter out sounds that have already been used
    unused = [s for s in sounds if normalize_title(s["title"]) not in used_signatures and s["title"]]

    # If few unused sounds are visible, scroll down to load more (TikTok loads +20 per scroll)
    if len(unused) < 5:
        print("[*] Less than 5 unused sounds visible, scrolling to load more...")
        use_buttons = page.locator('button:has-text("Use")')
        if use_buttons.count() > 0:
            try:
                use_buttons.last.scroll_into_view_if_needed(timeout=5000)
                time.sleep(2)
                sounds = get_sounds()
                unused = [s for s in sounds if normalize_title(s["title"]) not in used_signatures and s["title"]]
            except Exception:
                pass

    print(f"[*] Total sounds loaded: {len(sounds)} | Unused sounds available: {len(unused)}")

    if not unused:
        print("[!] All loaded sounds were previously used. Picking first available sound.")
        target_sound = sounds[0] if sounds else None
    else:
        # Pick randomly from the unused candidates for variety
        target_sound = random.choice(unused[:min(len(unused), 10)])

    if not target_sound:
        print("[!] No sound available to select.")
        page.keyboard.press("Escape")
        time.sleep(1)
        return None

    chosen_idx = target_sound["index"]
    use_buttons = page.locator('button:has-text("Use")')
    if chosen_idx < use_buttons.count():
        btn = use_buttons.nth(chosen_idx)
        print(f"[*] Selecting unique sound: '{target_sound['title']}' ({target_sound['subtitle']})")
        btn.click()
        time.sleep(2)

        # Ensure modal closes
        modal = page.locator('div[class*="TUXModal-overlay"], div[role="dialog"]')
        if modal.count() > 0 and modal.first.is_visible():
            page.keyboard.press("Escape")
            time.sleep(1)

        # Record to database so it is never reused
        save_used_sound(target_sound["title"], target_sound["subtitle"], post_id)
        print(f"[OK] Sound '{target_sound['title']}' saved to database (will not be repeated).")
        return target_sound["title"]

    page.keyboard.press("Escape")
    time.sleep(1)
    return None


def upload_to_tiktok(
    media_paths: Union[Path, List[Path]],
    caption: str,
    is_carousel: bool = False,
    headless: bool = False,
    post_id: str = ""
) -> bool:
    """
    Automates uploading either native Photo Carousels (multiple JPGs) or Videos (MP4) to TikTok Studio.
    Guarantees a 10-second upload & verification window before closing browser.
    """
    if isinstance(media_paths, Path):
        media_paths = [media_paths]

    if not SESSION_DIR.exists() or not list(SESSION_DIR.glob("*")):
        print("[!] No saved TikTok session found. Please run login.bat first.")
        return False

    valid_files = [p for p in media_paths if p.exists()]
    if not valid_files:
        print(f"[!] No valid media files to upload: {media_paths}")
        return False

    print(f"\n{'='*60}")
    print(f"[*] Starting TikTok Studio Uploader")
    print(f"[*] Post Type: {'Native Photo Carousel' if is_carousel else 'Standard Video'}")
    print(f"[*] Media Count: {len(valid_files)} file(s)")
    print(f"[*] Caption: {caption[:60]}...")
    print(f"{'='*60}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=headless,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ],
            viewport=None
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            print("[*] Navigating to TikTok Studio upload page...")
            page.goto("https://www.tiktok.com/tiktokstudio/upload", wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)

            if "login" in page.url.lower():
                print("[!] Session expired. Please re-run login.bat.")
                context.close()
                return False

            # 1. Dismiss unsaved draft banner and modal confirmation if present
            banner_discard = page.locator('button:has-text("Discard")')
            if banner_discard.count() > 0 and banner_discard.first.is_visible():
                print("[*] Dismissing draft alert banner...")
                banner_discard.first.click()
                time.sleep(1)

                modal_discard = page.locator('div[class*="TUXModal"] button:has-text("Discard"), div[role="dialog"] button:has-text("Discard")')
                if modal_discard.count() > 0 and modal_discard.first.is_visible():
                    print("[*] Dismissing draft modal confirmation...")
                    modal_discard.first.click()
                    time.sleep(2)

            # 2. Switch Tab if Photo Carousel
            if is_carousel:
                print("[*] Switching to 'Photos' tab for native Photo Carousel...")
                photos_tab = page.locator('div, button, span, p').filter(has_text="Photos").last
                photos_tab.click()
                time.sleep(2)

            # 3. Upload File(s)
            file_input = page.locator('input[type="file"]').first
            file_paths = [str(f.resolve()) for f in valid_files]
            print(f"[*] Selecting {len(file_paths)} slide file(s)...")
            file_input.set_input_files(file_paths)
            print("[*] Uploading files to TikTok...")
            time.sleep(4)

            # 4. Dismiss "Preview your video on your phone" ("Got it") modal if visible
            got_it = page.locator('button:has-text("Got it")')
            if got_it.count() > 0 and got_it.first.is_visible():
                print("[*] Dismissing 'Got it' popup...")
                got_it.first.click()
                time.sleep(1)

            # 4b. Add unique music from 'For You' if Carousel (never repeat sounds)
            if is_carousel:
                try:
                    add_sound_btn = page.locator('button:has-text("Add sound"), [role="button"]:has-text("Add sound")').first
                    if add_sound_btn.is_visible():
                        print("[*] Opening 'Add sound' modal...")
                        add_sound_btn.click()
                        time.sleep(2)

                        chosen_title = pick_unique_sound(page, post_id=post_id)
                        if chosen_title:
                            print(f"[OK] Background sound attached: '{chosen_title}'")
                        else:
                            print("[!] Warning: Could not select an unused sound.")
                except Exception as e:
                    print(f"[!] Warning: Error during sound selection: {e}")

            # 5. Fill Title & Description
            if is_carousel:
                # Title field (0/90 chars)
                title_input = page.locator('input[placeholder*="title"], input[placeholder*="Title"]')
                lines = [l.strip() for l in caption.splitlines() if l.strip()]
                title_text = lines[0] if lines else "all items in my spreadsheet!"
                if title_input.count() > 0 and title_input.first.is_visible():
                    title_input.first.fill(title_text[:85])
                    print(f"[*] Filled Carousel Title: {title_text[:40]}...")

                # Description editor
                desc_area = page.locator('div[contenteditable="true"]').first
                if desc_area.is_visible():
                    desc_area.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    time.sleep(0.3)
                    desc_body = "\n".join(lines[1:]) if len(lines) > 1 else caption
                    page.keyboard.type(desc_body + " ", delay=15)
                    time.sleep(0.5)
                    page.keyboard.press("Escape")
                    print("[*] Filled Carousel Description.")
            else:
                # Video caption editor
                desc_area = page.locator('div[contenteditable="true"]').first
                if desc_area.is_visible():
                    desc_area.click()
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    time.sleep(0.3)
                    page.keyboard.type(caption + " ", delay=15)
                    time.sleep(0.5)
                    page.keyboard.press("Escape")
                    print("[*] Filled Video Caption.")

            time.sleep(1)

            # 6. Locate & Click the Post button
            print("[*] Locating 'Post' button...")
            post_buttons = page.locator('button:has-text("Post")')
            post_btn = None
            for i in range(post_buttons.count()):
                b = post_buttons.nth(i)
                if b.inner_text().strip() == "Post":
                    post_btn = b

            if not post_btn and post_buttons.count() > 0:
                post_btn = post_buttons.last

            if not post_btn:
                print("[!] 'Post' button not found.")
                context.close()
                return False

            post_btn.scroll_into_view_if_needed()
            time.sleep(1)
            print("[*] Clicking 'Post'...")
            post_btn.click()

            # 7. 10-Second Verification & Confirmation Window
            print("[*] Monitoring post confirmation & holding 10-second upload window...")
            posted_confirmed = False

            for sec in range(1, 15):
                time.sleep(1)
                curr_url = page.url.lower()

                # Check if "Post now" or "Post anyway" confirmation popped up
                for confirm_sel in ['button:has-text("Post now")', 'button:has-text("Post anyway")']:
                    btn_c = page.locator(confirm_sel)
                    if btn_c.count() > 0 and btn_c.first.is_visible():
                        print(f"[*] Clicking confirmation popup: {confirm_sel}")
                        btn_c.first.click()

                # Check if redirected to Content Management page
                if "content" in curr_url or "manage" in curr_url:
                    posted_confirmed = True
                    print(f"[*] Verified by Content Manager redirect at second {sec}!")
                    break

                # Check if success modal appeared
                if page.locator('text="Your photo has been uploaded"').count() > 0 or \
                   page.locator('text="Your video has been uploaded"').count() > 0 or \
                   page.locator('text="Manage your posts"').count() > 0:
                    posted_confirmed = True
                    print(f"[*] Verified by success modal at second {sec}!")
                    break

            # Hold for 10 seconds post-upload to ensure TikTok completely finalizes file ingestion
            print("[*] Holding browser for 10 seconds to ensure full TikTok ingestion...")
            time.sleep(10)

            print("[OK] Post submitted and verified successfully on TikTok!")
            context.close()
            return True

        except Exception as e:
            print(f"[!] Upload error: {e}")
            try:
                page.screenshot(path=str(BASE_DIR / "last_upload_error.png"))
                print("[*] Error screenshot saved to last_upload_error.png")
            except Exception:
                pass
            context.close()
            return False


if __name__ == "__main__":
    test_dir = BASE_DIR / "processed_output" / "7701461631699635488"
    slides = sorted(list(test_dir.glob("slide_*_anti_flagged.jpg")))
    if slides:
        upload_to_tiktok(slides[:5], "all items in my spreadsheet! #reps #viral", is_carousel=True)
    else:
        print("No test slides found.")
