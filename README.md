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

### Option 3 — Koyeb (free, deploy from GitHub via Docker)

Koyeb has a free instance and builds straight from the `Dockerfile`. Because the
bot uses polling (no HTTP port), deploy it as a **Worker** service so Koyeb
doesn't run an HTTP health check against it.

1. On [koyeb.com](https://www.koyeb.com): **Create Service → GitHub** and pick
   this repository / branch (authorize the Koyeb GitHub app if asked).
2. **Builder:** choose **Dockerfile** (Koyeb auto-detects it).
3. **Service type:** select **Worker** (not Web). This skips port/health checks.
4. **Environment variables** → add:
   - `BOT_TOKEN` — your @BotFather token (**required**)
   - `MAX_FILESIZE_MB` — optional (default `50`)
   - `ALLOWED_USER_IDS` — optional, comma-separated
5. **Instance:** pick the **Free** instance, then **Deploy**.
6. Watch the **Runtime logs** for `Bot started.`, then message your bot.

> ⚠️ Set the token only in Koyeb env vars — never commit it to the repo.
> If you accidentally pick a *Web* service type, Koyeb will mark the deploy
> unhealthy because the bot opens no port — switch the type to **Worker**.

> A `railway.json` is also included if you ever switch back to Railway.

## YouTube on a server ("confirm you're not a bot")

YouTube blocks requests from datacenter IPs (most VPS/cloud providers) and asks
to "Sign in to confirm you're not a bot", or returns no audio formats
("Requested format is not available"). This bot follows the upstream
[yt-dlp guidance](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies):

**1. Provide cookies (export them the way yt-dlp recommends):**
   - Open a **new private/incognito window** and log into YouTube.
   - In the same tab, open `https://www.youtube.com/robots.txt`.
   - Export `youtube.com` cookies to `cookies.txt` (Netscape format) with an
     extension like *Get cookies.txt LOCALLY*.
   - **Close the incognito window** (do not log out — that invalidates the cookies).
   - Upload `cookies.txt` next to `docker-compose.yml` (it is mounted automatically),
     then `docker compose restart`.

**2. JavaScript runtime:** YouTube requires solving a JS "n-challenge" or it
   returns only storyboard images. Per the
   [EJS guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS), the Docker image
   installs **Deno** and `yt-dlp[default]` (the EJS solver scripts) so yt-dlp can
   solve it. If you run the bot without Docker, install Deno (≥2.3.0) and
   `pip install -U "yt-dlp[default]"` yourself.

**3. Player clients:** the bot asks yt-dlp to try the `tv` / `web_embedded` /
   `android_vr` clients, which per the
   [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) do **not**
   require a PO Token, before the default web client.

> ⚠️ YouTube is gradually enforcing **PO Tokens**, which yt-dlp cannot generate
> itself. If cookies + the clients above stop working, you need a
> [PO Token Provider plugin](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
> (e.g. bgutil) — this is an upstream YouTube limitation, not a bot bug.

The bot auto-detects `cookies.txt`, or set a custom path via `COOKIES_FILE`.
Other sites (Instagram posts/Reels, TikTok, etc.) usually work without cookies;
Instagram **stories** additionally require active (≤24h) content and valid
`instagram.com` cookies.

> When changing anything related to YouTube/format selection/cookies, always
> cross-check the current [yt-dlp docs](https://github.com/yt-dlp/yt-dlp) and
> wiki first — YouTube changes often and upstream is the source of truth.

## Sending files larger than 50 MB

The cloud Bot API caps bot uploads at **50 MB**. To send up to **2000 MB**, run
the bundled [local Bot API server](https://github.com/tdlib/telegram-bot-api)
(included as an optional `bigfiles` compose profile):

1. Get an **`api_id`** and **`api_hash`** from https://my.telegram.org (free).
2. In `.env` set:
   ```
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=your_api_hash
   BOT_API_BASE=http://telegram-bot-api:8081
   MAX_FILESIZE_MB=2000
   ```
3. Start both the bot and the local server:
   ```bash
   docker compose --profile bigfiles up -d --build
   ```

The bot then routes through the local server (`base_url`) and can upload large
files. To go back to the cloud API, clear `BOT_API_BASE` and run plain
`docker compose up -d`.

> A bot token can only run on one Bot API server at a time. If switching gives
> a 409/"token used by another server" error, call
> `https://api.telegram.org/bot<token>/logOut` once, then start the local server.
> Large videos also use more disk, bandwidth, and CPU (transcoding) on your VPS.

## Notes & limits

- Respect the copyright and terms of service of the sites you download from.

## License

MIT
