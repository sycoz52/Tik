import requests
import re
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import time

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(name)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # هياخد التوكن من متغيرات البيئة

stats = {'total': 0, 'video': 0, 'audio': 0, 'failed': 0, 'start_time': time.time()}

def clean_filename(text):
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    return (text[:50] if text else "tiktok_video").strip()

def get_video_info(url):
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(api_url, headers=headers, timeout=15)
        data = response.json()
        
        if data.get('code') == 0 and data.get('data'):
            video_data = data['data']
            return {
                'success': True,
                'video_url': video_data.get('play', ''),
                'title': clean_filename(video_data.get('title', 'tiktok_video')),
                'audio_url': video_data.get('music', '')
            }
    except Exception as e:
        logger.error(f"Error: {e}")
    return {'success': False}

def download_file(url, filename):
    try:
        response = requests.get(url, timeout=60, stream=True)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return filename
    except Exception as e:
        logger.error(f"Download error: {e}")
    return None

async def set_commands(app):
    commands = [
        BotCommand("start", "بدء البوت"),
        BotCommand("help", "شرح الاستخدام"),
        BotCommand("about", "معلومات عن البوت"),
        BotCommand("stat", "إحصائيات البوت"),
        BotCommand("cancel", "إلغاء العملية"),
    ]
    await app.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"""
🌟 أهلاً بك {user.first_name}! 🌟

🎬 بوت تحميل تيك توك - بدون علامة مائية

طريقة الاستخدام:
1️⃣ انسخ رابط فيديو من تيك توك
2️⃣ أرسل الرابط هنا
3️⃣ اختر فيديو او صوت

✅ البوت يعمل 24/7

👨‍💻 برعاية اياد
    """
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
📚 الخطوات:
1. نسخ الرابط من تيك توك
2. إرسال الرابط للبوت
3. اختيار فيديو أو صوت
4. استلام الملف

⚠️ الفيديو يجب أن يكون عام
    """
    await update.message.reply_text(text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
ℹ️ بوت تحميل تيك توك
📡 نسخة 2.0
⚡ تحميل بدون علامة مائية
🟢 يعمل 24/7 على Koyeb
    """
    await update.message.reply_text(text, parse_mode='Markdown')

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = int(time.time() - stats['start_time'])
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    
    text = f"""
📊 الإحصائيات
📥 التحميلات: {stats['total']}
🎬 فيديو: {stats['video']}
🎵 صوت: {stats['audio']}
❌ فشل: {stats['failed']}
⏰ وقت التشغيل: {hours} ساعة {minutes} دقيقة
    """
    await update.message.reply_text(text, parse_mode='Markdown')

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
        
        await query.message.edit_text(f"⏳ جاري تحميل {'الفيديو' if download_type == 'video' else 'الصوت'}...")
        await process_download(query.message, url, download_type)

async def process_download(message, url, download_type):
    try:
        info = get_video_info(url)
        
        if not info['success']:
            stats['failed'] += 1
            await message.edit_text("❌ فشل التحميل!\nالرابط غير صحيح أو الفيديو خاص")
            return
        
        stats['total'] += 1
        
        if download_type == 'video':
            await message.edit_text("📥 جاري تحميل الفيديو...")
            file_path = download_file(info['video_url'], f"{info['title']}_video.mp4")
            
            if file_path:
                stats['video'] += 1
                await message.delete()
                with open(file_path, 'rb') as f:
                    await message.reply_video(video=f, caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title'][:50]}")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                await message.edit_text("❌ فشل التحميل")
        
        else:
            await message.edit_text("📥 جاري تحميل الصوت...")
            file_path = download_file(info['audio_url'], f"{info['title']}_audio.mp3")
            
            if file_path:
                stats['audio'] += 1
                await message.delete()
                with open(file_path, 'rb') as f:
                    await message.reply_audio(audio=f, title=info['title'][:50], performer="TikTok")
                os.remove(file_path)
            else:
                stats['failed'] += 1
                await message.edit_text("❌ فشل التحميل")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        stats['failed'] += 1
        await message.edit_text("⚠️ حدث خطأ، حاول مرة أخرى")

def main():
    print("🚀 تشغيل البوت على Koyeb...")
    
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

if name == "main":
    main()
