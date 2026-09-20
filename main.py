import os
import re
import time
import random
import sqlite3
import requests
import html
import urllib.parse
import threading
import telebot
from telebot import types
import yt_dlp
from flask import Flask

# ==================== سيرفر وهمي لاستضافة ريندر (Render Keep-Alive) ====================
app = Flask('')

@app.route('/')
def home():
    return "🤖 البوت يعمل بنجاح وموصول بجيميني وريندر 100%!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

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

    # 1. إدخال الأسئلة المبدئية العامة
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
            "بتحبني ولا بتحبني؟"
        ]
        for q in questions_list:
            cursor.execute("INSERT INTO questions (question) VALUES (?)", (q,))

    # 2. إدخال 50 حزورة منطقية ومتقنة
    cursor.execute("SELECT COUNT(*) FROM riddles")
    if cursor.fetchone()[0] != 50:
        cursor.execute("DELETE FROM riddles")
        riddles_list = [
            ("ما هو الشيء الذي كلما أخذت منه كبر؟", "الحفرة"),
            ("ما هو الشيء الذي يتكلم جميع اللغات؟", "الصدى"),
            ("ما هو الشيء الذي يسير بلا رجلين ولا يدخل إلا بالإذن؟", "الصوت"),
            ("شيء إله عين وما بيشوف، شو هو؟", "الإبرة"),
            ("ما هو الشيء الذي يكتب ولا يقرأ؟", "القلم"),
            ("ما هو الشيء الذي إذا شرب مات وإذا أكل عاش؟", "النار"),
            ("له أوراق وليس شجرة، وله جلد وليس حيوان، فما هو؟", "الكتاب"),
            ("ما هو الشيء الذي يمشي طول اليوم ولا يتعب أبداً؟", "الساعة"),
            ("ما هو الشيء الذي يحملك وتحمله في نفس الوقت؟", "الحذاء"),
            ("ما هو البيت الذي ليس فيه أبواب ولا نوافذ؟", "بيت الشعر"),
            ("شيء يخترق الزجاج ولا يكاسره، ما هو؟", "الضوء"),
            ("ما هو الشيء الذي ينزل ولا يصعد أبداً؟", "المطر"),
            ("ما هو الشيء الذي يوجد في وسط باريس؟", "حرف ر"),
            ("ما هو الشيء الذي يكون أخضر في الأرض وأسود في السوق وأحمر في البيت؟", "الشاي"),
            ("أين يقع البحر الذي لا يوجد فيه ماء؟", "على الخريطة"),
            ("ما هو الشيء الذي لا يمكنك استخدامه إلا إذا كسرته؟", "البيض"),
            ("ما هو الشيء الذي يتبعك أينما ذهبت في النهار ويختفي بالليل؟", "الظل"),
            ("ما هو الشيء الذي يملك رقبة ولكن ليس لديه رأس؟", "الزجاجة"),
            ("ما هو الشيء الذي كلما زاد نقص؟", "العمر"),
            ("ما هو الشيء الذي يربيه الأب وتذبحه الأم وتبكي عليه الأخت ويقتله الأخ؟", "البصل"),
            ("ما هو الشيء الذي لا يمشي إلا بالضرب؟", "المسمار"),
            ("ما هو القفص الذي لا يحبس فيه طير ولا حيوان؟", "القفص الصدري"),
            ("ما هو الشيء الذي يمر عبر المدن والقبائل ولا يتحرك؟", "الطريق"),
            ("ما هو الشيء الذي يستطيع أن يملأ الغرفة دون أن شغل مساحة؟", "النور"),
            ("ما هو الشيء الذي يقرصك ولا تراه؟", "الجوع"),
            ("ما هو الشيء الذي له أربعة أرجل ولا يستطيع المشي؟", "الكرسي"),
            ("شيء ينبض بلا قلب، ما هو؟", "الساعة"),
            ("ما هو الشيء الذي إذا غليته تجمد؟", "البيض"),
            ("من هو الخال الوحيد لأولاد عمتك؟", "والدك"),
            ("ما هو الشيء الذي إذا لمسته صاح؟", "الجرس"),
            ("إذا أطعمته كبر وإذا سقيته مات، ما هو؟", "النار"),
            ("شيء يخرج من الماء ويموت بالماء؟", "الملح"),
            ("ما هو الشيء الذي يمتلك مفاتيح كثيرة ولكنه لا يستطيع فتح أي باب؟", "البيانو"),
            ("شيء أوله عين وآخره سن، ما هو؟", "العنب"),
            ("ما هو الشيء الذي لا يبتل حتى لو نزل في الماء؟", "الضوء"),
            ("ما هو الشيء الذي له أسنان ولا يعض؟", "المشط"),
            ("يمشي بلا رجلين ويبكي بلا عينين، ما هو؟", "السحاب"),
            ("ما هو الشيء الذي إذا نطقته كسرته؟", "الصمت"),
            ("ما هو الشيء الذي تحمله ويحملك؟", "الحذاء"),
            ("ما هو الشيء الذي يكون في الصيف داكناً وفي الشتاء أبيض؟", "الجبل"),
            ("كائن يرى كل شيء وليس له عيون، ما هو؟", "المرأة"),
            ("ما هو الشيء الذي يدور حول الحديقة دون أن يتحرك؟", "السور"),
            ("ما هي العروس التي بلا عريس؟", "الدمية"),
            ("ما هو الشيء الذي ترميه كلما احتجت إليه؟", "شبكة الصيد"),
            ("ما هو الشيء الذي يوجد بين السماء والأرض؟", "حرف الواو"),
            ("ما هو الشيء الذي تراه في الظلام ولا تراه في النور؟", "الظلام"),
            ("ما هو الشيء الذي تسمعه ولا تراه وإذا رأيته لا تسمعه؟", "الطلقة"),
            ("ما هو الشجر الذي ليس له ظل ولا ثمار؟", "شجرة العائلة"),
            ("ابن أمك وابن أبيك، وليس بأخيك ولا بأختك، فمن يكون؟", "أنت"),
            ("ما هو الشيء الذي يقف وينزل بلا حركة؟", "درجة الحرارة")
        ]
        for rq, ra in riddles_list:
            cursor.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (rq, ra))

    # 3. إدخال الردود التلقائية الكاملة
    extra_replies = [
        ("صباح الخير", "صباح النور… نورك مغطي عالصبح كله 😏"),
        ("مرحبا", "مرحبتين، وحدة إلك ووحدة لعيونك 😏❤️"),
        ("تصبحو على خير", "تصبحوا على خير، وإذا حدا حلم فيني بدي نسبة من الأرباح 😂"),
        ("بوت", "ولك أنا عم اشتغل بلا راتب🌝"),
        ("بوت", "قول اسمي مطوريني تعبو لساووني 😡 @syabd0 . @Lolo123000"),
        ("بوت", "اسمي فرفوووش"),
        ("بوت", "بوت بعينك اسمي فرفوش"),
        ("بوت", "قولا مرة تانية ورباح خلاط 😡"),
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
        ("فرفوش", "عيون فرفوش الروق يا حلو! 😍"),
        ("فرفوش", "فرفوش بالخدمة والروق والسعادة! ✨"),
        ("فرفوش", "لبيه يا عيون فرفوش 😘"),
        ("فرفوش", "فرفوش جاهز للضحك والتسلاية! 🕺"),
        ("فرفوشي", "يا عيون فرفوشي أنت! ❤️"),
        ("فرفوشي", "روح قلب فرفوشي من جوة 🫣"),
        ("فرفوشي", "فرفوشي بحبك أكتر مما تتخيل! 💕"),
        ("فرفوشي", "يا دلي أنا.. فرفوشي على خطك 🌸"),
        ("بحبك", "وأنا بحبك وبموت فيك يا عسل! ❤️"),
        ("بحبك", "الحب أفعال مش بس حكي.. هلي بالليرات بصدقك 😂❤️"),
        ("بحبك", "يا خجل البوتات! وأنا بحبك من أخر شريحة بقلبي 🙈"),
        ("بحبك", "قلبي الصغير لا يتحمل هذا الحب الكثيف! 🔥"),
        ("بكرهك", "ليه بس كدة؟ دا أنا فرفوش الطيب المسكين 🥺"),
        ("بكرهك", "من حبنا حبسناه.. عادي بكرة بتحبني 😂"),
        ("بكرهك", "القلوب شواهد.. بس أنا لساني بحبك يا غالي! 💔"),
        ("بكرهك", "لا تكرهني عشان الجروب يضل فرفوش وزاهي 😉")
    ]
    for kw, resp in extra_replies:
        cursor.execute("SELECT 1 FROM custom_replies WHERE keyword = ? AND response = ?", (kw, resp))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO custom_replies (keyword, response, media_type) VALUES (?, ?, 'text')", (kw, resp))

    # 4. إدخال قصص الجرائم
    cursor.execute("SELECT COUNT(*) FROM crime_stories")
    if cursor.fetchone()[0] < 50:
        crimes_list = [
            ("في ليلة ممطرة، وُجد رجل الأعمال 'سليم' مقتولاً في مكتبه. المحاسب (فادي) يدعي أنه كان يراجع الأوراق، السكرتيرة (مريم) تقول أنها كانت تعد القهوة، والحارس (سامر) يقول أنه كان يقف عند الباب وشاهد شخصاً يرتدي معطفاً خردلياً.", "فادي", "فادي، مريم، سامر"),
            ("اختفت قلادة الماسية من الخزنة. الخادم (رامي) يقول أنه كان ينظف المطبخ، والطباخ (شادي) يقول أنه كان يقطع الخضار، والسائق (ماهر) يدعي أنه كان يغسل السيارة تحت المطر.", "ماهر", "رامي، شادي، ماهر"),
            ("وُجد الطبيب 'كمال' مقتولاً داخل عيادته. الممرضة (ليلى) تقرر أنها كانت بالخارج، المريض (ياسر) يقول إنه كان ينتظر بالانتظار، والصيدلي (عمر) يدعي أنه سلم الأدوية ورجع.", "ليلى", "ليلى، ياسر، عمر"),
            ("في متحف الآثار، سُرق تمثال ذهبي. الحارس (خالد) يدعي أنه نام لدقيقة، المُنظف (حسن) يقول أنه غسل الأرضية، والزائر (أحمد) يقول إنه كان يلتقط صوراً.", "حسن", "خالد، حسن، أحمد"),
            ("في الفندق المهجور قُتل السائح 'روبرت'. المرشد (باسم) يقول كان يجهز الخريطة، المصور (زياد) يقول كان يبدل العدسة، والطباخ (طارق) يقول كان يشوي.", "زياد", "باسم، زياد، طارق"),
            ("سُرقت قطعة مجوهرات ثمينة من القصر. الطباخة (جميلة) تقول كانت تحضر العشاء، البستاني (نبيل) يقول كان يسقي الزرع بالشمس، والخادمة (سارة) تقول كانت تكوي.", "نبيل", "جميلة، نبيل، سارة"),
            ("عُثر على جثة المحامي 'جهاد' في شقته. الجار (توفيق) يقول سمع صراخاً، ابن أخته (عادل) يقول كان يدرس، والساعي (هشام) يقول سلم طرداً وغادر.", "عادل", "توفيق، عادل، هشام"),
            ("اختفت سبيكة ذهبية من المصرف. مدير الفرع (كمال) يقول كان باجتماع، الحارس (جمال) يقول كان بالدورية، والمحاسب (وائل) يقول كان يعد النقود.", "وائل", "كمال، جمال، وائل"),
            ("في مرأب السيارات، قُتل الميكانيكي 'سمير'. المساعد (خالد) يدعي أنه جلب القطع، الزبون (فراس) يقول كان ينتظر سيارته، والجار (سليم) يقول كان يغسل سيارته.", "خالد", "خالد، فراس، سليم"),
            ("سُرقت اللوحة الشهيرة من معرض الفنون. قيم المعرض (عامر) يقول كان يراجع الدفاتر، الحارس (نذير) يقول كان يتفقد الباب، والرسام (أيمن) يقول كان يتأمل اللوحة.", "أيمن", "عامر، نذير، أيمن"),
            ("وُجد المهندس 'عصام' مقتولاً بموقع البناء. المشرف (فاروق) يقول كان يفحص الاسمنت، العامل (مالك) يقول كان يرتاح، والسائق (وسيم) يقول كان يفرغ الشاحنة.", "فاروق", "فاروق، مالك، وسيم"),
            ("اختفى عقد لؤلؤ نادر من منزل العروس. المصففة (رولا) تقول كانت تسرح الشعر، الخياطة (ندى) تقول كانت تعدل الفستان، والمكياج (دينا) تقول كانت تضع المكياج.", "ندى", "رولا، ندى، دينا"),
            ("قُتل المزارع 'توفيق' في الحقل. جاره (مصطفى) يقول كان يحرث أرضه، ابن جاره (بلال) يقول كان يجمع الثمار، والراعي (سعيد) يقول كان يرعى الغنم.", "بلال", "مصطفى، بلال، سعيد"),
            ("في ليلة العاصفة، قُتل الربان 'يوسف' بالسفينة. مساعده (مراد) يقول كان يراقب البوصلة، الطباخ (فادي) يقول كان يطبخ، والبحار (سعد) يقول كان يربط الحبال.", "مراد", "مراد، فادي، سعد"),
            ("سُرق هاتف ذكي ثمنه باهظ من المتجر. البائع (رامز) يقول كان مع زبون، الكاشير (علاء) يقول كان يحسب الفاتورة، وعامل التنظيف (جهاد) يقول كان يمسح الزجاج.", "علاء", "رامز، علاء، جهاد"),
            ("وُجد الكاتب 'أنس' مقتولاً بين كتبه. الناشر (ماجد) يقول كان يقرأ المسودة، الناقد (سليم) يقول كان يناقشه، والمساعد (ربيع) يقول كان يرتب الرفوف.", "ماجد", "ماجد، سليم، ربيع"),
            ("اختفت ساعته الذهبية من غرفة السونا. العامل (سامي) يقول كان ينظف المناشف، الزبون (مروان) يقول كان بالاستراحة، والمدرب (عمر) يقول كان يدرب.", "سامي", "سامي، مروان، عمر"),
            ("قُتل الصحفي 'طارق' قبل نشر تحقيقه. المصور (أكرم) يقول كان يطور الصور، المحرر (هاني) يقول كان يراجع المقال، والطباع (كمال) يقول كان يجهز الأوراق.", "أكرم", "أكرم، هاني، كمال"),
            ("سُرقت خزنة التبرعات من الجمعية. المتطوع (يزن) يقول كان يوزع الطعام، المحاسب (مؤيد) يقول كان يعد الجدول، والحارس (حمزة) يقول كان يغلق الباب.", "مؤيد", "يزن، مؤيد، حمزة"),
            ("وُجد الصيدلي 'أحمد' مقتولاً في صيدليته. المساعد (وليد) يقول كان يرتب الأدوية، الزبون (باسل) يقول كان ينتظر دواءه، والمندوب (طارق) يقول سلم الشحنة.", "وليد", "وليد، باسل، طارق"),
            ("في القطار السريع، قُتل الدبلوماسي 'شريف'. الساقي (زياد) يقول كان يقدم القهوة، المفتش (عارف) يقول كان يفحص التذاكر، والمسافر (أنس) يقول كان نائماً.", "زياد", "زياد، عارف، أنس"),
            ("سُرقت المخطوطة الأثرية من المكتبة الوطنية. أمين المكتبة (صالح) يقول كان يسجل الكتب، المرمم (حسام) يقول كان يعالج الورق، والزائر (ماهر) يقول كان يقرأ.", "حسام", "صالح، حسام، ماهر"),
            ("قُتل الكيميائي 'منير' في المختبر. الباحث (تامر) يقول كان يسجل النتائج، الفني (عادل) يقول كان ينظف الأنابيب، والحارس (شادي) يقول كان بالخارج.", "تامر", "تامر، عادل، شادي"),
            ("اختفت حقيبة الأموال من سيارة المبالغ. السائق (خالد) يقول كان يقود السيارة، الحارس (فؤاد) يقول كان يراقب الطريق، والزميل (سامر) يقول كان يراجع المستندات.", "فؤاد", "خالد، فؤاد، سامر"),
            ("وُجد المخرج 'سامي' مقتولاً في كواليس المسرح. الممثل (عمر) يقول كان يجرب الأزياء، الماكيير (عماد) يقول كان يحضر المساحيق، وفني الصوت (سعيد) يقول كان يضبط الميكروفون.", "عماد", "عمر، عماد، سعيد"),
            ("قُتل المصمم 'زياد' في مشغله. المساعدة (هناء) تقول كانت ترتب القماش، العارض (طارق) يقول كان يجرب البدلة، والخياط (وسيم) يقول كان يستخدم المقس.", "طارق", "هناء، طارق، وسيم"),
            ("سُرق خاتم الياقوت من الخزنة. الطباخ (هشام) يقول كان يقلي البطاطس، السائق (سليم) يقول كان يمسح السيارة بالمرأب، والبستاني (رامي) يقول كان يقلم الأشجار بالحديقة.", "سليم", "هشام، سليم، رامي"),
            ("وُجد الحارس 'عمر' مقتولاً أمام المصرف. زميله (حسن) يقول كان بالحمام، موظف الاستقبال (نبيل) يقول كان يغلق المكاتب، وعامل الصيانة (بلال) يقول كان يصلح المصعد.", "حسن", "حسن، نبيل، بلال"),
            ("في السفينة، سُرقت حقيبة المجوهرات. الربان (مجدي) يقول كان بقمرة القيادة، الطاهي (جميل) يقول كان يقطع اللحم، والمسافر (كمال) يقول كان يتأمل البحر.", "كمال", "مجدي، جميل، كمال"),
            ("قُتل العالم 'ماجد' في مختبره. الفني (أشرف) يقول كان ينظف المجهر، المساعد (هاني) يقول كان يدون الملاحظات، والحارس (سامح) يقول كان يراجع السجل.", "أشرف", "أشرف، هاني، سامح"),
            ("سُرق تمثال أثري من القصر. الخادم (خالد) يقول كان يمسح الغبار، الحارس (عمر) يقول كان يتفقد البوابة، والطباخة (ريم) تقول كانت تخبز الكعك.", "خالد", "خالد، عمر، ريم"),
            ("وُجد الفنان 'فريد' مقتولاً بمرسمه. النموذج (سارة) تقول كانت تستريح، بائع الألوان (عادل) يقول كان يسلم الطلبية، والمساعد (ربيع) يقول كان يغسل الفرش.", "عادل", "سارة، عادل، ربيع"),
            ("في رحلة الصيد، قُتل 'حسام'. صديقه (فراس) يقول كان ينظف بندقيته، دليله (أحمد) يقول كان يوقد النار، والمصور (تامر) يقول كان يلتقط صوراً للطيور.", "فراس", "فراس، أحمد، تامر"),
            ("اختفت تحفة زجاجية من المعرض. المشرف (فادي) يقول كان يراجع التذاكر، المنظف (جهاد) يقول كان يمسح الواجهة، والزائر (سامر) يقول كان يشرب القهوة.", "جهاد", "فادي، جهاد، سامر"),
            ("قُتل الطبيب البيطري 'سمير' بالعيادة. المساعد (وائل) يقول كان يطعم الكلاب، السكرتيرة (منى) تقول كانت تتصل بالزبائن، والزبون (طارق) يقول كان ينتظر دوره.", "وائل", "وائل، منى، طارق"),
            ("سُرقت ساعة رئيس الشركة من مكتبه. السكرتير (ياسر) يقول كان يصور المستندات، الحارس (هشام) يقول كان يراقب الكاميرات، والمحاسب (سعيد) يقول كان يراجع الميزانية.", "ياسر", "ياسر، هشام، سعيد"),
            ("وُجد المدرب 'كمال' مقتولاً بالصالة الرياضية. العامل (حمزة) يقول كان ينظف الأجهزة، السباح (عارف) يقول كان بالمسبح، واللاعب (زياد) يقول كان يبدل ملابسه.", "حمزة", "حمزة، عارف، زياد"),
            ("في شاطئ البحر، قُتل 'أنس'. المنقذ (مصطفى) يقول كان يراقب البحر، بائع العصير (باسل) يقول كان يعصر البرتقال، والجار (ماهر) يقول كان يسبح.", "مصطفى", "مصطفى، باسل، ماهر"),
            ("اختفت سبيكة فضية من المترو. الركب (سليم) يقول كان يقرأ، السائق (وسيم) يقول كان يراقب السكة، والمفتش (عمر) يقول كان يراجع التذاكر.", "عمر", "سليم، وسيم، عمر"),
            ("قُتل المخرج 'توفيق' أثناء التصوير. الممثل (شادي) يقول كان يحفظ دوره، المصور (رامي) يقول كان يضبط الإضاءة، والماكيير (علاء) يقول كان يضع الماكياج.", "رامي", "شادي، رامي، علاء"),
            ("سُرقت لوحة أثرية من المتحف. الدليل (عامر) يقول كان يشرح للزوار، الحارس (نذير) يقول كان ينظر للخارج، والمنظف (أيمن) يقول كان يغسل الأرض.", "نذير", "عامر، نذير، أيمن"),
            ("وُجد مهندس الصوت 'فادي' مقتولاً بالاستوديو. المغني (سامر) يقول كان يسجل الأغنية، الموزع (ماجد) يقول كان يعزف، والحارس (نبيل) يقول كان يشرب الشاي.", "ماجد", "سامر، ماجد، نبيل"),
            ("قُتل الصيدلي 'ماهر' في الليل. المساعد (وليد) يقول كان يرتب الرفوف، الزبون (باسل) يقول كان يقيس الضغط، والدليفري (سعيد) يقول كان يوصل طلبية.", "وليد", "وليد، باسل، سعيد"),
            ("اختفت مجوهرات من غرفة الفندق. عاملة النظافة (فاطمة) تقول كانت تبدل الملاءات، موظف الاستقبال (أيمن) يقول كان يستقبل النزلاء، والحارس (خالد) يقول عند الباب.", "فاطمة", "فاطمة، أيمن، خالد"),
            ("وُجد الباحث 'سليم' مقتولاً بالمكتبة. المساعد (ربيع) يقول كان يرتب الكتب، القارئ (عادل) يقول كان يقرأ، وأمين المكتبة (كمال) يقول كان يسجل الإعارات.", "ربيع", "ربيع، عادل، كمال"),
            ("قُتل المزارع 'علي' بالحقل. جاره (حسن) يقول كان يسقي مزروعاته، العامل (بلال) يقول كان يجمع الثمار، والراعي (سعيد) يقول كان يرعى الأغنام.", "بلال", "حسن، بلال، سعيد"),
            ("سُرق هاتف ذهبي من المعرض. البائع (رامز) يقول كان يعرض الهواتف، الكاشير (علاء) يقول كان يحسب الفاتورة، وعامل النظافة (جهاد) يقول كان يمسح الزجاج.", "رامز", "رامز، علاء، جهاد"),
            ("قُتل الكيميائي 'رامي' بالمختبر. الباحث (تامر) يقول كان يزن المواد، الفني (وسيم) يقول كان يغسل الأنابيب، والحارس (شادي) يقول كان يراقب الباب.", "تامر", "تامر، وسيم، شادي"),
            ("اختفت حقيبة مستندات من السيارة. السائق (خالد) يقول كان ينظف المحرك، الحارس (فؤاد) يقول كان عند البوابة، والزميل (سامر) يقول كان يقرأ الجريدة.", "سامر", "خالد، فؤاد، سامر"),
            ("وُجد المصور 'أكرم' مقتولاً باستوديوه. المساعد (عماد) يقول كان يجهز العدسات، الزبون (عمر) يقول كان ينتظر صوره، والحارس (سعيد) يقول كان ينظف المدخل.", "عماد", "عماد، عمر، سعيد")
        ]
        for st, kl, sp in crimes_list:
            cursor.execute("SELECT 1 FROM crime_stories WHERE story = ?", (st,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (st, kl, sp))

    # 5. إدخال أسئلة المسلسلات
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

# ==================== نظام جيمني المطور والانشاء الدقيق للصور ====================
def fetch_ai_answer(question):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.9"
    }

    sys_prompt = "أنت مساعد ذكي واسمك فرفوش، تعمل بنظام Gemini المجاني والمتطور. أجب عن سؤال المستخدم باللغة العربية بشكل دقيق ومباشر ومنطقي جداً بناءً على ما طلبه حصراً دون تعذر. يمنع منعاً باتاً ذكر أي روابط أو خروج عن موضوع السؤال أو ذكر أي مصادر."

    models_chain = ["gemini", "gemini-thinking", "openai", "deepseek", "qwen", "llama", "mistral"]

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
                if ans and len(ans) > 5 and not any(bad in ans.lower() for bad in ["timed out", "error", "504", "403", "html", "cloudflare", "bad gateway"]):
                    return ans
        except Exception:
            continue

    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(question)}?system={urllib.parse.quote(sys_prompt)}&model=gemini"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200 and res.text:
            ans = clean_urls_and_sources(res.text)
            if ans and len(ans) > 5:
                return ans
    except Exception:
        pass

    return "أهلاً بك يا غالي! أنا جاهز للإجابة على أسئلتك عبر نظام جيمني المجاني. تفضل بتكرار سؤالك وسأجيبك فوراً."

def generate_image_pollinations(prompt):
    models = ["flux", "flux-realism", "any-dark", "turbo"]
    encoded_prompt = urllib.parse.quote(prompt)
    
    for m in models:
        try:
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={random.randint(1, 999999)}&nologo=true&model={m}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200 and len(res.content) > 2000:
                return res.content
        except Exception:
            continue
    return None

# ==================== خدمات تحميل الأغاني والفيديو والروابط ====================
def download_and_send_audio(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, "🔍 **جاري البحث وتحميل الصوت فوراً...**", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads', exist_ok=True)

    file_prefix = f"downloads/audio_{int(time.time())}_{random.randint(1000,9999)}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{file_prefix}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
    }

    search_target = query if query.startswith("http") else f"ytsearch1:{query}"

    downloaded = False
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=True)
            if info:
                video = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
                title = video.get('title', query)
                uploader = video.get('uploader', 'فرفوش')

                downloaded_file = None
                for ext in ['mp3', 'm4a', 'opus', 'webm', 'mp4', 'ogg']:
                    p = f"{file_prefix}.{ext}"
                    if os.path.exists(p):
                        downloaded_file = p
                        break

                if downloaded_file and os.path.exists(downloaded_file):
                    with open(downloaded_file, 'rb') as audio:
                        bot.send_audio(chat_id, audio, title=title, performer=uploader, reply_to_message_id=message_id)
                    try:
                        bot.delete_message(chat_id, status_msg.message_id)
                    except:
                        pass
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                    downloaded = True
                    return
    except Exception:
        pass

    if not downloaded:
        ydl_opts_fallback = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
            'outtmpl': f'{file_prefix}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                info = ydl.extract_info(search_target, download=True)
                if info:
                    video = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
                    title = video.get('title', query)
                    uploader = video.get('uploader', 'فرفوش')

                    downloaded_file = None
                    for ext in ['m4a', 'mp3', 'opus', 'webm', 'mp4', 'ogg']:
                        p = f"{file_prefix}.{ext}"
                        if os.path.exists(p):
                            downloaded_file = p
                            break

                    if downloaded_file and os.path.exists(downloaded_file):
                        with open(downloaded_file, 'rb') as audio:
                            bot.send_audio(chat_id, audio, title=title, performer=uploader, reply_to_message_id=message_id)
                        try:
                            bot.delete_message(chat_id, status_msg.message_id)
                        except:
                            pass
                        try:
                            os.remove(downloaded_file)
                        except:
                            pass
                        return
        except Exception:
            pass

    try:
        bot.edit_message_text("❌ تعذر تحميل الصوت حالياً، تأكد من اسم الأغنية أو جرب رابطاً مباشراً.", chat_id, status_msg.message_id)
    except:
        pass

def download_and_send_video(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, "🎬 **جاري البحث وتحميل الفيديو...**", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads', exist_ok=True)

    file_prefix = f"downloads/vid_{int(time.time())}_{random.randint(1000,9999)}"

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]',
        'outtmpl': f'{file_prefix}.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
    }

    target = query if query.startswith("http") else f"ytsearch1:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target, download=True)
            if info:
                video_info = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
                title = video_info.get('title', query) if video_info else query

                downloaded_file = None
                for ext in ['mp4', 'mkv', 'webm']:
                    p = f"{file_prefix}.{ext}"
                    if os.path.exists(p):
                        downloaded_file = p
                        break

                if downloaded_file and os.path.exists(downloaded_file):
                    with open(downloaded_file, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, caption=f"🎥 **{title}**", reply_to_message_id=message_id, parse_mode="Markdown")
                    try:
                        bot.delete_message(chat_id, status_msg.message_id)
                    except:
                        pass
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                    return
    except Exception:
        pass

    try:
        bot.edit_message_text("❌ تعذر تحميل الفيديو، تأكد من صحة الرابط أو الكلمات الدلالية.", chat_id, status_msg.message_id)
    except:
        pass

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
        "🛡️ **حماية المجموعة:** منع الروابط والمعرفات والتوجيه للأعضاء مع ذكر الاسم عند الحذف.\n"
        "🎮 **ألعاب متطورة:** XO، رياضيات، خمن الرقم، خمن المسلسل 📺، القاتل 🔪، وعجلة الحظ 🎡.\n"
        "💸 **اقتصاد كامل:** إهداء أصناف، بيع أصناف، مراهنات، قروض، سجن، سرقة، واستثمار 90%.\n"
        "🤖 **ذكاء اصطناعي (جيمني الاصلي):** اكتب `عندي سؤال` أو `بدي ساوي صورة [وصف]`.\n"
        "🎵 **تحميل يوتيوب تلقائي:** أرسل كلمة `يوتيوب` أو `سمعني` مع اسم الأغنية وسأحملها لك صوتياً فوراً وبسرعة."
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    add_group_btn = types.InlineKeyboardButton("➕ أضفني إلى المجموعة", url=f"https://t.me/{bot_username}?startgroup=true")
    markup.add(add_group_btn)

    if is_admin(user_id):
        admin_btn = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="open_admin_panel")
        markup.add(admin_btn)

    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ==================== الموجه الرئيسي الحماية والأوامر ====================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'sticker'])
def main_router(message):
    text = (message.text or message.caption or "").strip()
    chat_type = message.chat.type
    user_id = message.from_user.id
    chat_id = message.chat.id

    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (chat_id,))
    is_muted = c.fetchone()
    conn.close()

    if is_muted and not is_admin(user_id):
        return

    if text.startswith("/start") or text.lower() == "ستارت":
        send_welcome_message(message)
        return

    # فحص روابط يوتيوب المباشرة للتحميل الصوتي الفوري
    yt_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text)
    if yt_match:
        yt_url = yt_match.group(1)
        download_and_send_audio(chat_id, yt_url, message.message_id)
        return

    # 1. نظام الحماية والأوامر الإدارية في المجموعات
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

        # الحماية مع استثناء المشرفين
        if is_bot_admin(chat_id) and not sender_is_admin and not is_channel_post:
            user_name = message.from_user.first_name if message.from_user else "العضو"
            user_mention = f"[{user_name}](tg://user?id={user_id})"

            if message.forward_date or message.forward_from or message.forward_from_chat:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، التوجيه ممنوع هنا ومافيك تنسخها نسخ ❌", parse_mode="Markdown")
                except:
                    pass
                return

            has_username = bool(re.search(r'@[a-zA-Z0-9_]+', text))
            if has_username:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، اسال صاحب لكروب اذا بيسمحلك بنشر المعرفات ياطيب ❌", parse_mode="Markdown")
                except:
                    pass
                return

            has_link = bool(re.search(r'(https?://\S+|t\.me/\S+|\b\w+\.(com|net|org|site|online)\b)', text))
            if has_link:
                try:
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id, f"عذراً يا {user_mention}، كفاك روابط يا بني ❌", parse_mode="Markdown")
                except:
                    pass
                return

    # 2. فحص السجن
    jailed, debt = is_user_jailed(user_id)
    if jailed and text not in ["دفع ديني", "دفع دينو"] and not (message.reply_to_message and "دفع دينو" in text):
        bot.reply_to(message, "انت مسجون ياحباب دفاع دينك قبل يافقير")
        return

    # 3. حالات تفاعلية لجيمني
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
            gen_msg = bot.reply_to(message, "🎨 جاري رسم الصورة حسب الطلب... يرجى الانتظار قليلاً.")
            img_data = generate_image_pollinations(text)
            if img_data:
                try:
                    bot.delete_message(chat_id, gen_msg.message_id)
                except:
                    pass
                bot.send_photo(chat_id, photo=img_data, caption=f"🖼️ الصورة المطلوبة: `{text}`", reply_to_message_id=message.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ تعذر إنشاء الصورة حالياً، حاول مرة أخرى بوصف مختلف.", chat_id, gen_msg.message_id)
            return

    # 4. معالجة إدخالات الأدمن أو الأوامر العامة
    if is_admin(user_id) and user_id in admin_states:
        handle_admin_inputs(message)
    else:
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

    # الردود المخصصة التلقائية
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
                    bot.delete_message(chat_id, gen_msg.message_id)
                except:
                    pass
                bot.send_photo(chat_id, photo=img_data, caption=f"🖼️ الصورة المطلوبة: `{p_part}`", reply_to_message_id=message.message_id, parse_mode="Markdown")
            else:
                bot.edit_message_text("❌ تعذر إنشاء الصورة حالياً، حاول مرة أخرى بوصف مختلف.", chat_id, gen_msg.message_id)
        else:
            user_gemini_states[user_id] = "wait_gemini_image_prompt"
            bot.reply_to(message, "اكتب وصف الصورة التي تريد إنشاءها:")
        return

    # الألعاب ومتحقق الأجوبة
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

    # التحميل من يوتيوب فيديو وصوت
    if text.startswith("يوتيوب") or text.lower().startswith("youtube"):
        query = re.sub(r'^(يوتيوب|youtube)', '', text, flags=re.IGNORECASE).strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الفيديو أو الأغنية أو الرابط بعد الأمر.\nمثال: `يوتيوب الشامي`", parse_mode="Markdown")
            return
        download_and_send_audio(chat_id, query, message.message_id)
        return

    if text.startswith("سمعني"):
        query = text.replace("سمعني", "").strip()
        if not query:
            bot.reply_to(message, "يرجى كتابة اسم الأغنية بعد الأمر.\nمثال: `سمعني اصالة`", parse_mode="Markdown")
            return
        download_and_send_audio(chat_id, query, message.message_id)
        return

    # لعبة الرهان (70% ربح - 30% خسارة)
    if text.startswith("راهن"):
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_bet FROM bet_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            funny_bet_msgs = [
                f"🎲 روق على جيبتك شوي! المراهنة مقيدة مرة كل دقيقة، استنى `{remaining_secs}` ثانية ⏳",
                f"🎲 القمار بيخرب الديار! استنى `{remaining_secs}` ثانية قبل ما تراهن تاني 😂",
                f"🎲 يابني اهدى شوي على الرصيد! فاضل `{remaining_secs}` ثانية للرهان الجاي ⏱️"
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

            is_won = random.choices([True, False], weights=[70, 30])[0]
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
            if target_user.is_bot:
                bot.reply_to(message, "ما فيك تهدي البوت يا حباب!")
                return

            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
            row = c.fetchone()

            if row and row[0] >= count:
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (count, user_id, item_name))
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
            
            c.execute("SELECT price FROM store WHERE item_name = ?", (item_name,))
            store_row = c.fetchone()

            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
            inv_row = c.fetchone()

            if inv_row and inv_row[0] >= count:
                orig_price = store_row[0] if store_row else 10
                refund_per_item = orig_price // 2
                total_refund = refund_per_item * count
                
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (count, user_id, item_name))
                conn.commit()
                
                update_balance(user_id, total_refund)
                bot.reply_to(message, f"💰 **تم البيع بنجاح!**\nقمت ببيع **{count} {item_name}** واسترددت **{total_refund}** ليرة وهمية! 🎉", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"❌ لا تملك هذا العدد ({count}) من ({item_name}) لبيعه!")
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
            fail_no_money_messages = [
                f"😂 جيت تسرق {target_user.first_name} لقيت جيبته مخزوقة ومعهوش ولا فرنك!",
                f"😭 {target_user.first_name} مفلس أصلًا وعم يشحذ بالجروب، ارحمه!",
                f"❌ دخلت إيدك بجيبته طلعت فاضية... يا حوينت التعب!"
            ]
            bot.reply_to(message, random.choice(fail_no_money_messages))
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

            funny_success_messages = [
                f"🥷 دخلت عالساكت وسحبت من جيبة {target_user.first_name} مبلغ **{stolen_amount}** ليرة بدون ما يحس!",
                f"🕵️‍♂️ يادي العيب! سرقت من {target_user.first_name} **{stolen_amount}** ليرة ورحت اشتريت فيها متة!",
                f"😈 طيرتله **{stolen_amount}** ليرة من رصيده، يا عيب الشوم عليك يا حرامي!"
            ]
            bot.reply_to(message, random.choice(funny_success_messages), parse_mode="Markdown")
        else:
            funny_fail_messages = [
                f"🚨 كشفك {target_user.first_name} وأنت عم تمد إيدك! فركها وسحب منك كف ونفدت بالريش 😂",
                f"👮‍♂️ لمحك شرطي المرور وأنت عم تسرق وأكلك قتلة ونفدت بجلدك!",
                f"❌ تعثرت بالحجر وأنت عم تهرب واقتفطت السالفة وفشلت العملية!"
            ]
            bot.reply_to(message, random.choice(funny_fail_messages))
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
            bot.reply_to(message, "💡 للاستثمار أرسل:\n`استثمار [المبلغ]`\nمثال: `استثمار 100`", parse_mode="Markdown")
        return

    # لعبة العجلة (70% ربح - 30% خسارة)
    if text in ["عجلة", "العجلة", "لعبة العجلة"]:
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_wheel FROM wheel_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            funny_wheel_msgs = [
                f"🎡 العجلة من الندامة! هلكتنا عجلة استنى `{remaining_secs}` ثانية يا حباب ⌛",
                f"🎡 روق المانجا شوي! العجلة محتاجة استراحة، فاضل `{remaining_secs}` ثانية ⏱️",
                f"🎡 يا زلمة أصابيعك ميعت العجلة! استنى `{remaining_secs}` ثانية وارجع أدرها 🌀"
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

        is_win = random.choices([True, False], weights=[70, 30])[0]
        if is_win:
            prizes = [50, 100, 200, 500, 1000, 2000]
            weights = [35, 25, 20, 12, 6, 2]
            won = random.choices(prizes, weights=weights)[0]
            update_balance(user_id, won)
            bot.reply_to(message, f"🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وربحت **{won}** ليرة وهمية! 🎉", parse_mode="Markdown")
        else:
            bot.reply_to(message, "🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وخسرت! حظاً أفضل في المرة القادمة 💔", parse_mode="Markdown")
        return

    if text in ["اكسني", "لعبة اكس اوه"]:
        bal = get_balance(user_id)
        if bal < 50:
            bot.reply_to(message, "❌ رسوم بدء لعبة XO هي 50 ليرة ورصيدك لا يكفي!")
            return
        bot.send_message(chat_id, f"🎮 **لعبة XO جديدة!**\nالمنافس الأول: {message.from_user.first_name}\n💡 رسوم الدخول: 50 ليرة | جائزة الفائز: 200 ليرة\nاضغط للانضمام والمنافسة:", reply_markup=get_xo_keyboard(None, user_id, message.from_user.first_name), parse_mode="Markdown")
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

# ==================== إدارة الألعاب والـ XO ====================
def get_xo_keyboard(board, creator_id, creator_name, opponent_id=None, opponent_name=None):
    if board is None:
        board = [" "] * 9
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(9):
        val = board[i]
        btn_text = val if val != " " else "▫️"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"xocell_{i}"))
    
    markup.add(buttons[0], buttons[1], buttons[2])
    markup.add(buttons[3], buttons[4], buttons[5])
    markup.add(buttons[6], buttons[7], buttons[8])
    
    if opponent_id is None:
        markup.add(types.InlineKeyboardButton("⚔️ انضمام للعب (50 ليرة)", callback_data=f"xojoin_{creator_id}"))
    else:
        markup.add(types.InlineKeyboardButton("❌ إلغاء اللعبة", callback_data=f"xocancel_{creator_id}"))
        
    return markup

def check_xo_winner(b):
    wins = [
        (0,1,2), (3,4,5), (6,7,8),
        (0,3,6), (1,4,7), (2,5,8),
        (0,4,8), (2,4,6)
    ]
    for x, y, z in wins:
        if b[x] != " " and b[x] == b[y] == b[z]:
            return b[x]
    if " " not in b:
        return "DRAW"
    return None

def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO", callback_data="game_xo"),
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

# ==================== معالجة إدخالات الأدمن ولوحة التحكم ====================
def handle_admin_inputs(message):
    user_id = message.from_user.id
    state_data = admin_states.get(user_id)
    if not state_data:
        return

    st = state_data if isinstance(state_data, str) else state_data.get('state')

    if st == "wait_broadcast":
        del admin_states[user_id]
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id FROM groups")
        groups = c.fetchall()
        c.execute("SELECT DISTINCT user_id FROM users")
        users = c.fetchall()
        conn.close()

        sent_count = 0
        all_targets = set([g[0] for g in groups] + [u[0] for u in users])
        bot.send_message(message.chat.id, f"📢 جاري بدء الإذاعة إلى {len(all_targets)} وجهة...")

        for cid in all_targets:
            try:
                bot.copy_message(cid, message.chat.id, message.message_id)
                sent_count += 1
                time.sleep(0.05)
            except:
                pass

        bot.send_message(message.chat.id, f"✅ اكتملت الإذاعة بنجاح! تم التسليم إلى {sent_count} دردشة.")

    elif st == "wait_add_admin":
        del admin_states[user_id]
        if message.text and message.text.isdigit():
            new_admin = int(message.text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (new_admin,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم إضافة الأدمن الجديد `{new_admin}` بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ معرف غير صالح!")

    elif st == "wait_del_admin":
        del admin_states[user_id]
        if message.text and message.text.isdigit():
            rem_admin = int(message.text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM admins WHERE user_id = ?", (rem_admin,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم حذف الأدمن `{rem_admin}` بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ معرف غير صالح!")

    elif st == "wait_add_reply_kw":
        kw = message.text.strip() if message.text else ""
        if kw:
            admin_states[user_id] = {'state': 'wait_add_reply_resp', 'kw': kw}
            bot.reply_to(message, f"أرسل الآن الرد (نص، صورة، فيديو، استيكر) للكلمة المفتاحية: `{kw}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ نص غير صالح!")

    elif st == "wait_add_reply_resp":
        kw = state_data.get('kw')
        del admin_states[user_id]
        media_type = 'text'
        file_id = None
        resp_text = message.text or message.caption or ""

        if message.content_type == 'sticker':
            media_type = 'sticker'
            file_id = message.sticker.file_id
        elif message.content_type == 'photo':
            media_type = 'photo'
            file_id = message.photo[-1].file_id
        elif message.content_type == 'video':
            media_type = 'video'
            file_id = message.video.file_id

        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO custom_replies (keyword, response, media_type, file_id) VALUES (?, ?, ?, ?)", (kw, resp_text, media_type, file_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ تم إضافة الرد المخصص للكلمة `{kw}` بنجاح!", parse_mode="Markdown")

    elif st == "wait_del_reply":
        del admin_states[user_id]
        kw = message.text.strip() if message.text else ""
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM custom_replies WHERE keyword = ?", (kw,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            bot.reply_to(message, f"✅ تم حذف الرد المخصص للكلمة `{kw}` بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ الكلمة غير موجودة بالقائمة!")

    elif st == "wait_add_question":
        del admin_states[user_id]
        q_text = message.text.strip() if message.text else ""
        if q_text:
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO questions (question) VALUES (?)", (q_text,))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة السؤال بنجاح!")

    elif st == "wait_add_riddle":
        r_text = message.text.strip() if message.text else ""
        if r_text and "|" in r_text:
            del admin_states[user_id]
            q, a = r_text.split("|", 1)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q.strip(), a.strip()))
            conn.commit()
            conn.close()
            bot.reply_to(message, "✅ تم إضافة الحزورة بنجاح!")
        else:
            bot.reply_to(message, "⚠️ يرجى إرسال الحزورة والإجابة مفصولين بـ | مثال: `ما هو الشيء؟ | الجواب`", parse_mode="Markdown")

def send_admin_panel(chat_id, user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة عامة", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("➖ حذف أدمن", callback_data="admin_del_admin"),
        types.InlineKeyboardButton("💬 إضافة رد مخصص", callback_data="admin_add_reply"),
        types.InlineKeyboardButton("🗑️ حذف رد مخصص", callback_data="admin_del_reply"),
        types.InlineKeyboardButton("❓ إضافة سؤال", callback_data="admin_add_question"),
        types.InlineKeyboardButton("🧩 إضافة حزورة", callback_data="admin_add_riddle"),
        types.InlineKeyboardButton("🔇 كتم/إلغاء كتم المجموعة", callback_data="admin_toggle_mute"),
        types.InlineKeyboardButton("🤖 تفعيل/تعطيل جيمني بالمجموعة", callback_data="admin_toggle_gemini")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم بالبوت للإدارة:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_') or call.data == 'open_admin_panel')
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        try:
            bot.answer_callback_query(call.id, "❌ هذا الخيار مخصص للمطورين والأدمن فقط!", show_alert=True)
        except:
            pass
        return

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    chat_id = call.message.chat.id
    data = call.data

    if data == "open_admin_panel":
        send_admin_panel(chat_id, user_id)

    elif data == "admin_broadcast":
        admin_states[user_id] = "wait_broadcast"
        bot.send_message(chat_id, "📢 أرسل الآن الرسالة (نص، صورة، فيديو، ملف) التي تريد إرسالها لجميع المجموعات والأعضاء:")

    elif data == "admin_stats":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM groups")
        g_count = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM users")
        u_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM custom_replies")
        r_count = c.fetchone()[0]
        conn.close()
        msg = f"📊 **إحصائيات البوت الحالية:**\n\n👥 عدد المستخدمين: `{u_count}`\n🏰 عدد المجموعات: `{g_count}`\n💬 عدد الردود المخصصة: `{r_count}`"
        bot.send_message(chat_id, msg, parse_mode="Markdown")

    elif data == "admin_add_admin":
        admin_states[user_id] = "wait_add_admin"
        bot.send_message(chat_id, "أرسل المعرف العددي (ID) للأدمن الجديد:")

    elif data == "admin_del_admin":
        admin_states[user_id] = "wait_del_admin"
        bot.send_message(chat_id, "أرسل المعرف العددي (ID) للأدمن المراد حذفه:")

    elif data == "admin_add_reply":
        admin_states[user_id] = "wait_add_reply_kw"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد الجديد:")

    elif data == "admin_del_reply":
        admin_states[user_id] = "wait_del_reply"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد المراد حذفه:")

    elif data == "admin_add_question":
        admin_states[user_id] = "wait_add_question"
        bot.send_message(chat_id, "أرسل نص السؤال الجديد:")

    elif data == "admin_add_riddle":
        admin_states[user_id] = "wait_add_riddle"
        bot.send_message(chat_id, "أرسل الحزورة والإجابة بالصيغة التالية:\n`الحزورة | الإجابة`", parse_mode="Markdown")

    elif data == "admin_toggle_mute":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (chat_id,))
        exists = c.fetchone()
        if exists:
            c.execute("DELETE FROM muted_groups WHERE chat_id = ?", (chat_id,))
            bot.send_message(chat_id, "🔊 تم إلغاء كتم البوت في هذه المجموعة!")
        else:
            c.execute("INSERT INTO muted_groups VALUES (?)", (chat_id,))
            bot.send_message(chat_id, "🔇 تم كتم البوت في هذه المجموعة!")
        conn.commit()
        conn.close()

    elif data == "admin_toggle_gemini":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM gemini_groups WHERE chat_id = ?", (chat_id,))
        exists = c.fetchone()
        if exists:
            c.execute("DELETE FROM gemini_groups WHERE chat_id = ?", (chat_id,))
            bot.send_message(chat_id, "❌ تم تعطيل خدمات جيمني والذكاء الاصطناعي في هذه المجموعة.")
        else:
            c.execute("INSERT INTO gemini_groups VALUES (?)", (chat_id,))
            bot.send_message(chat_id, "✅ تم تفعيل خدمات جيمني والذكاء الاصطناعي في هذه المجموعة!")
        conn.commit()
        conn.close()

# ==================== معالجة أزرار XO والألعاب ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('xocell_') or call.data.startswith('xojoin_') or call.data.startswith('xocancel_'))
def handle_xo_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    chat_id = call.message.chat.id
    user_id = call.from_user.id
    user_name = call.from_user.first_name
    data = call.data

    if data.startswith("xojoin_"):
        creator_id = int(data.replace("xojoin_", ""))
        if user_id == creator_id:
            bot.send_message(chat_id, "⚠️ لا يمكنك منافسة نفسك!")
            return
        
        bal = get_balance(user_id)
        if bal < 50:
            bot.send_message(chat_id, f"❌ رصيدك لا يكفي لدخول اللعبة! تحتاج 50 ليرة (رصيدك: {bal}).")
            return

        update_balance(user_id, -50)
        update_balance(creator_id, -50)

        xo_games[chat_id] = {
            'board': [" "] * 9,
            'player_x': creator_id,
            'player_o': user_id,
            'player_x_name': call.message.text.split('\n')[1].replace('المنافس الأول: ', ''),
            'player_o_name': user_name,
            'current_turn': creator_id
        }

        game = xo_games[chat_id]
        msg = f"🎮 **بدأت لعبة XO!**\n❌ {game['player_x_name']} ضد ⭕ {game['player_o_name']}\n\n👉 الدور الآن لـ: **{game['player_x_name']}** (❌)"
        bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=get_xo_keyboard(game['board'], creator_id, game['player_x_name'], user_id, user_name), parse_mode="Markdown")

    elif data.startswith("xocancel_"):
        creator_id = int(data.replace("xocancel_", ""))
        if user_id == creator_id or is_admin(user_id):
            if chat_id in xo_games:
                del xo_games[chat_id]
            bot.edit_message_text("❌ تم إلغاء لعبة XO.", chat_id, call.message.message_id)

    elif data.startswith("xocell_"):
        idx = int(data.replace("xocell_", ""))
        if chat_id not in xo_games:
            bot.send_message(chat_id, "⚠️ هذه اللعبة انتهت أو غير موجودة! ابدأ لعبة جديدة بإرسال `اكسني`", parse_mode="Markdown")
            return

        game = xo_games[chat_id]
        if user_id != game['current_turn']:
            bot.send_message(chat_id, "⚠️ ليس دورك الآن!")
            return

        if game['board'][idx] != " ":
            bot.send_message(chat_id, "⚠️ هذه الخانة محجوزة بالفعل!")
            return

        symbol = "❌" if user_id == game['player_x'] else "⭕"
        game['board'][idx] = symbol

        winner_symbol = check_xo_winner(game['board'])
        if winner_symbol:
            if winner_symbol == "DRAW":
                update_balance(game['player_x'], 50)
                update_balance(game['player_o'], 50)
                msg = f"🤝 **تعادل في لعبة XO!**\nتم إعادة رسوم الدخول (50 ليرة) للاعبين."
            else:
                winner_id = game['player_x'] if winner_symbol == "❌" else game['player_o']
                winner_name = game['player_x_name'] if winner_symbol == "❌" else game['player_o_name']
                update_balance(winner_id, 200)
                msg = f"🎉 **الفائز في لعبة XO هو {winner_name} ({winner_symbol})!**\nربح جائزة القدرة **200 ليرة وهمية**! 🏆"

            bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=get_xo_keyboard(game['board'], game['player_x'], game['player_x_name'], game['player_o'], game['player_o_name']), parse_mode="Markdown")
            del xo_games[chat_id]
            return

        next_turn = game['player_o'] if user_id == game['player_x'] else game['player_x']
        next_name = game['player_o_name'] if user_id == game['player_x'] else game['player_x_name']
        game['current_turn'] = next_turn

        msg = f"🎮 **لعبة XO مستمرة!**\n❌ {game['player_x_name']} ضد ⭕ {game['player_o_name']}\n\n👉 الدور الآن لـ: **{next_name}** ({'❌' if next_turn == game['player_x'] else '⭕'})"
        bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=get_xo_keyboard(game['board'], game['player_x'], game['player_x_name'], game['player_o'], game['player_o_name']), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_games_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    action = call.data.replace('game_', '')

    if action == "xo":
        bal = get_balance(user_id)
        if bal < 50:
            bot.send_message(chat_id, "❌ رسوم دخول XO هي 50 ليرة ورصيدك لا يكفي!")
            return
        bot.send_message(chat_id, f"🎮 **لعبة XO جديدة!**\nالمنافس الأول: {call.from_user.first_name}\n💡 رسوم الدخول: 50 ليرة | جائزة الفائز: 200 ليرة\nاضغط للانضمام والمنافسة:", reply_markup=get_xo_keyboard(None, user_id, call.from_user.first_name), parse_mode="Markdown")

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
        op = random.choice(['+', '-', '*'])
        ans = eval(f"{n1} {op} {n2}")
        active_math_games[chat_id] = ans
        bot.send_message(chat_id, f"🧮 **تحدي الرياضيات السريع:**\nكم الناتج: `{n1} {op} {n2}` ؟\nأول شخص يكتب الناتج يربح **50 ليرة**!", parse_mode="Markdown")

    elif action == "guess":
        target = random.randint(1, 20)
        active_guess_games[chat_id] = target
        bot.send_message(chat_id, "🎯 **تحدي خمن الرقم:**\nخمنت رقم من `1` إلى `20`!\nأول شخص يكتب الرقم الصحيح يربح **50 ليرة**.", parse_mode="Markdown")

    elif action == "wheel":
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_wheel FROM wheel_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            bot.send_message(chat_id, f"🎡 العجلة مقيدة حالياً! انتظر `{remaining_secs}` ثانية قبل إدارتها مجدداً.", parse_mode="Markdown")
            conn.close()
            return

        bal = get_balance(user_id)
        if bal < 50:
            bot.send_message(chat_id, "❌ تكلفة تدوير العجلة هي 50 ليرة ورصيدك لا يكفي!")
            conn.close()
            return

        update_balance(user_id, -50)
        c.execute("INSERT INTO wheel_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_wheel = ?", (user_id, current_time, current_time))
        conn.commit()
        conn.close()

        is_win = random.choices([True, False], weights=[70, 30])[0]
        if is_win:
            prizes = [50, 100, 200, 500, 1000, 2000]
            weights = [35, 25, 20, 12, 6, 2]
            won = random.choices(prizes, weights=weights)[0]
            update_balance(user_id, won)
            bot.send_message(chat_id, f"🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وربحت **{won}** ليرة وهمية! 🎉", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "🎡 **درت عجلة الحظ!**\nتم خصم 50 ليرة... وخسرت! حظاً أفضل في المرة القادمة 💔", parse_mode="Markdown")

# ==================== التشغيل الرئيسي ====================
if __name__ == "__main__":
    print("🤖 Bot is starting up...")
    keep_alive()
    print("🌐 Keep-alive web server is running on Render port.")
    bot.infinity_polling(skip_pending=True)
