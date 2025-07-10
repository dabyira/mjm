import os
import re
import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from yt_dlp import YoutubeDL

TOKEN = "8146393797:AAESmjq0ApK-4e_qv_YO7uNTutWEkgtYWjM"
DOWNLOAD_DIR = "downloads"
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, "audio")
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, "video")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

user_links = {}
user_search = {}

WELCOME_MESSAGE = (
    "🎉 أهلاً بك في بوت التحميل المميز 🎶\n\n"
    "📌 للبحث في يوتيوب اكتب:\n"
    "يوت متبوع بكلمة البحث (مثال: يوت ناصيف زيتون)\n\n"
    "📥 يدعم روابط يوتيوب وتيك توك مباشرة\n"
    "⚡️ بواسطة: @zuz_4p"
)


def extract_url(text):
    yt_match = re.search(
        r"https?://(www\.)?youtube\.com/watch\?v=\S+|https?://youtu\.be/\S+", text
    )
    tt_match = re.search(r"https?://(www\.)?tiktok\.com/\S+", text)
    return yt_match.group(0) if yt_match else tt_match.group(0) if tt_match else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إرسال رسالة الترحيب بدون parse_mode لتجنب مشاكل الترميز
    await update.message.reply_text(WELCOME_MESSAGE)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    url = extract_url(text)
    if url:
        user_links[chat_id] = url
        buttons = [
            [InlineKeyboardButton("🎥 فيديو", callback_data="video")],
            [InlineKeyboardButton("🎧 صوت", callback_data="audio")],
        ]
        await update.message.reply_text(
            "📌 اختر نوع التحميل:", reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if text.startswith("يوت"):
        query = text[3:].strip()
        if not query:
            await update.message.reply_text("❌ الرجاء كتابة كلمة بحث بعد 'يوت'.")
            return

        await update.message.reply_text("🔍 يبحث الآن البوت على طلبك...")

        ydl_opts = {"quiet": True, "skip_download": True, "default_search": "ytsearch5"}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = info.get("entries", [])

        if not results:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")
            return

        user_search[chat_id] = results
        buttons = [
            [InlineKeyboardButton(f"{i+1}. {v['title'][:40]}", callback_data=f"select_{i}")]
            for i, v in enumerate(results)
        ]
        await update.message.reply_text(
            "🎬 اختر الفيديو من القائمة التالية:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await update.message.reply_text("❌ أرسل رابط يوتيوب أو تيك توك، أو استخدم 'يوت + بحث'.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data.startswith("select_"):
        idx = int(data.split("_")[1])
        video = user_search.get(chat_id, [])[idx]
        user_links[chat_id] = f"https://www.youtube.com/watch?v={video['id']}"
        buttons = [
            [InlineKeyboardButton("🎥 فيديو", callback_data="video")],
            [InlineKeyboardButton("🎧 صوت", callback_data="audio")],
        ]
        text = f"🎬 اختر نوع التحميل:\n{video['title']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "video":
        url = user_links.get(chat_id)
        if not url:
            await query.edit_message_text("❌ لم يتم تحديد فيديو.")
            return

        await query.edit_message_text("🔄 جاري جلب الجودات المتاحة...")
        ydl_opts = {"quiet": True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                (
                    f["format_id"],
                    f.get("format_note") or f.get("height"),
                    f.get("filesize") or 0,
                )
                for f in info["formats"]
                if f.get("vcodec") != "none"
            ]

        buttons = []
        for fmt in formats[:10]:
            size_mb = round(fmt[2] / 1024 / 1024, 1) if fmt[2] else "-"
            label = f"{fmt[1]} ({size_mb} MB)"
            buttons.append([InlineKeyboardButton(label, callback_data=f"format_{fmt[0]}")])

        await query.edit_message_text(
            "🎞️ اختر جودة الفيديو المطلوبة:", reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("format_"):
        format_id = data.split("_")[1]
        url = user_links.get(chat_id)
        await query.edit_message_text("📤 يتم التحميل والإرسال الآن...\n@zuz_4p")

        ydl_opts = {
            "format": format_id,
            "outtmpl": f"{VIDEO_DIR}/%(title).80s.%(ext)s",
            "quiet": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
                caption = (
                    f"🎞️ {info.get('title')[:60]}\n"
                    f"💾 الحجم: {round(os.path.getsize(path)/1024/1024,1)} MB\n@zuz_4p"
                )
                with open(path, "rb") as vid:
                    await context.bot.send_video(chat_id, video=vid, caption=caption)
                os.remove(path)
        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ خطأ أثناء التحميل: {e}")

    elif data == "audio":
        url = user_links.get(chat_id)
        await query.edit_message_text("📤 يتم إرسال الصوت الآن...\n@zuz_4p")

        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": f"{AUDIO_DIR}/%(title).80s.%(ext)s",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
            ],
            "quiet": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                mp3_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
                thumb_url = info.get("thumbnail")
                thumb_path = os.path.join(AUDIO_DIR, "thumb.jpg")
                if thumb_url:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(thumb_url) as resp:
                            with open(thumb_path, "wb") as f:
                                f.write(await resp.read())

                with open(mp3_path, "rb") as a:
                    thumb = open(thumb_path, "rb") if os.path.exists(thumb_path) else None
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=a,
                        title=info.get("title"),
                        performer=info.get("uploader"),
                        thumbnail=thumb,
                        caption="@zuz_4p",
                    )

                os.remove(mp3_path)
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)

        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ خطأ أثناء إرسال الصوت: {e}")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()
