# Vault Guardian - Quick Reference

## 📋 Essential Files

| File | Purpose |
|------|---------|
| `RUNNING.md` | Complete setup and running guide |
| `TESTING.md` | Testing instructions and checklist |
| `check_setup.py` | Prerequisites checker |
| `reset_data.py` | Reset all data for testing |
| `backup_data.py` | Manual backup tool |
| `.env` | Configuration (copy from `.env.example`) |

## 🚀 Quick Start Commands

```bash
# 1. Check prerequisites
python check_setup.py

# 2. Configure (edit .env file)
cp .env.example .env

# 3. Run bot
python -m src.main

# 4. Reset data (for testing)
python reset_data.py

# 5. Backup data (optional)
python backup_data.py
```

## 📱 Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/report [period]` | Generate report |
| `/summary [period]` | Get financial summary |
| `/earnings [period]` | View earnings |
| `/expenses [period]` | View expenses |
| `/reminders` | View pending reminders |

## 💬 Natural Language Examples

- "I earned ₹5000 from Nike today for 2 reels"
- "Show me my earnings for this month"
- "Add expense: ₹2000 for video editing"
- "Generate a PDF report for last week"
- "What's my financial summary for this week?"
- "Set reminder for Nike payment"

## 🔧 Configuration Required

Edit `.env` file with:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
ALLOWED_CHAT_ID=your_chat_id_here
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.1-70b-instruct
DATABASE_PATH=./data/vault_guardian.db
```

## 🧹 Testing Workflow

```bash
# 1. Reset data
python reset_data.py

# 2. Run bot
python -m src.main

# 3. Test in Telegram

# 4. Reset and repeat
python reset_data.py
```

## ⚠️ Common Issues

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Check chat ID in `.env` |
| Database error | Run `python reset_data.py` |
| LLM API error | Check API key in `.env` |
| Import error | Activate venv: `source venv/bin/activate` |
| Python not found | Use `python3` instead of `python` |

## 📚 Documentation

- **[Running Manual](RUNNING.md)** - Complete setup guide
- **[Testing Guide](TESTING.md)** - Testing instructions
- **[README](README.md)** - Project overview

## 🎯 First Steps

1. ✅ Read [RUNNING.md](RUNNING.md)
2. ✅ Run `python check_setup.py`
3. ✅ Configure `.env` file
4. ✅ Run `python -m src.main`
5. ✅ Test in Telegram
6. ✅ Use `python reset_data.py` to reset

---

**Need help?** Check the detailed guides or review logs in `logs/` directory.
