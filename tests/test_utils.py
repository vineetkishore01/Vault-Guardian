"""Tests for utility functions."""
import pytest
from datetime import date, datetime, timedelta
from src.utils import (
    parse_date_string, parse_amount_string, format_currency,
    format_date, get_date_range, normalize_brand_name,
    format_deliverables
)


def test_parse_date_string_today():
    """Test parsing 'today'."""
    result = parse_date_string("today")
    assert result == date.today()


def test_parse_date_string_yesterday():
    """Test parsing 'yesterday'."""
    result = parse_date_string("yesterday")
    assert result == date.today() - timedelta(days=1)


def test_parse_date_string_tomorrow():
    """Test parsing 'tomorrow'."""
    result = parse_date_string("tomorrow")
    assert result == date.today() + timedelta(days=1)


def test_parse_date_string_this_month():
    """Test parsing 'this month'."""
    result = parse_date_string("this month")
    assert result.day == 1
    assert result.month == date.today().month
    assert result.year == date.today().year


def test_parse_date_string_last_month():
    """Test parsing 'last month'."""
    result = parse_date_string("last month")
    today = date.today()
    
    if today.month == 1:
        expected_month = 12
        expected_year = today.year - 1
    else:
        expected_month = today.month - 1
        expected_year = today.year
    
    assert result.day == 1
    assert result.month == expected_month
    assert result.year == expected_year


def test_parse_date_string_iso_format():
    """Test parsing ISO date format."""
    result = parse_date_string("2024-01-15")
    assert result == date(2024, 1, 15)


def test_parse_date_string_invalid():
    """Test parsing invalid date string."""
    result = parse_date_string("invalid date")
    assert result is None


def test_parse_amount_string_simple():
    """Test parsing simple amount."""
    result = parse_amount_string("5000")
    assert result == 5000.0


def test_parse_amount_string_with_commas():
    """Test parsing amount with commas."""
    result = parse_amount_string("5,000")
    assert result == 5000.0


def test_parse_amount_string_with_k():
    """Test parsing amount with 'k' suffix."""
    result = parse_amount_string("5k")
    assert result == 5000.0


def test_parse_amount_string_with_l():
    """Test parsing amount with 'l' suffix."""
    result = parse_amount_string("1l")
    assert result == 100000.0


def test_parse_amount_string_invalid():
    """Test parsing invalid amount string."""
    result = parse_amount_string("invalid")
    assert result is None


def test_format_currency_inr():
    """Test formatting currency in INR."""
    result = format_currency(5000.0)
    assert result == "₹5,000.00"


def test_format_currency_custom():
    """Test formatting custom currency."""
    result = format_currency(5000.0, "USD")
    assert result == "USD 5,000.00"


def test_format_date_default():
    """Test formatting date with default format."""
    result = format_date(date(2024, 1, 15))
    assert result == "15 Jan 2024"


def test_format_date_custom():
    """Test formatting date with custom format."""
    result = format_date(date(2024, 1, 15), "%Y-%m-%d")
    assert result == "2024-01-15"


def test_get_date_range_today():
    """Test getting date range for today."""
    start, end = get_date_range("today")
    assert start == date.today()
    assert end == date.today()


def test_get_date_range_this_week():
    """Test getting date range for this week."""
    start, end = get_date_range("this week")
    today = date.today()
    assert start == today - timedelta(days=today.weekday())
    assert end == start + timedelta(days=6)


def test_get_date_range_this_month():
    """Test getting date range for this month."""
    start, end = get_date_range("this month")
    today = date.today()
    assert start.day == 1
    assert start.month == today.month
    assert start.year == today.year


def test_normalize_brand_name():
    """Test normalizing brand name."""
    result = normalize_brand_name("  Nike India  ")
    assert result == "nike india"


def test_normalize_brand_name_with_special_chars():
    """Test normalizing brand name with special characters."""
    result = normalize_brand_name("Nike's!")
    assert result == "nikes"


def test_format_deliverables():
    """Test formatting deliverables."""
    result = format_deliverables({"reels": 2, "stories": 1, "posts": 0})
    assert result == "2 reels, 1 stories"


def test_format_deliverables_empty():
    """Test formatting empty deliverables."""
    result = format_deliverables({"reels": 0, "stories": 0, "posts": 0})
    assert result == "No deliverables"


def test_format_deliverables_partial():
    """Test formatting partial deliverables."""
    result = format_deliverables({"reels": 0, "stories": 0, "posts": 5})
    assert result == "5 posts"
