import os
import re
import logging
import requests
import tempfile
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# التوكن من متغيرات البيئة
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

# دوال التحميل
def get_tiktok_info(url):
    try:
        response = requests.get("https://tikwm.com/api/", params={"url": url}, timeout=30)
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
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        return file_path
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "يا باشا"
    username = f"@{user.username}" if user.username else "مستخدم"
    
    welcome_text = f"""
╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
┃     
┃   🎬 **مرحباً بك {first_name}!** 🎬
┃   
┃   {username} أهلاً بك في **بوت تحميل تيك توك**
┃   
┃   📌 **مهمتي:**  
┃   تحميل فيديوهات وصوتيات تيك توك بدون علامة مائية  
┃   
┃   📋 **الأوامر المتاحة:**  
┃   • /start - بدء البوت وترحيب  
┃   • /help - شرح الاستخدام  
┃   • /about - معلومات عن البوت  
┃   • /stat - إحصائيات التحميلات  
┃   • /cancel - إلغاء العملية  
┃   
┃   ⚡ **طريقة الاستخدام:**  
┃   1️⃣ أرسل رابط فيديو تيك توك  
┃   2️⃣ اختر تحميل فيديو 🎬 أو صوت 🎵  
┃   3️⃣ انتظر قليلاً وسيتم الإرسال  
┃   
┃   ✅ **مميزات البوت:**  
┃   • تحميل بجودة عالية  
┃   • بدون علامة مائية  
┃   • دعم الفيديو والصوت  
┃   • سرعة في التحميل  
┃   
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

✨ **بوت تحميل تيك توك**  
🏢 برعاية **أياد**
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "يا باشا"
    
    help_text = f"""
╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
┃   🔧 **طريقة الاستخدام يا {first_name}**  
┃   
┃   1️⃣ اذهب إلى تيك توك وانسخ رابط الفيديو  
┃   2️⃣ ارسل الرابط هنا في الشات  
┃   3️⃣ اختر نوع التحميل:  
┃      🎬 فيديو | 🎵 صوت  
┃   4️⃣ انتظر ثواني وسيتم التحميل  
┃   
┃   💡 **ملاحظات مهمة:**  
┃   • الفيديو الخاص لا يمكن تحميله  
┃   • الحد الأقصى 50 ميجا للفيديو  
┃   • التحميل بدون علامة مائية  
┃   
┃   🆘 لأي مشكلة تواصل مع المطور  
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = """
╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
┃   ℹ️ **معلومات عن البوت**  
┃   
┃   📛 الاسم: بوت تحميل تيك توك  
┃   🔢 الإصدار: 3.0  
┃   🛠️ النوع: تحميل فيديوهات وصوتيات  
┃   📡 الحالة: يعمل بكفاءة 🟢  
┃   🖥️ السيرفرات: 2 سيرفر بديل  
┃   
┃   🚀 **المميزات:**  
┃   • سرعة فائقة في التحميل  
┃   • دعم جميع روابط تيك توك  
┃   • تحميل بدون علامة مائية  
┃   • واجهة سهلة وبسيطة  
┃   
┃   📅 تاريخ الإنشاء: 2026  
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    stat_text = f"""
╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮
┃   📊 **إحصائيات البوت**  
┃   
┃   📥 إجمالي التحميلات: `{stats['total']}`  
┃   🎬 فيديوهات: `{stats['video']}`  
┃   🎵 صوتيات: `{stats['audio']}`  
┃   ❌ فاشل: `{stats['failed']}`  
┃   
┃   ✅成功率: `{round((stats['total'] - stats['failed']) / max(stats['total'], 1) * 100)}%`  
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯
"""
    await update.message.reply_text(stat_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_url' in context.user_data:
        del context.user_data['current_url']
    await update.message.reply_text("✅ تم إلغاء العملية")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    match = re.search(r'(https?://)?(vm\.|vt\.|www\.|m\.)?tiktok\.com/\S+', text)
    if not match:
        await update.message.reply_text("❌ أرسل رابط تيك توك صحيح")
        return
    
    url = match.group(0)
    context.user_data['current_url'] = url
    
    keyboard = [
        [InlineKeyboardButton("🎬 فيديو", callback_data="video")],
        [InlineKeyboardButton("🎵 صوت", callback_data="audio")],
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
    
    url = context.user_data.get('current_url')
    if not url:
        await query.message.edit_text("❌ الرابط غير موجود")
        return
    
    download_type = query.data
    status_msg = await query.message.edit_text(f"⏳ جاري تحميل {'الفيديو' if download_type == 'video' else 'الصوت'}...")
    
    info = get_tiktok_info(url)
    if not info['success']:
        await status_msg.edit_text("❌ فشل التحميل!")
        return
    
    file_url = info['video_url'] if download_type == 'video' else info['audio_url']
    ext = "mp4" if download_type == 'video' else "mp3"
    file_path = download_file(file_url, f"{info['title']}.{ext}")
    
    if file_path:
        await status_msg.delete()
        with open(file_path, 'rb') as f:
            if download_type == 'video':
                await query.message.reply_video(video=f, caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title']}")
            else:
                await query.message.reply_audio(audio=f, title=info['title'], performer="TikTok")
        os.remove(file_path)
    else:
        await status_msg.edit_text("❌ فشل التحميل")

def main():
    print("🚀 تشغيل بوت تحميل تيك توك...")
    print("🤖 البوت يعمل بكفاءة")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("stat", stat_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ البوت جاهز ويعمل!")
    app.run_polling()

if __name__ == "__main__":
    main()
