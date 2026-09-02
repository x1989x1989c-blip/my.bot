import asyncio
import random
import json
import logging
import re
from aiohttp import web
import jinja2
import aiohttp_jinja2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

from config import BOT_TOKEN, SUPER_ADMIN_ID, PORT, WHEEL_VALUES
from database import init_db, db_query

logging.basicConfig(level=logging.INFO)

# رابط سيرفر الـ Web App لعجلة الحظ
SERVER_WHEEL_URL = "https://my-bot-j48l.onrender.com/wheel"

# --- تعريف كافة الحالات لـ ConversationHandler ---
(
    CAPTCHA, PHONE, CHARGE_AMT, CHARGE_TX, WITHDRAW_ACC, WITHDRAW_AMT,
    SITE_DEP_AMT, SITE_WITH_AMT, GIFT_CODE_INPUT, SUPPORT_INPUT, INJURY_INPUT,
    ADMIN_USER_DETAILS_SEARCH, ADMIN_ADD_BAL_USER, ADMIN_ADD_BAL_AMT, 
    ADMIN_DEDUCT_BAL_USER, ADMIN_DEDUCT_BAL_AMT, ADMIN_GEN_CODE_VAL, 
    ADMIN_GEN_CODE_USES, ADMIN_GEN_CODE_QTY, ADMIN_CANCEL_CODE_INPUT,
    ADMIN_BC_MSG, ADMIN_PRIV_USER, ADMIN_PRIV_TEXT, ADMIN_METHOD_NAME, 
    ADMIN_METHOD_DETAILS, ADMIN_METHOD_DEL, ADMIN_WEL_BONUS, ADMIN_DEP_BONUS,
    ADMIN_WHEEL_PROBS, ADMIN_OFFER_TITLE, ADMIN_OFFER_TEXT, ADMIN_SET_CHANNEL,
    ADMIN_BAN_USER, ADMIN_UNBAN_USER, ADMIN_ADD_ADMIN_ID, ADMIN_ADD_ADMIN_ROLE,
    ADMIN_REM_ADMIN_ID, ADMIN_REPLY_USER, ADMIN_REPLY_TEXT,
    ICHANCY_USER_INPUT, ICHANCY_PASS_INPUT
) = range(41)

# --- دالة التحقق المرنة والشاملة من الرقم السوري ---
def parse_syrian_phone(text: str) -> str | None:
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    
    if digits.startswith("00963"):
        digits = digits[5:]
    elif digits.startswith("963"):
        digits = digits[3:]
        
    if digits.startswith("0"):
        digits = digits[1:]
        
    if len(digits) == 9 and digits.startswith("9"):
        return "+963" + digits
    return None

# --- السيرفر لتشغيل WebApp وKeep-Alive ---
async def handle_ping(request):
    return web.Response(text="iChancy Bot Server is Active!")

async def handle_wheel_page(request):
    return aiohttp_jinja2.render_template('wheel.html', request, context={})

async def handle_spin_api(request):
    data = await request.json()
    user_id = data.get('user_id')
    user = db_query("SELECT wheel_spins, bot_balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    if not user or user['wheel_spins'] <= 0:
        return web.json_response({'success': False, 'message': 'لا تملك لفات مجانية حالياً!'})

    res = db_query("SELECT value FROM settings WHERE key = 'wheel_prob'", fetchone=True)
    probs_str = res['value'] if res and res['value'] else '[30.0, 25.0, 20.0, 10.0, 8.0, 5.0, 1.8, 0.19, 0.01]'
    try:
        probs = json.loads(probs_str)
    except Exception:
        probs = [30.0, 25.0, 20.0, 10.0, 8.0, 5.0, 1.8, 0.19, 0.01]

    prize = random.choices(WHEEL_VALUES, weights=probs, k=1)[0]
    
    db_query("UPDATE users SET wheel_spins = wheel_spins - 1, wheel_spins_done = wheel_spins_done + 1, bot_balance = bot_balance + ? WHERE user_id = ?",
             (prize, user_id), commit=True)
    return web.json_response({'success': True, 'prize': prize})

# --- الصلاحيات والاشتراك الإجباري ---
async def check_admin(user_id, role_needed='limited'):
    if user_id == SUPER_ADMIN_ID: return True
    res = db_query("SELECT role FROM admins WHERE user_id = ?", (user_id,), fetchone=True)
    if not res: return False
    role = res['role']
    if role == 'full': return True
    if role == 'support' and role_needed in ['support', 'limited']: return True
    if role == 'limited' and role_needed == 'limited': return True
    return False

async def check_sub(bot, user_id):
    res = db_query("SELECT value FROM settings WHERE key = 'mandatory_channel'", fetchone=True)
    ch = res['value'] if res else ''
    if not ch: return True
    try:
        member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception:
        pass
    return False

# --- البداية والكابتشا ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user and user['is_banned']:
        await update.message.reply_text("⛔️ حسابك محظور من استخدام البوت.")
        return ConversationHandler.END

    maint_res = db_query("SELECT value FROM settings WHERE key = 'maintenance'", fetchone=True)
    if maint_res and maint_res['value'] == '1' and not await check_admin(user_id):
        await update.message.reply_text("⚠️ البوت حالياً في وضع الصيانة. يرجى الانتظار.")
        return ConversationHandler.END

    if not user:
        ref_by = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
        db_query("INSERT INTO users (user_id, full_name, username, referred_by) VALUES (?, ?, ?, ?)",
                 (user_id, update.effective_user.full_name, update.effective_user.username, ref_by), commit=True)
        
        num1, num2 = random.randint(1, 9), random.randint(1, 9)
        context.user_data['captcha_res'] = num1 + num2
        await update.message.reply_text(f"🔒 **اختبار الحماية ضد الرشق:**\nحل المسألة للبدء:\nكم يساوي `{num1} + {num2}`؟", parse_mode="Markdown")
        return CAPTCHA

    if not user['is_verified']:
        num1, num2 = random.randint(1, 9), random.randint(1, 9)
        context.user_data['captcha_res'] = num1 + num2
        await update.message.reply_text(f"🔒 **اختبار الحماية ضد الرشق:**\nكم يساوي `{num1} + {num2}`؟", parse_mode="Markdown")
        return CAPTCHA

    return await show_main_menu(update, context)

async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text and text.isdigit() and int(text) == context.user_data.get('captcha_res'):
        kb = [[KeyboardButton("📱 مشاركة رقم الهاتف السوري", request_contact=True)]]
        await update.message.reply_text("✅ إجابة صحيحة! شارك رقمك السوري عبر الزر، أو أرسله كتابةً (مثال: 0912345678):",
                                       reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
        return PHONE
    else:
        await update.message.reply_text("❌ إجابة خاطئة! أعد المحاولة:")
        return CAPTCHA

# --- استلام وتأكيد الرقم السوري ---
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_input = ""
    if update.message and update.message.contact and update.message.contact.phone_number:
        raw_input = update.message.contact.phone_number
    elif update.message and update.message.text:
        raw_input = update.message.text

    phone = parse_syrian_phone(raw_input)
    if not phone:
        await update.message.reply_text("❌ رقم سوري غير صالح! أرسل رقماً يبدأ بـ 09 أو استخدم زر المشاركة.")
        return PHONE

    wb_res = db_query("SELECT value FROM settings WHERE key = 'welcome_bonus'", fetchone=True)
    try:
        welcome_bonus = float(wb_res['value']) if wb_res and wb_res['value'] else 0.0
    except ValueError:
        welcome_bonus = 0.0

    # إعداد وتأكيد رقم الهاتف دون إنشاء حساب ichancy تلقائياً
    db_query("""UPDATE users SET phone = ?, is_verified = 1, bot_balance = bot_balance + ? WHERE user_id = ?""",
             (phone, welcome_bonus, user_id), commit=True)

    user = db_query("SELECT referred_by FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    ref_id = user['referred_by'] if user else None

    if ref_id:
        db_query("UPDATE users SET wheel_spins = wheel_spins + 1, active_referrals = active_referrals + 1 WHERE user_id = ?", (ref_id,), commit=True)
        try:
            await context.bot.send_message(ref_id, "🎉 انضم شخص جديد عن طريق رابط الإحالة الخاص بك! حصلت على لفة مجانية.")
        except Exception: pass

    try:
        ref_txt = f"`{ref_id}`" if ref_id else "مباشر بدون إحالة"
        await context.bot.send_message(SUPER_ADMIN_ID, 
            f"🔔 **دخول وتسجيل عميل جديد:**\n"
            f"👤 الاسم: {update.effective_user.full_name}\n"
            f"🆔 ID: `{user_id}`\n"
            f"📱 الرقم: `{phone}`\n"
            f"🔗 المُحيل: {ref_txt}", parse_mode="Markdown")
    except Exception: pass

    await update.message.reply_text("✅ تم تفعيل رقمك بنجاح! يمكنك الآن إنشاء حساب iChancy من القائمة الرئيسية.", reply_markup=ReplyKeyboardMarkup([[]], remove_keyboard=True))
    return await show_main_menu(update, context)

# --- واجهة لوحة العميل ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await check_sub(context.bot, user_id):
        ch_res = db_query("SELECT value FROM settings WHERE key = 'channel_link'", fetchone=True)
        ch_name = db_query("SELECT value FROM settings WHERE key = 'channel_name'", fetchone=True)
        link = ch_res['value'] if ch_res else 'https://t.me/'
        name = ch_name['value'] if ch_name else 'القناة الرسمية'
        
        kb = [[InlineKeyboardButton(f"📢 اشترك في {name}", url=link)],
              [InlineKeyboardButton("✅ تحققت من الاشتراك", callback_data="check_sub_retry")]]
        await update.effective_message.reply_text("⚠️ **يجب عليك الاشتراك بقناة البوت لاستخدامه:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return ConversationHandler.END

    has_ichancy = bool(user['ichancy_user'])

    msg = (
        f"🙋‍♂️ **مرحباً بك {user['full_name']} في لوحة العميل**\n\n"
        f"🆔 معرف الحساب: `{user['user_id']}`\n"
        f"💰 رصيدك في البوت: `{user['bot_balance']:.2f}` ل.س\n"
        f"🌐 رصيدك في الموقع: `{user['site_balance']:.2f}` ل.س\n"
        f"🎡 اللفات المتاحة للعجلة: `{user['wheel_spins']}`\n"
    )

    # زر إنشاء / عرض حساب ichancy
    if has_ichancy:
        ichancy_btn = InlineKeyboardButton("👤 حسابي ichancy", callback_data="show_ichancy_acc")
    else:
        ichancy_btn = InlineKeyboardButton("✨ إنشاء حساب ichancy", callback_data="create_ichancy_acc")

    kb = [
        [ichancy_btn],
        [InlineKeyboardButton("💳 شحن رصيد للبوت", callback_data="charge_bot"), InlineKeyboardButton("💸 سحب رصيد من البوت", callback_data="withdraw_bot")],
        [InlineKeyboardButton("📥 شحن إلى الموقع", callback_data="site_dep"), InlineKeyboardButton("📤 سحب من الموقع", callback_data="site_with")],
        [InlineKeyboardButton("🎡 عجلة الحظ (Web App)", web_app=WebAppInfo(url=SERVER_WHEEL_URL))],
        [InlineKeyboardButton("🔗 نظام الإحالة المتطور", callback_data="ref_system"), InlineKeyboardButton("🎁 ادخال كود هدية", callback_data="enter_gift")],
        [InlineKeyboardButton("💬 مراسلة الدعم", callback_data="contact_support"), InlineKeyboardButton("🚨 إرسال إصابة", callback_data="send_injury")],
        [InlineKeyboardButton("📢 العروض الحالية", callback_data="view_offers")]
    ]

    if await check_admin(user_id):
        kb.append([InlineKeyboardButton("⚙️ لوحة التحكم للإدارة", callback_data="admin_panel")])

    if update.callback_query:
        await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- معالجة الأزرار التفاعلية ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "check_sub_retry" or data == "main_menu":
        await show_main_menu(update, context)

    elif data == "create_ichancy_acc":
        user_id = query.from_user.id
        user = db_query("SELECT ichancy_user FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if user and user['ichancy_user']:
            await query.answer("لديك حساب بالفعل!", show_alert=True)
            return
        await query.message.edit_text("✍️ **إنشاء حساب iChancy:**\n\nأدخل اسم المستخدم المطلوب (يجب أن يتكون من 6 أحرف/أرقام بالضبط):")
        return ICHANCY_USER_INPUT

    elif data == "show_ichancy_acc":
        user_id = query.from_user.id
        user = db_query("SELECT ichancy_user, ichancy_pass FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if user and user['ichancy_user']:
            acc_info = (
                f"🎮 **معلومات حسابك في iChancy:**\n\n"
                f"👤 اسم المستخدم: `{user['ichancy_user']}`\n"
                f"🔑 كلمة المرور: `{user['ichancy_pass']}`"
            )
            await query.message.edit_text(acc_info, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="main_menu")]]))
        else:
            await query.answer("لم تقم بإنشاء حساب بعد!", show_alert=True)

    elif data == "charge_bot":
        methods = db_query("SELECT name FROM payment_methods", fetchall=True)
        kb = [[InlineKeyboardButton(m['name'], callback_data=f"method_{m['name']}")] for m in methods]
        kb.append([InlineKeyboardButton("رجوع", callback_data="main_menu")])
        await query.message.edit_text("اختر طريقة الشحن المناسبة:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("method_"):
        method_name = data.replace("method_", "")
        context.user_data['selected_method'] = method_name
        pm = db_query("SELECT details FROM payment_methods WHERE name = ?", (method_name,), fetchone=True)
        details = pm['details'] if pm else 'تواصل مع الدعم'
        await query.message.edit_text(f"💳 **طريقة الشحن ({method_name}):**\n\n{details}\n\nأدخل مبلغ الشحن المطلوب (يتلقى أول رقم فقط):")
        return CHARGE_AMT

    elif data == "withdraw_bot":
        await query.message.edit_text("💸 **سحب رصيد من البوت:**\nأدخل رقم حسابك / محفظتك أولاً:")
        return WITHDRAW_ACC

    elif data == "site_dep":
        await query.message.edit_text("📥 **شحن إلى الموقع:**\nأدخل المبلغ المراد تحويله من رصيد البوت إلى الموقع:")
        return SITE_DEP_AMT

    elif data == "site_with":
        await query.message.edit_text("📤 **سحب من الموقع:**\nأدخل المبلغ المراد تحويله من الموقع إلى رصيد البوت:")
        return SITE_WITH_AMT

    elif data == "ref_system":
        user_id = query.from_user.id
        user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        ref_deps = db_query("SELECT SUM(total_deposited) as sum FROM users WHERE referred_by = ?", (user_id,), fetchone=True)
        total_ref_dep = ref_deps['sum'] if ref_deps and ref_deps['sum'] else 0.0

        msg = (
            f"🔗 **نظام الإحالة المتطور:**\n\n"
            f"رابط الإحالة الخاص بك:\n`{link}`\n\n"
            f"👥 عدد إحالاتك النشطة: `{user['active_referrals']}`\n"
            f"💰 إجمالي مشحونات إحالاتك: `{total_ref_dep:.2f}` ل.س\n"
            f"🎡 تحصّل على 1 لفة مجانية لكل شخص يُسجل عن طريقك.\n"
            f"🔥 **ميزة الـ 10% حرق:** عند امتلاك 3 إحالات نشطة، تربح 10% من نسبة حرق المشحونات (تراجع وتقبض يدويًا من الإدارة كل 10 أيام)."
        )
        await query.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="main_menu")]]))

    elif data == "enter_gift":
        await query.message.edit_text("🎁 أدخل كود الهدية:")
        return GIFT_CODE_INPUT

    elif data == "contact_support":
        context.user_data['ticket_type'] = 'support'
        await query.message.edit_text("💬 **مراسلة الدعم الفني:**\nأرسل رسالتك الآن (نص أو صورة):")
        return SUPPORT_INPUT

    elif data == "send_injury":
        context.user_data['ticket_type'] = 'injury'
        await query.message.edit_text("🚨 **إرسال إصابة / بلاغ:**\nأرسل تفاصيل البلاغ (نص أو صورة):")
        return INJURY_INPUT

    elif data == "view_offers":
        offers = db_query("SELECT * FROM offers ORDER BY id DESC", fetchall=True)
        txt = "📢 **العروض الحالية:**\n\n" + "\n\n".join([f"🔹 **{o['title']}**\n{o['content']}" for o in offers]) if offers else "لا توجد عروض حالياً."
        await query.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="main_menu")]]))

    # --- قبول ورفض الشحن والسحب ---
    elif data.startswith("app_tx_") or data.startswith("rej_tx_"):
        if not await check_admin(query.from_user.id): return
        parts = data.split("_")
        action, tx_id = parts[0], parts[2]
        tx = db_query("SELECT * FROM transactions WHERE id = ?", (tx_id,), fetchone=True)
        if not tx or tx['status'] != 'pending':
            await query.message.edit_text("هذه العملية معالجة سابقاً!")
            return

        if action == "app":
            db_query("UPDATE transactions SET status = 'approved' WHERE id = ?", (tx_id,), commit=True)
            if tx['type'] == 'deposit':
                bon_res = db_query("SELECT value FROM settings WHERE key = 'deposit_bonus_pct'", fetchone=True)
                match_res = db_query("SELECT value FROM settings WHERE key = 'matching_bonus_pct'", fetchone=True)
                
                try:
                    bonus_pct = float(bon_res['value']) if bon_res and bon_res['value'] else 0.0
                except ValueError: bonus_pct = 0.0

                try:
                    match_pct = float(match_res['value']) if match_res and match_res['value'] else 0.0
                except ValueError: match_pct = 0.0

                tx_code = str(tx['account_or_txid'])
                extra_bonus = match_pct if (len(tx_code) >= 2 and tx_code[-1] == tx_code[-2]) else 0.0
                
                tot_pct = bonus_pct + extra_bonus
                final_amt = tx['amount'] * (1 + tot_pct / 100.0)

                db_query("UPDATE users SET bot_balance = bot_balance + ?, total_deposited = total_deposited + ? WHERE user_id = ?",
                         (final_amt, tx['amount'], tx['user_id']), commit=True)
                
                try:
                    await context.bot.send_message(tx['user_id'], f"✅ تم قبول طلب الشحن! أضيف لرصيدك `{final_amt:.2f}` ل.س (تتضمن بونص {tot_pct}%).", parse_mode="Markdown")
                except Exception: pass

            elif tx['type'] == 'withdraw':
                db_query("UPDATE users SET bot_balance = bot_balance - ? WHERE user_id = ?", (tx['amount'], tx['user_id']), commit=True)
                try:
                    await context.bot.send_message(tx['user_id'], f"✅ تم تنفيذ طلب السحب بمبلغ `{tx['amount']:.2f}` ل.س بنجاح.", parse_mode="Markdown")
                except Exception: pass

            await query.message.edit_text(f"✅ تم قبول المعاملة #{tx_id}")

        elif action == "rej":
            db_query("UPDATE transactions SET status = 'rejected' WHERE id = ?", (tx_id,), commit=True)
            try:
                await context.bot.send_message(tx['user_id'], f"❌ تم رفض المعاملة #{tx_id}.")
            except Exception: pass
            await query.message.edit_text(f"❌ تم رفض المعاملة #{tx_id}")

    elif data == "admin_panel":
        if await check_admin(query.from_user.id):
            await show_admin_panel(query)

    elif data.startswith("adm_"):
        await handle_admin_callbacks(query, context, data)

# --- استلام اسم مستخدم وكلمة مرور حساب ichancy ---
async def receive_ichancy_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) != 6:
        await update.message.reply_text("❌ يجب أن يتكون اسم المستخدم من 6 أحرف أو أرقام بالضبط! أعد المحاولة:")
        return ICHANCY_USER_INPUT

    context.user_data['temp_ichancy_user'] = text
    await update.message.reply_text("🔑 الآن أدخل كلمة المرور الخاصة بالحساب:")
    return ICHANCY_PASS_INPUT

async def receive_ichancy_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = update.message.text.strip()
    user_id = update.effective_user.id
    u_name = context.user_data.get('temp_ichancy_user')

    user = db_query("SELECT ichancy_user FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    if user and not user['ichancy_user']:
        # عند الإنشاء لأول مرة بشكل يدوي -> إعطاء 1 لفة مجانية
        db_query("UPDATE users SET ichancy_user = ?, ichancy_pass = ?, wheel_spins = wheel_spins + 1 WHERE user_id = ?",
                 (u_name, pwd, user_id), commit=True)
        await update.message.reply_text("✅ تم إنشاء حسابك في iChancy بنجاح! وحصلت على 1 لفة مجانية في عجلة الحظ 🎡")
    else:
        db_query("UPDATE users SET ichancy_user = ?, ichancy_pass = ? WHERE user_id = ?",
                 (u_name, pwd, user_id), commit=True)
        await update.message.reply_text("✅ تم تحديث بيانات حساب iChancy بنجاح!")

    return await show_main_menu(update, context)

# --- استلام وتطبيق عمليات العميل ---
async def receive_charge_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", update.message.text or "")
    if not numbers:
        await update.message.reply_text("❌ أدخل مبلغ صحيح بالأرقام:")
        return CHARGE_AMT

    amt = float(numbers[0])
    context.user_data['charge_amt'] = amt
    await update.message.reply_text("الآن أدخل رقم العملية / التحويل:")
    return CHARGE_TX

async def receive_charge_tx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tx_id = update.message.text.strip()
    user_id = update.effective_user.id
    amt = context.user_data.get('charge_amt', 0)
    method = context.user_data.get('selected_method', 'غير محدد')

    db_query("INSERT INTO transactions (user_id, type, amount, method, account_or_txid) VALUES (?, 'deposit', ?, ?, ?)",
             (user_id, amt, method, tx_id), commit=True)
    
    res = db_query("SELECT last_insert_rowid() as id", fetchone=True)
    tx_no = res['id'] if res else 0

    await update.message.reply_text("✅ تم إرسال طلب الشحن للإدارة للمراجعة.")
    
    kb = [[InlineKeyboardButton("✅ موافقة", callback_data=f"app_tx_{tx_no}"), InlineKeyboardButton("❌ رفض", callback_data=f"rej_tx_{tx_no}")]]
    try:
        await context.bot.send_message(SUPER_ADMIN_ID,
            f"📥 **طلب شحن جديد (# {tx_no}):**\n"
            f"👤 العميل: `{user_id}`\n"
            f"💰 المبلغ: `{amt}` ل.س\n"
            f"💳 الطريقة: `{method}`\n"
            f"🔢 رقم العملية: `{tx_id}`",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception: pass
    return ConversationHandler.END

async def receive_withdraw_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['withdraw_acc'] = update.message.text.strip()
    await update.message.reply_text("أدخل المبلغ المطلوب سحبه:")
    return WITHDRAW_AMT

async def receive_withdraw_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", update.message.text or "")
    if not numbers:
        await update.message.reply_text("أدخل مبلغ صحيح:")
        return WITHDRAW_AMT

    amt = float(numbers[0])
    user_id = update.effective_user.id
    user = db_query("SELECT bot_balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)

    if not user or user['bot_balance'] < amt:
        await update.message.reply_text("❌ رصيدك في البوت غير كافٍ!")
        return ConversationHandler.END

    acc = context.user_data.get('withdraw_acc', '')
    db_query("INSERT INTO transactions (user_id, type, amount, method, account_or_txid) VALUES (?, 'withdraw', ?, 'سحب رصيد', ?)",
             (user_id, amt, acc), commit=True)
    
    res = db_query("SELECT last_insert_rowid() as id", fetchone=True)
    tx_no = res['id'] if res else 0

    await update.message.reply_text("✅ تم إرسال طلب السحب للإدارة.")
    kb = [[InlineKeyboardButton("✅ موافقة", callback_data=f"app_tx_{tx_no}"), InlineKeyboardButton("❌ رفض", callback_data=f"rej_tx_{tx_no}")]]
    try:
        await context.bot.send_message(SUPER_ADMIN_ID,
            f"📤 **طلب سحب جديد (# {tx_no}):**\n"
            f"👤 العميل: `{user_id}`\n"
            f"💰 المبلغ: `{amt}` ل.س\n"
            f"💳 الحساب: `{acc}`",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception: pass
    return ConversationHandler.END

async def receive_site_dep_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", update.message.text or "")
    if not numbers: return SITE_DEP_AMT
    amt = float(numbers[0])
    user_id = update.effective_user.id
    user = db_query("SELECT bot_balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)

    if not user or user['bot_balance'] < amt:
        await update.message.reply_text("❌ رصيدك في البوت غير كافٍ!")
        return ConversationHandler.END

    db_query("UPDATE users SET bot_balance = bot_balance - ?, site_balance = site_balance + ? WHERE user_id = ?",
             (amt, amt, user_id), commit=True)
    await update.message.reply_text(f"✅ تم تحويل `{amt:.2f}` ل.س بنجاح إلى حسابك في الموقع!", parse_mode="Markdown")
    return ConversationHandler.END

async def receive_site_with_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", update.message.text or "")
    if not numbers: return SITE_WITH_AMT
    amt = float(numbers[0])
    user_id = update.effective_user.id
    user = db_query("SELECT site_balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)

    if not user or user['site_balance'] < amt:
        await update.message.reply_text("❌ رصيدك بالموقع غير كافٍ!")
        return ConversationHandler.END

    db_query("UPDATE users SET site_balance = site_balance - ?, bot_balance = bot_balance + ? WHERE user_id = ?",
             (amt, amt, user_id), commit=True)
    await update.message.reply_text(f"✅ تم تحويل `{amt:.2f}` ل.س بنجاح إلى رصيد البوت الخاص بك!", parse_mode="Markdown")
    return ConversationHandler.END

async def receive_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_in = update.message.text.strip()
    user_id = update.effective_user.id

    code_data = db_query("SELECT * FROM gift_codes WHERE code = ? AND active = 1", (code_in,), fetchone=True)
    if not code_data or code_data['used_count'] >= code_data['max_uses']:
        await update.message.reply_text("❌ الكود غير صحيح أو ملغى أو منتهي الاستخدامات!")
        return ConversationHandler.END

    already = db_query("SELECT id FROM gift_code_logs WHERE code = ? AND user_id = ?", (code_in, user_id), fetchone=True)
    if already:
        await update.message.reply_text("❌ لقد استخدمت هذا الكود من قبل!")
        return ConversationHandler.END

    val = code_data['value']
    db_query("UPDATE users SET bot_balance = bot_balance + ? WHERE user_id = ?", (val, user_id), commit=True)
    db_query("UPDATE gift_codes SET used_count = used_count + 1 WHERE code = ?", (code_in,), commit=True)
    db_query("INSERT INTO gift_code_logs (code, user_id) VALUES (?, ?)", (code_in, user_id), commit=True)

    await update.message.reply_text(f"🎉 تم استخدام الكود وأُضيفت `{val:.2f}` ل.س لرصيدك!", parse_mode="Markdown")
    try:
        await context.bot.send_message(SUPER_ADMIN_ID, f"🎁 **استخدام كود هدية:**\nالعميل: `{user_id}`\nالكود: `{code_in}`\nالقيمة: `{val}` ل.س")
    except Exception: pass
    return ConversationHandler.END

async def receive_support_or_injury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txt = update.message.text or update.message.caption or "بدون نص"
    photo_id = update.message.photo[-1].file_id if update.message.photo else None
    ticket_type = context.user_data.get('ticket_type', 'support')
    
    db_query("INSERT INTO support_tickets (user_id, type, text, photo_id) VALUES (?, ?, ?, ?)",
             (user_id, ticket_type, txt, photo_id), commit=True)

    await update.message.reply_text("✅ تم إرسال الرسالة إلى الإدارة.")
    kb = [[InlineKeyboardButton("💬 رد على الرسالة", callback_data=f"reply_usr_{user_id}")]]
    try:
        title = "🚨 **بلاغ إصابة جديد**" if ticket_type == 'injury' else "💬 **رسالة دعم جديدة**"
        msg = f"{title}:\nالعميل: `{user_id}`\nالمحتوى: {txt}"
        if photo_id:
            await context.bot.send_photo(SUPER_ADMIN_ID, photo=photo_id, caption=msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(SUPER_ADMIN_ID, msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    except Exception: pass
    return ConversationHandler.END

# --- لوحة الإدارة الكاملة وباقي الوظائف ---
async def show_admin_panel(query):
    kb = [
        [InlineKeyboardButton("⚙️ صيانة البوت (تفعيل/إلغاء)", callback_data="adm_maint")],
        [InlineKeyboardButton("🔍 تفاصيل عميل", callback_data="adm_userdetails"), InlineKeyboardButton("📊 أرصدة وإحصائيات", callback_data="adm_stats")],
        [InlineKeyboardButton("➕ إضافة رصيد", callback_data="adm_addbal"), InlineKeyboardButton("➖ خصم رصيد", callback_data="adm_dedbal")],
        [InlineKeyboardButton("🎁 توليد كود هدية", callback_data="adm_gencode"), InlineKeyboardButton("📋 الأكواد النشطة", callback_data="adm_listcodes")],
        [InlineKeyboardButton("❌ إلغاء تفعيل كود", callback_data="adm_cancelcode"), InlineKeyboardButton("💳 إدارة طرق الشحن", callback_data="adm_methods")],
        [InlineKeyboardButton("🎁 البونص الترحيبي", callback_data="adm_welbonus"), InlineKeyboardButton("🎯 نسبة بونص الشحن", callback_data="adm_depbonus")],
        [InlineKeyboardButton("🎡 خوارزمية نسب العجلة", callback_data="adm_wheelprobs"), InlineKeyboardButton("📢 العروض الحالية", callback_data="adm_offers")],
        [InlineKeyboardButton("👥 قائمة الإحالات النشطة", callback_data="adm_reflist"), InlineKeyboardButton("📢 رسالة جماعية", callback_data="adm_bc")],
        [InlineKeyboardButton("✉️ رسالة خاصة", callback_data="adm_privmsg"), InlineKeyboardButton("🚫 حظر / فك حظر", callback_data="adm_ban_menu")],
        [InlineKeyboardButton("👑 إدارة الأدمنية", callback_data="adm_admins"), InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="adm_subchannel")],
        [InlineKeyboardButton("رجوع للرئيسية", callback_data="main_menu")]
    ]
    await query.message.edit_text("⚙️ **لوحة التحكم العليا للإدارة**", reply_markup=InlineKeyboardMarkup(kb))

async def handle_admin_callbacks(query, context, data):
    if data == "adm_maint":
        curr = db_query("SELECT value FROM settings WHERE key = 'maintenance'", fetchone=True)
        new_val = '0' if curr and curr['value'] == '1' else '1'
        db_query("UPDATE settings SET value = ? WHERE key = 'maintenance'", (new_val,), commit=True)
        await query.message.edit_text(f"وضع الصيانة الآن: {'مفعل ⚠️' if new_val == '1' else 'معطل ✅'}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="admin_panel")]]))

    elif data == "adm_userdetails":
        await query.message.edit_text("أدخل ID أو رقم العميل للبحث:")
        return ADMIN_USER_DETAILS_SEARCH

    elif data == "adm_stats":
        tot_u = db_query("SELECT COUNT(*) as c FROM users", fetchone=True)['c']
        tot_b = db_query("SELECT SUM(bot_balance) as s FROM users", fetchone=True)['s'] or 0.0
        tot_s = db_query("SELECT SUM(site_balance) as s FROM users", fetchone=True)['s'] or 0.0
        msg = f"📊 **إحصائيات وأرصدة اللاعبين:**\n\n👥 إجمالي المستخدمين: `{tot_u}`\n💰 إجمالي رصيد البوت: `{tot_b:.2f}` ل.س\n🌐 إجمالي رصيد الموقع: `{tot_s:.2f}` ل.س"
        await query.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="admin_panel")]]))

    elif data == "adm_addbal":
        await query.message.edit_text("أدخل معرف العميل (User ID) لإضافة رصيد له:")
        return ADMIN_ADD_BAL_USER

    elif data == "adm_dedbal":
        await query.message.edit_text("أدخل معرف العميل (User ID) لخصم رصيد منه:")
        return ADMIN_DEDUCT_BAL_USER

    elif data == "adm_gencode":
        await query.message.edit_text("أدخل قيمة الكود بالليرة السورية:")
        return ADMIN_GEN_CODE_VAL

    elif data == "adm_listcodes":
        codes = db_query("SELECT * FROM gift_codes WHERE active = 1", fetchall=True)
        txt = "📋 **الأكواد النشطة:**\n\n" + "\n".join([f"• `{c['code']}` | قيمة: {c['value']} ل.س | استخدام: {c['used_count']}/{c['max_uses']}" for c in codes]) if codes else "لا توجد أكواد نشطة."
        await query.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="admin_panel")]]))

    elif data == "adm_cancelcode":
        await query.message.edit_text("أدخل كود الهدية الذي تريد إلغاء تفعيله:")
        return ADMIN_CANCEL_CODE_INPUT

    elif data == "adm_methods":
        methods = db_query("SELECT * FROM payment_methods", fetchall=True)
        txt = "💳 **طرق الشحن الحالية:**\n\n" + "\n".join([f"• **{m['name']}**: {m['details']}" for m in methods])
        kb = [[InlineKeyboardButton("➕ إضافة طريقة شحن", callback_data="adm_addmethod")],
              [InlineKeyboardButton("❌ حذف طريقة شحن", callback_data="adm_delmethod")],
              [InlineKeyboardButton("رجوع", callback_data="admin_panel")]]
        await query.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_addmethod":
        await query.message.edit_text("أدخل اسم طريقة الشحن الجديدة (مثال: سيرياتيل كاش 2):")
        return ADMIN_METHOD_NAME

    elif data == "adm_delmethod":
        await query.message.edit_text("أدخل اسم طريقة الشحن المطلوبة للحذف:")
        return ADMIN_METHOD_DEL

    elif data == "adm_welbonus":
        await query.message.edit_text("أدخل قيمة البونص الترحيبي بالليرة السورية (أو 0 لإلغائه):")
        return ADMIN_WEL_BONUS

    elif data == "adm_depbonus":
        await query.message.edit_text("أدخل نسبة بونص الشحن المئوية % (مثال: 10):")
        return ADMIN_DEP_BONUS

    elif data == "adm_wheelprobs":
        await query.message.edit_text("أدخل قائمة الاحتمالات كمصفوفة JSON تضم 9 أرقام مجموعها 100:\nمثال: `[30.0, 25.0, 20.0, 10.0, 8.0, 5.0, 1.8, 0.19, 0.01]`")
        return ADMIN_WHEEL_PROBS

    elif data == "adm_offers":
        kb = [[InlineKeyboardButton("➕ إضافة عرض جديد", callback_data="adm_addoffer")], [InlineKeyboardButton("رجوع", callback_data="admin_panel")]]
        await query.message.edit_text("قسم إدارة العروض:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_addoffer":
        await query.message.edit_text("أدخل عنوان العرض الجديد:")
        return ADMIN_OFFER_TITLE

    elif data == "adm_reflist":
        users = db_query("SELECT user_id, full_name, active_referrals FROM users WHERE active_referrals > 0 ORDER BY active_referrals DESC", fetchall=True)
        txt = "👥 **قائمة الإحالات النشطة:**\n\n" + "\n".join([f"• {u['full_name']} (`{u['user_id']}`): {u['active_referrals']} إحالة نشطة" for u in users]) if users else "لا يوجد إحالات نشطة."
        await query.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="admin_panel")]]))

    elif data == "adm_bc":
        await query.message.edit_text("أدخل نص الرسالة الجماعية:")
        return ADMIN_BC_MSG

    elif data == "adm_privmsg":
        await query.message.edit_text("أدخل ID المستخدم لإرسال رسالة خاصة له:")
        return ADMIN_PRIV_USER

    elif data == "adm_ban_menu":
        kb = [[InlineKeyboardButton("🚫 حظر مستخدم", callback_data="adm_do_ban")], [InlineKeyboardButton("✅ فك حظر", callback_data="adm_do_unban")]]
        await query.message.edit_text("إدارة الحظر:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_do_ban":
        await query.message.edit_text("أدخل ID المستخدم لحظره:")
        return ADMIN_BAN_USER

    elif data == "adm_do_unban":
        await query.message.edit_text("أدخل ID المستخدم لفك حظره:")
        return ADMIN_UNBAN_USER

    elif data == "adm_admins":
        kb = [[InlineKeyboardButton("➕ إضافة أدمن", callback_data="adm_add_admin_start")], [InlineKeyboardButton("❌ إزالة أدمن", callback_data="adm_rem_admin_start")]]
        await query.message.edit_text("إدارة المسؤولين والأدمنية:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_add_admin_start":
        await query.message.edit_text("أدخل ID الأدمن الجديد:")
        return ADMIN_ADD_ADMIN_ID

    elif data == "adm_rem_admin_start":
        await query.message.edit_text("أدخل ID الأدمن لإزالته:")
        return ADMIN_REM_ADMIN_ID

    elif data == "adm_subchannel":
        await query.message.edit_text("أدخل معرف ورابط واسم القناة بالصيغة:\n`@ChannelUsername|رابط القناة|اسم القناة`")
        return ADMIN_SET_CHANNEL

    elif data.startswith("reply_usr_"):
        target_uid = data.replace("reply_usr_", "")
        context.user_data['reply_target'] = target_uid
        await query.message.edit_text(f"أدخل نص الرد الموجه للمستخدم `{target_uid}`:")
        return ADMIN_REPLY_TEXT

# --- دوال المعالجة المباشرة للأدمن ---
async def process_user_details_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inp = update.message.text.strip()
    user = db_query("SELECT * FROM users WHERE user_id = ? OR phone LIKE ?", (inp, f"%{inp}%"), fetchone=True)
    if not user:
        await update.message.reply_text("❌ لم يتم العثور على العميل.")
        return ConversationHandler.END

    uid = user['user_id']
    deps_cnt = db_query("SELECT COUNT(*) as c FROM transactions WHERE user_id = ? AND type='deposit' AND status='approved'", (uid,), fetchone=True)['c']
    codes_cnt = db_query("SELECT COUNT(*) as c FROM gift_code_logs WHERE user_id = ?", (uid,), fetchone=True)['c']
    
    msg = (
        f"📊 **تفاصيل العميل الشاملة:**\n\n"
        f"👤 الاسم: {user['full_name']}\n"
        f"🆔 ID الحساب: `{user['user_id']}`\n"
        f"📱 الرقم: `{user['phone']}`\n"
        f"🎮 حساب iChancy: `{user['ichancy_user'] or 'غير منشأ'}`\n"
        f"💰 رصيد البوت: `{user['bot_balance']:.2f}` ل.س\n"
        f"🌐 رصيد الموقع: `{user['site_balance']:.2f}` ل.س\n"
        f"📥 عدد الشحنات: `{deps_cnt}`\n"
        f"💵 إجمالي المشحون: `{user['total_deposited']:.2f}` ل.س\n"
        f"🎁 مرات استخدام الكود: `{codes_cnt}`\n"
        f"👥 عدد الإحالات النشطة: `{user['active_referrals']}`\n"
        f"🎡 لفات العجلة (المتبقية/المستخدمة): `{user['wheel_spins']}/{user['wheel_spins_done']}`\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_add_bal_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['target_user'] = update.message.text.strip()
    await update.message.reply_text("أدخل المبلغ المراد إضافته:")
    return ADMIN_ADD_BAL_AMT

async def process_admin_add_bal_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح للمبلغ.")
        return ADMIN_ADD_BAL_AMT

    uid = context.user_data.get('target_user')
    db_query("UPDATE users SET bot_balance = bot_balance + ? WHERE user_id = ?", (amt, uid), commit=True)
    await update.message.reply_text(f"✅ تم إضافة {amt} ل.س إلى رصيد المستخدم {uid}")
    try:
        await context.bot.send_message(uid, f"🎉 تمت إضافة `{amt}` ل.س إلى رصيدك من قبل الإدارة.", parse_mode="Markdown")
    except Exception: pass
    return ConversationHandler.END

async def process_admin_deduct_bal_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['target_user'] = update.message.text.strip()
    await update.message.reply_text("أدخل المبلغ المراد خصمه:")
    return ADMIN_DEDUCT_BAL_AMT

async def process_admin_deduct_bal_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح للمبلغ.")
        return ADMIN_DEDUCT_BAL_AMT

    uid = context.user_data.get('target_user')
    db_query("UPDATE users SET bot_balance = bot_balance - ? WHERE user_id = ?", (amt, uid), commit=True)
    await update.message.reply_text(f"✅ تم خصم {amt} ل.س من رصيد المستخدم {uid}")
    return ConversationHandler.END

async def process_admin_gen_code_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['code_val'] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل قيمة عددية صحيحة.")
        return ADMIN_GEN_CODE_VAL

    await update.message.reply_text("أدخل عدد مرات الاستخدام لكل كود:")
    return ADMIN_GEN_CODE_USES

async def process_admin_gen_code_uses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['code_uses'] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح لعدد المرات.")
        return ADMIN_GEN_CODE_USES

    await update.message.reply_text("كم عدد الأكواد المطلوب توليدها؟")
    return ADMIN_GEN_CODE_QTY

async def process_admin_gen_code_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح للكمية.")
        return ADMIN_GEN_CODE_QTY

    val = context.user_data.get('code_val', 1.0)
    uses = context.user_data.get('code_uses', 1)
    
    generated = []
    for _ in range(qty):
        code = f"GIFT-{random.randint(100000, 999999)}"
        db_query("INSERT INTO gift_codes (code, value, max_uses) VALUES (?, ?, ?)", (code, val, uses), commit=True)
        generated.append(code)

    txt = "✅ **تم توليد الأكواد بنجاح:**\n\n" + "\n".join([f"`{c}`" for c in generated])
    await update.message.reply_text(txt, parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_cancel_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    db_query("UPDATE gift_codes SET active = 0 WHERE code = ?", (code,), commit=True)
    await update.message.reply_text(f"✅ تم إلغاء تفعيل الكود `{code}`", parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_method_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['method_name'] = update.message.text.strip()
    await update.message.reply_text("أدخل تفاصيل وملاحظات طريقة الشحن (رقم الحساب/المحفظة):")
    return ADMIN_METHOD_DETAILS

async def process_admin_method_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    m_name = context.user_data.get('method_name')
    db_query("INSERT OR REPLACE INTO payment_methods (name, details) VALUES (?, ?)", (m_name, details), commit=True)
    await update.message.reply_text(f"✅ تم إضافة/تحديث طريقة الشحن ({m_name}).")
    return ConversationHandler.END

async def process_admin_method_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_name = update.message.text.strip()
    db_query("DELETE FROM payment_methods WHERE name = ?", (m_name,), commit=True)
    await update.message.reply_text(f"✅ تم حذف طريقة الشحن ({m_name}).")
    return ConversationHandler.END

async def process_admin_wel_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل قيمة عددية صحيحة.")
        return ADMIN_WEL_BONUS

    db_query("UPDATE settings SET value = ? WHERE key = 'welcome_bonus'", (str(val),), commit=True)
    await update.message.reply_text(f"✅ تم ضبط البونص الترحيبي على {val} ل.س.")
    return ConversationHandler.END

async def process_admin_dep_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ أدخل نسبة مئوية صحيحة.")
        return ADMIN_DEP_BONUS

    db_query("UPDATE settings SET value = ? WHERE key = 'deposit_bonus_pct'", (str(val),), commit=True)
    await update.message.reply_text(f"✅ تم ضبط نسبة بونص الشحن على {val}%.")
    return ConversationHandler.END

async def process_admin_wheel_probs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    probs_txt = update.message.text.strip()
    db_query("UPDATE settings SET value = ? WHERE key = 'wheel_prob'", (probs_txt,), commit=True)
    await update.message.reply_text("✅ تم تحديث نسب العجلة بنجاح.")
    return ConversationHandler.END

async def process_admin_offer_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['offer_title'] = update.message.text.strip()
    await update.message.reply_text("أدخل محتوى/تفاصيل العرض:")
    return ADMIN_OFFER_TEXT

async def process_admin_offer_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text.strip()
    title = context.user_data.get('offer_title')
    db_query("INSERT INTO offers (title, content) VALUES (?, ?)", (title, content), commit=True)
    await update.message.reply_text("✅ تم إضافه العرض بنجاح!")
    return ConversationHandler.END

async def process_admin_bc_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bc_text = update.message.text
    users = db_query("SELECT user_id FROM users", fetchall=True)
    success = 0
    for u in users:
        try:
            await context.bot.send_message(u['user_id'], bc_text)
            success += 1
            await asyncio.sleep(0.04)
        except Exception: pass
    await update.message.reply_text(f"✅ تم إرسال الرسالة الجماعية إلى {success} مستخدم.")
    return ConversationHandler.END

async def process_admin_priv_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['priv_target'] = update.message.text.strip()
    await update.message.reply_text("أدخل نص الرسالة الخاصة:")
    return ADMIN_PRIV_TEXT

async def process_admin_priv_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    uid = context.user_data.get('priv_target')
    try:
        await context.bot.send_message(uid, f"📩 **رسالة من الإدارة:**\n\n{txt}", parse_mode="Markdown")
        await update.message.reply_text("✅ تم إرسال الرسالة الخاصة بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل إرسال الرسالة: {e}")
    return ConversationHandler.END

async def process_admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    db_query("UPDATE users SET is_banned = 1 WHERE user_id = ?", (uid,), commit=True)
    await update.message.reply_text(f"🚫 تم حظر المستخدم {uid}")
    return ConversationHandler.END

async def process_admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    db_query("UPDATE users SET is_banned = 0 WHERE user_id = ?", (uid,), commit=True)
    await update.message.reply_text(f"✅ تم فك الحظر عن المستخدم {uid}")
    return ConversationHandler.END

async def process_admin_add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_admin_id'] = update.message.text.strip()
    kb = [
        [InlineKeyboardButton("كامل الصلاحيات (full)", callback_data="role_full")],
        [InlineKeyboardButton("ردود فقط (support)", callback_data="role_support")],
        [InlineKeyboardButton("محدود (limited)", callback_data="role_limited")]
    ]
    await update.message.reply_text("اختر نوع الصلاحيات للأدمن:", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_ADD_ADMIN_ROLE

async def process_admin_add_admin_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    role = query.data.replace("role_", "")
    aid = context.user_data.get('new_admin_id')
    db_query("INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, ?)", (aid, role), commit=True)
    await query.message.edit_text(f"✅ تم إضافة الأدمن {aid} بصلاحية ({role}).")
    return ConversationHandler.END

async def process_admin_rem_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    aid = update.message.text.strip()
    db_query("DELETE FROM admins WHERE user_id = ?", (aid,), commit=True)
    await update.message.reply_text(f"✅ تم إزالة الأدمن {aid}")
    return ConversationHandler.END

async def process_admin_subchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split("|")
    if len(parts) < 3:
        await update.message.reply_text("صيغة خاطئة! اكتب بالتنسيق:\n`@ChannelUsername|رابط القناة|اسم القناة`")
        return ADMIN_SET_CHANNEL

    ch_usr, ch_link, ch_name = parts[0].strip(), parts[1].strip(), parts[2].strip()
    db_query("UPDATE settings SET value = ? WHERE key = 'mandatory_channel'", (ch_usr,), commit=True)
    db_query("UPDATE settings SET value = ? WHERE key = 'channel_link'", (ch_link,), commit=True)
    db_query("UPDATE settings SET value = ? WHERE key = 'channel_name'", (ch_name,), commit=True)

    await update.message.reply_text("✅ تم إعداد القناة والتأكد من تفعيلها بنجاح!")
    return ConversationHandler.END

async def process_admin_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    target_uid = context.user_data.get('reply_target')
    try:
        await context.bot.send_message(target_uid, f"💬 **رد من الدعم الفني:**\n\n{txt}", parse_mode="Markdown")
        await update.message.reply_text("✅ تم إرسال الرد للعميل.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل إرسال الرد: {e}")
    return ConversationHandler.END

# --- تشغيل التطبيق الكامل ---
async def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(handle_callbacks)
        ],
        states={
            CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha)],
            PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, handle_phone)],
            ICHANCY_USER_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ichancy_user)],
            ICHANCY_PASS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ichancy_pass)],
            CHARGE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_charge_amt)],
            CHARGE_TX: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_charge_tx)],
            WITHDRAW_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_acc)],
            WITHDRAW_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_withdraw_amt)],
            SITE_DEP_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_site_dep_amt)],
            SITE_WITH_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_site_with_amt)],
            GIFT_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gift_code)],
            SUPPORT_INPUT: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, receive_support_or_injury)],
            INJURY_INPUT: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, receive_support_or_injury)],
            ADMIN_USER_DETAILS_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_details_search)],
            ADMIN_ADD_BAL_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_bal_user)],
            ADMIN_ADD_BAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_bal_amt)],
            ADMIN_DEDUCT_BAL_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_deduct_bal_user)],
            ADMIN_DEDUCT_BAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_deduct_bal_amt)],
            ADMIN_GEN_CODE_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_gen_code_val)],
            ADMIN_GEN_CODE_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_gen_code_uses)],
            ADMIN_GEN_CODE_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_gen_code_qty)],
            ADMIN_CANCEL_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_cancel_code)],
            ADMIN_METHOD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_method_name)],
            ADMIN_METHOD_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_method_details)],
            ADMIN_METHOD_DEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_method_del)],
            ADMIN_WEL_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_wel_bonus)],
            ADMIN_DEP_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_dep_bonus)],
            ADMIN_WHEEL_PROBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_wheel_probs)],
            ADMIN_OFFER_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_offer_title)],
            ADMIN_OFFER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_offer_text)],
            ADMIN_BC_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_bc_msg)],
            ADMIN_PRIV_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_priv_user)],
            ADMIN_PRIV_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_priv_text)],
            ADMIN_BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_ban_user)],
            ADMIN_UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_unban_user)],
            ADMIN_ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_admin_id)],
            ADMIN_ADD_ADMIN_ROLE: [CallbackQueryHandler(process_admin_add_admin_role)],
            ADMIN_REM_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_rem_admin_id)],
            ADMIN_SET_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_subchannel)],
            ADMIN_REPLY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_reply_text)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callbacks))

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

    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
