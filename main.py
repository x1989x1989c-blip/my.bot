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
        CREATE TABLE IF NOT EXISTS item_steal_cooldowns (
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

    # إضافة أصناف المتجر والمطعم
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('علبة متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('متة', 50)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كيلو سكر', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('شاورما', 100)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('برغر', 120)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('سكالوب', 150)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('كبة', 80)")
    cursor.execute("INSERT OR IGNORE INTO store VALUES ('بيتزا', 200)")

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

    # 2. إدخال 50 حزورة
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

    # 3. إدخال الردود التلقائية المخصصة والجديدة باللهجة السورية
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
        # الردود الجديدة باللهجة السورية المطلوب إضافتها
        ("فرفوش", "يا عيون وشرايين فرفوش أنت! شو تطلب أؤمرني يا غالي 😉"),
        ("فرفوش", "فرفوش بالخدمة والروق والسعادة! أهلاً وسهلاً يا أكابر ✨"),
        ("فرفوشي", "روح قلب فرفوشي أنت! تسلملي هالحلة والطلة ❤️"),
        ("فرفوشي", "لك تقبرني كلمة فرفوشي من تمك.. طالعة متل العسل 🍯"),
        ("فرفوشتي", "نعم يا عمري ونبض قلبي.. فرفوشتك جاهزة لخدمتك 😘"),
        ("فرفوشتي", "لك يا دلي أنا.. فرفوشتك على خطك شو يؤمر الجميل؟ 💕"),
        ("فرفشني", "ولك تكرم عينك! هي أطيب نكتة وفرفشة لعيونك الحلوة 😂"),
        ("فرفشني", "بدك فرفشة؟ كاسة متة مع شوية ضحك بتصير بألف خير وروقان 😉"),
        ("باي", "باي يا حلو.. لا تطول علينا بنشتاقلك ترا! 👋❤️"),
        ("باي", "الله معك يا غالي، ودير بالك على حالك وبنطر رجعتك 😉"),
        ("سلام", "وعليكم السلام ورحمة الله، يا مية أهلاً وسهلاً نورت المجموعه! ✨"),
        ("سلام", "سلامات يا طيب.. ألف سلامة ونورتنا وجودك مكسب 🌸")
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
            ("في الفندق المهجور قُتل السائح 'روبرت'. المرشد (باسم) يقول كان يجهز الخريطة، المصور (زياد) يقول كان يبدل العدسة، والطباخ (طارق) يقول كان يشوي.", "زياد", "باسم، زياد، طارق")
        ]
        for st, kl, sp in crimes_list:
            cursor.execute("SELECT 1 FROM crime_stories WHERE story = ?", (st,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (st, kl, sp))

    # 5. أسئلة المسلسلات
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

# ==================== نظام جيمني المطور والانشاء الدقيق ====================
def fetch_ai_answer(question):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.9"
    }

    sys_prompt = "أنت مساعد ذكي واسمك فرفوش، تعمل بنظام Gemini المتطور. أجب عن سؤال المستخدم باللغة العربية بشكل دقيق ومباشر ومنطقي جداً بناءً على ما طلبه حصراً دون تعذر. يمنع منعاً باتاً ذكر أي روابط أو خروج عن موضوع السؤال أو ذكر أي مصادر."

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
            res = requests.post("https://text.pollinations.ai/", json=payload, headers={**headers, "Content-Type": "application/json"}, timeout=8)
            if res.status_code == 200 and res.text:
                ans = clean_urls_and_sources(res.text)
                if ans and len(ans) > 5 and not any(bad in ans.lower() for bad in ["timed out", "error", "504", "403", "html", "cloudflare", "bad gateway"]):
                    return ans
        except Exception:
            continue

    return "أهلاً بك يا غالي! تفضل بتكرار سؤالك وسأجيبك فوراً بدقة عالية."

def generate_image_pollinations(prompt):
    models = ["flux", "flux-realism", "any-dark"]
    encoded_prompt = urllib.parse.quote(prompt)
    
    for m in models:
        try:
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&seed={random.randint(1, 999999)}&nologo=true&model={m}"
            res = requests.get(url, timeout=18)
            if res.status_code == 200 and len(res.content) > 2000:
                return res.content
        except Exception:
            continue
    return None

# ==================== خدمات تحميل الأغاني والفيديو (يوتيوب وسمعني) ====================
def download_and_send_audio(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, f"🔍 **جاري البحث وتحميل الصوت فوراُ...**", parse_mode="Markdown")
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
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        }
    }

    search_targets = [query] if query.startswith("http") else [f"ytsearch1:{query}", f"scsearch1:{query}"]

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
                        bot.delete_message(chat_id, status_msg.message_id)
                        try:
                            os.remove(downloaded_file)
                        except:
                            pass
                        return
        except Exception:
            continue

    bot.edit_message_text("❌ تعذر تحميل الصوت حالياً، تأكد من صحة الرابط أو جرب لاحقاً.", chat_id, status_msg.message_id)

def download_and_send_video(chat_id, query, message_id):
    status_msg = bot.send_message(chat_id, f"🎬 **جاري البحث وتحميل الصوت/الفيديو من يوتيوب...**", parse_mode="Markdown")
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    file_prefix = f"downloads/vid_{int(time.time())}_{random.randint(1000,9999)}"
    output_template = f"{file_prefix}.%(ext)s"

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]',
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'cachedir': False,
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
                for ext in ['mp4', 'mkv', 'webm', 'm4a', 'mp3']:
                    possible_path = f"{file_prefix}.{ext}"
                    if os.path.exists(possible_path):
                        downloaded_file = possible_path
                        break

                if downloaded_file and os.path.exists(downloaded_file):
                    with open(downloaded_file, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, caption=f"🎥 **{title}**", reply_to_message_id=message_id, parse_mode="Markdown")
                    bot.delete_message(chat_id, status_msg.message_id)
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
        "🛡️ **حماية المجموعة:** منع الروابط والمعرفات والتوجيه للأعضاء مع ذكر الاسم عند الحذف.\n"
        "🎮 **ألعاب متطورة:** XO (اكسني مجانية)، رياضيات، خمن الرقم، خمن المسلسل 📺، القاتل 🔪، وعجلة الحظ 🎡.\n"
        "🍽️ **مطعم وسوبرماركت:** أصناف مأكولات، شراء، بيع، إهداء، وسرقة أطعمة فكاهية.\n"
        "🤖 **ذكاء اصطناعي (جيمني الاصلي):** اكتب `عندي سؤال` أو `بدي ساوي صورة [وصف]`.\n"
        "🎵 **تحميل يوتيوب وسمعني:** أرسل كلمة `يوتيوب` أو `سمعني` مع اسم الأغنية وسأحملها لك فوراُ."
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
    if yt_match and not text.startswith("يوتيوب"):
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

    # المطعم وعرض الأصناف
    if text == "مطعم":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = c.fetchall()
        conn.close()
        msg_text = "🍽️ **مطعم وسوبرماركت فرفوش الشامل:**\n\n🍔 **قائمة المأكولات والمشروبات المتوفرة:**\n"
        for name, price in items:
            msg_text += f"• {name} 👈 {price} ليرة\n"
        msg_text += "\n💡 **الأوامر المتاحة:**\n"
        msg_text += "• للشراء: `شراء 1 شاورما`\n"
        msg_text += "• للبيع: `بيع 1 شاورما`\n"
        msg_text += "• للإهداء: بالرد على العضو وكتابة `اهداء 1 شاورما`\n"
        msg_text += "• للسرقة: بالرد على العضو وكتابة `طعميني شاورما` أو `شربني متة`"
        bot.send_message(chat_id, msg_text, parse_mode="Markdown")
        return

    # نظام سرقة الأصناف (طعميني / شربني) - تقييد 20 دقيقة
    if text.startswith("طعميني") or text.startswith("شربني"):
        parts = text.split(maxsplit=1)
        if len(parts) >= 2:
            item_name = parts[1].strip()
            if not message.reply_to_message:
                bot.reply_to(message, "⚠️ لازم تعمل رد (Reply) على رسالة الشخص يلي بدك تسرق منو الأكلة أو المشروب!")
                return

            target_user = message.reply_to_message.from_user
            if target_user.id == user_id:
                bot.reply_to(message, "عم تسرق حالك؟ ما بتزبط بنوب! 🤦‍♂️")
                return
            if target_user.is_bot:
                bot.reply_to(message, "ما فيك تسرق البوت يا حباب 🤖")
                return

            current_time = int(time.time())
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("SELECT last_steal FROM item_steal_cooldowns WHERE user_id = ?", (user_id,))
            row = c.fetchone()

            if row and (current_time - row[0]) < 1200: # 20 دقيقة
                remaining_mins = int((1200 - (current_time - row[0])) / 60) + 1
                funny_cool_msgs = [
                    f"⏳ اهدى شوي يا جوعان! سرقة المأكولات مقيدة كل 20 دقيقة.. فاضل `{remaining_mins}` دقيقة لتشبع كرشك تاني 😂",
                    f"⏳ طوّل بالك! المعدة مكركبة والسرقة مقيدة.. استنى `{remaining_secs}` ثانية أو `{remaining_mins}` دقيقة وارجع جرب ⏱️",
                    f"⏳ روق المانجا! القوانين صارمة.. بقيان `{remaining_mins}` دقيقة حتى يرجع يفتح الموسم 😉"
                ]
                bot.reply_to(message, random.choice(funny_cool_msgs), parse_mode="Markdown")
                conn.close()
                return

            c.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (target_user.id, item_name))
            target_item_row = c.fetchone()

            if not target_item_row or target_item_row[0] <= 0:
                funny_empty_msgs = [
                    f"😂 جيت لتسرق {item_name} من {target_user.first_name} لقيت صحنو فاضي وما معو ولا حبة!",
                    f"😭 {target_user.first_name} مفلس أصلًا وما عندو {item_name}، ارحمو يا زلمة!",
                    f"❌ فتشت جيبتو وصحنو وما لقيت ولا حبة {item_name}... طلعت على الفاضي!"
                ]
                bot.reply_to(message, random.choice(funny_empty_msgs))
                conn.close()
                return

            max_stealable = min(50, target_item_row[0])
            stolen_qty = random.randint(1, max_stealable)

            c.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (stolen_qty, target_user.id, item_name))
            c.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?", (user_id, item_name, stolen_qty, stolen_qty))
            c.execute("INSERT INTO item_steal_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_steal = ?", (user_id, current_time, current_time))
            conn.commit()
            conn.close()

            funny_steal_success = [
                f"🥷 دخلت عالساكت وسرقت **{stolen_qty}** قطعة `{item_name}` من {target_user.first_name} وأكلتهن وهن سخان! صحتين على قلبك 😂❤️",
                f"😋 يا سلام! سحبت **{stolen_qty}** `{item_name}` من {target_user.first_name} وعزمت حالك عليهن، يقطع عمر الهوى شو لذيذة!",
                f"🍗 يا عيب الشوم عليك! طيرتله **{stolen_qty}** `{item_name}` وقعدت تتسلى عليهن.. صحتين وهنا!"
            ]
            bot.reply_to(message, random.choice(funny_steal_success), parse_mode="Markdown")
            return

    # جيمني الأصلي
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

    # لعبة الرهان المحدثة (50% ربح - 50% خسارة - تقييد دقيقة برسائل سورية فكاهية)
    if text.startswith("راهن"):
        current_time = int(time.time())
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT last_bet FROM bet_cooldowns WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if row and (current_time - row[0]) < 60:
            remaining_secs = 60 - (current_time - row[0])
            funny_bet_msgs = [
                f"🎲 روق على جيبتك شوي! المراهنة مقيدة مرة كل دقيقة، استنى `{remaining_secs}` ثانية يا حباب ⏱️",
                f"🎲 القمار بيخرب الديار! هدّي اللعب واستنى `{remaining_secs}` ثانية قبل ما تراهن تاني 😂",
                f"🎲 يا بني اهدى شوي على الرصيد! فاضل `{remaining_secs}` ثانية للرهان الجاي ⏱️"
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

            # 50% ربح - 50% خسارة
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

    # لعبة العجلة المحدثة (50% ربح - 50% خسارة - تقييد دقيقة برسائل سورية فكاهية)
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

        c.execute("INSERT INTO wheel_cooldowns VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_wheel = ?", (user_id, current_time, current_time))
        conn.commit()
        conn.close()

        # 50% ربح و 50% خسارة
        is_win = random.choices([True, False], weights=[50, 50])[0]
        if is_win:
            prizes = [50, 100, 200, 500, 1000, 2000]
            weights = [35, 25, 20, 12, 6, 2]
            won = random.choices(prizes, weights=weights)[0]
            update_balance(user_id, won)
            bot.reply_to(message, f"🎡 **درت عجلة الحظ!**\nوربت **{won}** ليرة وهمية! 🎉", parse_mode="Markdown")
        else:
            bot.reply_to(message, "🎡 **درت عجلة الحظ!**\nللأسف وخسرت! حظاً أفضل في المرة القادمة 💔", parse_mode="Markdown")
        return

    # لعبة XO الرسمية المجانية بالكامل والرابح 100 ليرة
    if text in ["اكسني", "لعبة اكس اوه"]:
        bot.send_message(chat_id, f"🎮 **لعبة XO جديدة (اكسني)!**\nالمنافس الأول: {message.from_user.first_name}\n💡 رسوم الدخول: مجانية 🎁 | جائزة الفائز: 100 ليرة 🪙\nاضغط للانضمام والمنافسة:", reply_markup=get_xo_keyboard(None, user_id, message.from_user.first_name))
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
def send_games_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎮 لعبة XO (مجانية)", callback_data="game_xo"),
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
        bot.send_message(chat_id, f"🎮 لعبة XO جديدة (اكسني)!\nأنشأ اللعبة: {call.from_user.first_name}\n💡 مجانية والرابح يحصل على 100 ليرة!", reply_markup=get_xo_keyboard(None, call.from_user.id, call.from_user.first_name))
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
        else:
            bot.send_message(chat_id, "لا توجد أسئلة مسلسلات مضافة بعد.")
    elif action == "math":
        n1, n2 = random.randint(1, 50), random.randint(1, 50)
        active_math_games[chat_id] = n1 + n2
        bot.send_message(chat_id, f"🧮 كم الناتج: `{n1} + {n2}` ؟", parse_mode="Markdown")
    elif action == "guess":
        active_guess_games[chat_id] = random.randint(1, 20)
        bot.send_message(chat_id, "🎯 خمن رقم من `1` إلى `20`!", parse_mode="Markdown")
    elif action == "wheel":
        bot.send_message(chat_id, "🎡 للعب العجلة أرسل كلمة `عجلة` بالدردشة.")

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

# لعبة XO المجانية - الفائز يحصل على 100 ليرة
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
        bot.edit_message_text(f"🎮 بدأت مباراة XO المجانية!\n❌ {p1_name}\n⭕ {p2_name}\n\n🏆 الفائز سيحصل على 100 ليرة!\nالدور الحالي: {p1_name} (❌)", chat_id, msg_id, reply_markup=get_xo_keyboard(xo_games[msg_id]))
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
            # الفائز يحصل على 100 ليرة وهمية
            update_balance(winner, 100)
            bot.edit_message_text(f"🎉 الفائز باللعبة هو {call.from_user.first_name}! وربح **100 ليرة وهمية**! 🏆", chat_id, msg_id, reply_markup=get_xo_keyboard(game), parse_mode="Markdown")
            del xo_games[msg_id]
        elif " " not in game['board']:
            bot.edit_message_text("🤝 تعادل بين الطرفين! حظاً موفقاً في المرة القادمة.", chat_id, msg_id, reply_markup=get_xo_keyboard(game), parse_mode="Markdown")
            del xo_games[msg_id]
        else:
            game['turn'] = game['player2'] if user_id == game['player1'] else game['player1']
            next_name = game['p2_name'] if game['turn'] == game['player2'] else game['p1_name']
            next_sym = game['symbols'][game['turn']]
            bot.edit_message_text(f"🎮 المباراة مستمرة بين:\n❌ {game['p1_name']}\n⭕ {game['p2_name']}\n\nالدور الحالي: {next_name} ({next_sym})", chat_id, msg_id, reply_markup=get_xo_keyboard(game))

# ==================== لوحة الإدارة الشاملة والإمدادات ====================
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
        types.InlineKeyboardButton("سجل الأصناف 🛒", callback_data="admin_log_store"),
        types.InlineKeyboardButton("سجل الأسئلة ❓", callback_data="admin_log_questions"),
        types.InlineKeyboardButton("سجل الحزازير 🧩", callback_data="admin_log_riddles"),
        types.InlineKeyboardButton("سجل المسلسلات 📺", callback_data="admin_log_series"),
        types.InlineKeyboardButton("سجل الردود 💬", callback_data="admin_log_replies"),
        types.InlineKeyboardButton("سجل إجابات الجرائم 🎯", callback_data="admin_log_crimes"),
        types.InlineKeyboardButton("💰 إضافة رصيد وهمي", callback_data="admin_add_fake_balance"),
        types.InlineKeyboardButton("🤖 منح ميزات جيمني", callback_data="admin_gemini_groups"),
        types.InlineKeyboardButton("🔇 إسكات/تفعيل البوت بالجروبات", callback_data="admin_mute_grp_list"),
        types.InlineKeyboardButton("🚪 مغادرة مجموعة", callback_data="admin_leave_grp"),
        types.InlineKeyboardButton("✉️ رسالة خاصة لجروب", callback_data="admin_send_grp_msg")
    )
    bot.send_message(chat_id, "⚙️ **لوحة التحكم والإدارة الشاملة:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_admin(message.from_user.id):
        show_admin_panel(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel" or call.data.startswith('admin_') or call.data.startswith('grp_') or call.data.startswith('gemini_') or call.data.startswith('sendmsg_grp_'))
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

    # رسالة خاصة لجروب عبر الأزرار
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
        bot.send_message(chat_id, "أرسل الآيدي (ID) الخاص بالمستخدم المراد رفعه أدمن لمنحه كافة الصلاحيات:")
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

    if call.data == "admin_log_store":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT item_name, price FROM store")
        items = [f"السلعة: `{row[0]}` | السعر: `{row[1]}` ليرة" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "🛒 **سجل أصناف المتجر والمطعم:**", items)
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

    if call.data == "admin_log_series":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT id, question, answer FROM series_questions")
        items = [f"ID `{row[0]}`: {row[1]} 👈 المسلسل: `{row[2]}`" for row in c.fetchall()]
        conn.close()
        send_large_text(chat_id, "📺 **سجل مسلسلات خمن:**", items)
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

    if call.data == "admin_del_q":
        admin_states[user_id] = "wait_del_q_id"
        bot.send_message(chat_id, "أرسل ID السؤال المراد حذفه من سجل الأسئلة:")
        return

    if call.data == "admin_del_rep":
        admin_states[user_id] = "wait_del_rep_id"
        bot.send_message(chat_id, "أرسل ID الرد المراد حذفه من سجل الردود:")
        return

    if call.data == "admin_del_crime":
        admin_states[user_id] = "wait_del_crime_id"
        bot.send_message(chat_id, "أرسل ID قصة الجريمة المراد حذفها:")
        return

    if call.data == "admin_del_riddle":
        admin_states[user_id] = "wait_del_riddle_id"
        bot.send_message(chat_id, "أرسل ID الحزورة المراد حذفها:")
        return

    if call.data == "admin_del_store_item":
        admin_states[user_id] = "wait_del_store_item"
        bot.send_message(chat_id, "أرسل اسم الصنف المراد حذفه من المتجر تماماً:")
        return

    if call.data == "admin_del_series":
        admin_states[user_id] = "wait_del_series_id"
        bot.send_message(chat_id, "أرسل ID سؤال المسلسل المراد حذفه:")
        return

    if call.data == "admin_add_series":
        admin_states[user_id] = "wait_series_q"
        bot.send_message(chat_id, "أرسل سؤال/تلميح خمن المسلسل الجديد:")
        return

    if call.data == "admin_mute_grp_list":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT chat_id, title FROM groups")
        groups = c.fetchall()
        c.execute("SELECT chat_id FROM muted_groups")
        muted = [m[0] for m in c.fetchall()]
        conn.close()

        if not groups:
            bot.send_message(chat_id, "لا توجد مجموعات مسجلة حالياً.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for g_id, title in groups:
            status = "🔊 تفعيل البوت" if g_id in muted else "🔇 إسكات البوت"
            markup.add(types.InlineKeyboardButton(f"{status}: {title}", callback_data=f"grp_toggle_mute_{g_id}"))
        bot.send_message(chat_id, "اختر مجموعة للتحكم بإسكات البوت أو تفعيله فيها:", reply_markup=markup)
        return

    if call.data.startswith("grp_toggle_mute_"):
        target_g_id = int(call.data.split("_")[3])
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("SELECT 1 FROM muted_groups WHERE chat_id = ?", (target_g_id,))
        if c.fetchone():
            c.execute("DELETE FROM muted_groups WHERE chat_id = ?", (target_g_id,))
            msg_res = "🔊 تم تفعيل البوت بالمجموعة بنجاح!"
        else:
            c.execute("INSERT INTO muted_groups VALUES (?)", (target_g_id,))
            msg_res = "🔇 تم إسكات البوت في المجموعة بنجاح ولن يستجيب لأي أومر من الأعضاء فيها."
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, msg_res, show_alert=True)
        return

    if call.data == "admin_add_store_item":
        admin_states[user_id] = "wait_store_item_name"
        bot.send_message(chat_id, "أرسل اسم الصنف الجديد المراد إضافته للمتجر:")
        return

    if call.data == "admin_add_crime":
        admin_states[user_id] = "wait_crime_story"
        bot.send_message(chat_id, "أرسل تفاصيل قصة الجريمة الجديدة:")
        return

    if call.data == "admin_add_riddle":
        admin_states[user_id] = "wait_riddle_q"
        bot.send_message(chat_id, "أرسل نص الحزورة الجديدة:")
        return

    if call.data == "admin_add_q":
        admin_states[user_id] = "wait_q_text"
        bot.send_message(chat_id, "أرسل نص السؤال الجديد (اسألني):")
        return

    if call.data == "admin_add_rep":
        admin_states[user_id] = "wait_rep_kw"
        bot.send_message(chat_id, "أرسل الكلمة المفتاحية للرد الجديد:")
        return

    if call.data == "admin_leave_grp":
        admin_states[user_id] = "wait_leave_grp_chatid"
        bot.send_message(chat_id, "أرسل ID المجموعة المراد مغادرتها:")
        return

# ==================== معالجة إدخالات لوحة الإدارة الكاملة ====================
def handle_admin_inputs(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = (message.text or message.caption or "").strip()
    state = admin_states.get(user_id)

    if not state:
        return

    # معالجة إرسال رسالة خاصة لمجموعة عبر الأزرار
    if isinstance(state, dict) and state.get("state") == "wait_custom_grp_msg":
        target_chat_id = state["target_chat_id"]
        try:
            if message.content_type == 'text':
                bot.send_message(target_chat_id, text)
            elif message.content_type == 'photo':
                bot.send_photo(target_chat_id, message.photo[-1].file_id, caption=message.caption or "")
            elif message.content_type == 'video':
                bot.send_video(target_chat_id, message.video.file_id, caption=message.caption or "")
            elif message.content_type == 'sticker':
                bot.send_sticker(target_chat_id, message.sticker.file_id)
            bot.reply_to(message, "✅ تم إرسال الرسالة إلى المجموعة بنجاح!")
        except Exception as e:
            bot.reply_to(message, f"❌ فشل إرسال الرسالة للمجموعة: {e}")
        del admin_states[user_id]
        return

    if state == "wait_add_admin_id":
        if text.isdigit():
            new_admin = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (new_admin,))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم رفع المستخدم `{new_admin}` كـ أدمن بنجاح!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ يرجى إدخال ID صحيح (أرقام فقط).")
        del admin_states[user_id]
        return

    if state == "wait_fake_bal_userid":
        if text.isdigit():
            admin_states[user_id] = {"state": "wait_fake_bal_amount", "target_uid": int(text)}
            bot.send_message(chat_id, f"أرسل الآن المبلغ المراد إضافته لرصيد المستخدم `{text}`:")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
            del admin_states[user_id]
        return

    if isinstance(state, dict) and state.get("state") == "wait_fake_bal_amount":
        target_uid = state["target_uid"]
        if text.lstrip('-').isdigit():
            amt = int(text)
            update_balance(target_uid, amt)
            bot.reply_to(message, f"✅ تم تعديل رصيد المستخدم `{target_uid}` بمبلغ `{amt}` ليرة بنجاح!")
        else:
            bot.reply_to(message, "❌ قيمة المبلغ غير صحيحة.")
        del admin_states[user_id]
        return

    if state == "wait_store_item_name":
        admin_states[user_id] = {"state": "wait_store_item_price", "item_name": text}
        bot.send_message(chat_id, f"أرسل سعر الصنف (`{text}`):")
        return

    if isinstance(state, dict) and state.get("state") == "wait_store_item_price":
        item_name = state["item_name"]
        if text.isdigit():
            price = int(text)
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("INSERT INTO store (item_name, price) VALUES (?, ?) ON CONFLICT(item_name) DO UPDATE SET price = ?", (item_name, price, price))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"✅ تم إضافة/تحديث الصنف `{item_name}` بسعر `{price}` ليرة بنجاح!")
        else:
            bot.reply_to(message, "❌ السعر يجب أن يكون أرقاماً فقط.")
        del admin_states[user_id]
        return

    if state == "wait_del_store_item":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM store WHERE item_name = ?", (text,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"🗑️ تم حذف الصنف `{text}` من المتجر بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_crime_story":
        admin_states[user_id] = {"state": "wait_crime_killer", "story": text}
        bot.send_message(chat_id, "أرسل اسم القاتل الصحيح للجريمة:")
        return

    if isinstance(state, dict) and state.get("state") == "wait_crime_killer":
        admin_states[user_id] = {"state": "wait_crime_suspects", "story": state["story"], "killer": text}
        bot.send_message(chat_id, "أرسل المشتبه بهم يفصل بينهم فاصلة (مثال: رامي، شادي، ماهر):")
        return

    if isinstance(state, dict) and state.get("state") == "wait_crime_suspects":
        story = state["story"]
        killer = state["killer"]
        suspects = text
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO crime_stories (story, killer, suspects) VALUES (?, ?, ?)", (story, killer, suspects))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة قصة الجريمة بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_del_crime_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM crime_stories WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الجريمة ID `{text}` بنجاح!")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
        del admin_states[user_id]
        return

    if state == "wait_riddle_q":
        admin_states[user_id] = {"state": "wait_riddle_a", "question": text}
        bot.send_message(chat_id, "أرسل إجابة الحزورة:")
        return

    if isinstance(state, dict) and state.get("state") == "wait_riddle_a":
        q = state["question"]
        a = text
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO riddles (question, answer) VALUES (?, ?)", (q, a))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة الحزورة بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_del_riddle_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM riddles WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الحزورة ID `{text}` بنجاح!")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
        del admin_states[user_id]
        return

    if state == "wait_q_text":
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO questions (question) VALUES (?)", (text,))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة السؤال بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_del_q_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM questions WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف السؤال ID `{text}` بنجاح!")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
        del admin_states[user_id]
        return

    if state == "wait_rep_kw":
        admin_states[user_id] = {"state": "wait_rep_ans", "kw": text}
        bot.send_message(chat_id, f"أرسل الرد للكلمة المفتاحية (`{text}`):")
        return

    if isinstance(state, dict) and state.get("state") == "wait_rep_ans":
        kw = state["kw"]
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        
        m_type = 'text'
        f_id = None
        if message.content_type == 'sticker':
            m_type = 'sticker'
            f_id = message.sticker.file_id
        elif message.content_type == 'photo':
            m_type = 'photo'
            f_id = message.photo[-1].file_id
        elif message.content_type == 'video':
            m_type = 'video'
            f_id = message.video.file_id

        c.execute("INSERT INTO custom_replies (keyword, response, media_type, file_id) VALUES (?, ?, ?, ?)", (kw, text, m_type, f_id))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ تم إضافة الرد المخصص للكلمة `{kw}` بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_del_rep_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM custom_replies WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف الرد ID `{text}` بنجاح!")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
        del admin_states[user_id]
        return

    if state == "wait_series_q":
        admin_states[user_id] = {"state": "wait_series_a", "question": text}
        bot.send_message(chat_id, "أرسل اسم المسلسل الصحيح:")
        return

    if isinstance(state, dict) and state.get("state") == "wait_series_a":
        sq = state["question"]
        sa = text
        conn = sqlite3.connect("bot_data.db")
        c = conn.cursor()
        c.execute("INSERT INTO series_questions (question, answer) VALUES (?, ?)", (sq, sa))
        conn.commit()
        conn.close()
        bot.reply_to(message, "✅ تم إضافة مسلسل جديد لسلسلة خمن المسلسل بنجاح!")
        del admin_states[user_id]
        return

    if state == "wait_del_series_id":
        if text.isdigit():
            conn = sqlite3.connect("bot_data.db")
            c = conn.cursor()
            c.execute("DELETE FROM series_questions WHERE id = ?", (int(text),))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🗑️ تم حذف سؤال المسلسل ID `{text}` بنجاح!")
        else:
            bot.reply_to(message, "❌ ID غير صحيح.")
        del admin_states[user_id]
        return

    if state == "wait_leave_grp_chatid":
        try:
            target_gid = int(text)
            bot.leave_chat(target_gid)
            bot.reply_to(message, f"🚪 تم مغادرة المجموعة `{target_gid}` بنجاح!")
        except Exception as e:
            bot.reply_to(message, f"❌ تعذر مغادرة المجموعة: {e}")
        del admin_states[user_id]
        return

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    keep_alive()
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            time.sleep(3)
