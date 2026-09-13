from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Filter

from database import *
from keyboards import *
from config import ADMIN_IDS

router = Router()

class IsAdmin(Filter):
    async def __call__(self, msg: Message) -> bool:
        user = await get_user(msg.from_user.id)
        return user and user['role'] == 'admin'

class IsVbiv(Filter):
    async def __call__(self, msg: Message) -> bool:
        user = await get_user(msg.from_user.id)
        return user and user['role'] in ('admin', 'vbiv')

class AdminStates(StatesGroup):
    wait_price = State()
    wait_vbiv_id = State()
    wait_broadcast = State()
    wait_user_search = State()
    number_taken = State()

# ───── ОТКРЫТЬ АДМИНКУ ─────
@router.message(F.text == "🔧 Админка", IsAdmin())
async def admin_menu(msg: Message, state: FSMContext):
    await state.clear()
    work = await get_setting('work_active')
    status = "🟢 Ворк АКТИВЕН" if work == '1' else "🔴 Ворк ОСТАНОВЛЕН"
    await msg.answer(f"🔧 Панель администратора\n{status}", reply_markup=admin_menu_kb())

# ───── ВБИВ МЕНЮ ─────
@router.message(F.text == "🎯 Вбив", IsVbiv())
async def vbiv_menu(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🎯 Меню вбива", reply_markup=vbiv_menu_kb())

# ───── ВЗЯТЬ НОМЕР ─────
@router.message(F.text == "📥 Взять номер", IsVbiv())
async def take_number(msg: Message, state: FSMContext, bot: Bot):
    work = await get_setting('work_active')
    if work != '1':
        return await msg.answer("⛔ Ворк остановлен.")
    
    item = await pop_queue()
    if not item:
        return await msg.answer("🔲 Очередь пуста.")
    
    await add_log(msg.from_user.id, "take_number", f"#{item['number_id']} {item['phone']}")
    await state.update_data(current_number_id=item['number_id'], current_owner=item['user_id'])
    await state.set_state(AdminStates.number_taken)
    
    tariff_names = {'normal': 'Обычная аренда', 'fast': 'Без очереди', 'qr': 'QR'}
    
    await msg.answer(
        f"📥 Номер взят в работу:\n\n"
        f"#{item['number_id']} • {item['phone']}\n"
        f"Тип: {item['type'].upper()}\n"
        f"Тариф: {tariff_names.get(item['tariff'], item['tariff'])}\n"
        f"Продавец: @{item['username'] or item['user_id']}\n\n"
        f"Отправьте фото с кодом или QR для подтверждения.",
        reply_markup=number_result_kb(item['number_id'])
    )
    
    # Уведомление продавцу
    try:
        await bot.send_message(
            item['user_id'],
            f"🔔 Ваш номер #{item['number_id']} ({item['phone']}) взят в работу!"
        )
    except:
        pass

# Статус номера через callback
@router.callback_query(F.data.startswith("num_"))
async def number_status_cb(cb: CallbackQuery, bot: Bot, state: FSMContext):
    parts = cb.data.split("_")
    action = parts[1]
    number_id = int(parts[2])
    
    data = await state.get_data()
    owner_id = data.get('current_owner')
    
    status_map = {
        'stood': ('stood', '✅ Встал', '✅ Ваш номер встал! Выплата через 15 минут.'),
        'notstood': ('not_stood', '❌ Не встал', '❌ Ваш номер не встал. Оплаты нет.'),
        'slot': ('moment_slot', '⚡ Момент слёт', '⚡ Момент слёт — оплата не начисляется.'),
    }
    
    if action not in status_map:
        return
    
    status, label, user_msg = status_map[action]
    await set_number_status(number_id, status)
    
    if status == 'stood' and owner_id:
        # Начислить баланс
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT tariff FROM numbers WHERE id=?", (number_id,)) as cur:
                row = await cur.fetchone()
            if row:
                tariff = row[0]
                price_key = 'price_code_fast' if tariff == 'fast' else ('price_qr' if tariff == 'qr' else 'price_code_normal')
                price = float(await get_setting(price_key))
                await db.execute("UPDATE users SET balance = balance + ? WHERE tg_id=?", (price, owner_id))
                await db.commit()
    
    await add_log(cb.from_user.id, f"set_status_{status}", f"#{number_id}")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"{label} — номер #{number_id}")
    
    if owner_id:
        try:
            await bot.send_message(owner_id, f"🔔 #{number_id}: {user_msg}")
        except:
            pass
    
    await state.clear()
    await cb.answer()

# ───── СТАТИСТИКА ─────
@router.message(F.text == "📊 Статистика", IsAdmin())
async def admin_stats(msg: Message):
    stats = await get_admin_stats()
    text = (
        f"📊 Статистика\n\n"
        f"Сегодня:\n"
        f"— Сдано: {stats.get('total_today') or 0}\n"
        f"— Встало: {stats.get('stood_today') or 0}\n"
        f"— Не встало: {stats.get('not_stood_today') or 0}\n"
        f"— Момент слётов: {stats.get('slot_today') or 0}\n\n"
        f"За неделю:\n"
        f"— Всего: {stats.get('total_week') or 0}\n"
        f"— Встало: {stats.get('stood_week') or 0}\n\n"
        f"В очереди сейчас: {stats.get('in_queue') or 0}"
    )
    await msg.answer(text)

# ───── ИЗМЕНИТЬ ПРАЙС ─────
@router.message(F.text == "💰 Изменить прайс", IsAdmin())
async def change_price_start(msg: Message, state: FSMContext):
    cn = await get_setting('price_code_normal')
    cf = await get_setting('price_code_fast')
    qr = await get_setting('price_qr')
    await state.set_state(AdminStates.wait_price)
    await msg.answer(
        f"Текущий прайс:\n"
        f"Код обычный: {cn}$\n"
        f"Код без очереди: {cf}$\n"
        f"QR: {qr}$\n\n"
        f"Введите новые цены в формате:\n<код_норм> <код_быстро> <qr>\n"
        f"Пример: 2.5 2.0 1.8",
        reply_markup=back_kb()
    )

@router.message(AdminStates.wait_price, IsAdmin())
async def change_price_set(msg: Message, state: FSMContext):
    try:
        parts = msg.text.strip().split()
        cn, cf, qr = float(parts[0]), float(parts[1]), float(parts[2])
        await set_setting('price_code_normal', str(cn))
        await set_setting('price_code_fast', str(cf))
        await set_setting('price_qr', str(qr))
        await add_log(msg.from_user.id, "change_price", f"{cn} / {cf} / {qr}")
        await state.clear()
        await msg.answer(f"✅ Прайс обновлён:\nКод: {cn}$ / {cf}$\nQR: {qr}$", reply_markup=admin_menu_kb())
    except:
        await msg.answer("❌ Неверный формат. Пример: 2.5 2.0 1.8")

# ───── НАЗНАЧИТЬ ВБИВА ─────
@router.message(F.text == "🎯 Назначить вбива", IsAdmin())
async def assign_vbiv_start(msg: Message, state: FSMContext):
    await state.set_state(AdminStates.wait_vbiv_id)
    await msg.answer("Введите TG ID или @username пользователя:", reply_markup=back_kb())

@router.message(AdminStates.wait_vbiv_id, IsAdmin())
async def assign_vbiv_set(msg: Message, state: FSMContext):
    raw = msg.text.strip().lstrip('@')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if raw.isdigit():
            async with db.execute("SELECT * FROM users WHERE tg_id=?", (int(raw),)) as cur:
                user = await cur.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username=?", (raw,)) as cur:
                user = await cur.fetchone()
    
    if not user:
        return await msg.answer("❌ Пользователь не найден. Он должен был написать /start боту.")
    
    user = dict(user)
    await update_user(user['tg_id'], role='vbiv')
    await add_log(msg.from_user.id, "assign_vbiv", f"{user['tg_id']} @{user['username']}")
    await state.clear()
    await msg.answer(f"✅ @{user['username'] or user['tg_id']} назначен вбивом.", reply_markup=admin_menu_kb())

# ───── ПОЛЬЗОВАТЕЛИ ─────
@router.message(F.text == "👥 Пользователи", IsAdmin())
async def users_list(msg: Message, state: FSMContext):
    await state.set_state(AdminStates.wait_user_search)
    await msg.answer("Введите TG ID или @username для поиска:", reply_markup=back_kb())

@router.message(AdminStates.wait_user_search, IsAdmin())
async def user_search(msg: Message, state: FSMContext):
    raw = msg.text.strip().lstrip('@')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if raw.isdigit():
            async with db.execute("SELECT * FROM users WHERE tg_id=?", (int(raw),)) as cur:
                user = await cur.fetchone()
        else:
            async with db.execute("SELECT * FROM users WHERE username=?", (raw,)) as cur:
                user = await cur.fetchone()
    
    if not user:
        return await msg.answer("❌ Не найден.")
    
    user = dict(user)
    stats = await get_user_stats(user['tg_id'])
    text = (
        f"👤 @{user['username'] or '-'} | {user['tg_id']}\n"
        f"Роль: {user['role']}\n"
        f"Бан: {'Да' if user['is_banned'] else 'Нет'}\n"
        f"Приоритет: {'Да' if user['has_priority'] else 'Нет'}\n"
        f"Баланс: {user['balance']:.2f}$\n"
        f"Всего сдано: {stats.get('total') or 0}\n"
        f"Встало: {stats.get('stood') or 0}"
    )
    await state.clear()
    await msg.answer(text, reply_markup=user_manage_kb(user['tg_id'], user['is_banned']))

@router.callback_query(F.data.startswith("user_"))
async def user_action_cb(cb: CallbackQuery, bot: Bot):
    parts = cb.data.split("_")
    action = parts[1]
    tg_id = int(parts[2])
    user = await get_user(tg_id)
    
    if action == "ban":
        new_val = 0 if user['is_banned'] else 1
        await update_user(tg_id, is_banned=new_val)
        label = "разбанен" if not new_val else "забанен"
        await add_log(cb.from_user.id, f"user_{label}", str(tg_id))
        await cb.answer(f"Пользователь {label}")
        await cb.message.edit_reply_markup(reply_markup=user_manage_kb(tg_id, new_val))
    
    elif action == "priority":
        new_val = 0 if user['has_priority'] else 1
        await update_user(tg_id, has_priority=new_val)
        await add_log(cb.from_user.id, "user_priority", f"{tg_id} -> {new_val}")
        await cb.answer(f"Приоритет {'включён' if new_val else 'выключен'}")
    
    elif action == "buyer":
        new_val = 0 if user['buyer_access'] else 1
        await update_user(tg_id, buyer_access=new_val)
        await add_log(cb.from_user.id, "user_buyer", f"{tg_id} -> {new_val}")
        await cb.answer(f"Доступ покупателя {'включён' if new_val else 'выключен'}")

# ───── РАССЫЛКА ─────
@router.message(F.text == "📢 Рассылка", IsAdmin())
async def broadcast_start(msg: Message, state: FSMContext):
    await state.set_state(AdminStates.wait_broadcast)
    await msg.answer("Введите текст рассылки:", reply_markup=back_kb())

@router.message(AdminStates.wait_broadcast, IsAdmin())
async def broadcast_send(msg: Message, state: FSMContext, bot: Bot):
    text = msg.text
    users = await get_all_users()
    ok, fail = 0, 0
    for u in users:
        if u['is_banned']:
            continue
        try:
            await bot.send_message(u['tg_id'], text)
            ok += 1
        except:
            fail += 1
    await add_log(msg.from_user.id, "broadcast", f"ok={ok} fail={fail}")
    await state.clear()
    await msg.answer(f"📢 Рассылка завершена.\n✅ Доставлено: {ok}\n❌ Ошибок: {fail}", reply_markup=admin_menu_kb())

# ───── СТАРТ/СТОП ВОРК ─────
@router.message(F.text == "🟢 Старт/Стоп ворк", IsAdmin())
async def toggle_work(msg: Message, bot: Bot):
    work = await get_setting('work_active')
    new_val = '0' if work == '1' else '1'
    await set_setting('work_active', new_val)
    await add_log(msg.from_user.id, "work_toggle", f"-> {new_val}")
    
    if new_val == '1':
        status_text = "🟢 СТАРТ ВОРК! Приём номеров открыт."
    else:
        status_text = "🔴 СТОП ВОРК! Приём номеров остановлен."
    
    await msg.answer(f"✅ {status_text}", reply_markup=admin_menu_kb())
    
    # Рассылка всем
    users = await get_all_users()
    for u in users:
        if u['is_banned'] or u['role'] == 'admin':
            continue
        try:
            await bot.send_message(u['tg_id'], f"📢 {status_text}")
        except:
            pass

# ───── ЛОГИ ─────
@router.message(F.text == "📋 Логи", IsAdmin())
async def show_logs(msg: Message):
    logs = await get_logs(30)
    if not logs:
        return await msg.answer("Логов нет.")
    lines = []
    for l in logs:
        lines.append(f"[{l['created_at'][11:16]}] @{l['username'] or l['admin_id']}: {l['action']} {l['details'] or ''}")
    text = "📋 Последние логи:\n\n" + "\n".join(lines)
    # Разбиваем если длинный
    if len(text) > 4000:
        text = text[:4000] + "..."
    await msg.answer(text)
