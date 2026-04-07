# Vault Guardian — Quick Reference

## 🚀 Quick Start

```bash
source venv/bin/activate
python -m src.main
```

## 📱 Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/summary` | Get financial summary for this month |
| `/earnings` | List recent earnings |
| `/expenses` | List recent expenses |
| `/clear` | Clear conversation history |

## 💬 Natural Language Examples

- `"I earned ₹5000 from Nike today for 2 reels"`
- `"Got 50k from Amazon for 3 reels and 1 story"`
- `"Spent 2000 on video editing"`
- `"Show me all my earnings"`
- `"How much did Nike pay me?"`
- `"Update earning 1, amount is 55000"`

## 🔧 Configuration

Edit `.env` with your values (see `.env.example`):

```
TELEGRAM_BOT_TOKEN=your_token
ALLOWED_CHAT_ID=your_chat_id
LLM_API_KEY=your_nvidia_api_key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=z-ai/glm4.7
```

## 📋 Conversation ChatLog

Every turn is logged to `logs/chatlog/YYYY-MM-DD.jsonl`. View with:

```python
# In Python
from src.chatlog import ChatLog
cl = ChatLog()
turns = cl.get_turns()           # today's turns
turns = cl.get_turns("2026-04-07")  # specific date
```

Each entry captures: user message, LLM decision, tool calls with arguments, tool results, final response, and duration.

## ⚠️ Common Issues

| Issue | Fix |
|-------|-----|
| Bot doesn't respond | Check `ALLOWED_CHAT_ID` in `.env` |
| 409 Conflict | Kill stale bot instances: `pkill -f src.main` |
| Database error | `python reset_data.py` then restart |
| Import error | `source venv/bin/activate` |

## 📚 Full Docs

- **[RUNNING.md](RUNNING.md)** — Setup & deployment guide
- **[TESTING.md](TESTING.md)** — Testing instructions
- **[README.md](../README.md)** — Project overview
