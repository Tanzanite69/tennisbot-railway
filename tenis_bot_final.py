# tennis_bot_final.py — Готовый улучшенный бот для Telegram теннис-группы

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import sqlite3, asyncio, nest_asyncio 
import os


# === НАСТРОЙКИ ===
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# === СОЗДАНИЕ БАЗЫ ===
conn = sqlite3.connect("tennis.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    tg_id INTEGER,
    photo_file_id TEXT,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS matchday (
    id INTEGER PRIMARY KEY,
    date TEXT
);
""")
c.execute("""
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE,
    name TEXT
);
""")
conn.commit()

# === УТИЛИТА ===
def reply(update, text):
    if update.message:
        return update.message.reply_text(text)
    elif update.callback_query:
        return update.callback_query.edit_message_text(text)

# === КОМАНДЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Match Day", callback_data="matchday")],
        [InlineKeyboardButton("🎾 Записаться", callback_data="signup")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏆 Лидеры", callback_data="leaderboard")]
    ]
    await update.message.reply_text("Привет! Добро пожаловать в теннис-клуб!", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update, "Использование: /add_player <Имя> (ответом на фото)")
        return
    name = " ".join(context.args)
    tg_id = update.message.from_user.id
    photo_id = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo_id = update.message.reply_to_message.photo[-1].file_id
    conn = sqlite3.connect("tennis.db")
    conn.execute("INSERT INTO players (name, tg_id, photo_file_id) VALUES (?, ?, ?)", (name, tg_id, photo_id))
    conn.commit()
    await reply(update, f"✅ Игрок '{name}' добавлен!")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update, "Использование: /profile <Имя>")
        return
    name = " ".join(context.args)
    conn = sqlite3.connect("tennis.db")
    c = conn.cursor()
    c.execute("SELECT wins, losses, photo_file_id FROM players WHERE name = ?", (name,))
    row = c.fetchone()
    if not row:
        await reply(update, "Игрок не найден")
        return
    wins, losses, photo = row
    wins = wins or 0
    losses = losses or 0
    total = wins + losses
    winrate = f"{(wins / total) * 100:.1f}%" if total > 0 else "N/A"
    caption = f"👤 {name}\n✅ Побед: {wins}\n❌ Поражений: {losses}\n⭐ Винрейт: {winrate}"
    if photo:
        await update.message.reply_photo(photo=photo, caption=caption)
    else:
        await reply(update, caption)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("tennis.db")
    c = conn.cursor()
    c.execute("SELECT name, COALESCE(wins, 0), COALESCE(losses, 0) FROM players ORDER BY wins DESC LIMIT 10")
    players = c.fetchall()
    msg = ["🏆 Топ 10 игроков:"]
    for i, (n, w, l) in enumerate(players, 1):
        total = w + l
        winrate = f"{(w / total) * 100:.1f}%" if total > 0 else "N/A"
        msg.append(f"{i}. {n} — {w}W / {l}L ({winrate})")
    await reply(update, "\n".join(msg))

async def delete_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await reply(update, "⛔ Только админ может удалять игроков.")
        return
    if not context.args:
        await reply(update, "Использование: /delete_player <Имя>")
        return
    name = " ".join(context.args)
    conn = sqlite3.connect("tennis.db")
    conn.execute("DELETE FROM players WHERE name = ?", (name,))
    conn.execute("DELETE FROM participants WHERE name = ?", (name,))
    conn.commit()
    await reply(update, f"🗑 Игрок '{name}' удалён.")

async def matchday_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await reply(update, "⛔ Только админ может установить дату.")
        return
    date = " ".join(context.args)
    conn = sqlite3.connect("tennis.db")
    conn.execute("DELETE FROM matchday")
    conn.execute("DELETE FROM participants")
    conn.execute("INSERT INTO matchday (id, date) VALUES (1, ?)", (date,))
    conn.commit()
    await reply(update, f"📅 Match Day установлен: {date}")

async def matchday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("tennis.db")
    c = conn.cursor()
    c.execute("SELECT date FROM matchday")
    row = c.fetchone()
    msg = f"📅 Следующий Match Day: {row[0]}" if row else "Дата матча пока не установлена"
    c.execute("SELECT name FROM participants")
    names = [r[0] for r in c.fetchall()]
    if names:
        msg += "\n🎾 Участники: " + ", ".join(names)
    await reply(update, msg)

async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("tennis.db")
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE tg_id = ?", (user.id,))
    row = c.fetchone()
    if not row:
        await reply(update, "Сначала зарегистрируйтесь через /add_player")
        return
    name = row[0]
    try:
        conn.execute("INSERT INTO participants (tg_id, name) VALUES (?, ?)", (user.id, name))
        conn.commit()
        await reply(update, f"🎾 Вы записаны на Match Day: {name}")
    except sqlite3.IntegrityError:
        await reply(update, "Вы уже записаны на Match Day.")

async def record_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await reply(update, "⛔ Только админ может записывать результаты.")
        return
    if len(context.args) != 3:
        await reply(update, "Использование: /record_game <Игрок1> <Игрок2> <Победитель>")
        return
    p1, p2, winner = context.args
    conn = sqlite3.connect("tennis.db")
    c = conn.cursor()
    for name in (p1, p2):
        c.execute("SELECT id FROM players WHERE name = ?", (name,))
        if not c.fetchone():
            await reply(update, f"Игрок '{name}' не найден")
            return
    if winner not in (p1, p2):
        await reply(update, "Победитель должен быть одним из участников")
        return
    loser = p2 if winner == p1 else p1
    c.execute("UPDATE players SET wins = COALESCE(wins, 0) + 1 WHERE name = ?", (winner,))
    c.execute("UPDATE players SET losses = COALESCE(losses, 0) + 1 WHERE name = ?", (loser,))
    conn.commit()
    await reply(update, f"✅ Матч записан: {winner} победил {loser}")

# === ЗАПУСК ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("delete_player", delete_player))
    app.add_handler(CommandHandler("matchday", matchday))
    app.add_handler(CommandHandler("matchday_set", matchday_set))
    app.add_handler(CommandHandler("record_game", record_game))
    app.add_handler(CallbackQueryHandler(button_handler))

    await app.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("add_player", "Добавить игрока (ответом на фото)"),
        BotCommand("profile", "Показать профиль игрока"),
        BotCommand("leaderboard", "Рейтинг игроков"),
        BotCommand("delete_player", "Удалить игрока (только админ)"),
        BotCommand("matchday", "Показать дату матча"),
        BotCommand("matchday_set", "Назначить дату матча (админ)"),
        BotCommand("record_game", "Записать результат матча (админ)")
    ])

    print("✅ Бот запущен")
    await app.run_polling()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "matchday":
        await matchday(update, context)
    elif data == "signup":
        await signup(update, context)
    elif data == "profile":
        await reply(update, "Введите: /profile <Имя>")
    elif data == "leaderboard":
        await leaderboard(update, context)
    await query.answer()

if __name__ == "__main__":
    import nest_asyncio
    import asyncio
    nest_asyncio.apply()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
