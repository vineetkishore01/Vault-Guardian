"""Telegram bot message handler (Async with Persistence)."""
import asyncio
import json
import logging
import time
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
    get_date_range,
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
        "/help - Show this help\n"
        "/clear - Clear conversation history\n"
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


# Global conversation history cache: {chat_id: [messages]}
_chat_history: Dict[int, List[Dict[str, str]]] = {}
# Max messages to keep per chat (prevents context overflow)
_MAX_HISTORY = 20


def _get_history(chat_id: int) -> List[Dict[str, str]]:
    """Get conversation history for a chat."""
    return _chat_history.setdefault(chat_id, [])


def _append_history(chat_id: int, role: str, content: str):
    """Append to history, trimming if needed."""
    history = _get_history(chat_id)
    history.append({"role": role, "content": content})
    # Trim oldest entries to prevent context overflow
    while len(history) > _MAX_HISTORY:
        history.pop(0)


def _clear_history(chat_id: int):
    """Clear conversation history for a chat."""
    _chat_history.pop(chat_id, None)


def _build_summary_from_results(results: List[Dict[str, Any]]) -> str:
    """Build a response summary from actual tool results.
    This prevents the LLM from hallucinating entries that weren't saved."""
    added = []
    updated = []
    deleted_count = 0
    failed = []

    for r in results:
        if not r.get("success"):
            if r.get("requires_confirmation"):
                return ""  # Let handler deal with confirmation flow
            failed.append(r.get("message", "Operation failed"))
            continue

        msg = r.get("message", "")
        if "Added earning" in msg:
            # Extract brand and amount for cleaner display
            added.append(msg)
        elif "Added expense" in msg:
            added.append(msg)
        elif "Updated earning" in msg:
            updated.append(msg)
        elif "Deleted" in msg:
            # Extract count from message like "Deleted 1 earning" or "Deleted 2 earning(s)"
            import re
            m = re.search(r"Deleted (\d+)", msg)
            deleted_count += int(m.group(1)) if m else 1
        elif "Found" in msg or "summary" in msg.lower():
            return ""  # Query result — let LLM handle it

    parts = []
    if added:
        if len(added) == 1:
            parts.append(f"✅ {added[0]}")
        else:
            parts.append(f"✅ Added {len(added)} entries:\n" + "\n".join(f"• {a}" for a in added))
    if updated:
        parts.append(f"✏️ Updated {len(updated)}: " + ", ".join(updated))
    if deleted_count:
        parts.append(f"🗑️ Deleted {deleted_count} earning(s)")
    if failed:
        parts.append("❌ " + "\n".join(failed))

    return "\n\n".join(parts) if parts else "✅ Done."


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language messages (Async)."""
    chat_id = update.effective_chat.id
    user_message = update.message.text
    logger.info(f"📥 User message (chat_id={chat_id}): {user_message[:100]}")

    if not validate_chat_id(chat_id):
        logger.warning(f"Unauthorized chat_id: {chat_id}")
        await update.message.reply_text("Unauthorized access.")
        return

    if not user_message or len(user_message) > config.security.max_message_length:
        await update.message.reply_text("Message too long or empty.")
        return

    # Handle /clear command to reset history
    if user_message.strip().lower() == "/clear":
        _clear_history(update.effective_chat.id)
        await update.message.reply_text("🧹 Conversation history cleared.")
        return

    turn_start = time.monotonic()

    # Start persistent typing indicator — refreshes every 4 seconds
    async def _keep_typing():
        try:
            while True:
                await update.message.chat.send_action("typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    typing_task = asyncio.create_task(_keep_typing())

    async def _stop_typing():
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    # ── ChatLog variables ──
    from ..chatlog import chat_logger
    log_llm_content = None
    log_tool_calls = None
    log_tool_results = []
    log_response = None
    log_error = None
    # ────────────────────────

    try:
        async with db_manager.get_session() as db:
            executor = ToolExecutor(db)
            system_prompt = get_cached_system_prompt()
            tools = get_cached_tools()

            # Build messages: system prompt + conversation history + current message
            chat_id = update.effective_chat.id
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(_get_history(chat_id))
            messages.append({"role": "user", "content": user_message})

            # ── Multi-tool loop: keep calling LLM until no more tool calls ──
            max_iterations = 5  # Safety limit to prevent infinite loops
            iteration = 0
            confirmation_result = None
            tool_error = None
            all_results = []
            tools_called = set()  # Track all tool names across iterations

            while iteration < max_iterations:
                iteration += 1

                llm_response = await llm_client.chat_completion(
                    messages=messages, tools=tools, tool_choice="auto"
                )
                tool_calls = llm_response.get("tool_calls")
                content = llm_response.get("content")

                # Log LLM response details
                if tool_calls:
                    tool_names = [tc.function.name for tc in tool_calls]
                    logger.info(f"🤖 LLM called tools: {', '.join(tool_names)}")
                elif content:
                    content_preview = content[:150] + "..." if len(content) > 150 else content
                    logger.info(f"🤖 LLM responded: {content_preview}")

                if not tool_calls:
                    # No more tool calls — respond with LLM's text
                    log_llm_content = content

                    # For mutation tools, always use tool-based summary (never trust LLM's text)
                    # For query tools, let the LLM respond naturally
                    mutation_tools = {"add_earning", "add_expense", "delete_earning", "update_earning"}
                    had_mutations = bool(tools_called & mutation_tools)

                    if had_mutations and all_results:
                        # Mutation tools executed — build summary from actual results
                        summary = _build_summary_from_results(all_results)
                        if content and summary:
                            # LLM provided content AND we have mutation results.
                            # Use the tool-based summary to prevent hallucination.
                            log_response = summary
                        elif summary:
                            log_response = summary
                        elif content:
                            log_response = content
                        else:
                            log_response = "✅ Done."
                    elif content:
                        log_response = content
                    elif all_results:
                        # Query tools executed but LLM didn't generate response
                        log_response = _build_summary_from_results(all_results) or "✅ Done."
                    else:
                        log_response = "I'm not sure how to help. Could you rephrase?"

                    logger.info(f"📤 Bot response: {log_response[:150]}{'...' if len(log_response) > 150 else ''}")

                    await _stop_typing()
                    await update.message.reply_text(log_response)

                    # Save to history
                    _append_history(chat_id, "user", user_message)
                    _append_history(chat_id, "assistant", log_response)

                    chat_logger.record_turn(
                        user_message, log_llm_content, log_tool_calls,
                        log_tool_results, log_response,
                        int((time.monotonic() - turn_start) * 1000), log_error
                    )
                    return

                # Log tool calls from first iteration only (for chatlog)
                if log_tool_calls is None:
                    log_tool_calls = tool_calls

                # Execute each tool call sequentially
                batch_results = []
                stop_for_confirmation = False

                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    tools_called.add(tool_name)
                    arguments = json.loads(tool_call.function.arguments)

                    # Security: strip confirmation/confirm_brand from LLM args
                    arguments.pop("confirm", None)
                    arguments.pop("confirm_brand", None)

                    method = getattr(executor, tool_name, None)
                    if not method:
                        tool_error = {"tool": tool_name, "error": f"Unknown tool: {tool_name}"}
                        logger.error(f"LLM called unknown tool: {tool_name}")
                        break

                    # Log tool call with arguments (redact sensitive fields)
                    safe_args = {k: str(v)[:50] for k, v in arguments.items()}
                    logger.info(f"🔧 LLM calling: {tool_name}({json.dumps(safe_args)})")

                    try:
                        result = await method(**arguments)
                        batch_results.append(result)
                        log_tool_results.append(result)

                        # Log tool execution result
                        if result.get("success"):
                            logger.info(f"✅ Tool '{tool_name}': {result.get('message', 'OK')[:100]}")
                        else:
                            logger.warning(f"⚠️ Tool '{tool_name}' failed: {result.get('message', 'Unknown error')[:100]}")

                        # Send Telegram notification for data mutations
                        mutation_tools = {"add_earning", "add_expense", "update_earning", "delete_earning"}
                        if tool_name in mutation_tools:
                            status_emoji = "✅" if result.get("success") else "❌"
                            notify_msg = f"{status_emoji} **{tool_name.replace('_', ' ').title()}**\n"
                            notify_msg += f"Result: {result.get('message', 'No details')}"
                            try:
                                await update.message.reply_text(notify_msg, parse_mode="Markdown")
                            except Exception:
                                pass  # Don't fail the turn if notification fails

                        if result.get("requires_confirmation"):
                            confirmation_result = result
                            stop_for_confirmation = True
                            break
                    except Exception as e:
                        tool_error = {"tool": tool_name, "error": str(e)}
                        logger.error(f"Tool '{tool_name}' failed: {e}", exc_info=True)
                        break

                all_results.extend(batch_results)

                if stop_for_confirmation or tool_error:
                    break

                # Append the assistant's tool calls and tool results to the messages
                assistant_msg = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                }
                messages.append(assistant_msg)

                # Append tool results in the format the LLM expects
                for i, result in enumerate(batch_results):
                    tool_call_id = tool_calls[i].id if i < len(tool_calls) else ""
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result, default=str)
                    })

                # Loop back — LLM decides if more tools are needed

            # ── Handle tool execution error ──
            if tool_error:
                success_count = len([r for r in all_results if r.get("success")])
                error_msg = (
                    f"❌ Error with '{tool_error['tool']}'\n\n"
                    f"{'✅ ' + str(success_count) + ' step(s) completed successfully.' if success_count else ''}"
                    f"{'❌ ' + tool_error['error'] if tool_error else ''}"
                )
                log_response = error_msg
                log_error = tool_error["error"]
                await _stop_typing()
                await update.message.reply_text(error_msg)
                _append_history(chat_id, "user", user_message)
                _append_history(chat_id, "assistant", log_response)
                chat_logger.record_turn(
                    user_message, log_llm_content, log_tool_calls,
                    log_tool_results, log_response,
                    int((time.monotonic() - turn_start) * 1000), log_error
                )
                return

            # ── Handle confirmation dialog ──
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
                    earnings_list = "\n".join(
                        [f"• {e['brand']}: {format_currency(e['amount'])} ({e['date']})"
                         for e in confirmation_result.get("earnings", [])[:5]])
                    prefix = ""
                    other_results = [r for r in all_results if r != confirmation_result]
                    if other_results:
                        prefix = await llm_client.get_completion(
                            prompt=f"Summary of previous successful steps: {json.dumps(other_results, default=str)}",
                            system_prompt="Respond with a brief, user-friendly summary only."
                        ) + "\n\n"
                    message = (f"{prefix}⚠️ Confirm Deletion\n\n"
                               f"{confirmation_result['message']}\n\n{earnings_list}\n\n"
                               f"Tap 'Confirm' or 'Cancel'.")
                    keyboard = [[
                        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{confirmation_id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{confirmation_id}")
                    ]]

                log_response = message
                await _stop_typing()
                await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
                _append_history(chat_id, "user", user_message)
                _append_history(chat_id, "assistant", log_response)
                chat_logger.record_turn(
                    user_message, log_llm_content, log_tool_calls,
                    log_tool_results, log_response,
                    int((time.monotonic() - turn_start) * 1000), log_error
                )
                return

            # ── Should not reach here — safety net ──
            log_response = "I processed your request."
            await _stop_typing()
            await update.message.reply_text(log_response)
            _append_history(chat_id, "user", user_message)
            _append_history(chat_id, "assistant", log_response)
            chat_logger.record_turn(
                user_message, log_llm_content, log_tool_calls,
                log_tool_results, log_response,
                int((time.monotonic() - turn_start) * 1000), log_error
            )

    except Exception as e:
        log_error = str(e)
        logger.error(f"❌ Error processing message: {e}", exc_info=True)
        await _stop_typing()
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            log_response = "⏳ The AI service took too long to respond. Please try again."
            logger.warning("⏳ LLM timeout — responding with error message")
            await update.message.reply_text(log_response)
        else:
            log_response = "❌ Something went wrong. Please try rephrasing your request."
            await update.message.reply_text(log_response)
        chat_logger.record_turn(
            user_message, log_llm_content, log_tool_calls,
            log_tool_results, log_response,
            int((time.monotonic() - turn_start) * 1000), log_error
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries (Async with Persistence)."""
    query = update.callback_query
    user_chat_id = query.message.chat.id
    if not validate_chat_id(user_chat_id):
        await query.answer("Unauthorized.")
        return
    
    await query.answer()
    data = query.data
    
    if data.startswith("confirm_"):
        confirmation_id = data.replace("confirm_", "")
        confirmation = await confirmation_state.get_confirmation(confirmation_id)
        if confirmation:
            # Fix: Verify chat_id to prevent hijacking
            if confirmation["chat_id"] != user_chat_id:
                await query.edit_message_text("❌ Unauthorized: You did not initiate this action.")
                return

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
                logger.error(f"Error processing confirmation: {e}", exc_info=True)
                await query.edit_message_text("❌ An error occurred while processing. Please try again.")
        else:
            await query.edit_message_text("Expired or invalid.")
    
    elif data.startswith("keep_"):
        confirmation_id = data.replace("keep_", "")
        confirmation = await confirmation_state.get_confirmation(confirmation_id)
        if confirmation and confirmation["operation"] == "brand_match":
            # Fix: Verify chat_id to prevent hijacking
            if confirmation["chat_id"] != user_chat_id:
                await query.edit_message_text("❌ Unauthorized: You did not initiate this action.")
                return

            try:
                async with db_manager.get_session() as db:
                    executor = ToolExecutor(db)
                    brand_data = confirmation["data"]["data"]
                    brand_data["brand_name"] = confirmation["data"]["original_name"]
                    res = await executor.add_earning(confirm_brand=True, **brand_data)
                    await query.edit_message_text(f"✅ {res['message']}" if res["success"] else f"❌ {res['message']}")
                await confirmation_state.remove_confirmation(confirmation_id)
            except Exception as e:
                logger.error(f"Error processing confirmation: {e}", exc_info=True)
                await query.edit_message_text("❌ An error occurred while processing. Please try again.")
    
    elif data.startswith("cancel_"):
        confirmation_id = data.replace("cancel_", "")
        confirmation = await confirmation_state.get_confirmation(confirmation_id)
        if confirmation and confirmation["chat_id"] != user_chat_id:
             await query.answer("Unauthorized.", show_alert=True)
             return

        await confirmation_state.remove_confirmation(confirmation_id)
        await query.edit_message_text("Operation cancelled.")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary command."""
    await update.message.chat.send_action("typing")
    async with db_manager.get_session() as db:
        executor = ToolExecutor(db)
        res = await executor.get_financial_summary(period="this month")
        if res["success"]:
            logger.info(
                f"📊 /summary result: earnings={res['total_earnings']}, "
                f"expenses={res['total_expenses']}, net={res['net_income']}, "
                f"period={res.get('start_date')} to {res.get('end_date')}"
            )
            await update.message.reply_text(res["message"])
        else:
            await update.message.reply_text(f"❌ Error: {res.get('message')}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command — generates PDF report for current month."""
    chat_id = update.effective_chat.id
    if not validate_chat_id(chat_id):
        await update.message.reply_text("Unauthorized access.")
        return

    await update.message.chat.send_action("typing")
    logger.info(f"📥 /report command (chat_id={chat_id})")

    async with db_manager.get_session() as db:
        executor = ToolExecutor(db)
        result = await executor.generate_report(format="pdf", period="this month", include_charts=True)

        if result.get("success") and result.get("path"):
            from pathlib import Path
            rp = Path(result["path"])
            if rp.exists():
                await update.message.reply_document(
                    document=open(rp, 'rb'),
                    caption=f"📊 Monthly Report — {rp.name}",
                    filename=rp.name
                )
                logger.info(f"📎 Report sent via /report: {rp.name}")
            else:
                await update.message.reply_text(f"❌ Report file not found: {result['path']}")
        else:
            await update.message.reply_text(f"❌ Failed to generate report: {result.get('message', 'Unknown error')}")


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
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("earnings", earnings_command))
    application.add_handler(CommandHandler("expenses", expenses_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


async def run_bot():
    """Run the Telegram bot polling loop."""
    application = create_application()
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    try:
        # Keep running until cancelled
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
