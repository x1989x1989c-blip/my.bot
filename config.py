import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8929555984:AAEVLnYzg6wVmFrpuxICgoLg7t0ttFJcdTg")
SUPER_ADMIN_ID = int(os.getenv("ADMIN_ID", "8903157513"))
PORT = int(os.getenv("PORT", 8080))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-render-app-name.onrender.com")

DB_FILE = "bot_database.db"

# قيم عجلة الحظ
WHEEL_VALUES = [0, 5, 10, 15, 25, 50, 100, 500, 10000]
