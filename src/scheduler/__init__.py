"""Scheduler module for payment reminders and periodic tasks."""
import asyncio
import logging
from datetime import date, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from ..config import config
from ..database import db_manager, crud
from ..database.models import PaymentStatus
from ..utils import format_currency, format_date, get_ist_today

logging.basicConfig(
    level=getattr(logging, config.security.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler for payment reminders and periodic tasks."""
    
    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.bot: Optional[Bot] = None
    
    def set_bot(self, bot: Bot):
        """Set the Telegram bot instance."""
        self.bot = bot
    
    async def check_payment_reminders(self):
        """Check and send payment reminders."""
        if not self.bot:
            logger.warning("Bot not set, skipping reminder check")
            return
        
        today = get_ist_today()
        
        try:
            with db_manager.get_session() as db:
                pending_reminders = crud.PaymentReminderCRUD.get_pending_reminders(db, today)
                
                for reminder in pending_reminders:
                    earning = crud.EarningCRUD.get_by_id(db, reminder.earning_id)
                    
                    if not earning:
                        logger.warning(f"Earning {reminder.earning_id} not found for reminder {reminder.id}")
                        continue
                    
                    if earning.status == PaymentStatus.RECEIVED:
                        crud.PaymentReminderCRUD.update_status(db, reminder.id, "acknowledged")
                        continue
                    
                    message = (
                        f"⏰ Payment Reminder\n\n"
                        f"Brand: {earning.brand_name}\n"
                        f"Amount: {format_currency(earning.amount_earned)}\n"
                        f"Due Date: {format_date(reminder.reminder_date)}\n"
                        f"Status: {earning.status.value.title()}\n\n"
                        f"Please follow up on this payment."
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=config.telegram.allowed_chat_id,
                            text=message
                        )
                        
                        crud.PaymentReminderCRUD.update_status(db, reminder.id, "sent")
                        logger.info(f"Sent reminder for earning {earning.id}")
                    
                    except Exception as e:
                        logger.error(f"Failed to send reminder: {e}")
        
        except Exception as e:
            logger.error(f"Error checking payment reminders: {e}")
    
    async def check_overdue_payments(self):
        """Check for overdue payments."""
        if not self.bot:
            return

        today = get_ist_today()
        overdue_threshold = today - timedelta(days=30)

        try:
            with db_manager.get_session() as db:
                # Query overdue earnings directly at the database level
                overdue_earnings = db.query(crud.Earning).filter(
                    crud.Earning.status == PaymentStatus.PENDING,
                    crud.Earning.entry_date < overdue_threshold
                ).all()

                overdue_count = len(overdue_earnings)

                if overdue_count > 0:
                    message = (
                        f"⚠️ Overdue Payment Alert\n\n"
                        f"You have {overdue_count} overdue payment(s).\n"
                        f"Please follow up with the brands.\n\n"
                        f"Use /earnings to view all pending payments."
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=config.telegram.allowed_chat_id,
                            text=message
                        )
                    except Exception as e:
                        logger.error(f"Failed to send overdue alert: {e}")
        
        except Exception as e:
            logger.error(f"Error checking overdue payments: {e}")
    
    async def daily_summary(self):
        """Send daily financial summary."""
        if not self.bot:
            return
        
        today = get_ist_today()
        
        try:
            with db_manager.get_session() as db:
                from ..llm.tools import ToolExecutor
                executor = ToolExecutor(db)
                
                result = await executor.get_financial_summary(
                    period="today",
                    include_expenses=True
                )
                
                if result["success"]:
                    message = (
                        f"📊 Daily Summary - {format_date(today)}\n\n"
                        f"💰 Earnings: {format_currency(result['total_earnings'])}\n"
                        f"💸 Expenses: {format_currency(result['total_expenses'])}\n"
                        f"📈 Net: {format_currency(result['net_income'])}\n\n"
                        f"📦 Deliverables:\n"
                        f"  • Reels: {result['deliverables']['reels']}\n"
                        f"  • Stories: {result['deliverables']['stories']}\n"
                        f"  • Posts: {result['deliverables']['posts']}\n\n"
                        f"🤝 Deals: {result.get('cash_deals', 0)} cash, {result.get('barter_deals', 0)} barter"
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=config.telegram.allowed_chat_id,
                            text=message
                        )
                    except Exception as e:
                        logger.error(f"Failed to send daily summary: {e}")
        
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    async def auto_create_reminders(self):
        """Automatically create reminders for new earnings."""
        today = get_ist_today()
        
        try:
            with db_manager.get_session() as db:
                recent_earnings = crud.EarningCRUD.search(
                    db=db,
                    status=PaymentStatus.PENDING,
                    limit=100
                )
                
                for earning in recent_earnings:
                    existing_reminders = crud.PaymentReminderCRUD.get_pending_reminders(
                        db, 
                        earning.entry_date + timedelta(days=config.reminders.default_reminder_days)
                    )
                    
                    has_reminder = any(
                        r.earning_id == earning.id 
                        for r in existing_reminders
                    )
                    
                    if not has_reminder:
                        reminder_date = earning.entry_date + timedelta(
                            days=config.reminders.default_reminder_days
                        )
                        
                        crud.PaymentReminderCRUD.create(
                            db=db,
                            earning_id=earning.id,
                            reminder_date=reminder_date,
                            message=f"Payment reminder: {format_currency(earning.amount_earned)} from {earning.brand_name}"
                        )
                        
                        logger.info(f"Created reminder for earning {earning.id}")
        
        except Exception as e:
            logger.error(f"Error auto-creating reminders: {e}")
    
    def start(self):
        """Start the scheduler."""
        if not config.reminders.enabled:
            logger.info("Reminders disabled, scheduler not starting")
            return
        
        try:
            cron_parts = config.reminders.check_interval.split()
            if len(cron_parts) == 5:
                self.scheduler.add_job(
                    self.check_payment_reminders,
                    CronTrigger(
                        minute=cron_parts[0],
                        hour=cron_parts[1],
                        day=cron_parts[2],
                        month=cron_parts[3],
                        day_of_week=cron_parts[4]
                    ),
                    id='check_payment_reminders',
                    replace_existing=True
                )
            else:
                logger.warning(f"Invalid cron expression: {config.reminders.check_interval}")
            
            self.scheduler.add_job(
                self.check_overdue_payments,
                CronTrigger(hour=10, minute=0),
                id='check_overdue_payments',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self.daily_summary,
                CronTrigger(hour=20, minute=0),
                id='daily_summary',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self.auto_create_reminders,
                CronTrigger(hour=0, minute=0),
                id='auto_create_reminders',
                replace_existing=True
            )
            
            self.scheduler.start()
            logger.info("Scheduler started successfully")
        
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown")


# Global scheduler instance
reminder_scheduler = ReminderScheduler()
