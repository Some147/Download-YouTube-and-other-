"""Video downloading logic built on top of yt-dlp."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


class DownloadError(Exception):
    """Raised when a download cannot be completed."""


@dataclass
class DownloadResult:
    path: Path
    title: str
    filesize: int
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[int] = None


@dataclass
class MediaInfo:
    title: str
    uploader: Optional[str]
    duration: Optional[int]
    webpage_url: str


def _filesize_format(fmt: str) -> str:
    """Build a yt-dlp format string with a height cap.

    ``fmt`` is one of: ``best``, ``720``, ``480``, ``audio``.
    """
    if fmt == "audio":
        return "bestaudio/best"
    if fmt in {"720", "480", "360"}:
        height = fmt
        return (
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={height}][ext=mp4]/best[height<={height}]/best"
        )
    # default "best"
    return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"


def _apply_cookies(opts: dict, cookies_file: Optional[Path]) -> None:
    if cookies_file and cookies_file.exists():
        opts["cookiefile"] = str(cookies_file)


def probe(url: str, cookies_file: Optional[Path] = None) -> MediaInfo:
    """Fetch metadata for a URL without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    _apply_cookies(opts, cookies_file)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    if info is None:
        raise DownloadError("Could not extract media information.")

    # For playlists, fall back to the first entry.
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    return MediaInfo(
        title=info.get("title") or "video",
        uploader=info.get("uploader"),
        duration=info.get("duration"),
        webpage_url=info.get("webpage_url") or url,
    )


def download(
    url: str,
    download_dir: Path,
    fmt: str = "best",
    max_filesize_bytes: Optional[int] = None,
    progress_hook: Optional[Callable[[dict], None]] = None,
    cookies_file: Optional[Path] = None,
) -> DownloadResult:
    """Download a video/audio file and return its path.

    Raises :class:`DownloadError` on failure or if the result exceeds
    ``max_filesize_bytes``.
    """
    download_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    outtmpl = str(download_dir / f"{token}_%(title).80s.%(ext)s")

    opts: dict = {
        "format": _filesize_format(fmt),
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    if fmt == "audio":
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # Ensure the final container is mp4 when merging is needed.
        opts["merge_output_format"] = "mp4"

    if max_filesize_bytes:
        # Reject formats whose size is known to exceed the limit up front.
        opts["max_filesize"] = max_filesize_bytes

    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]

    _apply_cookies(opts, cookies_file)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise DownloadError("Download produced no result.")
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]
            filepath = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    # Account for postprocessor extension changes (e.g. .webm -> .mp3/.mp4).
    if not filepath.exists():
        candidates = sorted(download_dir.glob(f"{token}_*"))
        if not candidates:
            raise DownloadError("Downloaded file could not be located.")
        filepath = candidates[0]

    filesize = filepath.stat().st_size
    if max_filesize_bytes and filesize > max_filesize_bytes:
        filepath.unlink(missing_ok=True)
        raise DownloadError(
            f"File is too large ({filesize / 1024 / 1024:.1f} MB) to send via Telegram."
        )

    width, height = _extract_dimensions(info)

    return DownloadResult(
        path=filepath,
        title=info.get("title") or filepath.stem,
        filesize=filesize,
        width=width,
        height=height,
        duration=info.get("duration"),
    )


def _extract_dimensions(info: dict) -> tuple[Optional[int], Optional[int]]:
    """Pull video width/height so Telegram renders the correct aspect ratio.

    For merged downloads the top-level ``width``/``height`` may be missing, so
    fall back to the video stream listed in ``requested_formats``.
    """
    width = info.get("width")
    height = info.get("height")
    if not (width and height):
        for fmt in info.get("requested_formats") or []:
            if fmt.get("width") and fmt.get("height"):
                width, height = fmt["width"], fmt["height"]
                break
    return width, height
