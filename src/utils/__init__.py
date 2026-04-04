"""Utility functions for Vault Guardian."""
from datetime import datetime, date, timedelta
from typing import Optional, Tuple
import re
import pytz
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

from ..config import config


IST = pytz.timezone(config.database.timezone)


def get_ist_now() -> datetime:
    """Get current datetime in IST timezone."""
    return datetime.now(IST)


def get_ist_today() -> date:
    """Get today's date in IST timezone."""
    return get_ist_now().date()


def to_ist(dt: datetime) -> datetime:
    """Convert datetime to IST timezone."""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(IST)


def format_currency(amount: float, currency: str = None) -> str:
    """Format amount as currency string."""
    currency = currency or config.analytics.default_currency
    if currency == "INR":
        return f"₹{amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def format_date(dt: date, format_str: str = "%d %b %Y") -> str:
    """Format date as string."""
    return dt.strftime(format_str)


def parse_date_string(date_str: str) -> Optional[date]:
    """Parse natural language date string to date object."""
    date_str = date_str.strip().lower()
    
    today = get_ist_today()
    
    if date_str in ["today", "now"]:
        return today
    
    if date_str == "yesterday":
        return today - timedelta(days=1)
    
    if date_str == "tomorrow":
        return today + timedelta(days=1)
    
    if date_str == "this week":
        return today - timedelta(days=today.weekday())
    
    if date_str == "last week":
        return today - timedelta(days=today.weekday() + 7)
    
    if date_str == "this month":
        return today.replace(day=1)
    
    if date_str == "last month":
        return (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    if date_str == "this year":
        return today.replace(month=1, day=1)
    
    if date_str == "last year":
        return today.replace(year=today.year - 1, month=1, day=1)
    
    if date_str.startswith("this "):
        month_name = date_str[5:]
        month_num = _get_month_number(month_name)
        if month_num:
            result = today.replace(month=month_num, day=1)
            # If the month has already passed this year, it might mean next year? 
            # But usually 'this' means the one in the current calendar year.
            return result
    
    if date_str.startswith("last "):
        month_name = date_str[5:]
        month_num = _get_month_number(month_name)
        if month_num:
            # If current month is >= requested month, it's this year
            # If current month is < requested month, it's last year
            year = today.year
            if today.month <= month_num:
                year -= 1
            return today.replace(year=year, month=month_num, day=1)
    
    if "ago" in date_str:
        match = re.search(r'(\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago', date_str)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("day"):
                return today - timedelta(days=num)
            elif unit.startswith("week"):
                return today - timedelta(weeks=num)
            elif unit.startswith("month"):
                return today - relativedelta(months=num)
            elif unit.startswith("year"):
                return today - relativedelta(years=num)
    
    try:
        parsed_dt = date_parser.parse(date_str, dayfirst=True)
        if parsed_dt.tzinfo:
            parsed_dt = to_ist(parsed_dt)
        return parsed_dt.date()
    except (ValueError, TypeError):
        return None


def _get_month_number(month_name: str) -> Optional[int]:
    """Get month number from month name."""
    months = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }
    return months.get(month_name.lower())


def parse_amount_string(amount_str: str) -> Optional[float]:
    """Parse amount string to float. Most parsing should be done by LLM."""
    if amount_str is None:
        return None
    
    if isinstance(amount_str, (int, float)):
        return float(amount_str)

    # Clean the string
    amount_str = str(amount_str).strip().lower()
    amount_str = amount_str.replace(",", "").replace("₹", "").replace("$", "").replace("inr", "").replace("rs", "").strip()

    try:
        # LLM should provide "50000", but handle "50k" just in case
        match = re.search(r'([0-9]*\.?[0-9]+)\s*(k|l|cr|lac|lakh|crore)?', amount_str)
        if not match:
            return float(amount_str) if amount_str else None

        base_amount = float(match.group(1))
        suffix = match.group(2)

        if suffix == 'k':
            return base_amount * 1_000
        elif suffix in ('l', 'lac', 'lakh'):
            return base_amount * 100_000
        elif suffix in ('cr', 'crore'):
            return base_amount * 10_000_000
        else:
            return base_amount
    except (ValueError, TypeError):
        return None


def get_date_range(period: str) -> Tuple[date, date]:
    """Get start and end dates for a given period."""
    today = get_ist_today()
    period = period.lower().strip()
    
    if period == "today":
        return today, today
    
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    
    if period == "this week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    
    if period == "last week":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    
    if period == "this month":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start, end
    
    if period == "last month":
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        end = today.replace(day=1) - timedelta(days=1)
        return start, end
    
    if period == "this year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end
    
    if period == "last year":
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)
        return start, end
    
    if period == "all time":
        return date(2000, 1, 1), today
    
    return today, today


def normalize_brand_name(name: str) -> str:
    """Normalize brand name for matching."""
    if not name:
        return ""
    
    name = name.strip().lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    
    return name.strip()


def truncate_string(text: str, max_length: int = 100) -> str:
    """Truncate string to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_chat_id(chat_id: str) -> bool:
    """Validate chat ID against allowed chat ID."""
    return str(chat_id) == str(config.telegram.allowed_chat_id)


def format_deliverables(deliverables: dict) -> str:
    """Format deliverables dict as readable string."""
    parts = []
    if deliverables.get("reels", 0) > 0:
        parts.append(f"{deliverables['reels']} reels")
    if deliverables.get("stories", 0) > 0:
        parts.append(f"{deliverables['stories']} stories")
    if deliverables.get("posts", 0) > 0:
        parts.append(f"{deliverables['posts']} posts")
    
    if not parts:
        return "No deliverables"
    
    return ", ".join(parts)
