import os
import random
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_NAME = "database.db"

# 1. إنشاء قاعدة البيانات وتجهيز جدول خوارزميات الألعاب
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_settings (
            game_id TEXT PRIMARY KEY,
            win_rate INTEGER DEFAULT 30,       -- نسبة الربح المئوية (مثلاً 30%)
            algorithm_type TEXT DEFAULT 'normal', -- نوع الخوارزمية (normal, hard, lucky)
            is_active INTEGER DEFAULT 1         -- حالة اللعبة (1: مفعلة, 0: معطلة)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# -------------------------------------------------------------
# 2. التوجيه الديناميكي (استقبال أي لعبة جديدة تلقائياً)
# -------------------------------------------------------------

# الصفحة الرئيسية (صالة الألعاب AUREX)
@app.route('/')
def lobby():
    return render_template('index.html')

# استقبال أي لعبة تلقائياً عبر الرابط: /game/اسم_الملف
@app.route('/game/<game_name>')
def serve_game(game_name):
    template_file = f"{game_name}.html"
    
    # التأكد من وجود ملف اللعبة داخل مجلد templates
    if os.path.exists(os.path.join('templates', template_file)):
        return render_template(template_file)
    else:
        return "<h1>404 - اللعبة غير موجودة في مجلد templates</h1>", 404

# -------------------------------------------------------------
# 3. محرك الخوارزميات ورصد نتائج الألعاب (API للواجهات)
# -------------------------------------------------------------

@app.route('/api/play/<game_name>', methods=['POST'])
def process_game_play(game_name):
    data = request.json or {}
    user_id = data.get('user_id')
    bet_amount = data.get('bet', 0)

    # جلب الخوارزمية الخاصة بذه اللعبة المحددة
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT win_rate, algorithm_type, is_active FROM game_settings WHERE game_id = ?', (game_name,))
    setting = cursor.fetchone()
    conn.close()

    # قيم افتراضية في حال لم تكن اللعبة مسجلة في التحكم بعد
    win_rate = setting[0] if setting else 30
    algo_type = setting[1] if setting else 'normal'
    is_active = setting[2] if setting else 1

    if not is_active:
        return jsonify({'success': False, 'message': 'اللعبة معطلة حالياً من الإدارة'}), 403

    # تطبيق الخوارزمية بناءً على إعدادات اللعبة
    roll = random.randint(1, 100)
    is_win = False

    if algo_type == 'normal':
        # ربح بناءً على النسبة المئوية المحددة مباشرة
        is_win = (roll <= win_rate)
        
    elif algo_type == 'hard':
        # خوارزمية صارمة: تقليل نسبة الربح للمراهنات العالية
        actual_rate = win_rate // 2 if bet_amount > 1000 else win_rate
        is_win = (roll <= actual_rate)
        
    elif algo_type == 'lucky':
        # خوارزمية مرنة: تزيد فرصة الربح عند النسبة المحددة
        is_win = (roll <= min(win_rate + 15, 95))

    return jsonify({
        'success': True,
        'game': game_name,
        'is_win': is_win,
        'roll_value': roll,
        'applied_rate': win_rate
    })

# -------------------------------------------------------------
# 4. واجهة البرمجة للتعديل من داخل البوت (API للمسؤول)
# -------------------------------------------------------------

@app.route('/api/admin/update_game', methods=['POST'])
def update_game_algorithm():
    data = request.json or {}
    game_id = data.get('game_id')           # اسم اللعبة (مثلاً: wheel أو game1)
    win_rate = data.get('win_rate')         # نسبة الربح الجديدة (1-100)
    algo_type = data.get('algorithm_type', 'normal') # نوع الخوارزمية

    if not game_id or win_rate is None:
        return jsonify({'status': 'error', 'message': 'بيانات ناقصة'}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO game_settings (game_id, win_rate, algorithm_type)
        VALUES (?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET
            win_rate = excluded.win_rate,
            algorithm_type = excluded.algorithm_type
    ''', (game_id, win_rate, algo_type))
    conn.commit()
    conn.close()

    return jsonify({
        'status': 'success',
        'message': f'تم تحديث خوارزمية لعبة {game_id} بنجاح!',
        'new_win_rate': win_rate,
        'algo_type': algo_type
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
