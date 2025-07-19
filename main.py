import logging
import os
import re
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import NotFound

# --- CONFIGURATION ---
# IMPORTANT: Before running, you need to set up your credentials.
# 1. Create a file named 'config.py' in the same directory.
# 2. In config.py, add the following lines:
#    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
#    FIREBASE_APP_ID = "YOUR_FIREBASE_APP_ID" # e.g., 'default-power-store'
#    ADMIN_USER_ID = YOUR_TELEGRAM_USER_ID # e.g., 123456789 (must be an integer)
# 3. Create a Firebase service account and download the JSON key file.
#    Save it as 'firebase_credentials.json' in the same directory.

try:
    from config import TELEGRAM_BOT_TOKEN, FIREBASE_APP_ID, ADMIN_USER_ID
except ImportError:
    print("ERROR: config.py not found or missing variables. Please create it as per the instructions.")
    # You can add placeholder values here for testing if you don't want to create the file immediately
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    FIREBASE_APP_ID = "default-power-store"
    ADMIN_USER_ID = 123456789
    print("WARNING: Using placeholder values for configuration.")


# --- SETUP ---

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Firebase
try:
    # Check if the credentials file exists
    if os.path.exists("firebase_credentials.json"):
        cred = credentials.Certificate("firebase_credentials.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully.")
    else:
        logger.error("FATAL: firebase_credentials.json not found. Please download it from your Firebase project settings.")
        db = None # Set db to None to indicate Firebase is not available
        exit()
except Exception as e:
    logger.error(f"FATAL: Failed to initialize Firebase: {e}")
    db = None
    exit()

# --- CARD DEFINITIONS ---
POWER_CARDS = {
    # Tier 1: Utility & Minor Effects
    'speed': {'name': 'Speed', 'description': 'Instantly gain 20 Power Coins. A quick boost to get you ahead!', 'price': 15, 'icon': '⚡️', 'requires_target': False},
    'vision': {'name': 'Vision', 'description': 'Secretly view the card inventory of a target player.', 'price': 20, 'icon': '👁️', 'requires_target': True},
    'angel': {'name': 'Angel', 'description': 'Gift 20 of your own Power Coins to another player.', 'price': 10, 'icon': '👼', 'requires_target': True},
    'blackout': {'name': 'Blackout', 'description': 'For 4 hours, you are immune to Vision and Spotlight cards.', 'price': 15, 'icon': '🕶️', 'requires_target': False},
    'reroll': {'name': 'Re-roll', 'description': 'Discard your entire hand to gain back 75% of its total coin value.', 'price': 15, 'icon': '♻️', 'requires_target': False},
    'black_market': {'name': 'Black Market', 'description': 'For 1 hour, all items in the store are 50% off for you.', 'price': 10, 'icon': '💰', 'requires_target': False},
    
    # Tier 2: Direct Interaction
    'flame': {'name': 'Flame', 'description': 'Burn 10 Power Coins from a target player.', 'price': 25, 'icon': '🔥', 'requires_target': True},
    'glitch': {'name': 'Glitch', 'description': 'Force a target player to randomly discard one of their cards.', 'price': 30, 'icon': '🌀', 'requires_target': True},
    'spotlight': {'name': 'Spotlight', 'description': 'Publicly reveal a target player\'s entire card inventory to the group.', 'price': 25, 'icon': '�', 'requires_target': True},
    'time_warp': {'name': 'Time Warp', 'description': 'Immediately end an active Karma effect on a target player.', 'price': 25, 'icon': '⏳', 'requires_target': True},
    'mirage': {'name': 'Mirage', 'description': 'For 1 hour, Vision/Spotlight used on you will show a fake hand.', 'price': 25, 'icon': '🏜️', 'requires_target': False},
    
    # Tier 3: Powerful Effects
    'forcefield': {'name': 'Forcefield', 'description': 'Block the next negative card used on you.', 'price': 35, 'icon': '🛡️', 'requires_target': False},
    'devil': {'name': 'Devil', 'description': 'Steal 25 Power Coins from an opponent.', 'price': 40, 'icon': '😈', 'requires_target': True},
    'karma': {'name': 'Karma', 'description': 'For 4 hours, any negative card used on you is reflected back to the sender.', 'price': 45, 'icon': '⚖️', 'requires_target': False},
    'swap': {'name': 'Swap', 'description': 'Swap a random card from your hand with a random card from a target\'s hand.', 'price': 35, 'icon': '🔄', 'requires_target': True},
    'inflation': {'name': 'Inflation', 'description': 'For 1 hour, all card prices in the store are doubled for everyone but you.', 'price': 40, 'icon': '📈', 'requires_target': False},

    # Special Tier: Game-Changing Power
    'god': {'name': 'God', 'description': 'Choose one of three powers: Blessing (give a Forcefield), Smite (target loses half their coins), or Tribute (all other players pay you 5 coins).', 'price': 60, 'icon': '🛐', 'requires_target': False},
}

NEGATIVE_CARDS = {'flame', 'glitch', 'devil', 'swap', 'spotlight'}


# --- HELPER FUNCTIONS ---

def escape_markdown_v2(text: str) -> str:
    """Escapes characters for Telegram's MarkdownV2 parse mode."""
    if not text:
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def get_player_ref(user_id: int):
    """Returns a Firestore reference to a player's profile."""
    if not db: return None
    return db.collection(f'artifacts/{FIREBASE_APP_ID}/users').document(str(user_id))

def get_game_state_ref():
    """Returns a Firestore reference to the global game state."""
    if not db: return None
    return db.collection(f'artifacts/{FIREBASE_APP_ID}/state').document('game_data')

def get_player_data(user_id: int):
    """Retrieves player data from Firestore."""
    player_ref = get_player_ref(user_id)
    if not player_ref: return None
    doc = player_ref.get()
    return doc.to_dict() if doc.exists else None

async def log_activity(bot: Bot, message: str):
    """Logs an activity message."""
    logger.info(f"ACTIVITY: {message}")

# --- COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Registers a new player."""
    user = update.effective_user
    player_ref = get_player_ref(user.id)
    
    if not player_ref:
        await update.message.reply_text("Database is not configured. Please contact the admin.")
        return

    if not player_ref.get().exists:
        player_data = {
            'userId': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'coins': 50,
            'cards': [],
            'status': {
                'protected': False,
                'karma_active': False,
                'blackout_until': 0,
                'mirage_until': 0,
                'black_market_until': 0
            },
            'createdAt': firestore.SERVER_TIMESTAMP
        }
        player_ref.set(player_data)
        await update.message.reply_text(
            f"Welcome, {user.first_name}! 🎉\n\n"
            "You have joined the Power Store tournament and received 50 starter Power Coins (PC).\n\n"
            "Here are some commands to get you started:\n"
            "/profile - Check your coins and cards.\n"
            "/store - See available power cards.\n"
            "/help - Show this message again."
        )
        await log_activity(context.bot, f"🎉 {user.first_name} (@{user.username}) has joined the game.")
    else:
        player_ref.update({
            'username': user.username,
            'first_name': user.first_name
        })
        await update.message.reply_text("You are already registered! Use /profile to see your status.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    await update.message.reply_text(
        "--- Power Store Bot Help ---\n\n"
        "/start - Join the game.\n"
        "/profile - Check your coins and cards.\n"
        "/store - Browse and buy power cards.\n"
        "/use <CardName> - Use a power card. (Reply to a user's message to target them).\n\n"
        "--- Admin Commands ---\n"
        "/award <amount> @username - Give coins to a player.\n"
        "/givecard <CardName> @username - Give a card to a player.\n"
        "/allplayers - View a summary of all players."
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the player's profile."""
    user_id = update.effective_user.id
    player_data = get_player_data(user_id)

    if not player_data:
        await update.message.reply_text("You are not registered yet. Use /start to join.")
        return

    safe_first_name = escape_markdown_v2(player_data.get('first_name', ''))

    cards_list = [POWER_CARDS[card_id]['name'] for card_id in player_data.get('cards', []) if card_id in POWER_CARDS]
    cards_str = escape_markdown_v2(", ".join(cards_list) if cards_list else "None")
    
    status_list = []
    status = player_data.get('status', {})
    now = time.time()
    if status.get('protected'):
        status_list.append("Protected 🛡️")
    if status.get('karma_active'):
        status_list.append("Karma Active ⚖️")
    if status.get('blackout_until', 0) > now:
        status_list.append("Blackout Active 🕶️")
    if status.get('mirage_until', 0) > now:
        status_list.append("Mirage Active 🏜️")
    if status.get('black_market_until', 0) > now:
        status_list.append("In the Black Market 💰")
    
    game_state_ref = get_game_state_ref()
    if game_state_ref:
        game_state_doc = game_state_ref.get()
        game_state = game_state_doc.to_dict() if game_state_doc.exists else {}
        inflation_active = game_state.get('inflation_until', 0) > time.time()
        inflation_user_id = game_state.get('inflation_user_id')
        if inflation_active and user_id != inflation_user_id:
            status_list.append("Affected by Inflation 📈")

    status_str = ", ".join(status_list) if status_list else "Normal"


    message = (
        f"👤 *Profile for {safe_first_name}*\n\n"
        f"💰 *Power Coins:* {player_data.get('coins', 0)} PC\n"
        f"🎴 *Your Cards:* {cards_str}\n"
        f"✨ *Status:* {status_str}"
    )
    await update.message.reply_text(message, parse_mode='MarkdownV2')

# --- INTERACTIVE STORE ---

def build_store_menu(user_id):
    """Builds the main store menu text and keyboard markup, considering inflation and black market."""
    game_state_ref = get_game_state_ref()
    if not game_state_ref:
        return "The store is currently unavailable.", None

    game_state_doc = game_state_ref.get()
    game_state = game_state_doc.to_dict() if game_state_doc.exists else {}
    
    player_data = get_player_data(user_id)
    player_status = player_data.get('status', {}) if player_data else {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()

    text = "🛒 *Welcome to the Power Store\\!* \nSelect a card to view its details:"
    if black_market_active:
        text += "\n\n💰 *Black Market prices are active\\! All cards are 50% off for you\\!*"
    elif inflation_active and user_id != inflation_user_id:
        text += "\n\n📈 *Inflation is active\\! Prices are doubled\\!*"

    keyboard = []
    for card_id, card in POWER_CARDS.items():
        button_text = f"{card['icon']} {card['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"inspect_{card_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return text, reply_markup

async def store_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the power card store."""
    text, reply_markup = build_store_menu(update.effective_user.id)
    if reply_markup:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(text)


async def handle_inspect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles showing the details of a single card."""
    query = update.callback_query
    await query.answer()
    card_id = query.data.split('_', 1)[1]
    card = POWER_CARDS[card_id]
    user_id = query.from_user.id

    game_state_ref = get_game_state_ref()
    if not game_state_ref:
        await query.edit_message_text("Store is currently unavailable.")
        return
        
    game_state_doc = game_state_ref.get()
    game_state = game_state_doc.to_dict() if game_state_doc.exists else {}
    
    player_data = get_player_data(user_id)
    player_status = player_data.get('status', {}) if player_data else {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()

    price = card['price']
    if black_market_active:
        price = int(price * 0.5)
    elif inflation_active and user_id != inflation_user_id:
        price = int(price * 2)

    text = (
        f"{card['icon']} *{escape_markdown_v2(card['name'])}*\n\n"
        f"*Power:* {escape_markdown_v2(card['description'])}\n"
        f"*Cost:* {price} PC"
    )

    keyboard = [
        [InlineKeyboardButton(f"💰 Buy this card ({price} PC)", callback_data=f"buy_{card_id}")],
        [InlineKeyboardButton("⬅️ Back to Store", callback_data="back_to_store")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='MarkdownV2')

async def handle_back_to_store_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Back to Store' button press."""
    query = update.callback_query
    await query.answer()
    text, reply_markup = build_store_menu(query.from_user.id)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='MarkdownV2')

@firestore.transactional
def buy_card_transaction(transaction, player_ref, card_id, card_info, price):
    """Transactional logic for buying a card."""
    player_doc = player_ref.get(transaction=transaction)
    if not player_doc.exists:
        raise Exception("Player not found.")

    player_data = player_doc.to_dict()
    current_coins = player_data.get('coins', 0)

    if current_coins < price:
        raise Exception(f"Insufficient funds! You need {price} PC but only have {current_coins} PC.")
    
    transaction.update(player_ref, {
        'coins': firestore.Increment(-price),
        'cards': firestore.ArrayUnion([card_id])
    })
    return f"✅ Success! You bought a {card_info['name']} card for {price} PC."

async def handle_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the callback from the store's buy buttons."""
    query = update.callback_query
    await query.answer()
    card_id = query.data.split('_', 1)[1]
    card = POWER_CARDS[card_id]
    user_id = query.from_user.id
    player_ref = get_player_ref(user_id)

    if not player_ref:
        await query.edit_message_text("Database not available.")
        return

    game_state_ref = get_game_state_ref()
    game_state_doc = game_state_ref.get()
    game_state = game_state_doc.to_dict() if game_state_doc.exists else {}
    
    player_data = get_player_data(user_id)
    player_status = player_data.get('status', {}) if player_data else {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()

    price = card['price']
    if black_market_active:
        price = int(price * 0.5)
    elif inflation_active and user_id != inflation_user_id:
        price = int(price * 2)
    
    try:
        transaction = db.transaction()
        result = buy_card_transaction(transaction, player_ref, card_id, card, price)
        
        await query.edit_message_text(text=result)
        if "Success" in result:
                await log_activity(context.bot, f"🛒 {query.from_user.first_name} bought a {card['name']} card.")

    except Exception as e:
        logger.error(f"Error during buy transaction: {e}")
        await query.edit_message_text(text=f"Purchase failed: {e}")

async def use_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /use command with robust parsing for card names and IDs."""
    user = update.effective_user
    args = context.args
    
    if not args:
        await update.message.reply_text("Usage: /use <Card Name or ID> [args...]")
        return

    # --- Card Name/ID Parsing Logic ---
    card_id = None
    card_args = []
    
    if args[0].lower() in POWER_CARDS:
        card_id = args[0].lower()
        card_args = args[1:]
    else:
        potential_name = ""
        for i, arg in enumerate(args):
            potential_name = (potential_name + " " + arg).strip()
            found_card_id = next((cid for cid, c in POWER_CARDS.items() if c['name'].lower() == potential_name.lower()), None)
            if found_card_id:
                card_id = found_card_id
                card_args = args[i+1:]
                break

    if not card_id:
        await update.message.reply_text(f"Card not found. Please use the exact card name or ID.")
        return
        
    # --- End of Parsing Logic ---

    player_data = get_player_data(user.id)
    if not player_data or card_id not in player_data.get('cards', []):
        await update.message.reply_text(f"You don't have a {POWER_CARDS[card_id]['name']} card.")
        return
    
    if card_id == 'god':
        await execute_god_power(update, context, user, card_args)
        return
        
    card = POWER_CARDS[card_id]
    target_user = None
    if card['requires_target']:
        if not update.message.reply_to_message:
            await update.message.reply_text(f"To use the {card['name']} card, you must reply to a message from the player you want to target.")
            return
        target_user = update.message.reply_to_message.from_user
        if target_user.id == user.id:
            await update.message.reply_text("You cannot target yourself with this card.")
            return

    try:
        await execute_card_effect(update, context, user, card_id, target_user)
    except Exception as e:
        logger.error(f"Error executing card effect: {e}")
        await update.message.reply_text(f"Action failed: {e}")

@firestore.transactional
def use_card_transaction(transaction, user_ref, target_ref, card_id, game_state_ref):
    """Transactional logic for using a card."""
    card = POWER_CARDS[card_id]
    
    user_doc = user_ref.get(transaction=transaction)
    if not user_doc.exists:
        raise Exception("Your player data was not found.")
    
    user_data = user_doc.to_dict()
    user_name = user_data.get('first_name', 'A player')

    target_doc = None
    target_data = {}
    target_name = ""
    if target_ref:
        target_doc = target_ref.get(transaction=transaction)
        if not target_doc.exists:
            raise Exception("Target player not found.")
        target_data = target_doc.to_dict()
        target_name = target_data.get('first_name', 'another player')

    if card_id in NEGATIVE_CARDS and target_ref:
        if target_data.get('status', {}).get('karma_active'):
            effect_target_ref = user_ref
            effect_target_data = user_data
            
            if card_id == 'flame':
                transaction.update(effect_target_ref, {'coins': firestore.Increment(-10)})
            elif card_id == 'devil':
                stolen_amount = min(25, effect_target_data.get('coins', 0))
                transaction.update(effect_target_ref, {'coins': firestore.Increment(-stolen_amount)})
            elif card_id == 'glitch':
                user_cards = effect_target_data.get('cards', [])
                if user_cards:
                    card_to_discard = random.choice(user_cards)
                    transaction.update(effect_target_ref, {'cards': firestore.ArrayRemove([card_to_discard])})
            
            transaction.update(user_ref, {'cards': firestore.ArrayRemove([card_id])})
            return {'public': f"⚖️ Karma! {target_name}'s karma reflected the {card['name']} card back onto {user_name}!"}

        if target_data.get('status', {}).get('protected'):
            transaction.update(target_ref, {'status.protected': False})
            transaction.update(user_ref, {'cards': firestore.ArrayRemove([card_id])})
            return {'public': f"🛡️ Blocked! {target_name}'s Forcefield deflected the {card['name']} card!"}

    effect_message = ""

    if card_id == 'speed':
        transaction.update(user_ref, {'coins': firestore.Increment(20)})
        effect_message = f"⚡️ {user_name} used a Speed card and instantly gained 20 Power Coins!"
    elif card_id == 'reroll':
        cards_to_reroll = [c for c in user_data.get('cards', []) if c != 'reroll']
        if not cards_to_reroll:
            raise Exception("You have no other cards to re-roll!")
        
        value_to_regain = 0
        for c_id in cards_to_reroll:
            value_to_regain += POWER_CARDS.get(c_id, {}).get('price', 0)
        
        coins_gained = int(value_to_regain * 0.75)
        transaction.update(user_ref, {
            'cards': firestore.ArrayRemove(cards_to_reroll),
            'coins': firestore.Increment(coins_gained)
        })
        effect_message = f"♻️ {user_name} used Re-roll, discarded {len(cards_to_reroll)} cards, and regained {coins_gained} coins!"

    elif card_id == 'flame':
        transaction.update(target_ref, {'coins': firestore.Increment(-10)})
        effect_message = f"🔥 {user_name} used Flame on {target_name}, burning 10 Power Coins!"
    elif card_id == 'angel':
        if user_data.get('coins', 0) < 20:
            raise Exception("You need at least 20 coins to use the Angel card.")
        transaction.update(user_ref, {'coins': firestore.Increment(-20)})
        transaction.update(target_ref, {'coins': firestore.Increment(20)})
        effect_message = f"👼 {user_name} used an Angel card to gift 20 Power Coins to {target_name}!"
    elif card_id == 'devil':
        stolen_amount = min(25, target_data.get('coins', 0))
        transaction.update(target_ref, {'coins': firestore.Increment(-stolen_amount)})
        transaction.update(user_ref, {'coins': firestore.Increment(stolen_amount)})
        effect_message = f"😈 {user_name} used a Devil card and stole {stolen_amount} Power Coins from {target_name}!"
    elif card_id == 'karma':
        transaction.update(user_ref, {'status.karma_active': True})
        effect_message = f"⚖️ {user_name} activated a Karma card! Negative cards will be reflected for 4 hours."
    elif card_id == 'forcefield':
        transaction.update(user_ref, {'status.protected': True})
        effect_message = f"🛡️ {user_name} activated a Forcefield and is now protected from the next negative card."
    elif card_id == 'vision':
        if target_data.get('status', {}).get('blackout_until', 0) > time.time():
            return {'private': f"🕶️ Your Vision was blocked! {target_name} is under a Blackout.", 'public': f"👁️ {user_name} used a Vision card on another player."}
        if target_data.get('status', {}).get('mirage_until', 0) > time.time():
            fake_cards = [random.choice(list(POWER_CARDS.keys())) for _ in range(random.randint(1, 3))]
            cards_list = [POWER_CARDS[cid]['name'] for cid in fake_cards]
            cards_str = ", ".join(cards_list)
            return {'private': f"🏜️ You used Vision on {target_name}. A mirage shows they are holding: {cards_str}.", 'public': f"👁️ {user_name} used a Vision card on another player."}
        target_cards = target_data.get('cards', [])
        if not target_cards:
            cards_str = "None"
        else:
            cards_list = [POWER_CARDS[cid]['name'] for cid in target_cards if cid in POWER_CARDS]
            cards_str = ", ".join(cards_list)
        return {'private': f"👁️ You used Vision on {target_name}. They are holding: {cards_str}.", 'public': f"👁️ {user_name} used a Vision card on another player."}
    elif card_id == 'spotlight':
        if target_data.get('status', {}).get('blackout_until', 0) > time.time():
            effect_message = f"🕶️ {user_name}'s Spotlight was blocked! {target_name} is under a Blackout."
        elif target_data.get('status', {}).get('mirage_until', 0) > time.time():
            fake_cards = [random.choice(list(POWER_CARDS.keys())) for _ in range(random.randint(1, 3))]
            cards_list = [POWER_CARDS[cid]['name'] for cid in fake_cards]
            cards_str = ", ".join(cards_list)
            effect_message = f"💡 {user_name} used Spotlight on {target_name}! A mirage shows their cards are: {cards_str}"
        else:
            target_cards = target_data.get('cards', [])
            if not target_cards:
                cards_str = "None"
            else:
                cards_list = [POWER_CARDS[cid]['name'] for cid in target_cards if cid in POWER_CARDS]
                cards_str = ", ".join(cards_list)
            effect_message = f"💡 {user_name} used Spotlight on {target_name}! Their cards are: {cards_str}"
    elif card_id == 'blackout':
        four_hours_from_now = time.time() + (4 * 60 * 60)
        transaction.update(user_ref, {'status.blackout_until': four_hours_from_now})
        effect_message = f"🕶️ {user_name} activated Blackout! They are immune to Vision and Spotlight for 4 hours."
    elif card_id == 'mirage':
        one_hour_from_now = time.time() + (1 * 60 * 60)
        transaction.update(user_ref, {'status.mirage_until': one_hour_from_now})
        effect_message = f"🏜️ {user_name} cast a Mirage on themself! Their hand will appear differently to spies for 1 hour."
    elif card_id == 'time_warp':
        transaction.update(target_ref, {'status.karma_active': False})
        effect_message = f"⏳ {user_name} used Time Warp on {target_name}, ending their Karma effect immediately!"
    elif card_id == 'glitch':
        target_cards = target_data.get('cards', [])
        if not target_cards:
            effect_message = f"🌀 {user_name} tried to glitch {target_name}, but they had no cards to discard!"
        else:
            card_to_discard = random.choice(target_cards)
            transaction.update(target_ref, {'cards': firestore.ArrayRemove([card_to_discard])})
            discarded_card_name = POWER_CARDS[card_to_discard]['name']
            effect_message = f"🌀 {user_name} glitched {target_name}'s hand, forcing them to discard a {discarded_card_name} card!"
    elif card_id == 'swap':
        user_cards = user_data.get('cards', [])
        target_cards = target_data.get('cards', [])
        user_cards_for_swap = [c for c in user_cards if c != 'swap']

        if not user_cards_for_swap or not target_cards:
            effect_message = f"🔄 {user_name} tried to swap cards with {target_name}, but the swap failed because one player had no cards to trade!"
        else:
            card_from_user = random.choice(user_cards_for_swap)
            card_from_target = random.choice(target_cards)

            transaction.update(user_ref, {'cards': firestore.ArrayRemove([card_from_user])})
            transaction.update(user_ref, {'cards': firestore.ArrayUnion([card_from_target])})
            transaction.update(target_ref, {'cards': firestore.ArrayRemove([card_from_target])})
            transaction.update(target_ref, {'cards': firestore.ArrayUnion([card_from_user])})
            effect_message = f"🔄 {user_name} used a Swap card on {target_name}! A random card was exchanged between them."
    
    elif card_id == 'inflation':
        one_hour_from_now = time.time() + (1 * 60 * 60)
        # Use set with merge=True to create the document if it doesn't exist
        transaction.set(game_state_ref, {
            'inflation_until': one_hour_from_now,
            'inflation_user_id': user_data['userId']
        }, merge=True)
        effect_message = f"📈 {user_name} used Inflation! For the next 1 hour, card prices are doubled for everyone else."

    elif card_id == 'black_market':
        one_hour_from_now = time.time() + (1 * 60 * 60)
        transaction.update(user_ref, {'status.black_market_until': one_hour_from_now})
        effect_message = f"💰 {user_name} used Black Market! For the next hour, all store prices are 50% off for you."

    transaction.update(user_ref, {'cards': firestore.ArrayRemove([card_id])})
    
    return {'public': effect_message}

async def execute_card_effect(update: Update, context: ContextTypes.DEFAULT_TYPE, user, card_id, target_user):
    """The core logic for what happens when a card is used."""
    user_ref = get_player_ref(user.id)
    target_ref = get_player_ref(target_user.id) if target_user else None
    
    if not db:
        await update.message.reply_text("Database not available.")
        return

    transaction = db.transaction()
    game_state_ref = get_game_state_ref()
    result = use_card_transaction(transaction, user_ref, target_ref, card_id, game_state_ref)
    
    if 'public' in result and result['public']:
        await update.message.reply_text(result['public'])
    if 'private' in result and result['private']:
        await context.bot.send_message(chat_id=user.id, text=result['private'])
        
    await log_activity(update.get_bot(), result.get('public') or result.get('private'))

# --- GOD CARD LOGIC ---

@firestore.transactional
def god_power_transaction(transaction, db_ref, user_ref, power, target_ref=None):
    """Transactional logic for using a God card power."""
    user_doc = user_ref.get(transaction=transaction)
    user_data = user_doc.to_dict()
    user_name = user_data.get('first_name', 'A player')
    
    effect_message = ""

    if power == 'blessing':
        if not target_ref: raise Exception("Blessing power requires a target.")
        target_doc = target_ref.get(transaction=transaction)
        if not target_doc.exists: raise Exception("Target player not found.")
        target_name = target_doc.to_dict().get('first_name', 'another player')
        
        transaction.update(target_ref, {'cards': firestore.ArrayUnion(['forcefield'])})
        effect_message = f"🛐 {user_name} used God's Blessing on {target_name}, granting them a Forcefield card!"

    elif power == 'smite':
        if not target_ref: raise Exception("Smite power requires a target.")
        target_doc = target_ref.get(transaction=transaction)
        if not target_doc.exists: raise Exception("Target player not found.")
        target_name = target_doc.to_dict().get('first_name', 'another player')
        target_coins = target_doc.to_dict().get('coins', 0)
        coins_lost = target_coins // 2
        
        transaction.update(target_ref, {'coins': firestore.Increment(-coins_lost)})
        effect_message = f"🛐 {user_name} used God's Smite on {target_name}, destroying half their coins ({coins_lost} PC)!"

    elif power == 'tribute':
        effect_message = f"🛐 {user_name} used God's Tribute, demanding 5 coins from all other players!"

    else:
        raise Exception("Invalid God power.")

    transaction.update(user_ref, {'cards': firestore.ArrayRemove(['god'])})
    return effect_message

async def execute_god_power(update: Update, context: ContextTypes.DEFAULT_TYPE, user, args):
    """Handles the logic for using the God card's specific powers."""
    if not db:
        await update.message.reply_text("Database not available.")
        return
        
    try:
        if len(args) < 1:
            await update.message.reply_text("You must specify a power. Usage: /use God <Blessing|Smite|Tribute> [@target]")
            return
        
        power = args[0].lower()
        user_ref = get_player_ref(user.id)
        target_ref = None
        
        if power in ['blessing', 'smite']:
            if len(args) < 2:
                await update.message.reply_text(f"The '{power}' power requires a target. Usage: /use God {power} @username")
                return
            
            username = args[1].lstrip('@')
            users_ref = db.collection(f'artifacts/{FIREBASE_APP_ID}/users')
            query = users_ref.where('username', '==', username).limit(1)
            results = query.stream()
            target_doc = next(results, None)

            if not target_doc:
                await update.message.reply_text(f"Player @{username} not found.")
                return
            target_ref = target_doc.reference

        if power == 'tribute':
            users_ref = db.collection(f'artifacts/{FIREBASE_APP_ID}/users')
            all_players = users_ref.stream()
            total_tribute = 0
            other_player_refs = []

            for player_doc in all_players:
                if str(player_doc.id) != str(user.id):
                    player_data = player_doc.to_dict()
                    coins_to_pay = min(5, player_data.get('coins', 0))
                    total_tribute += coins_to_pay
                    other_player_refs.append(player_doc.reference)
            
            @firestore.transactional
            def tribute_transaction(transaction):
                for player_ref in other_player_refs:
                    transaction.update(player_ref, {'coins': firestore.Increment(-5)})
                transaction.update(user_ref, {'coins': firestore.Increment(total_tribute)})
            
            transaction = db.transaction()
            tribute_transaction(transaction)
            result_message = f"🛐 {user.first_name} used God's Tribute, collecting a total of {total_tribute} coins from all other players!"
            await update.message.reply_text(result_message)
            await log_activity(context.bot, result_message)
            user_ref.update({'cards': firestore.ArrayRemove(['god'])})
            return

        transaction = db.transaction()
        result_message = god_power_transaction(transaction, db, user_ref, power, target_ref)
        await update.message.reply_text(result_message)
        await log_activity(context.bot, result_message)

    except Exception as e:
        logger.error(f"Error executing God power: {e}")
        await update.message.reply_text(f"Action failed: {e}")


# --- ADMIN COMMANDS ---

async def all_players_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view all player stats."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not db:
        await update.message.reply_text("Database not available.")
        return

    try:
        users_ref = db.collection(f'artifacts/{FIREBASE_APP_ID}/users')
        all_user_docs = users_ref.stream()

        report_lines = ["📊 *All Players Report*\n"]
        player_found = False

        for user_doc in all_user_docs:
            player_found = True
            player_data = user_doc.to_dict()

            if player_data:
                username = player_data.get('username', f"ID: {user_doc.id}")
                safe_username = escape_markdown_v2(username)
                
                coins = player_data.get('coins', 0)
                cards_list = [POWER_CARDS[card_id]['name'] for card_id in player_data.get('cards', []) if card_id in POWER_CARDS]
                cards_str = escape_markdown_v2(", ".join(cards_list) if cards_list else "None")
                
                report_lines.append(
                    f"\n👤 *@{safe_username}*\n"
                    f"   💰 Coins: {coins} PC\n"
                    f"   🎴 Cards: {cards_str}"
                )

        if not player_found:
            await update.message.reply_text("No players have registered yet.")
            return

        report = "\n".join(report_lines)
        await update.message.reply_text(report, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in /allplayers command: {e}")
        await update.message.reply_text("An error occurred while fetching player data.")

async def award_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to award coins to a player."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not db:
        await update.message.reply_text("Database not available.")
        return

    try:
        amount_str, username = context.args
        amount = int(amount_str)
        username = username.lstrip('@')

        users_ref = db.collection(f'artifacts/{FIREBASE_APP_ID}/users')
        query = users_ref.where('username', '==', username).limit(1)
        results = query.stream()
        
        target_doc = next(results, None)

        if not target_doc:
            await update.message.reply_text(f"Player @{username} not found in the database. They must use /start first.")
            return

        target_ref = target_doc.reference
        target_ref.update({'coins': firestore.Increment(amount)})
        
        await update.message.reply_text(f"✅ Successfully awarded {amount} PC to @{username}.")
        await log_activity(context.bot, f"👑 Admin awarded {amount} PC to @{username}.")

    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /award <amount> @username")
    except Exception as e:
        logger.error(f"Error in /award command: {e}")
        await update.message.reply_text("An error occurred while awarding coins.")

async def givecard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to give a card to a player."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not db:
        await update.message.reply_text("Database not available.")
        return
    
    try:
        card_name_query, username = context.args
        username = username.lstrip('@')
        card_id = next((cid for cid, c in POWER_CARDS.items() if c['name'].lower() == card_name_query.lower()), None)
        
        if not card_id:
            await update.message.reply_text(f"Card '{card_name_query}' not found.")
            return

        users_ref = db.collection(f'artifacts/{FIREBASE_APP_ID}/users')
        query = users_ref.where('username', '==', username).limit(1)
        results = query.stream()
        
        target_doc = next(results, None)

        if not target_doc:
            await update.message.reply_text(f"Player @{username} not found in the database. They must use /start first.")
            return
            
        target_ref = target_doc.reference
        target_ref.update({'cards': firestore.ArrayUnion([card_id])})
        card_name = POWER_CARDS[card_id]['name']
        
        await update.message.reply_text(f"✅ Successfully gave a {card_name} card to @{username}.")
        await log_activity(context.bot, f"👑 Admin gave a {card_name} card to @{username}.")

    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /givecard <CardName> @username")
    except Exception as e:
        logger.error(f"Error in /givecard command: {e}")
        await update.message.reply_text("An error occurred while giving the card.")


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("FATAL: TELEGRAM_BOT_TOKEN is not configured. Please set it in config.py.")
        return
        
    if not db:
        logger.error("FATAL: Firebase is not initialized. The bot cannot start.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("store", store_command))
    application.add_handler(CommandHandler("use", use_command))
    
    # Admin command handlers
    application.add_handler(CommandHandler("award", award_command))
    application.add_handler(CommandHandler("givecard", givecard_command))
    application.add_handler(CommandHandler("allplayers", all_players_command))

    # Callback query handlers for the interactive store
    application.add_handler(CallbackQueryHandler(handle_inspect_callback, pattern="^inspect_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_store_callback, pattern="^back_to_store$"))
    application.add_handler(CallbackQueryHandler(handle_buy_callback, pattern="^buy_"))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling()
    logger.info("Bot has stopped.")

if __name__ == "__main__":
    main()