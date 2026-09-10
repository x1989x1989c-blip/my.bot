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
        CREATE TABLE IF NOT EXISTS loans (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER DEFAULT 0,
            loan_time INTEGER DEFAULT 0
        )
    """)

    # إضافات لتحديث المخطط للردود الوسائط إن لم تكن موجودة
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

    conn.commit()
    conn.close()

init_db()

admin_states = {}
active_riddles = {}
active_math_games = {}
active_guess_games = {}
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
        if (current_time - loan_time) >= 7200: # ساعتان (7200 ثانية)
            return True, amount
    return False, 0

def clean_urls(text):
    return re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text).strip()

def fetch_ai_answer(question):
    try:
        res = requests.get(f"https://api.popcat.xyz/chatbot?msg={requests.utils.quote(question)}&name=Bot", timeout=6).json()
        ans = res.get("response", "")
        if ans and "error" not in ans.lower():
            return clean_urls(ans)
    except:
        pass
    
    try:
        ddg_res = requests.get(f"https://api.duckduckgo.com/?q={requests.utils.quote(question)}&format=json&no_html=1", timeout=6).json()
        ans = ddg_res.get("AbstractText", "")
        if ans:
            return clean_urls(ans)
    except:
        pass

    return "أهلاً بك! أنا هنا للمساعدة، يمكنك إعادة طرح سؤالك بصيغة أخرى."

# ==================== الترحيب والوجهة ====================
def send_welcome_message(message):
    user_id = message.from_user.id
    try:
        bot_username = bot.get_me().username
    except:
        bot_username = "Bot"

    welcome_text = (
        "👋 **أهلاً بك في بوت إدارة المجموعات والتسلية الشامل!**\n\n"
        "✨ **المميزات المضافة:**\n"
        "🛡️ **حماية المجموعة:** منع الروابط والمعرفات والتحويل.\n"
        "🎮 **ألعاب متطورة:** XO مع الأسماء، رياضيات، خمن الرقم، وعجلة الحظ 🎡.\n"
        "💸 **استثمار وقروض:** نظام قرض واستثمار حقيقي ومخاطرة.\n"
        "🤖 **ذكاء اصطناعي:** اكتب `بدي اسالك [سؤالك]` للإجابة مباشرة.\n"
        "🎵 **تحميل موسيقى:** اكتب `سمعني [اسم الأغنية]` لتنزل فوراً MP3.\n"
        "💬 **ردود متعددة:** إمكانية إضافة ردود صور وفيديو وردود متعددة بضغطة واحدة."
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    add_group_btn = types.InlineKeyboardButton("➕ أضفني إلى المجموعة", url=f"https://t.me/{bot_username}?startgroup=true")
    markup.add(add_group_btn)

    if is_admin(user_id):
        admin_btn = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="open_admin_panel")
        markup.add(admin_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ==================== الموجه الرئيسي والحماية ====================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video'])
def main_router(message):
    text = (message.text or message.caption or "").strip()
    chat_type = message.chat.type
    user_id = message.from_user.id

    if text.startswith("/start") or text.lower() == "ستارت":
        send_welcome_message(message)
        return

    # حفظ الكروبات المتفاعلة
    if chat_type in ['group', 'supergroup']:
        chat_id = message.chat.id
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (chat_id, message.chat.title or "مجموعة بدون عنوان"))
        conn.commit()
        conn.close()

        if is_bot_admin(chat_id):
            if message.forward_date or message.forward_from or message.forward_from_chat:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, "مافيك تنسخا نسخ يعني؟")
                except:
                    pass
                return

            has_link = bool(re.search(r'(https?://\S+|t\.me/\S+|\b\w+\.(com|net|org|site|online)\b)', text))
            has_username = bool(re.search(r'@[a-zA-Z0-9_]+', text))

            if has_link or has_username:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, "بس يا ابني كفاك روابط")
                except:
                    pass
                return

    # التحقق من حالة السجن بسب الدين
    jailed, debt = is_user_jailed(user_id)
    if jailed and text not in ["دفع ديني", "دفع دينو"] and not (message.reply_to_message and "دفع دينو" in text):
        bot.reply_to(message, "انت مسجون ياحباب دفاع دينك قبل يافقير")
        return

    if is_admin(user_id) and user_id in admin_states:
        handle_admin_inputs(message)
    else:
        process_bot_commands(message)

# ==================== معالجة الأوامر والردود ====================
def process_bot_commands(message):
    text = (message.text or message.caption or "").strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1. الردود المخصصة المتعددة والوسائط (صور / فيديو / نص)
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

    # 2. الإجابة على الألعاب
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

    # 3. الذكاء الاصطناعي (بدي اسالك)
    if text.startswith("بدي اسالك"):
        question = text.replace("بدي اسالك", "").strip()
        if not question:
            bot.reply_to(message, "تفضل اكتب سؤالك بعد الأمر مباشرة.\nمثال: `بدي اسالك كم يبعد القمر؟`", parse_mode="Markdown")
            return
        bot.send_chat_action(chat_id, 'typing')
        ans = fetch_ai_answer(question)
        bot.reply_to(message, ans)
        return

    # 4. تحميل الصوت فوراً (سمعني)
    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الأغنية بعد الأمر.\nمثال: `سمعني فيروز`", parse_mode="Markdown")
            return
        download_and_send_audio(chat_id, query, message.message_id)
        return

    # 5. نظام القرض والدين
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
                bot.reply_to(message, f"✅ تم تسديد الدين بمبلغ {debt_amount} ليرة بنجاح والخرج من السجن!")
            else:
                bot.reply_to(message, f"❌ الرصيد غير كافي لتسديد الدين المحدد ({debt_amount} ليرة)!")
        else:
            bot.reply_to(message, "لا يوجد أي ديون مستحقة!")
        conn.close()
        return

    # 6. السرقة وتطوير الجمل والنسبة (5%)
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

        if row and (current_time - row[0]) < 600: # cooldown 10 دقائق
            bot.reply_to(message, "ياويلك من الله لسا هلق سرقت! انتظر شوية لتهدأ الأوضاع.")
            conn.close()
            return

        target_bal = get_balance(target_user.id)
        if target_bal <= 0:
            bot.reply_to(message, f"حرام عليك! {target_user.first_name} مفلس وما معه ولا ليرة.")
            conn.close()
            return

        stolen_amount = max(1, int(target_bal * 0.05)) # سرقة 5% من الرصيد
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

    # 7. نظام الاستثمار
    if text.startswith("استثمار"):
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            inv_amount = int(parts[1])
            bal = get_balance(user_id)
            if inv_amount <= 0:
                bot.reply_to(message, "⚠️ يجب إدخال مبلغ استثمار أكبر من 0.")
                return
            if bal < inv_amount:
                bot.reply_to(message, f"❌ رصيدك لا يكفي! معك حالياً {bal} ليرة.")
                return

            # تحديد النجاح أو الفشل عشوائياً
            is_success = random.choice([True, False])
            if is_success:
                gain_percent = random.randint(15, 70)
                profit = int(inv_amount * (gain_percent / 100))
                update_balance(user_id, profit)
                bot.reply_to(message, f"📈 **استثمار ناجح!**\nارتفعت أسهمك بنسبة `{gain_percent}%` وربحت `{profit}` ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                loss_percent = random.randint(15, 60)
                loss = int(inv_amount * (loss_percent / 100))
                update_balance(user_id, -loss)
                bot.reply_to(message, f"📉 **استثمار فاشل!**\nهبطت الأسهم بنسبة `{loss_percent}%` وخسرت `{loss}` ليرة وهمية! 💔", parse_mode="Markdown")
        else:
            bot.reply_to(message, "💡 للاستثمار أرسل:\n`استثمار [المبلغ]`\nمثال: `استثمار 100`", parse_mode="Markdown")
        return

    # 8. لعبة العجلة
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
            bot.reply_to(message, "🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وللأسف خسرت الحظيرة 0 ليرة! حظاً أفر 💔", parse_mode="Markdown")
        return

    # 9. تشغيل الألعاب بالأوامر المباشرة
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

    # 10. باقي الأوامر والالعاب والتجارة
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
            conn.close()
        return

    if text == "املاكي":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0", (user_id,))
        items = c.fetchall()
        conn.close()
        if items:
            msg_text = "📦 **ممتلكاتك الشحصية:**\n\n" + "\n".join([f"• {name}: {qty}" for name, qty in items])
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

# ==================== خدمة تحميل الأغاني من يوتيوب ====================
def download_and_send_audio(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, f"🔍 جاري البحث وتحميل الأغنية: **{query}**...", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    filename = f"downloads/{int(time.time())}_{random.randint(100,999)}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1:',
        'outtmpl': filename,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if info and 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                title = video.get('title', query)
                uploader = video.get('uploader', 'Music Bot')

                if os.path.exists(filename):
                    with open(filename, 'rb') as audio:
                        bot.send_audio(chat_id, audio, title=title, performer=uploader, reply_to_message_id=message_id)
                    bot.delete_message(chat_id, status_msg.message_id)
                    os.remove(filename)
                    return

            bot.edit_message_text("❌ لم يتم العثور على نتائج للأغنية.", chat_id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text("❌ حدث خطأ أثناء التحميل الفوري، حاول مرة أخرى.", chat_id, status_msg.message_id)

# ==================== قائمة الألعاب و XO ====================
def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO", callback_data="game_xo"),
        types.InlineKeyboardButton("🧩 حزرني", callback_data="game_riddle"),
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
        bot.send_message(chat_id, "لا توجد حزازير مضافة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_games_callbacks(call):
    chat_id = call.message.chat.id
    action = call.data.replace('game_', '')
    if action == "xo":
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة!\nأنشأ اللعبة: {call.from_user.first_name}", reply_markup=get_xo_keyboard(None, call.from_user.id, call.from_user.first_name))
    elif action == "riddle":
        start_riddle_game(chat_id)
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

# ==================== لوحة الإدارة المتطورة ====================
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("إضافة ادمن ➕", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("عرض الأدمنية 👥", callback_data="admin_list_admins"),
        types.InlineKeyboardButton("إضافة حزورة ➕", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("إضافة أسئلة ➕", callback_data="admin_add_q"),
        types.InlineKeyboardButton("إضافة ردود ➕", callback_data="admin_add_rep"),
        types.InlineKeyboardButton("عرض الردود 👁️", callback_data="admin_view_reps"),
        types.InlineKeyboardButton("🚪 مغادرة مجموعة", callback_data="admin_leave_grp"),
        types.InlineKeyboardButton("✉️ رسالة خاصة لجروب", callback_data="admin_send_grp_msg")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم الإدارية السريعة:**", reply_markup=markup, parse_mode="Markdown")

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

    # 1. مغادرة المجموعات
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

    # 2. إرسال رسالة خاصة لمجموعة
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
        bot.send_message(chat_id, "أرسل الأسئلة الجديدة (يمكنك إرسال كل سؤال في سطر جديد للدفعة الواحدة):")

    elif action == "add_riddle":
        admin_states[user_id] = "wait_riddle_q"
        bot.send_message(chat_id, "أرسل نص الحزورة:")

    elif action == "view_reps":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, keyword, response, media_type FROM custom_replies")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "👁️ **قائمة الردود المخزنة:**\n\n"
            for item in items:
                msg += f"• ID: `{item[0]}` | الكلمة: `{item[1]}` | النوع: `{item[3]}`\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد ردود مضافة.")

# ==================== معالجة إدخالات الأدمن والميديا ====================
def handle_admin_inputs(message):
    user_id = message.from_user.id
    state = admin_states.get(user_id)
    chat_id = message.chat.id

    # إرسال رسالة خاصة لجروب
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

    # إضافة ردود (صورة / فيديو / نص / ردود متعددة بأسطر)
    if state == "wait_rep_key":
        admin_states[f'{user_id}_temp_key'] = message.text.strip()
        admin_states[user_id] = "wait_rep_val"
        bot.send_message(chat_id, "أرسل الرد الآن (يمكن إرسال نص أو صورة أو فيديو، وإذا أرسلت أسطر متعددة سينزل كـ ردود عشوائية):")

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

    # إضافة أسئلة متعددة أسفل بعضها
    elif state == "wait_multi_q":
        lines = [line.strip() for line in message.text.split('\n') if line.strip()]
        conn = sqlite3.connect("bot_data.db")
        for line in lines:
            conn.execute("INSERT INTO questions (question) VALUES (?)", (line,))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, f"✅ تمت إضافة {len(lines)} سؤال/أسئلة بنجاح!")

    elif state == "wait_riddle_q":
        admin_states[f'{user_id}_temp_riddle'] = message.text
        admin_states[user_id] = "wait_riddle_a"
        bot.send_message(chat_id, "أرسل إجابة الحزورة:")

    elif state == "wait_riddle_a":
        q = admin_states.pop(f'{user_id}_temp_riddle')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q, message.text.strip()))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(chat_id, "✅ تمت إضافة الحزورة بنجاح!")

# ==================== التشغيل المستمر ====================
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
