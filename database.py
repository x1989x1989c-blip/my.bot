import sqlite3

DB_NAME = "bot_database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """إنشاء جداول قاعدة البيانات عند بدء التشغيل"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            spins_left INTEGER DEFAULT 1,
            points INTEGER DEFAULT 0,
            last_spin TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول الجوائز والسجلات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reward_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
