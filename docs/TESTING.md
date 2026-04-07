# Vault Guardian — Testing Guide

## Run Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Test Coverage

| File | Tests |
|------|-------|
| `tests/test_database.py` | Create, read, update, delete earnings and expenses |
| `tests/test_utils.py` | Date parsing, amount parsing, currency formatting, brand normalization |

## Live Testing Workflow

```bash
# 1. Reset database
python reset_data.py

# 2. Start bot
python -m src.main

# 3. Send messages in Telegram
# 4. Check database state
# 5. Kill bot (Ctrl+C)
# 6. Repeat
```

## Manual Database Check

```python
source venv/bin/activate
python
>>> from src.database import db_manager, crud
>>> import asyncio
>>> async def check():
...     async with db_manager.get_session() as db:
...         earnings = await crud.EarningCRUD.search(db, limit=10)
...         for e in earnings:
...             print(f"{e.brand_name} | ₹{e.amount_earned}")
>>> asyncio.run(check())
```

## Conversation ChatLog

After the bot runs, conversation turns are logged to `logs/chatlog/YYYY-MM-DD.jsonl`. View programmatically:

```python
from src.chatlog import ChatLog
cl = ChatLog()
turns = cl.get_turns()  # today's turns
for t in turns:
    print(f"User: {t['user_message']}")
    print(f"Bot:  {t['final_response']}")
```
