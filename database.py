import aiosqlite
import asyncio
from datetime import datetime

DB_PATH = "wabot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            role TEXT DEFAULT 'user',  -- user, vbiv, admin
            is_banned INTEGER DEFAULT 0,
            has_priority INTEGER DEFAULT 0,
            buyer_access INTEGER DEFAULT 0,
            balance REAL DEFAULT 0.0,
            is_online INTEGER DEFAULT 0,
            registered_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            type TEXT NOT NULL,       -- code, qr
            tariff TEXT NOT NULL,     -- normal, fast
            status TEXT DEFAULT 'queue',  -- queue, in_work, stood, not_stood, moment_slot
            admin_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            stood_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(tg_id)
        );

        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number_id INTEGER UNIQUE NOT NULL,
            position INTEGER,
            added_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (number_id) REFERENCES numbers(id)
        );

        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, done, rejected
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(tg_id)
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        INSERT OR IGNORE INTO settings VALUES ('work_active', '1');
        INSERT OR IGNORE INTO settings VALUES ('price_code_normal', '2.5');
        INSERT OR IGNORE INTO settings VALUES ('price_code_fast', '2.0');
        INSERT OR IGNORE INTO settings VALUES ('price_qr', '1.8');
        INSERT OR IGNORE INTO settings VALUES ('hold_minutes', '15');
        INSERT OR IGNORE INTO settings VALUES ('min_payout', '0.5');
        """)
        await db.commit()

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))
        await db.commit()

async def get_or_create_user(tg_id: int, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
            user = await cur.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (tg_id, username) VALUES (?,?)",
                (tg_id, username)
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
                user = await cur.fetchone()
        return dict(user)

async def get_user(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_user(tg_id: int, **kwargs):
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE tg_id=?", values)
        await db.commit()

async def add_number(user_id, phone, type_, tariff):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO numbers (user_id, phone, type, tariff) VALUES (?,?,?,?)",
            (user_id, phone, type_, tariff)
        )
        number_id = cur.lastrowid
        # Позиция в очереди
        async with db.execute("SELECT COUNT(*) FROM queue") as c:
            count = (await c.fetchone())[0]
        await db.execute(
            "INSERT INTO queue (number_id, position) VALUES (?,?)",
            (number_id, count + 1)
        )
        await db.commit()
        return number_id

async def get_queue():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT q.*, n.phone, n.type, n.tariff, n.user_id, u.username
            FROM queue q
            JOIN numbers n ON q.number_id = n.id
            JOIN users u ON n.user_id = u.tg_id
            ORDER BY q.position
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def pop_queue():
    """Берёт первый номер из очереди"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT q.*, n.phone, n.type, n.tariff, n.user_id, u.username, u.tg_id as owner_tg_id
            FROM queue q
            JOIN numbers n ON q.number_id = n.id
            JOIN users u ON n.user_id = u.tg_id
            ORDER BY q.position LIMIT 1
        """) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        row = dict(row)
        await db.execute("DELETE FROM queue WHERE id=?", (row['id'],))
        await db.execute("UPDATE numbers SET status='in_work' WHERE id=?", (row['number_id'],))
        await db.commit()
        return row

async def set_number_status(number_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        stood_at = f", stood_at=datetime('now')" if status in ('stood', 'not_stood', 'moment_slot') else ""
        await db.execute(
            f"UPDATE numbers SET status=?{stood_at} WHERE id=?",
            (status, number_id)
        )
        await db.commit()

async def get_user_numbers(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM numbers WHERE user_id=? ORDER BY id DESC",
            (tg_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_user_stats(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now().strftime('%Y-%m-%d')
        async with db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='stood' THEN 1 ELSE 0 END) as stood,
                SUM(CASE WHEN status='not_stood' THEN 1 ELSE 0 END) as not_stood,
                SUM(CASE WHEN status='moment_slot' THEN 1 ELSE 0 END) as moment_slot
            FROM numbers WHERE user_id=?
        """, (tg_id,)) as cur:
            all_stats = dict(await cur.fetchone())
        async with db.execute("""
            SELECT
                COUNT(*) as total_today,
                SUM(CASE WHEN status='stood' THEN 1 ELSE 0 END) as stood_today,
                SUM(CASE WHEN status='in_work' THEN 1 ELSE 0 END) as confirmed_today
            FROM numbers WHERE user_id=? AND DATE(created_at)=?
        """, (tg_id, today)) as cur:
            today_stats = dict(await cur.fetchone())
        return {**all_stats, **today_stats}

async def add_log(admin_id: int, action: str, details: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO logs (admin_id, action, details) VALUES (?,?,?)",
            (admin_id, action, details)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY registered_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_admin_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now().strftime('%Y-%m-%d')
        async with db.execute(f"""
            SELECT
                COUNT(*) as total_today,
                SUM(CASE WHEN status='stood' THEN 1 ELSE 0 END) as stood_today,
                SUM(CASE WHEN status='not_stood' THEN 1 ELSE 0 END) as not_stood_today,
                SUM(CASE WHEN status='moment_slot' THEN 1 ELSE 0 END) as slot_today
            FROM numbers WHERE DATE(created_at)=?
        """, (today,)) as cur:
            today_s = dict(await cur.fetchone())
        async with db.execute("""
            SELECT
                COUNT(*) as total_week,
                SUM(CASE WHEN status='stood' THEN 1 ELSE 0 END) as stood_week
            FROM numbers WHERE created_at >= datetime('now', '-7 days')
        """) as cur:
            week_s = dict(await cur.fetchone())
        async with db.execute("SELECT COUNT(*) as in_queue FROM queue") as cur:
            queue_s = dict(await cur.fetchone())
        return {**today_s, **week_s, **queue_s}

async def get_logs(limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT l.*, u.username FROM logs l
            LEFT JOIN users u ON l.admin_id = u.tg_id
            ORDER BY l.created_at DESC LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_pending_payouts():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT p.*, u.username FROM payouts p
            JOIN users u ON p.user_id = u.tg_id
            WHERE p.status='pending'
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
