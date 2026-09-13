from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(user: dict) -> ReplyKeyboardMarkup:
    is_online = user.get('is_online', 0)
    online_btn = "🔴 Оффлайн" if is_online else "⭐ Онлайн"
    
    buttons = [
        [KeyboardButton(text=online_btn), KeyboardButton(text="ℹ️ Профиль")],
        [KeyboardButton(text="💲 Баланс"), KeyboardButton(text="➕ Сдать WA")],
        [KeyboardButton(text="➕ Сдать WA Business"), KeyboardButton(text="📊 Мои номера")],
        [KeyboardButton(text="✉️ Общая очередь"), KeyboardButton(text="💡 Информация")],
        [KeyboardButton(text="⚠️ Помощь")],
    ]
    
    role = user.get('role', 'user')
    if role in ('admin',):
        buttons.append([KeyboardButton(text="🔧 Админка")])
    if role == 'vbiv':
        buttons.append([KeyboardButton(text="🎯 Вбив")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def submit_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚡ Код"), KeyboardButton(text="⚡ QR")],
        [KeyboardButton(text="➡️ Назад")]
    ], resize_keyboard=True)

def tariff_kb(price_normal, price_fast) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"⚡ Обычная аренда ({price_normal}$)")],
        [KeyboardButton(text=f"⚡ Без очереди ({price_fast}$)")],
        [KeyboardButton(text="➡️ Назад")]
    ], resize_keyboard=True)

def balance_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➡️ Назад"), KeyboardButton(text="💲 Вывод")]
    ], resize_keyboard=True)

def profile_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➡️ Назад"), KeyboardButton(text="💲 Обновить")]
    ], resize_keyboard=True)

def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➡️ Назад")]
    ], resize_keyboard=True)

def numbers_nav_kb(page: int, total: int) -> ReplyKeyboardMarkup:
    buttons = []
    nav = []
    if page > 1:
        nav.append(KeyboardButton(text="⬅️ Назад по списку"))
    nav.append(KeyboardButton(text=f"{page}/{total}"))
    if page < total:
        nav.append(KeyboardButton(text="➡️ Вперёд"))
    buttons.append(nav)
    buttons.append([KeyboardButton(text="➡️ Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# АДМИНКА
def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📥 Взять номер"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💰 Изменить прайс"), KeyboardButton(text="👥 Пользователи")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🟢 Старт/Стоп ворк")],
        [KeyboardButton(text="📋 Логи"), KeyboardButton(text="🎯 Назначить вбива")],
        [KeyboardButton(text="➡️ Назад")]
    ], resize_keyboard=True)

def vbiv_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📥 Взять номер")],
        [KeyboardButton(text="➡️ Назад")]
    ], resize_keyboard=True)

def number_result_kb(number_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Встал", callback_data=f"num_stood_{number_id}"),
            InlineKeyboardButton(text="❌ Не встал", callback_data=f"num_notstood_{number_id}"),
        ],
        [InlineKeyboardButton(text="⚡ Момент слёт", callback_data=f"num_slot_{number_id}")]
    ])

def user_manage_kb(tg_id: int, is_banned: int) -> InlineKeyboardMarkup:
    ban_text = "✅ Разбанить" if is_banned else "🚫 Забанить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=ban_text, callback_data=f"user_ban_{tg_id}"),
            InlineKeyboardButton(text="⭐ Приоритет", callback_data=f"user_priority_{tg_id}"),
        ],
        [InlineKeyboardButton(text="🛒 Доступ покупателя", callback_data=f"user_buyer_{tg_id}")]
    ])
