import logging
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global ---
users_data = {}
JOIN_CHANNEL_LINK = "https://t.me/Play_with_TG"
DAILY_BONUS = 5
MINIMUM_WITHDRAWAL = 50
CHANNEL_USERNAME = re.search(r"t\.me\/(.+)", JOIN_CHANNEL_LINK).group(1)

# --- Check Channel Join ---
def check_joined_channel(user_id, context: CallbackContext) -> bool:
    try:
        user_member = context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if user_member.status in ['member', 'administrator', 'creator']:
            users_data[user_id]['joined_channel'] = True
            return True
    except BadRequest as e:
        logger.error(f"Channel check error: {e}")
    return False

# --- Start Command ---
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in users_data:
        users_data[user_id] = {
            'balance': 0,
            'referrals': 0,
            'referred_by': None,
            'joined_channel': False
        }

    if not check_joined_channel(user_id, context):
        join_button = [[InlineKeyboardButton("✅ I've Joined / Refresh", callback_data='refresh')]]
        reply_markup = InlineKeyboardMarkup(join_button)
        update.message.reply_text(
            f"👉 To use this bot, please join our channel first:\n\n📢 {JOIN_CHANNEL_LINK}\n\nAfter joining, click the button below.",
            reply_markup=reply_markup)
        return

    main_menu(update.message, user_id)

# --- Main Menu ---
def main_menu(message_or_query, user_id):
    keyboard = [
        [InlineKeyboardButton("Check Balance", callback_data='balance'),
         InlineKeyboardButton("Referral Link", callback_data='referral_link')],
        [InlineKeyboardButton("How to Earn", callback_data='earnings'),
         InlineKeyboardButton("Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("📊 My Status", callback_data='status'),
         InlineKeyboardButton("🎰 Lucky Spin", callback_data='spin')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_or_query.reply_text("💰 Welcome to the Referral Earning Bot!", reply_markup=reply_markup)

# --- Button Callback ---
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
    elif query.data == 'status':
        balance = users_data[user_id]['balance']
        referrals = users_data[user_id]['referrals']
        referred_by = users_data[user_id]['referred_by']
        referred_by_text = f"{referred_by}" if referred_by else "None"
        msg = f"📊 *Your Status:*\n\n💰 Balance: ₹{balance}\n👥 Referrals: {referrals}\n🤝 Referred By: {referred_by_text}"
        query.edit_message_text(msg, parse_mode='Markdown', reply_markup=back_menu())
    elif query.data == 'spin':
        reward = random.randint(1, 10)
        users_data[user_id]['balance'] += reward
        query.edit_message_text(
            f"🎉 You spun the wheel and won ₹{reward}!\n\n"
            f"💰 New Balance: ₹{users_data[user_id]['balance']}",
            reply_markup=back_menu()
        )
    elif query.data == 'back':
        query.message.delete()
        main_menu(query.message, user_id)

# --- Back Button ---
def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back')]])

# --- Handle Referral ---
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

# --- Main ---
def main():
    updater = Updater("6104357336:AAFeiVvnB7Cg8dJH6tFTEGqyWVDT2UlXHsw")  # 🔁 Replace with your actual bot token
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_referral))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
