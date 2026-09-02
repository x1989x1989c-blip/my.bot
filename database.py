import sqlite3

DB_NAME = "bot_database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """إنشاء جميع جداول قاعدة البيانات بجميع الميزات والبيانات الافتراضية"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            phone TEXT,
            is_verified INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            bot_balance REAL DEFAULT 0.0,
            site_balance REAL DEFAULT 0.0,
            ichancy_user TEXT DEFAULT 'لم ينشأ بعد',
            ichancy_pass TEXT DEFAULT 'لم ينشأ بعد',
            wheel_spins INTEGER DEFAULT 0,
            wheel_spins_done INTEGER DEFAULT 0,
            referred_by INTEGER,
            active_referrals INTEGER DEFAULT 0,
            total_deposited REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. جدول الإعدادات العامة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # 3. جدول المسؤولين والأدمنية والأدوار
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'full' -- 'full', 'support', 'limited'
        )
    ''')

    # 4. جدول المعاملات والطلبات (شحن وسحب)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT, -- 'deposit', 'withdraw', 'site_dep', 'site_with'
            amount REAL,
            method TEXT,
            account_or_txid TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. جدول طرق وسائل الشحن والسحب
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_methods (
            name TEXT PRIMARY KEY,
            details TEXT
        )
    ''')

    # 6. جدول أكواد الهدايا
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            value REAL,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')

    # 7. سجل استخدام الأكواد
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_code_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            user_id INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. جدول العروض الحالية
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. جدول التذاكر ورسائل الدعم والإنذارات/الإصابات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT DEFAULT 'support', -- 'support', 'injury'
            text TEXT,
            photo_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # إدراج الإعدادات الافتراضية
    default_settings = [
        ('maintenance', '0'),
        ('mandatory_channel', ''),
        ('channel_name', 'قناة البوت الرسمية'),
        ('channel_link', 'https://t.me/'),
        ('welcome_bonus', '0.0'),
        ('deposit_bonus_pct', '0.0'),
        ('matching_bonus_pct', '5.0'), # بونص إضافي عند تشابه آخر رقمين في رقم العملية
        ('wheel_prob', '[30.0, 25.0, 20.0, 10.0, 8.0, 5.0, 1.8, 0.19, 0.01]')
    ]
    
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
    # إدراج طرق الدفع الافتراضية
    cursor.execute("INSERT OR IGNORE INTO payment_methods (name, details) VALUES (?, ?)", 
                   ('شام كاش', 'حساب شام كاش: 09XXXXXXX'))
    cursor.execute("INSERT OR IGNORE INTO payment_methods (name, details) VALUES (?, ?)", 
                   ('سيرياتيل كاش', 'حساب سيرياتيل كاش: 09XXXXXXX'))

    # إضافة حساب الأدمن الأساسي تلقائياً
    cursor.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, ?)", (8903157513, 'full'))

    conn.commit()
    conn.close()

def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = False):
    """دالة تنفيذ الاستعلامات في قاعدة البيانات"""
    conn = get_connection()
    cursor = conn.cursor()
    result = None
    
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            result = cursor.lastrowid
        elif fetchone:
            row = cursor.fetchone()
            result = dict(row) if row else None
        elif fetchall:
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    return result
