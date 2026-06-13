"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_dotenv() -> None:
    """Minimal .env loader so the bot works without extra dependencies."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Do not override variables already present in the environment.
        os.environ.setdefault(key, value)


def _parse_user_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                continue
    return ids


@dataclass
class Config:
    bot_token: str
    max_filesize_mb: int = 50
    download_dir: Path = field(default_factory=lambda: Path("downloads"))
    allowed_user_ids: set[int] = field(default_factory=set)
    cookies_file: Optional[Path] = None

    @property
    def max_filesize_bytes(self) -> int:
        return self.max_filesize_mb * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()

        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Copy .env.example to .env and add your token "
                "from @BotFather."
            )

        try:
            max_mb = int(os.environ.get("MAX_FILESIZE_MB", "50"))
        except ValueError:
            max_mb = 50

        download_dir = Path(os.environ.get("DOWNLOAD_DIR", "downloads"))
        download_dir.mkdir(parents=True, exist_ok=True)

        allowed = _parse_user_ids(os.environ.get("ALLOWED_USER_IDS", ""))

        # Optional cookies file (Netscape format) to bypass "confirm you're not
        # a bot" checks on YouTube and to access age/region-restricted content.
        cookies_file: Optional[Path] = None
        raw_cookies = os.environ.get("COOKIES_FILE", "").strip()
        if not raw_cookies and Path("cookies.txt").is_file():
            raw_cookies = "cookies.txt"
        if raw_cookies:
            candidate = Path(raw_cookies)
            # is_file() guards against an empty bind-mount showing up as a dir.
            if candidate.is_file():
                cookies_file = candidate

        return cls(
            bot_token=token,
            max_filesize_mb=max_mb,
            download_dir=download_dir,
            allowed_user_ids=allowed,
            cookies_file=cookies_file,
        )
