from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import *
from keyboards import *
from config import SUPPORT

router = Router()

class SubmitWA(StatesGroup):
    type_ = State()
    tariff = State()
    phone = State()

# ───── СТАРТ ─────
@router.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_or_create_user(msg.from_user.id, msg.from_user.username)
    if user['is_banned']:
        return await msg.answer("🚫 Вы заблокированы.")
    await msg.answer("🌐 Добро пожаловать в UNIVERSE WA BOT!", reply_markup=main_menu(user))

# ───── ОНЛАЙН/ОФФЛАЙН ─────
@router.message(F.text.in_(["⭐ Онлайн", "🔴 Оффлайн"]))
async def toggle_online(msg: Message):
    user = await get_user(msg.from_user.id)
    new_status = 0 if user['is_online'] else 1
    await update_user(msg.from_user.id, is_online=new_status)
    user['is_online'] = new_status
    if new_status:
        await msg.answer("✅ Вы перешли в статус Онлайн. Ваши номера снова доступны покупателям.", reply_markup=main_menu(user))
    else:
        await msg.answer("🚫 Вы перешли в статус Оффлайн. Ваши номера остаются в очереди, но не будут выдаваться покупателям.", reply_markup=main_menu(user))

# ───── ПРОФИЛЬ ─────
@router.message(F.text == "ℹ️ Профиль")
async def profile(msg: Message):
    user = await get_user(msg.from_user.id)
    stats = await get_user_stats(msg.from_user.id)
    
    total = stats.get('total') or 0
    stood = stats.get('stood') or 0
    percent = round((stood / total * 100), 1) if total > 0 else 0
    
    text = (
        f"ℹ️ ПРОФИЛЬ ПРОДАВЦА\n\n"
        f"ID: {user['tg_id']}\n"
        f"User: @{user['username'] or '-'}\n"
        f"Роль: {user['role']}\n"
        f"Зарегистрирован: {user['registered_at'][:16]}\n\n"
        f"🔄 ПРИОРИТЕТ\n{'✅ Есть' if user['has_priority'] else '❌ Нет'}\n\n"
        f"🛡 Доступ покупателя: {'✅ Есть' if user['buyer_access'] else '❌ Нет'}\n\n"
        f"📊 СТАТИСТИКА СЕГОДНЯ:\n"
        f"— Сдано: {stats.get('total_today') or 0}\n"
        f"— Встало: {stats.get('stood_today') or 0}\n"
        f"— Подтверждено: {stats.get('confirmed_today') or 0}\n\n"
        f"📊 ВСЯ СТАТИСТИКА\n"
        f"— Всего сдано: {total}\n"
        f"— Встало: {stood}\n"
        f"— Не встало: {stats.get('not_stood') or 0}\n"
        f"— Момент слётов: {stats.get('moment_slot') or 0}\n"
        f"— Процент вставания: {percent}%"
    )
    await msg.answer(text, reply_markup=profile_kb())

# ───── БАЛАНС ─────
@router.message(F.text == "💲 Баланс")
async def balance(msg: Message):
    user = await get_user(msg.from_user.id)
    min_pay = await get_setting('min_payout')
    text = (
        f"💲 Баланс: {user['balance']:.2f} $\n\n"
        f"Минимальный вывод: {min_pay} $\n"
        f"Выплата: чек в @CryptoBot (USDT)."
    )
    await msg.answer(text, reply_markup=balance_kb())

@router.message(F.text == "💲 Вывод")
async def payout(msg: Message):
    user = await get_user(msg.from_user.id)
    min_pay = float(await get_setting('min_payout'))
    if user['balance'] < min_pay:
        return await msg.answer(f"❌ Минимальный вывод {min_pay}$. Ваш баланс: {user['balance']:.2f}$")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO payouts (user_id, amount) VALUES (?,?)", (msg.from_user.id, user['balance']))
        await db.commit()
    await msg.answer(f"✅ Заявка на вывод {user['balance']:.2f}$ отправлена. Ожидайте.")

# ───── СДАТЬ WA ─────
@router.message(F.text.in_(["➕ Сдать WA", "➕ Сдать WA Business"]))
async def submit_wa_start(msg: Message, state: FSMContext):
    work = await get_setting('work_active')
    if work != '1':
        return await msg.answer("⛔ Приём номеров остановлен. Ожидайте старта ворка.")
    
    is_business = "Business" in msg.text
    await state.update_data(is_business=is_business)
    await state.set_state(SubmitWA.type_)
    await msg.answer(
        "Выберите тип сдачи: «Код» (номер) или «QR» ‼️\n\n"
        "Принимаем только рег ❗\n"
        "ℹ️ Ваш номер могут поставить по связи или по переносу.",
        reply_markup=submit_type_kb()
    )

@router.message(SubmitWA.type_, F.text.in_(["⚡ Код", "⚡ QR"]))
async def submit_type(msg: Message, state: FSMContext):
    type_ = "code" if msg.text == "⚡ Код" else "qr"
    await state.update_data(type_=type_)
    
    if type_ == "qr":
        price_qr = await get_setting('price_qr')
        await state.set_state(SubmitWA.phone)
        await state.update_data(tariff="qr")
        await msg.answer(f"⭐ QR аренда: {price_qr}$\n\nОтправьте ваш QR-код (фото):", reply_markup=back_kb())
    else:
        price_normal = await get_setting('price_code_normal')
        price_fast = await get_setting('price_code_fast')
        await state.set_state(SubmitWA.tariff)
        await msg.answer(
            f"🔄 Выберите тариф сдачи номера\n\n"
            f"Обычная аренда\n→ сейчас для вас: {price_normal} $\n\n"
            f"⚡ Без очереди — {price_fast} $ (08:00 – 18:30 МСК)",
            reply_markup=tariff_kb(price_normal, price_fast)
        )

@router.message(SubmitWA.tariff)
async def submit_tariff(msg: Message, state: FSMContext):
    if "Обычная" in msg.text:
        tariff = "normal"
    elif "Без очереди" in msg.text:
        tariff = "fast"
    else:
        return
    await state.update_data(tariff=tariff)
    await state.set_state(SubmitWA.phone)
    await msg.answer("📱 Введите номер телефона (формат: 79XXXXXXXXX):", reply_markup=back_kb())

@router.message(SubmitWA.phone)
async def submit_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    phone = msg.text.strip() if msg.text else None
    
    if not phone or not phone.startswith("7") or len(phone) != 11 or not phone.isdigit():
        return await msg.answer("❌ Неверный формат. Введите номер: 79XXXXXXXXX")
    
    number_id = await add_number(msg.from_user.id, phone, data['type_'], data['tariff'])
    await state.clear()
    
    user = await get_user(msg.from_user.id)
    queue = await get_queue()
    pos = len(queue)
    
    await msg.answer(
        f"✅ Номер {phone} добавлен в очередь!\n"
        f"Позиция: {pos}\n"
        f"ID номера: #{number_id}",
        reply_markup=main_menu(user)
    )

# ───── МОИ НОМЕРА ─────
NUMBERS_PER_PAGE = 5

@router.message(F.text == "📊 Мои номера")
async def my_numbers(msg: Message, state: FSMContext):
    await state.update_data(numbers_page=1)
    await show_numbers_page(msg, 1)

async def show_numbers_page(msg: Message, page: int):
    numbers = await get_user_numbers(msg.from_user.id)
    if not numbers:
        return await msg.answer("У вас нет номеров.", reply_markup=back_kb())
    
    total_pages = max(1, (len(numbers) + NUMBERS_PER_PAGE - 1) // NUMBERS_PER_PAGE)
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * NUMBERS_PER_PAGE
    chunk = numbers[start:start + NUMBERS_PER_PAGE]
    
    status_icons = {
        'queue': '🔍', 'in_work': '🔍', 'stood': '✅', 'not_stood': '❌', 'moment_slot': '⚡'
    }
    
    lines = ["Мои номера:\n"]
    for n in chunk:
        icon = status_icons.get(n['status'], '❓')
        lines.append(f"{icon} • #{n['id']} • {n['phone']} • {n['created_at'][11:16]}")
    
    await msg.answer("\n".join(lines), reply_markup=numbers_nav_kb(page, total_pages))

@router.message(F.text == "➡️ Вперёд")
async def numbers_next(msg: Message, state: FSMContext):
    data = await state.get_data()
    page = data.get('numbers_page', 1) + 1
    await state.update_data(numbers_page=page)
    await show_numbers_page(msg, page)

@router.message(F.text == "⬅️ Назад по списку")
async def numbers_prev(msg: Message, state: FSMContext):
    data = await state.get_data()
    page = max(1, data.get('numbers_page', 1) - 1)
    await state.update_data(numbers_page=page)
    await show_numbers_page(msg, page)

# ───── ОБЩАЯ ОЧЕРЕДЬ ─────
@router.message(F.text == "✉️ Общая очередь")
async def common_queue(msg: Message):
    queue = await get_queue()
    if not queue:
        return await msg.answer("🔲 Очередь пуста.")
    lines = [f"#{i+1} • {q['phone']} • @{q['username'] or '-'}" for i, q in enumerate(queue[:20])]
    await msg.answer("📋 Очередь:\n\n" + "\n".join(lines))

# ───── ИНФОРМАЦИЯ ─────
@router.message(F.text == "💡 Информация")
async def info(msg: Message):
    price_cn = await get_setting('price_code_normal')
    price_cf = await get_setting('price_code_fast')
    price_qr = await get_setting('price_qr')
    hold = await get_setting('hold_minutes')
    
    text = (
        f"Приветствуем в UNIVERSE WHATSAPP BOT 🌐\n\n"
        f"ℹ️ Информация:\n\n"
        f"ПРАЙС:\n"
        f"✅ Код:\nС 07:40 до 17:45 — {price_cn}$\n"
        f"С 07:40 до 17:45 — {price_cf}$ (без очереди)\n\n"
        f"⭐ QR:\nС 07:40 до 17:45 — {price_qr}$\n\n"
        f"💲 Холд — {hold} минут: номер должен простоять {hold} минут после «Встал», иначе оплаты нет.\n"
        f"💲 Выплата — через {hold} минут после «Встал».\n\n"
        f"— Номера по коду принимаются по очереди!\n"
        f"— Номера по QR принимаются по системе: кто первый нажал кнопку - тот и ставит\n\n"
        f"— Момент слёт не оплата!\n"
        f"— Нерег — оплаты нет!\n"
        f"— За отвяз номера — вечный бан и заморозка баланса!\n\n"
        f"⭐ Принимаем:\nТолько рег\nТолько РФ номера\n\n"
        f"Рабочее время:\nСтарт — 07:40\nСтоп — 17:45\n(Время МСК)"
    )
    await msg.answer(text)

# ───── ПОМОЩЬ ─────
@router.message(F.text == "⚠️ Помощь")
async def help_cmd(msg: Message):
    await msg.answer(f"⚠️ Помощь:\n\nНапишите в техподдержку в личные сообщения:\n{SUPPORT}")

# ───── НАЗАД ─────
@router.message(F.text == "➡️ Назад")
async def go_back(msg: Message, state: FSMContext):
    await state.clear()
    user = await get_user(msg.from_user.id)
    await msg.answer("🌐 Главное меню", reply_markup=main_menu(user))
