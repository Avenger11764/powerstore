# ⚡ Power Store Telegram Bot 🎮

An interactive card game, economy, and power-up Telegram bot designed for group chats and private interactions. Players earn and spend **Power Coins (PC)**, buy strategic **Power Cards**, unleash attacks and defenses against other players, and participate in live **Admin Events**.

---

## 🌟 Key Features

- 💰 **Power Economy:** Earn coins from message activity, admin awards, and card effects.
- 🎴 **Strategic Power Cards:** 29 unique cards across 4 tiers (Defensive, Offensive, Tactical, and Legendary).
- 🎉 **Live Event System:** 7 automated admin events with direct DM notifications to players.
- 🛑 **Dynamic Card Management:** Admins can temporarily disable/enable cards live without restarting the bot.
- 👥 **Multi-Admin Support:** Authenticated multi-admin authorization for server management.
- 🛡️ **Fail-Safe Robustness:** Safe message routing preventing crashes on edited messages, callback queries, or channel posts.
- ⚡ **Supabase Cloud Sync:** Real-time state persistence for user balances, inventories, and global timers.

---

## 🎴 Power Cards Catalog

Here is the exact price list, tier ranking, target type, and description of all **30 Power Cards** as defined in the bot store:

| Card Name | Icon | Price | Tier | Target | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Speed** | ⚡️ | **20 PC** | Tier 1 | Self/Global | Reduces the cooldown time on your card usage by half for the next 1 hour. |
| **Vision** | 👁️ | **20 PC** | Tier 1 | Targeted | Secretly view the card inventory of a target player. |
| **Angel** | 👼 | **20 PC** | Tier 1 | Targeted | Gift 20 of your own Power Coins to another player (Max 2 times in 24h). |
| **Blackout** | 🕶️ | **25 PC** | Tier 1 | Self/Global | For 3 hours, you are immune to Vision and Spotlight cards. |
| **Re-roll** | ♻️ | **15 PC** | Tier 1 | Self/Global | Discard your entire hand to gain back 75% of its total coin value. |
| **Black Market** | 💰 | **40 PC** | Tier 1 | Self/Global | For 5 minutes, all items in the store are 50% off for you. |
| **Lottery Ticket** | 🎟️ | **5 PC** | Tier 1 | Self/Global | A cheap card with a 2% chance to win 100 coins. A gamble for those feeling lucky. |
| **Coin Insurance** | 💼 | **25 PC** | Tier 1 | Self/Passive | Passive inventory card. Automatically refunds 50% of any coins stolen or burned from attacks. |
| **Flame** | 🔥 | **20 PC** | Tier 2 | Targeted | Burn 15 Power Coins from a target player. |
| **Glitch** | 🌀 | **30 PC** | Tier 2 | Targeted | Force a target player to randomly discard one of their cards. |
| **Shackle** | ⛓️ | **30 PC** | Tier 2 | Targeted | For 1 hour, your target is unable to use any cards. |
| **Spotlight** | 💡 | **25 PC** | Tier 2 | Targeted | Publicly reveal a target player's entire card inventory to the group. |
| **Time Warp** | ⏳ | **25 PC** | Tier 2 | Targeted | Immediately end an active Karma or Shackle effect on a target player. |
| **Mirage** | 🏜️ | **25 PC** | Tier 2 | Self/Global | For 1 hour, Vision/Spotlight used on you will show a fake hand. |
| **Dispel** | 💨 | **30 PC** | Tier 2 | Self/Global | Immediately removes Shackle and personal Inflation effects from yourself. |
| **Double or Nothing** | 🎲 | **20 PC** | Tier 2 | Targeted | Target a player. You both secretly wager 40 coins. A coin is flipped; the winner takes the entire pot (80 coins). |
| **Forcefield** | 🛡️ | **40 PC** | Tier 3 | Self/Global | Block the next negative card used on you. |
| **Trap** | 🪤 | **50 PC** | Tier 3 | Self/Global | Set a trap. The next player to target you with a negative card has it nullified and loses 15 coins. |
| **Ricochet** | ↪️ | **40 PC** | Tier 3 | Self/Global | Activate this card. For the next 1 hr, the next negative card used on you is redirected to a random other player in the game. |
| **Clairvoyance** | 🔮 | **40 PC** | Tier 3 | Targeted | Reveal the true cards of a target user, even if they are hidden using Mirage. Bypasses Mirage, but not Blackout. |
| **Devil** | 😈 | **35 PC** | Tier 3 | Targeted | Steal 25 Power Coins from an opponent. |
| **Karma** | ⚖️ | **45 PC** | Tier 3 | Self/Global | For 2 hours, any negative card used on you is reflected back to the sender. |
| **Swap** | 🔄 | **35 PC** | Tier 3 | Targeted | Swap a random card from your hand with a random card from a target's hand. |
| **Steal** | 🥷 | **40 PC** | Tier 3 | Targeted | Steals a random card from the target user. |
| **Inflation** | 📈 | **60 PC** | Tier 3 | Self/Global | For 1 hour, all card prices in the store are doubled for everyone but you. |
| **Purge** | 🎯 | **50 PC** | Tier 3 | Targeted | Name a card. If your target has it, they are forced to discard it. |
| **Vortex** | 🌪️ | **30 PC** | Tier 3 | Self/Global | All players in the game (including you) must immediately discard one random card. |
| **Amnesia** | ❓ | **75 PC** | Tier 3 | Targeted | Force a target player to discard their entire hand of cards. |
| **Frenzy** | 🔀 | **35 PC** | Tier 3 | Self/Global | Use your next two cards without a cooldown period. |
| **God** | 🛐 | **80 PC** | Tier 4 | Self/Global | Choose one of three powers: Blessing (give a Forcefield), Smite (target loses half their coins), or Tribute (all other players pay you 5 coins). |

---

### 👑 The God Card Divine Powers

The **God Card** holds ultimate authority:

- 🛐 **God's Tribute:** Collects 5 PC tribute from all other players.
  - **DM Alerts:** Automatically DMs every player notifying them who received their tribute.
- ⚡ **God's Smite:** Destroys 50% of a target player's coins.
- 🛐 **God's Blessing:** Grants a free Karma card to a target player.

---

### 🛡️ Anti-Targeting & Player Protection Suite

To prevent unfair dogpiling and continuous targeting of single players:
1. **🛡️ 30-Minute Attack Grace Period ("Victim Shield"):** Whenever a player is hit by an offensive card (`Flame`, `Devil`, `Glitch`, `Steal`, `Swap`, `Purge`, `Amnesia`, `Shackle`, `Double or Nothing`, `God Smite`), they gain a 30-minute recovery shield during which no other player can target them with negative cards.
2. **💰 Bankruptcy Floor (10 PC Protection):** Players with 10 PC or less cannot be targeted by coin-draining attacks (`Flame`, `Devil`, `God Smite`).
3. **📈 30% Escalating Repeat Attack Penalty:** If an attacker repeatedly uses the same card against the same player, they must pay an escalating surcharge (+30% of card price per repeat) to balance gameplay.
4. **💼 Coin Insurance (Tier 1 Passive):** When held in inventory, automatically refunds 50% of any coins stolen or burned by attacks.

---

## 🎉 Live Admin Event System

Admins can trigger **7 special events** to boost chat engagement. All events include automatic **Group Chat Broadcasts** and **Direct DM Notifications** to registered players:

| Event Command | Name | Duration | Description & Effects |
| :--- | :--- | :---: | :--- |
| `/startevent bogo` | **BOGO Sale** 🎁 | 15 Min | Every store purchase includes a free random Tier 1/2 card. |
| `/startevent secretsanta` | **Secret Santa** 🎅 | Instant | Players are paired to randomly exchange cards or coins with DM alerts. |
| `/startevent rushhour` | **Rush Hour** ⏰ | 1 Hour | All card cooldowns are bypassed (0s cooldown). |
| `/startevent truce` | **Truce** 🤝 | 15 Min | All negative and offensive cards are disabled. |
| `/startevent gambit` | **Gambit** 🎲 | Instant | Every registered player receives a random non-God card in their DM. |
| `/startevent coinrush` | **Coin Rush** 💰 | 10 Min | Group chat messages drop free bonus coins (5–15 PC). |
| `/startevent freebiefrenzy` | **Freebie Frenzy** 🎁 | 15 Min | All Tier 1 cards (except Angel) are 100% FREE in the store. |

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
| `/closestore` | `/closestore` | Closes the Power Store (blocks all card purchases and card usage). |
| `/openstore` | `/openstore` | Reopens the Power Store for all players. |
| `/startevent` | `/startevent <event_name>` | Launches one of the 7 admin events. |
| `/endevent` | `/endevent` | Clears all active events globally. |
| `/revertevent` | `/revertevent <event_name>` | Reverts effects of an event (takes back Gambit cards, returns Secret Santa gifts, or cancels active timers). |
| `/disablecard` | `/disablecard <card_name>` | Disables a card from store purchase and usage. |
| `/enablecard` | `/enablecard <card_name>` | Re-enables a previously disabled card. |
| `/disabledcards`| `/disabledcards` | Views all currently disabled cards. |
| `/eliminate` | `/eliminate @username` | Marks a player as ELIMINATED (blocks them from store, card usage, and events). |
| `/uneliminate` | `/uneliminate @username` | Restores an eliminated player to ACTIVE status. |
| `/award` | `/award <amount> @username` | Awards or deducts (negative amount) coins from a player. |
| `/awardall` | `/awardall <amount>` | Awards or deducts coins from ALL registered players. |
| `/givecard` | `/givecard <Card Name> @username` | Directly places a card into a player's inventory. |
| `/resetallcoins`| `/resetallcoins [amount]` | Resets all players to 0 PC (or specified amount) and clears card inventories. |
| `/allplayers` / `/players` | `/players` | Displays a detailed report of all registered players, coins, cards, and live statuses. |

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