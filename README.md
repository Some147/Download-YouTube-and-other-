# 📥 Telegram Video Downloader Bot

A Telegram bot that downloads videos from **YouTube** and **1000+ other sites**
(Twitter/X, TikTok, Instagram, Vimeo, Facebook, etc.) using
[yt-dlp](https://github.com/yt-dlp/yt-dlp).

Send the bot a link → choose a quality / format → get the file back in Telegram.

## Features

- 🔗 Paste any supported video URL
- 🎚 Choose quality: **Best**, **720p**, **480p**, or **🎵 Audio (MP3)**
- 📊 Shows title, uploader and duration before downloading
- 🛡 Optional allow-list to restrict who can use the bot
- 📦 Enforces a max file size so uploads don't exceed Telegram limits

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (required by yt-dlp to merge/convert audio & video)
- A bot token from [@BotFather](https://t.me/BotFather)

Install ffmpeg:

```bash
# Debian / Ubuntu
sudo apt install ffmpeg
# macOS
brew install ffmpeg
```

## Setup

```bash
git clone https://github.com/Some147/Download-YouTube-and-other-.git
cd Download-YouTube-and-other-

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set BOT_TOKEN
```

## Configuration (`.env`)

| Variable           | Default     | Description                                                        |
| ------------------ | ----------- | ------------------------------------------------------------------ |
| `BOT_TOKEN`        | —           | **Required.** Token from @BotFather.                               |
| `MAX_FILESIZE_MB`  | `50`        | Max upload size. Telegram bots allow 50 MB (2000 MB via local API).|
| `DOWNLOAD_DIR`     | `downloads` | Temp directory for downloaded files (auto-cleaned).                |
| `ALLOWED_USER_IDS` | _(empty)_   | Comma-separated user IDs allowed to use the bot. Empty = everyone. |

## Run

```bash
python -m bot.main
```

Then open Telegram, find your bot and send it a video link.

## Project structure

```
bot/
├── __init__.py
├── config.py       # Loads settings from .env / environment
├── downloader.py   # yt-dlp wrapper (probe + download)
└── main.py         # Telegram handlers and entry point
```

## Running 24/7

The bot uses long-polling, so it just needs a process that stays alive. Pick one:

### Option 1 — Docker (recommended, works on any server)

```bash
cp .env.example .env        # set BOT_TOKEN
docker compose up -d --build
```

`restart: unless-stopped` brings the bot back automatically after crashes or
reboots. View logs with `docker compose logs -f`, stop with `docker compose down`.

### Option 2 — Linux VPS with systemd (no Docker)

```bash
sudo git clone https://github.com/Some147/Download-YouTube-and-other-.git /opt/Download-YouTube-and-other-
cd /opt/Download-YouTube-and-other-
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo apt-get install -y ffmpeg
cp .env.example .env        # set BOT_TOKEN

sudo cp deploy/telegram-downloader-bot.service /etc/systemd/system/
# edit User= / WorkingDirectory= in the unit if your paths differ
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-downloader-bot
```

`Restart=always` keeps it running. Follow logs: `journalctl -u telegram-downloader-bot -f`.

### Option 3 — Railway / Render (deploy from GitHub)

- Create a new project from this GitHub repo.
- The included `Procfile` runs `python -m bot.main` as a **worker** (not a web service).
- Add `BOT_TOKEN` (and optional `MAX_FILESIZE_MB`, `ALLOWED_USER_IDS`) as
  environment variables in the dashboard.

> ⚠️ Free tiers that "sleep" idle apps are not suitable for a polling bot — use a
> worker/always-on plan, or Docker/VPS above.

## Notes & limits

- Telegram bots can upload files up to **50 MB** by default. For larger files,
  run your own [local Bot API server](https://github.com/tdlib/telegram-bot-api)
  (up to 2000 MB) and raise `MAX_FILESIZE_MB`.
- Respect the copyright and terms of service of the sites you download from.

## License

MIT
