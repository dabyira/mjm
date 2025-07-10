import os
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from yt_dlp import YoutubeDL

TOKEN = "8146393797:AAESmjq0ApK-4e_qv_YO7uNTutWEkgtYWjM"

DOWNLOAD_DIR = 'downloads'
AUDIO_DIR = os.path.join(DOWNLOAD_DIR, 'audio')
VIDEO_DIR = os.path.join(DOWNLOAD_DIR, 'video')

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

user_search = {}
user_links = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 أهلاً بك في بوت يوت 🎶\n"
        "📌 للبحث في يوتيوب اكتب:\n"
        "`يوت` متبوع بكلمة البحث\n"
        "مثال: `يوت ماذنب طفلي`\n\n"
        "⚡️ بواسطة: @zuz_4p",
        parse_mode='Markdown'
    )

def search_youtube(query):
    ydl_opts = {'quiet': True, 'skip_download': True, 'default_search': 'ytsearch5'}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        results = []
        for entry in info['entries']:
            results.append({
                'id': entry.get('id'),
                'title': entry.get('title'),
                'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
            })
        return results

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    if text.startswith("يوت"):
        query = text[3:].strip()
        if not query:
            await update.message.reply_text("❌ الرجاء كتابة كلمة بحث بعد 'يوت'.")
            return

        await update.message.reply_text("🔍 يبحث الآن البوت علي على طلبك...")

        results = search_youtube(query)
        if not results:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")
            return

        user_search[chat_id] = results

        buttons = []
        for i, video in enumerate(results, 1):
            buttons.append([InlineKeyboardButton(f"{i}. {video['title']}", callback_data=f"select_{i-1}")])

        await update.message.reply_text(
            "🎬 اختر الفيديو من القائمة التالية:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.message.reply_text("❌ يرجى استخدام أمر البحث بـ 'يوت' متبوع بكلمة البحث.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()

    data = query.data

    if data.startswith("select_"):
        index = int(data.split("_")[1])
        results = user_search.get(chat_id)
        if not results or index >= len(results):
            await query.edit_message_text("❌ خطأ: لا يوجد نتيجة بهذا الرقم.")
            return

        video = results[index]
        user_links[chat_id] = video['url']

        buttons = [
            [InlineKeyboardButton("🎥 فيديو", callback_data="video")],
            [InlineKeyboardButton("🎧 صوت", callback_data="audio")]
        ]
        await query.edit_message_text(
            f"🎬 اختر نوع التحميل للفيديو:\n{video['title']}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "video":
        url = user_links.get(chat_id)
        if not url:
            await query.edit_message_text("❌ لم يتم تحديد فيديو.")
            return

        await query.edit_message_text("🔄 جاري تحميل الجودات المتاحة...")

        ydl_opts = {'quiet': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                (f['format_id'], f.get('format_note') or f.get('height'))
                for f in info['formats']
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none'
            ]

        buttons = []
        for fid, label in formats[:10]:
            buttons.append([InlineKeyboardButton(f"{label}", callback_data=f"format_{fid}")])

        await query.edit_message_text(
            "🎞️ اختر جودة الفيديو المطلوبة:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("format_"):
        format_id = data.split("_")[1]
        url = user_links.get(chat_id)
        if not url:
            await query.edit_message_text("❌ لم يتم تحديد فيديو.")
            return

        await query.edit_message_text("📤 يتم الإرسال الآن...\n@zuz_4p")

        ydl_opts = {
            'format': format_id,
            'outtmpl': f'{VIDEO_DIR}/%(title).80s.%(ext)s',
            'quiet': True
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                with open(file_path, 'rb') as f:
                    await context.bot.send_video(chat_id, video=f, caption=f"{info.get('title', '')}\n@zuz_4p")
                os.remove(file_path)
        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ فشل التحميل: {e}")

    elif data == "audio":
        url = user_links.get(chat_id)
        if not url:
            await query.edit_message_text("❌ لم يتم تحديد فيديو.")
            return

        await query.edit_message_text("📤 يتم الإرسال الآن...\n@zuz_4p")

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
                audio_path = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
                thumb_url = info.get('thumbnail')
                thumb_path = os.path.join(AUDIO_DIR, 'thumb.jpg')

                if thumb_url:
                    r = requests.get(thumb_url)
                    with open(thumb_path, 'wb') as f:
                        f.write(r.content)

                with open(audio_path, 'rb') as a, open(thumb_path, 'rb') as t:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=a,
                        title=info.get("title", "بدون عنوان"),
                        performer=info.get("uploader", ""),
                        thumbnail=t,
                        caption=f"@zuz_4p"
                    )

                os.remove(audio_path)
                os.remove(thumb_path)

        except Exception as e:
            await context.bot.send_message(chat_id, f"❌ فشل تحميل الصوت: {e}")

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()
