import asyncio
import random
import json
import logging
from aiohttp import web
import jinja2
import aiohttp_jinja2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

from config import BOT_TOKEN, SUPER_ADMIN_ID, PORT, WEBAPP_URL, WHEEL_VALUES
from database import init_db, db_query

logging.basicConfig(level=logging.INFO)

# مسارات الحالات لـ ConversationHandlers
CAPTCHA, PHONE, CHARGE_AMT, CHARGE_TX, WITHDRAW_ACC, WITHDRAW_AMT, SUPPORT_MSG, GIFT_CODE, ADMIN_ADD_BAL, ADMIN_BROADCAST, ADMIN_GEN_CODE = range(11)

# --- خادم Web Server وتطبيق Render Keep-Alive ---
async def handle_ping(request):
    return web.Response(text="Bot is Live and Running 24/7!")

async def handle_wheel_page(request):
    return aiohttp_jinja2.render_template('wheel.html', request, context={})

async def handle_spin_api(request):
    data = await request.json()
    user_id = data.get('user_id')
    user = db_query("SELECT wheel_spins, bot_balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    if not user or user['wheel_spins'] <= 0:
        return web.json_response({'success': False, 'message': 'لا تملك لفات مجانية حالياً!'})

    probs_str = db_query("SELECT value FROM settings WHERE key = 'wheel_prob'", fetchone=True)['value']
    probs = json.loads(probs_str)

    prize = random.choices(WHEEL_VALUES, weights=probs, k=1)[0]
    
    # تحديث البيانات
    db_query("UPDATE users SET wheel_spins = wheel_spins - 1, bot_balance = bot_balance + ? WHERE user_id = ?", (prize, user_id), commit=True)
    return web.json_response({'success': True, 'prize': prize})

# --- دوال المساعدة لرفع الاشتراكات وصلاحيات الأدمن ---
async def check_admin(user_id, role_needed='limited'):
    res = db_query("SELECT role FROM admins WHERE user_id = ?", (user_id,), fetchone=True)
    if not res: return False
    role = res['role']
    if role == 'full': return True
    if role == 'support' and role_needed in ['support', 'limited']: return True
    if role == 'limited' and role_needed == 'limited': return True
    return False

async def check_sub(bot, user_id):
    ch = db_query("SELECT value FROM settings WHERE key = 'mandatory_channel'", fetchone=True)['value']
    if not ch: return True
    try:
        member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception:
        pass
    return False

# --- واجهة المستخدم الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # التحقق من وضع الصيانة
    maint = db_query("SELECT value FROM settings WHERE key = 'maintenance'", fetchone=True)['value']
    if maint == '1' and not await check_admin(user_id):
        await update.message.reply_text("⚠️ البوت حالياً في وضع الصيانة. يرجى الانتظار لحين الانتهاء.")
        return ConversationHandler.END

    user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    if not user:
        ref_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
        db_query("INSERT INTO users (user_id, full_name, username, referred_by) VALUES (?, ?, ?, ?)",
                 (user_id, update.effective_user.full_name, update.effective_user.username, ref_by), commit=True)
        
        # حماية من الرشق - اختبار الكابتشا
        num1, num2 = random.randint(1, 9), random.randint(1, 9)
        context.user_data['captcha_res'] = num1 + num2
        await update.message.reply_text(f"🔒 **اختبار الحماية ضد الرشق:**\nرجاءً قم بحل الإجابة الصحيحة للبدء:\nكم يساوي `{num1} + {num2}`؟")
        return CAPTCHA

    if not user['is_verified']:
        num1, num2 = random.randint(1, 9), random.randint(1, 9)
        context.user_data['captcha_res'] = num1 + num2
        await update.message.reply_text(f"🔒 **اختبار الحماية ضد الرشق:**\nكم يساوي `{num1} + {num2}`؟")
        return CAPTCHA

    return await show_main_menu(update, context)

async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.isdigit() and int(text) == context.user_data.get('captcha_res'):
        kb = [[KeyboardButton("📱 مشاركة رقم الهاتف السوري", request_contact=True)]]
        await update.message.reply_text("✅ إجابة صحيحة! يرجى الآن مشاركة رقم هاتفك السوري حصراً للتحقق (+963):",
                                       reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
        return PHONE
    else:
        await update.message.reply_text("❌ إجابة خاطئة! أعد المحاولة:")
        return CAPTCHA

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact or not contact.phone_number.startswith(('963', '+963')):
        await update.message.reply_text("❌ نعتذر! يجب استخدام رقم سوري حصراً يدعم (+963).")
        return PHONE

    user_id = update.effective_user.id
    phone = contact.phone_number
    db_query("UPDATE users SET phone = ?, is_verified = 1 WHERE user_id = ?", (phone, user_id), commit=True)

    # معالجة البونص الترحيبي والإحالات
    welcome_bonus = float(db_query("SELECT value FROM settings WHERE key = 'welcome_bonus'", fetchone=True)['value'])
    if welcome_bonus > 0:
        db_query("UPDATE users SET bot_balance = bot_balance + ? WHERE user_id = ?", (welcome_bonus, user_id), commit=True)

    user = db_query("SELECT referred_by FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user and user['referred_by']:
        ref_id = user['referred_by']
        db_query("UPDATE users SET wheel_spins = wheel_spins + 1, active_referrals = active_referrals + 1 WHERE user_id = ?", (ref_id,), commit=True)
        try:
            await context.bot.send_message(ref_id, f"🎉 انضم شخص جديد عن طريق رابط الإحالة الخاص بك! حصلت على لفة مجانية في العجلة.")
        except Exception: pass

    # إشعار للآدمن
    await context.bot.send_message(SUPER_ADMIN_ID, f"🔔 **دخول مستخدم جديد:**\nالاسم: {update.effective_user.full_name}\nالرقم: {phone}\nالمُحيل: {user['referred_by'] if user else 'لا يوجد'}")

    await update.message.reply_text("✅ تم التحقق بنجاح من رقمك!", reply_markup=ReplyKeyboardMarkup([[]], remove_keyboard=True))
    return await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # تحقق من الاشتراكات الأجبارية
    if not await check_sub(context.bot, user_id):
        ch_link = db_query("SELECT value FROM settings WHERE key = 'channel_link'", fetchone=True)['value']
        await update.effective_message.reply_text(f"⚠️ يجب عليك الاشتراك بقناة البوت أولاً لاستخدامه:\n{ch_link}")
        return

    user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    msg = (
        f"🙋‍♂️ **مرحباً بك {user['full_name']} في لوحة العميل**\n\n"
        f"🆔 معرف الحساب: `{user['user_id']}`\n"
        f"👤 حساب iChancy الخاص بك: `{user['ichancy_user']}`\n"
        f"🔑 كلمة المرور: `{user['ichancy_pass']}`\n\n"
        f"💰 رصيدك في البوت: `{user['bot_balance']}`$\n"
        f"🌐 رصيدك في الموقع: `{user['site_balance']}`$\n"
        f"🎡 اللفات المتاحة للعجلة: `{user['wheel_spins']}`\n"
    )

    kb = [
        [InlineKeyboardButton("💳 شحن رصيد للبوت", callback_data="charge_bot"), InlineKeyboardButton("💸 سحب رصيد من البوت", callback_data="withdraw_bot")],
        [InlineKeyboardButton("📥 شحن إلى الموقع", callback_data="site_dep"), InlineKeyboardButton("📤 سحب من الموقع", callback_data="site_with")],
        [InlineKeyboardButton("🎡 عجلة الحظ (Web App)", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("🔗 نظام الإحالة المتطور", callback_data="ref_system"), InlineKeyboardButton("🎁 ادخال كود هدية", callback_data="enter_gift")],
        [InlineKeyboardButton("💬 مراسلة الدعم", callback_data="contact_support"), InlineKeyboardButton("📢 العروض الحالية", callback_data="view_offers")]
    ]

    if await check_admin(user_id):
        kb.append([InlineKeyboardButton("⚙️ لوحة التحكم للآدمن", callback_data="admin_panel")])

    if update.callback_query:
        await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- معالجة طلب الشحن والسحب ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "charge_bot":
        kb = [
            [InlineKeyboardButton("شام كاش", callback_data="method_شام كاش")],
            [InlineKeyboardButton("سيرياتيل كاش", callback_data="method_سيرياتيل كاش")]
        ]
        await query.message.edit_text("اختر طريقة الشحن المناسبة:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("method_"):
        method = data.split("_")[1]
        context.user_data['selected_method'] = method
        pm = db_query("SELECT details FROM payment_methods WHERE name = ?", (method,), fetchone=True)
        await query.message.edit_text(f"💳 **طريقة الشحن {method}:**\n{pm['details']}\n\nرجاءً أدخل المبلغ الذي أرسلته بالسورية/الدولار:")
        return CHARGE_AMT

    elif data == "ref_system":
        user = db_query("SELECT * FROM users WHERE user_id = ?", (query.from_user.id,), fetchone=True)
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={query.from_user.id}"
        msg = (
            f"🔗 **نظام الإحالة المتطور:**\n\n"
            f"شارك هذا الرابط للربح:\n`{link}`\n\n"
            f"👥 عدد الإحالات النشطة لديك: `{user['active_referrals']}`\n"
            f"🎁 تحصل على لفة مجانية لكل شخص ينشئ حسابه.\n"
            f"🔥 **نظام الـ 10% حرق:** عند امتلاكك 3 إحالات نشطة، ستحصل على 10% من نسبة حرق مشحونات إحالاتك (تراجع وتقبض يدوي كل 10 أيام من الإدارة)."
        )
        await query.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="main_menu")]]))

    elif data == "main_menu":
        await show_main_menu(update, context)

    # موافقات الإدارة
    elif data.startswith("app_") or data.startswith("rej_"):
        if not await check_admin(query.from_user.id): return
        action, tx_id = data.split("_")
        tx = db_query("SELECT * FROM transactions WHERE id = ?", (tx_id,), fetchone=True)
        if not tx or tx['status'] != 'pending':
            await query.message.edit_text("هذه العملية معالجة سابقاً!")
            return

        if action == "app":
            db_query("UPDATE transactions SET status = 'approved' WHERE id = ?", (tx_id,), commit=True)
            if tx['type'] == 'deposit':
                bonus_pct = float(db_query("SELECT value FROM settings WHERE key = 'deposit_bonus_pct'", fetchone=True)['value'])
                final_amt = tx['amount'] * (1 + bonus_pct / 100.0)
                db_query("UPDATE users SET bot_balance = bot_balance + ?, total_deposited = total_deposited + ? WHERE user_id = ?",
                         (final_amt, tx['amount'], tx['user_id']), commit=True)
                await context.bot.send_message(tx['user_id'], f"✅ تم قبول طلب الشحن بمبلغ {tx['amount']}$ (+ بونص {bonus_pct}%)!")
            
            await query.message.edit_text(f"✅ تم القبول للعملية رقم #{tx_id}")

        elif action == "rej":
            db_query("UPDATE transactions SET status = 'rejected' WHERE id = ?", (tx_id,), commit=True)
            await context.bot.send_message(tx['user_id'], f"❌ تم رفض عملية {tx['type']} رقم #{tx_id}")
            await query.message.edit_text(f"❌ تم الرفض للعملية رقم #{tx_id}")

    elif data == "admin_panel":
        if await check_admin(query.from_user.id):
            await show_admin_panel(query)

async def receive_charge_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        amt = float(text)
        context.user_data['charge_amt'] = amt
        await update.message.reply_text("الآن أدخل رقم العملية/التحويل:")
        return CHARGE_TX
    except ValueError:
        await update.message.reply_text("يرجى إدخال مبلغ صحيح بالأرقام:")
        return CHARGE_AMT

async def receive_charge_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_id = update.message.text
    user_id = update.effective_user.id
    amt = context.user_data['charge_amt']
    method = context.user_data['selected_method']

    db_query("INSERT INTO transactions (user_id, type, amount, method, account_or_txid) VALUES (?, 'deposit', ?, ?, ?)",
             (user_id, amt, method, tx_id), commit=True)
    
    res = db_query("SELECT last_insert_rowid() as id", fetchone=True)
    tx_no = res['id']

    await update.message.reply_text("✅ تم إرسال طلب الشحن إلى الإدارة للمراجعة والموافقة.")
    
    # إشعار للإدارة
    kb = [
        [InlineKeyboardButton("✅ موافقة", callback_data=f"app_{tx_no}"), InlineKeyboardButton("❌ رفض", callback_data=f"rej_{tx_no}")]
    ]
    await context.bot.send_message(
        SUPER_ADMIN_ID,
        f"📥 **طلب شحن جديد (# {tx_no}):**\nالمستخدم: `{user_id}`\nالمبلغ: `{amt}`$\nالطريقة: `{method}`\nرقم العملية: `{tx_id}`",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- لوحة تحكم الإدارة الكاملة ---
async def show_admin_panel(query):
    kb = [
        [InlineKeyboardButton("⚙️ تفعيل/إلغاء وضع الصيانة", callback_data="adm_maint")],
        [InlineKeyboardButton("➕ إضافة رصيد", callback_data="adm_addbal"), InlineKeyboardButton("🎁 توليد كود هدية", callback_data="adm_gencode")],
        [InlineKeyboardButton("📢 رسالة جماعية", callback_data="adm_bc"), InlineKeyboardButton("📊 إحصائيات وأرصدة اللاعبين", callback_data="adm_stats")]
    ]
    await query.message.edit_text("⚙️ **لوحة التحكم العليا للإدارة**", reply_markup=InlineKeyboardMarkup(kb))

# --- تشغيل البوت مع خادم Web Server على Render ---
async def main():
    init_db()

    # إنشاء تطبيق التلجرام
    app = Application.builder().token(BOT_TOKEN).build()

    # إضافة Handlers
    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(handle_callbacks)
        ],
        states={
            CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, handle_phone)],
            CHARGE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_charge_amt)],
            CHARGE_TX: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_charge_tx)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callbacks))

    # تهيئة تطبيق aiohttp ليعمل كسيرفر متكامل على Render
    web_app = web.Application()
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader('templates'))

    web_app.router.add_get('/', handle_ping)
    web_app.router.add_get('/wheel', handle_wheel_page)
    web_app.router.add_post('/api/spin', handle_spin_api)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    logging.info(f"Web server active on port {PORT}")

    # بدء البوت بالتوازي
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # الحفاظ على الجلسة شغال
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
