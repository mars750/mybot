import logging
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Bot Data ---
users_data = {}
JOIN_CHANNEL_LINK = "https://t.me/Play_with_TG"
DAILY_BONUS = 5
MINIMUM_WITHDRAWAL = 50

# Extract username safely
CHANNEL_USERNAME = re.search(r"t\.me\/(.+)", JOIN_CHANNEL_LINK).group(1).replace("/", "")

# --- Check if User Joined Channel ---
def check_joined_channel(user_id, context: CallbackContext) -> bool:
    try:
        member = context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status in ['member', 'administrator', 'creator']:
            users_data[user_id]['joined_channel'] = True
            return True
    except BadRequest as e:
        logger.error(f"Join check error: {e}")
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

    # Check Channel Join
    if not check_joined_channel(user_id, context):
        join_button = [[InlineKeyboardButton("✅ I've Joined / Refresh", callback_data='refresh')]]
        reply_markup = InlineKeyboardMarkup(join_button)
        update.message.reply_text(f"👉 पहले हमारे चैनल को जॉइन करें:\n\n📢 {JOIN_CHANNEL_LINK}\n\nजॉइन करने के बाद नीचे बटन दबाएँ।",
                                  reply_markup=reply_markup)
        return

    # Show Menu
    main_menu(update.message, user_id)

# --- Main Menu ---
def main_menu(message_or_query, user_id):
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance'),
         InlineKeyboardButton("🔗 Referral Link", callback_data='referral_link')],
        [InlineKeyboardButton("📈 How to Earn", callback_data='earnings'),
         InlineKeyboardButton("💵 Withdraw", callback_data='withdraw')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_or_query.reply_text("🎉 Welcome to the Earning Bot!", reply_markup=reply_markup)

# --- Callback Handler ---
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
            query.answer("❗ अभी भी चैनल जॉइन नहीं किया है।", show_alert=True)
        return

    if not users_data[user_id]['joined_channel']:
        query.answer("❗ पहले चैनल को जॉइन करें।", show_alert=True)
        return

    if query.data == 'balance':
        query.edit_message_text(f"💰 आपका बैलेंस: ₹{users_data[user_id]['balance']}", reply_markup=back_menu())
    elif query.data == 'referral_link':
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        query.edit_message_text(f"🔗 आपकी रेफरल लिंक:\n{link}", reply_markup=back_menu())
    elif query.data == 'earnings':
        query.edit_message_text("💸 हर रेफरल पर ₹5 कमाएँ!", reply_markup=back_menu())
    elif query.data == 'withdraw':
        balance = users_data[user_id]['balance']
        if balance >= MINIMUM_WITHDRAWAL:
            users_data[user_id]['balance'] -= MINIMUM_WITHDRAWAL
            query.edit_message_text(f"✅ ₹{MINIMUM_WITHDRAWAL} विदड्रॉल सफल!\nनई बैलेंस: ₹{users_data[user_id]['balance']}", reply_markup=back_menu())
        else:
            query.edit_message_text(f"❌ कम से कम ₹{MINIMUM_WITHDRAWAL} चाहिए विदड्रॉल के लिए।", reply_markup=back_menu())
    elif query.data == 'back':
        query.message.delete()
        main_menu(query.message, user_id)

# --- Back Menu ---
def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back')]])

# --- Referral Handler ---
def handle_referral(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in users_data:
        users_data[user_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}

    if text.startswith('/start') and len(text.split()) > 1:
        referrer_id = int(text.split()[1])
        if referrer_id != user_id and users_data[user_id]['referred_by'] is None:
            users_data[user_id]['referred_by'] = referrer_id
            if referrer_id not in users_data:
                users_data[referrer_id] = {'balance': 0, 'referrals': 0, 'referred_by': None, 'joined_channel': False}
            users_data[referrer_id]['balance'] += DAILY_BONUS
            users_data[referrer_id]['referrals'] += 1
            update.message.reply_text("🎉 रेफरल सफल! ₹5 जोड़ दिए गए।")

    start(update, context)

# --- Main Function ---
def main():
    updater = Updater("6104357336:AAFeiVvnB7Cg8dJH6tFTEGqyWVDT2UlXHsw")  # यहां अपना बॉट टोकन डालो
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_referral))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
