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

bot = telebot.TeleBot(TOKEN)

# هياكل بيانات لتتبع العقوبات المؤقتة في لعبة مين كفو
muted_5min_users = {}       # (chat_id, user_id) -> expire_time
name_penalties = {}         # (chat_id, user_id) -> {'target_name': str, 'expire_time': int}
embarrassing_penalties = {} # (chat_id, user_id) -> {'user_name': str, 'question': str, 'msg_id': int}

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
        CREATE TABLE IF NOT EXISTS saraha_questions (
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
        CREATE TABLE IF NOT EXISTS custom_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT,
            rules TEXT
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

    # إضافة أصناف المتجر والمطعم
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('علبة متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كيلو سكر', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('شاورما', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('برغر', 150)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('بيتزا', 200)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كباب', 250)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('عصير', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('متة', 50)")

    # 1. الأسئلة العامة
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        questions_list = [
            "لو كان بإمكانك إلغاء مادة دراسية واحدة من العالم تماماً، ماذا ستختار؟",
            "لو استيقظت غداً ووجدت نفسك الحيوان المفضّل لديك، فماذا ستفعل في أول ساعة؟",
            "لو أتيحت لك فرصة تسمية كوكب جديد، ما الاسم الذي ستختاره له؟",
            "لو كان بإمكانك تناول العشاء مع أي شخصية تاريخية، من ستختار؟",
            "لو تحولت الألوان إلى نكهات، ما هو طعم اللون الأزرق برأيك؟",
            "لو عُرض عليك مليون دولار مقابل عدم استخدام هاتفك لمدة شهر كامل، هل توافق؟",
            "لو كنت تستطيع تجميد الوقت لمدة ساعة كل يوم، كيف ستقضي هذه الساعة؟",
            "لو قمت بتأليف كتاب عن حياتك الآن، ما العنوان الرئيسي الذي ستضعه على الغلاف؟",
            "لو كان بإمكانك تجربة مهنة واحدة ليوم واحد فقط دون عواقب، ما هي؟",
            "لو عاد بك الزمن لتقديم نصيحة واحدة لنفسك وأنت بعمر 10 سنوات، ماذا ستقول؟",
            "ما هو أكثر تصرف غبي قمت به عندما كنت بمفردك في المنزل؟",
            "ما هي الكذبة البيضاء التي ما زلت تستخدمها حتى اليوم؟",
            "ما هو الشيء الذي كنت تخاف منه وأنت طفل واكتشفت الآن أنه سخيف؟",
            "ما هي أغرب أكلة جربتها في حياتك وأعجبتك ضد كل التوقعات؟",
            "هل سبق لك أن تظاهرت بالمرض للهروب من موعد أو مناسبة؟",
            "ما هي العادة الغريبة المضحكة التي تفعلها ولا يعرفها أحد عنك؟",
            "ما هو الموقف الذي كلما تذكرته تضحك من قلبك حتى لو كنت وحدك؟",
            "ما هو الشيء الذي اشتريته وندمت عليه فوراً لأنه كان بلا فائدة؟",
            "هل تعتقد أنك تستطيع البقاء حياً في جزيرة مهجورة؟",
            "كم يوماً ستصمد؟",
            "ما هي الأغنية التي تحبها سراً وتستحي أن تشاركها مع الآخرين؟",
            "ما هي الصفة التي تمنيت لو أنها موجودة في كل البشر؟",
            "ما هو أكثر درس قاسم تعلمته من الحياة حتى الآن؟",
            "إذا كان بإمكانك تغيير شيء واحد في العالم، ماذا سيكون؟",
            "ما الذي يجعلك تشعر بالأمان والراحة النفسية فوراً؟",
            "ما هو التطبيق على هاتفك الذي لا يمكنك العيش بدونه مطلقاً؟",
            "ما هي الكلمة أو العبارة التي تكررها كثيراً في كلامك اليومي؟",
            "كيف تبدو \"الجنّة الشخصية\" أو اليوم المثالي بالنسبة لك؟",
            "ما هو أكثر شيء يثير فضولك في هذا الكون؟",
            "لو كان بإمكانك امتلاك موهبة فنية فورية (رسم، غناء، تمثيل.رقص.اكل بلا سمنة)، ماذا تختار؟",
            "ما هو الإنجاز الصغير الذي حققته مؤخراً وتفتخر به؟",
            "الصيف الصاخب أم الشتاء الهادئ؟",
            "طلعة برية في الطبيعة أم سهرة في مقهى فاخر؟",
            "قراءة كتاب ورقي أم مشاهدة فيلم سينمائي؟",
            "الاستيقاظ مبكراً جداً أم السهر حتى الفجر؟",
            "السفر مع مجموعة كبيرة أم السفر بمفردك أو مع شخص واحد؟",
            "الطعام الحار (السبايسي) أم الطعام الحالي والحلويات؟",
            "التخطيط الدقيق لكل شيء أم ترك الأمور للعفوية والارتجال؟",
            "العيش في مدينة ساحلية أم العيش في مدينة جبلية؟",
            "قيادة السيارة بسرعة أم الاستمتاع بالطريق بهدوء؟",
            "امتلاك الكثير من الوقت أم امتلاك الكثير من المال؟",
            "مجدرة ولا شيبس؟",
            "شاورما ولا سكالوب؟",
            "بيتزا ولا برغر؟",
            "بتحبني ولا بتحبني؟",
            "لو خيروك بين السفر إلى المستقبل أو العودة إلى الماضي، أيهما تختار ولماذا؟",
            "ما هي القوة الخارقة التي تتمنى امتلاكها لو كنت بطلاً خارقاً؟",
            "إذا أتيحت لك فرصة تغيير اسمك، ما الاسم الذي ستختاره؟",
            "ما هو الموقف الأكثر إحراجاً الذي تعرضت له أمام جمهور أو أقاربك؟",
            "لو عثرت على حقيبة ملئية بالمال في الشارع، ما هو أول تصرف تفكر فيه؟",
            "ما هو القرار الأفضل الذي اتخذته في حياتك حتى الآن؟"
        ]
        for q in questions_list:
            cursor.execute("INSERT INTO questions (question) VALUES (?)", (q,))

    # 2. أسئلة صراحة الجريئة والموسعة لمنع التكرار
    cursor.execute("SELECT COUNT(*) FROM saraha_questions")
    if cursor.fetchone()[0] < 20:
        saraha_list = [
            "ما هي أكبر غلطة ارتكبتها بحق شخص وما زلت نادماً عليها؟",
            "هل سبق لك أن راقبت حساب شخص بعد الفراق أو الخصام؟",
            "ما هي الصفة التي تكرها في نفسك وتتمنى تغييرها فوراً؟",
            "هل تفضل العقل أم العاطفة في اتخاذ قراراتك المصيرية؟",
            "ما هو السر الذي لم تقله لأقرب شخص إليك حتى اليوم؟",
            "هل اعتذرت يوماً لشخص رغم أنك تدرك أنك لست المخطئ فقط لكي لا تخسره؟",
            "ما هو التصرف الذي يقضي على ثقتك بالشخص الآخر فوراً؟",
            "هل شعرت يوماً بالغيرة الشديدة من نجاح أحد أصدقائك؟",
            "ما هو القرار الذي اتخذته بناءً على عاطفتك وندمت عليه لاحقاً؟",
            "هل تعتقد أن الحب الأول ينتهي أم يظل محفوراً في الذاكرة؟",
            "ما هي الكلمة التي قيلت لك وجرحتك عميقاً ولم تنسَها أبداً؟",
            "هل تجيد المسامحة بسهولة أم أنك تحتفظ بالزعل لفترة طويلة؟",
            "ما هو الشيء الذي تفعله عندما تكون حزيناً جداً ولا يعرفه أحد؟",
            "هل تظاهرت يوماً بالقوة بينما كنت مكسوراً من الداخل؟",
            "ما هو الاختبار الأكثر صعوبة الذي مرت به شخصيتك؟",
            "ما هو الموقف الأكثر إحراجاً الذي تعرضت له أمام شخص تحبه؟",
            "هل سبق لك أن قرأت محادثات شخص آخر بالخفية ودون علمه؟",
            "ما هي الكذبة الكبيرة التي ما زلت تخفيها عن عائلتك؟",
            "هل سبق لك أن تظاهرت بالنوم للهروب من حديث محرج مع أحدهم؟",
            "ما هي العادة الغريبة أو المحرجة التي تفعلها عندما تكون بمفردك؟",
            "ما هو الشيء الذي اشتريته بسعر مرتفع جداً وكان يمثل قمة الغباء؟",
            "هل حظرت شخصاً في هذا الجروب أو على مواقع التواصل من قبل؟ ولماذا؟",
            "ما هو أغلظ مقلب أكلته بحياتك ومن كان صاحبه؟",
            "هل سبق لك أن أكلت طعام شخص آخر بالسر وأنكرت ذلك؟",
            "ما هو الشيء الذي تحسد غيرك عليه ولكنك تبتسم وتتظاهر بالعكس؟",
            "ما هو الاسم المستعار الغريب والمحرج الذي كنت تستخدمه في الماضي؟",
            "هل تحب أو تعجب بشخص موجود معنا في هذا الجروب حالياً؟",
            "لو طلبنا منك إظهار آخر محادثة على واتساب، هل تتجرأ؟",
            "ما هو أكثر موقف شعرت فيه بالخجل الشديد وتمنيت لو الأرض ابتلعتك؟",
            "هل سبق لك أن أرسلت رسالة عتاب أو حب بالخطأ للشخص نفسه؟",
            "ما هو الشيء الذي لو عرفه الناس عنك ستتغير نظرتهم لك تماماً؟",
            "ما هي أسرع طريقة تجعل دموعك تنزل فوراً؟",
            "هل سبق لك أن تظاهرت بالمرض للهروب من امتحان أو عمل؟",
            "ما هو المبلغ المالي الأكبر الذي خسرته في تجربة أو لعبة وندمت عليه؟",
            "هل تعتقد أن هناك شخصاً يكرهك بشدة في هذه اللحظة؟ من هو برأيك؟"
        ]
        for sq in saraha_list:
            cursor.execute("INSERT INTO saraha_questions (question) VALUES (?)", (sq,))

    # 3. 50 حزورة منطقية
    cursor.execute("DELETE FROM riddles")
    new_riddles_list = [
        ("ما هو الشيء الذي يتكلم كل لغات العالم بدون أن ينطق كلمة؟", "الصدى"),
        ("ما هو الشيء الذي كُلما أخذت منه كَبُر وزاد حجمه؟", "الحفرة"),
        ("شيء يحملك وتحمله في نفس الوقت أينما ذهبت، ما هو؟", "الحذاء"),
        ("ما هو الشيء الذي ينزل من السماء ولا يصعد إليها أبداً؟", "المطر"),
        ("له أوراق كثيرة ولكنه ليس بنبات، وله جلد وليس بليوم حيوان، ما هو؟", "الكتاب"),
        ("يمشي بدون رجلين، ويبكي بدون عينين، فما هو؟", "السحاب"),
        ("ما هو الشيء الذي كلما زاد نقص؟", "العمر"),
        ("ما هو البيت الذي لا يحتوي على أبواب ولا نوافذ ولا غرف؟", "بيت الشعر"),
        ("شيء يكتب ولا يستطيع القراءة، ما هو؟", "القلم"),
        ("ما هو الشيء الذي يُقرصك دون أن تراه أو تلمسه؟", "الجوع"),
        ("له أسرار كبرى وتراه في السماء والماء، وهو موجود بين الأرض والسماء، ما هو؟", "حرف الواو"),
        ("أين يقع البحر الذي لا توجد فيه نقطة ماء واحدة؟", "على الخريطة"),
        ("ما هو الشيء الذي إذا صببت عليه الماء لا يبتل؟", "الضوء"),
        ("شيء يملك رقبة ولكنه بلا رأس، ما هو؟", "الزجاجة"),
        ("ما هو الشيء الذي لا يستفاد منه إلا بعد كسره؟", "البيض"),
        ("كائن يرى كل شيء حوله ولكنه لا يملك عيوناً، ما هو؟", "المرآة"),
        ("ما هو الشيء الذي يستطيع ملء الغرفة كاملة دون أن يشغل أي مساحة؟", "النور"),
        ("شيء يمر عبر المدن والقرى والجبال ولكنه لا يتحرك أبداً، ما هو؟", "الطريق"),
        ("ما هو القفص الذي لا يستطيع الحفاظ على طائر أو حيوان بداخله؟", "القفص الصدري"),
        ("شيء يطوف حول الحديقة بأكملها دون أن يقفز أو يتحرك، ما هو؟", "السور"),
        ("ما هو الشيء الذي يملك أسنان كثيرة ولكنه لا يعض أبداً؟", "المشط"),
        ("من هو الشخص الذي يرى عدوه وصديقه بعين واحدة فقط؟", "الأعور"),
        ("شيء إذا أطعمته كبر وقوي، وإذا سقيته ماءً مات؟", "النار"),
        ("ما هو الشيء الذي يملك مفاتيح كثيرة جداً ولكنه لا يفتح أي باب؟", "البيانو"),
        ("إذا دخل الماء لم يبتل، وإذا قطعته لا ينزل منه دم، ما هو؟", "الظل"),
        ("أخضر في حقلها، وأسود في السوق، وأحمر في بيتك، ما هو؟", "الشاي"),
        ("شيء ينبض باستمرار دون أن يملك قلباً، ما هو؟", "الساعة"),
        ("ما هو الشيء الذي يحوي أرقاماً كثيرة ولكنه لا يحسب ولا يفكر؟", "التقويم"),
        ("ما هو الشيء الذي يكون أمامك دائماً ولكنك لا تستطيع رؤيته؟", "المستقبل"),
        ("ما هي العروس التي تزف بلا عريس؟", "الدمية"),
        ("ما هو الشيء الذي ترميه في البحر كلما احتجت إليه؟", "شبكة الصيد"),
        ("ابن أمك وابن أبيك، وليس بأخيك ولا بأختك، فمن يكون؟", "أنت"),
        ("ما هو الشيء الذي إذا غليته على النار يتجمد بدلاً من أن يذوب؟", "البيض"),
        ("شيء يملك أربعة أرجل في الصباح ولا يستطيع المشي أبداً، ما هو؟", "الطاولة"),
        ("ما هو الشيء الذي تجده في وسط باريس؟", "حرف ر"),
        ("شيء أوله عين وأخيره سن، فما هو؟", "العنب"),
        ("ما هو الشيء الذي يستطيع الثقب والعبور من الزجاج دون أن يكسره؟", "الضوء"),
        ("ما هو الشجر الذي ليس له ثمر ولا يملك ظلاً؟", "شجرة العائلة"),
        ("شيء يخرج من الماء ويموت فور دخوله الماء، ما هو؟", "الملح"),
        ("ما هو الشيء الذي تسمعه وتراه ولكنك لا تتكلم معه إلا بإذن؟", " التلفاز"),
        ("ما هو الشيء الذي يقف وينزل دون أن يتحرك خطوة واحدة؟", "درجة الحرارة"),
        ("إذا أردت استخدامه رميته، وإذا انتهيت منه جمعته، ما هو؟", "المرساة"),
        ("ما هو الشيء الذي يربيه الأب وتذبحه الأم ويبكي عليه الجميع؟", "البصل"),
        ("شيء يملك عين واحدة ولكنه لا يرى بها أبداً، ما هو؟", "الإبرة"),
        ("ما هو الصندوق الذي يملك أقفالاً موسيقية؟", "البيانو"),
        ("شيء يمشي بلا أرجل ولا يدخل إلا بالاستئذان، ما هو؟", "الصوت"),
        ("ما هو الشيء الذي يتبعك طوال النهار ويختفي في الليل تماماً؟", "الظل"),
        ("ما هو الشيء الذي يمكنك إمساكه بيدك اليمنى ولا تستطيع إمساكه بيدك اليسرى؟", "كوعك الأيسر"),
        ("ما هو الشيء الذي يصبح أطول عندما يكون صغيراً وأقصر عندما يكبر؟", "الشمعة"),
        ("شيء يطير بلا أجنحة ويبكي بلا عيون، ما هو؟", "السحاب")
    ]
    for rq, ra in new_riddles_list:
        cursor.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (rq, ra))

    # 4. إدخال الردود المخصصة
    extra_replies = [
        ("بحبك", "وانا بحبك قد المتة والبحيرة! ❤️😍"),
        ("بحبك", "لك يسلملي ربك وانا بعشقك يا عسل! 🥰"),
        ("بحبك", "بحبك الحب كلو بس لا تطلب مني مصاري 😂💔"),
        ("بحبك", "لك تقبر قلبي الهي! عيون فرفوش إلك ❤️"),
        ("بحبك", "يا عيني على الكلام الحلو! خجلتني والرب 🙈"),
        ("بكرهك", "ليش يا غالي شو عملتلك؟ بتضل على راسي والله! 🥹❤️"),
        ("بكرهك", "تكرهني؟ لك انا يلي شغال ليل نهار كرمالك! 💔😭"),
        ("بكرهك", "ما بني شي بس انكسر خاطري صراحة 😔"),
        ("بكرهك", "حتى لو كرهتني، فرفوش بيحبك غصباً عنك! 😘💃"),
        ("بتحبني", "بحبك وبموت عليك وعلى عيونك كمان! ❤️"),
        ("بتحبني", "يعني بالله عليك في بوت بيقدر ما يحب أحلى عضو بالجروب؟ 😍"),
        ("بتحبني", "أكيد بحبك، بس القعدة معك بدها كاسة متة مظبوطة! ☕✨"),
        ("بتحبني", "اي بحبك، بس لا تعيدها قدام المدام للفضايح 😂"),
        ("صباح الخير", "صباح النور… نورك مغطي عالصبح كله 😏"),
        ("مرحبا", "مرحبتين، وحدة إلك ووحدة لعيونك 😏❤️"),
        ("تصبحو على خير", "تصبحوا على خير، وإذا حدا حلم فيني بدي نسبة من الأرباح 😂"),
        ("بوت", "ولك أنا عم اشتغل بلا راتب🌝"),
        ("بوت", "قول اسمي مطوريني تعبو لساووني 😡 @syabd0 . @Lolo123000"),
        ("بوت", "اسمي فرفوووش"),
        ("بوت", "بوت بعينك اسمي فرفوش"),
        ("قولا مرة تانية ورباح خلاط 😡", "خلاط ممتاز 😂"),
        ("كيفك", "رميها على الله 😔"),
        ("كيفك", "بخير بشوفتك 🌝"),
        ("كيفك", "منيح تروح ناكل؟"),
        ("كيفك", "خزان احزان ياباشا 🥺"),
        ("The Kurdish", "عم ينادي لعسل لكروب 🌝"),
        ("The Kurdish", "ارجل زلمة ♥️"),
        ("The Kurdish", "هاد اللقب اسمو سري للغاية 🫣"),
        ("فرانكو", "رد عليه يامدمرني 🥺"),
        ("فرانكو", "فرانكو عسل عل قلب 🤍"),
        ("فرانكو", "فرانكو الدهبب 💛"),
        (".", "https://t.me/goldennlera"),
        ("ا", "https://t.me/lerafree"),
        ("قانون", "عزيزي العضو بكروبنا قوانين كروبنا ممنوع الحكي بسياسة ممنوع تطلب من حدا رصيد كاش عل عام وبس صار قوانين جديدة بخبركن 🌝 تسلمولي 🫶♥️"),
        ("هات القهوة ياغلام", "يلا حاضر"),
        ("..", "شو بدك من مطوريني @syabd0 @Lolo123000"),
        ("بعتلي صورتك", "لسا مارتحتلك 🌝"),
        ("بعتلي صورتك", "شو بتعطيني اذا بعتا"),
        ("بعتلي صورتك", "بفكر بالموضوع"),
        ("ملل فتحلنا سيرة", "شو طبختو اليوم؟"),
        ("ملل فتحلنا سيرة", "برايك انو احلا منطقة حلوة بسوريا من ناحية الطبيعة؟"),
        ("ملل فتحلنا سيرة", "شو اكتر موقع فاتح هي لفترة وعم يعطي؟"),
        ("ملل فتحلنا سيرة", "شو عملت ليوم وين رحت وين جيت؟"),
        ("ملل فتحلنا سيرة", "برايك انو اطيب متة خارطة بيضا ولا لخضرا ولا لمتة لحمرا ولا شو برايك في انواع جديدة مامنعرفا؟"),
        ("ملل فتحلنا سيرة", "شو اكبر مبلغ ربحتو بمسيرتك القمارية؟"),
        ("ملل فتحلنا سيرة", "بتندم لانك تعلمت عل مواقع ولا لا مبسوط؟"),
        ("ملل فتحلنا سيرة", "احكولنا كم مرة انتصب عليكن وشو كانت طريقة"),
        ("ملل فتحلنا سيرة", "احكولنا عن اكتر موقف نصب مضحك ومابتصدق شفتو"),
        ("زوجني", "لزوج حالي اول 😒"),
        ("زوجني", "روح عند امك تزوجك شو شايفني دلالة 🌝"),
        ("زوجني", "خليك عزابي ولاك 😁"),
        ("زوجني", "بنصحك لاتتورط بل زواج فخ 🌝"),
        ("زوجني", "حل عني 😠"),
        ("نسونجي", "اخرس ولا"),
        ("نسونجي", "فشرت 🌝"),
        ("نسونجي", "خود خمسة واسكت 😒"),
        ("هات", "عم تصحلي امي باي 🌝"),
        ("هات", "صدقت 😳"),
        ("هات", "فرفوش ماهون 🫣"),
        ("فرفوشتي", "نعم حبيبتي"),
        ("فرفوش", "عيون فرفوش الروق كله! 😍"),
        ("فرفوش", "فرفوش بالخدمة والروق والسعادة! ✨"),
        ("فرفوش", "لبيه يا عيون فرفوش 😘"),
        ("فرفوشي", "يا عيون فرفوشي أنت! ❤️"),
        ("فرفوشي", "روح قلب فرفوشي من جوة 🫣"),
        ("فرفوشتي", "نعم يا روح فرفوشتك! 🌸"),
        ("فرفوشتي", "لك أهلاً وسهلاً بفرفوشتي الغالي ❤️"),
        ("فرفشني", "تفضل هي نكتة وفرفشة لعيونك! 🕺"),
        ("فرفشني", "من عيوني الهنتين.. أحلى فرفشة لعيونك يا غالي ✨"),
        ("باي", "الله معك يا غالي، بشوفك بخير! 👋"),
        ("باي", "باي يا حلو، لا تطول علينا! 🌸"),
        ("سلام", "وعليكم السلام ورحمة الله وبركاته، نورت يا حباب! ❤️"),
        ("سلام", "سلامات يا طيب، أهلاً وسهلاً بك! ✨")
    ]
    for kw, resp in extra_replies:
        cursor.execute("SELECT 1 FROM custom_replies WHERE keyword = ? AND response = ?", (kw, resp))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO custom_replies (keyword, response, media_type) VALUES (?, ?, 'text')", (kw, resp))

    # 5. قصص الجرائم
    cursor.execute("SELECT COUNT(*) FROM crime_stories")
    if cursor.fetchone()[0] < 2:
        crimes_list = [
            ("في ليلة ممطرة، وُجد رجل الأعمال 'سليم' مقتولاً في مكتبه. المحاسب (فادي) يدعي أنه كان يراجع الأوراق، السكرتيرة (مريم) تقول أنها كانت تعد القهوة، والحارس (سامر) يقول أنه كان يقف عند الباب وشاهد شخصاً يرتدي معطفاً خردلياً.", "فادي", "فادي، مريم، سامر"),
            ("اختفت قلادة الماسية من الخزنة. الخادم (رامي) يقول أنه كان ينظف المطبخ، والطباخ (شادي) يقول أنه كان يقطع الخضار، والسائق (ماهر) يدعي أنه كان يغسل السيارة تحت المطر.", "ماهر", "رامي، شادي، ماهر")
        ]
        for st, kl, sp in crimes_list:
            cursor.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (st, kl, sp))

    # 6. أسئلة المسلسلات
    cursor.execute("SELECT COUNT(*) FROM series_questions")
    if cursor.fetchone()[0] == 0:
        series_list = [
            ("مسلسل شامي شهير فيه شخصية 'أبو عصام' و'عكيد الحارة' ما هو؟", "باب الحارة"),
            ("مسلسل كوميدي سوري عن ضيعة مفترضة اسمها 'أم الطنافس الفوقا'؟", "ضيعة ضايعة"),
            ("مسلسل درامي فيه شخصية 'جبل شيخ الجبل'؟", "الهيبة"),
            ("مسلسل تاريخي شهير يتناول قصة فتح الأندلس؟", "صقر قريش"),
            ("مسلسل كوميدي شهير من بطولة ياسر العظمة ينتهي بكلمات ناقدة وساخرة؟", "مرايا")
        ]
        for sq, sa in series_list:
            cursor.execute("INSERT INTO series_questions (question, answer) VALUES (?, ?)", (sq, sa))

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
min_kafo_games = {}  # لعبة مين كفو

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

# ==================== نظام جيمني المطورالانشاء الدقيق ====================
def fetch_ai_answer(question):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ar,en;q=0.9"
    }

    sys_prompt = "أنت مساعد ذكي واسمك فرفوش، تعمل بنظام Gemini المتطور وتفهم اللهجة السورية والعربية بدقة. أجب عن سؤال المستخدم بشكل دقيق ومباشر ومنطقي جداً بناءً على ما طلبه حصراً دون تعذر. يمنع منعاً باتاً ذكر أي روابط أو خروج عن موضوع السؤال أو ذكر أي مصادر."

    models_chain = ["gemini", "gemini-thinking", "openai", "deepseek", "qwen"]

    for model in models_chain:
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": question}
                ],
                "model": model,
                "seed": random.randint(1, 99999)
            }
            res = requests.post("https://text.pollinations.ai/", json=payload, headers={**headers, "Content-Type": "application/json"}, timeout=10)
            if res.status_code == 200 and res.text:
                ans = clean_urls_and_sources(res.text)
                if ans and len(ans) > 5 and not any(bad in ans.lower() for bad in ["timed out", "error", "504", "403"]):
                    return ans
        except Exception:
            continue

    return "أهلاً بك يا غالي! أعتذر عن التأخير البسيط. تفضل بتكرار سؤالك وسأجيبك فوراً بدقة عالية."

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
        "🤖 **ذكاء اصطناعي (جيمني الأصلي):** اكتب `عندي سؤال` أو `بدي ساوي صورة [وصف]`.\n"
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

    # 1. تطبيق عقوبة الكتم لمدة 5 دقائق (للأعضاء والمشرفين)
    if key in muted_5min_users:
        if curr_t < muted_5min_users[key]:
            safe_delete_message(chat_id, message.message_id)
            return
        else:
            del muted_5min_users[key]

    # 2. تطبيق عقوبة تغيير الاسم (يتعرف البوت تلقائياً دون الحاجة للكتابة)
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

    # 3. تطبيق عقوبة السؤال المحرج (يطلب الإجابة بالرد أو الكتابة)
    if key in embarrassing_penalties:
        p_data = embarrassing_penalties[key]
        is_game_cmd = text in ["مين كفو", "مين كفو؟", "انا", "أنا", "بلشها", "بلش"]
        # إذا أرسل المعاقب نصاً وليس أمراً للعب يعتبر إجابة
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

    # زر ميزة إسكات البوت أو كتم البوت في المجموعات
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

    # معالجة مدخلات أدمن الردود المخصصة المتعددة
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

    # ==================== لعبة "مين كفو" المحدثة والآمنة ====================
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
                embarrassing_qs = [
                    "ما هو أكثر موقف محرج تعرضت له أمام شخص تحبه أو تحترمه؟",
                    "ما هي أكبر كذبة كذبتها على أعضاء هذا الجروب أو على أهلك؟",
                    "ما هو السر الذي تخفيه عن الجميع وتخاف أن ينكشف يوماً ما؟",
                    "لو طلبنا منك فتح الاستوديو وإرسال الصورة رقم 5 عندك بالهاتف، هل تجرؤ؟",
                    "ما هي أكثر صفة سيئة فيك وتتمنى أن تتخلص منها فوراً؟",
                    "هل سبق لك أن راقبت حساب شخص في الجروب بالسر وبشكل متكرر؟ من هو؟",
                    "ما هو التصرف الغريب أو الغبي الذي تفعله عندما تكون وحدك تماماً؟",
                    "هل سبق أن تظاهرت بالحب أو الصداقة مع شخص وأنت تبغضه بالداخل؟"
                ]
                chosen_q = random.choice(embarrassing_qs)
                q_msg = bot.send_message(
                    chat_id,
                    f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n"
                    f"وقع الاختيار على المعاقب: **[{victim_name}](tg://user?id={victim_id})** 🎯\n\n"
                    f"😳 **العقوبة (سؤال محرج جداً):**\n"
                    f"❓ `{chosen_q}`\n\n"
                    f"⚠️ **تنبيه:** لن يتم السماح لك باللعب أو الكتابة إلا بعد إرسال الجواب بالرد على هذا السؤال! كل ما تكتب شيء سيُقال لك جاوب حتى تجاوب!",
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
                    f"🔥 **[{victim_name}](tg://user?id={victim_id})** الحكم فكاهي وناقد: اعترف مين أكثر عضو بتموت منه بالجروب وبدون مجاملة! 🤫",
                    f"🎭 **[{victim_name}](tg://user?id={victim_id})** حكم القدر: أرسل بصمة صوت وأنت عم تغني أغنية للأطفال وشوف تقييم الجروب إلك 🎤"
                ]
                bot.send_message(chat_id, f"🔥 **صدور الحكم في تحدي مين كفو!** 🔥\n\n{random.choice(funny_judgments)}", parse_mode="Markdown")

            del min_kafo_games[chat_id]
            return

    # ==================== نظام وأسئلة "صراحة" ====================
    if text in ["صراحة", "صراحه", "اسئلة صراحة", "سؤال صراحة"]:
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT question FROM saraha_questions ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row:
            bot.send_message(chat_id, f"😳 **سؤال صراحة (جريء ومباشر):**\n\n{row[0]}\n\n💬 أتحفنا بإجابتك بكل صراحة وبدون هروب!", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "لا توجد أسئلة صراحة مضافة حالياً.")
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
                f"❌ فتشت بجيوب {target_user.first_name} لقيتها فاضية ما فيها ولا قطعة ({item_req})!"
            ]
            bot.reply_to(message, random.choice(funny_food_fail))
        conn.close()
        return

    # الردود التلقائية
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

    # جيمني الاصلي
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

    # الألعاب
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

            is_won = random.choices([True, False], weights=[50, 50])[0]
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
                f"🎡 روق المانجا شوي! فاضل `{remaining_secs}` ثانية ⏱️",
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

        is_win = random.choices([True, False], weights=[50, 50])[0]
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

            is_success = random.choices([True, False], weights=[90, 10])[0]
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

        try:
            bot.answer_callback_query(call.id)
        except:
            pass

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
        bot.edit_message_text(f"🎮 بدأت مباراة XO المجانية!\n❌ {p1_name}\n⭕ {p2_name}\n\n🎁 الفائز سيحصل على 100 ليرة وهمية!\nالدور الحالي: {p1_name} (❌)", chat_id, msg_id, reply_markup=get_xo_keyboard(xo_games[msg_id]))
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

        try:
            bot.answer_callback_query(call.id)
        except:
            pass

        game['board'][idx] = game['symbols'][user_id]
        
        wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
        winner = None
        for a, b, c in wins:
            if game['board'][a] == game['board'][b] == game['board'][c] != " ":
                winner = user_id
                break

        if winner:
            update_balance(winner, 100)
            bot.edit_message_text(f"🎉 الفائز باللعبة هو {call.from_user.first_name}! وربح **100 ليرة وهمية**! 🏆", chat_id, msg_id, reply_markup=get_xo_keyboard(game), parse_mode="Markdown")
            del xo_games[msg_id]
        elif " " not in game['board']:
            bot.edit_message_text("🤝 تعادل بين الطرفين!", chat_id, msg_id, reply_markup=get_xo_keyboard(game), parse_mode="Markdown")
            del xo_games[msg_id]
        else:
            game['turn'] = game['player2'] if user_id == game['player1'] else game['player1']
            next_name = game['p2_name'] if game['turn'] == game['player2'] else game['p1_name']
            next_sym = game['symbols'][game['turn']]
            bot.edit_message_text(f"🎮 المباراة مستمرة بين:\n❌ {game['p1_name']}\n⭕ {game['p2_name']}\n\nالدور الحالي: {next_name} ({next_sym})", chat_id, msg_id, reply_markup=get_xo_keyboard(game))

# ==================== معالجة مدخلات الأدمن لوحة التحكم ====================
def handle_admin_inputs(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    state = admin_states.get(user_id)
    text = (message.text or "").strip()

    if isinstance(state, dict):
        st_name = state.get('state')
        if st_name == 'wait_custom_game_rules':
            game_name = state.get('name')
            rules = text
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO custom_games (game_name, rules) VALUES (?, ?)", (game_name, rules))
            conn.commit()
            conn.close()
            del admin_states[user_id]
            bot.reply_to(message, f"✅ **تم إضافة اللعبة بنجاح!**\n\n🎮 **الاسم:** {game_name}\n📜 **القوانين:** {rules}", parse_mode="Markdown")
            return

        elif st_name == 'wait_custom_grp_msg':
            target_chat_id = state.get('target_chat_id')
            try:
                if message.photo:
                    bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption)
                elif message.video:
                    bot.send_video(target_chat_id, message.video.file_id, caption=message.caption)
                elif message.sticker:
                    bot.send_sticker(target_chat_id, message.sticker.file_id)
                else:
                    bot.send_message(target_chat_id, text)
                bot.reply_to(message, f"✅ تم إرسال الرسالة إلى المجموعة `{target_chat_id}` بنجاح!", parse_mode="Markdown")
            except Exception as e:
                bot.reply_to(message, f"❌ فشل إرسال الرسالة: {e}")
            del admin_states[user_id]
            return

        elif st_name == 'wait_fake_bal_amount':
            target_u_id = state.get('target_user_id')
            if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
                amt = int(text)
                update_balance(target_u_id, amt)
                bot.reply_to(message, f"✅ تم تعديل رصيد المستخدم `{target_u_id}` بمبلغ {amt} ليرة بنجاح!", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ يرجى إدخال رقم صحيح.")
            del admin_states[user_id]
            return

    if state == "wait_custom_game_name":
        admin_states[user_id] = {'state': 'wait_custom_game_rules', 'name': text}
        bot.reply_to(message, f"📜 ممتاز! اسم اللعبة: **{text}**\n\nالان أرسل **القوانين والشرح** لهذه اللعبة:", parse_mode="Markdown")
        return

    elif state == "wait_add_admin_id":
        if text.isdigit():
            new_admin_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (new_admin_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم إضافة الأدمن `{new_admin_id}` بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ ID غير صالح.")
        del admin_states[user_id]
        return

    elif state == "wait_fake_bal_userid":
        if text.isdigit():
            target_u_id = int(text)
            admin_states[user_id] = {'state': 'wait_fake_bal_amount', 'target_user_id': target_u_id}
            bot.reply_to(message, f"أرسل الآن المبلغ الوهمي المراد إضافته (أو خصمه برقم سالب) للمستخدم `{target_u_id}`:", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ ID غير صالح.")
            del admin_states[user_id]
        return

    elif state == "wait_add_store_item":
        parts = text.split("-")
        if len(parts) == 2 and parts[1].strip().isdigit():
            i_name, i_price = parts[0].strip(), int(parts[1].strip())
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO store VALUES (?, ?)", (i_name, i_price))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم إضافة `{i_name}` بسعر {i_price} ليرة بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ تنسيق خاطئ. التنسيق المطلوب: `اسم الصنف - السعر`", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_del_store_item":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM store WHERE item_name LIKE ?", (f"%{text}%",))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"🗑️ تم حذف الصنف `{text}` إذا كان موجوداً.", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_add_crime":
        parts = text.split("|")
        if len(parts) == 3:
            st, kl, sp = parts[0].strip(), parts[1].strip(), parts[2].strip()
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (st, kl, sp))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة القصة بنجاح!")
        else:
            bot.reply_to(message, "❌ التنسيق غير صحيح. المطلوب: `القصة | القاتل | المشتبه بهم`", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_del_crime":
        if text.isdigit():
            c_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM crime_stories WHERE id = ?", (c_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الجريمة رقم `{c_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال رقم الجريمة (ID).")
        del admin_states[user_id]
        return

    elif state == "wait_add_riddle":
        parts = text.split("-")
        if len(parts) == 2:
            rq, ra = parts[0].strip(), parts[1].strip()
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (rq, ra))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة الحزورة بنجاح!")
        else:
            bot.reply_to(message, "❌ التنسيق المطلوب: `الحزورة - الإجابة`", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_del_riddle":
        if text.isdigit():
            r_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM riddles WHERE id = ?", (r_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الحزورة رقم `{r_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال رقم الحزورة (ID).")
        del admin_states[user_id]
        return

    elif state == "wait_add_q":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO questions (question) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة السؤال بنجاح!")
        del admin_states[user_id]
        return

    elif state == "wait_del_q":
        if text.isdigit():
            q_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM questions WHERE id = ?", (q_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف السؤال رقم `{q_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال رقم السؤال (ID).")
        del admin_states[user_id]
        return

    elif state == "wait_add_rep":
        parts = text.split("-")
        if len(parts) == 2:
            kw, resp = parts[0].strip(), parts[1].strip()
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO custom_replies (keyword, response, media_type) VALUES (?, ?, 'text')", (kw, resp))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة الرد بنجاح!")
        else:
            bot.reply_to(message, "❌ التنسيق المطلوب: `الكلمة - الرد`", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_del_rep":
        if text.isdigit():
            rep_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM custom_replies WHERE id = ?", (rep_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الرد رقم `{rep_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال رقم الرد (ID).")
        del admin_states[user_id]
        return

    elif state == "wait_add_series":
        parts = text.split("-")
        if len(parts) == 2:
            sq, sa = parts[0].strip(), parts[1].strip()
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO series_questions (question, answer) VALUES (?, ?)", (sq, sa))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة سؤال المسلسل بنجاح!")
        else:
            bot.reply_to(message, "❌ التنسيق المطلوب: `السؤال - اسم المسلسل`", parse_mode="Markdown")
        del admin_states[user_id]
        return

    elif state == "wait_del_series":
        if text.isdigit():
            s_id = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM series_questions WHERE id = ?", (s_id,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف مسلسل رقم `{s_id}`.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال رقم المسلسل (ID).")
        del admin_states[user_id]
        return

    del admin_states[user_id]

# ==================== لوحة الإدارة الشاملة ====================
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("إضافة ادمن ➕", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("عرض الأدمنية 👥", callback_data="admin_list_admins"),
        types.InlineKeyboardButton("إضافة صنف 🛒", callback_data="admin_add_store_item"),
        types.InlineKeyboardButton("حذف صنف 🗑️", callback_data="admin_del_store_item"),
        types.InlineKeyboardButton("إضافة جريمة 🔪", callback_data="admin_add_crime"),
        types.InlineKeyboardButton("حذف جريمة 🗑️", callback_data="admin_del_crime"),
        types.InlineKeyboardButton("إضافة حزورة ➕", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("حذف حزورة 🗑️", callback_data="admin_del_riddle"),
        types.InlineKeyboardButton("إضافة أسئلة ➕", callback_data="admin_add_q"),
        types.InlineKeyboardButton("حذف سؤال 🗑️", callback_data="admin_del_q"),
        types.InlineKeyboardButton("إضافة ردود ➕", callback_data="admin_add_rep"),
        types.InlineKeyboardButton("حذف رد 🗑️", callback_data="admin_del_rep"),
        types.InlineKeyboardButton("إضافة مسلسل 📺", callback_data="admin_add_series"),
        types.InlineKeyboardButton("حذف مسلسل 🗑️", callback_data="admin_del_series"),
        types.InlineKeyboardButton("إضافة لعبة 🎮", callback_data="admin_add_custom_game"),
        types.InlineKeyboardButton("سجل الألعاب 📜", callback_data="admin_log_custom_games"),
        types.InlineKeyboardButton("سجل الأصناف 🛒", callback_data="admin_log_store"),
        types.InlineKeyboardButton("سجل الأسئلة ❓", callback_data="admin_log_questions"),
        types.InlineKeyboardButton("سجل الحزازير 🧩", callback_data="admin_log_riddles"),
        types.InlineKeyboardButton("سجل المسلسلات 📺", callback_data="admin_log_series"),
        types.InlineKeyboardButton("سجل الردود (20 بالصفحة) 💬", callback_data="admin_replies_page_0"),
        types.InlineKeyboardButton("سجل إجابات الجرائم 🎯", callback_data="admin_log_crimes"),
        types.InlineKeyboardButton("💰 إضافة رصيد وهمي", callback_data="admin_add_fake_balance"),
        types.InlineKeyboardButton("🤖 منح ميزات جيمني", callback_data="admin_gemini_groups"),
        types.InlineKeyboardButton("🔇 إسكات / تشغيل البوت", callback_data="admin_toggle_mute_bot"),
        types.InlineKeyboardButton("🚪 مغادرة مجموعة", callback_data="admin_leave_grp"),
        types.InlineKeyboardButton("✉️ رسالة خاصة لكروب", callback_data="admin_send_grp_msg")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم والإدارة الشاملة:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_admin(message.from_user.id):
        show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel" or call.data.startswith('admin_') or call.data.startswith('gemini_') or call.data.startswith('sendmsg_grp_'))
def handle_admin_actions(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "اللوحة مخصصة للآدمن فقط!", show_alert=True)
        return
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "open_admin_panel":
        show_admin_panel(chat_id)
        return

    if call.data == "admin_add_custom_game":
        admin_states[user_id] = "wait_custom_game_name"
        bot.send_message(chat_id, "🎮 **إضافة لعبة جديدة:**\n\nيرجى إرسال **اسم اللعبة** أولاً:", parse_mode="Markdown")
        return

    if call.data == "admin_log_custom_games":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, game_name, rules FROM custom_games")
        games = [f"ID `{row[0]}` | **{row[1]}**: {row[2]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🎮 **سجل الألعاب المخصصة المضافة:**", games)
        return

    if call.data == "admin_toggle_mute_bot":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (chat_id,))
        if c.fetchone():
            c.execute("DELETE FROM muted_groups WHERE chat_id = ?", (chat_id,))
            msg_res = "🔊 تم تشغيل البوت وفك الإسكات!"
        else:
            c.execute("INSERT INTO muted_groups VALUES (?)", (chat_id,))
            msg_res = "🔇 تم إسكات البوت في هذه المجموعة!"
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, msg_res, show_alert=True)
        return

    if call.data.startswith("admin_replies_page_"):
        page = int(call.data.split("_")[3])
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, keyword, response FROM custom_replies ORDER BY id ASC")
        all_replies = c.fetchall()
        conn.close()

        total_replies = len(all_replies)
        page_size = 20
        total_pages = max(1, (total_replies + page_size - 1) // page_size)

        start_idx = page * page_size
        end_idx = start_idx + page_size
        page_items = all_replies[start_idx:end_idx]

        markup = types.InlineKeyboardMarkup(row_width=2)
        text_msg = f"💬 **سجل الردود المخصصة (الصفحة {page + 1} من {total_pages}):**\n\n"
        
        for rep_id, kw, resp in page_items:
            short_resp = (resp[:15] + '..') if len(resp) > 15 else resp
            text_msg += f"• ID `{rep_id}` | الكلمة: `{kw}` 👈 الرد: {short_resp}\n"

        nav_btns = []
        if page > 0:
            nav_btns.append(types.InlineKeyboardButton("◀️ الصفحة السابقة", callback_data=f"admin_replies_page_{page - 1}"))
        if page < total_pages - 1:
            nav_btns.append(types.InlineKeyboardButton("الصفحة التالية ▶️", callback_data=f"admin_replies_page_{page + 1}"))

        if nav_btns:
            markup.add(*nav_btns)
        markup.add(types.InlineKeyboardButton("🔙 العودة للوحة", callback_data="open_admin_panel"))

        try:
            bot.edit_message_text(text_msg, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, text_msg, reply_markup=markup, parse_mode="Markdown")
        return

    if call.data == "admin_send_grp_msg":
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
            markup.add(types.InlineKeyboardButton(f"📢 {title}", callback_data=f"sendmsg_grp_{g_id}"))
        bot.send_message(chat_id, "✉️ **اختر المجموعة المراد إرسال رسالة خاصة إليها:**", reply_markup=markup, parse_mode="Markdown")
        return

    if call.data.startswith("sendmsg_grp_"):
        target_g_id = int(call.data.split("_")[2])
        admin_states[user_id] = {"state": "wait_custom_grp_msg", "target_chat_id": target_g_id}
        bot.send_message(chat_id, f"أرسل الآن المحتوى المراد إرساله (نص، صورة، فيديو، أو ملصق) إلى المجموعة `{target_g_id}`:", parse_mode="Markdown")
        return

    if call.data == "admin_gemini_groups":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM gemini_groups")
        allowed_g = [g[0] for g in c.fetchall()]
        conn.close()

        if not groups:
            bot.send_message(chat_id, "لا توجد مجموعات مسجلة حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, title in groups:
            status = "✨ ميزة جيمني مفعلة" if g_id in allowed_g else "❌ ميزة جيمني معطلة"
            markup.add(types.InlineKeyboardButton(f"{status}: {title}", callback_data=f"gemini_toggle_{g_id}"))
        bot.send_message(chat_id, "🤖 **التحكم بميزات جيمني للمجموعات:**\nانقر على المجموعة لمنحها أو سحب الميزة منها:", reply_markup=markup)
        return

    if call.data.startswith("gemini_toggle_"):
        target_g_id = int(call.data.split("_")[2])
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM gemini_groups WHERE chat_id = ?", (target_g_id,))
        if c.fetchone():
            c.execute("DELETE FROM gemini_groups WHERE chat_id = ?", (target_g_id,))
            msg_res = "❌ تم إلغاء تفعيل ميزات جيمني للمجموعة."
        else:
            c.execute("INSERT INTO gemini_groups VALUES (?)", (target_g_id,))
            msg_res = "✨ تم منح ميزات جيمني للمجموعة بنجاح!"
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, msg_res, show_alert=True)
        return

    if call.data == "admin_add_fake_balance":
        admin_states[user_id] = "wait_fake_bal_userid"
        bot.send_message(chat_id, "أرسل ID المستخدم المراد إضافة رصيد وهمي له:")
        return

    if call.data == "admin_add_admin":
        admin_states[user_id] = "wait_add_admin_id"
        bot.send_message(chat_id, "أرسل الآيدي (ID) الخاص بالمستخدم المراد رفعه أدمن:")
        return

    if call.data == "admin_list_admins":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        conn.close()
        admins_list = [f"المالك الأساسي: `{ADMIN_ID}`"]
        for r in rows:
            if r[0] != ADMIN_ID:
                admins_list.append(f"أدمن: `{r[0]}`")
        send_large_text(chat_id, "👥 **سجل الأدمنية المخولين:**", admins_list)
        return

    if call.data == "admin_add_store_item":
        admin_states[user_id] = "wait_add_store_item"
        bot.send_message(chat_id, "أرسل الصنف والسعر بالشكل:\n`اسم الصنف - السعر`", parse_mode="Markdown")
        return

    if call.data == "admin_del_store_item":
        admin_states[user_id] = "wait_del_store_item"
        bot.send_message(chat_id, "أرسل اسم الصنف المراد حذفه:")
        return

    if call.data == "admin_add_crime":
        admin_states[user_id] = "wait_add_crime"
        bot.send_message(chat_id, "أرسل القصة بالشكل:\n`القصة | القاتل | المشتبه بهم`", parse_mode="Markdown")
        return

    if call.data == "admin_del_crime":
        admin_states[user_id] = "wait_del_crime"
        bot.send_message(chat_id, "أرسل رقم (ID) الجريمة المراد حذفها:")
        return

    if call.data == "admin_add_riddle":
        admin_states[user_id] = "wait_add_riddle"
        bot.send_message(chat_id, "أرسل الحزورة والإجابة بالشكل:\n`الحزورة - الإجابة`", parse_mode="Markdown")
        return

    if call.data == "admin_del_riddle":
        admin_states[user_id] = "wait_del_riddle"
        bot.send_message(chat_id, "أرسل رقم (ID) الحزورة المراد حذفها:")
        return

    if call.data == "admin_add_q":
        admin_states[user_id] = "wait_add_q"
        bot.send_message(chat_id, "أرسل السؤال المراد إضافته:")
        return

    if call.data == "admin_del_q":
        admin_states[user_id] = "wait_del_q"
        bot.send_message(chat_id, "أرسل رقم (ID) السؤال المراد حذفه:")
        return

    if call.data == "admin_add_rep":
        admin_states[user_id] = "wait_add_rep"
        bot.send_message(chat_id, "أرسل الكلمة والرد بالشكل:\n`الكلمة - الرد`", parse_mode="Markdown")
        return

    if call.data == "admin_del_rep":
        admin_states[user_id] = "wait_del_rep"
        bot.send_message(chat_id, "أرسل رقم (ID) الرد المراد حذفه:")
        return

    if call.data == "admin_add_series":
        admin_states[user_id] = "wait_add_series"
        bot.send_message(chat_id, "أرسل السؤال واسم المسلسل بالشكل:\n`السؤال - اسم المسلسل`", parse_mode="Markdown")
        return

    if call.data == "admin_del_series":
        admin_states[user_id] = "wait_del_series"
        bot.send_message(chat_id, "أرسل رقم (ID) المسلسل المراد حذفه:")
        return

    if call.data == "admin_log_store":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = [f"السلعة: `{row[0]}` | السعر: `{row[1]}` ليرة" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🛒 **سجل الأصناف والمتجر:**", items)
        return

    if call.data == "admin_log_questions":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question FROM questions")
        qs = [f"ID `{row[0]}` | {row[1]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "❓ **سجل الأسئلة العامة:**", qs)
        return

    if call.data == "admin_log_riddles":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question, answer FROM riddles")
        rds = [f"ID `{row[0]}` | {row[1]} 👈 الإجابة: {row[2]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🧩 **سجل الحزازير:**", rds)
        return

    if call.data == "admin_log_series":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question, answer FROM series_questions")
        srs = [f"ID `{row[0]}` | {row[1]} 👈 المسلسل: {row[2]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "📺 **سجل مسابقات المسلسلات:**", srs)
        return

    if call.data == "admin_log_crimes":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, story, killer FROM crime_stories")
        crms = [f"ID `{row[0]}` | {row[1][:30]}... 👈 القاتل: {row[2]}" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🎯 **سجل إجابات الجرائم:**", crms)
        return

    if call.data == "admin_leave_grp":
        try:
            bot.leave_chat(chat_id)
        except Exception as e:
            bot.send_message(chat_id, f"❌ متعذر المغادرة: {e}")
        return

# ==================== تشغيل البوت ====================
if __name__ == '__main__':
    keep_alive()
    print("🤖 فرفوش يعمل الآن بنجاح وتألق...")
    bot.infinity_polling(skip_pending=True)
