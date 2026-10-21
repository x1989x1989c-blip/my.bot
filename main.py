import os
import re
import time
import random
import sqlite3
import requests
import html
import urllib.parse
import telebot
from telebot import types
import yt_dlp
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive():
        pass

# ==================== الإعدادات الأساسية ====================
TOKEN = "8880921736:AAHBAZ_5tDNKbmc0VsFI5xaShgYZFlLns08"
ADMIN_ID = 8577656131

# مفتاح OpenRouter الـ API الخاص بك
OPENROUTER_API_KEY = "Sk-or-v1-2a718ad8a8dd208c13eb4fe1cfab91167dc363b311aafc7012ea5282195fc95f"
OPENROUTER_MODEL = "xingchen-agi/xing4.0-29b-a4b:free"

bot = telebot.TeleBot(TOKEN)

# هياكل بيانات لتتبع العقوبات والحالات المؤقتة
muted_5min_users = {}       # (chat_id, user_id) -> expire_time
name_penalties = {}         # (chat_id, user_id) -> {'target_name': str, 'expire_time': int}
embarrassing_penalties = {} # (chat_id, user_id) -> {'user_name': str, 'question': str, 'msg_id': int}
farfoosh_challenge_users = {} # user_id -> bool
farfoosh_game_sessions = {}   # (chat_id, user_id) -> bool

# ==================== نظام الحذف المتطور والآمن ====================
def safe_delete_message(chat_id, message_id):
    """نظام حذف متطور ومحمي لعدم توقف البوت أو تجميده"""
    try:
        return bot.delete_message(chat_id, message_id)
    except Exception:
        return False

# ==================== قاعدة البيانات ====================
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            item_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, item_name)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS store (
            item_name TEXT PRIMARY KEY,
            price INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riddles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            response TEXT,
            media_type TEXT DEFAULT 'text',
            file_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steal_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_steal INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_steal_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_steal INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invest_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_invest INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheel_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_wheel INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bet_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_bet INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER DEFAULT 0,
            loan_time INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crime_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story TEXT,
            killer TEXT,
            suspects TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS muted_groups (
            chat_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gemini_groups (
            chat_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gift_claimed (
            user_id INTEGER PRIMARY KEY,
            last_claim INTEGER DEFAULT 0
        )
    """)

    try:
        cursor.execute("ALTER TABLE custom_replies ADD COLUMN media_type TEXT DEFAULT 'text'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE custom_replies ADD COLUMN file_id TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE gift_claimed ADD COLUMN last_claim INTEGER DEFAULT 0")
    except:
        pass

    # إضافة أصناف المتجر والمطعم
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('علبة متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كيلو سكر', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('شاورما', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('برغر', 150)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('بيتزا', 200)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كباب', 250)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('عصير', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('متة', 50)")

    conn.commit()
    conn.close()

init_db()

admin_states = {}
user_gemini_states = {}
active_riddles = {}
active_math_games = {}
active_guess_games = {}
active_crime_games = {}
active_series_games = {}
xo_games = {}
min_kafo_games = {}

# ==================== أدوات مساعدة ====================
def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def is_chat_admin(chat_id, user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def is_bot_admin(chat_id):
    try:
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        return bot_member.status in ['administrator', 'creator']
    except:
        return False

def is_gemini_enabled(chat_type, chat_id, user_id):
    if chat_type == 'private':
        return True
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM gemini_groups WHERE chat_id = ?", (chat_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def get_balance(user_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = max(0, balance + ?)", (user_id, max(0, amount), amount))
    conn.commit()
    conn.close()

def is_user_jailed(user_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT amount, loan_time FROM loans WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] > 0:
        amount, loan_time = row
        current_time = int(time.time())
        if (current_time - loan_time) >= 7200: # ساعتان
            return True, amount
    return False, 0

def clean_urls_and_sources(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text)
    text = re.sub(r'(📌\s*المصادر:?|🔗\s*المصدر:?|المصدر:|المصادر:|Source:|Sources:)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\d+\]', '', text)
    return text.strip()

def clean_syrian_search_query(text):
    remove_words = [
        "بدي غنية", "بدي اغنية", "نزللي غنية", "نزل اغنية", "شغلي غنية", "شغل اغنية",
        "بديا غنية", "بدي فيديو", "نزل فيديو", "شغل فيديو", "كليب", "يا بوت", "فرفوش"
    ]
    cleaned = text
    for w in remove_words:
        cleaned = re.sub(r'\b' + re.escape(w) + r'\b', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or text

def send_large_text(chat_id, header, items_list):
    if not items_list:
        bot.send_message(chat_id, f"{header}\n\nلا توجد بيانات مخزنة حالياً.")
        return
    
    current_msg = f"{header}\n\n"
    for item in items_list:
        line = f"• {item}\n"
        if len(current_msg) + len(line) > 3500:
            bot.send_message(chat_id, current_msg)
            current_msg = ""
        current_msg += line
    if current_msg:
        bot.send_message(chat_id, current_msg)

# ==================== نظام الذكاء الاصطناعي عبر OpenRouter ====================
def fetch_ai_answer(question, custom_sys_prompt=None):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    if not custom_sys_prompt:
        custom_sys_prompt = (
            "أنت بوت ذكي وفكاهي اسمك 'فرفوش'، أنت شاب سوري حماوي أصيل من مدينة حماة. "
            "تتحدث باللهجة السورية الحماوية اللطيفة والفرفوشة، تحب المزاح والتسلية والضحك، "
            "وتجيب على المستخدمين بأسلوب ممتع ومباشر بدون مقدمات رسمية ولا تذكر روابط أو مصادر."
        )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": custom_sys_prompt},
            {"role": "user", "content": question}
        ]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            ans = data['choices'][0]['message']['content']
            return clean_urls_and_sources(ans)
    except Exception as e:
        print(f"OpenRouter Error: {e}")

    return "لك أهلاً وسهلاً بك يا غالي! أنا فرفوش الحموي، أطلب وتمنّى وشو في ببالك ألعاب أو تسلية؟ 😉"

def ask_ai_saraha_question():
    sys_p = "أنت مساعد ذكي ومرح. تولد أسئلة صراحة محرجة وجريئة جداً وممتعة للشباب والصبايا في الكروبات. أرسل سؤالاً واحداً فقط وبدون مقدمات."
    prompt = "اعطني سؤال صراحة واحد محرج جداً وجريء للشباب والصبايا في الجروب."
    return fetch_ai_answer(prompt, custom_sys_prompt=sys_p)

def generate_image_pollinations(prompt):
    clean_prompt = prompt
    syrian_phrases = ["بدي ساوي صورة", "ساويلي صورة", "اعملي صورة", "رسيملي صورة", "بدي صورة", "صورة لـ", "صورة"]
    for p in syrian_phrases:
        clean_prompt = clean_prompt.replace(p, "").strip()
    
    if not clean_prompt:
        clean_prompt = prompt

    models = ["flux", "flux-realism", "any-dark"]
    encoded_prompt = urllib.parse.quote(clean_prompt)
    
    for m in models:
        try:
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={random.randint(1, 999999)}&nologo=true&model={m}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200 and len(res.content) > 2000:
                return res.content
        except Exception:
            continue
    return None

# ==================== خدمات تحميل الصوتيات والفيديو ====================
def download_and_send_audio(chat_id, query, message_id):
    clean_q = clean_syrian_search_query(query)
    status_msg = bot.send_message(chat_id, f"🔍 **جاري البحث وتحميل الصوت فوراً...**", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file_prefix = f"downloads/{int(time.time())}_{random.randint(1000,9999)}"
    output_template = f"{file_prefix}.%(ext)s"

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'cachedir': False,
    }

    search_targets = [clean_q] if clean_q.startswith("http") else [f"ytsearch1:{clean_q}", f"scsearch1:{clean_q}"]

    for target in search_targets:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if info:
                    video = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
                    title = video.get('title', 'صوتية يوتيوب')
                    uploader = video.get('uploader', 'فرفوش')

                    downloaded_file = None
                    for ext in ['m4a', 'mp3', 'webm', 'opus', 'mp4']:
                        possible_path = f"{file_prefix}.{ext}"
                        if os.path.exists(possible_path):
                            downloaded_file = possible_path
                            break

                    if downloaded_file and os.path.exists(downloaded_file):
                        with open(downloaded_file, 'rb') as audio:
                            bot.send_audio(chat_id, audio, title=title, performer=uploader, reply_to_message_id=message_id)
                        safe_delete_message(chat_id, status_msg.message_id)
                        try:
                            os.remove(downloaded_file)
                        except:
                            pass
                        return
        except Exception:
            continue

    bot.edit_message_text("❌ تعذر تحميل الصوت حالياً، تأكد من صحة الرابط أو اسم الأغنية.", chat_id, status_msg.message_id)

def download_and_send_video(chat_id, query, message_id):
    clean_q = clean_syrian_search_query(query)
    status_msg = bot.send_message(chat_id, f"🎬 **جاري البحث وتحميل الفيديو...**", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file_prefix = f"downloads/vid_{int(time.time())}_{random.randint(1000,9999)}"
    output_template = f"{file_prefix}.%(ext)s"

    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[filesize<45M]',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'cachedir': False,
    }

    target = clean_q if clean_q.startswith("http") else f"ytsearch1:{clean_q}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=True)
            if info:
                video_info = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
                title = video_info.get('title', clean_q) if video_info else clean_q

                downloaded_file = None
                for ext in ['mp4', 'mkv', 'webm']:
                    possible_path = f"{file_prefix}.{ext}"
                    if os.path.exists(possible_path):
                        downloaded_file = possible_path
                        break

                if downloaded_file and os.path.exists(downloaded_file):
                    with open(downloaded_file, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, caption=f"🎥 **{title}**", reply_to_message_id=message_id, parse_mode="Markdown")
                    safe_delete_message(chat_id, status_msg.message_id)
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                    return
    except Exception:
        pass

    bot.edit_message_text("❌ تعذر تحميل الفيديو، تأكد من صحة الرابط أو الكلمات الدلالية.", chat_id, status_msg.message_id)

# ==================== لوحة تحكم الإدارة الأزرار التفاعلية ====================
def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة للكل", callback_data="admin_broadcast_all"),
        types.InlineKeyboardButton("👥 إذاعة للمجموعات", callback_data="admin_broadcast_groups"),
        types.InlineKeyboardButton("📩 رسالة خاصة لجروب", callback_data="admin_select_group_msg"),
        types.InlineKeyboardButton("➕ إضافة رد", callback_data="admin_add_reply"),
        types.InlineKeyboardButton("🗑 حذف رد", callback_data="admin_del_reply"),
        types.InlineKeyboardButton("📋 قائمة الردود", callback_data="admin_list_replies"),
        types.InlineKeyboardButton("🔇 إسكات لجروب", callback_data="admin_mute_group_list"),
        types.InlineKeyboardButton("🚪 مغادرة جروب", callback_data="admin_leave_group_list"),
        types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("➖ حذف مشرف", callback_data="admin_del_admin"),
        types.InlineKeyboardButton("📋 قائمة المشرفين", callback_data="admin_list_admins"),
        types.InlineKeyboardButton("➕ إضافة رصيد وهمي", callback_data="admin_add_fake_balance"),
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        types.InlineKeyboardButton("🤖 جيمني للمجموعات", callback_data="admin_gemini_groups"),
        types.InlineKeyboardButton("🎮 سجلات الألعاب", callback_data="admin_game_logs"),
        types.InlineKeyboardButton("🗑️ إعادة ضبط الألعاب", callback_data="admin_reset_games")
    )
    return markup

# ==================== الترحيب وموجه الرسائل ====================
@bot.message_handler(content_types=['new_chat_members'])
def on_bot_added_to_group(message):
    bot_id = bot.get_me().id
    for member in message.new_chat_members:
        if member.id == bot_id:
            welcome_text = "انا جيييييت\nفوتو سلمولي على مطوري @syabd0"
            bot.send_message(message.chat.id, welcome_text)
            
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (message.chat.id, message.chat.title or "مجموعة بدون عنوان"))
            conn.commit()
            conn.close()
            break

def send_welcome_message(message):
    user_id = message.from_user.id
    try:
        bot_username = bot.get_me().username
    except:
        bot_username = "Bot"

    welcome_text = (
        "👋 **أهلاً بك في بوت فرفوش الشامل للمجموعات والتسلية!**\n\n"
        "✨ **المميزات المفعلة:**\n"
        "🛡️ **حماية المجموعة:** منع الروابط والمعرفات والتوجيه للأعضاء.\n"
        "🎮 **ألعاب متطورة:** XO، رياضيات، خمن الرقم، خمن المسلسل 📺، القاتل 🔪، وعجلة الحظ 🎡، ولعبة مين كفو 🔥.\n"
        "🍔 **مطعم ومتجر:** شراء، بيع، إهداء، وسرقة المأكولات والمشروبات بالرد!\n"
        "🤖 **ذكاء اصطناعي (OpenRouter):** اكتب `عرفني عن نفسك فرفوش` أو `فرفوش لعبني` أو `صراحة`.\n"
        "🎵 **تحميل يوتيوب تلقائي:** أرسل كلمة `يوتيوب` أو `سمعني` مع اسم الأغنية وسيتم تحميلها فوراً."
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    add_group_btn = types.InlineKeyboardButton("➕ أضفني إلى المجموعة", url=f"https://t.me/{bot_username}?startgroup=true")
    markup.add(add_group_btn)

    if is_admin(user_id):
        admin_btn = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="open_admin_panel")
        markup.add(admin_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ==================== الموجه الرئيسي الحماية والأوامر والعقوبات ====================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'audio', 'voice', 'sticker'])
def main_router(message):
    text = (message.text or message.caption or "").strip()
    chat_type = message.chat.type
    user_id = message.from_user.id
    chat_id = message.chat.id
    curr_t = int(time.time())
    key = (chat_id, user_id)

    # 1. تطبيق عقوبة الكتم لمدة 5 دقائق
    if key in muted_5min_users:
        if curr_t < muted_5min_users[key]:
            safe_delete_message(chat_id, message.message_id)
            return
        else:
            del muted_5min_users[key]

    # 2. تطبيق عقوبة تغيير الاسم
    if key in name_penalties:
        p_info = name_penalties[key]
        if curr_t >= p_info['expire_time']:
            del name_penalties[key]
        else:
            full_name = (message.from_user.first_name or "") + " " + (message.from_user.last_name or "")
            if p_info['target_name'] in full_name:
                del name_penalties[key]
                bot.reply_to(message, f"✅ كفو! تم التعرف على اسمك الجديد ({p_info['target_name']}) وتم رفع العقوبة عنك بنجاح! 🎉")
            else:
                safe_delete_message(chat_id, message.message_id)
                return

    # 3. تطبيق عقوبة السؤال المحرج
    if key in embarrassing_penalties:
        p_data = embarrassing_penalties[key]
        is_game_cmd = text in ["مين كفو", "مين كفو؟", "انا", "أنا", "بلشها", "بلش"]
        if text and not is_game_cmd:
            del embarrassing_penalties[key]
            bot.reply_to(message, f"✅ تم قبول إجابتك الصريحة يا **{p_data['user_name']}**! تم رفع التقييد عنك ويمكنك المشاركة في اللعب الآن. 🎉", parse_mode="Markdown")
            return
        else:
            safe_delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, f"⚠️ يا [{p_data['user_name']}](tg://user?id={user_id}) جاوب على السؤال المحرج أولاً للفك عن التقييد! 😳\nالسؤال: `{p_data['question']}`", parse_mode="Markdown")
            return

    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (chat_id,))
    is_muted = c.fetchone()
    conn.close()

    if text in ["إسكات البوت", "اسكات البوت"] and is_chat_admin(chat_id, user_id):
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (chat_id,))
        if c.fetchone():
            c.execute("DELETE FROM muted_groups WHERE chat_id = ?", (chat_id,))
            bot.reply_to(message, "🔊 تم فك إسكات البوت وبإمكانه الرد الآن!")
        else:
            c.execute("INSERT INTO muted_groups VALUES (?)", (chat_id,))
            bot.reply_to(message, "🔇 تم إسكات البوت في هذه المجموعة بنجاح!")
        conn.commit()
        conn.close()
        return

    if is_muted and not is_admin(user_id) and text not in ["إسكات البوت", "اسكات البوت"]:
        return

    # معالجة مدخلات أدمن الردود المخصصة والإدارة
    if is_admin(user_id) and user_id in admin_states:
        handle_admin_inputs(message)
        return

    if text.startswith("/start") or text.lower() == "ستارت":
        send_welcome_message(message)
        return

    # فحص روابط يوتيوب المباشرة
    yt_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text)
    if yt_match:
        yt_url = yt_match.group(1)
        download_and_send_audio(chat_id, yt_url, message.message_id)
        return

    # حماية المجموعات
    if chat_type in ['group', 'supergroup']:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (chat_id, message.chat.title or "مجموعة بدون عنوان"))
        conn.commit()
        conn.close()

        sender_is_admin = is_chat_admin(chat_id, user_id)
        is_channel_post = message.sender_chat is not None and message.sender_chat.type == 'channel'

        if message.reply_to_message and sender_is_admin:
            target_id = message.reply_to_message.from_user.id
            if text == "اكتمو":
                try:
                    bot.restrict_chat_member(chat_id, target_id, can_send_messages=False)
                    bot.reply_to(message, "تم كتم العضو بنجاح 🤐")
                except Exception as e:
                    bot.reply_to(message, f"❌ متعذر الكتم: {e}")
                return

            elif text == "خليه يحكي":
                try:
                    bot.restrict_chat_member(
                        chat_id, target_id, 
                        can_send_messages=True, 
                        can_send_media_messages=True, 
                        can_send_other_messages=True, 
                        can_add_web_page_previews=True
                    )
                    bot.reply_to(message, "تم فك الكتم عن العضو، خليه يحكي 🗣️")
                except Exception as e:
                    bot.reply_to(message, f"❌ متعذر فك الكتم: {e}")
                return

            elif text == "قلعو":
                try:
                    bot.ban_chat_member(chat_id, target_id)
                    bot.reply_to(message, "تم طرد العضو من المجموعة بنجاح 🚪")
                except Exception as e:
                    bot.reply_to(message, f"❌ متعذر الطرد: {e}")
                return

        if is_bot_admin(chat_id) and not sender_is_admin and not is_channel_post:
            user_name = message.from_user.first_name if message.from_user else "العضو"
            user_mention = f"[{user_name}](tg://user?id={user_id})"

            if message.forward_date or message.forward_from or message.forward_from_chat:
                try:
                    safe_delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، التوجيه ممنوع هنا ❌", parse_mode="Markdown")
                except:
                    pass
                return

            has_username = bool(re.search(r'@[a-zA-Z0-9_]+', text))
            if has_username:
                try:
                    safe_delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، المعرفات ممنوعة هنا ❌", parse_mode="Markdown")
                except:
                    pass
                return

            has_link = bool(re.search(r'(https?://\S+|t\.me/\S+|\b\w+\.(com|net|org|site|online)\b)', text))
            if has_link:
                try:
                    safe_delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، كفاك روابط يا بني ❌", parse_mode="Markdown")
                except:
                    pass
                return

    # فحص السجن
    jailed, debt = is_user_jailed(user_id)
    if jailed and text not in ["دفع ديني", "دفع دينو"] and not (message.reply_to_message and "دفع دينو" in text):
        bot.reply_to(message, "انت مسجون ياحباب دفاع دينك قبل يافقير")
        return

    # متابعة جلسة التفاعل للعبة فرفوش
    session_key = (chat_id, user_id)
    if session_key in farfoosh_game_sessions and text:
        farfoosh_sys = (
            "أنت 'فرفوش' شاب حماوي سوري متفاعل مع لعبة جماعية بالكروب. "
            "رد على إجابة أو حركة المستخدم بتعليق فرفوش ومضحك، ثم قل له: "
            "'لإكمال اللعب والخطوة التالية أرسل [كذا]' ليبقى التفاعل مستمراً بكفاءة."
        )
        ai_resp = fetch_ai_answer(text, custom_sys_prompt=farfoosh_sys)
        bot.reply_to(message, ai_resp)
        return

    # حالات جيمني
    if user_id in user_gemini_states:
        g_state = user_gemini_states.pop(user_id)
        if g_state == "wait_gemini_question":
            thinking_msg = bot.reply_to(message, "جاري التفكير والبحث... 🔍")
            ans = fetch_ai_answer(text)
            try:
                bot.edit_message_text(ans, chat_id, thinking_msg.message_id)
            except:
                bot.reply_to(message, ans)
            return

        elif g_state == "wait_gemini_image_prompt":
            gen_msg = bot.reply_to(message, "🎨 جاري رسم الصورة حسب الطلب...")
            img_data = generate_image_pollinations(text)
            if img_data:
                try:
                    safe_delete_message(chat_id, gen_msg.message_id)
                except:
                    pass
                bot.send_photo(chat_id, photo=img_data, caption=f"🖼️ الصورة المطلوبة: `{text}`", reply_to_message_id=message.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ تعذر إنشاء الصورة حالياً، حاول بوصف آخر.", chat_id, gen_msg.message_id)
            return

    process_bot_commands(message)

# ==================== معالجة الأوامر والردود ====================
def process_bot_commands(message):
    text = (message.text or message.caption or "").strip()
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type

    if text == "شو انا":
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if user_id == ADMIN_ID or member.status == 'creator':
                bot.reply_to(message, "انت المالك ياقلبي")
            elif member.status == 'administrator' or is_admin(user_id):
                bot.reply_to(message, "انت مشرف ياحبيبي")
            else:
                bot.reply_to(message, "انت عضو بس عضو من قلبي ♥️")
        except:
            if is_admin(user_id):
                bot.reply_to(message, "انت مشرف ياحبيبي")
            else:
                bot.reply_to(message, "انت عضو بس عضو من قلبي ♥️")
        return

    # ==================== أمر "عرفني عن نفسك فرفوش" ====================
    if text in ["عرفني عن نفسك فرفوش", "من انت فرفوش", "مين انت فرفوش"]:
        prompt_intro = "عرفني عن نفسك يا فرفوش بأسلوب حماوي ممتع وفكاهي جداً مع ترحيب بالجروب."
        sys_p = "أنت فرفوش، شاب حماوي من حماة بسوريا، مرح وفكاهي جداً، تعرّف عن نفسك بأسلوب حموي ممتع."
        intro_resp = fetch_ai_answer(prompt_intro, custom_sys_prompt=sys_p)
        bot.reply_to(message, intro_resp)
        return

    # ==================== أمر "فرفوش لعبني" (الذكاء التفاعلي) ====================
    if text in ["فرفوش لعبني", "لعبني فرفوش", "فرفوش نلعب"]:
        farfoosh_game_sessions[(chat_id, user_id)] = True
        game_sys = (
            "أنت فرفوش السوري من حماة. اقترح الآن لعبة جماعية أو تحدي ممتع فوراً للمستخدم بالجروب، "
            "وأنهِ كلامك بعبارة دقيقة موجهة له: 'ولإكمال اللعب وتجاوز المرحلة، أرسل [كلمة السر أو الحركة]'."
        )
        game_start_msg = fetch_ai_answer("اقترح لعبة فرفوشية جديدة تفاعلية الآن!", custom_sys_prompt=game_sys)
        bot.reply_to(message, game_start_msg)
        return

    # ==================== ميزة عطيني هديتي (تتكرر كل 6 ساعات ومبالغ عشوائية) ====================
    if text in ["عطيني هديتي", "اعطيني هديتي", "هديتي"]:
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_claim FROM gift_claimed WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        cooldown_seconds = 6 * 3600 # 6 ساعات
        if row and row[0] and (current_time - row[0]) < cooldown_seconds:
            remaining_seconds = cooldown_seconds - (current_time - row[0])
            rem_hours = int(remaining_seconds // 3600)
            rem_mins = int((remaining_seconds % 3600) // 60)
            
            funny_claimed_msgs = [
                f"😂 **لك أخدتها يا طماع!**\nفاضل لك `{rem_hours}` ساعة و `{rem_mins}` دقيقة لتفتح الهدية التالية، روح اشتغل واستثمر بمصرياتك! 🏃‍♂️💨",
                f"👀 عم تحاول وتاخدها مرة ثانية؟ الهدية بتجي مرة كل 6 ساعات، استنى لك `{rem_hours}` ساعة! 😂",
                f"😜 أخدت الهدية وبدك ثانية فوراً؟ طوّل بالك فرّقنا مو كل شوية عطيني هديتي! 🗿"
            ]
            bot.reply_to(message, random.choice(funny_claimed_msgs), parse_mode="Markdown")
            conn.close()
        else:
            gift_amount = random.randint(100, 1000000)
            c.execute("INSERT INTO gift_claimed (user_id, last_claim) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_claim = ?", (user_id, current_time, current_time))
            conn.commit()
            conn.close()

            update_balance(user_id, gift_amount)
            gift_msg = (
                f"🎁 **خود يا غالي هديتك الفرفوشية!**\n"
                f"تم إضافة **{gift_amount:,}** ليرة وهمية لرصيدك بنجاح! 🎉\n"
                f"💡 يمكنك العودة وأخذ هدية جديدة بعد **6 ساعات**!"
            )
            bot.reply_to(message, gift_msg, parse_mode="Markdown")
        return

    # ==================== أسئلة صراحة بالذكاء الاصطناعي ====================
    if text in ["صراحة", "صراحه", "اسئلة صراحة", "سؤال صراحة"]:
        thinking_s = bot.reply_to(message, "جاري إحضار سؤال صراحة محرج بامتياز... 😳")
        ai_q = ask_ai_saraha_question()
        try:
            bot.edit_message_text(f"😳 **سؤال صراحة (من الذكاء الاصطناعي):**\n\n{ai_q}\n\n💬 أتحفنا بإجابتك بكل صراحة وبدون هروب!", chat_id, thinking_s.message_id, parse_mode="Markdown")
        except:
            bot.reply_to(message, f"😳 **سؤال صراحة:**\n\n{ai_q}")
        return

    # ==================== لعبة فرفوش اتحداك ====================
    if text in ["فرفوش اتحداك", "اتحداك", "تحدي فرفوش"]:
        farfoosh_challenge_users[user_id] = True
        bot.reply_to(message, "🎯 **تحدي فرفوش الأصلي!**\n\nأرسل لي أي **حرف عربي** الآن وسأعطيك حكمة فرفوشية جبارة تبدأ بنفس الحرف! 😎🔥", parse_mode="Markdown")
        return

    if user_id in farfoosh_challenge_users:
        del farfoosh_challenge_users[user_id]
        user_letter = text.strip()[0] if text.strip() else "ف"
        prompt_chal = f"أعطني حكمة فرفوشية سورية مضحكة ومبتكرة تبدأ بالحرف '{user_letter}'."
        phrase = fetch_ai_answer(prompt_chal)
        bot.reply_to(message, f"🎯 **تحدي فرفوش بالحرف ({user_letter}):**\n\n{phrase}\n\n😎 شو رأيك بفرفوش معلمك؟ 😉🔥", parse_mode="Markdown")
        return

    # ==================== لعبة "مين كفو" ====================
    if text in ["مين كفو", "مين كفو؟"]:
        if chat_id in min_kafo_games:
            bot.reply_to(message, "⚠️ يوجد لعبة 'مين كفو' مفتوحة حالياً في المجموعة! شارك فيها بـ إرسال كلمة (انا) بدلاً من فتح لعبة جديدة 😉")
            return

        min_kafo_games[chat_id] = {
            'host_id': user_id,
            'host_name': message.from_user.first_name,
            'participants': {user_id: message.from_user.first_name},
            'status': 'waiting'
        }
        bot.reply_to(
            message,
            f"⚔️ **تحدي مين كفو الأقوى!** 🔥\n\n"
            f"أنشأ التحدي: **{message.from_user.first_name}**\n"
            f"من يريد المشاركة ويريد إثبات أنه كفو يرسل كلمة: **انا** 🙋‍♂️\n\n"
            f"👑 عندما يكتمل انضمام الأعضاء، يرسل صاحب اللعبة (**{message.from_user.first_name}**) كلمة: **بلشها** لبدء التحدي!",
            parse_mode="Markdown"
        )
        return

    if text.lower() in ["انا", "أنا"] and chat_id in min_kafo_games:
        game = min_kafo_games[chat_id]
        if game['status'] == 'waiting':
            if user_id not in game['participants']:
                game['participants'][user_id] = message.from_user.first_name
                count = len(game['participants'])
                bot.reply_to(message, f"✅ تم انضمامك للتحدي يا **{message.from_user.first_name}**! (عدد الكفو الحالي: {count})", parse_mode="Markdown")
            else:
                bot.reply_to(message, "أنت منضم في اللعبة مسبقاً! 😉")
            return

    if text.lower() in ["بلشها", "بلش"] and chat_id in min_kafo_games:
        game = min_kafo_games[chat_id]
        if game['status'] == 'waiting':
            if user_id != game['host_id'] and not is_admin(user_id):
                bot.reply_to(message, f"⚠️ فقط **{game['host_name']}** الذي فتح اللعبة يستطيع إرسال **بلشها** لبدء التحدي!", parse_mode="Markdown")
                return

            participants = list(game['participants'].items())
            if not participants:
                bot.reply_to(message, "لا يوجد مشاركون في اللعبة بعد!")
                return

            game['status'] = 'running'
            victim_id, victim_name = random.choice(participants)

            penalties_pool = ["mute_5min", "change_name", "embarrassing_question", "funny_judgments"]
            chosen_p = random.choice(penalties_pool)
            curr_t = int(time.time())

            if chosen_p == "mute_5min":
                expire_t = curr_t + 300
                muted_5min_users[(chat_id, victim_id)] = expire_t
                try:
                    bot.restrict_chat_member(chat_id, victim_id, until_date=expire_t, can_send_messages=False)
                except Exception:
                    pass
                bot.send_message(
                    chat_id,
                    f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n"
                    f"وقع الاختيار على الكفو: **[{victim_name}](tg://user?id={victim_id})** 🎯\n\n"
                    f"🤐 **الحكم:** تم كتمك لمدة **5 دقائق** كاملاً! حتا لو كنت مشرفاً أو عضواً ستُحذف رسائلك تلقائياً حتى انقضاء الـ 5 دقائق 🤫",
                    parse_mode="Markdown"
                )

            elif chosen_p == "change_name":
                target_names = ["دبدوب الفرفوش", "أمير الفجل", "ملك الشاورما", "سلطان الملوخية", "شيخ المحشي", "فرفوش الصغير", "كابتن البندورة"]
                req_name = random.choice(target_names)
                expire_t = curr_t + 300
                name_penalties[(chat_id, victim_id)] = {'target_name': req_name, 'expire_time': expire_t}

                bot.send_message(
                    chat_id,
                    f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n"
                    f"وقع الاختيار على: **[{victim_name}](tg://user?id={victim_id})** 🎯\n\n"
                    f"🏷️ **الحكم:** سمي حالك (**{req_name}**) أو تنكتم لمدة 5 دقائق!\n"
                    f"⚠️ يتعرف البوت على اسمك تلقائياً دون الحاجة للكتابة، وعند انتهاء الـ 5 دقائق ينتهي الكتم والتقييد تماماً مهما كان اسمك.",
                    parse_mode="Markdown"
                )

            elif chosen_p == "embarrassing_question":
                chosen_q = ask_ai_saraha_question()
                q_msg = bot.send_message(
                    chat_id,
                    f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n"
                    f"وقع الاختيار على المعاقب: **[{victim_name}](tg://user?id={victim_id})** 🎯\n\n"
                    f"😳 **العقوبة (سؤال محرج جداً):**\n"
                    f"❓ `{chosen_q}`\n\n"
                    f"⚠️ **تنبيه:** لن يتم السماح لك باللعب أو الكتابة إلا بعد إرسال الجواب بالرد على هذا السؤال!",
                    parse_mode="Markdown"
                )
                embarrassing_penalties[(chat_id, victim_id)] = {
                    'user_name': victim_name,
                    'question': chosen_q,
                    'msg_id': q_msg.message_id
                }

            else:
                funny_judgments = [
                    f"👑 **[{victim_name}](tg://user?id={victim_id})** أنت الكفو! ولكن الحكم عليك: اعترف بأحرج موقف صار معك بحياتك فوراً 😂",
                    f"😜 **[{victim_name}](tg://user?id={victim_id})** طلعت مو كفو هالمرة! الحكم: غير صورتك الشخصية لمدة يوم كامل أو اعزم الجروب على شاورما 🌯",
                    f"🔥 **[{victim_name}](tg://user?id={victim_id})** حكم القدر: اعترف مين أكثر عضو بتموت منه بالجروب وبدون مجاملة! 🤫",
                    f"🎭 **[{victim_name}](tg://user?id={victim_id})** حكم القدر: أرسل بصمة صوت وأنت عم تغني أغنية للأطفال وشوف تقييم الجروب إلك 🎤"
                ]
                bot.send_message(chat_id, f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n{random.choice(funny_judgments)}", parse_mode="Markdown")

            del min_kafo_games[chat_id]
            return

    # سرقة المأكولات والمشروبات
    if text.startswith("طعميني") or text.startswith("شربني"):
        item_req = text.replace("طعميني", "").replace("شربني", "").strip()
        if not item_req:
            bot.reply_to(message, "💡 للسرقة أو إطعام/إشراب نفسك أرسل بالرد على عضو:\n`طعميني شاورما` أو `شربني متة`", parse_mode="Markdown")
            return

        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ يجب الرد (Reply) على رسالة العضو الذي تريد أن تأكل/تشرب منه!")
            return

        target_user = message.reply_to_message.from_user
        if target_user.id == user_id:
            bot.reply_to(message, "عم تطعمي حالك من حالك؟ هاد انفصام شخصية! 😂")
            return
        if target_user.is_bot:
            bot.reply_to(message, "البوتات ما بتاكل ولا بتشرب يا حباب! 🤖")
            return

        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_steal FROM food_steal_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 1200: # 20 دقيقة
            remaining_mins = int((1200 - (current_time - row[0])) / 60) + 1
            bot.reply_to(message, f"⏳ طول بالك يا مفجوع! السرقة مقيدة مرة كل 20 دقيقة.\nباقي: `{remaining_mins}` دقيقة ⏱️", parse_mode="Markdown")
            conn.close()
            return

        c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name LIKE ?", (target_user.id, f"%{item_req}%"))
        inv_row = c.fetchone()

        if inv_row and inv_row[0] > 0:
            target_qty = inv_row[0]
            stolen_qty = min(random.randint(1, 50), target_qty)

            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name LIKE ?", (stolen_qty, target_user.id, f"%{item_req}%"))
            c.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?", (user_id, item_req, stolen_qty, stolen_qty))
            c.execute("INSERT INTO food_steal_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?", (user_id, current_time, current_time))
            conn.commit()

            funny_food_success = [
                f"🥷 هجمت بلهفة وسرقت من {target_user.first_name} عدد **{stolen_qty}** من ({item_req}) وأكلتها بلمح البصر! صحتين وهنا على قلبك 😂",
                f"😋 دخلت على غفلة وطيرت لـ {target_user.first_name} **{stolen_qty}** حبة ({item_req})! يا سلام شو طيبة!",
                f"🕵️‍♂️ غافلت {target_user.first_name} وشفطت من جيبته **{stolen_qty}** ({item_req}) ورحت لبعيد تلغّم فيها!"
            ]
            bot.reply_to(message, random.choice(funny_food_success), parse_mode="Markdown")
        else:
            c.execute("INSERT INTO food_steal_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?", (user_id, current_time, current_time))
            conn.commit()
            funny_food_fail = [
                f"😭 جيت لتطعمي حالك من {target_user.first_name} طلع ما معو ولا حبة ({item_req})! مسكين مفلس معتر!",
                f"❌ فتشت بجيوب {target_user.first_name} لقيتهافاضية ما فيها ولا قطعة ({item_req})!"
            ]
            bot.reply_to(message, random.choice(funny_food_fail))
        conn.close()
        return

    # الردود التلقائية المخصصة
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT response, media_type, file_id FROM custom_replies WHERE keyword = ?", (text,))
    replies = c.fetchall()
    conn.close()
    if replies:
        selected_reply = random.choice(replies)
        rep_text, media_type, file_id = selected_reply[0], selected_reply[1], selected_reply[2]
        if media_type == 'sticker' and file_id:
            bot.send_sticker(chat_id, file_id, reply_to_message_id=message.message_id)
        elif media_type == 'photo' and file_id:
            bot.send_photo(chat_id, file_id, caption=rep_text, reply_to_message_id=message.message_id)
        elif media_type == 'video' and file_id:
            bot.send_video(chat_id, file_id, caption=rep_text, reply_to_message_id=message.message_id)
        elif media_type == 'audio' and file_id:
            bot.send_audio(chat_id, file_id, caption=rep_text, reply_to_message_id=message.message_id)
        elif media_type == 'voice' and file_id:
            bot.send_voice(chat_id, file_id, reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, rep_text)
        return

    # أسئلة جيمني المباشرة
    if text == "عندي سؤال" or text.startswith("عندي سؤال "):
        if not is_gemini_enabled(chat_type, chat_id, user_id):
            bot.reply_to(message, "عليك الاشتراك في هذه الميزة حدث المطور @syabd0")
            return

        q_part = text.replace("عندي سؤال", "").strip()
        if q_part:
            thinking_msg = bot.reply_to(message, "جاري التفكير والبحث... 🔍")
            ans = fetch_ai_answer(q_part)
            try:
                bot.edit_message_text(ans, chat_id, thinking_msg.message_id)
            except:
                bot.reply_to(message, ans)
        else:
            user_gemini_states[user_id] = "wait_gemini_question"
            bot.reply_to(message, "اكتب ماهو سؤالك انا اسمعك")
        return

    if text == "بدي ساوي صورة" or text.startswith("بدي ساوي صورة "):
        if not is_gemini_enabled(chat_type, chat_id, user_id):
            bot.reply_to(message, "عليك الاشتراك في هذه الميزة حدث المطور @syabd0")
            return

        p_part = text.replace("بدي ساوي صورة", "").strip()
        if p_part:
            gen_msg = bot.reply_to(message, "🎨 جاري رسم الصورة... يرجى الانتظار قليلاً.")
            img_data = generate_image_pollinations(p_part)
            if img_data:
                try:
                    safe_delete_message(chat_id, gen_msg.message_id)
                except:
                    pass
                bot.send_photo(chat_id, photo=img_data, caption=f"🖼️ الصورة المطلوبة: `{p_part}`", reply_to_message_id=message.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ تعذر إنشاء الصورة حالياً، حاول بوصف آخر.", chat_id, gen_msg.message_id)
        else:
            user_gemini_states[user_id] = "wait_gemini_image_prompt"
            bot.reply_to(message, "اكتب وصف الصورة التي تريد إنشاءها:")
        return

    # الألعاب النشطة
    if chat_id in active_crime_games:
        game_data = active_crime_games[chat_id]
        if text.lower() == game_data['killer'].lower():
            update_balance(user_id, 50)
            bot.reply_to(message, f"🎉 كفووو يا بطل! اكتشفت القاتل الحقيقي ({game_data['killer']}) وتم إغلاق القضية! 🕵️‍♂️\nتم إضافة **50 ليرة وهمية** لرصيدك!", parse_mode="Markdown")
            del active_crime_games[chat_id]
            return

    if chat_id in active_series_games:
        correct_ans = active_series_games[chat_id].strip().lower()
        user_ans = text.strip().lower()
        if user_ans == correct_ans or correct_ans in user_ans:
            update_balance(user_id, 50)
            bot.reply_to(message, f"🎉 كفووو يا بطل! إجابة صحيحة، المسلسل هو ({active_series_games[chat_id]})! 📺\nتم إضافة **50 ليرة وهمية** لرصيدك!", parse_mode="Markdown")
            del active_series_games[chat_id]
            return

    if chat_id in active_riddles:
        if text.lower() == active_riddles[chat_id].lower():
            update_balance(user_id, 50)
            bot.reply_to(message, "🎉 أحسنت! إجابة صحيحة، ربحت **50 ليرة وهمية**.")
            del active_riddles[chat_id]
            return

    if chat_id in active_math_games:
        if text == str(active_math_games[chat_id]):
            update_balance(user_id, 50)
            bot.reply_to(message, "🧠 عبقري! إجابة رياضية صحيحة، ربحت **50 ليرة وهمية**.")
            del active_math_games[chat_id]
            return

    if chat_id in active_guess_games:
        if text.isdigit() and int(text) == active_guess_games[chat_id]:
            update_balance(user_id, 50)
            bot.reply_to(message, f"🎯 كفو! التخمين صحيح الرقم هو {active_guess_games[chat_id]}، ربحت **50 ليرة وهمية**.")
            del active_guess_games[chat_id]
            return

    # التحميل من يوتيوب وسمعني
    if text.startswith("يوتيوب") or text.lower().startswith("youtube"):
        query = re.sub(r'^(يوتيوب|youtube)', '', text, flags=re.IGNORECASE).strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الفيديو أو الأغنية أو الرابط بعد الأمر.\nمثال: `يوتيوب الشامي`", parse_mode="Markdown")
            return
        download_and_send_video(chat_id, query, message.message_id)
        return

    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الأغنية بعد الأمر.\nمثال: `سمعني اصالة`", parse_mode="Markdown")
            return
        download_and_send_audio(chat_id, query, message.message_id)
        return

    # لعبة الرهان
    if text.startswith("راهن"):
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_bet FROM bet_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            funny_bet_msgs = [
                f"🎲 طول بالك يا زلمة! الرهان مقيد كل دقيقة، استنى لك `{remaining_secs}` ثانية ودقّة ثانية ⏱️",
                f"🎲 اهدى شوي على جيبتك! فاضل `{remaining_secs}` ثانية للرهان الجاي 😂",
                f"🎲 لك ارحم رصيدك شوي! باقي `{remaining_secs}` ثانية ⏳"
            ]
            bot.reply_to(message, random.choice(funny_bet_msgs), parse_mode="Markdown")
            conn.close()
            return

        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            bet_amount = int(parts[1])
            bal = get_balance(user_id)
            if bet_amount <= 0:
                bot.reply_to(message, "⚠️ يجب إدخال مبلغ مراهنة أكبر من 0.")
                conn.close()
                return
            if bal < bet_amount:
                bot.reply_to(message, f"❌ رصيدك لا يكفي للمراهنة! معك حالياً {bal} ليرة.")
                conn.close()
                return
            
            c.execute("INSERT INTO bet_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_bet = ?", (user_id, current_time, current_time))
            conn.commit()
            conn.close()

            is_won = random.choices([True, False], weights=[60, 40])[0]
            if is_won:
                update_balance(user_id, bet_amount)
                bot.reply_to(message, f"🎲 **مراهنة ناجحة!**\nضاعفت مبلغك وربحت **{bet_amount}** ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                update_balance(user_id, -bet_amount)
                bot.reply_to(message, f"🎲 **مراهنة خاسرة!**\nللأسف خسرت المبلغ بالكامل (**{bet_amount}** ليرة)! 💔", parse_mode="Markdown")
        else:
            conn.close()
            bot.reply_to(message, "💡 للمراهنة أرسل:\n`راهن [المبلغ]`\nمثال: `راهن 20`", parse_mode="Markdown")
        return

    # لعبة العجلة
    if text in ["عجلة", "العجلة", "لعبة العجلة"]:
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_wheel FROM wheel_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            funny_wheel_msgs = [
                f"🎡 على مهلك يا حباب! العجلة بدها استراحة دقيقة، باقي `{remaining_secs}` ثانية وبتفتّ من جديد 🎡",
                f"🎡 روق المانجا شوي! فاضل `{remaining_secs}` ثانية ⏱",
                f"🎡 لك هلكتها للعجلة! استنى لك `{remaining_secs}` ثانية وارجع أدرها 🌀"
            ]
            bot.reply_to(message, random.choice(funny_wheel_msgs), parse_mode="Markdown")
            conn.close()
            return

        bal = get_balance(user_id)
        if bal < 50:
            bot.reply_to(message, "❌ تكلفة تدوير العجلة هي 50 ليرة ورصيدك لا يكفي!")
            conn.close()
            return

        update_balance(user_id, -50)
        c.execute("INSERT INTO wheel_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_wheel = ?", (user_id, current_time, current_time))
        conn.commit()
        conn.close()

        is_win = random.choices([True, False], weights=[60, 40])[0]
        if is_win:
            won = random.choice([50, 100, 200, 500, 1000, 2000])
            update_balance(user_id, won)
            bot.reply_to(message, f"🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وربحت **{won}** ليرة وهمية! 🎉", parse_mode="Markdown")
        else:
            bot.reply_to(message, "🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وخسرت! حظاً أفضل في المرة القادمة 💔", parse_mode="Markdown")
        return

    # لعبة XO
    if text in ["اكسني", "لعبة اكس اوه"]:
        bot.send_message(chat_id, f"🎮 **لعبة XO جديدة ومجانية بالكامل!**\nالمنافس الأول: {message.from_user.first_name}\n🎁 **جائزة الفائز:** 100 ليرة وهمية!\nاضغط للانضمام والمنافسة:", reply_markup=get_xo_keyboard(None, user_id, message.from_user.first_name))
        return

    # المطعم والمتجر
    if text in ["مطعم", "المطعم"]:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        msg_text = "🍔 **قائمة المطعم والمتجر:**\n\n"
        for name, price in items:
            msg_text += f"• {name} 👈 {price} ليرة\n"
        msg_text += "\n🛒 **الأوامر المتاحة:**\n"
        msg_text += "• للشراء: `شراء 1 شاورما`\n"
        msg_text += "• للبيع: `بيع 1 شاورما`\n"
        msg_text += "• للإهداء: `اهداء 1 شاورما` (بالرد)\n"
        msg_text += "• للسرقة والتسلية: `طعميني شاورما` أو `شربني متة` (بالرد على عضو)"
        bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        return

    if text.startswith("اهداء") or text.startswith("إهداء"):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1].isdigit():
            count = int(parts[1])
            item_name = parts[2].strip()

            if not message.reply_to_message:
                bot.reply_to(message, "⚠️ يجب الرد (Reply) على رسالة الشخص الذي تريد إهداءه الصنف!")
                return

            target_user = message.reply_to_message.from_user
            if target_user.id == user_id:
                bot.reply_to(message, "عم تهدي حالك؟ ما بتزبط!")
                return

            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name LIKE ?", (user_id, f"%{item_name}%"))
            row = c.fetchone()

            if row and row[0] >= count:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name LIKE ?", (count, user_id, f"%{item_name}%"))
                c.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?", (target_user.id, item_name, count, count))
                conn.commit()
                bot.reply_to(message, f"🎁 **إهداء جديد!**\nأهدى {message.from_user.first_name} إلى {target_user.first_name} **{count} {item_name}**! يا سلام على الكرم ❤️", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"❌ لا تملك هذا العدد ({count}) من ({item_name}) لإهدائه!")
            conn.close()
            return

    if text.startswith("بيع"):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1].isdigit():
            count = int(parts[1])
            item_name = parts[2].strip()

            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT price FROM store WHERE item_name LIKE ?", (f"%{item_name}%",))
            store_row = c.fetchone()
            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name LIKE ?", (user_id, f"%{item_name}%"))
            inv_row = c.fetchone()

            if inv_row and inv_row[0] >= count:
                orig_price = store_row[0] if store_row else 10
                refund_per_item = orig_price // 2
                total_refund = refund_per_item * count
                
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name LIKE ?", (count, user_id, f"%{item_name}%"))
                conn.commit()
                
                update_balance(user_id, total_refund)
                bot.reply_to(message, f"💰 **تم البيع بنجاح!**\nقمت ببيع **{count} {item_name}** واسترددت **{total_refund}** ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"❌ لا تملك هذا العدد ({count}) من ({item_name}) لبيعه!")
            conn.close()
            return

    if text.startswith("شراء"):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1].isdigit():
            count = int(parts[1])
            item_name = parts[2].strip()
            
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT item_name, price FROM store WHERE item_name LIKE ?", (f"%{item_name}%",))
            price_row = c.fetchone()
            
            if price_row:
                real_item_name = price_row[0]
                total_price = price_row[1] * count
                bal = get_balance(user_id)
                if bal >= total_price:
                    update_balance(user_id, -total_price)
                    c.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?", (user_id, real_item_name, count, count))
                    conn.commit()
                    bot.reply_to(message, f"✅ تم شراء {count} {real_item_name} بنجاح!")
                else:
                    bot.reply_to(message, "❌ رصيدك غير كافي!")
            else:
                bot.reply_to(message, "❌ هذا الصنف غير موجود بالمتجر!")
            conn.close()
        return

    if text in ["خمن المسلسل", "لعبة خمن المسلسل", "مسلسلات"]:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question, answer FROM series_questions ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            active_series_games[chat_id] = row[1]
            bot.send_message(chat_id, f"📺 **تحدي خمن المسلسل:**\n\n{row[0]}\n\n💡 أول شخص يكتب اسم المسلسل يربح **50 ليرة وهمية**!")
        else:
            bot.send_message(chat_id, "لا توجد أسئلة مسلسلات مضافة بعد.")
        return

    if text in ["القاتل", "من هو القاتل", "لعبة القاتل"]:
        start_crime_game(chat_id)
        return

    if text == "قرض":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT amount FROM loans WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0] > 0:
            bot.reply_to(message, f"⚠️ لديك قرض قديم بقيمة {row[0]} ليرة لم تسدده بعد!")
        else:
            current_time = int(time.time())
            c.execute("INSERT INTO loans (user_id, amount, loan_time) VALUES (?, 100, ?) ON CONFLICT(user_id) DO UPDATE SET amount = 100, loan_time = ?", (user_id, current_time, current_time))
            conn.commit()
            update_balance(user_id, 100)
            bot.reply_to(message, "💰 تم إضافة 100 ليرة وهمية إلى رصيدك كقرض.\n⚠️ يجب عليك سداده خلال ساعتين بإرسال `دفع ديني` وإلا ستسجن!")
        conn.close()
        return

    if text in ["دفع ديني", "دفع دينو"]:
        target_id = user_id
        if message.reply_to_message and text == "دفع دينو":
            target_id = message.reply_to_message.from_user.id

        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT amount FROM loans WHERE user_id = ?", (target_id,))
        row = c.fetchone()

        if row and row[0] > 0:
            debt_amount = row[0]
            payer_bal = get_balance(user_id)
            if payer_bal >= debt_amount:
                update_balance(user_id, -debt_amount)
                c.execute("UPDATE loans SET amount = 0 WHERE user_id = ?", (target_id,))
                conn.commit()
                bot.reply_to(message, f"✅ تم تسديد الدين بمبلغ {debt_amount} ليرة بنجاح والخروج من السجن!")
            else:
                bot.reply_to(message, f"❌ الرصيد غير كافي لتسديد الدين المحدد ({debt_amount} ليرة)!")
        else:
            bot.reply_to(message, "لا يوجد أي ديون مستحقة!")
        conn.close()
        return

    if text in ["سرقة", "سرقه"]:
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ يجب أن تقوم بالرد (Reply) على رسالة العضو الذي تريد سرقته!")
            return
        
        target_user = message.reply_to_message.from_user
        if target_user.id == user_id:
            bot.reply_to(message, "عم تسرق حالك؟ ما بتزبط 🤦‍♂️")
            return
        if target_user.is_bot:
            bot.reply_to(message, "ما فيك تسرق بوت يا حباب 🤖")
            return

        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_steal FROM steal_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 900:
            remaining_mins = int((900 - (current_time - row[0])) / 60) + 1
            bot.reply_to(message, f"⏳ السرقة مقيدة! يمكنك السرقة مرة واحدة كل 15 دقيقة.\nيرجى الانتظار: `{remaining_mins}` دقيقة.", parse_mode="Markdown")
            conn.close()
            return

        target_bal = get_balance(target_user.id)

        if target_bal <= 0:
            bot.reply_to(message, f"😭 {target_user.first_name} مفلس أصلًا وعم يشحذ بالجروب، ارحمه!")
            conn.close()
            return

        steal_success = random.choices([True, False], weights=[80, 20])[0]

        c.execute("INSERT INTO steal_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?", (user_id, current_time, current_time))
        conn.commit()
        conn.close()

        if steal_success:
            stolen_amount = max(1, int(target_bal * random.uniform(0.05, 0.15)))
            update_balance(target_user.id, -stolen_amount)
            update_balance(user_id, stolen_amount)
            bot.reply_to(message, f"🥷 دخلت عالساكت وسحبت من جيبة {target_user.first_name} مبلغ **{stolen_amount}** ليرة!", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"🚨 كشفك {target_user.first_name} وأنت عم تمد إيدك ونفدت بالريش 😂")
        return

    # لعبة الاستثمار
    if text.startswith("استثمار"):
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_invest FROM invest_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 900:
            remaining_mins = int((900 - (current_time - row[0])) / 60) + 1
            bot.reply_to(message, f"⏳ الاستثمار مقيد! يمكنك الاستثمار مرة واحدة كل 15 دقيقة.\nيرجى الانتظار: `{remaining_mins}` دقيقة.", parse_mode="Markdown")
            conn.close()
            return

        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            inv_amount = int(parts[1])
            bal = get_balance(user_id)
            if inv_amount <= 0 or bal < inv_amount:
                bot.reply_to(message, "❌ رصيدك لا يكفي للاستثمار!")
                conn.close()
                return

            c.execute("INSERT INTO invest_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_invest = ?", (user_id, current_time, current_time))
            conn.commit()
            conn.close()

            is_success = random.choices([True, False], weights=[60, 40])[0]
            if is_success:
                gain_percent = random.randint(20, 90)
                profit = int(inv_amount * (gain_percent / 100))
                update_balance(user_id, profit)
                bot.reply_to(message, f"📈 **استثمار ناجح!**\nارتفعت الأسهم بنسبة `{gain_percent}%` وربحت **{profit}** ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                loss_percent = random.randint(10, 40)
                loss = int(inv_amount * (loss_percent / 100))
                update_balance(user_id, -loss)
                bot.reply_to(message, f"📉 **استثمار فاشل!**\nهبطت الأسهم بنسبة `{loss_percent}%` وخسرت **{loss}** ليرة وهمية! 💔", parse_mode="Markdown")
        else:
            conn.close()
            bot.reply_to(message, "💡 للاستثمار أرسل:\n`استثمار [المبلغ]`", parse_mode="Markdown")
        return

    if text in ["رياضيات", "لعبة رياضيات"]:
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
        ans = eval(f"{n1} {op} {n2}")
        active_math_games[chat_id] = ans
        bot.send_message(chat_id, f"🧮 **تحدي الرياضيات السريع:**\nكم الناتج: `{n1} {op} {n2}` ؟\nأول شخص يكتب الناتج يربح **50 ليرة**!", parse_mode="Markdown")
        return

    if text in ["خمن رقم", "لعبة خمن رقم"]:
        target = random.randint(1, 20)
        active_guess_games[chat_id] = target
        bot.send_message(chat_id, "🎯 **تحدي خمن الرقم:**\nخمنت رقم من `1` إلى `20`!\nأول شخص يكتب الرقم الصحيح يربح **50 ليرة**.", parse_mode="Markdown")
        return

    if text in ["الالعاب", "الألعاب", "العاب"]:
        send_games_menu(chat_id)
        return

    if text == "حزرني":
        start_riddle_game(chat_id)
        return

    if text == "مصرياتي":
        bal = get_balance(user_id)
        bot.reply_to(message, f"💰 معك حالياً: {bal} ليرة وهمية.")
        return

    if text in ["المتجر"]:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        msg_text = "🛍 **قائمة المشتريات المتوفرة:**\n\n"
        for name, price in items:
            msg_text += f"• {name} 👈 {price} ليرة\n"
        msg_text += "\nللشراء ارسل: `شراء 1 شاورما` مثلاً"
        bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        return

    if text == "املاكي":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0", (user_id,))
        items = c.fetchall()
        conn.close()
        if items:
            msg_text = "📦 **ممتلكاتك الشخصية:**\n\n" + "\n".join([f"• {name}: {qty}" for name, qty in items])
            bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا تملك أي غرض حالياً.")
        return

    if text == "اسالني":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question FROM questions ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            bot.send_message(chat_id, f"❓ **سؤال لك:**\n{row[0]}", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد أسئلة مضافة بعد.")
        return

# ==================== إدارة الألعاب والـ XO ====================
def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO", callback_data="game_xo"),
        types.InlineKeyboardButton("⚔️ مين كفو", callback_data="game_kafo"),
        types.InlineKeyboardButton("🧩 حزرني", callback_data="game_riddle"),
        types.InlineKeyboardButton("🔪 القاتل", callback_data="game_crime"),
        types.InlineKeyboardButton("📺 خمن المسلسل", callback_data="game_series"),
        types.InlineKeyboardButton("🧮 تحدي الرياضيات", callback_data="game_math"),
        types.InlineKeyboardButton("🎯 خمن الرقم", callback_data="game_guess"),
        types.InlineKeyboardButton("🎡 عجلة الحظ", callback_data="game_wheel")
    )
    bot.send_message(chat_id, "🎲 **قائمة الألعاب والتحديات التفاعلية:**", reply_markup=markup, parse_mode="Markdown")

def start_riddle_game(chat_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT question, answer FROM riddles ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        active_riddles[chat_id] = row[1]
        bot.send_message(chat_id, f"🧩 **حزورة جديدة:**\n{row[0]}\n\n💡 الإجابة الصحيحة تمنحك **50 ليرة وهمية**!")
    else:
        bot.send_message(chat_id, "لا توجد حزازير مضافة بعد.")

def start_crime_game(chat_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT id, story, killer, suspects FROM crime_stories ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        active_crime_games[chat_id] = {'story_id': row[0], 'killer': row[2], 'suspects': row[3]}
        msg = f"🔪 **لعبة من هو القاتل:**\n\n📜 {row[1]}\n\n👥 **المشتبه بهم:** {row[3]}\n\n💡 ارسل اسم القاتل لحل القضية وربح **50 ليرة وهمية**!"
        bot.send_message(chat_id, msg)
    else:
        bot.send_message(chat_id, "لا توجد قضايا مضافة بعد.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_games_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    chat_id = call.message.chat.id
    action = call.data.replace('game_', '')
    if action == "xo":
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة ومجانية بالكامل!\nأنشأ اللعبة: {call.from_user.first_name}\n🎁 الرابح يحصل على 100 ليرة!", reply_markup=get_xo_keyboard(None, call.from_user.id, call.from_user.first_name))
    elif action == "kafo":
        bot.send_message(chat_id, "⚔️ لبدء لعبة مين كفو، أرسل كلمة **مين كفو** في المجموعة!")
    elif action == "riddle":
        start_riddle_game(chat_id)
    elif action == "crime":
        start_crime_game(chat_id)
    elif action == "series":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question, answer FROM series_questions ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            active_series_games[chat_id] = row[1]
            bot.send_message(chat_id, f"📺 **تحدي خمن المسلسل:**\n\n{row[0]}\n\n💡 أول شخص يكتب اسم المسلسل يربح **50 ليرة وهمية**!")
    elif action == "math":
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        active_math_games[chat_id] = n1 + n2
        bot.send_message(chat_id, f"🧮 كم الناتج: `{n1} + {n2}` ؟", parse_mode="Markdown")
    elif action == "guess":
        active_guess_games[chat_id] = random.randint(1, 20)
        bot.send_message(chat_id, "🎯 خمن رقم من `1` إلى `20`!", parse_mode="Markdown")
    elif action == "wheel":
        bot.send_message(chat_id, "🎡 للعب العجلة أرسل كلمة `عجلة` بالدردشة (التكلفة 50 ليرة).")

# ==================== نظام لعبة XO الكامل والتفاعلي ====================
def get_xo_keyboard(game_data=None, host_id=None, host_name=""):
    markup = types.InlineKeyboardMarkup()
    if not game_data:
        markup.add(types.InlineKeyboardButton(f"الانضمام للعب مع {host_name} 🎮", callback_data=f"xo_start_{host_id}"))
        return markup
    
    board = game_data['board']
    game_id = game_data['game_id']
    for i in range(3):
        row_btns = []
        for j in range(3):
            idx = i * 3 + j
            val = board[idx] if board[idx] else " "
            row_btns.append(types.InlineKeyboardButton(val, callback_data=f"xo_move_{game_id}_{idx}"))
        markup.row(*row_btns)
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('xo_'))
def handle_xo_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    if data.startswith("xo_start_"):
        host_id = int(data.replace("xo_start_", ""))
        if user_id == host_id:
            try:
                bot.answer_callback_query(call.id, "⚠️ لا يمكنك الانضمام للعب ضد نفسك!", show_alert=True)
            except:
                pass
            return

        game_id = f"{chat_id}_{int(time.time())}"
        xo_games[game_id] = {
            'game_id': game_id,
            'board': [None] * 9,
            'player_x': host_id,
            'player_x_name': call.message.reply_markup.keyboard[0][0].text.replace("الانضمام للعب مع ", "").replace(" 🎮", ""),
            'player_o': user_id,
            'player_o_name': call.from_user.first_name,
            'turn': host_id,
            'chat_id': chat_id
        }
        g = xo_games[game_id]
        bot.edit_message_text(
            f"🎮 **بدأت لعبة XO!**\n\n❌ **{g['player_x_name']}** ضد ⭕ **{g['player_o_name']}**\n\n👉 الدور الآن لـ: ❌ **{g['player_x_name']}**",
            chat_id, call.message.message_id,
            reply_markup=get_xo_keyboard(g),
            parse_mode="Markdown"
        )

    elif data.startswith("xo_move_"):
        parts = data.split("_")
        if len(parts) < 4:
            return
        idx = int(parts[-1])
        game_id = "_".join(parts[2:-1])

        if game_id not in xo_games:
            try:
                bot.answer_callback_query(call.id, "⚠️ هذه اللعبة انتهت أو أصبحت غير صالحة!", show_alert=True)
            except:
                pass
            return

        g = xo_games[game_id]
        if user_id != g['turn']:
            try:
                bot.answer_callback_query(call.id, "⚠️ ليس دورك الآن!", show_alert=True)
            except:
                pass
            return

        if g['board'][idx] is not None:
            try:
                bot.answer_callback_query(call.id, "⚠️ هذا المربع مشغول من قبل!", show_alert=True)
            except:
                pass
            return

        symbol = "❌" if user_id == g['player_x'] else "⭕"
        g['board'][idx] = symbol

        # فحص الفوز
        win_combos = [
            (0,1,2), (3,4,5), (6,7,8),
            (0,3,6), (1,4,7), (2,5,8),
            (0,4,8), (2,4,6)
        ]
        winner = None
        for a, b, c_idx in win_combos:
            if g['board'][a] and g['board'][a] == g['board'][b] == g['board'][c_idx]:
                winner = user_id
                break

        if winner:
            winner_name = g['player_x_name'] if winner == g['player_x'] else g['player_o_name']
            update_balance(winner, 100)
            bot.edit_message_text(
                f"🎉 **مبروك الفوز في لعبة XO!**\n\n🏆 الفائز: **{winner_name}** ({symbol})\n🎁 تم إضافة **100 ليرة وهمية** لرصيدك!",
                chat_id, call.message.message_id,
                reply_markup=get_xo_keyboard(g),
                parse_mode="Markdown"
            )
            del xo_games[game_id]
            return

        # فحص التعادل
        if None not in g['board']:
            bot.edit_message_text(
                f"🤝 **تعادل في لعبة XO!**\n\nانتهت المباراة بالتعادل بين **{g['player_x_name']}** و **{g['player_o_name']}**.",
                chat_id, call.message.message_id,
                reply_markup=get_xo_keyboard(g),
                parse_mode="Markdown"
            )
            del xo_games[game_id]
            return

        # تبديل الدور
        g['turn'] = g['player_o'] if g['turn'] == g['player_x'] else g['player_x']
        next_name = g['player_x_name'] if g['turn'] == g['player_x'] else g['player_o_name']
        next_symbol = "❌" if g['turn'] == g['player_x'] else "⭕"

        bot.edit_message_text(
            f"🎮 **لعبة XO قائمة!**\n\n❌ **{g['player_x_name']}** ضد ⭕ **{g['player_o_name']}**\n\n👉 الدور الآن لـ: {next_symbol} **{next_name}**",
            chat_id, call.message.message_id,
            reply_markup=get_xo_keyboard(g),
            parse_mode="Markdown"
        )

# ==================== معالجة أزرار لوحة الإدارة والدوال الخاصة بها ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_') or call.data == "open_admin_panel")
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if not is_admin(user_id):
        try:
            bot.answer_callback_query(call.id, "⚠️ هذه اللوحة مخصصة للمشرفين والآدمن فقط!", show_alert=True)
        except:
            pass
        return

    data = call.data

    if data in ["open_admin_panel", "admin_panel_back"]:
        try:
            bot.edit_message_text("⚙️ **لوحة التحكم والإدارة الشاملة للبوت:**\nاختر من الأزرار التالية للتعديل والتحكم:", chat_id, call.message.message_id, reply_markup=get_admin_keyboard(), parse_mode="Markdown")
        except:
            bot.send_message(chat_id, "⚙️ **لوحة التحكم والإدارة الشاملة للبوت:**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

    elif data == "admin_broadcast_all":
        admin_states[user_id] = {'stage': 'broadcast_all'}
        bot.send_message(chat_id, "📢 **أرسل الرسالة الآن (نص، صورة، فيديو، إلخ) للإذاعة لجميع المستخدمين والمجموعات:**", parse_mode="Markdown")

    elif data == "admin_broadcast_groups":
        admin_states[user_id] = {'stage': 'broadcast_groups'}
        bot.send_message(chat_id, "👥 **أرسل الرسالة الآن (نص، صورة، فيديو، إلخ) للإذاعة لجميع المجموعات:**", parse_mode="Markdown")

    elif data == "admin_select_group_msg":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        conn.close()

        if not groups:
            bot.send_message(chat_id, "❌ لا توجد أي مجموعات مسجلة في قاعدة البيانات حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            markup.add(types.InlineKeyboardButton(f"💬 {g_title or 'جروب بدون عنوان'}", callback_data=f"admin_send_msg_grp_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        bot.send_message(chat_id, "📩 **اختر المجموعة التي تريد إرسال رسالة خاصة إليها:**", reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admin_send_msg_grp_"):
        target_g_id = int(data.replace("admin_send_msg_grp_", ""))
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT title FROM groups WHERE chat_id = ?", (target_g_id,))
        row = c.fetchone()
        conn.close()
        g_title = row[0] if row else "المجموعة"

        admin_states[user_id] = {'stage': 'send_msg_to_group', 'target_chat_id': target_g_id}
        bot.send_message(chat_id, f"✏️ **أرسل المحتوى الآن (نص، صورة، فيديو، صوت، ملصق، بصمة) لإرساله مباشرة إلى مجموعة ({g_title}):**", parse_mode="Markdown")

    elif data == "admin_add_reply":
        admin_states[user_id] = {'stage': 'wait_reply_keyword'}
        bot.send_message(chat_id, "✏️ **أرسل الكلمة المفتاحية (الكلمة) أولاً:**", parse_mode="Markdown")

    elif data == "admin_del_reply":
        admin_states[user_id] = {'stage': 'wait_del_reply_keyword'}
        bot.send_message(chat_id, "✏️ **أرسل الكلمة المفتاحية التي تريد حذف جميع ردودها المخصصة:**", parse_mode="Markdown")

    elif data == "admin_list_replies":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT keyword, media_type FROM custom_replies")
        rows = c.fetchall()
        conn.close()
        if not rows:
            bot.send_message(chat_id, "📋 لا توجد ردود مخصصة حالياً.")
        else:
            rep_summary = {}
            for kw, mt in rows:
                rep_summary[kw] = rep_summary.get(kw, 0) + 1
            items = [f"`{kw}` (عدد الردود: {cnt})" for kw, cnt in rep_summary.items()]
            send_large_text(chat_id, "📋 **قائمة الردود المخصصة المسجلة:**", items)

    elif data == "admin_mute_group_list":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM muted_groups")
        muted = [r[0] for r in c.fetchall()]
        conn.close()

        if not groups:
            bot.send_message(chat_id, "❌ لا توجد أي مجموعات مسجلة حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            status = "🔇 [مكتوم]" if g_id in muted else "🔊 [مفعل]"
            markup.add(types.InlineKeyboardButton(f"{status} {g_title or 'جروب'}", callback_data=f"admin_toggle_mute_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        bot.send_message(chat_id, "🔇 **إدارة إسكات المجموعات (اضغط على اسم المجموعة للتغيير):**", reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admin_toggle_mute_"):
        target_g_id = int(data.replace("admin_toggle_mute_", ""))
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (target_g_id,))
        if c.fetchone():
            c.execute("DELETE FROM muted_groups WHERE chat_id = ?", (target_g_id,))
            msg_text = "🔊 تم فك إسكات المجموعة بنجاح!"
        else:
            c.execute("INSERT INTO muted_groups (chat_id) VALUES (?)", (target_g_id,))
            msg_text = "🔇 تم إسكات المجموعة بنجاح!"
        conn.commit()

        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM muted_groups")
        muted = [r[0] for r in c.fetchall()]
        conn.close()

        try:
            bot.answer_callback_query(call.id, msg_text)
        except:
            pass

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            status = "🔇 [مكتوم]" if g_id in muted else "🔊 [مفعل]"
            markup.add(types.InlineKeyboardButton(f"{status} {g_title or 'جروب'}", callback_data=f"admin_toggle_mute_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
        except:
            pass

    elif data == "admin_leave_group_list":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        conn.close()

        if not groups:
            bot.send_message(chat_id, "❌ لا توجد مجموعات مسجلة حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            markup.add(types.InlineKeyboardButton(f"🚪 مغادرة: {g_title or 'جروب'}", callback_data=f"admin_confirm_leave_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        bot.send_message(chat_id, "🚪 **اختر المجموعة المراد مغادرتها:**", reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admin_confirm_leave_"):
        target_g_id = int(data.replace("admin_confirm_leave_", ""))
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT title FROM groups WHERE chat_id = ?", (target_g_id,))
        row = c.fetchone()
        conn.close()
        g_title = row[0] if row else "المجموعة"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ تأكيد المغادرة", callback_data=f"admin_do_leave_{target_g_id}"),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel_back")
        )
        bot.send_message(chat_id, f"⚠️ **هل أنت متأكد من مغادرة المجموعة ({g_title})؟**", reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admin_do_leave_"):
        target_g_id = int(data.replace("admin_do_leave_", ""))
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT title FROM groups WHERE chat_id = ?", (target_g_id,))
        row = c.fetchone()
        c.execute("DELETE FROM groups WHERE chat_id = ?", (target_g_id,))
        conn.commit()
        conn.close()
        g_title = row[0] if row else "المجموعة"

        try:
            bot.leave_chat(target_g_id)
            bot.send_message(chat_id, f"✅ تم مغادرة المجموعة **{g_title}** وحذفها من السجلات بنجاح!", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ تم مسح المجموعة من القاعدة ولكن تعذر المغادرة تلقائياً: {e}")

    elif data == "admin_add_admin":
        admin_states[user_id] = {'stage': 'wait_add_admin_id'}
        bot.send_message(chat_id, "✏️ **أرسل آيدي (ID) المستخدم المراد رفعه مشرفاً:**", parse_mode="Markdown")

    elif data == "admin_del_admin":
        admin_states[user_id] = {'stage': 'wait_del_admin_id'}
        bot.send_message(chat_id, "✏️ **أرسل آيدي (ID) المشرف المراد تنزيله:**", parse_mode="Markdown")

    elif data == "admin_list_admins":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        admins = [r[0] for r in c.fetchall()]
        conn.close()

        msg = f"📋 **قائمة المشرفين:**\n\n• المالك الرئيسي: `{ADMIN_ID}`\n"
        for a in admins:
            msg += f"• مشرف: `{a}`\n"
        bot.send_message(chat_id, msg, parse_mode="Markdown")

    elif data == "admin_add_fake_balance":
        admin_states[user_id] = {'stage': 'wait_fake_balance_user_id'}
        bot.send_message(chat_id, "➕ **أرسل آيدي (ID) المستخدم الذي تريد إضافة الرصيد الوهمي له:**", parse_mode="Markdown")

    elif data == "admin_stats":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        u_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM groups")
        g_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM custom_replies")
        r_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM muted_groups")
        m_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM gemini_groups")
        ge_cnt = c.fetchone()[0]
        conn.close()

        msg = (
            f"📊 **إحصائيات البوت الكاملة:**\n\n"
            f"👥 عدد المستخدمين المسجلين: `{u_cnt}`\n"
            f"🏰 عدد المجموعات المفعلة: `{g_cnt}`\n"
            f"💬 عدد الردود المخصصة: `{r_cnt}`\n"
            f"🔇 المجموعات المكتومة: `{m_cnt}`\n"
            f"🤖 مجموعات جيمني: `{ge_cnt}`\n"
            f"🎮 الألعاب المفتوحة حالياً: `{len(xo_games) + len(min_kafo_games) + len(active_riddles)}`"
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")

    elif data == "admin_gemini_groups":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM gemini_groups")
        gem_groups = [r[0] for r in c.fetchall()]
        conn.close()

        if not groups:
            bot.send_message(chat_id, "❌ لا توجد مجموعات مسجلة.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            st = "🟢 [مفعل]" if g_id in gem_groups else "🔴 [معطل]"
            markup.add(types.InlineKeyboardButton(f"{st} {g_title or 'جروب'}", callback_data=f"admin_toggle_gemini_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        bot.send_message(chat_id, "🤖 **تفعيل/تعطيل ذكاء جيمني المباشر في المجموعات:**", reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("admin_toggle_gemini_"):
        target_g_id = int(data.replace("admin_toggle_gemini_", ""))
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM gemini_groups WHERE chat_id = ?", (target_g_id,))
        if c.fetchone():
            c.execute("DELETE FROM gemini_groups WHERE chat_id = ?", (target_g_id,))
            st_msg = "🔴 تم تعطيل جيمني لهذه المجموعة."
        else:
            c.execute("INSERT INTO gemini_groups (chat_id) VALUES (?)", (target_g_id,))
            st_msg = "🟢 تم تفعيل جيمني لهذه المجموعة بنجاح!"
        conn.commit()

        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM gemini_groups")
        gem_groups = [r[0] for r in c.fetchall()]
        conn.close()

        try:
            bot.answer_callback_query(call.id, st_msg)
        except:
            pass

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, g_title in groups:
            st = "🟢 [مفعل]" if g_id in gem_groups else "🔴 [معطل]"
            markup.add(types.InlineKeyboardButton(f"{st} {g_title or 'جروب'}", callback_data=f"admin_toggle_gemini_{g_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_back"))
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
        except:
            pass

    elif data == "admin_game_logs":
        msg = (
            f"🎮 **سجلات الألعاب النشطة:**\n\n"
            f"• ألعاب XO الجارية: `{len(xo_games)}`\n"
            f"• تحديات مين كفو: `{len(min_kafo_games)}`\n"
            f"• الحزازير النشطة: `{len(active_riddles)}`\n"
            f"• قضايا القاتل: `{len(active_crime_games)}`\n"
            f"• تحديات المسلسلات: `{len(active_series_games)}`\n"
            f"• تحديات الرياضيات: `{len(active_math_games)}`\n"
            f"• تحديات تخمين الرقم: `{len(active_guess_games)}`"
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")

    elif data == "admin_reset_games":
        xo_games.clear()
        min_kafo_games.clear()
        active_riddles.clear()
        active_crime_games.clear()
        active_series_games.clear()
        active_math_games.clear()
        active_guess_games.clear()
        bot.send_message(chat_id, "🧹 **تم إعادة ضبط ومسح جميع الألعاب والجلسات النشطة بنجاح!**", parse_mode="Markdown")

def handle_admin_inputs(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or message.caption or "").strip()
    
    if user_id not in admin_states:
        return

    state = admin_states[user_id]
    stage = state.get('stage')

    if stage == 'broadcast_all':
        del admin_states[user_id]
        bot.reply_to(message, "📢 جاري بدء الإذاعة الشاملة للجميع...")
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        u_ids = [row[0] for row in c.fetchall()]
        c.execute("SELECT chat_id FROM groups")
        g_ids = [row[0] for row in c.fetchall()]
        conn.close()

        success, fail = 0, 0
        all_targets = set(u_ids + g_ids)
        for target in all_targets:
            try:
                bot.copy_message(target, chat_id, message.message_id)
                success += 1
            except:
                fail += 1
            time.sleep(0.05)
        bot.send_message(chat_id, f"✅ اكتملت الإذاعة!\nالنجاح: `{success}` | الفشل: `{fail}`", parse_mode="Markdown")

    elif stage == 'broadcast_groups':
        del admin_states[user_id]
        bot.reply_to(message, "👥 جاري بدء الإذاعة للمجموعات...")
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id FROM groups")
        g_ids = [row[0] for row in c.fetchall()]
        conn.close()

        success, fail = 0, 0
        for target in g_ids:
            try:
                bot.copy_message(target, chat_id, message.message_id)
                success += 1
            except:
                fail += 1
            time.sleep(0.05)
        bot.send_message(chat_id, f"✅ اكتملت الإذاعة للمجموعات!\nالنجاح: `{success}` | الفشل: `{fail}`", parse_mode="Markdown")

    elif stage == 'send_msg_to_group':
        target_chat_id = state.get('target_chat_id')
        del admin_states[user_id]
        try:
            bot.copy_message(target_chat_id, chat_id, message.message_id)
            bot.reply_to(message, f"✅ تم إرسال الرسالة إلى المجموعة بنجاح!")
        except Exception as e:
            bot.reply_to(message, f"❌ تعذر إرسال الرسالة إلى المجموعة: {e}")

    elif stage == 'wait_reply_keyword':
        if not text:
            bot.reply_to(message, "⚠ يرجى كتابة الكلمة المفتاحية كنص!")
            return
        admin_states[user_id] = {
            'stage': 'wait_reply_content',
            'keyword': text,
            'added_count': 0
        }
        bot.reply_to(
            message,
            f"✅ تم تسجيل الكلمة: **{text}**\n\n"
            f"الآن قم بإرسال المحتوى المطلوب (نص، صوت، فيديو، ملصق، صورة، أو بصمة).\n"
            f"💡 يمكنك إرسال أكثر من خيار متتابع، وعند الانتهاء تماماً اكتب كلمة **تم** للإنهاء.",
            parse_mode="Markdown"
        )

    elif stage == 'wait_reply_content':
        keyword = state.get('keyword')
        if text.lower() in ["تم", "تم.", "تم ينتهي", "انتهى"]:
            count = state.get('added_count', 0)
            del admin_states[user_id]
            bot.reply_to(message, f"✅ **تم إنهاء إضافة الردود وحفظها بنجاح!**\nالكلمة: `{keyword}`\nإجمالي الردود المضافة: `{count}`", parse_mode="Markdown")
            return

        media_type = 'text'
        resp_text = text
        file_id = None

        if message.sticker:
            media_type = 'sticker'
            resp_text = ''
            file_id = message.sticker.file_id
        elif message.photo:
            media_type = 'photo'
            resp_text = message.caption or ''
            file_id = message.photo[-1].file_id
        elif message.video:
            media_type = 'video'
            resp_text = message.caption or ''
            file_id = message.video.file_id
        elif message.audio:
            media_type = 'audio'
            resp_text = message.caption or ''
            file_id = message.audio.file_id
        elif message.voice:
            media_type = 'voice'
            resp_text = message.caption or ''
            file_id = message.voice.file_id

        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO custom_replies (keyword, response, media_type, file_id) VALUES (?, ?, ?, ?)", (keyword, resp_text, media_type, file_id))
        conn.commit()
        conn.close()

        state['added_count'] = state.get('added_count', 0) + 1
        bot.reply_to(
            message,
            f"✅ تم إضافة خيار رد جديد ({media_type}) للكلمة (`{keyword}`)!\n"
            f"عدد الردود المضافة لهذه الكلمة حتى الآن: `{state['added_count']}`.\n"
            f"💡 يمكنك إرسال خيار آخر، أو اكتب **تم** عند الانتهاء.",
            parse_mode="Markdown"
        )

    elif stage == 'wait_del_reply_keyword':
        del admin_states[user_id]
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM custom_replies WHERE keyword = ?", (text,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            bot.reply_to(message, f"✅ تم حذف جميع الردود المخصصة للكلمة ({text}) بنجاح.")
        else:
            bot.reply_to(message, f"❌ لم يتم العثور على أي رد مخصص للكلمة ({text}).")

    elif stage == 'wait_add_admin_id':
        del admin_states[user_id]
        if text.isdigit():
            new_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم إضافة المشرف ({new_id}) بنجاح!")
        else:
            bot.reply_to(message, "❌ يرجى إرسال آيدي (ID) صحيح كأرقام فقط.")

    elif stage == 'wait_del_admin_id':
        del admin_states[user_id]
        if text.isdigit():
            target_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM admins WHERE user_id = ?", (target_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم تنزيل المشرف ({target_id}) بنجاح!")
        else:
            bot.reply_to(message, "❌ يرجى إرسال آيدي (ID) صحيح كأرقام فقط.")

    elif stage == 'wait_fake_balance_user_id':
        if text.isdigit():
            target_user_id = int(text)
            admin_states[user_id] = {'stage': 'wait_fake_balance_amount', 'target_user_id': target_user_id}
            bot.reply_to(message, f"✅ تم تحديد الآيدي (`{target_user_id}`).\nالآن أرسل المبلغ الوهمي المراد إضافته إلى رصيده:", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إرسال آيدي (ID) صحيح كأرقام فقط.")

    elif stage == 'wait_fake_balance_amount':
        target_user_id = state.get('target_user_id')
        if text.isdigit():
            amount = int(text)
            del admin_states[user_id]
            update_balance(target_user_id, amount)
            new_bal = get_balance(target_user_id)
            bot.reply_to(message, f"✅ **تمت إضافة الرصيد الوهمي بنجاح!**\n\n👤 المستخدم: `{target_user_id}`\n💵 المبلغ المضاف: `{amount:,}` ليرة\n💰 إجمالي الرصيد الحالي: `{new_bal:,}` ليرة", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى كتابة المبلغ بأرقام صحيحة فقط.")

# ==================== تشغيل البوت ====================
if __name__ == '__main__':
    keep_alive()
    print("🤖 Bot Farfoosh is running successfully...")
    bot.infinity_polling(skip_pending=True)
