# 🛠️ Vault Guardian — Developer Guide

## Local Development

```bash
git clone https://github.com/vineetkishore01/Vault-Guardian.git
cd Vault-Guardian
pip install -r requirements-dev.txt
cp .env.example .env  # edit with your credentials
python -m src.main
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_database.py::test_create_earning -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Architecture

```
src/
├── main.py           # Entry point: DB init, scheduler, bot, warmup
├── config.py         # Config loader (YAML + env vars)
├── chatlog.py        # Conversation turn logger (JSONL)
├── brand_matching.py # Fuzzy brand name matching
│
├── bot/
│   ├── __init__.py   # Re-exports
│   └── handler.py    # Telegram bot: commands, message handling, LLM loop
│
├── database/
│   ├── __init__.py   # DB manager, engine setup, session factory
│   ├── models.py     # SQLAlchemy models (Earning, Expense, etc.)
│   └── crud.py       # Async CRUD operations
│
├── llm/
│   ├── __init__.py   # Re-exports
│   ├── client.py     # OpenAI-compatible client with retries/rate limit
│   └── tools.py      # Tool definitions (add_earning, search_earnings, etc.)
│
├── scheduler/
│   └── __init__.py   # APScheduler: payment reminders, overdue alerts
│
├── analytics/
│   └── __init__.py   # Report generation (PDF, Excel, charts)
│
└── utils/
    └── __init__.py   # Date/amount parsing, formatting, validation
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Usage guide |
| `/clear` | Clear conversation history |
| `/summary` | Financial summary (this month) |
| `/earnings` | Recent earnings list |
| `/expenses` | Recent expenses |
| `/report` | Generate PDF report |

## Natural Language Examples

| Input | What Happens |
|-------|-------------|
| "I earned 50k from Nike for 2 reels" | Creates earning entry |
| "Spent 2000 on video editing" | Creates expense entry |
| "Show me all earnings" | Queries and lists earnings |
| "How much did Nike pay me?" | Filters and sums by brand |
| "Update earning 1, amount is 55000" | Updates existing entry |
| "Delete the Nike entry" | Deletes with confirmation |

## Configuration

### .env (secrets)
```
TELEGRAM_BOT_TOKEN=
ALLOWED_CHAT_ID=
LLM_API_KEY=
```

### config/config.yaml (settings)
```yaml
llm:
  max_tokens: 4096
  temperature: 0.7
  timeout: 120
security:
  rate_limit_per_minute: 30
  max_message_length: 4000
```

### config/prompts/system_prompt.txt
The LLM system prompt — domain rules, anti-injection rules, amount parsing instructions.

## Chat Logs

Every conversation turn is logged to `logs/chatlog/YYYY-MM-DD.jsonl`:

```json
{
  "turn_id": 1,
  "timestamp": "2026-04-09T22:27:44",
  "user_message": "earned 4k from zomato for a reel 3 days ago",
  "llm_decision": "tool_call",
  "tool_calls": [{"name": "add_earning", "arguments": {...}}],
  "final_response": "✅ Added earning: ₹4,000.00 from zomato on 07 Apr 2026",
  "duration_ms": 20460,
  "error": null
}
```

## Key Design Decisions

- **Single-user**: Chat ID whitelist, no multi-user support
- **SQLite**: Fine for single user, switch to PostgreSQL for scale
- **LLM tool calling**: All database operations go through LLM tool calls
- **Confirmation dialogs**: Destructive operations (delete/update) require user confirmation
- **Brand matching**: Fuzzy matching with confirmation for ambiguous matches
- **IST timezone**: All dates/times in Asia/Kolkata
- **Anti-hallucination**: Mutation tool results override LLM-generated text
