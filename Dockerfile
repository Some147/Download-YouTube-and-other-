FROM python:3.12-slim

# ffmpeg merges video+audio / extracts MP3. curl+unzip are used to install
# Deno, the JS runtime yt-dlp needs to solve YouTube's n-challenge
# (see https://github.com/yt-dlp/yt-dlp/wiki/EJS).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (recommended runtime; yt-dlp auto-detects it on PATH).
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Token and other settings are provided via environment variables at runtime.
CMD ["python", "-m", "bot.main"]
