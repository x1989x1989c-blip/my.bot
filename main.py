import os
import re
import time
import random
import sqlite3
import requests
import telebot
from telebot import types
import yt_dlp
from keep_alive import keep_alive

# ==================== الإعدادات الأساسية ====================
TOKEN = "8880921736:AAFOlFgyuR9QZ1Lz62y2iqMxsdgyCfFIVIM"
ADMIN_ID = 8577656131

bot = telebot.TeleBot(TOKEN)

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
        CREATE TABLE IF NOT EXISTS invest_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_invest INTEGER
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

    try:
        cursor.execute("ALTER TABLE custom_replies ADD COLUMN media_type TEXT DEFAULT 'text'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE custom_replies ADD COLUMN file_id TEXT")
    except:
        pass

    cursor.execute("INSERT OR IGNORE INTO store VALUES ('علبة متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كيلو سكر', 100)")

    cursor.execute("SELECT COUNT(*) FROM crime_stories")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO crime_stories (story, killer, suspects) 
            VALUES (?, ?, ?)
        """, (
            "في ليلة ممطرة، وُجد رجل الأعمال 'سليم' مقتولاً في مكتبه. المحاسب (فادي) يدعي أنه كان يراجع الأوراق، السكرتيرة (مريم) تقول أنها كانت تعد القهوة، والحارس (سامر) يقول أنه كان يقف عند الباب وشاهد شخصاً يرتدي معطفاً خردلياً.",
            "فادي",
            "فادي، مريم، سامر"
        ))
        cursor.execute("""
            INSERT INTO crime_stories (story, killer, suspects) 
            VALUES (?, ?, ?)
        """, (
            "اختفت قلادة الماسية من الخزنة. الخادم (رامي) يقول أنه كان ينظف المطبخ، والطباخ (شادي) يقول أنه كان يقطع الخضار، والسائق (ماهر) يدعي أنه كان يغسل السيارة تحت المطر.",
            "ماهر",
            "رامي، شادي، ماهر"
        ))

    conn.commit()
    conn.close()

init_db()

admin_states = {}
active_riddles = {}
active_math_games = {}
active_guess_games = {}
active_crime_games = {}
xo_games = {}

# ==================== أدوات مساعدة ونظام السجن ====================
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
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text)
    text = re.sub(r'(📌\s*المصادر:?|🔗\s*المصدر:?|المصدر:|المصادر:)', '', text)
    return text.strip()

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

# ==================== محرك البحث والذكاء الاصطناعي (المحدث والسريع جداً) ====================
def fetch_ai_answer(question):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

    sys_prompt = "أنت مساعد ذكي واسمك فرفوش. أجب عن سؤال المستخدم باللغة العربية بشكل دقيق ومباشر ومنطقي. يمنع منعاً باتاً ذكر أي روابط أو مواقع أو الإشارة إلى المصادر. إجابتك يجب أن تكون المضمون المباشر فقط."

    # 1. المحاولة الأولى: Pollinations عبر POST (الأسرع والأكثر استقراراً)
    try:
        payload = {
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question}
            ],
            "model": "openai"
        }
        res = requests.post("https://text.pollinations.ai/", json=payload, headers=headers, timeout=8)
        if res.status_code == 200 and res.text:
            ans = clean_urls_and_sources(res.text)
            if ans and len(ans) > 3 and not any(bad in ans.lower() for bad in ["timed out", "error", "504", "403", "html", "cloudflare", "bad gateway"]):
                return ans
    except Exception:
        pass

    # 2. المحاولة الثانية: Pollinations عبر نماذج متعددة (Mistral / SearchGPT)
    for model in ["mistral", "searchgpt"]:
        try:
            url = f"https://text.pollinations.ai/{requests.utils.quote(question)}?model={model}&system={requests.utils.quote(sys_prompt)}"
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200 and res.text:
                ans = clean_urls_and_sources(res.text)
                if ans and len(ans) > 3 and not any(bad in ans.lower() for bad in ["timed out", "error", "504", "403", "html", "cloudflare", "bad gateway"]):
                    return ans
        except Exception:
            pass

    # 3. المحاولة الثالثة: البحث في ويكيبيديا (بحث العناوين ثم جلب الملخص)
    try:
        search_url = f"https://ar.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(question)}&utf8=&format=json"
        s_res = requests.get(search_url, headers=headers, timeout=5)
        if s_res.status_code == 200:
            s_data = s_res.json()
            search_results = s_data.get("query", {}).get("search", [])
            if search_results:
                top_title = search_results[0]["title"]
                summary_url = f"https://ar.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(top_title)}"
                sum_res = requests.get(summary_url, headers=headers, timeout=5)
                if sum_res.status_code == 200:
                    sum_data = sum_res.json()
                    extract = sum_data.get("extract")
                    if extract:
                        return clean_urls_and_sources(extract)
    except Exception:
        pass

    # 4. المحاولة الرابعة: DuckDuckGo Instant Answer API
    try:
        ddg_api = f"https://api.duckduckgo.com/?q={requests.utils.quote(question)}&format=json&no_html=1&skip_disambig=1"
        res = requests.get(ddg_api, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            abstract = data.get("AbstractText")
            if abstract:
                return clean_urls_and_sources(abstract)
    except Exception:
        pass

    # 5. المحاولة الخامسة: جلب نتائج DuckDuckGo HTML المباشرة
    try:
        ddg_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(question)}"
        res = requests.get(ddg_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, 'html.parser')
            results = soup.find_all('a', class_='result__snippet')
            snippets = []
            for r in results[:2]:
                snip = clean_urls_and_sources(r.get_text().strip())
                if snip:
                    snippets.append(snip)
            if snippets:
                return "\n\n".join(snippets)
    except Exception:
        pass

    return "عذراً، تعذر الوصول إلى الإجابة حالياً. يرجى إعادة المحاولة لاحقاً."

# ==================== خدمة تحميل الأغاني ====================
def download_and_send_audio(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, f"🔍 جاري البحث وتحميل الأغنية: **{query}**...", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file_prefix = f"downloads/{int(time.time())}_{random.randint(1000,9999)}"
    output_template = f"{file_prefix}.%(ext)s"

    ydl_opts_base = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'cachedir': False,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'web', 'ios'],
                'player_skip': ['webpage', 'configs']
            }
        }
    }

    search_sources = [
        f"ytsearch1:{query}",
        f"scsearch1:{query}"
    ]

    for source in search_sources:
        try:
            opts = ydl_opts_base.copy()
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(source, download=True)
                if info:
                    if 'entries' in info and len(info['entries']) > 0:
                        video = info['entries'][0]
                    else:
                        video = info
                    
                    title = video.get('title', query)
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
                        bot.delete_message(chat_id, status_msg.message_id)
                        try:
                            os.remove(downloaded_file)
                        except:
                            pass
                        return
        except Exception as e:
            print(f"Download error on source {source}: {e}")
            continue

    bot.edit_message_text("❌ متعذر تحميل الأغنية حالياً، يرجى إعادة المحاولة لاحقاً.", chat_id, status_msg.message_id)
    for ext in ['m4a', 'mp3', 'webm', 'opus', 'mp4']:
        p = f"{file_prefix}.{ext}"
        if os.path.exists(p):
            try:
                os.remove(p)
            except:
                pass

# ==================== الترحيب عند إضافة البوت لمجموعة ====================
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

# ==================== الترحيب الخاص بـ /start ====================
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
        "🎮 **ألعاب متطورة:** XO، رياضيات، خمن الرقم، القاتل 🔪، وعجلة الحظ 🎡.\n"
        "💸 **اقتصاد كامل:** قروض، سجن، سرقة (كل 15 دقيقة)، واستثمار مخاطرة كل 15 دقيقة.\n"
        "🤖 **ذكاء اصطناعي:** اكتب `بدي اسالك [سؤالك]` للإجابة الدقيقة.\n"
        "🎵 **تحميل أغاني:** اكتب `سمعني [اسم الأغنية]` لتنزل فوراً صوتية."
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    add_group_btn = types.InlineKeyboardButton("➕ أضفني إلى المجموعة", url=f"https://t.me/{bot_username}?startgroup=true")
    markup.add(add_group_btn)

    if is_admin(user_id):
        admin_btn = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="open_admin_panel")
        markup.add(admin_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ==================== الموجه الرئيسي والحماية والإشراف ====================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video'])
def main_router(message):
    text = (message.text or message.caption or "").strip()
    chat_type = message.chat.type
    user_id = message.from_user.id
    chat_id = message.chat.id

    if text.startswith("/start") or text.lower() == "ستارت":
        send_welcome_message(message)
        return

    # 1. نظام الحماية والأوامر الإدارية في المجموعات
    if chat_type in ['group', 'supergroup']:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (chat_id, message.chat.title or "مجموعة بدون عنوان"))
        conn.commit()
        conn.close()

        sender_is_admin = is_chat_admin(chat_id, user_id)

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

        if is_bot_admin(chat_id) and not sender_is_admin:
            if message.forward_date or message.forward_from or message.forward_from_chat:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"يعني مافيك تنسخها نسخ", reply_to_message_id=message.message_id)
                except:
                    pass
                return

            has_username = bool(re.search(r'@[a-zA-Z0-9_]+', text))
            if has_username:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, "اسال صاحب لكروب اذا بيسمحلك ياطيب")
                except:
                    pass
                return

            has_link = bool(re.search(r'(https?://\S+|t\.me/\S+|\b\w+\.(com|net|org|site|online)\b)', text))
            if has_link:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, "كفاك روابط يا بني")
                except:
                    pass
                return

    # 2. فحص السجن
    jailed, debt = is_user_jailed(user_id)
    if jailed and text not in ["دفع ديني", "دفع دينو"] and not (message.reply_to_message and "دفع دينو" in text):
        bot.reply_to(message, "انت مسجون ياحباب دفاع دينك قبل يافقير")
        return

    # 3. معالجة إدخالات الأدمن أو الأوامر العامة
    if is_admin(user_id) and user_id in admin_states:
        handle_admin_inputs(message)
    else:
        process_bot_commands(message)

# ==================== معالجة الأوامر والردود ====================
def process_bot_commands(message):
    text = (message.text or message.caption or "").strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1. أمر "شو انا"
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

    # 2. الردود المخصصة المتعددة والوسائط
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT response, media_type, file_id FROM custom_replies WHERE keyword = ?", (text,))
    replies = c.fetchall()
    conn.close()
    if replies:
        selected_reply = random.choice(replies)
        rep_text, media_type, file_id = selected_reply[0], selected_reply[1], selected_reply[2]
        if media_type == 'photo' and file_id:
            bot.send_photo(chat_id, file_id, caption=rep_text, reply_to_message_id=message.message_id)
        elif media_type == 'video' and file_id:
            bot.send_video(chat_id, file_id, caption=rep_text, reply_to_message_id=message.message_id)
        else:
            bot.reply_to(message, rep_text)
        return

    # 3. الإجابة على لعبة من هو القاتل
    if chat_id in active_crime_games:
        game_data = active_crime_games[chat_id]
        if text.lower() == game_data['killer'].lower():
            update_balance(user_id, 50)
            bot.reply_to(message, f"🎉 كفووو يا بطل! اكتشفت القاتل الحقيقي ({game_data['killer']}) وتم إغلاق القضية! 🕵️‍♂️\nتم إضافة **50 ليرة وهمية** لرصيدك!", parse_mode="Markdown")
            del active_crime_games[chat_id]
            return
        elif any(suspect.strip().lower() in text.lower() for suspect in game_data['suspects'].split('،')):
            responses = ["لساتك بعيد ❌", "ممكن يكون هو بس رجاع فكر 🔍"]
            bot.reply_to(message, random.choice(responses))
            return

    # 4. الإجابة على باقي الألعاب
    if chat_id in active_riddles:
        if text.lower() == active_riddles[chat_id].lower():
            update_balance(user_id, 10)
            bot.reply_to(message, "🎉 أحسنت! إجابة صحيحة، ربحت 10 ليرات وهمية.")
            del active_riddles[chat_id]
            return

    if chat_id in active_math_games:
        if text == str(active_math_games[chat_id]):
            update_balance(user_id, 15)
            bot.reply_to(message, "🧠 عبقري! إجابة رياضية صحيحة، ربحت 15 ليرة وهمية.")
            del active_math_games[chat_id]
            return

    if chat_id in active_guess_games:
        if text.isdigit() and int(text) == active_guess_games[chat_id]:
            update_balance(user_id, 20)
            bot.reply_to(message, f"🎯 كفو! التخمين صحيح الرقم هو {active_guess_games[chat_id]}، ربحت 20 ليرة وهمية.")
            del active_guess_games[chat_id]
            return

    # 5. الذكاء الاصطناعي والبحث الفوري (بدي اسالك)
    if text.startswith("بدي اسالك"):
        question = text.replace("بدي اسالك", "").strip()
        if not question:
            bot.reply_to(message, "تفضل اكتب سؤالك بعد الأمر مباشرة.\nمثال: `بدي اسالك كيف الجو اليوم`", parse_mode="Markdown")
            return
        
        thinking_msg = bot.reply_to(message, "جاري البحث والإجابة... 🔍")
        ans = fetch_ai_answer(question)
        try:
            bot.edit_message_text(ans, chat_id, thinking_msg.message_id)
        except:
            bot.reply_to(message, ans)
        return

    # 6. تحميل الصوت فوراً (سمعني)
    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الأغنية بعد الأمر.\nمثال: `سمعني اصالة`", parse_mode="Markdown")
            return
        download_and_send_audio(chat_id, query, message.message_id)
        return

    # 7. لعبة من هو القاتل
    if text in ["القاتل", "من هو القاتل", "لعبة القاتل"]:
        start_crime_game(chat_id)
        return

    # 8. نظام القرض والدين
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

    # 9. السرقة (تقييد 15 دقيقة)
    if text in ["سرقة", "سرقه"]:
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ يجب أن تقوم بالرد (Reply) على رسالة العضو الذي تريد سرقته!")
            return
        
        target_user = message.reply_to_message.from_user
        if target_user.id == user_id:
            bot.reply_to(message, "عم تسرق حالك؟ ما بتزبط!")
            return
        if target_user.is_bot:
            bot.reply_to(message, "ما فيك تسرق بوت يا حباب!")
            return

        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_steal FROM steal_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        # 15 دقيقة = 900 ثانية
        if row and (current_time - row[0]) < 900:
            remaining_mins = int((900 - (current_time - row[0])) / 60) + 1
            bot.reply_to(message, f"⏳ السرقة مقيدة! يمكنك السرقة مرة واحدة كل 15 دقيقة.\nيرجى الانتظار: `{remaining_mins}` دقيقة.", parse_mode="Markdown")
            conn.close()
            return

        target_bal = get_balance(target_user.id)
        if target_bal <= 0:
            bot.reply_to(message, f"حرام عليك! {target_user.first_name} مفلس وما معه ولا ليرة.")
            conn.close()
            return

        stolen_amount = max(1, int(target_bal * 0.05))
        update_balance(target_user.id, -stolen_amount)
        update_balance(user_id, stolen_amount)

        c.execute("INSERT INTO steal_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?", (user_id, current_time, current_time))
        conn.commit()
        conn.close()

        funny_messages = [
            f"🥷 دخلت عالساكت وسحبت من جيبة {target_user.first_name} مبلغ {stolen_amount} ليرة (5%) بدون ما يحس!",
            f"🕵️‍♂️ يادي العيب! سرقت من {target_user.first_name} {stolen_amount} ليرة ورحت اشتريت فيها متة!",
            f"😈 طيرتله {stolen_amount} ليرة من رصيده، يا عيب الشوم عليك يا حرامي!"
        ]
        bot.reply_to(message, random.choice(funny_messages))
        return

    # 10. نظام الاستثمار المقيد (كل 15 دقيقة)
    if text.startswith("استثمار"):
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_invest FROM invest_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 900: # 15 دقيقة = 900 ثانية
            remaining_mins = int((900 - (current_time - row[0])) / 60) + 1
            bot.reply_to(message, f"⏳ الاستثمار مقيد! يمكنك الاستثمار مرة واحدة كل 15 دقيقة.\nيرجى الانتظار: `{remaining_mins}` دقيقة.", parse_mode="Markdown")
            conn.close()
            return

        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            inv_amount = int(parts[1])
            bal = get_balance(user_id)
            if inv_amount <= 0:
                bot.reply_to(message, "⚠️ يجب إدخال مبلغ استثمار أكبر من 0.")
                conn.close()
                return
            if bal < inv_amount:
                bot.reply_to(message, f"❌ رصيدك لا يكفي! معك حالياً {bal} ليرة.")
                conn.close()
                return

            c.execute("INSERT INTO invest_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_invest = ?", (user_id, current_time, current_time))
            conn.commit()
            conn.close()

            is_success = random.choice([True, False])
            if is_success:
                gain_percent = random.randint(15, 80)
                profit = int(inv_amount * (gain_percent / 100))
                update_balance(user_id, profit)
                bot.reply_to(message, f"📈 **استثمار ناجح!**\nارتفعت الأسهم بنسبة `{gain_percent}%` وربحت `{profit}` ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                loss_percent = random.randint(15, 60)
                loss = int(inv_amount * (loss_percent / 100))
                update_balance(user_id, -loss)
                bot.reply_to(message, f"📉 **استثمار فاشل!**\nهبطت الأسهم بنسبة `{loss_percent}%` وخسرت `{loss}` ليرة وهمية! 💔", parse_mode="Markdown")
        else:
            conn.close()
            bot.reply_to(message, "💡 للاستثمار أرسل:\n`استثمار [المبلغ]`\nمثال: `استثمار 100`", parse_mode="Markdown")
        return

    # 11. لعبة العجلة
    if text in ["عجلة", "العجلة", "لعبة العجلة"]:
        bal = get_balance(user_id)
        if bal < 50:
            bot.reply_to(message, "❌ تكلفة تدوير العجلة هي 50 ليرة ورصيدك لا يكفي!")
            return

        update_balance(user_id, -50)
        prizes = [0, 20, 50, 100, 200, 500, 1000]
        weights = [35, 25, 15, 12, 8, 4, 1]
        won = random.choices(prizes, weights=weights)[0]

        if won > 0:
            update_balance(user_id, won)
            bot.reply_to(message, f"🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وربحت **{won}** ليرة وهمية! 🎉", parse_mode="Markdown")
        else:
            bot.reply_to(message, "🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وخسرت 0 ليرة! حظاً أفضل المرة القادمة 💔", parse_mode="Markdown")
        return

    # 12. باقي الألعاب المباشرة
    if text in ["اكسني", "لعبة اكس اوه"]:
        bot.send_message(chat_id, f"🎮 **لعبة XO جديدة!**\nالمنافس الأول: {message.from_user.first_name}\nاضغط للانضمام والمنافسة:", reply_markup=get_xo_keyboard(None, user_id, message.from_user.first_name))
        return

    if text in ["رياضيات", "لعبة رياضيات"]:
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
        ans = eval(f"{n1} {op} {n2}")
        active_math_games[chat_id] = ans
        bot.send_message(chat_id, f"🧮 **تحدي الرياضيات السريع:**\nكم الناتج: `{n1} {op} {n2}` ؟\nأول شخص يكتب الناتج يربح 15 ليرة!", parse_mode="Markdown")
        return

    if text in ["خمن رقم", "لعبة خمن رقم"]:
        target = random.randint(1, 20)
        active_guess_games[chat_id] = target
        bot.send_message(chat_id, "🎯 **تحدي خمن الرقم:**\nخمنت رقم من `1` إلى `20`!\nأول شخص يكتب الرقم الصحيح يربح 20 ليرة.", parse_mode="Markdown")
        return

    # 13. القوائم ومتجر الممتلكات
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

    if text == "المتجر":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        msg_text = "🛍 **قائمة المشتريات المتوفرة:**\n\n"
        for name, price in items:
            msg_text += f"• {name} 👈 {price} ليرة\n"
        msg_text += "\nللشراء ارسل: `شراء [العدد] [اسم السلعة]`"
        bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        return

    if text.startswith("شراء"):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1].isdigit():
            count = int(parts[1])
            item_name = parts[2]
            
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT price FROM store WHERE item_name = ?", (item_name,))
            price_row = c.fetchone()
            
            if price_row:
                total_price = price_row[0] * count
                bal = get_balance(user_id)
                if bal >= total_price:
                    update_balance(user_id, -total_price)
                    c.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?", (user_id, item_name, count, count))
                    conn.commit()
                    bot.reply_to(message, f"✅ تم شراء {count} {item_name} بنجاح!")
                else:
                    bot.reply_to(message, "❌ رصيدك غير كافي!")
            else:
                bot.reply_to(message, "❌ هذا الصنف غير موجود بالمتجر!")
            conn.close()
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

# ==================== إدارة الألعاب والـ XO والجرائم ====================
def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO", callback_data="game_xo"),
        types.InlineKeyboardButton("🧩 حزرني", callback_data="game_riddle"),
        types.InlineKeyboardButton("🔪 القاتل", callback_data="game_crime"),
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
        bot.send_message(chat_id, f"🧩 **حزورة جديدة:**\n{row[0]}\n\nأرسل الإجابة بالدردشة!")
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
        msg = f"🔪 **لعبة من هو القاتل:**\n\n📜 {row[1]}\n\n👥 **المشتبه بهم:** {row[3]}\n\n💡 ارسل اسم القاتل لحل القضية وربح 50 ليرة وهمية!"
        bot.send_message(chat_id, msg)
    else:
        bot.send_message(chat_id, "لا توجد قضايا مضافة بعد.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_games_callbacks(call):
    chat_id = call.message.chat.id
    action = call.data.replace('game_', '')
    if action == "xo":
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة!\nأنشأ اللعبة: {call.from_user.first_name}", reply_markup=get_xo_keyboard(None, call.from_user.id, call.from_user.first_name))
    elif action == "riddle":
        start_riddle_game(chat_id)
    elif action == "crime":
        start_crime_game(chat_id)
    elif action == "math":
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        active_math_games[chat_id] = n1 + n2
        bot.send_message(chat_id, f"🧮 كم الناتج: `{n1} + {n2}` ؟", parse_mode="Markdown")
    elif action == "guess":
        active_guess_games[chat_id] = random.randint(1, 20)
        bot.send_message(chat_id, "🎯 خمن رقم من `1` إلى `20`!", parse_mode="Markdown")
    elif action == "wheel":
        bot.send_message(chat_id, "🎡 للعب العجلة أرسل كلمة `عجلة` بالدردشة (التكلفة 50 ليرة).")

def get_xo_keyboard(game_data=None, host_id=None, host_name=""):
    markup = types.InlineKeyboardMarkup()
    if not game_data:
        markup.add(types.InlineKeyboardButton(f"الانضمام للعب مع {host_name} 🎮", callback_data=f"xo_start_{host_id}"))
        return markup
    
    board = game_data['board']
    for i in range(3):
        row_btns = []
        for j in range(3):
            idx = i * 3 + j
            val = board[idx] if board[idx] != " " else " "
            row_btns.append(types.InlineKeyboardButton(val, callback_data=f"xo_move_{idx}"))
        markup.add(*row_btns)
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('xo_'))
def handle_xo_callbacks(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    user_id = call.from_user.id

    if call.data.startswith("xo_start_"):
        host_id = int(call.data.split("_")[2])
        if user_id == host_id:
            bot.answer_callback_query(call.id, "انتظر انضمام لاعب آخر!", show_alert=True)
            return
        
        p1_name = bot.get_chat_member(chat_id, host_id).user.first_name
        p2_name = call.from_user.first_name

        xo_games[msg_id] = {
            'player1': host_id,
            'player2': user_id,
            'p1_name': p1_name,
            'p2_name': p2_name,
            'turn': host_id,
            'board': [" "] * 9,
            'symbols': {host_id: "❌", user_id: "⭕"}
        }
        bot.edit_message_text(f"🎮 بدأت اللعبة بين:\n❌ {p1_name}\n⭕ {p2_name}\n\nالدور الحالي: {p1_name} (❌)", chat_id, msg_id, reply_markup=get_xo_keyboard(xo_games[msg_id]))
        return

    if call.data.startswith("xo_move_"):
        if msg_id not in xo_games:
            bot.answer_callback_query(call.id, "انتهت اللعبة.")
            return
        
        game = xo_games[msg_id]
        if user_id != game['turn']:
            bot.answer_callback_query(call.id, "ليس دورك الآن!", show_alert=True)
            return

        idx = int(call.data.split("_")[2])
        if game['board'][idx] != " ":
            bot.answer_callback_query(call.id, "المربع محجوز!", show_alert=True)
            return

        game['board'][idx] = game['symbols'][user_id]
        
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        winner = None
        for a, b, c in wins:
            if game['board'][a] == game['board'][b] == game['board'][c] != " ":
                winner = user_id
                break

        if winner:
            bot.edit_message_text(f"🎉 الفائز باللعبة هو {call.from_user.first_name}!", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            update_balance(user_id, 30)
            del xo_games[msg_id]
        elif " " not in game['board']:
            bot.edit_message_text("🤝 تعادل بين الطرفين!", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            del xo_games[msg_id]
        else:
            game['turn'] = game['player2'] if user_id == game['player1'] else game['player1']
            next_name = game['p2_name'] if game['turn'] == game['player2'] else game['p1_name']
            next_sym = game['symbols'][game['turn']]
            bot.edit_message_text(f"🎮 المباراة مستمرة بين:\n❌ {game['p1_name']}\n⭕ {game['p2_name']}\n\nالدور الحالي: {next_name} ({next_sym})", chat_id, msg_id, reply_markup=get_xo_keyboard(game))

# ==================== لوحة الإدارة السريعة والسجلات ====================
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("إضافة ادمن ➕", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("عرض الأدمنية 👥", callback_data="admin_list_admins"),
        types.InlineKeyboardButton("إضافة صنف جديد 🛒", callback_data="admin_add_store_item"),
        types.InlineKeyboardButton("إضافة قصة جريمة 🔪", callback_data="admin_add_crime"),
        types.InlineKeyboardButton("إضافة حزورة ➕", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("إضافة أسئلة ➕", callback_data="admin_add_q"),
        types.InlineKeyboardButton("إضافة ردود ➕", callback_data="admin_add_rep"),
        types.InlineKeyboardButton("سجل الأصناف 🛒", callback_data="admin_log_store"),
        types.InlineKeyboardButton("سجل الأسئلة ❓", callback_data="admin_log_questions"),
        types.InlineKeyboardButton("سجل الحزازير 🧩", callback_data="admin_log_riddles"),
        types.InlineKeyboardButton("سجل الردود 💬", callback_data="admin_log_replies"),
        types.InlineKeyboardButton("سجل إجابات الجرائم 🎯", callback_data="admin_log_crimes"),
        types.InlineKeyboardButton("🚪 مغادرة مجموعة", callback_data="admin_leave_grp"),
        types.InlineKeyboardButton("✉️ رسالة خاصة لجروب", callback_data="admin_send_grp_msg")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم والإدارة الشاملة:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_admin(message.from_user.id):
        show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel" or call.data.startswith('admin_') or call.data.startswith('grp_'))
def handle_admin_actions(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "اللوحة مخصصة للآدمن فقط!", show_alert=True)
        return
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "open_admin_panel":
        show_admin_panel(chat_id)
        return

    if call.data == "admin_log_store":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = [f"السلعة: `{row[0]}` | السعر: `{row[1]}` ليرة" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🛒 **سجل أصناف المتجر:**", items)
        return

    if call.data == "admin_log_questions":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question FROM questions")
        items = [f"ID `{row[0]}`: {row[1]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "❓ **سجل الأسئلة:**", items)
        return

    if call.data == "admin_log_riddles":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question, answer FROM riddles")
        items = [f"ID `{row[0]}`: {row[1]} 👈 الإجابة: `{row[2]}`" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🧩 **سجل الحزازير:**", items)
        return

    if call.data == "admin_log_replies":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, keyword, response, media_type FROM custom_replies")
        items = [f"ID `{row[0]}` | الكلمة: `{row[1]}` | الرد: `{row[2]}` | النوع: `{row[3]}`" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "💬 **سجل الردود المخصصة:**", items)
        return

    if call.data == "admin_log_crimes":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, killer, suspects FROM crime_stories")
        items = [f"قضية `{row[0]}` 👈 القاتل الصحيح: **{row[1]}** | المشتبه بهم: ({row[2]})" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🎯 **سجل الإجابات الصحيحة للجرائم:**", items)
        return

    if call.data == "admin_add_store_item":
        admin_states[user_id] = "wait_store_item_name"
        bot.send_message(chat_id, "أرسل اسم الصنف الجديد المراد إضافته للمتجر:")
        return

    if call.data == "admin_add_crime":
        admin_states[user_id] = "wait_crime_story"
        bot.send_message(chat_id, "أرسل نص قصة الجريمة جديدة:")
        return

    if call.data == "admin_leave_grp":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        conn.close()

        if not groups:
            bot.send_message(chat_id, "لا توجد مجموعات مسجلة حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, title in groups:
            markup.add(types.InlineKeyboardButton(f"🚪 مغادرة: {title}", callback_data=f"grp_leave_{g_id}"))
        bot.send_message(chat_id, "اختر المجموعة المراد مغادرتها:", reply_markup=markup)
        return

    if call.data.startswith("grp_leave_"):
        target_g_id = int(call.data.split("_")[2])
        try:
            bot.leave_chat(target_g_id)
            conn = sqlite3.connect("bot_data.db")
            conn.execute("DELETE FROM groups WHERE chat_id = ?", (target_g_id,))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, "تم المغادرة بنجاح!", show_alert=True)
            bot.edit_message_text("✅ تمت المغادرة وحذف المجموعة من القائمة.", chat_id, call.message.message_id)
        except Exception as e:
            bot.send_message(chat_id, f"❌ حدث خطأ أثناء المغادرة: {e}")
        return

    if call.data == "admin_send_grp_msg":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        conn.close()

        if not groups:
            bot.send_message(chat_id, "لا توجد مجموعات مسجلة.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, title in groups:
            markup.add(types.InlineKeyboardButton(f"✉️ إرسال إلى: {title}", callback_data=f"grp_send_{g_id}"))
        bot.send_message(chat_id, "اختر المجموعة التي تريد إرسال رسالة إليها:", reply_markup=markup)
        return

    if call.data.startswith("grp_send_"):
        target_g_id = int(call.data.split("_")[2])
        admin_states[user_id] = f"wait_send_msg_{target_g_id}"
        bot.send_message(chat_id, "أرسل الآن الرسالة (نص، صورة، أو فيديو) ليتم توجيهها للمجموعة مباشرة:")
        return

    action = call.data.replace('admin_', '')

    if action == "add_rep":
        admin_states[user_id] = "wait_rep_key"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد:")

    elif action == "add_q":
        admin_states[user_id] = "wait_multi_q"
        bot.send_message(chat_id, "أرسل الأسئلة الجديدة (يمكنك إرسال كل سؤال في سطر جديد):")

    elif action == "add_riddle":
        admin_states[user_id] = "wait_riddle_q"
        bot.send_message(chat_id, "أرسل نص الحزورة:")

# ==================== إدخالات الأدمن التفاعلية ====================
def handle_admin_inputs(message):
    user_id = message.from_user.id
    state = admin_states.get(user_id)
    chat_id = message.chat.id

    if state == "wait_store_item_name":
        admin_states[f"{user_id}_temp_store_name"] = message.text.strip()
        admin_states[user_id] = "wait_store_item_price"
        bot.send_message(chat_id, "أرسل سعر الصنف بالليرات الوهمية (رقم فقط):")
        return

    if state == "wait_store_item_price":
        if message.text.isdigit():
            item_name = admin_states.pop(f"{user_id}_temp_store_name")
            price = int(message.text)
            conn = sqlite3.connect("bot_data.db")
            conn.execute("INSERT OR REPLACE INTO store (item_name, price) VALUES (?, ?)", (item_name, price))
            conn.commit()
            conn.close()
            del admin_states[user_id]
            bot.send_message(chat_id, f"✅ تم إضافة الصنف `{item_name}` بسعر `{price}` ليرة بنجاح لتظهر في المتجر والممتلكات!", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ يرجى إدخال رقم صحيح للسعر.")
        return

    if state == "wait_crime_story":
        admin_states[f"{user_id}_temp_crime_story"] = message.text.strip()
        admin_states[user_id] = "wait_crime_suspects"
        bot.send_message(chat_id, "أرسل أسماء المشتبه بهم مفصولة بفواصل (مثال: فادي، مريم، سامر):")
        return

    if state == "wait_crime_suspects":
        admin_states[f"{user_id}_temp_crime_suspects"] = message.text.strip()
        admin_states[user_id] = "wait_crime_killer"
        bot.send_message(chat_id, "أرسل اسم القاتل الحقيقي من بينهم:")
        return

    if state == "wait_crime_killer":
        story = admin_states.pop(f"{user_id}_temp_crime_story")
        suspects = admin_states.pop(f"{user_id}_temp_crime_suspects")
        killer = message.text.strip()

        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (story, killer, suspects))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, f"✅ تمت إضافة قصة الجريمة وتحديد القاتل (`{killer}`) بنجاح!", parse_mode="Markdown")
        return

    if state and state.startswith("wait_send_msg_"):
        target_chat_id = int(state.replace("wait_send_msg_", ""))
        try:
            if message.photo:
                bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                bot.send_video(target_chat_id, message.video.file_id, caption=message.caption or "")
            else:
                bot.send_message(target_chat_id, message.text)
            bot.send_message(chat_id, "✅ تم إرسال الرسالة إلى المجموعة بنجاح!")
        except Exception as e:
            bot.send_message(chat_id, f"❌ فشل إرسال الرسالة: {e}")
        del admin_states[user_id]
        return

    if state == "wait_rep_key":
        admin_states[f'{user_id}_temp_key'] = message.text.strip()
        admin_states[user_id] = "wait_rep_val"
        bot.send_message(chat_id, "أرسل الرد الآن (يمكنك إرسال نص أو صورة أو فيديو):")
        return

    elif state == "wait_rep_val":
        k = admin_states.pop(f'{user_id}_temp_key')
        conn = sqlite3.connect("bot_data.db")
        
        if message.photo:
            file_id = message.photo[-1].file_id
            caption = message.caption or ""
            conn.execute("INSERT INTO custom_replies (keyword, response, media_type, file_id) VALUES (?, ?, 'photo', ?)", (k, caption, file_id))
        elif message.video:
            file_id = message.video.file_id
            caption = message.caption or ""
            conn.execute("INSERT INTO custom_replies (keyword, response, media_type, file_id) VALUES (?, ?, 'video', ?)", (k, caption, file_id))
        elif message.text:
            lines = [line.strip() for line in message.text.split('\n') if line.strip()]
            for line in lines:
                conn.execute("INSERT INTO custom_replies (keyword, response, media_type) VALUES (?, ?, 'text')", (k, line))
        
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, f"✅ تم حفظ الردود للكلمة `{k}` بنجاح!", parse_mode="Markdown")
        return

    elif state == "wait_multi_q":
        lines = [line.strip() for line in message.text.split('\n') if line.strip()]
        conn = sqlite3.connect("bot_data.db")
        for line in lines:
            conn.execute("INSERT INTO questions (question) VALUES (?)", (line,))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, f"✅ تمت إضافة {len(lines)} سؤال/أسئلة بنجاح!")
        return

    elif state == "wait_riddle_q":
        admin_states[f'{user_id}_temp_riddle'] = message.text
        admin_states[user_id] = "wait_riddle_a"
        bot.send_message(chat_id, "أرسل إجابة الحزورة:")
        return

    elif state == "wait_riddle_a":
        q = admin_states.pop(f'{user_id}_temp_riddle')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q, message.text.strip()))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, "✅ تمت إضافة الحزورة بنجاح!")
        return

# ==================== التشغيل المستمر ====================
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
