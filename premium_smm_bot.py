import asyncio
import requests
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

================= CONFIG =================

BOT_TOKEN = "8158373028:AAEPWnnWrae-ZC-4W5RY8aph5pHHJtNCMMQ"
API_KEY = "d331884eb2750f2e08d6afca07b27c5d"
API_URL = "https://best-smm.com/api/v2"
ADMIN_ID = 6166723158

USD_TO_BDT = 128
PROFIT = 1.35

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

================= DATABASE =================

async def init_db():
async with aiosqlite.connect("smm.db") as db:
await db.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id INTEGER PRIMARY KEY,
username TEXT,
balance REAL DEFAULT 0,
total_spent REAL DEFAULT 0
)""")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_id INTEGER,
        link TEXT,
        quantity INTEGER,
        api_order_id TEXT,
        status TEXT
    )""")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        trx TEXT,
        status TEXT
    )""")

    await db.commit()

================= PRICE =================

def price(rate):
return round(float(rate) * USD_TO_BDT * PROFIT, 2)

================= API =================

def api(data):
data["key"] = API_KEY
r = requests.post(API_URL, data=data)
return r.json()

================= START =================

@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
async with aiosqlite.connect("smm.db") as db:
await db.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES (?,?)",
(msg.from_user.id, msg.from_user.username))
await db.commit()

kb = InlineKeyboardMarkup()
kb.add(InlineKeyboardButton("📊 Services", callback_data="services"))
kb.add(InlineKeyboardButton("👤 Profile", callback_data="profile"))
kb.add(InlineKeyboardButton("📜 Orders", callback_data="orders"))
kb.add(InlineKeyboardButton("💳 Add Money", callback_data="addmoney"))

await msg.answer("🚀 Welcome Premium SMM Bot", reply_markup=kb)

================= CATEGORY =================

@dp.callback_query_handler(lambda c: c.data == "services")
async def services(call):
kb = InlineKeyboardMarkup()
kb.add(InlineKeyboardButton("📸 Instagram", callback_data="cat_instagram"))
kb.add(InlineKeyboardButton("📘 Facebook", callback_data="cat_facebook"))
kb.add(InlineKeyboardButton("🎵 TikTok", callback_data="cat_tiktok"))

await call.message.edit_text("Select Category:", reply_markup=kb)

================= LOAD SERVICES =================

async def show_services(call, keyword):
services = api({"action": "services"})

kb = InlineKeyboardMarkup(row_width=1)

for s in services[:50]:
    if keyword.lower() in s["name"].lower():
        p = price(s["rate"])
        kb.add(InlineKeyboardButton(
            f"{s['service']} | ৳{p}",
            callback_data=f"buy_{s['service']}"
        ))

await call.message.edit_text("Select Service:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("cat_"))
async def category(call):
cat = call.data.split("_")[1]
await show_services(call, cat)

================= ORDER =================

user_data = {}

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy(call):
sid = call.data.split("_")[1]
user_data[call.from_user.id] = {"service": sid}

await call.message.answer("🔗 Send Link:")

@dp.message_handler(lambda m: m.from_user.id in user_data and "link" not in user_data[m.from_user.id])
async def link(msg):
user_data[msg.from_user.id]["link"] = msg.text
await msg.answer("🔢 Send Quantity:")

@dp.message_handler(lambda m: m.from_user.id in user_data and "qty" not in user_data[m.from_user.id])
async def qty(msg):
data = user_data[msg.from_user.id]
qty = int(msg.text)

services = api({"action": "services"})
s = next((x for x in services if str(x["service"]) == data["service"]), None)

if not s:
    return await msg.answer("Invalid service")

total = (price(s["rate"]) / 1000) * qty

async with aiosqlite.connect("smm.db") as db:
    cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (msg.from_user.id,))
    bal = (await cur.fetchone())[0]

    if bal < total:
        return await msg.answer("❌ Not enough balance")

    order = api({
        "action": "add",
        "service": data["service"],
        "link": data["link"],
        "quantity": qty
    })

    if "order" in order:
        await db.execute("UPDATE users SET balance=balance-?, total_spent=total_spent+? WHERE user_id=?",
                         (total, total, msg.from_user.id))

        await db.execute("""
        INSERT INTO orders(user_id, service_id, link, quantity, api_order_id, status)
        VALUES (?,?,?,?,?,?)
        """, (msg.from_user.id, data["service"], data["link"], qty, order["order"], "Processing"))

        await db.commit()

        await msg.answer(f"✅ Order Placed\nID: {order['order']}\nCost: ৳{round(total,2)}")

user_data.pop(msg.from_user.id)

================= AUTO STATUS CHECK =================

async def check_orders():
while True:
async with aiosqlite.connect("smm.db") as db:
cur = await db.execute("SELECT id, api_order_id FROM orders WHERE status!='Completed'")
orders = await cur.fetchall()

        for o in orders:
            res = api({"action": "status", "order": o[1]})
            if "status" in res:
                await db.execute("UPDATE orders SET status=? WHERE id=?",
                                 (res["status"], o[0]))

        await db.commit()

    await asyncio.sleep(60)

================= PAYMENT =================

@dp.callback_query_handler(lambda c: c.data == "addmoney")
async def addmoney(call):
await call.message.answer("""
Send Money:

bKash: 01726986114
Nagad: 01726986114

Format:
1000 trx123
""")

@dp.message_handler(lambda m: "trx" in m.text.lower())
async def payment(msg):
amount, trx = msg.text.split()

async with aiosqlite.connect("smm.db") as db:
    await db.execute("""
    INSERT INTO payments(user_id, amount, trx, status)
    VALUES (?,?,?,?)
    """, (msg.from_user.id, amount, trx, "Pending"))
    await db.commit()

await bot.send_message(ADMIN_ID, f"💰 Payment\n{amount} - {trx}")
await msg.answer("Submitted")

================= ADMIN PANEL =================

@dp.message_handler(commands=['admin'])
async def admin(msg: types.Message):
if msg.from_user.id != ADMIN_ID:
return

kb = InlineKeyboardMarkup()
kb.add(InlineKeyboardButton("Payments", callback_data="admin_payments"))
kb.add(InlineKeyboardButton("Users", callback_data="admin_users"))

await msg.answer("Admin Panel", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_payments")
async def admin_payments(call):
async with aiosqlite.connect("smm.db") as db:
cur = await db.execute("SELECT * FROM payments WHERE status='Pending'")
data = await cur.fetchall()

text = ""
for p in data:
    text += f"{p[0]} | {p[2]} | {p[3]}\n"

await call.message.answer(text)

================= RUN =================

async def on_startup(dp):
await init_db()
asyncio.create_task(check_orders())

if name == "main":
executor.start_polling(dp, on_startup=on_startup)