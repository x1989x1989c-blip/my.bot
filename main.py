import os
import re
import random
import sqlite3
import requests
import telebot
from telebot import types
import yt_dlp
from keep_alive import keep_alive

TOKEN = "8909949919:AAHAD8GZxZs-cHXKJHikkzjUrmktuZiG1qU"
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
    # جدول الردود يتسع لأكثر من رد لنفس الكلمة المفتاحية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            response TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)

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

# ==================== أدوات مساعدة ====================
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

# ==================== رسالة الترحيب /start و ستارت ====================
def send_welcome_message(message):
    user_id = message.from_user.id
    try:
        bot_username = bot.get_me().username
    except:
        bot_username = "Bot"

    welcome_text = (
        "👋 **أهلاً بك في بوت إدارة المجموعات والتسلية الشامل!**\n\n"
        "✨ **مميزات البوت:**\n"
        "🛡️ **حماية المجموعة:** منع الروابط، المعرفات، والرسائل المحولة تلقائياً.\n"
        "🎮 **العاب وتسلية:** قائمة ألعاب تفاعلية، XO، حزازير، رياضيات، وسرقة.\n"
        "💰 **نظام اقتصادي:** رصيد وهمي، متجر مشتريات، وسجل ممتلكات.\n"
        "🤖 **ذكاء اصطناعي:** إجابة فورية بكتابة `بدي اسالك [سؤالك]`.\n"
        "🎵 **موسيقى:** البحث والاستماع للأغاني بـ `سمعني [اسم الأغنية]`.\n"
        "💬 **ردود مخصصة متكررة وعشوائية.**\n\n"
        "👇 اضغط على الزر أدناه لإضافة البوت إلى مجموعتك وترقيته لمشرف:"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    add_group_btn = types.InlineKeyboardButton("➕ أضفني إلى المجموعة", url=f"https://t.me/{bot_username}?startgroup=true")
    markup.add(add_group_btn)

    if user_id == ADMIN_ID:
        admin_btn = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="open_admin_panel")
        markup.add(admin_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ==================== الموجه الرئيسي والحماية ====================
@bot.message_handler(func=lambda message: True)
def main_router(message):
    text = (message.text or "").strip()
    chat_type = message.chat.type

    if text.startswith("/start") or text.lower() == "ستارت":
        send_welcome_message(message)
        return

    if chat_type in ['group', 'supergroup']:
        chat_id = message.chat.id
        
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (chat_id, message.chat.title))
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

    if message.from_user.id == ADMIN_ID and ADMIN_ID in admin_states:
        handle_admin_inputs(message)
    else:
        process_bot_commands(message)

# ==================== معالجة الأوامر والردود ====================
def process_bot_commands(message):
    text = (message.text or "").strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # 1. الردود المخصصة المتعددة (اختيار عشوائي)
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT response FROM custom_replies WHERE keyword = ?", (text,))
    replies = c.fetchall()
    conn.close()
    if replies:
        selected_reply = random.choice(replies)[0]
        bot.reply_to(message, selected_reply)
        return

    # 2. التحقق من إجابات الألعاب التفاعلية النشطة
    if chat_id in active_riddles:
        correct_ans = active_riddles[chat_id]
        if text.lower() == correct_ans.lower():
            update_balance(user_id, 10)
            bot.reply_to(message, "🎉 أحسنت! إجابة صحيحة، ربحت 10 ليرات وهمية.")
            del active_riddles[chat_id]
            return

    if chat_id in active_math_games:
        correct_ans = active_math_games[chat_id]
        if text == str(correct_ans):
            update_balance(user_id, 15)
            bot.reply_to(message, "🧠 ذكي جداً! إجابة رياضية صحيحة، ربحت 15 ليرة وهمية.")
            del active_math_games[chat_id]
            return

    if chat_id in active_guess_games:
        target_num = active_guess_games[chat_id]
        if text.isdigit() and int(text) == target_num:
            update_balance(user_id, 20)
            bot.reply_to(message, f"🎯 كفو! التخمين صحيح الرقم هو {target_num}، ربحت 20 ليرة وهمية.")
            del active_guess_games[chat_id]
            return

    # 3. الذكاء الاصطناعي المباشر
    if text.startswith("بدي اسالك"):
        question = text.replace("بدي اسالك", "").strip()
        if not question:
            bot.reply_to(message, "تفضل اكتب سؤالك بعد الأمر مباشرة.\nمثال: `بدي اسالك من هو مخترع الكهرباء؟`", parse_mode="Markdown")
            return
        bot.send_chat_action(chat_id, 'typing')
        try:
            res = requests.get(f"https://api.popcat.xyz/chatbot?msg={requests.utils.quote(question)}&name=Bot", timeout=8).json()
            response_text = res.get("response", "عذراً، لم أستطع فهم السؤال.")
        except:
            response_text = "حدث خطأ أثناء التواصل مع سيرفر الذكاء الاصطناعي."
        bot.reply_to(message, response_text)
        return

    # 4. البحث في يوتيوب المطور
    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if query:
            bot.reply_to(message, f"🔍 جاري البحث عن: **{query}**...", parse_mode="Markdown")
            ydl_opts = {
                'format': 'bestaudio/best',
                'default_search': 'ytsearch1:',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if info and 'entries' in info and len(info['entries']) > 0:
                        video = info['entries'][0]
                        url = video.get('webpage_url', f"https://www.youtube.com/watch?v={video.get('id')}")
                        title = video.get('title', query)
                        bot.send_message(chat_id, f"🎵 **{title}**\n\n🔗 [اضغط للاستماع على يوتيوب]({url})", parse_mode="Markdown")
                    else:
                        bot.reply_to(message, "لم يتم العثور على نتائج.")
            except Exception:
                encoded_query = requests.utils.quote(query)
                search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
                bot.send_message(chat_id, f"🎵 **نتائج البحث عن {query}:**\n\n🔗 [فتح البحث المباشر في يوتيوب]({search_url})", parse_mode="Markdown")
        return

    # 5. ميزة السرقة عند الرد
    if text == "سرقة" or text == "سرقه":
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

        target_bal = get_balance(target_user.id)
        if target_bal <= 0:
            bot.reply_to(message, f"حرام عليك! {target_user.first_name} مفلس وما معه ولا ليرة.")
            return

        stolen_amount = max(1, int(target_bal * 0.01)) # سرقة 1% من رصيده
        update_balance(target_user.id, -stolen_amount)
        update_balance(user_id, stolen_amount)

        bot.reply_to(message, f"😈 يا ويلك من الله! سرقت من {target_user.first_name} مبلغ {stolen_amount} ليرة وهمية (1% من رصيده)!")
        return

    # 6. قائمة الألعاب الاحترافية
    if text in ["الالعاب", "الألعاب", "العاب"]:
        send_games_menu(chat_id)
        return

    # 7. الأوامر العادية والألعاب
    if text == "اكسني":
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة!\nأنشأ اللعبة: {message.from_user.first_name}\nاضغط للانضمام:", reply_markup=get_xo_keyboard(None, user_id))
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
        msg_text += "\nللشراء ارسل: `شراء [العدد] [اسم السلعة]`\nمثال: `شراء 2 علبة متة`"
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
                    bot.reply_to(message, f"✅ تم شراء {count} {item_name} بنجاح! وخصم {total_price} ليرة.")
                else:
                    bot.reply_to(message, "❌ رصيدك غير كافي لشراء هذه الكمية!")
            else:
                bot.reply_to(message, "❌ السلعة غير موجودة في المتجر.")
            conn.close()
        return

    if text == "املاكي":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0", (user_id,))
        items = c.fetchall()
        conn.close()
        if items:
            msg_text = "📦 **ممتلكاتك الشحصية:**\n\n"
            for name, qty in items:
                msg_text += f"• {name}: {qty}\n"
            msg_text += "\nللبيع ارسل: `بيع [العدد] [اسم السلعة]`"
            bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا تملك أي غرض حالياً.")
        return

    if text.startswith("بيع"):
        parts = text.split(maxsplit=2)
        if len(parts) == 3 and parts[1].isdigit():
            count = int(parts[1])
            item_name = parts[2]
            
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
            inv_row = c.fetchone()
            
            if inv_row and inv_row[0] >= count:
                c.execute("SELECT price FROM store WHERE item_name = ?", (item_name,))
                price_row = c.fetchone()
                base_price = price_row[0] if price_row else 10
                refund = int((base_price / 2) * count)
                
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (count, user_id, item_name))
                conn.commit()
                update_balance(user_id, refund)
                bot.reply_to(message, f"💵 تم بيع {count} {item_name} وإضافة {refund} ليرة إلى حسابك.")
            else:
                bot.reply_to(message, "لا تملك هذه الكمية لبيعها.")
            conn.close()
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
            bot.send_message(chat_id, "لا توجد أسئلة مضافة في القائمة بعد.")
        return

# ==================== قائمة الألعاب والتحديات ====================
def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO", callback_data="game_xo"),
        types.InlineKeyboardButton("🧩 حزرني", callback_data="game_riddle"),
        types.InlineKeyboardButton("🧮 تحدي الرياضيات", callback_data="game_math"),
        types.InlineKeyboardButton("🎯 خمن الرقم", callback_data="game_guess"),
        types.InlineKeyboardButton("🪙 طرة أم نقش", callback_data="game_coin")
    )
    bot.send_message(chat_id, "🎲 **قائمة الألعاب والتحديات التفاعلية:**\nاختر اللعبة التي تريدها للبدء والمنافسة:", reply_markup=markup, parse_mode="Markdown")

def start_riddle_game(chat_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT question, answer FROM riddles ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        active_riddles[chat_id] = row[1]
        bot.send_message(chat_id, f"🧩 **حزورة جديدة:**\n{row[0]}\n\nأرسل الإجابة مباشرة بالدردشة!")
    else:
        bot.send_message(chat_id, "لا توجد حزازير مضافة حالياً في اللوحة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_games_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    action = call.data.replace('game_', '')

    if action == "xo":
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة!\nأنشأ اللعبة: {call.from_user.first_name}\nاضغط للانضمام:", reply_markup=get_xo_keyboard(None, user_id))
    
    elif action == "riddle":
        start_riddle_game(chat_id)

    elif action == "math":
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
        ans = eval(f"{n1} {op} {n2}")
        active_math_games[chat_id] = ans
        bot.send_message(chat_id, f"🧮 **تحدي الرياضيات السريع:**\nكم الناتج: `{n1} {op} {n2}` ؟\nأول شخص يكتب الناتج الصحيح يربح 15 ليرة!", parse_mode="Markdown")

    elif action == "guess":
        target = random.randint(1, 20)
        active_guess_games[chat_id] = target
        bot.send_message(chat_id, "🎯 **تحدي خمن الرقم:**\nقمت بتخمين رقم من `1` إلى `20`!\nأول من يكتب الرقم الصحيح يربح 20 ليرة وهمية.", parse_mode="Markdown")

    elif action == "coin":
        res = random.choice(["طرة 🪙", "نقش 📜"])
        bot.answer_callback_query(call.id, f"نتيجة رمي العملة: {res}", show_alert=True)

# ==================== لعبة XO ====================
def get_xo_keyboard(game_data=None, host_id=None):
    markup = types.InlineKeyboardMarkup()
    if not game_data:
        markup.add(types.InlineKeyboardButton("بدء اللعب 🎮", callback_data=f"xo_start_{host_id}"))
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
            bot.answer_callback_query(call.id, "انتظر انضمام منافس آخر!", show_alert=True)
            return
        
        xo_games[msg_id] = {
            'player1': host_id,
            'player2': user_id,
            'turn': host_id,
            'board': [" "] * 9,
            'symbols': {host_id: "❌", user_id: "⭕"}
        }
        bot.edit_message_text("بدأت اللعبة! دور اللاعب الأول ❌", chat_id, msg_id, reply_markup=get_xo_keyboard(xo_games[msg_id]))
        return

    if call.data.startswith("xo_move_"):
        if msg_id not in xo_games:
            bot.answer_callback_query(call.id, "هذه اللعبة انتهت.")
            return
        
        game = xo_games[msg_id]
        if user_id != game['turn']:
            bot.answer_callback_query(call.id, "ليس دورك الآن!", show_alert=True)
            return

        idx = int(call.data.split("_")[2])
        if game['board'][idx] != " ":
            bot.answer_callback_query(call.id, "هذا المربع محجوز!", show_alert=True)
            return

        game['board'][idx] = game['symbols'][user_id]
        
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        winner = None
        for a, b, c in wins:
            if game['board'][a] == game['board'][b] == game['board'][c] != " ":
                winner = user_id
                break

        if winner:
            bot.edit_message_text(f"🎉 الفائز هو {call.from_user.first_name}!", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            del xo_games[msg_id]
        elif " " not in game['board']:
            bot.edit_message_text("🤝 تعادل! انتهت اللعبة.", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            del xo_games[msg_id]
        else:
            game['turn'] = game['player2'] if user_id == game['player1'] else game['player1']
            next_sym = game['symbols'][game['turn']]
            bot.edit_message_text(f"دور اللاعب {next_sym}", chat_id, msg_id, reply_markup=get_xo_keyboard(game))

# ==================== لوحة الإدارة المتكاملة ====================
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("إضافة حزورة ➕", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("حذف حزورة ❌", callback_data="admin_del_riddle"),
        types.InlineKeyboardButton("إضافة سؤال ➕", callback_data="admin_add_q"),
        types.InlineKeyboardButton("حذف سؤال ❌", callback_data="admin_del_q"),
        types.InlineKeyboardButton("إضافة رد ➕", callback_data="admin_add_rep"),
        types.InlineKeyboardButton("حذف رد ❌", callback_data="admin_del_rep"),
        types.InlineKeyboardButton("عرض الردود 👁️", callback_data="admin_view_reps"),
        types.InlineKeyboardButton("إضافة صنف ➕", callback_data="admin_add_store"),
        types.InlineKeyboardButton("حذف صنف ❌", callback_data="admin_del_store"),
        types.InlineKeyboardButton("سجل الكروبات 📋", callback_data="admin_list_groups")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم الإدارية المبرمجة:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel" or call.data.startswith('admin_'))
def handle_admin_actions(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "عذراً، هذا الزر مخصص لمدير البوت فقط!", show_alert=True)
        return
    
    chat_id = call.message.chat.id

    if call.data == "open_admin_panel":
        show_admin_panel(chat_id)
        return

    action = call.data.replace('admin_', '')

    if action == "add_riddle":
        admin_states[ADMIN_ID] = "wait_riddle_q"
        bot.send_message(chat_id, "أرسل نص الحزورة الآن:")
    elif action == "del_riddle":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question FROM riddles")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "📋 **الحزازير المتوفرة:**\n\n"
            for item in items:
                msg += f"ID: `{item[0]}` - {item[1]}\n"
            msg += "\nأرسل **رقم (ID)** الحزورة المراد حذفها:"
            admin_states[ADMIN_ID] = "wait_del_riddle_id"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد حزازير لحذفها.")

    elif action == "add_q":
        admin_states[ADMIN_ID] = "wait_q_text"
        bot.send_message(chat_id, "أرسل السؤال الجديد:")
    elif action == "del_q":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question FROM questions")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "📋 **الأسئلة المتوفرة:**\n\n"
            for item in items:
                msg += f"ID: `{item[0]}` - {item[1]}\n"
            msg += "\nأرسل **رقم (ID)** السؤال المراد حذفه:"
            admin_states[ADMIN_ID] = "wait_del_q_id"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد أسئلة لحذفها.")

    elif action == "add_rep":
        admin_states[ADMIN_ID] = "wait_rep_key"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد:")
    elif action == "del_rep":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, keyword, response FROM custom_replies")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "📋 **الردود المتوفرة:**\n\n"
            for item in items:
                msg += f"ID: `{item[0]}` | الكلمة: `{item[1]}` 👈 الرد: {item[2]}\n"
            msg += "\nأرسل **رقم (ID)** الرد المراد حذفه:"
            admin_states[ADMIN_ID] = "wait_del_rep_id"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد ردود مضافة.")

    elif action == "view_reps":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, keyword, response FROM custom_replies")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "👁️ **قائمة الكلمات والردود المخزنة:**\n\n"
            for item in items:
                msg += f"• ID: `{item[0]}` | الكلمة: `{item[1]}` 👈 الرد: {item[2]}\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد ردود مضافة بعد.")

    elif action == "add_store":
        admin_states[ADMIN_ID] = "wait_store_name"
        bot.send_message(chat_id, "أرسل اسم الصنف الجديد:")
    elif action == "del_store":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        if items:
            msg = "📋 **أصناف المتجر:**\n\n"
            for item in items:
                msg += f"- `{item[0]}` (السعر: {item[1]})\n"
            msg += "\nأرسل **اسم الصنف** المراد حذفه:"
            admin_states[ADMIN_ID] = "wait_del_store_name"
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "المتجر فارغ حالياً.")

    elif action == "list_groups":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT title FROM groups")
        groups = c.fetchall()
        conn.close()
        if groups:
            text = "📋 **المجموعات المضافة:**\n\n" + "\n".join([f"- {g[0]}" for g in groups])
        else:
            text = "لا توجد مجموعات مسجلة بعد."
        bot.send_message(chat_id, text, parse_mode="Markdown")

def handle_admin_inputs(message):
    state = admin_states[ADMIN_ID]
    text = message.text.strip()
    chat_id = message.chat.id

    if state == "wait_riddle_q":
        admin_states['temp_riddle_q'] = text
        admin_states[ADMIN_ID] = "wait_riddle_a"
        bot.send_message(chat_id, "أرسل إجابة الحزورة:")
    elif state == "wait_riddle_a":
        q = admin_states.pop('temp_riddle_q')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q, text))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(chat_id, "✅ تمت إضافة الحزورة بنجاح!")

    elif state == "wait_del_riddle_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            conn.execute("DELETE FROM riddles WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "🗑️ تم حذف الحزورة بنجاح!")
        else:
            bot.send_message(chat_id, "يرجى إرسال رقم صحيح.")
        del admin_states[ADMIN_ID]

    elif state == "wait_q_text":
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO questions (question) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(chat_id, "✅ تمت إضافة السؤال بنجاح!")

    elif state == "wait_del_q_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            conn.execute("DELETE FROM questions WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "🗑️ تم حذف السؤال بنجاح!")
        else:
            bot.send_message(chat_id, "يرجى إرسال رقم صحيح.")
        del admin_states[ADMIN_ID]

    elif state == "wait_rep_key":
        admin_states['temp_rep_key'] = text
        admin_states[ADMIN_ID] = "wait_rep_val"
        bot.send_message(chat_id, f"أرسل نص الرد للكلمة `{text}` (يمكنك إضافة ردود إضافية لنفس الكلمة بنفس الطريقة):", parse_mode="Markdown")
    elif state == "wait_rep_val":
        k = admin_states.pop('temp_rep_key')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO custom_replies (keyword, response) VALUES (?, ?)", (k, text))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(chat_id, "✅ تمت إضافة الرد بنجاح!")

    elif state == "wait_del_rep_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            conn.execute("DELETE FROM custom_replies WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "🗑️ تم حذف الرد المحدد بنجاح!")
        else:
            bot.send_message(chat_id, "يرجى إرسال رقم ID صحيح.")
        del admin_states[ADMIN_ID]

    elif state == "wait_store_name":
        admin_states['temp_store_name'] = text
        admin_states[ADMIN_ID] = "wait_store_price"
        bot.send_message(chat_id, "أرسل سعر الصنف:")
    elif state == "wait_store_price":
        name = admin_states.pop('temp_store_name')
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            conn.execute("INSERT OR REPLACE INTO store VALUES (?, ?)", (name, int(text)))
            conn.commit()
            conn.close()
            bot.send_message(chat_id, "✅ تمت إضافة الصنف للمتجر بنجاح!")
        else:
            bot.send_message(chat_id, "السعر يجب أن يكون رقماً!")
        del admin_states[ADMIN_ID]

    elif state == "wait_del_store_name":
        conn = sqlite3.connect("bot_data.db")
        conn.execute("DELETE FROM store WHERE item_name = ?", (text,))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(chat_id, "🗑️ تم حذف الصنف من المتجر!")

# تشغيل البوت والسيرفر
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
