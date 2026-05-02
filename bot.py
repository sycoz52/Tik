import os
import re
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# معرفة معلومات الفيديو
def get_tiktok_info(tiktok_url):
    try:
        session = requests.Session()
        response = session.get("https://ssstik.io/en")
        if 'dfp' not in response.cookies:
            return None
        
        url = "https://ssstik.io/abc?url=dl"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        data = {
            'id': tiktok_url,
            'locale': 'en',
            'tt': response.cookies.get('dfp', '')
        }
        
        response = session.post(url, headers=headers, data=data)
        
        if response.status_code == 200:
            text = response.text
            # البحث عن رابط الفيديو (mp4)
            import re
            video_match = re.search(r'https?://[^\s"\'<>]+\.mp4', text)
            # البحث عن رابط الصوت (mp3)
            audio_match = re.search(r'https?://[^\s"\'<>]+\.mp3', text)
            
            # محاولة استخراج عنوان الفيديو
            title_match = re.search(r'<p class=\"title\">([^<]+)</p>', text)
            title = title_match.group(1) if title_match else "TikTok"
            
            return {
                'success': True,
                'title': title,
                'video_url': video_match.group(0) if video_match else None,
                'audio_url': audio_match.group(0) if audio_match else None
            }
        
        return {'success': False, 'error': 'فشل الاتصال'}
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return {'success': False, 'error': str(e)}

# تحميل الملف
def download_file(url, filename):
    try:
        import tempfile
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
🎬 مرحباً بك {first_name}!

أرسل رابط فيديو من تيك توك وسأقوم بتحميله لك.
يمكنك اختيار تحميل الفيديو أو الصوت فقط.

📌 الأوامر المتاحة:
/start - عرض رسالة الترحيب
/help - عرض المساعدة

✨ بوت تحميل تيك توك
برعاية أياد
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🔧 كيفية الاستخدام:

1️⃣ أرسل رابط فيديو تيك توك
2️⃣ اختر نوع التحميل (فيديو أو صوت)
3️⃣ انتظر قليلاً وسيتم الإرسال

⚠️ ملاحظة: الفيديو الخاص لا يمكن تحميله
"""
    await update.message.reply_text(help_text)

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
    try:
        # جلب معلومات التحميل
        info = get_tiktok_info(url)
        
        if not info['success'] or (download_type == 'video' and not info['video_url']) or (download_type == 'audio' and not info['audio_url']):
            await status_msg.edit_text("❌ فشل التحميل!\nالرابط غير صحيح أو الفيديو خاص")
            return
        
        # تحميل الملف
        if download_type == 'video':
            await status_msg.edit_text("📥 جاري تحميل الفيديو...")
            file_path = download_file(info['video_url'], f"{info['title']}_video.mp4")
        else:
            await status_msg.edit_text("📥 جاري تحميل الصوت...")
            file_path = download_file(info['audio_url'], f"{info['title']}_audio.mp3")
        
        if file_path and os.path.exists(file_path):
            await status_msg.delete()
            
            if download_type == 'video':
                with open(file_path, 'rb') as f:
                    await message.reply_video(video=f, caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title'][:50]}")
            else:
                with open(file_path, 'rb') as f:
                    await message.reply_audio(audio=f, title=info['title'][:50], performer="TikTok")
            
            os.remove(file_path)
        else:
            await status_msg.edit_text("❌ فشل التحميل")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ حدث خطأ، حاول مرة أخرى")

def main():
    print("🚀 تشغيل البوت...")
    
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
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
