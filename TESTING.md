# Testing Guide

## Quick Test Cycle

### 1. Start Fresh
```bash
python reset_data.py
```

### 2. Run the Bot
```bash
python -m src.main
```

### 3. Test in Telegram
- Send `/start` to your bot
- Try natural language commands like:
  - "I earned ₹5000 from Nike today for 2 reels"
  - "Show me my earnings for this month"
  - "Add expense: ₹2000 for video editing"

### 4. Reset and Repeat
```bash
python reset_data.py
```

## What Gets Reset

When you run `reset_data.py`, it deletes:
- `data/vault_guardian.db` (database)
- `logs/` (all log files)
- `reports/` (generated PDFs/Excel files)
- `.pytest_cache/` (test cache)

## Manual Backup (Optional)

Before resetting, you can backup:
```bash
python backup_data.py
```

This creates a timestamped backup in `backups/YYYYMMDD_HHMMSS/`

## Testing Checklist

- [ ] Bot connects to Telegram
- [ ] `/start` command works
- [ ] `/help` command works
- [ ] Add earning via natural language
- [ ] Add expense via natural language
- [ ] View earnings with `/earnings`
- [ ] View expenses with `/expenses`
- [ ] Generate report with `/report`
- [ ] Get summary with `/summary`
- [ ] Brand matching works
- [ ] Error messages are helpful

## Common Issues

### Bot doesn't respond
- Check bot token in `.env`
- Check allowed chat ID in `.env`
- Check logs in `logs/` directory

### Database errors
- Run `reset_data.py` to start fresh
- Check `data/` directory exists

### LLM errors
- Check NVIDIA NIM API key in `.env`
- Check rate limits (40 req/min)
- Check logs for specific errors

## Next Steps After Testing

Once testing is complete:
1. Document any issues found
2. Fix critical problems
3. Improve UX based on experience
4. Update documentation as needed
