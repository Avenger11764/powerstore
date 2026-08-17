import logging
import os
import re
import random
import time
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.request import HTTPXRequest
from supabase import create_client, Client

# --- CONFIGURATION (Environment variables with config.py fallback) ---
try:
    import config
except ImportError:
    config = None

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, "TELEGRAM_BOT_TOKEN", None)
ADMIN_USER_ID_VAL = os.environ.get("ADMIN_USER_ID") or getattr(config, "ADMIN_USER_ID", None)
SUPABASE_URL = os.environ.get("SUPABASE_URL") or getattr(config, "SUPABASE_URL", None)
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or getattr(config, "SUPABASE_KEY", None)
LOG_CHANNEL_ID = os.environ.get("LOG_CHANNEL_ID") or getattr(config, "LOG_CHANNEL_ID", None)

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")

ADMIN_USER_IDS = [7602825139, 1253445521]
if ADMIN_USER_ID_VAL:
    try:
        val = int(ADMIN_USER_ID_VAL)
        if val not in ADMIN_USER_IDS:
            ADMIN_USER_IDS.append(val)
    except ValueError:
        pass

if hasattr(config, "ADMIN_USER_IDS"):
    for aid in config.ADMIN_USER_IDS:
        if int(aid) not in ADMIN_USER_IDS:
            ADMIN_USER_IDS.append(int(aid))

ADMIN_USER_ID = ADMIN_USER_IDS[0]

def is_admin(user_id: int) -> bool:
    """Checks if a user ID is an authorized admin."""
    try:
        return int(user_id) in ADMIN_USER_IDS
    except Exception:
        return False

# --- SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

db: Client = None
try:
    if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL != "YOUR_SUPABASE_URL" and SUPABASE_KEY != "YOUR_SUPABASE_KEY":
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
        key_prefix = SUPABASE_KEY[:12] if len(SUPABASE_KEY) >= 12 else SUPABASE_KEY
        logger.info(f"Supabase initialized successfully with key prefix: {key_prefix}...")
    else:
        logger.warning("Supabase URL or Key not fully configured. Using placeholder database state.")
except Exception as e:
    logger.error(f"FATAL: Failed to initialize Supabase: {e}")
    db = None


# --- CARD DEFINITIONS ---
POWER_CARDS = {
    # Tier 1: Utility & Minor Effects
    'speed': {'name': 'Speed', 'description': 'Reduces the cooldown time on your card usage by half for the next 1 hour.', 'price': 20, 'icon': '⚡️', 'tier': 1, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWZlbjB5YXZibzdnZmF4MG05Mm02dDc0ejZwcnJ2eHU5YTQwcWpweCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3ornjIhZGFWpbcGMAU/giphy.gif'},
    'vision': {'name': 'Vision', 'description': 'Secretly view the card inventory of a target player.', 'price': 20, 'icon': '👁️', 'tier': 1, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2JkamxzaTNwMXo4ZXJreHl5a3M5dnFxMGowNTdsbm9sbmRpbnhhOSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o7bufkPz3LRof205G/giphy.gif'},
    'angel': {'name': 'Angel', 'description': 'Gift 20 of your own Power Coins to another player.', 'price': 20, 'icon': '👼', 'tier': 1, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeHRmbDlncDAxeHN4eGFqem5weWkxMXV4eDB1bjY3ajZ1NGFzeHBtNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/bGkOcTT6NjuRQQEAAj/giphy.gif'},
    'blackout': {'name': 'Blackout', 'description': 'For 3 hours, you are immune to Vision and Spotlight cards.', 'price': 25, 'icon': '🕶️', 'tier': 1, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdWFwbWJkYmZsN3Bmbm03aTM1NXh4NWQ3Njd4aDM5bDJyczZlODA5ZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Kfg01zJWGDMT6/giphy.gif'},
    'reroll': {'name': 'Re-roll', 'description': 'Discard your entire hand to gain back 75% of its total coin value.', 'price': 15, 'icon': '♻️', 'tier': 1, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdTdyZng0bzloNnlvajdzdDIxc2VjMjl2OTN4MW9wdzlmbHZ0amd2ZyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Loe03BsYRrv13l8h9q/giphy.gif'},
    'black_market': {'name': 'Black Market', 'description': 'For 1 hour, all items in the store are 50% off for you.', 'price': 40, 'icon': '💰', 'tier': 1, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYjJsaXhoOTRsc2V6dHU0YnFyNTl6dHR6d2FoZnM1NXZoMjU2YnU5YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l3vRl0hL5yTjuOFji/giphy.gif'},
    'lottery_ticket': {'name': 'Lottery Ticket', 'description': 'A cheap card with a 2% chance to win 100 coins. A gamble for those feeling lucky.', 'price': 5, 'icon': '🎟️', 'tier': 1, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNzQ1bmc2MW1iMXFlYjRvN2JteW9sNXczOWxtNjU3MzFhbmIzZm0zdCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/30VBSGB7QW1RJpNcHO/giphy.gif'},
    
    # Tier 2: Direct Interaction
    'flame': {'name': 'Flame', 'description': 'Burn 15 Power Coins from a target player.', 'price': 20, 'icon': '🔥', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3Nm41eWMyOWk0bmZodzc0c2xkZmJ4MWNyMnUyeW5vajc2MGowZGFzbiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ASM4IvHzkop00e6sUN/giphy.gif'},
    'glitch': {'name': 'Glitch', 'description': 'Force a target player to randomly discard one of their cards.', 'price': 30, 'icon': '🌀', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcXphOWVramc1bXo4a2tqZ2JtYjF1OG45bzFxODlpYTc2Mm9hZml2cyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/10DnwPMOWFxn7G/giphy.gif'},
    'shackle': {'name': 'Shackle', 'description': 'For 1 hour, your target is unable to use any cards.', 'price': 30, 'icon': '⛓️', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcnF4eW1oNnBtazZnMHozNTFmdjcxazVlODJqZTdvaTUzYm90ZmJmNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/hZfLN9xZyuALtcseXG/giphy.gif'},
    'spotlight': {'name': 'Spotlight', 'description': 'Publicly reveal a target player\'s entire card inventory to the group.', 'price': 25, 'icon': '💡', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeWZqMDIzODFlMWdldjh3eDJrbDdmbzN5cms3MHhyc2RjM29nczQ0aCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/cEy0W6cMR584tK1vbM/giphy.gif'},
    'time_warp': {'name': 'Time Warp', 'description': 'Immediately end an active Karma or Shackle effect on a target player.', 'price': 25, 'icon': '⏳', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdzgwcGQwdzljMXdqeWNzMzdmNWEyc2Zxb3l6bTZ4YzhndXR0YjczMCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3oxRmvU3GAJay6F60g/giphy.gif'},
    'mirage': {'name': 'Mirage', 'description': 'For 1 hour, Vision/Spotlight used on you will show a fake hand.', 'price': 25, 'icon': '🏜️', 'tier': 2, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3VkZ3M3a3U0ampwNTgxN2dkeTgzZmFpeGg3M254NGNjMGdvaXhmbyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3ohzdNDknsTEB1dNny/giphy.gif'},
    'dispel': {'name': 'Dispel', 'description': 'Immediately removes Shackle and personal Inflation effects from yourself.', 'price': 30, 'icon': '💨', 'tier': 2, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWtpczRwbnhxYjFxZmUyMGJyeW5rOXY4YTZ0NmxvNWg5N2NhM2JtdSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3bJr49ky73noj6Pb64/giphy.gif'},
    'double_or_nothing': {'name': 'Double or Nothing', 'description': 'Target a player. You both secretly wager 40 coins. A coin is flipped; the winner takes the entire pot (80 coins).', 'price': 20, 'icon': '🎲', 'tier': 2, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeXk2cXMyODB4bDNhYnI0NXlmMng3eWNvaW5paXhxamUzOGE0MDZqcCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/26uf2YTgF5upXUTm0/giphy.gif'},

    # Tier 3: Powerful Effects
    'forcefield': {'name': 'Forcefield', 'description': 'Block the next negative card used on you.', 'price': 40, 'icon': '🛡️', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeHBtbW54MHliaHhuMjlmcG1zb3BsMG44NW12cHhuOHlwaWtoeW1idCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dyKyTBu6adRKuJpmWU/giphy.gif'},
    'trap': {'name': 'Trap', 'description': 'Set a trap. The next player to target you with a negative card has it nullified and loses 15 coins.', 'price': 50, 'icon': '🪤', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbHk5MGNtY2x6bDhtcW9hc3M5cjdheTgydjZ0eGc5aXltc2RjNTR5ZyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/XYCHHBtZxfmAU/giphy.gif'},
    'ricochet': {'name': 'Ricochet', 'description': 'Activate this card.For the next 1 hr, the next negative card used on you is redirected to a random other player in the game (not the original sender).', 'price': 40, 'icon': '↪️', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMjI4amMyaGp5aTdzd2JrdDdocGFiaGtsc2IycDl4Y2RjdTZ3ZGxmdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/hje9Yxu2SNtNlx80oZ/giphy.gif'},
    'clairvoyance': {'name': 'Clairvoyance', 'description': 'Reveal the true cards of a target user, even if they are hidden using Mirage. Bypasses Mirage, but not Blackout.', 'price': 40, 'icon': '🔮', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eG1iMTlsbnk5dWp5azNocWQyNmtyd3l0enY2cWIxdDUyYmpyMnV4byZlcD12MV9naWZzX3NlYXJjaCZjdD1n/n6EMXWDjT9G8Q0EMCQ/giphy.gif'},
    'devil': {'name': 'Devil', 'description': 'Steal 25 Power Coins from an opponent.', 'price': 35, 'icon': '😈', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZmE5bGtkOGttb2c1Z29tbm9yOW5obnp0MXRtM2x5MGsxMnNob3pvOCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/pw1lmX78sDOyRvMKhZ/giphy.gif'},
    'karma': {'name': 'Karma', 'description': 'For 2 hours, any negative card used on you is reflected back to the sender.', 'price': 45, 'icon': '⚖️', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOGQwdW5wajFuOTI5N3F6dzJlaWE3aWd2NDJzdDVnYzE5MjFja2lpcSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Th9FMIgIgu9hK/giphy.gif'},
    'swap': {'name': 'Swap', 'description': 'Swap a random card from your hand with a random card from a target\'s hand.', 'price': 35, 'icon': '🔄', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdGVyMXk3dzNyOGRqeWsxbm9zejZ4N3QzcXF4ajQ2NXh0bjJwcHlsbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/HWVx61TKUD7nGdruml/giphy.gif'},
    'steal': {'name': 'Steal', 'description': 'Steals a random card from the target user.', 'price': 40, 'icon': '🥷', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExenVqNmVweWFwdzJiOWMxNmN0YzFkZHB2dTQ3bXIzeGlzc28xdmhvayZlcD12MV9naWZzX3NlYXJjaCZjdD1n/HUtsjiqzv1M9a/giphy.gif'},
    'inflation': {'name': 'Inflation', 'description': 'For 1 hour, all card prices in the store are doubled for everyone but you.', 'price': 60, 'icon': '📈', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGtsejkyemNsbWhseXpzaGIxOTJ6eDNheGNoYmp4YjJ1Yjg5dGQ1NiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/gKxSdzHFNUpZ8EKirE/giphy.gif'},
    'purge': {'name': 'Purge', 'description': 'Name a card. If your target has it, they are forced to discard it.', 'price': 50, 'icon': '🎯', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaXNvbGIwMTRvb2FmcmtuaGs4bXZ4MDZnNTMzOWg1ZTRvbHBxbm1qYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/8uvgnTDSSpcVdVMjmf/giphy.gif'},
    'vortex': {'name': 'Vortex', 'description': 'All players in the game (including you) must immediately discard one random card.', 'price': 30, 'icon': '🌪️', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMmRyYXRvb2dmMTJnZGlqOHVzamcxM3Q3cHEzN2U0MGV2eHdwNmticSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/uWXDBmVYdByWreOuRs/giphy.gif'},
    'amnesia': {'name': 'Amnesia', 'description': 'Force a target player to discard their entire hand of cards.', 'price': 75, 'icon': '❓', 'tier': 3, 'requires_target': True, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYjJ4b3FrYWlmNGQ4YjV1dGNoMW9zbDlpcGJ2OWlxOTZob2xzbmZubSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/1zR9zWe9tzwoZi84ws/giphy.gif'},
    'frenzy': {'name': 'Frenzy', 'description': 'Use your next two cards without a cooldown period.', 'price': 35, 'icon': '🔀', 'tier': 3, 'requires_target': False, 'gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcXA4MW0ybDRieXk4ODFwMXZzbDhxY2phYXU0cWFuMGdtcHZoYnVieiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/fcODRi10teFrO/giphy.gif'},

    # Special Tier: Game-Changing Power
    'god': {'name': 'God', 'description': 'Choose one of three powers: Blessing (give a Forcefield), Smite (target loses half their coins), or Tribute (all other players pay you 5 coins).', 'price': 80, 'icon': '🛐', 'tier': 4, 'requires_target': False, 'gifs': {'blessing': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3V3YXZxa3g3Nm41ODZnbjNzbDl2ZXFtN2ttNm1nZG13dThmcmN2MiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/zItSCrxIAg14zNVtjP/giphy.gif', 'smite': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnNpbDJmMGRnZGIzZGswYmx0OXZiem5jYnNnZHMydzI5YXE0cWlhcyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/RKUVT8fPMsRfa/giphy.gif', 'tribute': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWc1cGxveGQ5NmFmZmd6YWhua2gyZzNjdjc2Mm84Nm01aXBjd3ZycCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dAhtjvu5VYan5RjU2r/giphy.gif'}},
}

NEGATIVE_CARDS = {'flame', 'glitch', 'devil', 'swap', 'spotlight', 'purge', 'amnesia', 'shackle', 'steal', 'double_or_nothing'}

import json
import ast

def parse_json_dict(val) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            res = json.loads(val)
            if isinstance(res, dict): return res
        except Exception:
            try:
                res = ast.literal_eval(val)
                if isinstance(res, dict): return res
            except Exception:
                pass
    return {}

def parse_json_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            res = json.loads(val)
            if isinstance(res, list): return res
        except Exception:
            try:
                res = ast.literal_eval(val)
                if isinstance(res, list): return res
            except Exception:
                pass
    return []

def escape_markdown_v2(text) -> str:
    """Escapes characters for Telegram's MarkdownV2 parse mode."""
    if text is None:
        return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', str(text))

async def send_safe_message(target_obj, text: str, reply_markup=None, parse_mode='MarkdownV2'):
    """Sends or edits a message safely, falling back to plain text if MarkdownV2 parsing fails."""
    if target_obj is None:
        return None
    try:
        if hasattr(target_obj, 'reply_text') and callable(getattr(target_obj, 'reply_text', None)):
            return await target_obj.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif hasattr(target_obj, 'edit_message_text') and callable(getattr(target_obj, 'edit_message_text', None)):
            return await target_obj.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif hasattr(target_obj, 'send_message') and callable(getattr(target_obj, 'send_message', None)):
            return await target_obj.send_message(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"Markdown parsing failed ({e}), sending plain text fallback.")
        clean_text = text.replace('*', '').replace('_', '').replace('\\', '')
        try:
            if hasattr(target_obj, 'reply_text') and callable(getattr(target_obj, 'reply_text', None)):
                return await target_obj.reply_text(clean_text, reply_markup=reply_markup)
            elif hasattr(target_obj, 'edit_message_text') and callable(getattr(target_obj, 'edit_message_text', None)):
                return await target_obj.edit_message_text(text=clean_text, reply_markup=reply_markup)
            elif hasattr(target_obj, 'send_message') and callable(getattr(target_obj, 'send_message', None)):
                return await target_obj.send_message(text=clean_text, reply_markup=reply_markup)
        except Exception as e2:
            logger.error(f"Failed to send fallback plain text message: {e2}")

async def safe_reply(update: Update, text: str, reply_markup=None, parse_mode=None):
    """Safely sends a reply using update.effective_message or update.effective_chat."""
    if not update:
        return None
    msg = update.effective_message
    if msg:
        try:
            return await msg.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass
    chat = update.effective_chat
    if chat:
        try:
            return await chat.send_message(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass
    return None

async def safe_reply_animation(update: Update, animation, caption=None, parse_mode=None):
    """Safely sends an animation reply using update.effective_message or update.effective_chat, falling back to safe_reply text."""
    if not update:
        return None
    msg = update.effective_message
    if msg and hasattr(msg, 'reply_animation') and callable(getattr(msg, 'reply_animation', None)):
        try:
            return await msg.reply_animation(animation=animation, caption=caption, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"Could not send animation via msg ({e}), falling back to text.")
    chat = update.effective_chat
    if chat and hasattr(chat, 'send_animation') and callable(getattr(chat, 'send_animation', None)):
        try:
            return await chat.send_animation(animation=animation, caption=caption, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"Could not send animation via chat ({e}), falling back to text.")
    if caption:
        return await safe_reply(update, caption, parse_mode=parse_mode)
    return None

def extract_telegram_id(data: dict):
    if not isinstance(data, dict): return None
    for key in ['Telegram_id', 'telegram_id', 'user_id', 'id', 'Telegram_Id']:
        if key in data and data[key] is not None:
            return data[key]
    return None

def get_player_data(user_id: int) -> dict:
    """Retrieves player data from Supabase using Telegram_id, telegram_id or user_id."""
    if not db: return None
    try:
        response = None
        for col in ['Telegram_id', 'telegram_id', 'user_id']:
            for val in [str(user_id), int(user_id)]:
                try:
                    res = db.table('users').select('*').eq(col, val).execute()
                    if res and res.data and len(res.data) > 0:
                        response = res
                        break
                except Exception:
                    pass
            if response: break

        if response and response.data and len(response.data) > 0:
            data = response.data[0]
            tid = extract_telegram_id(data) or user_id
            data['user_id'] = int(tid)
            data['status'] = parse_json_dict(data.get('status'))
            data['cards'] = parse_json_list(data.get('cards'))
            return data
        return None
    except Exception as e:
        logger.error(f"Error fetching player data for {user_id}: {e}")
        return None

def get_player_by_username(username: str) -> dict:
    """Retrieves player data by Telegram username, first_name, in_game_name or ID."""
    if not db: return None
    clean_username = username.lstrip('@').lower().strip()
    try:
        all_players = get_all_players()
        for p in all_players:
            p_uname = str(p.get('username') or '').lstrip('@').lower().strip()
            p_fname = str(p.get('first_name') or '').lower().strip()
            p_gname = str(p.get('in_game_name') or '').lower().strip()
            p_uid = str(p.get('user_id') or '').lower().strip()
            if clean_username in [p_uname, p_fname, p_gname, p_uid] or (clean_username and clean_username in p_uname):
                return p

        for col in ['username', 'first_name', 'in_game_name']:
            for pattern in [username.lstrip('@'), f"@{username.lstrip('@')}"]:
                try:
                    res = db.table('users').select('*').ilike(col, pattern).execute()
                    if res and res.data and len(res.data) > 0:
                        data = res.data[0]
                        tid = extract_telegram_id(data)
                        if tid: data['user_id'] = int(tid)
                        data['status'] = parse_json_dict(data.get('status'))
                        data['cards'] = parse_json_list(data.get('cards'))
                        return data
                except Exception:
                    pass
        return None
    except Exception as e:
        logger.error(f"Error fetching player by username {username}: {e}")
        return None

def get_all_players_debug() -> tuple:
    """Retrieves all players from Supabase and returns debug details."""
    if not db:
        return [], "Database client is None"
    try:
        res = db.table('users').select('*').execute()
        rows = res.data if res and hasattr(res, 'data') and res.data is not None else []
        players = []
        for data in rows:
            tid = extract_telegram_id(data)
            if tid is not None:
                try:
                    data['user_id'] = int(tid)
                except (ValueError, TypeError):
                    data['user_id'] = tid
            data['status'] = parse_json_dict(data.get('status'))
            data['cards'] = parse_json_list(data.get('cards'))
            players.append(data)
        return players, f"Success (returned {len(rows)} rows)"
    except Exception as e:
        return [], f"Exception: {e}"

def get_all_players() -> list:
    players, _ = get_all_players_debug()
    return players

def save_player_data(user_id: int, player_data: dict):
    """Upserts full player profile into Supabase."""
    if not db: return
    try:
        # Build exact clean payload for Supabase users table schema
        payload = {
            'Telegram_id': str(user_id),
            'username': player_data.get('username') or f"user_{user_id}",
            'first_name': player_data.get('first_name') or "Player",
            'in_game_name': player_data.get('in_game_name') or player_data.get('first_name') or "Player",
            'coins': player_data.get('coins', 5),
            'cards': player_data.get('cards', []),
            'status': player_data.get('status', {}),
            'msgc_registered': player_data.get('msgc_registered', False)
        }
        
        # Primary attempt: upsert using Telegram_id
        try:
            res = db.table('users').upsert(payload, on_conflict='Telegram_id').execute()
            if res and hasattr(res, 'data') and res.data:
                logger.info(f"Successfully saved player {user_id} in Supabase via Telegram_id.")
                return
        except Exception as e1:
            logger.warning(f"Upsert on Telegram_id failed: {e1}")

        # Fallback 1: upsert using lowercase telegram_id
        try:
            payload_fallback = {'telegram_id': str(user_id), **payload}
            payload_fallback.pop('Telegram_id', None)
            res = db.table('users').upsert(payload_fallback, on_conflict='telegram_id').execute()
            if res and hasattr(res, 'data') and res.data:
                logger.info(f"Successfully saved player {user_id} with telegram_id.")
                return
        except Exception as e2:
            logger.warning(f"Upsert on telegram_id failed: {e2}")

        # Fallback 2: insert directly without on_conflict parameter
        try:
            res = db.table('users').insert(payload).execute()
            logger.info(f"Successfully inserted player {user_id} directly.")
        except Exception as e3:
            logger.error(f"Direct insert failed for user {user_id}: {e3}")
    except Exception as e:
        logger.error(f"Error saving player data for {user_id}: {e}")

def update_player_data(user_id: int, updates: dict):
    """Updates specific fields of a player profile in Supabase."""
    if not db: return
    try:
        payload = {**updates}
        payload.pop('user_id', None)
        for col in ['Telegram_id', 'telegram_id', 'user_id']:
            for val in [str(user_id), int(user_id)]:
                try:
                    res = db.table('users').update(payload).eq(col, val).execute()
                    if res and res.data and len(res.data) > 0:
                        return
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error updating player data for {user_id}: {e}")

def ensure_player_registered(user_id: int, telegram_user=None) -> dict:
    """Ensures player is registered in Supabase. Auto-registers if missing."""
    player_data = get_player_data(user_id)
    if not player_data:
        username = getattr(telegram_user, 'username', None) or f"user_{user_id}"
        first_name = getattr(telegram_user, 'first_name', None) or "Player"
        new_player = {
            'user_id': user_id,
            'telegram_id': str(user_id),
            'username': username,
            'first_name': first_name,
            'in_game_name': first_name or username,
            'coins': 5,
            'cards': [],
            'msgc_registered': False,
            'status': {
                'protected': False,
                'karma_active_until': 0,
                'ricochet_active_until': 0,
                'blackout_until': 0,
                'mirage_until': 0,
                'black_market_until': 0,
                'shackled_until': 0,
                'trap_active': False,
                'last_card_use_time': 0,
                'speed_active_until': 0,
                'frenzy_active': 0,
                'inflation_immunity_until': 0
            }
        }
        save_player_data(user_id, new_player)
        player_data = get_player_data(user_id) or new_player
    return player_data

GLOBAL_GAME_STATE = {}

def get_game_state() -> dict:
    """Retrieves global game state, merging in-memory state with Supabase."""
    state = {**GLOBAL_GAME_STATE}
    if db:
        try:
            res = db.table('game_state').select('*').execute()
            if res and hasattr(res, 'data') and res.data:
                for row in res.data:
                    if 'key' in row and 'data' in row:
                        val = row['data']
                        if isinstance(val, dict):
                            state.update(val)
                        else:
                            state[row['key']] = val
                    else:
                        state.update(row)
        except Exception as e:
            logger.warning(f"Failed to fetch game_state from Supabase: {e}")
    return state

def update_game_state(updates: dict):
    """Updates global game state both in-memory and in Supabase."""
    GLOBAL_GAME_STATE.update(updates)
    if not db: return
    try:
        payload = {'id': 'game_data', **updates}
        try:
            db.table('game_state').upsert(payload, on_conflict='id').execute()
        except Exception:
            pass

        for k, v in updates.items():
            try:
                db.table('game_state').upsert({'key': k, 'data': v}, on_conflict='key').execute()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error updating game state: {e}")

async def log_activity(bot: Bot, message: str, title: str = "Power Store Logs"):
    """Logs an activity message to python logger and Telegram channel if configured."""
    logger.info(f"ACTIVITY: {message}")
    if LOG_CHANNEL_ID and bot:
        try:
            formatted_text = f"<b>{title}</b>\n{message}"
            await bot.send_message(chat_id=LOG_CHANNEL_ID, text=formatted_text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send activity log to channel {LOG_CHANNEL_ID}: {e}")


# --- COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command. Registers a new player."""
    user = update.effective_user
    if not user:
        return

    if not db:
        await safe_reply(update, "Database is not configured. Please contact the admin.")
        return

    player_data = get_player_data(user.id)
    if not player_data:
        new_player = {
            'user_id': user.id,
            'telegram_id': str(user.id),
            'username': user.username or f"user_{user.id}",
            'first_name': user.first_name or "Player",
            'in_game_name': user.first_name or user.username or f"Player_{user.id}",
            'coins': 5,
            'cards': [],
            'msgc_registered': False,
            'status': {
                'protected': False,
                'karma_active_until': 0,
                'ricochet_active_until': 0,
                'blackout_until': 0,
                'mirage_until': 0,
                'black_market_until': 0,
                'shackled_until': 0,
                'trap_active': False,
                'last_card_use_time': 0,
                'speed_active_until': 0,
                'frenzy_active': 0,
                'inflation_immunity_until': 0
            }
        }
        save_player_data(user.id, new_player)
        await safe_reply(update, 
            f"Welcome, {user.first_name}! 🎉\n\n"
            "You have joined the Power Store tournament and received 5 starter Power Coins (PC).\n\n"
            "Here are some commands to get you started:\n"
            "/profile - Check your coins and cards.\n"
            "/store - See available power cards.\n"
            "/help - Show this message again."
        )
        await log_activity(context.bot, f"🎉 {user.first_name} (@{user.username}) has joined the game.")
    else:
        update_player_data(user.id, {
            'username': user.username,
            'first_name': user.first_name
        })
        await safe_reply(update, "You are already registered! Use /profile to see your status.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    await safe_reply(update, 
        "--- Power Store Bot Help ---\n\n"
        "/start - Join the game.\n"
        "/profile - Check your coins and cards (private chat only).\n"
        "/store - Browse and buy power cards (private chat only).\n"
        "/use <CardName> [Args] - Use a power card in the group chat. (Reply to a user's message to target them).\n\n"
        "--- Admin Commands ---\n"
        "/award <amount> @username - Give coins to a player.\n"
        "/awardall <amount> - Give coins to all players.\n"
        "/givecard <CardName> @username - Give a card to a player.\n"
        "/allplayers - View a summary of all players."
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the player's profile. Can only be used in private chat."""
    chat = update.effective_chat
    msg = update.effective_message
    if chat and chat.type != 'private':
        await safe_reply(update, "You can only check your profile in a private chat with me. Please send /profile here.")
        return

    if not update.effective_user:
        return

    user_id = update.effective_user.id
    player_data = ensure_player_registered(user_id, update.effective_user)

    if not player_data:
        await safe_reply(update, "Unable to load profile. Please try again.")
        return

    safe_first_name = escape_markdown_v2(player_data.get('first_name', ''))

    cards_list = [POWER_CARDS[card_id]['name'] for card_id in player_data.get('cards', []) if card_id in POWER_CARDS]
    cards_str = escape_markdown_v2(", ".join(cards_list) if cards_list else "None")
    
    status_list = []
    status = player_data.get('status', {}) or {}
    now = time.time()
    if status.get('protected'):
        status_list.append("Protected 🛡️")
    if status.get('trap_active'):
        status_list.append("Trap Active 🪤")
    if status.get('karma_active_until', 0) > now:
        status_list.append("Karma Active ⚖️")
    if status.get('ricochet_active_until', 0) > now:
        status_list.append("Ricochet Active ↪️")
    if status.get('blackout_until', 0) > now:
        status_list.append("Blackout Active 🕶️")
    if status.get('mirage_until', 0) > now:
        status_list.append("Mirage Active 🏜️")
    if status.get('black_market_until', 0) > now:
        status_list.append("In the Black Market 💰")
    if status.get('shackled_until', 0) > now:
        status_list.append("Shackled ⛓️")
    if status.get('speed_active_until', 0) > now:
        status_list.append("Speed Active ⚡️")
    if status.get('frenzy_active', 0) > 0:
        status_list.append("Frenzy Active 🔀")
    if status.get('inflation_immunity_until', 0) > now:
        status_list.append("Immune to Inflation 🛡️")

    game_state = get_game_state()
    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    is_affected_by_inflation = inflation_active and user_id != inflation_user_id and status.get('inflation_immunity_until', 0) < now
    if is_affected_by_inflation:
        status_list.append("Affected by Inflation 📈")
    if player_data.get('msgc_registered'):
        status_list.append("MSGC Registered ✅")

    from datetime import datetime
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    last_god_date = status.get('last_god_use_date', '')
    god_uses_today = status.get('god_card_uses_today', 0) if last_god_date == today_str else 0

    status_str = escape_markdown_v2(", ".join(status_list) if status_list else "Normal")

    message = (
        f"👤 *Profile for {safe_first_name}*\n\n"
        f"💰 *Power Coins:* {player_data.get('coins', 0)} PC\n"
        f"🎴 *Your Cards:* {cards_str}\n"
        f"⚡ *God Card Uses Today:* {god_uses_today}/2\n"
        f"✨ *Status:* {status_str}"
    )
    await send_safe_message(msg or chat, message, parse_mode='MarkdownV2')


# --- INTERACTIVE STORE ---

def build_store_menu(user_id, telegram_user=None):
    """Builds the main store menu text and keyboard markup, considering inflation and black market."""
    game_state = get_game_state()
    player_data = ensure_player_registered(user_id, telegram_user)
    player_status = player_data.get('status', {}) if player_data else {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()
    is_affected_by_inflation = inflation_active and user_id != inflation_user_id and player_status.get('inflation_immunity_until', 0) < time.time()

    freebie_frenzy_active = game_state.get('freebie_frenzy_until', 0) > time.time()
    bogo_active = game_state.get('bogo_active_until', 0) > time.time()

    text = "🛒 *Welcome to the Power Store\\!* \nSelect a card to view its details:"
    if freebie_frenzy_active:
        text += "\n\n🎁 *FREEBIE FRENZY Active\\! Tier 1 cards are FREE\\!*"
    if bogo_active:
        text += "\n\n🎁 *BOGO Event Active\\! Buy 1 card, get 1 FREE Tier 1/2 card\\!*"
    if black_market_active:
        text += "\n\n💰 *Black Market prices are active\\! All cards are 50% off for you\\!*"
    elif is_affected_by_inflation:
        text += "\n\n📈 *Inflation is active\\! Prices are doubled\\!*"

    keyboard = []
    for card_id, card in POWER_CARDS.items():
        c_price = card['price']
        if freebie_frenzy_active and card.get('tier') == 1 and card_id != 'angel':
            c_price = 0
        button_text = f"{card['icon']} {card['name']} ({c_price} PC)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"inspect_{card_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    return text, reply_markup

async def store_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the power card store. Can only be used in private chat."""
    chat = update.effective_chat
    msg = update.effective_message
    if chat and chat.type != 'private':
        await safe_reply(update, "You can only access the store in a private chat with me. Please send /store here.")
        return

    if not update.effective_user:
        return

    text, reply_markup = build_store_menu(update.effective_user.id, update.effective_user)
    if reply_markup:
        await send_safe_message(msg or chat, text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    else:
        await send_safe_message(msg or chat, text, parse_mode=None)

async def handle_inspect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles showing the details of a single card."""
    query = update.callback_query
    await query.answer()
    card_id = query.data.split('_', 1)[1]
    card = POWER_CARDS[card_id]
    user_id = query.from_user.id

    game_state = get_game_state()
    player_data = ensure_player_registered(user_id, query.from_user)
    player_status = player_data.get('status', {}) if player_data else {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()
    is_affected_by_inflation = inflation_active and user_id != inflation_user_id and player_status.get('inflation_immunity_until', 0) < time.time()
    freebie_frenzy_active = game_state.get('freebie_frenzy_until', 0) > time.time()

    price = card['price']
    if freebie_frenzy_active and card.get('tier') == 1 and card_id != 'angel':
        price = 0
    elif black_market_active:
        price = int(price * 0.5)
    elif is_affected_by_inflation:
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

    await send_safe_message(query, text, reply_markup=reply_markup, parse_mode='MarkdownV2')

async def handle_back_to_store_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'Back to Store' button press."""
    query = update.callback_query
    await query.answer()
    text, reply_markup = build_store_menu(query.from_user.id, query.from_user)
    await send_safe_message(query, text, reply_markup=reply_markup, parse_mode='MarkdownV2')

async def handle_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles purchasing a card."""
    query = update.callback_query
    await query.answer()
    card_id = query.data.split('_', 1)[1]
    card = POWER_CARDS[card_id]
    user_id = query.from_user.id

    if not db:
        await query.edit_message_text("Database not available.")
        return

    player_data = ensure_player_registered(user_id, query.from_user)
    if not player_data:
        await query.edit_message_text("Unable to process purchase. Please try again.")
        return

    current_cards = player_data.get('cards', [])
    if card_id in current_cards:
        await query.edit_message_text(f"You already have a {card['name']} card. Use it before buying another one.")
        return

    game_state = get_game_state()
    player_status = player_data.get('status', {}) or {}

    inflation_active = game_state.get('inflation_until', 0) > time.time()
    inflation_user_id = game_state.get('inflation_user_id')
    black_market_active = player_status.get('black_market_until', 0) > time.time()
    is_affected_by_inflation = inflation_active and user_id != inflation_user_id and player_status.get('inflation_immunity_until', 0) < time.time()
    freebie_frenzy_active = game_state.get('freebie_frenzy_until', 0) > time.time()

    price = card['price']
    if freebie_frenzy_active and card.get('tier') == 1 and card_id != 'angel':
        price = 0
    elif black_market_active:
        price = int(price * 0.5)
    elif is_affected_by_inflation:
        price = int(price * 2)

    current_coins = player_data.get('coins', 0)
    if current_coins < price:
        await query.edit_message_text(f"Insufficient funds! You need {price} PC but only have {current_coins} PC.")
        return

    new_coins = current_coins - price
    new_cards = current_cards + [card_id]

    bogo_active = game_state.get('bogo_active_until', 0) > time.time()
    bonus_card_msg = ""
    if bogo_active:
        eligible_bogo = [cid for cid, c in POWER_CARDS.items() if c.get('tier') in [1, 2] and cid not in new_cards]
        if eligible_bogo:
            bogo_bonus_card = random.choice(eligible_bogo)
            new_cards.append(bogo_bonus_card)
            bonus_card_name = POWER_CARDS[bogo_bonus_card]['name']
            bonus_card_msg = f"\n🎁 BOGO Bonus! You also received a FREE {bonus_card_name} card!"

    update_player_data(user_id, {'coins': new_coins, 'cards': new_cards})

    result = f"✅ Success! You bought a {card['name']} card for {price} PC.{bonus_card_msg}"
    await query.edit_message_text(text=result)
    await log_activity(context.bot, f"🛒 {query.from_user.first_name} bought a {card['name']} card.")


async def use_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /use command."""
    user = update.effective_user
    chat = update.effective_chat
    args = context.args
    
    if not user or not chat:
        return

    if not args:
        await safe_reply(update, "Usage: /use <Card Name or ID> [args...]")
        return

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
        await safe_reply(update, "Card not found. Please use the exact card name or ID.")
        return

    player_data = ensure_player_registered(user.id, user)
    if not player_data:
        await safe_reply(update, "Unable to load profile. Please try again.")
        return

    now = time.time()
    status = player_data.get('status', {}) or {}
    game_state = get_game_state()

    # Rush Hour check: Disable card cooldown
    rush_hour_active = game_state.get('rush_hour_until', 0) > now
    
    if status.get('frenzy_active', 0) == 0 and not rush_hour_active:
        last_use = status.get('last_card_use_time', 0)
        cooldown = 15 * 60

        if status.get('speed_active_until', 0) > now:
            cooldown /= 2

        if now - last_use < cooldown:
            remaining_time = int(cooldown - (now - last_use))
            mins = remaining_time // 60
            secs = remaining_time % 60
            await safe_reply(update, f"You must wait {mins}m {secs}s before using another card.")
            return

    # Truce check: Disable negative/targeted cards
    truce_active = game_state.get('truce_until', 0) > now
    if truce_active and (card_id in NEGATIVE_CARDS or POWER_CARDS[card_id].get('requires_target')):
        await safe_reply(update, "🤝 A Truce has been called! Negative cards are disabled right now.")
        return

    if status.get('shackled_until', 0) > time.time() and card_id != 'dispel':
        await safe_reply(update, "⛓️ You are shackled! You cannot use any cards right now (except Dispel).")
        return

    if card_id not in player_data.get('cards', []):
        await safe_reply(update, f"You don't have a {POWER_CARDS[card_id]['name']} card.")
        return
    
    card = POWER_CARDS[card_id]

    if chat.type == 'private':
        if card_id in NEGATIVE_CARDS or card.get('requires_target') or card_id == 'god':
            await safe_reply(update, "❌ Attacking or targeted cards can only be used in group chats!")
            return

    if card_id == 'god':
        await execute_god_power(update, context, user, card_args)
        return
        
    target_user = None
    if card['requires_target']:
        effective_msg = update.effective_message
        reply_msg = effective_msg.reply_to_message if effective_msg else None

        if reply_msg and reply_msg.from_user:
            target_user = reply_msg.from_user
        elif card_args:
            target_username = card_args[0].lstrip('@')
            target_player_data = get_player_by_username(target_username)
            if target_player_data:
                class PseudoUser:
                    def __init__(self, uid, fname, uname):
                        self.id = uid
                        self.first_name = fname
                        self.username = uname
                target_user = PseudoUser(
                    target_player_data['user_id'],
                    target_player_data.get('first_name', target_username),
                    target_player_data.get('username', target_username)
                )
            else:
                await safe_reply(update, f"Player @{target_username} was not found in the game. They must use /start first.")
                return

        if not target_user:
            await safe_reply(update, f"To use the {card['name']} card, reply to a message from the target player OR mention their username (e.g., /use {card['name']} @username).")
            return

        if target_user.id == user.id:
            await safe_reply(update, "You cannot target yourself with this card.")
            return

        user_is_msgc = bool(player_data.get('msgc_registered', False))
        target_player_data = get_player_data(target_user.id)
        if target_player_data:
            target_is_msgc = bool(target_player_data.get('msgc_registered', False))
            if user_is_msgc and not target_is_msgc:
                await safe_reply(update, "❌ MSGC registered players can only use cards on other MSGC registered players.")
                return
            elif not user_is_msgc and target_is_msgc:
                await safe_reply(update, "❌ Non-MSGC players cannot use cards on MSGC registered players.")
                return
    
    if card_id == 'double_or_nothing':
        if player_data.get('coins', 0) < 40:
            await safe_reply(update, "❌ You need at least 40 Power Coins to trigger Double or Nothing!")
            return
        await handle_double_or_nothing_challenge(update, context, user, target_user)
        return

    try:
        await execute_card_effect(update, context, user, card_id, target_user, card_args)
    except Exception as e:
        logger.error(f"Error executing card effect: {e}")
        await safe_reply(update, f"Action failed: {e}")


def process_use_card(user_data, target_data, card_id, card_args=None):
    """Core logic for executing card effect."""
    card = POWER_CARDS[card_id]
    user_id = user_data['user_id']
    user_name = user_data.get('first_name', 'A player')
    user_status = user_data.get('status', {}) or {}
    user_cards = list(user_data.get('cards', []))

    target_id = target_data.get('user_id') if target_data else None
    target_name = target_data.get('first_name', 'another player') if target_data else ""
    target_status = target_data.get('status', {}) if target_data else {}
    target_cards = list(target_data.get('cards', [])) if target_data else []

    if target_data:
        user_is_msgc = bool(user_data.get('msgc_registered', False))
        target_is_msgc = bool(target_data.get('msgc_registered', False))
        if user_is_msgc and not target_is_msgc:
            return {'public': "❌ MSGC registered players can only use cards on other MSGC registered players."}
        elif not user_is_msgc and target_is_msgc:
            return {'public': "❌ Non-MSGC players cannot use cards on MSGC registered players."}

    if card_id in NEGATIVE_CARDS and target_data:
        if target_status.get('trap_active'):
            target_status['trap_active'] = False
            user_coins = max(0, user_data.get('coins', 0) - 15)
            if card_id in user_cards: user_cards.remove(card_id)
            user_status['last_card_use_time'] = time.time()
            
            update_player_data(target_id, {'status': target_status})
            update_player_data(user_id, {'coins': user_coins, 'cards': user_cards, 'status': user_status})
            return {
                'public': f"🪤 Sprung! {target_name}'s Trap nullified the {card['name']} card and made {user_name} lose 15 coins!",
                'override_gif': 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExam55aGthejd1ano0Mm1uY3FqNzFvZjV2b2xzcnA3OGc1ajZ5a2dzbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/26vUSsA7qFftHrgCk/giphy.gif'
            }

        if target_status.get('ricochet_active_until', 0) > time.time():
            target_status['ricochet_active_until'] = 0
            if card_id in user_cards: user_cards.remove(card_id)
            user_status['last_card_use_time'] = time.time()

            update_player_data(target_id, {'status': target_status})
            update_player_data(user_id, {'cards': user_cards, 'status': user_status})
            return {
                'action': 'trigger_ricochet',
                'data': {
                    'attacker_id': user_id,
                    'original_target_id': target_id,
                    'card_id': card_id,
                    'card_args': card_args
                }
            }

        if target_status.get('karma_active_until', 0) > time.time():
            reflected_message = f"⚖️ Karma! {target_name}'s karma reflected the {card['name']} card back onto {user_name}!"
            
            if card_id == 'flame':
                user_data['coins'] = max(0, user_data.get('coins', 0) - 10)
            elif card_id == 'devil':
                stolen_amount = min(25, user_data.get('coins', 0))
                user_data['coins'] = max(0, user_data.get('coins', 0) - stolen_amount)
            elif card_id == 'glitch':
                if user_cards:
                    c_disc = random.choice(user_cards)
                    user_cards.remove(c_disc)
            elif card_id == 'steal':
                stealable = [c for c in user_cards if c != 'steal' and c not in target_cards]
                if stealable:
                    stolen = random.choice(stealable)
                    user_cards.remove(stolen)
                    target_cards.append(stolen)
                    update_player_data(target_id, {'cards': target_cards})
                    reflected_message = f"⚖️ Karma! {target_name}'s karma reversed the Steal! Instead, {target_name} stole a {POWER_CARDS[stolen]['name']} card from {user_name}!"
            elif card_id == 'spotlight':
                c_disp = [c for c in user_cards if c != 'spotlight']
                cards_str = ", ".join([POWER_CARDS[cid]['name'] for cid in c_disp if cid in POWER_CARDS]) if c_disp else "None"
                reflected_message = f"⚖️ Karma! {target_name}'s karma reflected the Spotlight back onto {user_name}!\n💡 Their cards are: {cards_str}"
            elif card_id == 'purge':
                if card_args:
                    p_name = " ".join(card_args)
                    p_id = next((cid for cid, c in POWER_CARDS.items() if c['name'].lower() == p_name.lower()), None)
                    if p_id and p_id in user_cards:
                        user_cards.remove(p_id)
                        reflected_message = f"⚖️ Karma! {target_name}'s karma reflected Purge back onto {user_name}, forcing them to discard their own {POWER_CARDS[p_id]['name']} card!"
            elif card_id == 'amnesia':
                user_cards = []
                reflected_message = f"⚖️ Karma! {target_name}'s karma reflected Amnesia back onto {user_name}, forcing them to discard their entire hand!"
            elif card_id == 'shackle':
                user_status['shackled_until'] = time.time() + (1 * 60 * 60)
                reflected_message = f"⚖️ Karma! {target_name}'s karma reflected the Shackle back onto {user_name}!"

            if card_id in user_cards: user_cards.remove(card_id)
            user_status['last_card_use_time'] = time.time()
            update_player_data(user_id, {'coins': user_data.get('coins', 0), 'cards': user_cards, 'status': user_status})
            return {'public': reflected_message}

        if target_status.get('protected'):
            target_status['protected'] = False
            if card_id in user_cards: user_cards.remove(card_id)
            user_status['last_card_use_time'] = time.time()
            update_player_data(target_id, {'status': target_status})
            update_player_data(user_id, {'cards': user_cards, 'status': user_status})
            return {'public': f"🛡️ Blocked! {target_name}'s Forcefield deflected the {card['name']} card!"}

    effect_message = ""
    special_action = None

    if card_id == 'speed':
        user_status['speed_active_until'] = time.time() + (1 * 60 * 60)
        effect_message = f"⚡️ {user_name} activated Speed! Your card cooldown is halved for 1 hour."
    elif card_id == 'reroll':
        cards_to_reroll = [c for c in user_cards if c != 'reroll']
        if not cards_to_reroll:
            raise Exception("You have no other cards to re-roll!")
        val = sum(POWER_CARDS.get(c, {}).get('price', 0) for c in cards_to_reroll)
        gained = int(val * 0.75)
        user_cards = [c for c in user_cards if c not in cards_to_reroll]
        user_data['coins'] = user_data.get('coins', 0) + gained
        effect_message = f"♻️ {user_name} used Re-roll, discarded {len(cards_to_reroll)} cards, and regained {gained} coins!"
    elif card_id == 'flame':
        target_coins = max(0, target_data.get('coins', 0) - 10)
        update_player_data(target_id, {'coins': target_coins})
        effect_message = f"🔥 {user_name} used Flame on {target_name}, burning 10 Power Coins!"
    elif card_id == 'angel':
        if user_data.get('coins', 0) < 20:
            raise Exception("You need at least 20 coins to use the Angel card.")
        user_data['coins'] -= 20
        update_player_data(target_id, {'coins': target_data.get('coins', 0) + 20})
        effect_message = f"👼 {user_name} used an Angel card to gift 20 Power Coins to {target_name}!"
    elif card_id == 'devil':
        stolen = min(25, target_data.get('coins', 0))
        update_player_data(target_id, {'coins': target_data.get('coins', 0) - stolen})
        user_data['coins'] = user_data.get('coins', 0) + stolen
        effect_message = f"😈 {user_name} used a Devil card and stole {stolen} Power Coins from {target_name}!"
    elif card_id == 'karma':
        user_status['karma_active_until'] = time.time() + (2 * 60 * 60)
        effect_message = f"⚖️ {user_name} activated a Karma card! Negative cards will be reflected for 2 hours."
    elif card_id == 'ricochet':
        user_status['ricochet_active_until'] = time.time() + (1 * 60 * 60)
        effect_message = f"↪️ {user_name} activated Ricochet! The next negative card will be redirected."
    elif card_id == 'forcefield':
        user_status['protected'] = True
        effect_message = f"🛡️ {user_name} activated a Forcefield and is now protected from the next negative card."
    elif card_id == 'trap':
        user_status['trap_active'] = True
        effect_message = f"🪤 {user_name} set a Trap!"
    elif card_id == 'vision':
        if target_status.get('blackout_until', 0) > time.time():
            return {'private': f"🕶️ Your Vision was blocked! {target_name} is under a Blackout.", 'public': f"👁️ {user_name} used a Vision card on another player."}
        if target_status.get('mirage_until', 0) > time.time():
            fake = [random.choice(list(POWER_CARDS.keys())) for _ in range(random.randint(1, 3))]
            cstr = ", ".join([POWER_CARDS[cid]['name'] for cid in fake])
            return {'private': f"🏜️ You used Vision on {target_name}. A mirage shows they are holding: {cstr}.", 'public': f"👁️ {user_name} used a Vision card on another player."}
        cstr = ", ".join([POWER_CARDS[cid]['name'] for cid in target_cards if cid in POWER_CARDS]) if target_cards else "None"
        return {'private': f"👁️ You used Vision on {target_name}. They are holding: {cstr}.", 'public': f"👁️ {user_name} used a Vision card on another player."}
    elif card_id == 'clairvoyance':
        if target_status.get('blackout_until', 0) > time.time():
            return {'private': f"🕶️ Your Clairvoyance was blocked! {target_name} is under a Blackout.", 'public': f"🔮 {user_name} used a Clairvoyance card on another player."}
        cstr = ", ".join([POWER_CARDS[cid]['name'] for cid in target_cards if cid in POWER_CARDS]) if target_cards else "None"
        return {'private': f"🔮 You used Clairvoyance on {target_name}. Their true cards are: {cstr}.", 'public': f"🔮 {user_name} used a Clairvoyance card on another player."}
    elif card_id == 'spotlight':
        if target_status.get('blackout_until', 0) > time.time():
            effect_message = f"🕶️ {user_name}'s Spotlight was blocked! {target_name} is under a Blackout."
        elif target_status.get('mirage_until', 0) > time.time():
            fake = [random.choice(list(POWER_CARDS.keys())) for _ in range(random.randint(1, 3))]
            cstr = ", ".join([POWER_CARDS[cid]['name'] for cid in fake])
            effect_message = f"💡 {user_name} used Spotlight on {target_name}! A mirage shows their cards are: {cstr}"
        else:
            cstr = ", ".join([POWER_CARDS[cid]['name'] for cid in target_cards if cid in POWER_CARDS]) if target_cards else "None"
            effect_message = f"💡 {user_name} used Spotlight on {target_name}! Their cards are: {cstr}"
    elif card_id == 'blackout':
        user_status['blackout_until'] = time.time() + (4 * 60 * 60)
        effect_message = f"🕶️ {user_name} activated Blackout! They are immune to Vision and Spotlight for 4 hours."
    elif card_id == 'mirage':
        user_status['mirage_until'] = time.time() + (1 * 60 * 60)
        effect_message = f"🏜️ {user_name} cast a Mirage on themself! Their hand will appear differently to spies for 1 hour."
    elif card_id == 'time_warp':
        target_status['karma_active_until'] = 0
        target_status['shackled_until'] = 0
        update_player_data(target_id, {'status': target_status})
        effect_message = f"⏳ {user_name} used Time Warp on {target_name}, ending their Karma or Shackle effect immediately!"
    elif card_id == 'glitch':
        if not target_cards:
            effect_message = f"🌀 {user_name} tried to glitch {target_name}, but they had no cards to discard!"
        else:
            disc = random.choice(target_cards)
            target_cards.remove(disc)
            update_player_data(target_id, {'cards': target_cards})
            effect_message = f"🌀 {user_name} glitched {target_name}'s hand, forcing them to discard a {POWER_CARDS[disc]['name']} card!"
    elif card_id == 'swap':
        user_swaps = [c for c in user_cards if c != 'swap']
        if not user_swaps or not target_cards:
            effect_message = f"🔄 {user_name} tried to swap cards with {target_name}, but the swap failed because one player had no cards to trade!"
        else:
            c_u = random.choice(user_swaps)
            c_t = random.choice(target_cards)
            user_cards.remove(c_u)
            user_cards.append(c_t)
            target_cards.remove(c_t)
            target_cards.append(c_u)
            update_player_data(target_id, {'cards': target_cards})
            effect_message = f"🔄 {user_name} used a Swap card on {target_name}! A random card was exchanged between them."
    elif card_id == 'steal':
        stealable = [c for c in target_cards if c not in user_cards]
        if not stealable:
            effect_message = f"🥷 {user_name} tried to steal from {target_name}, but there were no cards they could take!"
        else:
            stolen = random.choice(stealable)
            target_cards.remove(stolen)
            user_cards.append(stolen)
            update_player_data(target_id, {'cards': target_cards})
            effect_message = f"🥷 {user_name} used Steal on {target_name} and took their {POWER_CARDS[stolen]['name']} card!"
    elif card_id == 'inflation':
        update_game_state({
            'inflation_until': time.time() + (1 * 60 * 60),
            'inflation_user_id': user_id
        })
        effect_message = f"📈 {user_name} used Inflation! For the next 1 hour, card prices are doubled for everyone else."
    elif card_id == 'black_market':
        user_status['black_market_until'] = time.time() + (1 * 60)
        effect_message = f"💰 {user_name} used Black Market! For the next minute, all store prices are 50% off for you."
    elif card_id == 'purge':
        if not card_args:
            raise Exception("You must specify a card to purge. Usage: /use Purge <Card Name>")
        p_name = " ".join(card_args)
        p_id = next((cid for cid, c in POWER_CARDS.items() if c['name'].lower() == p_name.lower()), None)
        if not p_id:
            raise Exception(f"The card '{p_name}' does not exist.")
        if p_id in target_cards:
            target_cards.remove(p_id)
            update_player_data(target_id, {'cards': target_cards})
            effect_message = f"🎯 {user_name} used Purge on {target_name} and successfully discarded their {POWER_CARDS[p_id]['name']} card!"
        else:
            effect_message = f"🎯 {user_name} used Purge on {target_name}, but they did not have a {POWER_CARDS[p_id]['name']} card."
    elif card_id == 'amnesia':
        update_player_data(target_id, {'cards': []})
        effect_message = f"❓ {user_name} used Amnesia on {target_name}, forcing them to discard their entire hand!"
    elif card_id == 'vortex':
        special_action = "trigger_vortex"
        effect_message = f"🌪️ {user_name} unleashed a Vortex!"
    elif card_id == 'shackle':
        target_status['shackled_until'] = time.time() + (1 * 60 * 60)
        update_player_data(target_id, {'status': target_status})
        effect_message = f"⛓️ {user_name} shackled {target_name}! They cannot use cards for 1 hour."
    elif card_id == 'frenzy':
        effect_message = f"🔀 {user_name} activated Frenzy! Your next two cards have no cooldown."
    elif card_id == 'dispel':
        game_state = get_game_state()
        now = time.time()
        removed = []
        if user_status.get('shackled_until', 0) > now:
            removed.append('Shackle')
            user_status['shackled_until'] = 0
        inflation_active = game_state.get('inflation_until', 0) > now
        if inflation_active and user_id != game_state.get('inflation_user_id'):
            removed.append('Inflation')
            user_status['inflation_immunity_until'] = game_state.get('inflation_until', 0)
        if not removed:
            raise Exception("You are not affected by Shackle or Inflation.")
        effect_message = f"💨 {user_name} used Dispel and removed the following effects: {', '.join(removed)}!"
    elif card_id == 'lottery_ticket':
        if random.random() < 0.02:
            user_data['coins'] = user_data.get('coins', 0) + 100
            effect_message = f"🎟️ Unbelievable! {user_name}'s Lottery Ticket was a winner! They won 100 coins!"
        else:
            effect_message = f"🎟️ {user_name} scratched their Lottery Ticket... but it wasn't a winner. Better luck next time!"

    if card_id in user_cards:
        user_cards.remove(card_id)

    if card_id == 'frenzy':
        user_status['frenzy_active'] = 2
        user_status['last_card_use_time'] = time.time()
    elif user_status.get('frenzy_active', 0) > 0:
        user_status['frenzy_active'] = max(0, user_status['frenzy_active'] - 1)
    else:
        user_status['last_card_use_time'] = time.time()

    update_player_data(user_id, {'coins': user_data.get('coins', 0), 'cards': user_cards, 'status': user_status})
    return {'public': effect_message, 'action': special_action, 'data': user_data}


async def execute_card_effect(update: Update, context: ContextTypes.DEFAULT_TYPE, user, card_id, target_user, card_args):
    """The core logic for what happens when a card is used."""
    if not db:
        await safe_reply(update, "Database not available.")
        return

    card = POWER_CARDS.get(card_id, {})
    user_data = get_player_data(user.id)
    user_name = user_data.get('first_name', user.first_name or 'A player') if user_data else getattr(user, 'first_name', 'A player')
    target_data = get_player_data(target_user.id) if target_user else None

    if target_user and not target_data:
        target_name = getattr(target_user, 'first_name', 'The target player')
        await safe_reply(update, f"Target player {target_name} is not registered in the game yet. They must use /start to join.")
        return

    result = process_use_card(user_data, target_data, card_id, card_args)

    if result.get('action') == 'trigger_ricochet':
        attacker_data = get_player_data(result['data']['attacker_id'])
        original_target_data = get_player_data(result['data']['original_target_id'])
        card_name = POWER_CARDS[result['data']['card_id']]['name']
        
        await safe_reply(update, f"↪️ {original_target_data['first_name']}'s Ricochet redirected the {card_name} card from {attacker_data['first_name']}!")

        all_players = get_all_players()
        attacker_is_msgc = bool(attacker_data.get('msgc_registered', False)) if attacker_data else False
        potential_targets = [
            p for p in all_players
            if p['user_id'] != result['data']['attacker_id']
            and p['user_id'] != result['data']['original_target_id']
            and bool(p.get('msgc_registered', False)) == attacker_is_msgc
        ]

        if not potential_targets:
            await safe_reply(update, "...but there was no one else to redirect it to!")
            return

        new_target_data = random.choice(potential_targets)
        redirect_result = process_use_card(attacker_data, new_target_data, result['data']['card_id'], result['data']['card_args'])

        if 'public' in redirect_result and redirect_result['public']:
            await safe_reply(update, redirect_result['public'])
        if 'private' in redirect_result and redirect_result['private']:
            await context.bot.send_message(chat_id=result['data']['attacker_id'], text=redirect_result['private'])

        if new_target_data and new_target_data.get('user_id') and new_target_data['user_id'] != result['data']['attacker_id']:
            try:
                redirect_dm = f"↪️ A {card_name} card was redirected onto you!\n\nEffect: {redirect_result.get('public', '')}"
                await context.bot.send_message(chat_id=new_target_data['user_id'], text=redirect_dm)
            except Exception as e:
                logger.warning(f"Could not send DM to redirected target {new_target_data['user_id']}: {e}")

        await log_activity(update.get_bot(), redirect_result.get('public') or redirect_result.get('private'))
        return

    if result.get('action') == 'trigger_vortex':
        gif_url = POWER_CARDS['vortex'].get('gif')
        if gif_url and 'public' in result and result['public']:
            await safe_reply_animation(update, animation=gif_url, caption=result['public'])
        elif 'public' in result and result['public']:
            await safe_reply(update, result['public'])
        
        all_players = get_all_players()
        attacker_is_msgc = bool(user_data.get('msgc_registered', False)) if user_data else False
        discard_summary = ["The Vortex has struck!"]
        
        for p_data in all_players:
            p_id = p_data['user_id']
            p_name = p_data.get('first_name', 'A player')
            p_status = p_data.get('status', {}) or {}
            p_cards = list(p_data.get('cards', []))
            p_is_msgc = bool(p_data.get('msgc_registered', False))

            if p_is_msgc != attacker_is_msgc:
                continue

            if p_status.get('protected'):
                p_status['protected'] = False
                update_player_data(p_id, {'status': p_status})
                discard_summary.append(f"🛡️ {p_name} was protected by a Forcefield!")
                if p_id != user.id:
                    try:
                        await context.bot.send_message(chat_id=p_id, text=f"🌪️ {user_name} (@{user.username or 'user'}) unleashed a Vortex, but your Forcefield protected you!")
                    except Exception as e:
                        logger.warning(f"Could not send Vortex DM to {p_id}: {e}")
            elif not p_cards:
                discard_summary.append(f"💨 {p_name} had no cards to discard.")
            else:
                c_disc = random.choice(p_cards)
                p_cards.remove(c_disc)
                update_player_data(p_id, {'cards': p_cards})
                c_name = POWER_CARDS.get(c_disc, {}).get('name', 'Unknown Card')
                discard_summary.append(f"🌪️ {p_name} lost a {c_name} card.")
                if p_id != user.id:
                    try:
                        await context.bot.send_message(chat_id=p_id, text=f"🌪️ {user_name} (@{user.username or 'user'}) unleashed a Vortex!\nYou were forced to discard your {c_name} card.")
                    except Exception as e:
                        logger.warning(f"Could not send Vortex DM to {p_id}: {e}")

        summary_message = "\n".join(discard_summary)
        await safe_reply(update, summary_message)
        await log_activity(update.get_bot(), summary_message)
        return

    if 'public' in result and result['public']:
        gif_url = result.get('override_gif') or (card.get('gif') if isinstance(card, dict) else None)
        if gif_url:
            await safe_reply_animation(update, animation=gif_url, caption=result['public'])
        else:
            await safe_reply(update, result['public'])
    if 'private' in result and result['private']:
        await context.bot.send_message(chat_id=user.id, text=result['private'])

    if card_id == 'inflation' and result.get('public'):
        all_players = get_all_players()
        user_is_msgc = bool(user_data.get('msgc_registered', False)) if user_data else False
        for p in all_players:
            p_is_msgc = bool(p.get('msgc_registered', False))
            if p['user_id'] != user.id and p_is_msgc == user_is_msgc:
                try:
                    await context.bot.send_message(
                        chat_id=p['user_id'],
                        text=f"📈 {user.first_name} (@{user.username or 'user'}) used Inflation!\nFor the next 1 hour, store card prices are doubled for everyone else!"
                    )
                except Exception as e:
                    logger.warning(f"Could not send Inflation DM to user {p['user_id']}: {e}")

    if target_user and getattr(target_user, 'id', None) and target_user.id != user.id and result.get('public'):
        try:
            target_dm_text = f"⚠️ {user.first_name} (@{user.username or 'user'}) used a {card['name']} card on you!\n\nEffect: {result['public']}"
            await context.bot.send_message(chat_id=target_user.id, text=target_dm_text)
        except Exception as e:
            logger.warning(f"Could not send DM to target user {target_user.id}: {e}")
        
    await log_activity(update.get_bot(), result.get('public') or result.get('private'))


# --- DOUBLE OR NOTHING LOGIC ---

async def handle_double_or_nothing_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE, attacker, target):
    chat = update.effective_chat
    if chat and chat.type == 'private':
        await safe_reply(update, "❌ Double or Nothing can only be used in group chats!")
        return

    attacker_data = get_player_data(attacker.id)
    target_data = get_player_data(target.id)
    wager = 40

    if not attacker_data or attacker_data.get('coins', 0) < wager:
        await safe_reply(update, f"You do not have enough coins to wager! You need {wager} PC.")
        return
    if not target_data or target_data.get('coins', 0) < wager:
        await safe_reply(update, f"{target.first_name} does not have enough coins for this wager! The card was not used.")
        return

    user_is_msgc = bool(attacker_data.get('msgc_registered', False)) if attacker_data else False
    target_is_msgc = bool(target_data.get('msgc_registered', False)) if target_data else False

    if user_is_msgc and not target_is_msgc:
        await safe_reply(update, "❌ MSGC registered players can only challenge other MSGC registered players.")
        return
    elif not user_is_msgc and target_is_msgc:
        await safe_reply(update, "❌ Non-MSGC players cannot challenge MSGC registered players.")
        return

    winner, loser = (attacker, target) if random.random() < 0.5 else (target, attacker)
    winner_data = attacker_data if winner.id == attacker.id else target_data
    loser_data = target_data if winner.id == attacker.id else attacker_data

    update_player_data(winner.id, {'coins': winner_data.get('coins', 0) + wager})
    update_player_data(loser.id, {'coins': max(0, loser_data.get('coins', 0) - wager)})

    att_cards = list(attacker_data.get('cards', []))
    if 'double_or_nothing' in att_cards:
        att_cards.remove('double_or_nothing')
    att_status = attacker_data.get('status', {}) or {}
    att_status['last_card_use_time'] = time.time()
    update_player_data(attacker.id, {'cards': att_cards, 'status': att_status})

    message = (
        f"🎲 **Double or Nothing!** 🎲\n\n"
        f"{attacker.first_name} challenged {target.first_name}, betting {wager} coins each.\n\n"
        f"The coin flip reveals **{winner.first_name}** as the winner!\n\n"
        f"{winner.first_name} takes the entire pot of {wager * 2} coins from {loser.first_name}."
    )
    gif_url = POWER_CARDS['double_or_nothing'].get('gif')
    if gif_url:
        await safe_reply_animation(update, animation=gif_url, caption=message)
    else:
        await safe_reply(update, message)

    try:
        target_dm_text = f"🎲 {attacker.first_name} (@{attacker.username or 'user'}) used Double or Nothing on you!\n\nWinner: {winner.first_name}\nPot won: {wager * 2} Power Coins"
        await context.bot.send_message(chat_id=target.id, text=target_dm_text)
    except Exception as e:
        logger.warning(f"Could not send DM to target {target.id}: {e}")

    await log_activity(context.bot, f"🎲 {attacker.first_name} used Double or Nothing on {target.first_name}. Winner: {winner.first_name}")


# --- GOD CARD LOGIC ---

async def execute_god_power(update: Update, context: ContextTypes.DEFAULT_TYPE, user, args):
    """Handles the logic for using the God card's specific powers."""
    chat = update.effective_chat
    if chat and chat.type == 'private':
        await safe_reply(update, "❌ God powers can only be used in group chats!")
        return

    if not db:
        await safe_reply(update, "Database not available.")
        return
        
    try:
        if len(args) < 1:
            await safe_reply(update, "You must specify a power. Usage: /use God <Blessing|Smite|Tribute> [@target]")
            return
        
        power = args[0].lower()
        user_data = get_player_data(user.id)
        if not user_data: return

        # Check daily God card usage limit (Max 2 per day per player)
        from datetime import datetime
        now = time.time()
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        user_status = user_data.get('status', {}) or {}
        last_god_date = user_status.get('last_god_use_date', '')
        god_uses_today = user_status.get('god_card_uses_today', 0) if last_god_date == today_str else 0

        if god_uses_today >= 2:
            await safe_reply(update, "❌ You have reached your limit of 2 God card uses for today! Try again tomorrow.")
            return

        game_state = get_game_state()

        # Global 24-Hour Limits for Tribute (Max 1 globally per 24h) and Smite (Max 2 globally per 24h)
        if power == 'tribute':
            last_tribute = game_state.get('last_tribute_time', 0)
            if now - last_tribute < (24 * 60 * 60):
                remaining = int((24 * 60 * 60) - (now - last_tribute))
                hrs = remaining // 3600
                mins = (remaining % 3600) // 60
                await safe_reply(update, f"❌ God's Tribute can only be used once globally every 24 hours! A Tribute was already used in the last 24h. Try again in {hrs}h {mins}m.")
                return

        elif power == 'smite':
            smite_times = list(game_state.get('smite_times', []))
            recent_smites = [ts for ts in smite_times if now - ts < (24 * 60 * 60)]
            if len(recent_smites) >= 2:
                oldest_smite = min(recent_smites)
                remaining = int((24 * 60 * 60) - (now - oldest_smite))
                hrs = remaining // 3600
                mins = (remaining % 3600) // 60
                await safe_reply(update, f"❌ God's Smite has already been used 2 times in the last 24 hours! Try again in {hrs}h {mins}m.")
                return

        user_is_msgc = bool(user_data.get('msgc_registered', False))
        target_data = None

        if power in ['blessing', 'smite']:
            if len(args) < 2:
                await safe_reply(update, f"The '{power}' power requires a target. Usage: /use God {power} @username")
                return
            
            username = args[1].lstrip('@')
            target_data = get_player_by_username(username)
            if not target_data:
                await safe_reply(update, f"Player @{username} not found.")
                return

            target_is_msgc = bool(target_data.get('msgc_registered', False))
            if user_is_msgc and not target_is_msgc:
                await safe_reply(update, "❌ MSGC registered players can only target other MSGC registered players.")
                return
            elif not user_is_msgc and target_is_msgc:
                await safe_reply(update, "❌ Non-MSGC players cannot target MSGC registered players.")
                return

        user_name = user_data.get('first_name', 'A player')
        effect_message = ""
        override_gif = None

        if power == 'blessing':
            t_cards = list(target_data.get('cards', []))
            t_cards.append('karma')
            update_player_data(target_data['user_id'], {'cards': t_cards})
            effect_message = f"🛐 {user_name} used God's Blessing on {target_data.get('first_name')}, granting them a Karma card!"

        elif power == 'smite':
            target_status = target_data.get('status', {}) or {}
            if target_status.get('trap_active'):
                target_status['trap_active'] = False
                user_coins = max(0, user_data.get('coins', 0) - 15)
                update_player_data(target_data['user_id'], {'status': target_status})
                update_player_data(user.id, {'coins': user_coins})
                effect_message = f"🪤 Sprung! {target_data.get('first_name')}'s Trap nullified God's Smite and made {user_name} lose 15 coins!"
                override_gif = 'https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExam55aGthejd1ano0Mm1uY3FqNzFvZjV2b2xzcnA3OGc1ajZ5a2dzbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/26vUSsA7qFftHrgCk/giphy.gif'
            elif target_status.get('protected'):
                target_status['protected'] = False
                update_player_data(target_data['user_id'], {'status': target_status})
                effect_message = f"🛡️ Blocked! {target_data.get('first_name')}'s Forcefield deflected God's Smite!"
            else:
                coins_lost = target_data.get('coins', 0) // 2
                update_player_data(target_data['user_id'], {'coins': target_data.get('coins', 0) - coins_lost})
                effect_message = f"🛐 {user_name} used God's Smite on {target_data.get('first_name')}, destroying half their coins ({coins_lost} PC)!"

        elif power == 'tribute':
            all_players = get_all_players()
            total_tribute = 0
            for p in all_players:
                p_is_msgc = bool(p.get('msgc_registered', False))
                if p['user_id'] != user.id and p_is_msgc == user_is_msgc:
                    c_pay = min(5, p.get('coins', 0))
                    total_tribute += c_pay
                    update_player_data(p['user_id'], {'coins': p.get('coins', 0) - c_pay})
                    try:
                        await context.bot.send_message(
                            chat_id=p['user_id'],
                            text=f"🛐 {user_name} (@{user.username or 'user'}) used God's Tribute!\nYou paid {c_pay} Power Coins in tribute."
                        )
                    except Exception as e:
                        logger.warning(f"Could not send Tribute DM to user {p['user_id']}: {e}")
            
            user_data['coins'] = user_data.get('coins', 0) + total_tribute
            effect_message = f"🛐 {user_name} used God's Tribute, collecting a total of {total_tribute} coins from all other players!"
        else:
            await safe_reply(update, "Invalid God power. Choose Blessing, Smite, or Tribute.")
            return

        # Record global 24-hour limit timestamps
        if power == 'tribute':
            update_game_state({'last_tribute_time': now})
        elif power == 'smite':
            smite_times = list(game_state.get('smite_times', []))
            recent_smites = [ts for ts in smite_times if now - ts < (24 * 60 * 60)]
            recent_smites.append(now)
            update_game_state({'smite_times': recent_smites})

        # Track daily God card usage
        user_status['god_card_uses_today'] = god_uses_today + 1
        user_status['last_god_use_date'] = today_str

        u_cards = list(user_data.get('cards', []))
        if 'god' in u_cards: u_cards.remove('god')
        update_player_data(user.id, {'coins': user_data.get('coins', 0), 'cards': u_cards, 'status': user_status})

        god_gifs = POWER_CARDS['god'].get('gifs', {})
        gif_url = override_gif or (god_gifs.get(power) if isinstance(god_gifs, dict) else None)
        
        if gif_url:
            await safe_reply_animation(update, animation=gif_url, caption=effect_message)
        else:
            await safe_reply(update, effect_message)
        
        if target_data and target_data.get('user_id') and target_data['user_id'] != user.id:
            try:
                await context.bot.send_message(
                    chat_id=target_data['user_id'],
                    text=f"🛐 {user_name} (@{user.username or 'user'}) used God's {power.capitalize()} on you!\n\nEffect: {effect_message}"
                )
            except Exception as e:
                logger.warning(f"Could not send DM to target {target_data['user_id']}: {e}")

        await log_activity(context.bot, effect_message)

    except Exception as e:
        logger.error(f"Error executing God power: {e}")
        await safe_reply(update, f"Action failed: {e}")


# --- ADMIN COMMANDS ---

async def all_players_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view all player stats."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return

    if not db:
        await safe_reply(update, "Database not available.")
        return

    try:
        all_players = get_all_players()
        if not all_players:
            await safe_reply(update, "No players have registered yet.")
            return

        report_lines = ["📊 *All Players Report*\n"]
        for p in all_players:
            username = p.get('username') or f"ID: {p.get('user_id')}"
            safe_username = escape_markdown_v2(username)
            coins = p.get('coins', 0)
            cards_list = [POWER_CARDS[cid]['name'] for cid in p.get('cards', []) if cid in POWER_CARDS]
            cards_str = escape_markdown_v2(", ".join(cards_list) if cards_list else "None")
            msgc_tag = " [MSGC]" if bool(p.get('msgc_registered', False)) else ""
            
            report_lines.append(
                f"\n👤 *@{safe_username}*{msgc_tag}\n"
                f"    💰 Coins: {coins} PC\n"
                f"    🎴 Cards: {cards_str}"
            )

        report = "\n".join(report_lines)
        await safe_reply(update, report, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"Error in /allplayers command: {e}")
        await safe_reply(update, "An error occurred while fetching player data.")

async def award_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to award coins to a player."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return
    
    if not db:
        await safe_reply(update, "Database not available.")
        return

    try:
        amount_str, username = context.args
        amount = int(amount_str)
        username = username.lstrip('@')

        target_data = get_player_by_username(username)
        if not target_data:
            await safe_reply(update, f"Player @{username} not found in the database. They must use /start first.")
            return

        new_coins = target_data.get('coins', 0) + amount
        update_player_data(target_data['user_id'], {'coins': new_coins})
        
        award_gif_url = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYnp4amQzMGRvcTk1YWRtNXk3d2NpeHd4eGxidGh5ZWltMnhldDdkMCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/MkvZFvzHIWbRK/giphy.gif"
        reply_msg = f"✅ Successfully awarded {amount} PC to @{username}."

        # Send DM notification to the player
        try:
            await context.bot.send_animation(
                chat_id=target_data['user_id'],
                animation=award_gif_url,
                caption=f"🎁 You have received {amount} Power Coins from the Admin!"
            )
        except Exception as e:
            logger.warning(f"Could not send DM to user {target_data['user_id']}: {e}")

        await safe_reply_animation(update, animation=award_gif_url, caption=reply_msg)
        await log_activity(context.bot, f"👑 Admin awarded {amount} PC to @{username}.")

    except (ValueError, IndexError):
        await safe_reply(update, "Usage: /award <amount> @username")
    except Exception as e:
        logger.error(f"Error in /award command: {e}")
        await safe_reply(update, "An error occurred while awarding coins.")

async def awardall_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to award coins to all players."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return

    if not db:
        await safe_reply(update, "Database not available.")
        return

    try:
        amount_str = context.args[0]
        amount = int(amount_str)
        if amount <= 0:
            await safe_reply(update, "Please provide a positive amount.")
            return
    except (ValueError, IndexError):
        await safe_reply(update, "Usage: /awardall <amount>")
        return

    try:
        awardall_gif_url = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYnp4amQzMGRvcTk1YWRtNXk3d2NpeHd4eGxidGh5ZWltMnhldDdkMCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/pwyW4XDmtqjG8/giphy.gif"
        all_players, debug_info = get_all_players_debug()
        if not all_players:
            key_prefix = SUPABASE_KEY[:12] if SUPABASE_KEY else 'None'
            await safe_reply(update, 
                f"⚠️ No registered players were retrieved.\n\n"
                f"🔍 *Diagnostic Details:*\n"
                f"• URL: `{SUPABASE_URL}`\n"
                f"• Key Prefix: `{key_prefix}...`\n"
                f"• DB Response: `{debug_info}`"
            )
            return

        for p in all_players:
            update_player_data(p['user_id'], {'coins': p.get('coins', 0) + amount})
            try:
                await context.bot.send_animation(
                    chat_id=p['user_id'],
                    animation=awardall_gif_url,
                    caption=f"🎁 You have received {amount} Power Coins from the Admin!"
                )
            except Exception as e:
                logger.warning(f"Could not send DM to user {p['user_id']}: {e}")
        
        reply_msg = f"✅ Successfully awarded {amount} PC to all {len(all_players)} players."
        await safe_reply_animation(update, animation=awardall_gif_url, caption=reply_msg)
        await log_activity(context.bot, f"👑 Admin awarded {amount} PC to all {len(all_players)} players.")

    except Exception as e:
        logger.error(f"Error in /awardall command: {e}")
        await safe_reply(update, "An error occurred while awarding coins to all players.")

async def givecard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to give a card to a player."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return

    if not db:
        await safe_reply(update, "Database not available.")
        return
    
    try:
        if len(context.args) < 2:
            await safe_reply(update, "Usage: /givecard <Card Name> @username")
            return

        username = context.args[-1].lstrip('@')
        card_name_query = " ".join(context.args[:-1])
        card_id = next((cid for cid, c in POWER_CARDS.items() if c['name'].lower() == card_name_query.lower() or cid.lower() == card_name_query.lower()), None)
        
        if not card_id:
            await safe_reply(update, f"Card '{card_name_query}' not found. Please use the exact card name.")
            return

        target_data = get_player_by_username(username)
        if not target_data:
            await safe_reply(update, f"Player @{username} not found in the database. They must use /start first.")
            return
            
        c_list = list(target_data.get('cards', []))
        c_list.append(card_id)
        update_player_data(target_data['user_id'], {'cards': c_list})
        card_name = POWER_CARDS[card_id]['name']
        
        # Send DM notification to the player
        try:
            await context.bot.send_message(
                chat_id=target_data['user_id'],
                text=f"🎁 You have received a {card_name} card from the Admin!"
            )
        except Exception as e:
            logger.warning(f"Could not send DM to user {target_data['user_id']}: {e}")

        await safe_reply(update, f"✅ Successfully gave a {card_name} card to @{username}.")
        await log_activity(context.bot, f"👑 Admin gave a {card_name} card to @{username}.")

    except (ValueError, IndexError):
        await safe_reply(update, "Usage: /givecard <CardName> @username")

async def resetallcoins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reset all players' coins to 5 and clear their cards."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return

    if not db:
        await safe_reply(update, "Database not available.")
        return

    try:
        all_players = get_all_players()
        if not all_players:
            await safe_reply(update, "No players found in database.")
            return

        for p in all_players:
            if p.get('user_id'):
                update_player_data(p['user_id'], {'coins': 5, 'cards': []})

        reply_msg = f"✅ Successfully reset all {len(all_players)} players to 5 coins and 0 cards."
        await safe_reply(update, reply_msg)
        await log_activity(context.bot, f"👑 Admin reset all {len(all_players)} players to 5 coins and 0 cards.")
    except Exception as e:
        logger.error(f"Error in /resetallcoins command: {e}")
        await safe_reply(update, "An error occurred while resetting coins.")

async def startevent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central command dispatcher to trigger any admin event."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return
    
    if not context.args:
        await safe_reply(update, 
            "Usage: /startevent <event_name>\n\n"
            "Available Events (MSGC Registered Players Only):\n"
            "• bogo - Free Tier 1 or 2 card with every store purchase (15 min)\n"
            "• secretsanta - MSGC players gift cards or coins to each other\n"
            "• rushhour - All card usage cooldowns disabled for MSGC players (1 hour)\n"
            "• truce - All negative cards disabled for MSGC players (15 min)\n"
            "• gambit - Every MSGC registered player receives a random non-God card\n"
            "• coinrush - Messages in group chats drop bonus coins for MSGC players (10 min)\n"
            "• freebiefrenzy - Tier 1 cards are FREE in the store for MSGC players (15 min)"
        )
        return
        
    event_name = context.args[0].lower()
    now = time.time()

    if event_name == 'bogo':
        update_game_state({'bogo_active_until': now + (15 * 60)})
        await broadcast_event_message(context.bot, "🎁 *BOGO EVENT STARTED!* 🎁\n\nFor 15 minutes, store purchases for MSGC registered players include a FREE Tier 1 or 2 card!", context)
        await safe_reply(update, "✅ BOGO event started for 15 minutes.")

    elif event_name == 'secretsanta':
        await safe_reply(update, "🎅 Initiating Secret Santa...")
        await execute_secret_santa_event(context.bot, context)

    elif event_name == 'rushhour':
        update_game_state({'rush_hour_until': now + (60 * 60)})
        await broadcast_event_message(context.bot, "⏰ *RUSH HOUR HAS BEGUN!* ⏰\n\nFor 1 hour, all card cooldowns are disabled for MSGC registered players!", context)
        await safe_reply(update, "✅ Rush Hour started for 1 hour.")

    elif event_name == 'truce':
        update_game_state({'truce_until': now + (15 * 60)})
        await broadcast_event_message(context.bot, "🤝 *A TRUCE HAS BEEN CALLED!* 🤝\n\nFor 15 minutes, negative cards are disabled for MSGC registered players!", context)
        await safe_reply(update, "✅ Truce event started for 15 minutes.")

    elif event_name == 'gambit':
        await safe_reply(update, "🎲 Initiating Gambit...")
        await execute_gambit_event(context.bot, context)

    elif event_name == 'coinrush':
        duration = 10 * 60
        update_game_state({'coin_rush_until': now + duration})
        
        async def coin_rush_end(ctx: ContextTypes.DEFAULT_TYPE):
            await broadcast_event_message(ctx.bot, "💰 *Coin Rush has ended!* 💰\n\nThanks for participating!", ctx)
            
        if context.job_queue:
            context.job_queue.run_once(coin_rush_end, duration)
        await broadcast_event_message(context.bot, "💰 *COIN RUSH!* 💰\n\nFor 10 minutes, messages in group chats drop free Power Coins for MSGC registered players!", context)
        await safe_reply(update, "✅ Coin Rush started for 10 minutes.")

    elif event_name == 'freebiefrenzy':
        update_game_state({'freebie_frenzy_until': now + (15 * 60)})
        await broadcast_event_message(context.bot, "🎁 *FREEBIE FRENZY!* 🎁\n\nFor 15 minutes, Tier 1 cards (except Angel) are FREE in the store for MSGC registered players!", context)
        await safe_reply(update, "✅ Freebie Frenzy started for 15 minutes.")

    else:
        await safe_reply(update, f"Unknown event: '{event_name}'. Use /startevent to see available events.")

async def endevent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to clear all active events."""
    if not is_admin(update.effective_user.id):
        await safe_reply(update, "You are not authorized to use this command.")
        return

    update_game_state({
        'bogo_active_until': 0,
        'rush_hour_until': 0,
        'truce_until': 0,
        'coin_rush_until': 0,
        'freebie_frenzy_until': 0
    })
    await safe_reply(update, "🛑 All active events have been ended.")


# --- EVENT SYSTEM ---

async def broadcast_event_message(bot: Bot, message: str, context: ContextTypes.DEFAULT_TYPE = None):
    """Utility to broadcast an event announcement to tracked group chats and activity log."""
    await log_activity(bot, message, title="🎉 Power Store Event!")
    
    group_chat_ids = set()
    if context and hasattr(context, 'bot_data'):
        group_chat_ids.update(context.bot_data.get('group_chat_ids', set()))
    
    game_state = get_game_state()
    stored_chats = game_state.get('group_chat_ids', [])
    if isinstance(stored_chats, list):
        group_chat_ids.update(stored_chats)

    for chat_id in group_chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Failed to send event broadcast to chat {chat_id}: {e}")

async def execute_secret_santa_event(bot: Bot, context: ContextTypes.DEFAULT_TYPE):
    """Executes Secret Santa card/coin gift exchange across all MSGC registered players."""
    all_players = get_all_players()
    msgc_players = [p for p in all_players if bool(p.get('msgc_registered', False))]

    if len(msgc_players) < 2:
        logger.info("Secret Santa cancelled: Less than 2 MSGC registered players.")
        await broadcast_event_message(bot, "🎅 *Secret Santa Cancelled:* At least 2 MSGC registered players are required.", context)
        return

    player_ids = [p.get('user_id') for p in msgc_players if p.get('user_id')]
    player_map = {p.get('user_id'): p for p in msgc_players if p.get('user_id')}

    if len(player_ids) < 2:
        return

    receivers = player_ids[:]
    random.shuffle(receivers)

    # Prevent self-gifting
    for i in range(len(player_ids)):
        if player_ids[i] == receivers[i]:
            swap_idx = (i + 1) % len(player_ids)
            receivers[i], receivers[swap_idx] = receivers[swap_idx], receivers[i]

    summary_messages = ["🎁 *Secret Santa Event!* 🎁\n\nGifts have been exchanged between MSGC registered players:"]
    eligible_santa_cards = [cid for cid, c in POWER_CARDS.items() if c.get('tier') in [1, 2]]

    for i, sender_id in enumerate(player_ids):
        receiver_id = receivers[i]
        sender_data = player_map[sender_id]
        receiver_data = player_map[receiver_id]

        sender_name = sender_data.get('first_name') or sender_data.get('username') or 'A player'
        receiver_name = receiver_data.get('first_name') or receiver_data.get('username') or 'Another player'
        
        sender_cards = list(sender_data.get('cards', []))
        receiver_cards = list(receiver_data.get('cards', []))
        eligible_cards = [card for card in sender_cards if card in eligible_santa_cards]

        try:
            if eligible_cards:
                card_to_send = random.choice(eligible_cards)
                sender_cards.remove(card_to_send)
                if card_to_send not in receiver_cards:
                    receiver_cards.append(card_to_send)

                update_player_data(sender_id, {'cards': sender_cards})
                update_player_data(receiver_id, {'cards': receiver_cards})

                card_name = POWER_CARDS.get(card_to_send, {}).get('name', card_to_send)
                summary_messages.append(f"🎁 {sender_name} gifted a {card_name} card to {receiver_name}!")
            else:
                sender_coins = sender_data.get('coins', 0)
                coins_to_send = min(50, sender_coins)
                if coins_to_send > 0:
                    receiver_coins = receiver_data.get('coins', 0)
                    update_player_data(sender_id, {'coins': sender_coins - coins_to_send})
                    update_player_data(receiver_id, {'coins': receiver_coins + coins_to_send})
                    summary_messages.append(f"💰 {sender_name} gifted {coins_to_send} PC to {receiver_name}!")
                else:
                    summary_messages.append(f"💨 {sender_name} had no gifts/coins to give to {receiver_name}.")
        except Exception as e:
            logger.error(f"Error transferring Secret Santa gift ({sender_id} -> {receiver_id}): {e}")

    await broadcast_event_message(bot, "\n".join(summary_messages), context)

async def execute_gambit_event(bot: Bot, context: ContextTypes.DEFAULT_TYPE):
    """Executes Gambit event: awards a random non-God card to every MSGC registered player."""
    all_players = get_all_players()
    msgc_players = [p for p in all_players if bool(p.get('msgc_registered', False))]

    if not msgc_players:
        logger.info("Gambit cancelled: No MSGC registered players found.")
        await broadcast_event_message(bot, "🎲 *Gambit Cancelled:* No MSGC registered players found.", context)
        return

    gambit_cards = [card_id for card_id in POWER_CARDS if card_id != 'god']
    summary_messages = ["🎲 *Gambit Event!* 🎲\n\nEvery MSGC registered player receives a random card!"]

    for player in msgc_players:
        player_id = player.get('user_id')
        if not player_id: continue
        player_name = player.get('first_name') or player.get('username') or 'Player'
        player_cards = list(player.get('cards', []))

        try:
            random_card = random.choice(gambit_cards)
            card_name = POWER_CARDS.get(random_card, {}).get('name', random_card)
            if random_card not in player_cards:
                player_cards.append(random_card)

            update_player_data(player_id, {'cards': player_cards})
            summary_messages.append(f"🎁 {player_name} received a {card_name} card!")
        except Exception as e:
            logger.error(f"Error awarding Gambit card to player {player_id}: {e}")

    await broadcast_event_message(bot, "\n".join(summary_messages), context)

async def handle_group_message_and_coin_rush(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks active group chat IDs and processes Coin Rush random coin drops."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user or user.is_bot:
        return

    if chat.type in ['group', 'supergroup']:
        group_chats = context.bot_data.setdefault('group_chat_ids', set())
        group_chats.add(chat.id)

    game_state = get_game_state()
    if game_state.get('coin_rush_until', 0) > time.time():
        if random.random() < 0.25:
            drop = random.randint(2, 5)
            p_data = get_player_data(user.id)
            if p_data:
                update_player_data(user.id, {'coins': p_data.get('coins', 0) + drop})
                await safe_reply(update, f"💰 *Coin Rush Drop!* {user.first_name} received +{drop} Power Coins!")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler to handle errors gracefully and avoid raw Markdown entity parse crashes."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    err_str = str(context.error) if context.error else "Unknown error"
    
    if any(k in err_str.lower() for k in ["can't parse entities", "bad request", "query is too old", "message is not modified", "chat not found"]):
        logger.warning(f"Captured minor Telegram API error ({err_str}). Handled gracefully.")
        return
        
    if isinstance(update, Update):
        await safe_reply(update, f"❌ An error occurred: {err_str}")

# --- APPLICATION SETUP ---

request_obj = HTTPXRequest(
    connect_timeout=20.0,
    read_timeout=20.0,
    write_timeout=20.0,
    pool_timeout=20.0
)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request_obj).build()

application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("profile", profile_command))
application.add_handler(CommandHandler("store", store_command))
application.add_handler(CommandHandler("use", use_command))
application.add_handler(CommandHandler("award", award_command))
application.add_handler(CommandHandler("awardall", awardall_command))
application.add_handler(CommandHandler("resetallcoins", resetallcoins_command))
application.add_handler(CommandHandler("startevent", startevent_command))
application.add_handler(CommandHandler("endevent", endevent_command))
application.add_handler(CommandHandler("givecard", givecard_command))
application.add_handler(CommandHandler("allplayers", all_players_command))
application.add_handler(CallbackQueryHandler(handle_inspect_callback, pattern="^inspect_"))
application.add_handler(CallbackQueryHandler(handle_back_to_store_callback, pattern="^back_to_store$"))
application.add_handler(CallbackQueryHandler(handle_buy_callback, pattern="^buy_"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message_and_coin_rush))
application.add_error_handler(global_error_handler)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to process updates."""
    async def handle_update():
        await application.initialize()
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        await application.shutdown()

    asyncio.run(handle_update())
    return 'ok'

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == "__main__":
    mode = os.environ.get("RUN_MODE", "polling").lower()
    if mode == "webhook":
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    else:
        logger.info("Starting bot in polling mode...")
        application.run_polling()