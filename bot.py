import os
import re
import asyncio
import aiohttp
import html
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from yt_dlp import YoutubeDL

TOKEN = "8146393797:AAESmjq0ApK-4e_qv_YO7uNTutWEkgtYWjM"
DOWNLOAD_DIR = 'downloads'
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, 'audio')
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, 'video')
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

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def extract_url(text):
    yt_match = re.search(r"https?://(www\.)?youtube\.com/watch\?v=\S+|https?://youtu\.be/\S+", text)
    tt_match = re.search(r"https?://(www\.)?tiktok\.com/\S+", text)
    return yt_match.group(0) if yt_match else tt_match.group(0) if tt_match else None

async def safe_send_message(chat_id, text, context, reply_markup=None):
    try:
        # نستخدم html.escape لحماية النص من مشاكل الترميز
        escaped_text = html.escape(text)
        await context.bot.send_message(chat_id=chat_id, text=escaped_text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Failed to send message to {chat_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    url = extract_url(text)
    if url:
        user_links[chat_id] = url
        buttons = [
            [InlineKeyboardButton("🎥 فيديو", callback_data="video")],
            [InlineKeyboardButton("🎧 صوت", callback_data="audio")]
        ]
        await update.message.reply_text("📌 اختر نوع التحميل:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if text.startswith("يوت"):
        query = text[3:].strip()
        if not query:
            await update.message.reply_text("❌ الرجاء كتابة كلمة بحث بعد 'يوت'.")
            return

        await update.message.reply_text("🔍 يبحث الآن البوت على طلبك...")

        ydl_opts = {'quiet': True, 'skip_download': True, 'default_search': 'ytsearch5'}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
            results = info.get('entries', [])
        except Exception as e:
            logging.error(f"Error searching YouTube: {e}")
            await update.message.reply_text("❌ حدث خطأ أثناء البحث.")
            return

        if not results:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")
            return

        user_search[chat_id] = results
        buttons = [
            [InlineKeyboardButton(f"{i+1}. {v['title'][:40]}", callback_data=f"select_{i}")]
            for i, v in enumerate(results)
        ]
        await update.message.reply_text("🎬 اختر الفيديو من القائمة التالية:", reply_markup=InlineKeyboardMarkup(buttons))
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
            [InlineKeyboardButton("🎧 صوت", callback_data="audio")]
        ]
        text = f"🎬 اختر نوع التحميل:\n{video['title']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "video":
        url = user_links.get(chat_id)
        if not url:
            await query.edit_message_text("❌ لم يتم تحديد فيديو.")
            return

        await query.edit_message_text("🔄 جاري جلب الجودات المتاحة...")
        try:
            ydl_opts = {'quiet': True}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            formats = [
                (f['format_id'], f.get('format_note') or f.get('height'), f.get('filesize') or 0)
                for f in info['formats']
                if f.get('vcodec') != 'none' and f.get('filesize') is not None
            ]
        except Exception as e:
            logging.error(f"Error fetching formats: {e}")
            await query.edit_message_text("❌ حدث خطأ أثناء جلب الجودات.")
            return

        buttons = []
        for fmt in formats[:10]:
            size_mb = round(fmt[2] / 1024 / 1024, 1) if fmt[2] else "-"
            label = f"{fmt[1]} ({size_mb} MB)"
            buttons.append([InlineKeyboardButton(label, callback_data=f"format_{fmt[0]}")])

        await query.edit_message_text("🎞️ اختر جودة الفيديو المطلوبة:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("format_"):
        format_id = data.split("_")[1]
        url = user_links.get(chat_id)
        await query.edit_message_text("📤 يتم التحميل والإرسال الآن...\n@zuz_4p")

        ydl_opts = {
            'format': format_id,
            'outtmpl': f'{VIDEO_DIR}/%(title).80s.%(ext)s',
            'quiet': True
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
                size_mb = round(os.path.getsize(path) / 1024 / 1024, 1)
                caption = f"🎞️ {html.escape(info.get('title', '')[:60])}\n💾 الحجم: {size_mb} MB\n@zuz_4p"
                async with aiofiles.open(path, 'rb') as vid:
                    await context.bot.send_video(chat_id, video=vid, caption=caption)
                os.remove(path)
        except Exception as e:
            logging.error(f"Error downloading/sending video: {e}")
            await context.bot.send_message(chat_id, f"❌ خطأ أثناء التحميل: {e}")

    elif data == "audio":
        url = user_links.get(chat_id)
        await query.edit_message_text("📤 يتم إرسال الصوت الآن...\n@zuz_4p")

        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': f'{AUDIO_DIR}/%(title).80s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3'
            }],
            'quiet': True
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                mp3_path = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                thumb_url = info.get('thumbnail')
                thumb_path = os.path.join(AUDIO_DIR, 'thumb.jpg')

                if thumb_url and not os.path.exists(thumb_path):
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(thumb_url) as resp:
                            if resp.status == 200:
                                async with aiofiles.open(thumb_path, 'wb') as f:
                                    await f.write(await resp.read())

                async with aiofiles.open(mp3_path, 'rb') as a:
                    thumb = None
                    if os.path.exists(thumb_path):
                        thumb = open(thumb_path, 'rb')
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=a,
                        title=info.get("title"),
                        performer=info.get("uploader"),
                        thumbnail=thumb,
                        caption="@zuz_4p"
                    )
                    if thumb:
                        thumb.close()

                os.remove(mp3_path)
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)

        except Exception as e:
            logging.error(f"Error downloading/sending audio: {e}")
            await context.bot.send_message(chat_id, f"❌ خطأ أثناء إرسال الصوت: {e}")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    await app.run_polling()

if __name__ == '__main__':
    import aiofiles  # تأكد من تثبيت aiofiles (pip install aiofiles)
    asyncio.run(main())
