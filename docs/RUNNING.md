# Vault Guardian — Running Manual

## Prerequisites

- Python 3.14+
- Telegram Bot Token (from @BotFather)
- Your Telegram Chat ID
- NVIDIA NIM API Key (or any OpenAI-compatible API)

## Setup

```bash
cd "/Users/vineetkishore/Code/Vault Guardian"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
```

Edit `.env`:
```
TELEGRAM_BOT_TOKEN=your_token
ALLOWED_CHAT_ID=your_chat_id
LLM_API_KEY=your_nvidia_api_key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=z-ai/glm4.7
```

### Get Your Credentials

| Value | How to Get |
|-------|-----------|
| Bot Token | Telegram → @BotFather → `/newbot` |
| Chat ID | Telegram → @userinfobot → send any message |
| LLM API Key | https://build.nvidia.com/ → sign up → copy API key |

## Running

```bash
source venv/bin/activate
python -m src.main
```

You should see:
```
Starting Vault Guardian
Database initialized successfully
Scheduler started successfully
Startup notification sent
Bot is running. Press Ctrl+C to stop.
```

## Stopping

Press `Ctrl+C` to stop gracefully.

## Resetting Data

```bash
python reset_data.py
```

Deletes: database, logs, reports. You'll be prompted to confirm.

## Backup

```bash
python backup_data.py
```

Creates a timestamped backup in `backups/YYYYMMDD_HHMMSS/`.

## Docker

```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 409 Conflict error | `pkill -f src.main` then restart |
| Bot doesn't respond | Verify `ALLOWED_CHAT_ID` matches your Telegram chat ID |
| LLM API error | Check `LLM_API_KEY` and `LLM_BASE_URL` in `.env` |
| Import error | `source venv/bin/activate` first |
| Database locked | Delete `data/vault_guardian.db` and restart |

## Architecture

```
User (Telegram)
  → handler.py (message routing, security, conversation history)
    → llm/client.py (OpenAI-compatible API, rate limiting, retries)
      → llm/tools.py (ToolExecutor: add_earning, search_earnings, etc.)
        → database/crud.py (Async SQLAlchemy)
  → scheduler/__init__.py (payment reminders, daily summary)
  → chatlog.py (conversation audit trail)
```

## Key Files

| File | Purpose |
|------|---------|
| `src/bot/handler.py` | Telegram message handling, conversation history |
| `src/llm/client.py` | LLM API client with rate limiting |
| `src/llm/tools.py` | Tool definitions and executor |
| `src/database/models.py` | SQLAlchemy models |
| `src/database/crud.py` | Database CRUD operations |
| `src/scheduler/__init__.py` | Payment reminders & cron jobs |
| `src/config.py` | Configuration from YAML + .env |
| `config/prompts/system_prompt.txt` | LLM system prompt |
