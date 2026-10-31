"""
One-Time TikTok Login Script.
Opens a Chromium window using a persistent session directory.
Log into your TikTok account once, and the session will be saved for automated uploading.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.resolve()
SESSION_DIR = BASE_DIR / "tiktok_session"


def login():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    print("==========================================================")
    print("           TikTok One-Time Login Setup                    ")
    print("==========================================================\n")
    print("[*] Opening Chromium browser window...")
    print("[*] Please log into your TikTok profile in the browser.")
    print("[*] You can log in via QR code, Google, Email, or Phone.\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ],
            viewport=None
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="networkidle")

        print("----------------------------------------------------------")
        print(">> Log into your TikTok account in the browser.")
        print(">> When you are logged in and see your TikTok home feed,")
        print(">> press [ENTER] in this terminal window to finish and save.")
        print("----------------------------------------------------------\n")

        try:
            input("Press [ENTER] here AFTER you have logged in...")
        except KeyboardInterrupt:
            pass

        # Give it a moment to write cookies to disk
        time.sleep(2)
        context.close()

    print("\n[OK] Success! Your login session has been saved to:")
    print(f"     {SESSION_DIR}")
    print("[*] The automated reposter can now upload to your profile.\n")


if __name__ == "__main__":
    login()
