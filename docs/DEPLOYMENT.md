# 🚀 Vault Guardian - Production Deployment Guide

## Overview

This guide covers deploying Vault Guardian to production using Docker images from GitHub Container Registry (GHCR).

---

## 📦 Docker Image

**Image URL:** `ghcr.io/vineetkishore01/vault-guardian:latest`

The image is built automatically on every push to `main` branch using GitHub Actions.

### Available Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable build from main branch |
| `v1.x.x` | Specific version tags |
| `sha-<commit>` | Build from specific commit |

---

## 🔧 Deployment on Fedora Server

### Prerequisites

```bash
# Install Docker Engine
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### Step 1: Create Deployment Directory

```bash
mkdir -p ~/vault-guardian
cd ~/vault-guardian
```

### Step 2: Create Environment File

```bash
cat > .env << 'EOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_CHAT_ID=your_telegram_chat_id_here

# LLM Configuration
LLM_API_KEY=your_nvidia_api_key_here
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=z-ai/glm4.7
LLM_TEMPERATURE=0.7
LLM_TOP_P=1.0
LLM_MAX_TOKENS=16384
LLM_STREAM=false
LLM_ENABLE_THINKING=false
LLM_CLEAR_THINKING=true
LLM_TIMEOUT=60
LLM_MAX_RETRIES=3
LLM_RETRY_DELAY=2

# Database & Timezone
DATABASE_PATH=/app/data/vault_guardian.db
TIMEZONE=Asia/Kolkata
EOF

# Edit with your actual values
nano .env
```

### Step 3: Create Docker Compose File

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

### Step 4: Login to GHCR

```bash
# Create a personal access token with 'read:packages' scope
# https://github.com/settings/tokens

echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### Step 5: Deploy

```bash
# Pull and start the container
docker compose up -d

# Check logs
docker compose logs -f vault-guardian

# Check status
docker compose ps
```

---

## 🔐 Security Best Practices

### 1. Protect Your Environment Variables

```bash
# Set restrictive permissions on .env file
chmod 600 .env
```

### 2. Use Docker Secrets (Advanced)

For production, consider using Docker secrets instead of .env files:

```bash
# Create secret
echo "your_bot_token" | docker secret create telegram_token -

# Use in compose file
services:
  vault-guardian:
    secrets:
      - telegram_token
```

### 3. Network Isolation

Run the container on an isolated Docker network:

```bash
docker network create vault-network
docker compose up -d --network vault-network
```

### 4. Regular Backups

```bash
#!/bin/bash
# backup.sh - Add to crontab for automated backups
BACKUP_DIR="/opt/backups/vault-guardian"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

docker run --rm \
  -v vault-guardian_vault-data:/data:ro \
  -v "$BACKUP_DIR:/backup" \
  alpine tar czf "/backup/data_$TIMESTAMP.tar.gz" -C /data .

# Keep only last 30 days
find "$BACKUP_DIR" -name "data_*.tar.gz" -mtime +30 -delete
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /opt/scripts/backup.sh
```

---

## 🔄 Updating

### Check for Updates

```bash
# Pull latest image
docker compose pull

# Check if new image was pulled
docker compose images
```

### Deploy Update

```bash
# Stop, recreate, restart
docker compose down
docker compose up -d

# Or zero-downtime update
docker compose pull
docker compose up -d --force-recreate
```

### Rollback to Previous Version

```bash
# Use specific version tag
sed -i 's|ghcr.io/vineetkishore01/vault-guardian:latest|ghcr.io/vineetkishore01/vault-guardian:v1.2.3|' docker-compose.yml
docker compose up -d
```

---

## 🐛 Troubleshooting

### View Logs

```bash
# Recent logs
docker compose logs --tail=100 vault-guardian

# Follow live logs
docker compose logs -f vault-guardian
```

### Access Container Shell

```bash
docker exec -it vault-guardian sh
```

### Check Container Health

```bash
docker inspect --format='{{.State.Health.Status}}' vault-guardian
```

### Database Access

```bash
# Copy database to local for inspection
docker cp vault-guardian:/app/data/vault_guardian.db ./vault_guardian.db

# Open with SQLite
sqlite3 vault_guardian.db
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Container exits immediately | Check logs: `docker compose logs` |
| Can't connect to Telegram | Verify `TELEGRAM_BOT_TOKEN` is correct |
| LLM errors | Check `LLM_API_KEY` and `LLM_BASE_URL` |
| Permission denied | Ensure volumes are owned by UID 1000 |
| Out of memory | Increase memory limit in docker-compose.yml |

---

## 📊 Monitoring

### Resource Usage

```bash
# Real-time stats
docker stats vault-guardian

# One-time snapshot
docker stats --no-stream vault-guardian
```

### Log Rotation

Logs are automatically rotated (10MB max, 3 files). Configure in `docker-compose.yml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "5"
```

---

## 🆘 Support

- **Documentation:** See [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- **Issues:** https://github.com/vineetkishore01/Vault-Guardian/issues
- **Discussions:** https://github.com/vineetkishore01/Vault-Guardian/discussions
