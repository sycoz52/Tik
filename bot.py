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

# =============== السيرفرات البديلة لتحميل الفيديو ===============

def get_video_info_api1(url):
    """السيرفر الأول - TikWM"""
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
        logger.error(f"API1 Error: {e}")
        return {'success': False}

def get_video_info_api2(url):
    """السيرفر الثاني - TikSave"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json'
        }
        data = {"url": url}
        response = requests.post("https://www.tiksave.app/api/ajaxSearch", json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'ok':
                video_url = result.get('links', {}).get('nowatermark', result.get('links', {}).get('watermark'))
                audio_url = result.get('music', {}).get('url')
                title = result.get('title', 'TikTok Video')[:50]
                title = re.sub(r'[\\/*?:"<>|]', "", title)
                return {
                    'success': True,
                    'title': title,
                    'video_url': video_url,
                    'audio_url': audio_url
                }
        return {'success': False}
    except Exception as e:
        logger.error(f"API2 Error: {e}")
        return {'success': False}

def get_video_info_api3(url):
    """السيرفر الثالث - SSSTik"""
    try:
        session = requests.Session()
        response = session.get("https://ssstik.io/en")
        if 'dfp' not in response.cookies:
            return {'success': False}
        
        api_url = "https://ssstik.io/abc?url=dl"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        data = {
            'id': url,
            'locale': 'en',
            'tt': response.cookies.get('dfp', '')
        }
        
        response = session.post(api_url, headers=headers, data=data, timeout=30)
        if response.status_code == 200:
            text = response.text
            video_match = re.search(r'https?://[^\s"\'<>]+\.mp4', text)
            audio_match = re.search(r'https?://[^\s"\'<>]+\.mp3', text)
            title_match = re.search(r'<p class=\"title\">([^<]+)</p>', text)
            
            title = title_match.group(1) if title_match else "TikTok Video"
            title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
            
            return {
                'success': True,
                'title': title,
                'video_url': video_match.group(0) if video_match else None,
                'audio_url': audio_match.group(0) if audio_match else None
            }
        return {'success': False}
    except Exception as e:
        logger.error(f"API3 Error: {e}")
        return {'success': False}

def get_video_info(url):
    """محاولة التحميل من كل السيرفرات بالترتيب"""
    servers = [
        ("TikWM", get_video_info_api1),
        ("TikSave", get_video_info_api2),
        ("SSSTik", get_video_info_api3)
    ]
    
    for server_name, server_func in servers:
        logger.info(f"محاولة التحميل من {server_name}...")
        result = server_func(url)
        if result['success'] and result.get('video_url'):
            logger.info(f"نجح التحميل من {server_name}")
            return result
        else:
            logger.warning(f"فشل التحميل من {server_name}")
    
    return {'success': False}

def get_audio_info(url):
    """جلب الصوت فقط من السيرفرات"""
    servers = [
        ("TikWM", get_video_info_api1),
        ("TikSave", get_video_info_api2),
        ("SSSTik", get_video_info_api3)
    ]
    
    for server_name, server_func in servers:
        logger.info(f"محاولة جلب الصوت من {server_name}...")
        result = server_func(url)
        if result['success'] and result.get('audio_url'):
            logger.info(f"نجح جلب الصوت من {server_name}")
            return result
        elif result['success'] and result.get('video_url'):
            return result
        else:
            logger.warning(f"فشل جلب الصوت من {server_name}")
    
    return {'success': False}

def download_file(url, filename):
    """تحميل الملف من الرابط"""
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, stream=True, timeout=90, headers=headers)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        
        return file_path
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

# =============== أوامر البوت ===============

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
- البوت يستخدم 3 سيرفرات تحميل بديلة
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = """
ℹ️ **معلومات عن البوت:**
الإصدار: 3.0
النوع: بوت تحميل تيك توك
الحالة: يعمل بكفاءة 🟢
السيرفرات: 3 سيرفرات بديلة

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
        
        status_msg = await query.message.edit_text(f"⏳ جاري التحميل...\nنوع: {'فيديو' if download_type == 'video' else 'صوت'}\n0/3 سيرفرات يعمل")
        await process_download(query.message, status_msg, url, download_type)

async def process_download(message, status_msg, url, download_type):
    global stats
    
    try:
        # جلب المعلومات حسب النوع
        if download_type == 'video':
            await status_msg.edit_text("📥 جاري البحث عن روابط الفيديو...\n1/3 سيرفرات يعمل")
            info = get_video_info(url)
        else:
            await status_msg.edit_text("📥 جاري البحث عن روابط الصوت...\n1/3 سيرفرات يعمل")
            info = get_audio_info(url)
        
        if not info['success']:
            stats['failed'] += 1
            save_stats(stats)
            await status_msg.edit_text("❌ فشل التحميل!\nتم تجربة جميع السيرفرات الثلاثة بدون نجاح")
            return
        
        stats['total'] += 1
        save_stats(stats)
        
        if download_type == 'video':
            if not info.get('video_url'):
                await status_msg.edit_text("❌ لا يوجد رابط فيديو")
                stats['failed'] += 1
                save_stats(stats)
                return
            
            await status_msg.edit_text("📥 جاري تحميل الفيديو... (3/3 سيرفرات يعمل)")
            file_path = download_file(info['video_url'], f"{info['title']}_video.mp4")
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:
                    await status_msg.edit_text("❌ الفيديو أكبر من 50 ميجا - لا يمكن رفعه للتليجرام")
                    os.remove(file_path)
                    stats['failed'] += 1
                    save_stats(stats)
                    return
                
                stats['video'] += 1
                save_stats(stats)
                await status_msg.delete()
                
                with open(file_path, 'rb') as f:
                    await message.reply_video(
                        video=f, 
                        caption=f"✅ تم التحميل بنجاح!\n🎬 {info['title']}\n✨ برعاية أياد",
                        timeout=120
                    )
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل تحميل الفيديو")
        
        else:
            if not info.get('audio_url'):
                await status_msg.edit_text("❌ لا يوجد رابط للصوت")
                stats['failed'] += 1
                save_stats(stats)
                return
            
            await status_msg.edit_text("📥 جاري تحميل الصوت... (3/3 سيرفرات يعمل)")
            file_path = download_file(info['audio_url'], f"{info['title']}_audio.mp3")
            
            if file_path and os.path.exists(file_path):
                stats['audio'] += 1
                save_stats(stats)
                await status_msg.delete()
                
                with open(file_path, 'rb') as f:
                    await message.reply_audio(
                        audio=f, 
                        title=info['title'], 
                        performer="TikTok - برعاية أياد",
                        timeout=120
                    )
                os.remove(file_path)
            else:
                stats['failed'] += 1
                save_stats(stats)
                await status_msg.edit_text("❌ فشل تحميل الصوت")
    
    except Exception as e:
        logger.error(f"Error in process_download: {e}")
        stats['failed'] += 1
        save_stats(stats)
        await status_msg.edit_text(f"⚠️ حدث خطأ: {str(e)[:80]}")

def main():
    print("🚀 تشغيل بوت تحميل تيك توك...")
    print("📡 السيرفرات المتاحة: TikWM | TikSave | SSSTik")
    
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود! ضيفه في Environment Variables")
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
    print("💡 أرسل /start في البوت على تليجرام")
    
    app.run_polling()

if __name__ == "__main__":
    main()
