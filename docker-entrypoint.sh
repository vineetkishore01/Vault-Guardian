#!/bin/sh
# Ensure data directories exist and are writable
mkdir -p /app/data /app/logs /app/reports
chown -R appuser:appgroup /app/data /app/logs /app/reports 2>/dev/null || true

# Run the main command
exec "$@"
