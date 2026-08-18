# ⚡ Power Store Telegram Bot 🎮

An interactive card game, economy, and power-up Telegram bot designed for group chats and private interactions. Players earn and spend **Power Coins (PC)**, buy strategic **Power Cards**, unleash attacks and defenses against other players, and participate in live **Admin Events**.

---

## 🌟 Key Features

- 💰 **Power Economy:** Earn coins from message activity, admin awards, and card effects.
- 🎴 **Strategic Power Cards:** 16 unique cards across 3 tiers (Defensive, Offensive, Tactical, and Legendary).
- 🎉 **Live Event System:** 7 automated admin events with direct DM notifications to players.
- 🛑 **Dynamic Card Management:** Admins can temporarily disable/enable cards live without restarting the bot.
- 👥 **Multi-Admin Support:** Authenticated multi-admin authorization for server management.
- 🛡️ **Fail-Safe Robustness:** Safe message routing preventing crashes on edited messages, callback queries, or channel posts.
- ⚡ **Supabase Cloud Sync:** Real-time state persistence for user balances, inventories, and global timers.

---

## 🎴 Power Cards Catalog

Cards are categorized into **3 Tiers** based on their power level and coin cost:

### 🛡️ Tier 1 Cards (Basic & Defensive)
| Card Name | Icon | Price | Type | Effect Description |
| :--- | :---: | :---: | :---: | :--- |
| **Forcefield** | 🛡️ | 10 PC | Defense | Protects you from the next negative card attack targeting you. |
| **Trap** | 🪤 | 10 PC | Defense | Sprung when attacked! Counter-attacks the attacker, causing them to lose 15 PC. |
| **Karma** | ⚖️ | 15 PC | Passive | Lasts 30 mins. If someone attacks you, they suffer 50% of the damage. |
| **Angel** | 👼 | 20 PC | Support | Transfer up to 20 PC to another player safely without tax. |

### ⚡ Tier 2 Cards (Tactical & Offensive)
| Card Name | Icon | Price | Type | Effect Description |
| :--- | :---: | :---: | :---: | :--- |
| **Double or Nothing** | 🎲 | 40 PC | Gamble | Require $\ge 40$ PC balance. 50% chance to double your wager or lose it all! |
| **Mirage** | 🏜️ | 30 PC | Illusion | Lasts 15 mins. Creates 3 fake cards in your inventory to confuse stealers. |
| **Speed** | ⚡ | 35 PC | Buff | Lasts 20 mins. Reduces your card usage cooldowns by 50%. |
| **Blackout** | 🕶️ | 35 PC | Utility | Hides your coin balance and active cards from `/profile` lookups for 1 hour. |
| **Black Market** | 💰 | 50 PC | Economy | Grants 50% discount on all store card purchases for 15 minutes. |
| **Shackles** | ⛓️ | 50 PC | Debuff | Shackles a target player for 15 mins, preventing them from using cards (except Dispel). |
| **Frenzy** | 🔀 | 60 PC | Buff | Grants 3 consecutive instant card uses with 0s cooldown. |
| **Ricochet** | ↪️ | 60 PC | Defense | Lasts 20 mins. Reflects 100% of negative card attacks back onto the attacker. |
| **Dispel** | 🪄 | 40 PC | Utility | Cleanses all active negative status debuffs from yourself or a target ally. |

### 👑 Tier 3 Cards (Legendary & Ultimate)
| Card Name | Icon | Price | Type | Effect Description |
| :--- | :---: | :---: | :---: | :--- |
| **Devil** | 😈 | 100 PC | Offensive | Steals 30% of a target player's total Power Coins. |
| **Inflation** | 📈 | 150 PC | Economy | Doubles `/store` card prices for all other players for 30 minutes. |
| **God** | 👑 | 250 PC | Ultimate | Unleashes 1 of 3 divine powers (**Blessing**, **Smite**, or **Tribute**). |

---

### 👑 The God Card Divine Powers

The **God Card** holds ultimate authority with strict global and daily balancing limits:

- ⚡ **Daily Player Limit:** Max **2 God Card uses** per player per day (`⚡ God Card Uses Today: X/2`).
- 🛐 **God's Tribute:** Collects tribute coins from all other players.
  - **Global Limit:** Max **1 Tribute globally every 24 hours** across the entire bot.
  - **DM Alerts:** Automatically DMs every player notifying them who received their tribute.
- ⚡ **God's Smite:** Destroys 50% of a target player's coins.
  - **Global Limit:** Max **2 Smites globally every 24 hours** across the entire bot.
- 🛐 **God's Blessing:** Grants a free Karma card to a target player.

---

## 🎉 Live Admin Event System

Admins can trigger **7 special events** to boost chat engagement. All events include automatic **Group Chat Broadcasts** and **Direct DM Notifications** to registered players:

| Event Command | Name | Duration | Description & Effects |
| :--- | :--- | :---: | :--- |
| `/startevent bogo` | **BOGO Sale** 🎁 | 15 Mins | Purchases in `/store` include a FREE Tier 1 or 2 bonus card. |
| `/startevent secretsanta` | **Secret Santa** 🎅 | Instant | Automatically shuffles players to exchange cards/coins with DM alerts. |
| `/startevent rushhour` | **Rush Hour** ⏰ | 1 Hour | All card usage cooldown timers are disabled (0s wait). |
| `/startevent truce` | **Truce** 🤝 | 15 Mins | All negative and attacking cards are disabled. |
| `/startevent gambit` | **Gambit** 🎲 | Instant | Every registered player receives a random non-God card in their DM. |
| `/startevent coinrush` | **Coin Rush** 💰 | 10 Mins | Random messages in group chats drop bonus coins (2-5 PC). |
| `/startevent freebiefrenzy` | **Freebie Frenzy** 🎁 | 15 Mins | Tier 1 cards (except Angel) become 100% FREE in the store. |

- `/endevent` — Terminates all active events immediately.

---

## 🎮 Player Commands

| Command | Usage | Description |
| :--- | :--- | :--- |
| `/start` | `/start` | Registers your player account and opens welcome menu. |
| `/profile` | `/profile` | Displays your coin balance, card inventory, active status, and daily God card counter. |
| `/store` | `/store` | Opens the interactive Power Card Store (Private DM only). |
| `/use` | `/use <Card Name> [@target]` | Activates a card from your inventory (use in group chats for targeted cards). |
| `/help` | `/help` | Displays command overview and game rules. |

---

## 👑 Admin Commands

Admins specified in `config.py` (`ADMIN_USER_IDS`) have full access to management tools:

| Command | Usage | Description |
| :--- | :--- | :--- |
| `/startevent` | `/startevent <event_name>` | Launches one of the 7 admin events. |
| `/endevent` | `/endevent` | Clears all active events globally. |
| `/disablecard` | `/disablecard <card_name>` | Disables a card from store purchase and usage. |
| `/enablecard` | `/enablecard <card_name>` | Re-enables a previously disabled card. |
| `/disabledcards`| `/disabledcards` | Views all currently disabled cards. |
| `/award` | `/award <amount> @username` | Awards or deducts (negative amount) coins from a player. |
| `/awardall` | `/awardall <amount>` | Awards or deducts coins from ALL registered players. |
| `/givecard` | `/givecard <Card Name> @username` | Directly places a card into a player's inventory. |
| `/resetallcoins`| `/resetallcoins` | Resets all players to 5 PC and clears their card inventories. |
| `/allplayers` | `/allplayers` | Displays a detailed report of all registered players and stats. |

---

## 🛠️ Architecture & Tech Stack

- **Language:** Python 3.12
- **Telegram Framework:** `python-telegram-bot` (v20+ async architecture)
- **Database:** Supabase PostgreSQL Cloud Database via `supabase-py` SDK
- **Web Server:** Flask web server running parallel ping health endpoints
- **HTTP Client:** Custom `httpx` request handler with configured timeouts

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
- Python 3.10+ installed
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- A Supabase Project URL & Publishable API Key

### 2. Environment Variables
Configure your environment variables or update `config.py`:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
SUPABASE_URL="https://your_supabase_project.supabase.co"
SUPABASE_KEY="your_supabase_api_key"
ADMIN_USER_IDS="7602825139,1253445521"
```

### 3. Installation Steps
```bash
# Clone repository
git clone https://github.com/Avenger11764/powerstore.git
cd powerstore

# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py
```

---

## 📜 License & Credits

Developed with ❤️ for Telegram Gaming Communities.  
Maintained by **[Avenger11764](https://github.com/Avenger11764)**.