# Vault Guardian - Running Manual

## Prerequisites

- Python 3.14+ installed
- Telegram Bot Token (from @BotFather)
- Your Telegram Chat ID
- NVIDIA NIM API Key (or other OpenAI-compatible API)
- Virtual environment (recommended)

## Step 1: Setup Environment

### Create Virtual Environment
```bash
cd "/Users/vineetkishore/Code/Vault Guardian"
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 2: Configure Bot

### Get Telegram Bot Token
1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow instructions
3. Copy the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Get Your Chat ID
1. Open Telegram and search for @userinfobot
2. Send any message to the bot
3. Copy your chat ID (looks like: `123456789`)

### Get NVIDIA NIM API Key
1. Go to https://build.nvidia.com/
2. Sign up and get your API key
3. Copy the API key

### Configure .env File
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_ID=your_telegram_chat_id_here

# LLM Configuration
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.1-70b-instruct

# Database Configuration
DATABASE_PATH=./data/vault_guardian.db
```

**Important:** Replace the placeholder values with your actual credentials.

## Step 3: Run the Bot

### Start the Bot
```bash
cd "/Users/vineetkishore/Code/Vault Guardian"
source venv/bin/activate
python -m src.main
```

### What You Should See
```
==================================================
Starting Vault Guardian
==================================================
Ensured directory exists: ./data
Ensured directory exists: ./logs
Ensured directory exists: ./reports
Ensured directory exists: ./config/prompts
Initializing database...
Database initialized successfully
Starting scheduler...
Scheduler started successfully
Sending startup notification...
Starting bot...
Bot is running. Press Ctrl+C to stop.
```

### Stop the Bot
Press `Ctrl+C` to stop the bot gracefully.

## Step 4: Test in Telegram

### Start the Bot
1. Open Telegram
2. Search for your bot (using the name you gave it)
3. Click "Start" or send `/start`

### You Should See
```
👋 Welcome to Vault Guardian!

I'm your personal financial tracking assistant. Here's what I can help you with:

💰 Track earnings from brand collaborations
📊 Monitor expenses
📈 Generate financial reports
⏰ Set payment reminders
🔍 Search and filter your data

Just tell me what you need in natural language, like:
• "I earned ₹5000 from Nike today for 2 reels"
• "Show me my earnings for this month"
• "Add expense: ₹2000 for video editing"
• "Generate a PDF report for last week"

Type /help for more commands.
```

### Try These Commands

**Add Earning:**
```
I earned ₹5000 from Nike today for 2 reels
```

**View Earnings:**
```
Show me my earnings for this month
```

**Add Expense:**
```
Add expense: ₹2000 for video editing
```

**Generate Report:**
```
Generate a PDF report for this month
```

**Get Summary:**
```
What's my financial summary for this week?
```

**View Commands:**
```
/help
```

## Step 5: Reset for Testing

### Reset All Data
```bash
python reset_data.py
```

You'll see:
```
⚠️  This will delete ALL data. Continue? (yes/no):
```

Type `yes` to confirm. This deletes:
- Database (`data/vault_guardian.db`)
- All log files (`logs/`)
- All reports (`reports/`)
- Test cache (`.pytest_cache/`)

### Manual Backup (Optional)
```bash
python backup_data.py
```

This creates a timestamped backup in `backups/YYYYMMDD_HHMMSS/`

## Common Issues

### Bot doesn't respond
**Problem:** Bot starts but doesn't respond to messages

**Solution:**
1. Check your chat ID is correct in `.env`
2. Make sure you're sending messages from the correct Telegram account
3. Check logs in `logs/` directory for errors

### Database error
**Problem:** `sqlite3.OperationalError: unable to open database file`

**Solution:**
```bash
python reset_data.py
```

### LLM API error
**Problem:** `OpenAIError: API connection error`

**Solution:**
1. Check your NVIDIA NIM API key in `.env`
2. Verify the base URL is correct
3. Check you haven't exceeded the 40 req/min rate limit

### Import error
**Problem:** `ModuleNotFoundError: No module named 'xxx'`

**Solution:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Python not found
**Problem:** `python: command not found`

**Solution:**
```bash
# Use python3 instead
python3 -m src.main

# Or activate virtual environment first
source venv/bin/activate
python -m src.main
```

## Docker Setup (Optional)

### Build and Run
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f
```

### Stop
```bash
docker-compose down
```

## Quick Reference

### Commands
```bash
# Activate virtual environment
source venv/bin/activate

# Run bot
python -m src.main

# Reset data
python reset_data.py

# Backup data
python backup_data.py

# Run tests
pytest tests/

# Stop bot
Ctrl+C
```

### Natural Language Examples
- "I earned ₹5000 from Nike today for 2 reels"
- "Show me my earnings for this month"
- "Add expense: ₹2000 for video editing"
- "Generate a PDF report for last week"
- "What's my financial summary for this week?"
- "Set reminder for Nike payment"

### Bot Commands
- `/start` - Start the bot
- `/help` - Show help message
- `/report [period]` - Generate report
- `/summary [period]` - Get financial summary
- `/earnings [period]` - View earnings
- `/expenses [period]` - View expenses
- `/reminders` - View pending reminders

## Next Steps

1. ✅ Configure your `.env` file
2. ✅ Run the bot: `python -m src.main`
3. ✅ Test in Telegram
4. ✅ Try natural language commands
5. ✅ Reset and test again: `python reset_data.py`

## Support

If you encounter issues:
1. Check logs in `logs/` directory
2. Verify your `.env` configuration
3. Try resetting data: `python reset_data.py`
4. Check all prerequisites are met

---

**Happy testing! 🚀**
