import os
import re
import logging
import tempfile
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATS_FILE = "stats.json"

def load_stats():
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'total': 0, 'video': 0, 'audio': 0, 'failed': 0}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f)
    except:
        pass

stats = load_stats()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def get_video_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'impersonate': 'chrome-131',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = None
            audio_url = None
            if 'formats' in info:
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('acodec') == 'none':
                        if video_url is None or f.get('height', 0) > 720:
                            video_url = f['url']
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                        if audio_url is None:
                            audio_url = f['url']
            if not video_url:
                video_url = info.get('url')
            if not audio_url:
                audio_url = info.get('url')
            return {
                'success': True,
                'title': info.get('title', 'بدون عنوان').replace('/', '_').replace('\\', '_'),
                'video_url': video_url,
                'audio_url': audio_url
            }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {'success': False}

def download_file(url, filename):
    try:
        import requests
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "يا باشا"
    welcome_text = f"""
🎬 مرحباً بك {first_name}!

أرسل رابط فيديو من تيك توك وسأقوم بتحميله لك.
يمكنك اختيار تحميل الفيديو أو الصوت فقط.

📌 الأوامر المتاحة:
/start - عرض رسالة الترحيب
/help - عرض المساعدة
/about - معلومات عن البوت
/stat - عرض الإحصائيات
/cancel - إلغاء العملية

✨ بوت تحميل تيك توك
برعاية أياد
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 أرسل رابط تيك توك وسأقوم بتحميله لك.")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ بوت تحميل تيك توك - برعاية أياد")

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    await update.message.reply_text(f"📊 إجمالي التحميلات: {stats['total']}\n🎬 فيديو: {stats['video']}\n🎵 صوت: {stats['audio']}\n❌ فاشل: {stats['failed']}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'url' in context.user_data:
        del context.user_data['url']
    await update.message.reply_text("✅ تم الإلغاء")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.search(r'(https?://)?(vm\.|vt\.|www\.|m\.)?tiktok\.com/\S+', text)
    if not match:
        await update.message.reply_text("❌ أرسل رابط تيك توك صحيح")
        return
    url = match.group(0)
    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data=f"video|{url}"), InlineKeyboardButton("🎵 صوت", callback_data=f"audio|{url}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]
    await update.message.reply_text("✅ تم استلام الرابط!\nاختر نوع التحميل:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text("✅ تم الإلغاء")
        return
    parts = query.data.split("|")
    if len(parts) == 2:
        download_type = parts[0]
        url = parts[1]
        status_msg = await query.message.edit_text(f"⏳ جاري تحميل {'الفيديو' if download_type == 'video' else 'الصوت'}...")
        await process_download(update, query.message, status_msg, url, download_type, context)

async def process_download(update, message, status_msg, url, download_type, context):
    global stats
    try:
        info = get_video_info(url)
        if not info['success']:
            stats['failed'] += 1
            save_stats(stats)
            await status_msg.edit_text("❌ فشل التحميل!")
            return
        stats['total'] += 1
        save_stats(stats)
        if download_type == 'video':
            await status_msg.edit_text("📥 جاري تحميل الفيديو...")
            file_path = download_file(info['video_url'], f"{info['title']}_video.mp4")
            if file_path:
                stats['video'] += 1
                save_stats(stats)
                await status_msg.delete()
                with open(file_path, 'rb') as f:
                    await message.reply_video(video=f, caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title'][:50]}")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل التحميل")
        else:
            await status_msg.edit_text("📥 جاري تحميل الصوت...")
            file_path = download_file(info['audio_url'], f"{info['title']}_audio.mp3")
            if file_path:
                stats['audio'] += 1
                save_stats(stats)
                await status_msg.delete()
                with open(file_path, 'rb') as f:
                    await message.reply_audio(audio=f, title=info['title'][:50], performer="TikTok")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل التحميل")
    except Exception as e:
        logger.error(f"Error: {e}")
        stats['failed'] += 1
        save_stats(stats)
        await status_msg.edit_text("⚠️ حدث خطأ، حاول مرة أخرى")

def main():
    print("🚀 تشغيل البوت...")
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("stat", stat_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("✅ البوت جاهز!")
    app.run_polling()

if __name__ == "__main__":
    main()
