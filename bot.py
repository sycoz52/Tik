import os
import re
import logging
import requests
import tempfile
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
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

def get_video_info(url):
    try:
        response = requests.get("https://tikwm.com/api/", params={"url": url}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                video_data = data['data']
                title = re.sub(r'[\\/*?:"<>|]', "", video_data.get('title', 'TikTok'))[:50]
                return {
                    'success': True,
                    'title': title,
                    'video_url': video_data.get('play'),
                    'audio_url': video_data.get('music')
                }
        return {'success': False}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {'success': False}

def download_file(url, filename):
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        response = requests.get(url, stream=True, timeout=60)
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
    await update.message.reply_text(f"""
🎬 مرحباً بك {first_name}!

أرسل رابط فيديو من تيك توك وسأقوم بتحميله لك.

📌 الأوامر:
/start - ترحيب
/help - مساعدة

✨ بوت تحميل تيك توك
برعاية أياد
""")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 أرسل رابط تيك توك، اختر فيديو أو صوت، وسأقوم بتحميله.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.search(r'(https?://)?(vm\.|vt\.|www\.|m\.)?tiktok\.com/\S+', text)
    if not match:
        await update.message.reply_text("❌ أرسل رابط تيك توك صحيح")
        return
    
    url = match.group(0)
    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data=f"video|{url}")],
        [InlineKeyboardButton("🎵 صوت", callback_data=f"audio|{url}")],
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
        download_type, url = parts[0], parts[1]
        status_msg = await query.message.edit_text(f"⏳ جاري تحميل {'الفيديو' if download_type == 'video' else 'الصوت'}...")
        
        info = get_video_info(url)
        if not info['success']:
            await status_msg.edit_text("❌ فشل التحميل!")
            return
        
        file_path = download_file(info['video_url'] if download_type == 'video' else info['audio_url'], 
                                  f"{info['title']}_{download_type}.mp4" if download_type == 'video' else f"{info['title']}_audio.mp3")
        
        if file_path:
            await status_msg.delete()
            with open(file_path, 'rb') as f:
                if download_type == 'video':
                    await query.message.reply_video(video=f, caption=f"✅ تم التحميل!\n🎬 {info['title']}")
                else:
                    await query.message.reply_audio(audio=f, title=info['title'], performer="TikTok")
            os.remove(file_path)
        else:
            await status_msg.edit_text("❌ فشل التحميل")

def main():
    print("🚀 تشغيل البوت...")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("✅ البوت جاهز!")
    app.run_polling()

if __name__ == "__main__":
    main()
