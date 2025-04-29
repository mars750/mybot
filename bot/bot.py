import logging
import random
import re
import threading
import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global ---
users_data = {}
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)

JOIN_CHANNEL_LINK = "https://t.me/Play_with_TG"
DAILY_BONUS = 5
MINIMUM_WITHDRAWAL = 50
CHANNEL_USERNAME = re.search(r"t\.me\/(.+)", JOIN_CHANNEL_LINK).group(1)

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
        if user_member.status in ['member', 'administrator', 'creator']:
            users_data[user_id]['joined_channel'] = True
            return True
    except BadRequest as e:
        logger.error(f"Channel check error: {e}")
    return False

def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in users_data:
        users_data[user_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

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

    if user_id not in users_data:
        users_data[user_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

    if query.data == 'refresh':
        if check_joined_channel(user_id, context):
            query.message.delete()
            main_menu(query.message, user_id)
        else:
            query.answer("❗ You haven't joined yet.", show_alert=True)
        return

    if not users_data[user_id]['joined_channel']:
        query.answer("❗ Please join the channel first.")
        return

    if query.data == 'balance':
        query.edit_message_text(f"💰 Your current balance is ₹{users_data[user_id]['balance']}", reply_markup=back_menu())
    elif query.data == 'referral_link':
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        query.edit_message_text(f"📢 Your referral link:\n{link}", reply_markup=back_menu())
    elif query.data == 'earnings':
        query.edit_message_text("💸 You earn ₹5 for every person who joins using your referral link.", reply_markup=back_menu())
    elif query.data == 'withdraw':
        balance = users_data[user_id]['balance']
        if balance >= MINIMUM_WITHDRAWAL:
            users_data[user_id]['balance'] -= MINIMUM_WITHDRAWAL
            query.edit_message_text(f"✅ Withdrawal of ₹{MINIMUM_WITHDRAWAL} successful!\nNew Balance: ₹{users_data[user_id]['balance']}", reply_markup=back_menu())
        else:
            query.edit_message_text(f"❌ You need at least ₹{MINIMUM_WITHDRAWAL} to withdraw.", reply_markup=back_menu())
    elif query.data == 'back':
        query.message.delete()
        main_menu(query.message, user_id)

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back')]])

def add_points(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in users_data:
        users_data[user_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}
    try:
        points = int(context.args[0])
        users_data[user_id]['balance'] += points
        update.message.reply_text(f"🎉 {points} points added!\n💰 Balance: ₹{users_data[user_id]['balance']}")
    except (IndexError, ValueError):
        update.message.reply_text("❗ Use: /addpoints <amount>")

def handle_referral(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users_data:
        users_data[user_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

    if text.startswith('/start') and len(text.split()) > 1:
        referrer_id = int(text.split()[1])
        if referrer_id != user_id and users_data[user_id].get('referred_by') is None:
            users_data[user_id]['referred_by'] = referrer_id
            if referrer_id not in users_data:
                users_data[referrer_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}
            users_data[referrer_id]['balance'] += 5
            users_data[referrer_id]['referrals'] += 1
            update.message.reply_text("🎉 Referral successful! Referrer earned ₹5.")

    start(update, context)

# --- Register Handlers ---
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("addpoints", add_points))
dispatcher.add_handler(CallbackQueryHandler(button_callback))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_referral))

# --- Set Webhook ---
if __name__ == '__main__':
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # जैसे: https://your-app.onrender.com
    bot.delete_webhook()
    bot.set_webhook(f"https://refer-earn-bot.onrender.com/6104357336:AAFeiVvnB7Cg8dJH6tFTEGqyWVDT2UlXHsw")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
