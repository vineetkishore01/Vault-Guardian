#!/bin/sh
# Ensure data directories exist and are writable
mkdir -p /app/data /app/logs /app/reports

# Run the main command
exec "$@"
