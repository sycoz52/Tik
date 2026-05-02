import os
import re
import logging
import requests
import tempfile
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# توكن البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")

# إحصائيات
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

# دوال التحميل من TikWM API
def get_video_info(url):
    try:
        api_url = "https://tikwm.com/api/"
        response = requests.get(api_url, params={"url": url}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('code') == 0:
                video_data = data['data']
                title = video_data.get('title', 'TikTok Video')
                title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
                
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

# دوال البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "يا باشا"
    
    welcome_text = f"""
🎬 **مرحباً بك {first_name}!**

أرسل رابط فيديو من تيك توك وسأقوم بتحميله لك.
يمكنك اختيار تحميل الفيديو أو الصوت فقط.

📌 **الأوامر المتاحة:**
/start - عرض رسالة الترحيب
/help - عرض المساعدة
/about - معلومات عن البوت
/stat - عرض الإحصائيات
/cancel - إلغاء العملية

✨ **بوت تحميل تيك توك**
برعاية أياد
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🔧 **كيفية الاستخدام:**

1️⃣ أرسل رابط فيديو تيك توك
2️⃣ اختر نوع التحميل (فيديو أو صوت)
3️⃣ انتظر قليلاً وسيتم التحميل والإرسال

⚠️ **ملاحظات:**
- الفيديو الخاص لا يمكن تحميله
- الحد الأقصى لحجم الملف 50 ميجا
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = """
ℹ️ **معلومات عن البوت:**
الإصدار: 3.0
النوع: بوت تحميل تيك توك
الحالة: يعمل بكفاءة 🟢

**بوت تحميل تيك توك**
برعاية أياد
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    stat_text = f"""
📊 **إحصائيات البوت:**

📥 إجمالي التحميلات: {stats['total']}
🎬 فيديوهات: {stats['video']}
🎵 صوتيات: {stats['audio']}
❌ فاشل: {stats['failed']}
"""
    await update.message.reply_text(stat_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'url' in context.user_data:
        del context.user_data['url']
    await update.message.reply_text("✅ تم إلغاء العملية")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    match = re.search(r'(https?://)?(vm\.|vt\.|www\.|m\.)?tiktok\.com/\S+', text)
    if not match:
        await update.message.reply_text("❌ أرسل رابط تيك توك صحيح")
        return
    
    url = match.group(0)
    context.user_data['url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 فيديو", callback_data=f"video|{url}"),
            InlineKeyboardButton("🎵 صوت", callback_data=f"audio|{url}")
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]
    
    await update.message.reply_text(
        "✅ تم استلام الرابط!\nاختر نوع التحميل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
        await process_download(query.message, status_msg, url, download_type)

async def process_download(message, status_msg, url, download_type):
    global stats
    
    try:
        info = get_video_info(url)
        
        if not info['success']:
            stats['failed'] += 1
            save_stats(stats)
            await status_msg.edit_text("❌ فشل التحميل!\nالرابط غير صحيح أو الفيديو خاص")
            return
        
        stats['total'] += 1
        save_stats(stats)
        
        if download_type == 'video':
            await status_msg.edit_text("📥 جاري تحميل الفيديو...")
            file_path = download_file(info['video_url'], f"{info['title']}_video.mp4")
            
            if file_path and os.path.exists(file_path):
                stats['video'] += 1
                save_stats(stats)
                await status_msg.delete()
                
                with open(file_path, 'rb') as f:
                    await message.reply_video(video=f, caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title']}")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل التحميل")
        
        else:
            await status_msg.edit_text("📥 جاري تحميل الصوت...")
            file_path = download_file(info['audio_url'], f"{info['title']}_audio.mp3")
            
            if file_path and os.path.exists(file_path):
                stats['audio'] += 1
                save_stats(stats)
                await status_msg.delete()
                
                with open(file_path, 'rb') as f:
                    await message.reply_audio(audio=f, title=info['title'], performer="TikTok")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل التحميل")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        stats['failed'] += 1
        save_stats(stats)
        await status_msg.edit_text(f"⚠️ حدث خطأ: {str(e)[:50]}")

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
