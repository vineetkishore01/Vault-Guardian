"""Tool definitions for LLM tool calling."""
import json
import logging
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Dict, Any, List, Optional
from datetime import date

from ..database import crud
from ..database.models import PaymentType, PaymentStatus, ExpenseCategory
from ..utils import (
    parse_date_string, parse_amount_string, format_currency,
    format_date, get_ist_today, get_date_range
)

logger = logging.getLogger(__name__)


class EarningSchema(BaseModel):
    """Schema for adding an earning."""
    brand_name: str = Field(default="--UNKNOWN Brand--", max_length=255)
    amount: float = Field(..., ge=0, le=1000000000) # Min 0 (barter), Max 100 Crore
    payment_type: str = Field(default="cash")
    deliverables: Dict[str, int] = Field(default_factory=lambda: {"reels": 0, "stories": 0, "posts": 0})
    date: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    confirm_brand: bool = False

    @field_validator("payment_type")
    @classmethod
    def validate_payment_type(cls, v):
        if v.lower() not in ["cash", "barter"]:
            raise ValueError("payment_type must be 'cash' or 'barter'")
        return v.lower()


class ExpenseSchema(BaseModel):
    """Schema for adding an expense."""
    category: str
    amount: float = Field(..., gt=0, le=1000000000)
    description: Optional[str] = Field(None, max_length=1000)
    date: Optional[str] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid = [c.value for c in ExpenseCategory]
        if v.lower() not in valid:
            raise ValueError(f"category must be one of {valid}")
        return v.lower()


class ToolExecutor:
    """Execute tools called by LLM (Async)."""
    
    def __init__(self, db_session):
        """Initialize tool executor with async database session."""
        self.db = db_session
    
    async def add_earning(self, **kwargs) -> Dict[str, Any]:
        """Add a new earning entry."""
        try:
            # Defense-in-depth: strip security-sensitive fields
            kwargs.pop("confirm", None)
            kwargs.pop("confirm_brand", None)

            # Pydantic validation
            data = EarningSchema(**kwargs)

            entry_date = parse_date_string(data.date) if data.date else get_ist_today()
            if not entry_date:
                entry_date = get_ist_today()

            payment_type_enum = PaymentType(data.payment_type)

            # Brand matching integration — resolve canonical name FIRST
            from ..brand_matching import match_brand, get_or_create_brand_alias

            brand_name = data.brand_name
            if not data.confirm_brand:
                matches = await match_brand(brand_name, threshold=0.75, db_session=self.db)
                if matches:
                    top_match = matches[0]
                    if top_match["confidence"] >= 0.9:
                        # Auto-match to canonical name
                        canonical_name = top_match["brand_name"]
                        await get_or_create_brand_alias(canonical_name, brand_name, db_session=self.db)
                        brand_name = canonical_name
                    elif top_match["confidence"] >= 0.75:
                        # Request confirmation — dedup will run when user confirms
                        return {
                            "success": False,
                            "requires_confirmation": True,
                            "type": "brand_match",
                            "original_name": brand_name,
                            "suggested_name": top_match["brand_name"],
                            "confidence": top_match["confidence"],
                            "data": kwargs,
                            "message": f"Did you mean '{top_match['brand_name']}'? (Match confidence: {int(top_match['confidence']*100)}%)"
                        }

            # ── Dedup: check AFTER brand resolution, using resolved brand_name ──
            from sqlalchemy import select, and_, func
            from ..database.models import Earning
            stmt = select(Earning).where(
                and_(
                    func.lower(Earning.brand_name) == func.lower(brand_name),
                    Earning.amount_earned == data.amount,
                    Earning.entry_date == entry_date
                )
            ).limit(1)
            existing = await self.db.execute(stmt)
            if existing.scalar_one_or_none():
                return {
                    "success": False,
                    "error": "Duplicate",
                    "message": f"This entry already exists: {format_currency(data.amount)} from {brand_name} on {format_date(entry_date)}."
                }
            # ───────────────────────────────────────────────────────────────────

            earning = await crud.EarningCRUD.create(
                db=self.db,
                brand_name=brand_name,
                amount_earned=data.amount,
                payment_type=payment_type_enum,
                deliverables=data.deliverables,
                entry_date=entry_date,
                notes=data.notes
            )

            return {
                "success": True,
                "id": earning.id,
                "message": f"Added earning: {format_currency(data.amount)} from {brand_name} on {format_date(entry_date)}"
            }
        except ValidationError as ve:
            logger.error(f"Validation error in add_earning: {ve}")
            return {"success": False, "error": "Validation Error", "message": "Invalid input data. Please check the details and try again."}
        except Exception as e:
            logger.error(f"Internal error in add_earning: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while adding the earning. Please try again."}
    
    async def update_earning(self, id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing earning entry."""
        try:
            earning = await crud.EarningCRUD.get_by_id(self.db, id)
            if not earning:
                return {"success": False, "error": "Earning not found", "message": f"No earning found with ID {id}"}

            # Security: whitelist allowed fields to prevent LLM from setting internal attributes
            # Map LLM-friendly field names to internal names
            FIELD_MAP = {
                "amount": "amount_earned",
                "brand": "brand_name",
                "date": "entry_date",
                "type": "payment_type",
            }
            ALLOWED_FIELDS = {"brand_name", "amount_earned", "payment_type", "deliverables", "entry_date", "notes", "status",
                              "brand", "amount", "date", "type"}  # include LLM-friendly aliases
            update_data = {}
            for key, value in fields.items():
                if key not in ALLOWED_FIELDS:
                    logger.warning(f"LLM attempted to set disallowed field: {key}")
                    continue

                # Map to internal field name
                internal_key = FIELD_MAP.get(key, key)

                if internal_key == "payment_type":
                    update_data["payment_type"] = PaymentType(value.lower())
                elif internal_key == "status":
                    update_data["status"] = PaymentStatus(value.lower())
                elif internal_key == "entry_date":
                    entry_date = parse_date_string(value) if isinstance(value, str) else value
                    if entry_date:
                        update_data["entry_date"] = entry_date
                else:
                    update_data[internal_key] = value

            updated = await crud.EarningCRUD.update(self.db, id, **update_data)
            return {"success": True, "id": updated.id, "message": f"Updated earning ID {id}"}
        except Exception as e:
            logger.error(f"Internal error in update_earning: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while updating the earning. Please try again."}
    
    async def delete_earning(self, filter: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
        """Delete earning entry/entries."""
        try:
            if "id" in filter:
                earning = await crud.EarningCRUD.get_by_id(self.db, filter["id"])
                if not earning:
                    return {"success": False, "error": "Earning not found", "message": f"No earning found with ID {filter['id']}"}

                if not confirm:
                    return {
                        "success": False,
                        "requires_confirmation": True,
                        "type": "delete_earning",
                        "earnings": [{"id": earning.id, "brand": earning.brand_name, "amount": earning.amount_earned, "date": format_date(earning.entry_date)}],
                        "message": f"Found 1 earning. Please confirm deletion."
                    }

                if await crud.EarningCRUD.delete(self.db, filter["id"]):
                    return {"success": True, "deleted_count": 1, "message": f"Deleted 1 earning"}
                return {"success": False, "error": "Delete failed", "message": "Failed to delete earning"}

            earnings = await crud.EarningCRUD.search(
                db=self.db,
                brand_name=filter.get("brand_name"),
                start_date=parse_date_string(filter.get("start_date")) if filter.get("start_date") else None,
                end_date=parse_date_string(filter.get("end_date")) if filter.get("end_date") else None,
                limit=10
            )
            
            if not earnings:
                return {"success": False, "error": "No matching earnings found", "message": "No earnings match the specified criteria"}

            if not confirm:
                return {
                    "success": False,
                    "requires_confirmation": True,
                    "type": "delete_earning",
                    "earnings": [{"id": e.id, "brand": e.brand_name, "amount": e.amount_earned, "date": format_date(e.entry_date)} for e in earnings],
                    "message": f"Found {len(earnings)} earning(s). Please confirm deletion."
                }
            
            deleted_count = 0
            for earning in earnings:
                if await crud.EarningCRUD.delete(self.db, earning.id):
                    deleted_count += 1
            
            return {"success": True, "deleted_count": deleted_count, "message": f"Deleted {deleted_count} earning(s)"}
        except Exception as e:
            logger.error(f"Internal error in delete_earning: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while deleting earnings. Please try again."}
    
    async def search_earnings(self, filters: Optional[Dict[str, Any]] = None, sort_by: str = "date", limit: Optional[int] = None) -> Dict[str, Any]:
        """Search earnings with filters."""
        try:
            filters = filters or {}
            start_date, end_date = None, None

            if "period" in filters:
                start_date, end_date = get_date_range(filters["period"])
            else:
                if "start_date" in filters:
                    start_date = parse_date_string(filters["start_date"])
                if "end_date" in filters:
                    end_date = parse_date_string(filters["end_date"])

            payment_type = PaymentType(filters["payment_type"].lower()) if "payment_type" in filters else None
            status = PaymentStatus(filters["status"].lower()) if "status" in filters else None

            # Cap limit to prevent token overflow
            safe_limit = min(limit, 100) if limit else 100

            earnings = await crud.EarningCRUD.search(self.db, brand_name=filters.get("brand_name"), start_date=start_date, end_date=end_date, payment_type=payment_type, status=status, limit=safe_limit)
            results = [{"id": e.id, "brand": e.brand_name, "amount": e.amount_earned, "payment_type": e.payment_type.value, "deliverables": e.deliverables, "date": format_date(e.entry_date), "status": e.status.value, "notes": e.notes} for e in earnings]
            
            return {"success": True, "count": len(results), "results": results, "message": f"Found {len(results)} earning(s)"}
        except Exception as e:
            logger.error(f"Internal error in search_earnings: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while searching earnings. Please try again."}
    
    async def add_expense(self, **kwargs) -> Dict[str, Any]:
        """Add a new expense entry."""
        try:
            data = ExpenseSchema(**kwargs)
            expense_date = parse_date_string(data.date) if data.date else get_ist_today()
            category_enum = ExpenseCategory(data.category)

            # ── Dedup: prevent accidental doubles ──
            from sqlalchemy import select, and_, func
            from ..database.models import Expense
            stmt = select(Expense).where(
                and_(
                    Expense.category == category_enum,
                    Expense.amount == data.amount,
                    Expense.expense_date == expense_date
                )
            ).limit(1)
            existing = await self.db.execute(stmt)
            if existing.scalar_one_or_none():
                return {
                    "success": False,
                    "error": "Duplicate",
                    "message": f"This expense already exists: {format_currency(data.amount)} for {data.category} on {format_date(expense_date)}."
                }
            # ──────────────────────────────────────────────

            expense = await crud.ExpenseCRUD.create(db=self.db, category=category_enum, amount=data.amount, description=data.description, expense_date=expense_date)
            return {"success": True, "id": expense.id, "message": f"Added expense: {format_currency(data.amount)} for {data.category} on {format_date(expense_date)}"}
        except ValidationError as ve:
            logger.error(f"Validation error in add_expense: {ve}")
            return {"success": False, "error": "Validation Error", "message": "Invalid input data. Please check the details and try again."}
        except Exception as e:
            logger.error(f"Internal error in add_expense: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while adding the expense. Please try again."}
    
    async def get_financial_summary(self, period: str = "this month", include_expenses: bool = True) -> Dict[str, Any]:
        """Get financial summary for period."""
        try:
            start_date, end_date = get_date_range(period)
            total_earnings = await crud.EarningCRUD.get_total_earnings(self.db, start_date=start_date, end_date=end_date)
            
            total_expenses, expenses_by_category = 0.0, {}
            if include_expenses:
                total_expenses = await crud.ExpenseCRUD.get_total_expenses(self.db, start_date=start_date, end_date=end_date)
                expenses_by_category = await crud.ExpenseCRUD.get_expenses_by_category(self.db, start_date=start_date, end_date=end_date)
            
            net_income = total_earnings - total_expenses
            deliverables = await crud.EarningCRUD.get_deliverables_summary(self.db, start_date=start_date, end_date=end_date)
            payment_breakdown = await crud.EarningCRUD.get_payment_type_breakdown(self.db, start_date=start_date, end_date=end_date)

            return {
                "success": True, "period": period, "start_date": format_date(start_date), "end_date": format_date(end_date),
                "total_earnings": total_earnings, "total_expenses": total_expenses, "net_income": net_income,
                "expenses_by_category": expenses_by_category, "deliverables": deliverables,
                "cash_deals": payment_breakdown.get("cash", 0), "barter_deals": payment_breakdown.get("barter", 0),
                "message": f"Financial summary for {period}: {format_currency(total_earnings)} earnings, {format_currency(total_expenses)} expenses"
            }
        except Exception as e:
            logger.error(f"Internal error in get_financial_summary: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while generating the financial summary. Please try again."}

    async def generate_report(self, format: str, period: str, include_charts: bool = True) -> Dict[str, Any]:
        """Generate PDF or Excel report (wrapper for analytics)."""
        try:
            from ..analytics import generate_report
            path = await generate_report(format=format, period=period, include_charts=include_charts, db_session=self.db)
            return {"success": True, "path": path, "message": f"Generated {format.upper()} report for {period}"}
        except Exception as e:
            logger.error(f"Internal error in generate_report: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while generating the report. Please try again."}

    async def match_brand(self, name: str, threshold: float = 0.75) -> Dict[str, Any]:
        """Match brand name."""
        from ..brand_matching import match_brand
        try:
            matches = await match_brand(brand_name=name, threshold=threshold, db_session=self.db)
            return {"success": True, "matches": matches, "message": f"Found {len(matches)} match(es)"}
        except Exception as e:
            logger.error(f"Internal error in match_brand: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while matching the brand. Please try again."}

    async def set_reminder(self, earning_id: int, days: Optional[int] = None, reminder_date: Optional[str] = None) -> Dict[str, Any]:
        """Set payment reminder."""
        try:
            earning = await crud.EarningCRUD.get_by_id(self.db, earning_id)
            if not earning:
                return {"success": False, "message": "Earning not found"}

            # ── Check for existing PENDING reminder ──
            from sqlalchemy import select, and_
            from ..database.models import PaymentReminder, ReminderStatus
            stmt = select(PaymentReminder).where(
                and_(
                    PaymentReminder.earning_id == earning_id,
                    PaymentReminder.status == ReminderStatus.PENDING
                )
            ).limit(1)
            existing = await self.db.execute(stmt)
            existing_reminder = existing.scalar_one_or_none()
            # ───────────────────────────────────────────

            from datetime import timedelta

            # Support natural language dates: "tomorrow", "next week", "15th may"
            if reminder_date:
                parsed = parse_date_string(reminder_date)
                if parsed:
                    target_date = parsed
                else:
                    target_date = earning.entry_date + timedelta(days=days or 7)
            else:
                target_date = earning.entry_date + timedelta(days=days or 7)

            if existing_reminder:
                # Update existing reminder instead of creating a duplicate
                existing_reminder.reminder_date = target_date
                existing_reminder.message = f"Reminder for {earning.brand_name}"
                await self.db.flush()
                return {
                    "success": True,
                    "id": existing_reminder.id,
                    "reminder_date": format_date(target_date),
                    "message": f"Updated reminder for {earning.brand_name} to {format_date(target_date)}"
                }

            reminder = await crud.PaymentReminderCRUD.create(
                self.db, earning_id=earning_id,
                reminder_date=target_date,
                message=f"Reminder for {earning.brand_name}"
            )
            return {
                "success": True,
                "id": reminder.id,
                "reminder_date": format_date(target_date),
                "message": f"Reminder set for {earning.brand_name} on {format_date(target_date)}"
            }
        except Exception as e:
            logger.error(f"Internal error in set_reminder: {e}", exc_info=True)
            return {"success": False, "error": "Processing Error", "message": "Something went wrong while setting the reminder. Please try again."}


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions for LLM (OpenAI function calling format)."""
    return [
        {
            "type": "function",
            "function": {
                "name": "add_earning",
                "description": "Add a new earning entry. Auto-fills: brand_name='--UNKNOWN Brand--' if missing, payment_type='cash' if missing, deliverables all zeros if missing, date=today if missing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brand_name": {"type": "string", "description": "Name of the brand. Use '--UNKNOWN Brand--' if not mentioned."},
                        "amount": {"type": "number", "description": "Amount earned in rupees. PARSE natural language (e.g., '50k' -> 50000.0, '1.5 lakh' -> 150000.0) before calling."},
                        "payment_type": {"type": "string", "enum": ["cash", "barter"], "description": "Payment type. Default 'cash' if not mentioned."},
                        "deliverables": {
                            "type": "object",
                            "properties": {
                                "reels": {"type": "integer"},
                                "stories": {"type": "integer"},
                                "posts": {"type": "integer"}
                            }
                        },
                        "date": {"type": "string", "description": "Date of earning. Default 'today' if not mentioned."},
                        "notes": {"type": "string", "description": "Additional notes"}
                    },
                    "required": ["amount"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_earning",
                "description": "Update an existing earning entry. Use 'amount' for amount_earned, 'date' for entry_date, 'brand_name' for brand.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Earning ID to update"},
                        "fields": {
                            "type": "object",
                            "description": "Fields to update. Use keys: amount (number), brand_name (string), payment_type ('cash'/'barter'), deliverables (object), date (string), notes (string), status ('pending'/'received').",
                            "properties": {
                                "amount": {"type": "number", "description": "New amount earned"},
                                "brand_name": {"type": "string", "description": "New brand name"},
                                "payment_type": {"type": "string", "enum": ["cash", "barter"]},
                                "deliverables": {"type": "object"},
                                "date": {"type": "string", "description": "New date"},
                                "notes": {"type": "string"},
                                "status": {"type": "string", "enum": ["pending", "received"]}
                            }
                        }
                    },
                    "required": ["id", "fields"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_earning",
                "description": "Delete earning entry/entries",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "object", "description": "Filter criteria"}
                    },
                    "required": ["filter"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_earnings",
                "description": "Search earnings with filters",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {"type": "object", "description": "Search filters"},
                        "sort_by": {"type": "string", "description": "Sort field"},
                        "limit": {"type": "integer", "description": "Max results"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_expense",
                "description": "Add a new expense entry",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["video_editing", "travel", "equipment", "other"], "description": "Expense category"},
                        "amount": {"type": "number", "description": "Expense amount in rupees. PARSE natural language (e.g., '2k' -> 2000.0) before calling."},
                        "description": {"type": "string", "description": "Expense description"},
                        "date": {"type": "string", "description": "Date of expense"}
                    },
                    "required": ["category", "amount"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_financial_summary",
                "description": "Get financial summary for period",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string", "description": "Time period (e.g., 'this month', 'last week')"},
                        "include_expenses": {"type": "boolean", "description": "Include expenses in summary"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_report",
                "description": "Generate PDF or Excel report",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "enum": ["pdf", "excel"], "description": "Report format"},
                        "period": {"type": "string", "description": "Time period for report"},
                        "include_charts": {"type": "boolean", "description": "Include charts in report"}
                    },
                    "required": ["format", "period"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "match_brand",
                "description": "Match brand name to existing brands",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Brand name to match"},
                        "threshold": {"type": "number", "description": "Confidence threshold (0-1)"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_reminder",
                "description": "Set payment reminder for an earning. Use reminder_date for natural language dates like 'tomorrow', 'next week', '15th may'. Use days for number of days after earning date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "earning_id": {"type": "integer", "description": "Earning ID to remind about"},
                        "days": {"type": "integer", "description": "Days after the earning's date. Use if reminder_date is not suitable."},
                        "reminder_date": {"type": "string", "description": "When to remind. Use natural language: 'tomorrow', 'next week', '15th may', 'end of month'. Preferred over days."}
                    },
                    "required": ["earning_id"]
                }
            }
        }
    ]
