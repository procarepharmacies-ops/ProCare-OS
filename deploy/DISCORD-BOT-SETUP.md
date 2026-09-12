# ProCare Discord Bot — Weekly Schedule Distribution

**Version:** 1.0  
**Date:** 2026-09-12  
**Purpose:** Automate staff schedule distribution via Discord

---

## Setup Instructions

### 1. Discord Server Setup

1. Create a Discord server for ProCare staff
2. Create channels:
   - `#📋-weekly-schedule` — Schedule announcements
   - `#⏰-reminders` — Daily reminders
   - `#🏥-announcements` — General staff announcements

### 2. Discord Bot Creation

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application**
3. Name it: `ProCare Schedule Bot`
4. Go to **Bot** section → **Add Bot**
5. Copy the **Token** (keep it secret)
6. Under **TOKEN**, click **Copy** and save to `.env`:

```bash
DISCORD_BOT_TOKEN=your_token_here
DISCORD_CHANNEL_ID=your_channel_id_here  # #📋-weekly-schedule channel ID
```

### 3. Bot Permissions

Enable these permissions:
- ✅ Send Messages
- ✅ Read Message History
- ✅ Mention @everyone / @here
- ✅ Manage Messages

### 4. Invite Bot to Server

Use this URL (replace YOUR_BOT_ID):
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=8&scope=bot
```

---

## Special Week Schedule Message Format

### For September 13-19, 2026:

**Copy & paste into Discord:**

```
📋 **جدول الأسبوع الخاص — Special Week Schedule**

⚠️ **هذا الجدول فقط 13-19 سبتمبر 2026**

**الاجازات هذا الأسبوع:**
🕐 الأحد (Sun 14): **يوسف** ❌ إجازة
🕑 الاثنين (Mon 15): **عبدالله** ❌ إجازة
🕒 الثلاثاء (Tue 16): **ندي** ❌ إجازة
🕓 الأربعاء (Wed 17): **المدير** ❌ إجازة
🕔 الخميس (Thu 18): **ريم** ❌ إجازة
🕕 الجمعة (Fri 19): **كريم** ❌ إجازة

**الفرع الأول (Branch 1):**
- السبت-الجمعة: ندي 8-4 | نور 12-8 | يوسف/عبدالله 4-12 | كريم 12ص-8
- **الثلاثاء (Tue 16):** عبدالله يغطي صباح ندي
- **الأربعاء (Wed 17):** لا موظف صباحي

**الفرع الثاني (Branch 2):**
- السبت-الجمعة: ريم 8-4 | أفاف 4-12

📌 **ابتداءً من السبت 20 سبتمبر:** العودة للجدول الأساسي

للتفاصيل الكاملة، شاهد الملف:
📄 ProCare-Weekly-Schedule-Special-Week-Sep13-19.html
```

---

## Daily Reminder Format

**Every day at 9:00 PM Egypt time:**

```
🌙 **غد — Tomorrow's Shift**

📅 {TOMORROW_DATE}

**موظفي غدا:**
⏰ الصباح (8 AM): {NAMES}
⏰ الظهيرة (12 PM): {NAMES}
⏰ المساء (4 PM): {NAMES}
⏰ الليل (8 PM): {NAMES}

تأكدوا من حضوركم في الموعد المحدد! ✅
```

---

## Special Weeks Message Template

For any special week (different day-offs):

```python
# In Python bot code:

special_weeks = {
    "2026-09-13": {
        "name": "Special Week Sep 13-19",
        "days_off": {
            "2026-09-14": "Youssef",
            "2026-09-15": "Abdalla",
            "2026-09-16": "Nada",
            "2026-09-17": "Manager",
            "2026-09-18": "Reem",
            "2026-09-19": "Karim Mohy",
        },
        "html_file": "ProCare-Weekly-Schedule-Special-Week-Sep13-19.html"
    }
}
```

---

## Discord.py Bot Example

**Install Discord.py:**
```bash
pip install discord.py
```

**Basic bot code (bot.py):**

```python
import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo

bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    send_daily_reminder.start()

@tasks.loop(hours=24)
async def send_daily_reminder():
    # Send at 9 PM Egypt time
    cairo_tz = ZoneInfo("Africa/Cairo")
    now = datetime.now(cairo_tz)
    
    if now.hour == 21:  # 9 PM
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        message = generate_tomorrow_schedule()
        await channel.send(message)

@bot.command(name='schedule')
async def send_schedule(ctx):
    """Send this week's schedule"""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    message = """
    📋 **جدول الأسبوع الخاص — Special Week Sep 13-19, 2026**
    
    ⚠️ الاجازات:
    • يوسف: الأحد
    • عبدالله: الاثنين
    • ندي: الثلاثاء
    • المدير: الأربعاء
    • ريم: الخميس
    • كريم: الجمعة
    
    شاهد التفاصيل الكاملة:
    📄 ProCare-Weekly-Schedule-Special-Week-Sep13-19.html
    """
    await channel.send(message)

# Run bot
bot.run(DISCORD_BOT_TOKEN)
```

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| `!schedule` | Send this week's schedule |
| `!reminder tomorrow` | Send tomorrow's shift reminder |
| `!days-off` | Show who's off this week |
| `!help` | Show all commands |

---

## File Reference

- **Schedule HTML:** `docs/ProCare-Weekly-Schedule-Special-Week-Sep13-19.html`
- **Discord Bot Setup:** `deploy/DISCORD-BOT-SETUP.md`
- **Bot Code Template:** Create `src/discord_bot.py`
- **Configuration:** Add to `.env`:
  - `DISCORD_BOT_TOKEN=`
  - `DISCORD_CHANNEL_ID=`

---

## Testing

**Test message in Discord:**
```
!schedule
```

**Expected output:** Schedule message appears in #📋-weekly-schedule

---

**Next steps:**
1. Create Discord server & channel
2. Generate bot token
3. Fill in `.env` with DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID
4. Run bot code
5. Send `!schedule` to test

---

*Last updated: 2026-09-12*  
*For support: Contact ProCare IT Team*
