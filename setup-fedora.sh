#!/bin/bash
# Vault Guardian - Fedora Server Setup Script
# Run this script on your Fedora server to deploy Vault Guardian

set -e

echo "🛡️  Vault Guardian - Fedora Server Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Please do not run this script as root${NC}"
    echo "Run: bash setup-fedora.sh"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing Docker...${NC}"
    echo ""
    
    sudo dnf install -y dnf-plugins-core
    sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
    sudo dnf install -y docker-ce docker-compose-plugin
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✅ Docker installed successfully${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: You need to logout and login again for Docker permissions to take effect${NC}"
    echo "After logging back in, run this script again"
    exit 0
fi

echo -e "${GREEN}✅ Docker is installed${NC}"
echo ""

# Create deployment directory
DEPLOY_DIR="$HOME/vault-guardian"
if [ -d "$DEPLOY_DIR" ]; then
    echo -e "${YELLOW}Directory $DEPLOY_DIR already exists${NC}"
    read -p "Do you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted"
        exit 0
    fi
else
    mkdir -p "$DEPLOY_DIR"
    echo -e "${GREEN}✅ Created deployment directory: $DEPLOY_DIR${NC}"
fi

cd "$DEPLOY_DIR"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "📝 Creating environment file..."
    echo ""
    
    cat > .env << 'ENVEOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=
ALLOWED_CHAT_ID=

# LLM Configuration
LLM_API_KEY=
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
ENVEOF
    
    echo -e "${YELLOW}⚠️  Please edit .env file with your credentials:${NC}"
    echo "   nano $DEPLOY_DIR/.env"
    echo ""
fi

# Create docker-compose.yml if it doesn't exist
if [ ! -f "docker-compose.yml" ]; then
    echo "📝 Creating docker-compose.yml..."
    
    cat > docker-compose.yml << 'COMPOSEOF'
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
COMPOSEOF
    
    echo -e "${GREEN}✅ Created docker-compose.yml${NC}"
fi

# Check if logged into GHCR
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo ""
    echo "🔐 GitHub Container Registry Login Required"
    echo ""
    echo "1. Go to: https://github.com/settings/tokens"
    echo "2. Create a token with 'read:packages' scope"
    echo "3. Run the following command:"
    echo ""
    echo "   echo \"YOUR_TOKEN\" | docker login ghcr.io -u YOUR_USERNAME --password-stdin"
    echo ""
fi

echo ""
echo "========================================="
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Edit .env with your credentials:"
echo "   nano $DEPLOY_DIR/.env"
echo ""
echo "2. Login to GitHub Container Registry:"
echo "   echo \"YOUR_TOKEN\" | docker login ghcr.io -u YOUR_USERNAME --password-stdin"
echo ""
echo "3. Start the bot:"
echo "   cd $DEPLOY_DIR"
echo "   docker compose up -d"
echo ""
echo "4. View logs:"
echo "   docker compose logs -f vault-guardian"
echo ""
echo "5. Stop the bot:"
echo "   docker compose down"
echo ""
echo "📚 Documentation: $DEPLOY_DIR/docs/DEPLOYMENT.md"
echo "========================================="
