#!/usr/bin/env python
"""Integration test: Simulates real Telegram conversations to validate all bot features."""
import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.database import db_manager, crud
from src.database.models import PaymentType, PaymentStatus, ExpenseCategory
from src.llm import llm_client, get_tool_definitions
from src.llm.tools import ToolExecutor
from src.utils import (
    format_currency, format_date, get_ist_today,
    get_date_range, parse_amount_string, parse_date_string
)
from src.analytics import generate_report

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
warnings = 0


def result(success: bool, test_name: str, detail: str = ""):
    global passed, failed, warnings
    if success:
        passed += 1
        print(f"  {GREEN}✅ PASS{RESET}: {test_name}")
        if detail:
            print(f"     {detail}")
    else:
        failed += 1
        print(f"  {RED}❌ FAIL{RESET}: {test_name}")
        if detail:
            print(f"     {detail}")


def warn(test_name: str, detail: str = ""):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠️  WARN{RESET}: {test_name}")
    if detail:
        print(f"     {detail}")


async def test_llm_tool_calls():
    """Test that LLM can properly call tools with correct format."""
    print(f"\n{BOLD}{CYAN}Test 1: LLM Tool Calling{RESET}")

    tools = get_tool_definitions()

    # Verify tool format (must have "type": "function" wrapper)
    for tool in tools:
        if tool.get("type") != "function":
            result(False, f"Tool format check: {tool.get('function', {}).get('name', 'unknown')}",
                   f"Missing 'type': 'function' wrapper")
        elif "function" not in tool:
            result(False, f"Tool format check: missing 'function' key", "")
        else:
            result(True, f"Tool format: {tool['function']['name']}")

    # Test LLM can parse a simple earning request
    system_prompt_path = Path("config/prompts/system_prompt.txt")
    system_prompt = system_prompt_path.read_text() if system_prompt_path.exists() else ""

    response = await llm_client.get_tool_calls(
        prompt="I earned 5000 rupees from Nike for 2 reels today",
        tools=tools,
        system_prompt=system_prompt
    )

    if response:
        result(True, "LLM returned tool calls", f"Found {len(response)} tool call(s)")
        for tc in response:
            print(f"     Tool: {tc['name']}, Args: {tc['arguments'][:100]}...")
    else:
        result(False, "LLM returned tool calls", "No tool calls returned")

    # Test expense parsing
    response = await llm_client.get_tool_calls(
        prompt="I spent 3000 on video editing",
        tools=tools,
        system_prompt=system_prompt
    )

    if response:
        has_expense = any(tc["name"] == "add_expense" for tc in response)
        result(has_expense, "LLM parsed expense request",
               f"Tool: {response[0]['name'] if response else 'none'}")
    else:
        result(False, "LLM parsed expense request", "No tool calls")

    # Test summary request
    response = await llm_client.get_tool_calls(
        prompt="how much did I earn this month",
        tools=tools,
        system_prompt=system_prompt
    )

    if response:
        has_summary = any(tc["name"] == "get_financial_summary" for tc in response)
        result(has_summary, "LLM parsed summary request",
               f"Tool: {response[0]['name'] if response else 'none'}")
    else:
        result(False, "LLM parsed summary request", "No tool calls")


async def test_earning_creation():
    """Test earning creation with various inputs."""
    print(f"\n{BOLD}{CYAN}Test 2: Earning Creation{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        # Test 1: Full details
        result_data = await executor.add_earning(
            brand_name="Nike",
            amount=5000,
            payment_type="cash",
            deliverables={"reels": 2, "stories": 0, "posts": 0},
            date="today"
        )
        result(result_data["success"], "Full details earning",
               result_data.get("message", result_data.get("error", "")))

        # Test 2: Minimal details (auto-fill)
        result_data = await executor.add_earning(
            brand_name="Zen",
            amount=4000,
            payment_type=None,
            deliverables=None,
            date=None
        )
        result(result_data["success"], "Auto-fill defaults",
               result_data.get("message", result_data.get("error", "")))

        # Test 3: Unknown brand
        result_data = await executor.add_earning(
            brand_name="--UNKNOWN Brand--",
            amount=2000,
            payment_type="barter",
            deliverables={"reels": 1, "stories": 1, "posts": 0},
            date="today"
        )
        result(result_data["success"], "Unknown brand entry",
               result_data.get("message", result_data.get("error", "")))

        # Test 4: Barter deal
        result_data = await executor.add_earning(
            brand_name="Adidas",
            amount=0,
            payment_type="barter",
            deliverables={"reels": 3, "stories": 0, "posts": 1},
            date="today"
        )
        # Amount=0 should fail validation
        result(not result_data["success"], "Barter with zero amount rejected",
               result_data.get("message", result_data.get("error", "")))

        # Test 5: Barter with nominal amount
        result_data = await executor.add_earning(
            brand_name="Adidas",
            amount=1,
            payment_type="barter",
            deliverables={"reels": 3, "stories": 0, "posts": 1},
            date="today"
        )
        result(result_data["success"], "Barter with nominal amount",
               result_data.get("message", result_data.get("error", "")))


async def test_expense_creation():
    """Test expense creation."""
    print(f"\n{BOLD}{CYAN}Test 3: Expense Creation{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        # Video editing expense
        result_data = await executor.add_expense(
            category="video_editing",
            amount=5000,
            description="Video editing",
            date="today"
        )
        result(result_data["success"], "Video editing expense",
               result_data.get("message", result_data.get("error", "")))

        # Travel expense
        result_data = await executor.add_expense(
            category="travel",
            amount=2000,
            description="Travel and shoot",
            date="today"
        )
        result(result_data["success"], "Travel expense",
               result_data.get("message", result_data.get("error", "")))

        # Equipment expense
        result_data = await executor.add_expense(
            category="equipment",
            amount=10000,
            description="Equipment purchase",
            date="today"
        )
        result(result_data["success"], "Equipment expense",
               result_data.get("message", result_data.get("error", "")))


async def test_financial_summary():
    """Test financial summary with deliverables and barter count."""
    print(f"\n{BOLD}{CYAN}Test 4: Financial Summary{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        result_data = await executor.get_financial_summary(period="today")

        if result_data["success"]:
            result(True, "Financial summary retrieved",
                   f"Earnings: {format_currency(result_data['total_earnings'])}, "
                   f"Expenses: {format_currency(result_data['total_expenses'])}, "
                   f"Net: {format_currency(result_data['net_income'])}")

            # Check deliverables
            d = result_data["deliverables"]
            result(True, "Deliverables breakdown",
                   f"Reels: {d['reels']}, Stories: {d['stories']}, Posts: {d['posts']}")

            # Check barter count
            barter = result_data.get("barter_deals", 0)
            cash = result_data.get("cash_deals", 0)
            result(True, "Payment type breakdown",
                   f"Cash: {cash}, Barter: {barter}")
        else:
            result(False, "Financial summary", result_data.get("error", "Unknown error"))


async def test_search_earnings():
    """Test searching earnings."""
    print(f"\n{BOLD}{CYAN}Test 5: Search Earnings{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        # Search all today
        result_data = await executor.search_earnings(filters={"period": "today"})
        if result_data["success"]:
            result(True, "Search today's earnings",
                   f"Found {result_data['count']} earning(s)")
            for e in result_data["results"]:
                print(f"     • {e['brand']}: {format_currency(e['amount'])} ({e['payment_type']})")
        else:
            result(False, "Search today's earnings", result_data.get("error", ""))

        # Search by brand
        result_data = await executor.search_earnings(
            filters={"brand_name": "Nike"},
            limit=10
        )
        if result_data["success"]:
            result(True, "Search by brand (Nike)",
                   f"Found {result_data['count']} earning(s)")
        else:
            result(False, "Search by brand (Nike)", result_data.get("error", ""))


async def test_brand_matching():
    """Test brand matching functionality."""
    print(f"\n{BOLD}{CYAN}Test 6: Brand Matching{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        # First create a known brand
        await executor.add_earning(
            brand_name="Kellogs",
            amount=10000,
            payment_type="cash",
            deliverables={"reels": 2, "stories": 0, "posts": 0},
            date="today"
        )

        # Now try matching variant
        from src.brand_matching import match_brand
        matches = await match_brand("Kellogs Chocos", threshold=0.5, db_session=db)

        if matches:
            result(True, "Brand matching variant",
                   f"'Kellogs Chocos' → '{matches[0]['brand_name']}' (confidence: {matches[0]['confidence']:.2f})")
        else:
            warn("Brand matching variant", "No match found for 'Kellogs Chocos'")

        # Test exact match
        matches = await match_brand("kellogs", threshold=0.5, db_session=db)
        if matches:
            result(True, "Brand matching case-insensitive",
                   f"'kellogs' → '{matches[0]['brand_name']}' (confidence: {matches[0]['confidence']:.2f})")
        else:
            result(False, "Brand matching case-insensitive", "No match")


async def test_update_delete():
    """Test update and delete operations."""
    print(f"\n{BOLD}{CYAN}Test 7: Update & Delete{RESET}")

    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        # Create an entry to update
        result_data = await executor.add_earning(
            brand_name="TestBrand",
            amount=3000,
            payment_type="cash",
            deliverables={"reels": 1, "stories": 0, "posts": 0},
            date="today"
        )

        if result_data["success"]:
            earning_id = result_data["id"]

            # Update it
            result_data = await executor.update_earning(
                id=earning_id,
                fields={"amount": 4000}
            )
            result(result_data["success"], "Update earning amount",
                   result_data.get("message", result_data.get("error", "")))

            # Delete it
            result_data = await executor.delete_earning(
                filter={"id": earning_id},
                confirm=True
            )
            result(result_data["success"], "Delete earning",
                   result_data.get("message", result_data.get("error", "")))
        else:
            result(False, "Create test entry for update/delete", result_data.get("error", ""))


async def test_report_generation():
    """Test PDF and Excel report generation."""
    print(f"\n{BOLD}{CYAN}Test 8: Report Generation{RESET}")

    with db_manager.get_session() as db:
        # PDF report
        try:
            pdf_path = await generate_report(
                format="pdf",
                period="today",
                include_charts=True,
                db_session=db
            )
            pdf_exists = Path(pdf_path).exists()
            result(pdf_exists, "PDF report generated",
                   f"Path: {pdf_path}, Exists: {pdf_exists}")
        except Exception as e:
            result(False, "PDF report generated", str(e))

        # Excel report
        try:
            xlsx_path = await generate_report(
                format="excel",
                period="today",
                include_charts=False,
                db_session=db
            )
            xlsx_exists = Path(xlsx_path).exists()
            result(xlsx_exists, "Excel report generated",
                   f"Path: {xlsx_path}, Exists: {xlsx_exists}")
        except Exception as e:
            result(False, "Excel report generated", str(e))


async def test_deliverables_summary():
    """Test deliverables summary (the astext bug fix)."""
    print(f"\n{BOLD}{CYAN}Test 9: Deliverables Summary (SQLite json_extract){RESET}")

    with db_manager.get_session() as db:
        try:
            summary = crud.EarningCRUD.get_deliverables_summary(db)
            result(True, "Deliverables summary query",
                   f"Reels: {summary['reels']}, Stories: {summary['stories']}, Posts: {summary['posts']}")
        except Exception as e:
            result(False, "Deliverables summary query", str(e))

        try:
            breakdown = crud.EarningCRUD.get_payment_type_breakdown(db)
            result(True, "Payment type breakdown",
                   f"Cash: {breakdown.get('cash', 0)}, Barter: {breakdown.get('barter', 0)}")
        except Exception as e:
            result(False, "Payment type breakdown", str(e))


async def test_amount_parsing():
    """Test amount string parsing."""
    print(f"\n{BOLD}{CYAN}Test 10: Amount Parsing{RESET}")

    tests = [
        ("5000", 5000.0),
        ("5k", 5000.0),
        ("1.5l", 150000.0),
        ("2.5cr", 25000000.0),
        ("₹10000", 10000.0),
        ("10,000", 10000.0),
        ("100", 100.0),
        ("abc", None),
    ]

    for input_str, expected in tests:
        parsed = parse_amount_string(input_str)
        if parsed == expected:
            result(True, f"Parse '{input_str}'", f"= {parsed}")
        else:
            result(False, f"Parse '{input_str}'", f"Expected {expected}, got {parsed}")


async def test_natural_language_simulation():
    """Simulate natural language conversations."""
    print(f"\n{BOLD}{CYAN}Test 11: Natural Language Simulation{RESET}")

    system_prompt_path = Path("config/prompts/system_prompt.txt")
    system_prompt = system_prompt_path.read_text() if system_prompt_path.exists() else ""
    tools = get_tool_definitions()

    scenarios = [
        {
            "name": "Earning with partial info",
            "prompt": "I earned 4000 rupees for collab with zen and made 2 reels only, save it",
            "expected_tool": "add_earning"
        },
        {
            "name": "Expense entry",
            "prompt": "I spent 5000 for video editing",
            "expected_tool": "add_expense"
        },
        {
            "name": "Total earnings query",
            "prompt": "what is my total earning till now",
            "expected_tool": "get_financial_summary"
        },
        {
            "name": "Monthly earnings query",
            "prompt": "how much did i earn this month",
            "expected_tool": "get_financial_summary"
        },
        {
            "name": "Brand-specific query",
            "prompt": "how much did zen pay me",
            "expected_tool": "search_earnings"
        },
        {
            "name": "Report request",
            "prompt": "send me the earning report for today as pdf",
            "expected_tool": "generate_report"
        },
        {
            "name": "Delete request",
            "prompt": "delete the entry from zen",
            "expected_tool": "delete_earning"
        },
        {
            "name": "Multiple expenses",
            "prompt": "I spent 2000 for travel and 10000 for equipments",
            "expected_tool": "add_expense"
        },
    ]

    for scenario in scenarios:
        try:
            response = await llm_client.get_tool_calls(
                prompt=scenario["prompt"],
                tools=tools,
                system_prompt=system_prompt
            )

            if response:
                tool_names = [tc["name"] for tc in response]
                has_expected = scenario["expected_tool"] in tool_names
                result(has_expected,
                       f"NL: {scenario['name']}",
                       f"Expected: {scenario['expected_tool']}, Got: {', '.join(tool_names)}")

                # Execute the tools and show results
                with db_manager.get_session() as db:
                    executor = ToolExecutor(db)
                    for tc in response:
                        method = getattr(executor, tc["name"], None)
                        if method:
                            try:
                                args = json.loads(tc["arguments"])
                                exec_result = await method(**args)
                                if exec_result.get("success"):
                                    print(f"     ✅ {tc['name']}: {exec_result.get('message', 'OK')}")
                                elif exec_result.get("requires_confirmation"):
                                    print(f"     ⚠️  {tc['name']}: Requires confirmation")
                                else:
                                    print(f"     ❌ {tc['name']}: {exec_result.get('error', 'Failed')}")
                            except Exception as e:
                                print(f"     ❌ {tc['name']}: {str(e)[:100]}")
            else:
                result(False, f"NL: {scenario['name']}", "No tool calls returned")
        except Exception as e:
            result(False, f"NL: {scenario['name']}", str(e)[:150])


async def main():
    print(f"\n{BOLD}{'='*60}")
    print(f"  Vault Guardian — Integration Test Suite")
    print(f"{'='*60}{RESET}")

    await test_llm_tool_calls()
    await test_earning_creation()
    await test_expense_creation()
    await test_financial_summary()
    await test_search_earnings()
    await test_brand_matching()
    await test_update_delete()
    await test_report_generation()
    await test_deliverables_summary()
    await test_amount_parsing()
    await test_natural_language_simulation()

    print(f"\n{BOLD}{'='*60}")
    print(f"  Results: {GREEN}{passed} passed{RESET}, "
          f"{RED}{failed} failed{RESET}, "
          f"{YELLOW}{warnings} warnings{RESET}")
    print(f"{'='*60}{RESET}\n")

    await llm_client.close()
    db_manager.close()

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
