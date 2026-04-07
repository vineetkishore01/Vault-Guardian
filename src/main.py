"""Main entry point for Vault Guardian."""
import asyncio
import logging
import os
import sys
from pathlib import Path

from src.config import config
from src.database import db_manager
from src.bot import run_bot
from src.scheduler import reminder_scheduler

# ── Duplicate instance guard ──
PID_FILE = Path(".vault_guardian.pid")

def _check_duplicate():
    """Kill any existing bot instance, or fail if PID file is stale."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # Check if process exists
            logger.info(f"Another instance running (PID {old_pid}), killing it...")
            os.kill(old_pid, 9)  # SIGKILL — instant death
            import time
            time.sleep(3)  # Let Telegram release the polling lock
        except (ProcessLookupError, ValueError):
            pass  # Stale PID file, safe to remove
        except PermissionError:
            logger.warning(f"Cannot kill existing instance (PID {old_pid}), starting anyway")
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))

def _cleanup_pid():
    PID_FILE.unlink(missing_ok=True)
# ──────────────────────────────

# Log to both file and stdout with immediate flushing
log_file = Path("logs/bot.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

# Force unbuffered logging
import io
class UnbufferedFileHandler(logging.StreamHandler):
    """Stream handler that writes to file with immediate flush."""
    def __init__(self, filename):
        self._filename = filename
        super().__init__(open(filename, 'a', buffering=1))  # line-buffered

    def emit(self, record):
        try:
            super().emit(record)
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=getattr(logging, config.security.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        UnbufferedFileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories."""
    directories = [
        Path("./data"),
        Path("./logs"),
        Path("./reports"),
        Path("./config/prompts")
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


async def send_startup_notification():
    """Send notification when bot starts."""
    if not config.bot.notify_on_restart:
        return

    try:
        from telegram import Bot
        async with Bot(token=config.telegram.bot_token) as bot:
            message = (
                "🚀 Vault Guardian is now online!\n\n"
                "All systems operational.\n"
                "Ready to track your finances."
            )

            await bot.send_message(
                chat_id=config.telegram.allowed_chat_id,
                text=message
            )

            logger.info("Startup notification sent")

    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")


async def main():
    """Main entry point."""
    _check_duplicate()

    logger.info("=" * 50)
    logger.info("Starting Vault Guardian")
    logger.info("=" * 50)
    
    setup_directories()
    
    logger.info("Initializing database...")
    try:
        async with db_manager.get_session():
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    logger.info("Starting scheduler...")
    reminder_scheduler.start()
    
    logger.info("Sending startup notification...")
    await send_startup_notification()
    
    logger.info("Starting bot...")
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        reminder_scheduler.shutdown()
        db_manager.close()
        _cleanup_pid()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
