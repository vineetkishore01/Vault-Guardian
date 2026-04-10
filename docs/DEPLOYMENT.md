# 🚀 Vault Guardian — Deployment Guide

## Quick Start

```bash
# Pull the image from GitHub Container Registry
docker pull ghcr.io/vineetkishore01/vault-guardian:latest

# Create deployment directory
mkdir -p ~/vault-guardian && cd ~/vault-guardian
```

---

## 📦 Docker Image

**URL:** `ghcr.io/vineetkishore01/vault-guardian:latest`

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable build from main branch |
| `v1.x.x` | Specific version tags |
| `sha-<commit>` | Build from specific commit |

The image is built automatically on every push to `main` via GitHub Actions.

---

## 🔧 Deploy on Fedora Server

### Step 1: Create Environment File

```bash
cd ~/vault-guardian
cat > .env << 'EOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_ID=your_telegram_chat_id_here

# LLM Configuration (NVIDIA NIM)
LLM_API_KEY=your_nvidia_api_key_here
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=z-ai/glm4.7
LLM_TEMPERATURE=0.7
LLM_TOP_P=1.0
LLM_MAX_TOKENS=4096
LLM_STREAM=false
LLM_ENABLE_THINKING=false
LLM_CLEAR_THINKING=true
LLM_TIMEOUT=120
LLM_MAX_RETRIES=3
LLM_RETRY_DELAY=2

# Database & Timezone
DATABASE_PATH=/app/data/vault_guardian.db
TIMEZONE=Asia/Kolkata
EOF

chmod 600 .env
```

**Where to get credentials:**
- `TELEGRAM_BOT_TOKEN`: Telegram → `@BotFather` → `/newbot`
- `ALLOWED_CHAT_ID`: Message your bot → Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` → find `"chat":{"id":123456}`
- `LLM_API_KEY`: https://build.nvidia.com

### Step 2: Create Docker Compose File

```bash
cat > docker-compose.yml << 'EOF'
services:
  vault-guardian:
    image: ghcr.io/vineetkishore01/vault-guardian:latest
    container_name: vault-guardian
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - vault-data:/app/data
      - vault-logs:/app/logs
      - vault-reports:/app/reports
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  vault-data:
    driver: local
  vault-logs:
    driver: local
  vault-reports:
    driver: local
EOF
```

### Step 3: Login to GHCR (Private Repos Only)

```bash
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u vineetkishore01 --password-stdin
```

### Step 4: Deploy

```bash
docker compose up -d
docker compose logs -f
```

---

## 🔐 Security

```bash
# Restrict .env file permissions
chmod 600 .env

# Back up data regularly
docker cp vault-guardian:/app/data/ ./backup/
```

---

## 🔄 Updating

```bash
# Check for updates
docker compose pull

# Deploy update (zero-downtime)
docker compose up -d --force-recreate

# Rollback to specific version
# Edit docker-compose.yml image tag, then:
docker compose up -d
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Container exits immediately | `docker compose logs` for error details |
| Can't connect to Telegram | Verify `TELEGRAM_BOT_TOKEN` is correct |
| LLM errors | Check `LLM_API_KEY` and `LLM_BASE_URL` |
| Permission denied | Ensure volumes are owned by UID 1000 |
| Out of memory | Increase memory limit in docker-compose.yml |
| Slow first response | Normal — model cold-start on NVIDIA. Subsequent responses are 5-25s |

### View Logs

```bash
# Recent logs
docker compose logs --tail=100 vault-guardian

# Live logs
docker compose logs -f
```

### Access Container Shell

```bash
docker exec -it vault-guardian sh
```

### Check Database

```bash
docker cp vault-guardian:/app/data/vault_guardian.db ./vault_guardian.db
sqlite3 vault_guardian.db ".tables"
```

---

## 📊 Monitoring

```bash
# Resource usage
docker stats vault-guardian

# Log rotation: 10MB max, 3 files (configured in docker-compose.yml)
```

---

## 📋 Commands Reference

| Task | Command |
|------|---------|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Logs | `docker compose logs -f` |
| Update | `docker compose pull && docker compose up -d` |
| Shell | `docker exec -it vault-guardian sh` |
| Backup | `docker cp vault-guardian:/app/data/ ./backup/` |
