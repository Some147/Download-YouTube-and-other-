"""Telegram bot entry point.

Run with: python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from functools import partial

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Config
from . import downloader

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s]+")

WELCOME = (
    "👋 *Загрузчик видео*\n\n"
    "Пришлите мне ссылку на видео с YouTube, Twitter/X, TikTok, Instagram, "
    "Vimeo и 1000+ других сайтов — и я скачаю его для вас."
)

HELP = (
    "*Как пользоваться:*\n"
    "1. Пришлите ссылку на видео.\n"
    "2. Выберите качество / формат.\n"
    "3. Дождитесь файла.\n\n"
    "*Команды:*\n"
    "/start — показать приветствие\n"
    "/help — показать эту справку\n\n"
    "_Внимание: Telegram ограничивает размер загружаемых ботом файлов, "
    "поэтому очень большие видео могут не отправиться. Попробуйте качество "
    "пониже или только аудио._"
)


def _is_allowed(config: Config, update: Update) -> bool:
    if not config.allowed_user_ids:
        return True
    user = update.effective_user
    return bool(user and user.id in config.allowed_user_ids)


def _format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(WELCOME, disable_web_page_preview=True)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(HELP, disable_web_page_preview=True)


async def on_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE, config: Config
) -> None:
    if not _is_allowed(config, update):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    match = URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text(
            "Пришлите корректную ссылку на видео (начинается с http:// или https://)."
        )
        return

    url = match.group(0)
    status = await update.message.reply_text("🔎 Проверяю ссылку…")

    try:
        info = await asyncio.to_thread(downloader.probe, url, config.cookies_file)
    except downloader.DownloadError as exc:
        await status.edit_text(f"❌ Не удалось прочитать эту ссылку.\n\n`{_clip(str(exc))}`",
                               parse_mode="Markdown")
        return

    # Store URL behind a short token so it fits in callback_data.
    token = uuid.uuid4().hex[:10]
    context.chat_data[token] = url

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📹 Best", callback_data=f"dl:{token}:best"),
                InlineKeyboardButton("720p", callback_data=f"dl:{token}:720"),
                InlineKeyboardButton("480p", callback_data=f"dl:{token}:480"),
            ],
            [InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl:{token}:audio")],
        ]
    )

    duration = _format_duration(info.duration)
    caption = f"*{_clip(info.title, 200)}*"
    if info.uploader:
        caption += f"\n👤 {info.uploader}"
    if duration:
        caption += f"\n⏱ {duration}"
    caption += "\n\nВыберите формат:"

    await status.edit_text(
        caption, reply_markup=keyboard, parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def on_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, config: Config
) -> None:
    query = update.callback_query
    await query.answer()

    try:
        _, token, fmt = query.data.split(":", 2)
    except ValueError:
        await query.edit_message_text("⚠️ Некорректный выбор.")
        return

    url = context.chat_data.get(token)
    if not url:
        await query.edit_message_text(
            "⚠️ Срок запроса истёк. Пришлите ссылку ещё раз."
        )
        return

    await query.edit_message_text("⏬ Скачиваю…")
    chat_id = query.message.chat_id

    await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)

    try:
        result = await asyncio.to_thread(
            downloader.download,
            url,
            config.download_dir,
            fmt,
            config.max_filesize_bytes,
            None,
            config.cookies_file,
        )
    except downloader.DownloadError as exc:
        await query.edit_message_text(
            f"❌ Не удалось скачать.\n\n`{_clip(str(exc))}`", parse_mode="Markdown"
        )
        return

    await query.edit_message_text("📤 Загружаю в Telegram…")

    try:
        with result.path.open("rb") as fh:
            if fmt == "audio":
                await context.bot.send_audio(
                    chat_id, fh, title=result.title, read_timeout=120,
                    write_timeout=120,
                )
            else:
                await context.bot.send_video(
                    chat_id, fh, caption=result.title, supports_streaming=True,
                    width=result.width, height=result.height,
                    duration=result.duration,
                    read_timeout=120, write_timeout=120,
                )
        await query.edit_message_text("✅ Готово!")
    except Exception as exc:  # noqa: BLE001 - surface upload errors to the user
        logger.exception("Failed to send file")
        await query.edit_message_text(
            f"❌ Не удалось отправить файл.\n\n`{_clip(str(exc))}`",
            parse_mode="Markdown",
        )
    finally:
        result.path.unlink(missing_ok=True)
        context.chat_data.pop(token, None)


def _clip(text: str, limit: int = 300) -> str:
    text = text.strip().replace("`", "'")
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error", exc_info=context.error)


async def _post_init(app: Application) -> None:
    """Register the Telegram commands menu (the button next to the input box)."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Запустить / показать приветствие"),
            BotCommand("help", "Как пользоваться ботом"),
        ]
    )


def build_application(config: Config) -> Application:
    app = Application.builder().token(config.bot_token).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Entity("url") & ~filters.COMMAND,
            partial(on_url, config=config),
        )
    )
    # Fallback: any text containing a URL even without a Telegram url entity.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(URL_RE),
            partial(on_url, config=config),
        )
    )
    app.add_handler(
        CallbackQueryHandler(partial(on_choice, config=config), pattern=r"^dl:")
    )
    app.add_error_handler(on_error)
    return app


def main() -> None:
    config = Config.from_env()
    app = build_application(config)
    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
