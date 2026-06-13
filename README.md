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

## Notes & limits

- Telegram bots can upload files up to **50 MB** by default. For larger files,
  run your own [local Bot API server](https://github.com/tdlib/telegram-bot-api)
  (up to 2000 MB) and raise `MAX_FILESIZE_MB`.
- Respect the copyright and terms of service of the sites you download from.

## License

MIT
