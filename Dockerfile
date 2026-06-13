FROM python:3.12-slim

# ffmpeg is required by yt-dlp to merge video+audio and extract MP3.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

# Token and other settings are provided via environment variables at runtime.
CMD ["python", "-m", "bot.main"]
