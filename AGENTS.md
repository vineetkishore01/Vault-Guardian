# Vault Guardian - Agent Guidelines

## Build/Test Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run single test file
pytest tests/test_database.py -v

# Run specific test
pytest tests/test_database.py::test_create_earning -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run linting (if using ruff)
ruff check src/

# Run type checking (if using mypy)
mypy src/

# Run the bot locally
python -m src.main

# Run with environment file
cp .env.example .env
# Edit .env with your credentials
python -m src.main
```

## Code Style Guidelines

### Imports
- Use absolute imports: `from src.database.models import Earning`
- Group imports: stdlib → third-party → local
- Sort imports alphabetically within groups
- Use `isort` for consistency

### Formatting
- Use 4 spaces for indentation
- Max line length: 100 characters
- Use f-strings for string formatting
- Type hints required for all functions

### Naming Conventions
- Classes: `PascalCase` (e.g., `EarningCRUD`)
- Functions/variables: `snake_case` (e.g., `get_earnings`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Private: `_leading_underscore` (e.g., `_init_db`)

### Error Handling
- Use specific exceptions, not bare `except:`
- Log errors with context
- Use `raise from` for exception chaining
- Validate inputs early

### Database
- Always use context managers for sessions
- Commit explicitly, don't rely on autoflush
- Use transactions for multi-record operations
- Index frequently queried fields

### Async/Await
- Use async/await for I/O operations
- Don't mix sync and async code
- Use `asyncio.gather()` for concurrent operations

## Project Plan & Todos

### Phase 1: Foundation (In Progress)
- [x] Project structure setup
- [x] Configuration management
- [x] Database models
- [x] CRUD operations
- [ ] Database migrations
- [ ] Basic tests

### Phase 2: Core Bot Features
- [ ] Telegram bot integration
- [ ] Message handler with typing indicators
- [ ] Command system (/help, /start, /report)
- [ ] Natural language router
- [ ] Confirmation dialogs

### Phase 3: LLM Integration
- [ ] OpenAI-compatible client
- [ ] Tool calling framework
- [ ] Prompt management
- [ ] Rate limit handler
- [ ] Retry mechanism

### Phase 4: Brand Matching
- [ ] Fuzzy matching implementation
- [ ] Alias management
- [ ] Confidence scoring
- [ ] User confirmation system

### Phase 5: Analytics & Reports
- [ ] PDF generator with charts
- [ ] Excel export
- [ ] Financial summaries
- [ ] Report templates

### Phase 6: Automation
- [ ] Payment reminders
- [ ] Scheduler integration
- [ ] Status tracking
- [ ] Cron jobs

### Phase 7: Security & Reliability
- [ ] Audit logging
- [ ] Error handling
- [ ] Rate limiting
- [ ] Input validation

### Phase 8: Docker & Deployment
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] Environment setup
- [ ] Deployment guide

## Key Principles

1. **Test Locally First**: Always test on Mac before Docker deployment
2. **Config-Driven**: All settings in config.yaml and .env
3. **Error Recovery**: Auto-retry with fallback, notify user
4. **Audit Everything**: Log all operations for transparency
5. **IST Timezone**: All dates in Asia/Kolkata
6. **Single User**: Chat ID whitelist only
7. **Tool Calling**: Use LLM tools for all DB operations
8. **Confirm Destructive**: Always ask before delete/update

## Development Notes

- Database path: `./data/vault_guardian.db` (auto-created)
- Config location: `./config/config.yaml`
- Logs location: `./logs/`
- Run locally: `python -m src.main`
- Docker: `docker-compose up -d`
- NVIDIA NIM rate limit: 40 req/min (handle with queue)