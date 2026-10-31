# 🚀 TikTok Auto-Reposter & Mirroring Bot

An autonomous, production-ready tool to mirror and repost content from any public TikTok profile to your own account. Supports **native swipeable photo carousels**, **anti-flagging transformations**, **smart sound selection with zero duplicate tracks**, and **persistent cooldown timing**.

---

## ✨ Features

- **📸 Native Swipeable Photo Carousels**:
  Uploads multi-slide image posts directly to TikTok Studio's native `Photos` tab. Never degrades carousels into flat MP4 videos.

- **🛡️ Multi-Layer Anti-Flagging Engine**:
  Bypasses TikTok's "Unoriginal Content" and FYP suppression filters:
  - Complete EXIF/metadata stripping.
  - Sub-pixel micro-cropping (1.5%) to break perceptual hashes.
  - Micro-adjustments to contrast (+3%), saturation (+4%), and brightness.
  - Video speed adjustments (1.02x) and audio tempo modifications.
  - Automated hashtag & caption spinning.

- **🎵 Trending Sound Auto-Selection (No Duplicate Tracks)**:
  - Automatically queries TikTok Studio's "For You" sound library.
  - Maintains a persistent database (`used_sounds.json`) so **no song is ever repeated twice**.
  - Dynamically infinite-scrolls the sounds list to load new fresh tracks as your catalog grows.

- **⏳ Persistent Cooldown & Resume**:
  - Paced publishing (default 2–3 hours) to prevent spam shadowbans.
  - State is saved to disk: **Closing CMD or shutting down your PC does NOT reset the timer**. The countdown seamlessly picks up right where it left off.

- **🪟 Windows Auto-Start on Boot**:
  - Includes one-click scripts to launch minimized in your Windows taskbar whenever your PC powers on.

- **0️⃣ Zero Paid API Keys Required**:
  - Uses browser automation and native reverse-engineered scraping. 100% free to run.

---

## 📋 Requirements

1. **Operating System**: Windows 10/11 (or Linux/macOS with minor batch script adaptations).
2. **Python**: Python 3.10 or newer.
3. **FFmpeg**: Installed and added to system `PATH` (required for video processing).

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/tiktok-auto-reposter.git
cd tiktok-auto-reposter
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Your Settings
Copy the example config:
```bash
copy config.example.json config.json
```
Edit `config.json`:
```json
{
  "source_username": "target_account_username",
  "check_interval_minutes": 180,
  "caption_settings": {
    "strip_original_hashtags": true,
    "new_hashtags": "#reps #spreadsheet #fyp #viral"
  }
}
```

### 4. Authenticate Your TikTok Account
Run the login helper to log in to your destination TikTok account once:
```bash
login.bat
```
*(A browser window will open. Log in via QR code, email, or username. Once on the homepage, close the window. Your session cookies are securely saved locally in `tiktok_session/` and will never be shared).*

### 5. Start the Reposter
```bash
start_scheduler.bat
```
The bot will:
1. Scan the target account and organize all posts from oldest to newest into `queue.json`.
2. Process the next post with anti-flagging transformations.
3. Open TikTok Studio, upload the media, attach a fresh trending track, and publish.
4. Begin the countdown for the next post.

---

## ⚙️ Configuration Reference (`config.json`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `source_username` | string | `""` | The public TikTok handle to mirror (without `@`). |
| `check_interval_minutes` | int | `180` | Delay between posts (180 mins = 3-4 posts/day for optimal FYP reach). |
| `headless_browser` | bool | `false` | Run browser invisibly (keep `false` for higher TikTok trust scores). |
| `video_modifications.crop_percent` | float | `1.5` | Percentage of video border cropped to alter hash. |
| `video_modifications.speed_multiplier` | float | `1.02` | Slight speed boost to bypass audio/video fingerprints. |
| `carousel_modifications.strip_exif` | bool | `true` | Strips all camera and timestamp metadata from image slides. |
| `caption_settings.new_hashtags` | string | `"#fyp #viral"` | Custom hashtags appended to every post. |

---

## 🔄 Managing the Queue

- **Auto-Start on Boot**:
  Double-click `enable_autostart.bat` to have the scheduler start quietly in your taskbar whenever Windows boots.
  To disable: double-click `disable_autostart.bat`.

- **Reset Queue**:
  If you ever want to re-run from post #1:
  ```bash
  python reset_queue.py
  ```

---

## 📁 Project Structure

```text
├── anti_reposter.py        # Video/image transformations & caption spin engine
├── build_queue.py          # Scraper & chronological post cataloger
├── playwright_uploader.py  # Browser automation for TikTok Studio
├── scheduler.py            # Persistent queue daemon & cooldown timer
├── login_tiktok.py         # Persistent session authenticator
├── login.bat               # 1-click login launcher
├── start_scheduler.bat     # 1-click scheduler launcher
├── enable_autostart.bat    # Windows Startup shortcut creator
├── disable_autostart.bat   # Windows Startup shortcut remover
├── reset_queue.py          # Queue reset utility
├── config.example.json     # Configuration template
└── requirements.txt        # Python package dependencies
```

---

## ⚠️ Disclaimer

This tool is created for educational and archival purposes. Please respect intellectual property rights and TikTok's Community Guidelines. Use responsible posting intervals (2–4 hours) to avoid account suppression.
