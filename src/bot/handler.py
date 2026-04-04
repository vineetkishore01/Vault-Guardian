"""Telegram bot message handler (Async with Persistence)."""
import asyncio
import json
import logging
import uuid
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from ..config import config
from ..database import db_manager, crud
from ..database.models import utcnow
from ..llm import llm_client, get_tool_definitions
from ..llm.tools import ToolExecutor
from ..utils import (
    format_currency,
    format_date,
    validate_chat_id,
    format_deliverables,
)

logger = logging.getLogger(__name__)


class PersistentConfirmationState:
    """Persistent confirmation state using database."""

    async def add_confirmation(
        self, chat_id: int, operation: str, data: Dict[str, Any]
    ) -> str:
        """Create a new confirmation and store in DB."""
        confirmation_id = str(uuid.uuid4())
        async with db_manager.get_session() as db:
            await crud.PendingConfirmationCRUD.create(
                db=db,
                confirmation_id=confirmation_id,
                chat_id=chat_id,
                operation=operation,
                data=data
            )
        return confirmation_id

    async def get_confirmation(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve confirmation from DB."""
        async with db_manager.get_session() as db:
            conf = await crud.PendingConfirmationCRUD.get(db, confirmation_id)
            if conf:
                return {
                    "chat_id": conf.chat_id,
                    "operation": conf.operation,
                    "data": conf.data
                }
        return None

    async def remove_confirmation(self, confirmation_id: str):
        """Remove confirmation from DB."""
        async with db_manager.get_session() as db:
            await crud.PendingConfirmationCRUD.delete(db, confirmation_id)


# Global confirmation state instance
confirmation_state = PersistentConfirmationState()

# Global caches for optimization
_system_prompt_cache: Optional[str] = None
_tools_cache: Optional[List[Dict[str, Any]]] = None


def get_cached_system_prompt() -> str:
    """Get system prompt from cache or file."""
    global _system_prompt_cache
    if _system_prompt_cache is None:
        from pathlib import Path
        system_prompt_path = Path(__file__).parent.parent.parent / "config" / "prompts" / "system_prompt.txt"
        if system_prompt_path.exists():
            with open(system_prompt_path, 'r') as f:
                _system_prompt_cache = f.read()
        else:
            _system_prompt_cache = "You are a financial tracking assistant. Use the available tools to help the user."
    return _system_prompt_cache


def get_cached_tools() -> List[Dict[str, Any]]:
    """Get tool definitions from cache."""
    global _tools_cache
    if _tools_cache is None:
        _tools_cache = get_tool_definitions()
    return _tools_cache


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not validate_chat_id(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return

    welcome_text = (
        "👋 Welcome to **Vault Guardian**!\n\n"
        "I am your personal financial tracking assistant for Instagram collaborations.\n\n"
        "**What I can do:**\n"
        "• Track earnings (Cash or Barter)\n"
        "• Log expenses (Editing, Travel, etc.)\n"
        "• Generate PDF/Excel reports\n"
        "• Set payment reminders\n\n"
        "Try saying something like: _'Received ₹5000 from Nike for 2 reels today'_"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "🤖 **Vault Guardian Help**\n\n"
        "**Commands:**\n"
        "/start - Start the bot\n"
        "/summary - Get financial summary\n"
        "/report - Generate reports\n"
        "/earnings - List recent earnings\n"
        "/expenses - List recent expenses\n\n"
        "**Examples:**\n"
        "• 'Add earning 50k from Amazon'\n"
        "• 'Spent 2000 for taxi today'\n"
        "• 'Show me my earnings for February'\n"
        "• 'Delete my last Nike entry'"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages (Async)."""
    if not validate_chat_id(update.effective_chat.id):
        await update.message.reply_text("Unauthorized access.")
        return

    user_message = update.message.text
    if not user_message or len(user_message) > config.security.max_message_length:
        await update.message.reply_text("Message too long or empty.")
        return

    await update.message.chat.send_action("typing")
    
    try:
        async with db_manager.get_session() as db:
            executor = ToolExecutor(db)
            system_prompt = get_cached_system_prompt()
            tools = get_cached_tools()

            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]

            llm_response = await llm_client.chat_completion(messages=messages, tools=tools, tool_choice="auto")
            tool_calls = llm_response.get("tool_calls")
            content = llm_response.get("content")

            if not tool_calls:
                if content:
                    await update.message.reply_text(content)
                else:
                    await update.message.reply_text("I'm not sure how to help. Could you rephrase?")
                return

            tasks = []
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                method = getattr(executor, tool_name, None)
                if method:
                    tasks.append(method(**arguments))
            
            if tasks:
                results = await asyncio.gather(*tasks)
                
                confirmation_result = None
                other_results = []
                for result in results:
                    if result.get("requires_confirmation") and not confirmation_result:
                        confirmation_result = result
                    else:
                        other_results.append(result)

                if confirmation_result:
                    conf_type = confirmation_result.get("type", "delete_earning")
                    confirmation_id = await confirmation_state.add_confirmation(
                        chat_id=update.effective_chat.id,
                        operation=conf_type,
                        data=confirmation_result
                    )

                    keyboard = []
                    if conf_type == "brand_match":
                        message = confirmation_result["message"]
                        keyboard = [[
                            InlineKeyboardButton(f"✅ Yes, {confirmation_result['suggested_name']}", callback_data=f"confirm_{confirmation_id}"),
                            InlineKeyboardButton(f"❌ No, keep '{confirmation_result['original_name']}'", callback_data=f"keep_{confirmation_id}")
                        ], [InlineKeyboardButton("🚫 Cancel", callback_data=f"cancel_{confirmation_id}")]]
                    else:
                        earnings_list = "\n".join([f"• {e['brand']}: {format_currency(e['amount'])} ({e['date']})" for e in confirmation_result.get("earnings", [])[:5]])
                        prefix = ""
                        if other_results:
                            prefix = await llm_client.get_completion(
                                prompt=f"Summary of: {json.dumps(other_results, default=str)}",
                                system_prompt=system_prompt
                            ) + "\n\n"
                        message = f"{prefix}⚠️ Confirm Deletion\n\n{confirmation_result['message']}\n\n{earnings_list}\n\nTap 'Confirm' or 'Cancel'."
                        keyboard = [[
                            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{confirmation_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{confirmation_id}")
                        ]]
                    
                    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
                    return

                final_response = await llm_client.get_completion(
                    prompt=f"User: {user_message}\nResults: {json.dumps(results, default=str)}",
                    system_prompt=system_prompt
                )
                await update.message.reply_text(final_response)
            else:
                await update.message.reply_text("I processed your request but found no information.")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {type(e).__name__}\n{str(e)}")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries (Async with Persistence)."""
    query = update.callback_query
    if not validate_chat_id(query.message.chat.id):
        await query.answer("Unauthorized.")
        return
    
    await query.answer()
    data = query.data
    
    if data.startswith("confirm_"):
        confirmation_id = data.replace("confirm_", "")
        confirmation = await confirmation_state.get_confirmation(confirmation_id)
        if confirmation:
            try:
                async with db_manager.get_session() as db:
                    executor = ToolExecutor(db)
                    op = confirmation["operation"]
                    if op == "delete_earning":
                        deleted = 0
                        for earning in confirmation["data"].get("earnings", []):
                            res = await executor.delete_earning(filter={"id": earning["id"]}, confirm=True)
                            if res.get("success"): deleted += 1
                        await query.edit_message_text(f"✅ Deleted {deleted} earning(s)")
                    elif op == "brand_match":
                        res = await executor.add_earning(confirm_brand=True, **confirmation["data"]["data"])
                        await query.edit_message_text(f"✅ {res['message']}" if res["success"] else f"❌ {res['message']}")
                await confirmation_state.remove_confirmation(confirmation_id)
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {str(e)}")
        else:
            await query.edit_message_text("Expired or invalid.")
    
    elif data.startswith("keep_"):
        confirmation_id = data.replace("keep_", "")
        confirmation = await confirmation_state.get_confirmation(confirmation_id)
        if confirmation and confirmation["operation"] == "brand_match":
            try:
                async with db_manager.get_session() as db:
                    executor = ToolExecutor(db)
                    brand_data = confirmation["data"]["data"]
                    brand_data["brand_name"] = confirmation["data"]["original_name"]
                    res = await executor.add_earning(confirm_brand=True, **brand_data)
                    await query.edit_message_text(f"✅ {res['message']}" if res["success"] else f"❌ {res['message']}")
                await confirmation_state.remove_confirmation(confirmation_id)
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {str(e)}")
    
    elif data.startswith("cancel_"):
        await confirmation_state.remove_confirmation(data.replace("cancel_", ""))
        await query.edit_message_text("Operation cancelled.")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary command."""
    await update.message.chat.send_action("typing")
    async with db_manager.get_session() as db:
        executor = ToolExecutor(db)
        res = await executor.get_financial_summary(period="this month")
        if res["success"]:
            await update.message.reply_text(res["message"])
        else:
            await update.message.reply_text(f"❌ Error: {res.get('message')}")


async def earnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /earnings command."""
    async with db_manager.get_session() as db:
        executor = ToolExecutor(db)
        res = await executor.search_earnings(limit=5)
        if res["success"] and res["results"]:
            lines = [f"• {e['brand']}: {format_currency(e['amount'])} ({e['date']})" for e in res["results"]]
            await update.message.reply_text("📊 **Recent Earnings:**\n\n" + "\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("No earnings found.")


async def expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /expenses command."""
    async with db_manager.get_session() as db:
        start_date, end_date = get_date_range("this month")
        expenses = await crud.ExpenseCRUD.get_by_date_range(db, start_date, end_date)
        if expenses:
            lines = [f"• {ex.category.value}: {format_currency(ex.amount)} ({format_date(ex.expense_date)})" for ex in expenses[:10]]
            await update.message.reply_text("💸 **Recent Expenses:**\n\n" + "\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("No expenses found this month.")


def create_application() -> Application:
    """Create and configure the Telegram bot application."""
    application = Application.builder().token(config.telegram.bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("earnings", earnings_command))
    application.add_handler(CommandHandler("expenses", expenses_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application
