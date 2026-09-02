import sqlite3

DB_NAME = "bot_database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """إنشاء جميع جداول قاعدة البيانات والبيانات الافتراضية عند بدء التشغيل"""
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
            bot_balance REAL DEFAULT 0.0,
            site_balance REAL DEFAULT 0.0,
            ichancy_user TEXT DEFAULT 'غير محدد',
            ichancy_pass TEXT DEFAULT 'غير محدد',
            wheel_spins INTEGER DEFAULT 1,
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
    
    # 3. جدول المسؤولين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'full'
        )
    ''')

    # 4. جدول المعاملات والطلبات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            method TEXT,
            account_or_txid TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. جدول طرق الدفع
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_methods (
            name TEXT PRIMARY KEY,
            details TEXT
        )
    ''')

    # 6. جدول الجوائز والسجلات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reward_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # إدراج الإعدادات الافتراضية للمنع من الأخطاء
    default_settings = [
        ('maintenance', '0'),
        ('mandatory_channel', ''),
        ('channel_link', 'https://t.me/'),
        ('welcome_bonus', '0.0'),
        ('deposit_bonus_pct', '0.0'),
        ('wheel_prob', '[30.0, 25.0, 20.0, 10.0, 8.0, 5.0, 1.8, 0.19, 0.01]')
    ]
    
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
    # إضافة حساب الآدمن تلقائياً
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
