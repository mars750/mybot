import logging
import random
import re
import threading
import os
import sqlite3  # SQLite के लिए
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global ---
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)

JOIN_CHANNEL_LINK = "https://t.me/Play_with_TG"
DAILY_BONUS = 5
MINIMUM_WITHDRAWAL = 50
CHANNEL_USERNAME = re.search(r"t\.me\/(.+)", JOIN_CHANNEL_LINK).group(1)

# --- डेटाबेस कनेक्शन ---
DATABASE_NAME = 'users.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # कॉलम नाम से एक्सेस करने के लिए
    return conn

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER,
            joined_channel BOOLEAN DEFAULT FALSE
        )
    """)
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return dict(user_data) if user_data else None

def update_user_data(user_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    set_clause = ', '.join(f"{key} = ?" for key in data.keys())
    cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", (*data.values(), user_id))
    conn.commit()
    conn.close()

def create_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# --- Flask App ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running with webhook!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

def check_joined_channel(user_id, context: CallbackContext) -> bool:
    try:
        user_member = context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        joined = user_member.status in ['member', 'administrator', 'creator']
        user_data = get_user_data(user_id)
        if user_data and user_data.get('joined_channel') != joined:
            update_user_data(user_id, {'joined_channel': joined})
        elif not user_data:
            create_user(user_id)
            update_user_data(user_id, {'joined_channel': joined})
        return joined
    except BadRequest as e:
        logger.error(f"Channel check error: {e}")
    return False

def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        create_user(user_id)
        user_data = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

    if not check_joined_channel(user_id, context):
        join_button = [[InlineKeyboardButton("✅ I've Joined / Refresh", callback_data='refresh')]]
        reply_markup = InlineKeyboardMarkup(join_button)
        update.message.reply_text(
            f"👉 To use this bot, join our channel:\n\n📢 {JOIN_CHANNEL_LINK}\n\nThen click the button below.",
            reply_markup=reply_markup)
        return

    main_menu(update.message, user_id)

def main_menu(message_or_query, user_id):
    keyboard = [
        [InlineKeyboardButton("Check Balance", callback_data='balance'),
         InlineKeyboardButton("Referral Link", callback_data='referral_link')],
        [InlineKeyboardButton("How to Earn", callback_data='earnings'),
         InlineKeyboardButton("Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("🎡 Spin Wheel", web_app=WebAppInfo(url="https://spin-wheel-3igb.vercel.app/"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_or_query.reply_text("💰 Welcome to the Referral Earning Bot!", reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        create_user(user_id)
        user_data = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

    if query.data == 'refresh':
        if check_joined_channel(user_id, context):
            query.message.delete()
            main_menu(query.message, user_id)
        else:
            query.answer("❗ You haven't joined yet.", show_alert=True)
        return

    if not user_data.get('joined_channel', False):
        query.answer("❗ Please join the channel first.")
        return

    if query.data == 'balance':
        query.edit_message_text(f"💰 Your current balance is ₹{user_data['balance']}", reply_markup=back_menu())
    elif query.data == 'referral_link':
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        query.edit_message_text(f"📢 Your referral link:\n{link}", reply_markup=back_menu())
    elif query.data == 'earnings':
        query.edit_message_text("💸 You earn ₹5 for every person who joins using your referral link.", reply_markup=back_menu())
    elif query.data == 'withdraw':
        balance = user_data['balance']
        if balance >= MINIMUM_WITHDRAWAL:
            update_user_data(user_id, {'balance': balance - MINIMUM_WITHDRAWAL})
            query.edit_message_text(f"✅ Withdrawal of ₹{MINIMUM_WITHDRAWAL} successful!\nNew Balance: ₹{get_user_data(user_id)['balance']}", reply_markup=back_menu())
        else:
            query.edit_message_text(f"❌ You need at least ₹{MINIMUM_WITHDRAWAL} to withdraw.", reply_markup=back_menu())
    elif query.data == 'back':
        query.message.delete()
        main_menu(query.message, user_id)

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back')]])

def add_points(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    try:
        points = int(context.args[0])
        user_data = get_user_data(user_id)
        if not user_data:
            create_user(user_id)
            user_data = {'balance': 0}
        update_user_data(user_id, {'balance': user_data['balance'] + points})
        update.message.reply_text(f"🎉 {points} points added!\n💰 Balance: ₹{get_user_data(user_id)['balance']}")
    except (IndexError, ValueError):
        update.message.reply_text("❗ Use: /addpoints <amount>")

def handle_referral(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    referred_user_data = get_user_data(user_id)
    if not referred_user_data:
        create_user(user_id)
        referred_user_data = {'referred_by': None}

    if text.startswith('/start') and len(text.split()) > 1:
        referrer_id = int(text.split()[1])
        if referrer_id != user_id and referred_user_data.get('referred_by') is None:
            update_user_data(user_id, {'referred_by': referrer_id})
            referrer_data = get_user_data(referrer_id)
            if not referrer_data:
                create_user(referrer_id)
                referrer_data = {'balance': 0, 'referrals': 0}
            update_user_data(referrer_id, {'balance': referrer_data['balance'] + 5, 'referrals': referrer_data['referrals'] + 1})
            update.message.reply_text("🎉 Referral successful! Referrer earned ₹5.")

    start(update, context)

# --- Register Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("addpoints", add_points))
dispatcher.add_handler(CallbackQueryHandler(button_callback))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_referral))

# --- Set Webhook and Initialize Database ---
if __name__ == '__main__':
    initialize_database()
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # जैसे: https://your-app.onrender.com
    bot.delete_webhook()
    bot.set_webhook(f"https://refer-earn-bot.onrender.com/6104357336:AAFeiVvnB7Cg8dJH6tFTEGqyWVDT2UlXHsw")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
