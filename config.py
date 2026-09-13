import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))

# Время работы МСК
WORK_START = "07:40"
WORK_STOP = "17:45"

# Выплаты
CRYPTO_BOT = "@CryptoBot"
SUPPORT = "@supppot_teams"
