# 🛡️ Vault Guardian

An agentic AI Telegram bot for Instagram influencers to track earnings and expenses using natural language.

## 🚀 Key Features

- **Natural Language Processing** — Understands amounts like "50k", "1.5 lakh", "₹75000" and dates like "today", "yesterday", "2nd April"
- **Async Architecture** — `python-telegram-bot` + `SQLAlchemy (Async)` + `aiosqlite`
- **Persistent Confirmations** — Delete/brand-match confirmations survive bot restarts
- **Intelligent Brand Matching** — Fuzzy matching prevents duplicate brand entries
- **Conversation ChatLog** — Every turn logged to `logs/chatlog/YYYY-MM-DD.jsonl`
- **Safety** — Audit logging, chat ID validation, Pydantic schema validation

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.14+ |
| Bot | `python-telegram-bot` (Async) |
| AI | OpenAI-compatible API (NVIDIA NIM) |
| Database | SQLite + SQLAlchemy 2.0 (Async/aiosqlite) |
| Validation | Pydantic v2 |
| Matching | fuzzywuzzy |

## 📦 Setup

```bash
git clone https://github.com/vineetkishore01/Vault-Guardian.git
cd Vault-Guardian
pip install -r requirements.txt
cp .env.example .env  # edit with your credentials
python -m src.main
```

## 💬 Usage Examples

| Input | What Happens |
|-------|-------------|
| `"I earned 50k from Nike for 2 reels"` | Creates earning entry |
| `"Spent 2000 on video editing"` | Creates expense entry |
| `"Show me all earnings"` | Queries and lists earnings |
| `"How much did Nike pay me?"` | Filters and sums by brand |
| `"Update earning 1, amount is 55000"` | Updates existing entry |

## 📚 Documentation

| File | Content |
|------|---------|
| [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) | Commands, config, chatlog access |
| [docs/RUNNING.md](docs/RUNNING.md) | Setup, deployment, troubleshooting |
| [docs/TESTING.md](docs/TESTING.md) | Test suite, live testing workflow |

## 🛡️ Engineering Principles

- **Strict Input Validation** — Every tool call validated against Pydantic schemas
- **Audit Trails** — Every DB mutation logged to `audit_log` table
- **Conversation ChatLog** — Every turn persisted for post-mortem analysis
- **Transactional Safety** — Async context managers, auto-rollback on failure
- **Conversation History** — 20-turn context window for multi-turn understanding

## 📄 License

MIT License.
