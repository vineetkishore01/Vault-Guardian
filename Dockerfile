# Stage 1: Build dependencies
FROM python:3.13.3-slim-bookworm AS builder

WORKDIR /app

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production runtime
FROM python:3.13.3-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/vineetkishore01/Vault-Guardian"
LABEL org.opencontainers.image.description="Vault Guardian - AI-powered Telegram bot for finance tracking"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Copy entrypoint script (fixes volume permissions at runtime)
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create non-root user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -M -s /bin/false appuser && \
    chown -R appuser:appgroup /app

# Create runtime directories (will be overridden by volumes, fixed by entrypoint)
RUN mkdir -p /app/data /app/logs /app/reports

# Switch to non-root user
USER appuser

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/app/data/vault_guardian.db \
    TELEGRAM_BOT_TOKEN="" \
    ALLOWED_CHAT_ID="" \
    LLM_API_KEY="" \
    LLM_BASE_URL="https://integrate.api.nvidia.com/v1" \
    LLM_MODEL="z-ai/glm4.7" \
    LLM_TEMPERATURE="0.7" \
    LLM_TOP_P="1.0" \
    LLM_MAX_TOKENS="16384" \
    LLM_STREAM="false" \
    LLM_ENABLE_THINKING="false" \
    LLM_CLEAR_THINKING="true" \
    LLM_TIMEOUT="60" \
    LLM_MAX_RETRIES="3" \
    LLM_RETRY_DELAY="2" \
    TIMEZONE="Asia/Kolkata"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]
