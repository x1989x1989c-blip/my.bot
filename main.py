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
    
    # جدول المستخدمين
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    # جدول الممتلكات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            item_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, item_name)
        )
    """)
    # جدول المتجر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS store (
            item_name TEXT PRIMARY KEY,
            price INTEGER
        )
    """)
    # جدول الحزازير
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS riddles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT
        )
    """)
    # جدول أسئلة "اسألني"
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT
        )
    """)
    # جدول الردود التلقائية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_replies (
            keyword TEXT PRIMARY KEY,
            response TEXT
        )
    """)
    # جدول المجموعات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT
        )
    """)

    # إضافة عناصر المتجر الافتراضية والحزازير
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('علبة متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كيلو سكر', 100)")
    cursor.execute("INSERT OR IGNORE INTO riddles (question, answer) VALUES ('من رئيس سوريا الحالي', 'احمد شرع')")

    conn.commit()
    conn.close()

init_db()

# حالات الانتظار (ChatGPT والإدارة)
user_states = {}
admin_states = {}
active_riddles = {}
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
    c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?", (user_id, max(0, amount), amount))
    conn.commit()
    conn.close()

# ==================== الحماية والإشراف ====================
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def group_moderation_and_router(message):
    chat_id = message.chat.id
    
    # تسجيل المجموعات
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO groups VALUES (?, ?)", (chat_id, message.chat.title))
    conn.commit()
    conn.close()

    # التحقق من صلاحيات المشرف
    if not is_bot_admin(chat_id):
        return

    # 1. منع الرسائل المحولة
    if message.forward_date or message.forward_from or message.forward_from_chat:
        try:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, "مافيك تنسخا نسخ يعني؟")
        except:
            pass
        return

    text = message.text or ""

    # 2. منع الروابط والمعرفات
    has_link = bool(re.search(r'(https?://\S+|t\.me/\S+|\b\w+\.(com|net|org|site|online)\b)', text))
    has_username = bool(re.search(r'@[a-zA-Z0-9_]+', text))

    if has_link or has_username:
        try:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, "بس يا ابني كفاك روابط")
        except:
            pass
        return

    # متابعة معالجة الأوامر والردود
    process_bot_commands(message)

def process_bot_commands(message):
    text = (message.text or "").strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    # نظام الردود المخصصة
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT response FROM custom_replies WHERE keyword = ?", (text,))
    reply = c.fetchone()
    conn.close()
    if reply:
        bot.reply_to(message, reply[0])
        return

    # الرد على الحزازير النشطة
    if chat_id in active_riddles:
        correct_ans = active_riddles[chat_id]
        if text.lower() == correct_ans.lower():
            update_balance(user_id, 10)
            bot.reply_to(message, "احسنت ربحت عشر ليرات وهمية")
            del active_riddles[chat_id]
            return

    # ChatGPT state
    if user_states.get(user_id) == 'waiting_ai_question':
        user_states[user_id] = None
        bot.send_chat_action(chat_id, 'typing')
        try:
            res = requests.get(f"https://api.popcat.xyz/chatbot?msg={requests.utils.quote(text)}&name=Bot").json()
            response_text = res.get("response", "عذراً، لم أستطع فهم السؤال.")
        except:
            response_text = "حدث خطأ أثناء التواصل مع سيرفر الذكاء الاصطناعي."
        bot.reply_to(message, response_text)
        return

    # الأوامر الأساسية
    if text == "اكسني":
        msg = bot.send_message(chat_id, f"لعبة XO جديدة!\nأنشأ اللعبة: {message.from_user.first_name}\nاضغط على الزر للانضمام والبدء.", reply_markup=get_xo_keyboard(None, user_id))
        return

    if text == "بدي اسالك":
        user_states[user_id] = 'waiting_ai_question'
        bot.reply_to(message, "تفضل اسال")
        return

    if text == "حزرني":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question, answer FROM riddles ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            active_riddles[chat_id] = row[1]
            bot.send_message(chat_id, f"الحزورة:\n{row[0]}")
        else:
            bot.send_message(chat_id, "لا يوجد حزازير متوفرة حالياً.")
        return

    if text == "مصرياتي":
        bal = get_balance(user_id)
        bot.reply_to(message, f"معك {bal} ليرة وهمية.")
        return

    if text == "المتجر":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        msg_text = "🛍 **قائمة المشتريات:**\n\n"
        for name, price in items:
            msg_text += f"- {name}: سعره {price} ليرة\n"
        msg_text += "\nللشراء ارسل: شراء [العدد] [اسم السلعة]\nمثال: شراء 5 علبة متة"
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
                    bot.reply_to(message, f"تم شراء {count} {item_name} بنجاح! وخصم {total_price} ليرة.")
                else:
                    bot.reply_to(message, "رصيدك غير كافي لشراء هذه الكمية!")
            else:
                bot.reply_to(message, "السلعة غير موجودة في المتجر.")
            conn.close()
        return

    if text == "املاكي":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0", (user_id,))
        items = c.fetchall()
        conn.close()
        if items:
            msg_text = "📦 **ممتلكاتك:**\n\n"
            for name, qty in items:
                msg_text += f"- {name}: {qty}\n"
            msg_text += "\nللبيع ارسل: بيع [العدد] [اسم السلعة]"
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
                bot.reply_to(message, f"تم بيع {count} {item_name} وإضافة {refund} ليرة إلى حسابك.")
            else:
                bot.reply_to(message, "لا تملك هذه الكمية لبيعها.")
            conn.close()
        return

    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if query:
            bot.reply_to(message, f"جاري البحث عن: {query}...")
            ydl_opts = {'format': 'bestaudio/best', 'default_search': 'ytsearch1:', 'noplaylist': True, 'quiet': True}
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info and len(info['entries']) > 0:
                        video = info['entries'][0]
                        url = video['webpage_url']
                        title = video['title']
                        bot.send_message(chat_id, f"🎵 **{title}**\n\n🔗 [رابط الاستماع على يوتيوب]({url})", parse_mode="Markdown")
                    else:
                        bot.reply_to(message, "لم يتم العثور على نتائح.")
            except Exception as e:
                bot.reply_to(message, "حدث خطأ أثناء البحث عن الأغنية.")
        return

    if text == "اسالني":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question FROM questions ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            bot.send_message(chat_id, f"سؤال لك:\n{row[0]}")
        else:
            bot.send_message(chat_id, "لا توجد أسئلة مضافة بعد.")
        return

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
        
        # فحص الفوز
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        winner = None
        for a, b, c in wins:
            if game['board'][a] == game['board'][b] == game['board'][c] != " ":
                winner = user_id
                break

        if winner:
            bot.edit_message_text(f"الفائز هو {call.from_user.first_name} 🎉", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            del xo_games[msg_id]
        elif " " not in game['board']:
            bot.edit_message_text("تعادل! انتهت اللعبة.", chat_id, msg_id, reply_markup=get_xo_keyboard(game))
            del xo_games[msg_id]
        else:
            game['turn'] = game['player2'] if user_id == game['player1'] else game['player1']
            next_sym = game['symbols'][game['turn']]
            bot.edit_message_text(f"دور اللاعب {next_sym}", chat_id, msg_id, reply_markup=get_xo_keyboard(game))

# ==================== لوحة الإدارة ====================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("إضافة حزورة ➕", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("حذف حزورة ❌", callback_data="admin_del_riddle"),
        types.InlineKeyboardButton("إضافة سؤال ➕", callback_data="admin_add_q"),
        types.InlineKeyboardButton("حذف سؤال ❌", callback_data="admin_del_q"),
        types.InlineKeyboardButton("إضافة رد ➕", callback_data="admin_add_rep"),
        types.InlineKeyboardButton("حذف رد ❌", callback_data="admin_del_rep"),
        types.InlineKeyboardButton("إضافة صنف ➕", callback_data="admin_add_store"),
        types.InlineKeyboardButton("حذف صنف ❌", callback_data="admin_del_store"),
        types.InlineKeyboardButton("سجل الكروبات 📋", callback_data="admin_list_groups")
    )
    bot.send_message(message.chat.id, "أهلاً بك في لوحة التحكم الإدارية:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_actions(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    action = call.data.replace('admin_', '')
    chat_id = call.message.chat.id

    if action == "add_riddle":
        admin_states[ADMIN_ID] = "wait_riddle_q"
        bot.send_message(chat_id, "أرسل نص الحزورة الآن:")
    elif action == "add_q":
        admin_states[ADMIN_ID] = "wait_q_text"
        bot.send_message(chat_id, "أرسل السؤال الجديد:")
    elif action == "add_rep":
        admin_states[ADMIN_ID] = "wait_rep_key"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد:")
    elif action == "add_store":
        admin_states[ADMIN_ID] = "wait_store_name"
        bot.send_message(chat_id, "أرسل اسم الصنف الجديد:")
    elif action == "list_groups":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT title FROM groups")
        groups = c.fetchall()
        conn.close()
        text = "📋 **المجموعات المضافة:**\n\n" + "\n".join([g[0] for g in groups])
        bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and ADMIN_ID in admin_states)
def handle_admin_inputs(message):
    state = admin_states[ADMIN_ID]
    text = message.text

    if state == "wait_riddle_q":
        admin_states['temp_riddle_q'] = text
        admin_states[ADMIN_ID] = "wait_riddle_a"
        bot.send_message(message.chat.id, "أرسل إجابة الحزورة:")
    elif state == "wait_riddle_a":
        q = admin_states.pop('temp_riddle_q')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q, text))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(message.chat.id, "تمت إضافة الحزورة بنجاح!")
    
    elif state == "wait_q_text":
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT INTO questions (question) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(message.chat.id, "تمت إضافة السؤال بنجاح!")

    elif state == "wait_rep_key":
        admin_states['temp_rep_key'] = text
        admin_states[ADMIN_ID] = "wait_rep_val"
        bot.send_message(message.chat.id, "أرسل نص الرد:")
    elif state == "wait_rep_val":
        k = admin_states.pop('temp_rep_key')
        conn = sqlite3.connect("bot_data.db")
        conn.execute("INSERT OR REPLACE INTO custom_replies VALUES (?, ?)", (k, text))
        conn.commit()
        conn.close()
        del admin_states[ADMIN_ID]
        bot.send_message(message.chat.id, "تمت إضافة الرد بنجاح!")

    elif state == "wait_store_name":
        admin_states['temp_store_name'] = text
        admin_states[ADMIN_ID] = "wait_store_price"
        bot.send_message(message.chat.id, "أرسل سعر الصنف:")
    elif state == "wait_store_price":
        name = admin_states.pop('temp_store_name')
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            conn.execute("INSERT OR REPLACE INTO store VALUES (?, ?)", (name, int(text)))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "تمت إضافة الصنف بنجاح!")
        else:
            bot.send_message(message.chat.id, "السعر يجب أن يكون رقماً!")
        del admin_states[ADMIN_ID]

# تشغيل البوت والسيرفر
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
