"""Video downloading logic built on top of yt-dlp."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

logger = logging.getLogger(__name__)

# YouTube hides formats from the web client on server IPs (causing "Requested
# format is not available" / "Sign in to confirm you're not a bot"). Per the
# yt-dlp PO Token Guide, the tv / web_embedded / android_vr clients do not
# require a PO Token, so prefer them before falling back to the default client.
_EXTRACTOR_ARGS = {
    "youtube": {"player_client": ["default", "tv", "web_embedded", "android_vr"]}
}


class _YtdlpLogger:
    """Forwards yt-dlp's own messages into our logs so failures are visible."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        logger.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        logger.error("yt-dlp: %s", msg)


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
    # Prefer H.264 video for mobile, but never drop audio: accept any audio
    # codec (transcode fixes it later) and fall back to a combined stream that
    # already contains audio (e.g. HLS / format 18) when no separate audio-only
    # track is offered.
    compat = "[vcodec~='^(avc|h264)']"
    if fmt in {"720", "480", "360"}:
        h = fmt
        return (
            f"bv*[height<={h}]{compat}+ba/"
            f"bv*[height<={h}]+ba/"
            f"b[height<={h}]{compat}/b[height<={h}]/bv*+ba/b"
        )
    # default "best"
    return f"bv*{compat}+ba/bv*+ba/b{compat}/b"


def _apply_cookies(opts: dict, cookies_file: Optional[Path]) -> None:
    if not (cookies_file and cookies_file.is_file()):
        return
    # yt-dlp rewrites the cookie file when it closes, which fails if the file is
    # mounted read-only. Work on a writable copy so the original is left intact.
    try:
        tmp = Path(tempfile.gettempdir()) / "ytdlp_cookies.txt"
        shutil.copyfile(cookies_file, tmp)
        opts["cookiefile"] = str(tmp)
    except OSError:
        opts["cookiefile"] = str(cookies_file)


def probe(url: str, cookies_file: Optional[Path] = None) -> MediaInfo:
    """Fetch metadata for a URL without downloading."""
    opts = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 30,
        "logger": _YtdlpLogger(),
        "extractor_args": _EXTRACTOR_ARGS,
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
        "socket_timeout": 30,
        "logger": _YtdlpLogger(),
        "extractor_args": _EXTRACTOR_ARGS,
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
            filepath = _resolve_output_path(info, ydl, download_dir, token)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    logger.info(
        "Downloaded: vcodec=%s acodec=%s ext=%s (%s)",
        info.get("vcodec"), info.get("acodec"), info.get("ext"), filepath.name,
    )

    if fmt != "audio":
        _make_mobile_compatible(filepath)

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


def _resolve_output_path(info: dict, ydl, download_dir: Path, token: str) -> Path:
    """Find the real downloaded file (the merged video, not a leftover fragment).

    After merging, yt-dlp may leave the separate audio/video parts on disk
    (e.g. ``*.f251.webm``). Trust the path yt-dlp records first, and only fall
    back to scanning — picking the largest file, never a small audio fragment.
    """
    def _complete(p: Path) -> bool:
        # Ignore yt-dlp's in-progress/partial files.
        return p.exists() and p.suffix not in (".part", ".ytdl", ".temp")

    # yt-dlp records the final, post-merge/post-process path here.
    for entry in info.get("requested_downloads") or []:
        fp = entry.get("filepath")
        if fp and _complete(Path(fp)):
            return Path(fp)
    fp = info.get("filepath")
    if fp and _complete(Path(fp)):
        return Path(fp)

    candidate = Path(ydl.prepare_filename(info))
    if _complete(candidate):
        return candidate

    # Last resort: the largest *complete* file is the merged video.
    files = sorted(
        (p for p in download_dir.glob(f"{token}_*") if _complete(p)),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not files:
        # Only partial files left — the download was aborted, usually because
        # the video exceeded the Telegram size limit mid-download.
        raise DownloadError(
            "Video is too large to send via Telegram. Try a lower quality "
            "(480p) or Audio."
        )
    return files[0]


def _probe_streams(path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (vcodec, pix_fmt, acodec) of the first video/audio streams."""
    def q(select: str, entries: str) -> list[str]:
        try:
            return subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", select,
                    "-show_entries", entries, "-of", "default=nw=1:nk=1", str(path),
                ],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout.split()
        except (subprocess.SubprocessError, OSError):
            return []

    v = q("v:0", "stream=codec_name,pix_fmt")
    a = q("a:0", "stream=codec_name")
    vcodec = v[0] if len(v) > 0 else None
    pix = v[1] if len(v) > 1 else None
    acodec = a[0] if len(a) > 0 else None
    return vcodec, pix, acodec


def _make_mobile_compatible(path: Path) -> None:
    """Ensure the video AND audio play on mobile Telegram.

    Mobile players only decode H.264 video (8-bit yuv420p) and AAC audio.
    Anything else (VP9/AV1/HEVC video, or Opus audio) plays on desktop but
    shows only a thumbnail and/or has no sound on phones. Re-encode only the
    streams that need it; if everything is already compatible just move the
    moov atom to the front (fast stream copy) for streaming.
    """
    if not path.exists():
        return
    vcodec, pix, acodec = _probe_streams(path)
    video_ok = vcodec == "h264" and pix in (None, "yuv420p", "yuvj420p")
    # None acodec means there is no audio track -> nothing to fix.
    audio_ok = acodec in (None, "aac")

    # -map keeps the first video + first audio track (the "?" makes audio
    # optional) so the audio is never dropped during the pass.
    maps = ["-map", "0:v:0?", "-map", "0:a:0?"]
    out = path.with_name(path.stem + "_mc.mp4")
    if video_ok and audio_ok:
        vcodec_args = ["-c", "copy"]
    elif video_ok and not audio_ok:
        # Video is fine; only the audio (e.g. Opus) needs converting to AAC.
        logger.info("Re-encoding audio %s -> aac for %s", acodec, path.name)
        vcodec_args = ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k"]
    else:
        logger.info("Transcoding %s (%s/%s) to H.264/AAC", path.name, vcodec, acodec)
        vcodec_args = [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        ]
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
        *maps, *vcodec_args, "-movflags", "+faststart", str(out),
    ]
    timeout = 180 if (video_ok and audio_ok) else 1800
    try:
        subprocess.run(cmd, check=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Mobile-compat pass failed (%s); sending original", exc)
        out.unlink(missing_ok=True)
        return
    out.replace(path)


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
