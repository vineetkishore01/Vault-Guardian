"""ChatLog module — records every conversation turn for analysis.

Each turn is a JSON entry:
  {
    "turn_id": 1,
    "timestamp": "2026-04-06T14:00:00.000Z",
    "user_message": "...",
    "llm_decision": "tool_call" | "text" | "error",
    "tool_calls": [...],
    "tool_results": [...],
    "final_response": "...",
    "duration_ms": 1234
  }

Written to logs/chatlog/YYYY-MM-DD.jsonl (one line per turn).
A companion .html viewer is auto-generated for easy browsing.
"""
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ChatLog:
    """Records and retrieves conversation turns."""

    def __init__(self, log_dir: str = None):
        """Initialize chat logger."""
        self.log_dir = log_dir or "./logs/chatlog"
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        self.session_id = str(uuid.uuid4())[:8]
        self._today_file = None

    @property
    def _log_path(self) -> str:
        """Today's log file path."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{today}.jsonl")

    def _write_entry(self, entry: Dict[str, Any]):
        """Append a single turn entry to today's JSONL file."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write chatlog entry: {e}")

    def record_turn(
        self,
        user_message: str,
        llm_content: Optional[str],
        tool_calls: Optional[List[Dict[str, Any]]],
        tool_results: Optional[List[Dict[str, Any]]],
        final_response: str,
        duration_ms: int,
        error: Optional[str] = None,
    ):
        """Record a complete conversation turn."""
        try:
            self._record_turn_safe(user_message, llm_content, tool_calls,
                                   tool_results, final_response, duration_ms, error)
        except Exception as e:
            # Never let chatlog crashes affect the bot
            logger.error(f"ChatLog error (bot continues): {e}")

    def _record_turn_safe(
        self,
        user_message: str,
        llm_content: Optional[str],
        tool_calls: Optional[List[Dict[str, Any]]],
        tool_results: Optional[List[Dict[str, Any]]],
        final_response: str,
        duration_ms: int,
        error: Optional[str] = None,
    ):
        """Record a complete conversation turn.

        Args:
            user_message: What the user typed
            llm_content: Raw text content from LLM (may be None if tool calls)
            tool_calls: List of tool call objects the LLM decided to make
            tool_results: List of results returned by each tool
            final_response: What was actually sent back to the user
            duration_ms: Total time from user message to response
            error: Error message if anything went wrong
        """
        # Determine LLM's decision type
        if error:
            llm_decision = "error"
        elif tool_calls:
            llm_decision = "tool_call"
        elif llm_content:
            llm_decision = "text"
        else:
            llm_decision = "no_response"

        # Sanitize tool_calls for storage (remove raw tool definitions, keep only calls)
        sanitized_tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                tc_dict = {}
                # Handle OpenAI SDK Pydantic objects (ChatCompletionMessageFunctionToolCall)
                if hasattr(tc, "function"):
                    tc_dict["id"] = getattr(tc, "id", "")
                    tc_dict["name"] = tc.function.name
                    tc_dict["arguments"] = tc.function.arguments
                # Handle already-dict form
                elif isinstance(tc, dict):
                    tc_dict["id"] = tc.get("id", "")
                    tc_dict["name"] = tc.get("name", tc.get("function", {}).get("name", "unknown") if isinstance(tc.get("function"), dict) else "unknown")
                    tc_dict["arguments"] = tc.get("arguments",
                                                   tc.get("function", {}).get("arguments", "{}") if isinstance(tc.get("function"), dict) else "{}")
                # Fallback: stringify
                else:
                    tc_dict["id"] = str(getattr(tc, "id", ""))
                    tc_dict["name"] = str(getattr(tc, "name", "unknown"))
                    tc_dict["arguments"] = str(getattr(tc, "arguments", "{}"))

                sanitized_tool_calls.append(tc_dict)

        entry = {
            "turn_id": self._count_turns() + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "user_message": user_message,
            "llm_decision": llm_decision,
            "llm_raw_content": llm_content,
            "tool_calls": sanitized_tool_calls,
            "tool_results": tool_results or [],
            "final_response": final_response,
            "duration_ms": duration_ms,
            "error": error,
        }

        self._write_entry(entry)

    def _count_turns(self) -> int:
        """Count existing turns in today's log."""
        path = self._log_path
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def get_turns(self, date: str = None) -> List[Dict[str, Any]]:
        """Retrieve all turns for a given date (YYYY-MM-DD). Defaults to today."""
        if date:
            path = os.path.join(self.log_dir, f"{date}.jsonl")
        else:
            path = self._log_path

        if not os.path.exists(path):
            return []

        turns = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        turns.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read chatlog {path}: {e}")

        return turns

    def get_available_dates(self) -> List[str]:
        """List all dates that have chatlogs."""
        if not os.path.exists(self.log_dir):
            return []
        files = [f.replace(".jsonl", "") for f in os.listdir(self.log_dir)
                 if f.endswith(".jsonl")]
        return sorted(files, reverse=True)


# Global instance
chat_logger = ChatLog()
