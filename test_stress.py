#!/usr/bin/env python
"""Stress test: Edge-case natural language queries to find failure points."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.database import db_manager, crud
from src.database.models import PaymentType, PaymentStatus, ExpenseCategory
from src.llm import llm_client, get_tool_definitions
from src.llm.tools import ToolExecutor
from src.utils import format_currency, format_date, get_ist_today
from datetime import timedelta

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

passed = 0
failed = 0
skipped = 0


def result(success, name, detail=""):
    global passed, failed, skipped
    if success:
        passed += 1
        print(f"  {GREEN}✅{RESET} {name}")
    else:
        failed += 1
        print(f"  {RED}❌{RESET} {name}")
    if detail:
        print(f"     {DIM}{detail}{RESET}")


async def run_nl(prompt, expected_tools=None, execute=True):
    """Run a natural language query and optionally execute the tools."""
    system_prompt = Path("config/prompts/system_prompt.txt").read_text()
    tools = get_tool_definitions()

    try:
        response = await llm_client.get_tool_calls(
            prompt=prompt, tools=tools, system_prompt=system_prompt
        )

        if not response:
            result(False, f"Q: {prompt[:70]}...", "No tool calls returned")
            return

        tool_names = [tc["name"] for tc in response]

        # Check if expected tool was called
        if expected_tools:
            matched = any(et in tool_names for et in expected_tools)
            if not matched:
                result(False, f"Q: {prompt[:70]}...",
                       f"Expected one of {expected_tools}, got {tool_names}")
                return

        # Execute tools
        if execute:
            with db_manager.get_session() as db:
                executor = ToolExecutor(db)
                for tc in response:
                    method = getattr(executor, tc["name"], None)
                    if method:
                        try:
                            args = json.loads(tc["arguments"])
                            r = await method(**args)
                            if r.get("success"):
                                print(f"     {GREEN}→{RESET} {tc['name']}: {r.get('message', 'OK')[:120]}")
                            elif r.get("requires_confirmation"):
                                print(f"     {YELLOW}→{RESET} {tc['name']}: ⚠️ needs confirmation — {r.get('message', '')[:100]}")
                            else:
                                print(f"     {RED}→{RESET} {tc['name']}: {r.get('error', 'Failed')[:120]}")
                        except Exception as e:
                            print(f"     {RED}→{RESET} {tc['name']}: EXCEPTION: {str(e)[:120]}")

        result(True, f"Q: {prompt[:70]}...", f"Tools: {', '.join(tool_names)}")

    except Exception as e:
        result(False, f"Q: {prompt[:70]}...", f"Exception: {str(e)[:150]}")


async def main():
    print(f"\n{BOLD}{'='*70}")
    print(f"  Vault Guardian — Edge Case Stress Test")
    print(f"{'='*70}{RESET}\n")

    # ── Phase 1: Seed data ──
    print(f"{BOLD}{CYAN}Phase 0: Seeding test data{RESET}")
    with db_manager.get_session() as db:
        executor = ToolExecutor(db)

        seed_data = [
            ("Nike", 15000, "cash", {"reels": 3, "stories": 2, "posts": 1}, "2026-03-15"),
            ("Adidas", 8000, "cash", {"reels": 2, "stories": 0, "posts": 0}, "2026-03-20"),
            ("Kellogs", 12000, "barter", {"reels": 1, "stories": 3, "posts": 0}, "2026-02-10"),
            ("Zen", 4000, "cash", {"reels": 2, "stories": 0, "posts": 0}, "2026-04-01"),
            ("Puma", 20000, "cash", {"reels": 5, "stories": 2, "posts": 2}, "2026-01-25"),
            ("Lakme", 6000, "barter", {"reels": 1, "stories": 1, "posts": 0}, "2026-03-28"),
            ("Nike", 10000, "cash", {"reels": 2, "stories": 0, "posts": 1}, "2026-02-14"),
            ("--UNKNOWN Brand--", 3000, "cash", {"reels": 0, "stories": 0, "posts": 0}, "2026-04-02"),
        ]

        for brand, amt, pt, deliv, dt in seed_data:
            try:
                r = await executor.add_earning(
                    brand_name=brand, amount=amt, payment_type=pt,
                    deliverables=deliv, date=dt
                )
                if r["success"]:
                    print(f"  {GREEN}+{RESET} {brand}: ₹{amt:,}")
                else:
                    print(f"  {RED}!{RESET} {brand}: {r.get('error', '')}")
            except Exception as e:
                print(f"  {RED}!{RESET} {brand}: {e}")

        # Seed expenses
        expenses = [
            ("video_editing", 5000, "2026-03-15"),
            ("travel", 3000, "2026-03-20"),
            ("equipment", 15000, "2026-02-01"),
            ("other", 2000, "2026-04-01"),
        ]
        for cat, amt, dt in expenses:
            try:
                r = await executor.add_expense(category=cat, amount=amt, date=dt)
                if r["success"]:
                    print(f"  {GREEN}+{RESET} Expense: {cat} ₹{amt:,}")
            except Exception as e:
                print(f"  {RED}!{RESET} Expense: {e}")

    # ── Phase 2: Earning creation edge cases ──
    print(f"\n{BOLD}{CYAN}Phase 1: Earning Creation — Edge Cases{RESET}")

    await run_nl(
        "I got 25000 from Samsung for 4 reels and 2 stories yesterday",
        ["add_earning"]
    )
    await run_nl(
        "barter deal with H&M, 3 posts, no money involved",
        ["add_earning"]
    )
    await run_nl(
        "earned 1.5 lakh from Reliance for a campaign last week",
        ["add_earning"]
    )
    await run_nl(
        "made 50k doing a collab with Mamaearth, 1 reel only, on 15th feb",
        ["add_earning"]
    )
    await run_nl(
        "got paid 7500 by boAt for 2 stories",
        ["add_earning"]
    )
    await run_nl(
        "collab with Nykaa, they gave me free products worth 3000, 1 reel",
        ["add_earning"]
    )

    # ── Phase 3: Expense edge cases ──
    print(f"\n{BOLD}{CYAN}Phase 2: Expense Creation — Edge Cases{RESET}")

    await run_nl(
        "I spent 8000 on a new ring light and tripod",
        ["add_expense"]
    )
    await run_nl(
        "paid 15000 to my video editor for the Nike shoot",
        ["add_expense"]
    )
    await run_nl(
        "spent 4500 on cab fare for the Mumbai shoot",
        ["add_expense"]
    )
    await run_nl(
        "bought a new microphone for 12000",
        ["add_expense"]
    )

    # ── Phase 4: Summary & query edge cases ──
    print(f"\n{BOLD}{CYAN}Phase 3: Summaries & Queries — Edge Cases{RESET}")

    await run_nl(
        "how much money have I made in total",
        ["get_financial_summary"]
    )
    await run_nl(
        "what were my earnings last month",
        ["get_financial_summary", "search_earnings"]
    )
    await run_nl(
        "show me all my Nike earnings",
        ["search_earnings"]
    )
    await run_nl(
        "how much did Kellogs pay me",
        ["search_earnings"]
    )
    await run_nl(
        "what is my net income this month",
        ["get_financial_summary"]
    )
    await run_nl(
        "how many barter deals have I done",
        ["search_earnings", "get_financial_summary"]
    )
    await run_nl(
        "list all my expenses",
        ["search_earnings", "get_financial_summary"]
    )
    await run_nl(
        "how much did I spend on equipment",
        ["search_earnings", "get_financial_summary"]
    )

    # ── Phase 5: Brand matching edge cases ──
    print(f"\n{BOLD}{CYAN}Phase 4: Brand Matching — Edge Cases{RESET}")

    await run_nl(
        "I earned 9000 from Kelloggs cereal for 2 reels",
        ["add_earning"]
    )
    await run_nl(
        "got 11000 from nike india for 3 stories",
        ["add_earning"]
    )
    await run_nl(
        "earned 7000 from adidas original for a reel",
        ["add_earning"]
    )

    # ── Phase 6: Delete/update edge cases ──
    print(f"\n{BOLD}{CYAN}Phase 5: Delete & Update — Edge Cases{RESET}")

    await run_nl(
        "delete the unknown brand entry",
        ["delete_earning"]
    )
    await run_nl(
        "remove the Lakme entry",
        ["delete_earning"]
    )
    await run_nl(
        "update the Zen earning amount to 5000",
        ["update_earning", "search_earnings"]
    )

    # ── Phase 7: Report generation ──
    print(f"\n{BOLD}{CYAN}Phase 6: Report Generation — Edge Cases{RESET}")

    await run_nl(
        "generate a PDF report for this month",
        ["generate_report"]
    )
    await run_nl(
        "send me an excel sheet of all my earnings",
        ["generate_report"]
    )
    await run_nl(
        "I need a pdf report for last month with charts",
        ["generate_report"]
    )

    # ── Phase 8: Ambiguous / tricky queries ──
    print(f"\n{BOLD}{CYAN}Phase 7: Ambiguous & Tricky Queries{RESET}")

    await run_nl(
        "hey",
        None  # No tool expected, just conversation
    )
    await run_nl(
        "thanks",
        None
    )
    await run_nl(
        "I earned something from a brand but I forgot the name, it was around 6000 rupees for a reel",
        ["add_earning"]
    )
    await run_nl(
        "what did I earn on 15th march",
        ["search_earnings"]
    )
    await run_nl(
        "show me earnings from the last 3 months",
        ["search_earnings", "get_financial_summary"]
    )
    await run_nl(
        "I spent 2000 on food during the shoot trip",
        ["add_expense"]
    )

    # ── Phase 9: Verify data integrity ──
    print(f"\n{BOLD}{CYAN}Phase 8: Data Integrity Check{RESET}")

    with db_manager.get_session() as db:
        all_earnings = crud.EarningCRUD.search(db, limit=100)
        result(True, f"Total earnings in DB: {len(all_earnings)}")
        for e in all_earnings:
            print(f"     {e.brand_name}: {format_currency(e.amount_earned)} | {e.payment_type.value} | {format_date(e.entry_date)} | R:{e.deliverables.get('reels',0)} S:{e.deliverables.get('stories',0)} P:{e.deliverables.get('posts',0)}")

        total = crud.EarningCRUD.get_total_earnings(db)
        result(True, f"Total earnings sum: {format_currency(total)}")

        deliverables = crud.EarningCRUD.get_deliverables_summary(db)
        result(True, f"Total deliverables: {deliverables}")

        expenses = crud.ExpenseCRUD.get_by_date_range(db, get_ist_today() - timedelta(days=365), get_ist_today())
        result(True, f"Total expenses: {len(expenses)}")
        for e in expenses:
            print(f"     {e.category.value}: {format_currency(e.amount)} | {format_date(e.expense_date)}")

    # ── Summary ──
    print(f"\n{BOLD}{'='*70}")
    print(f"  Results: {GREEN}{passed} passed{RESET}, "
          f"{RED}{failed} failed{RESET}")
    print(f"{'='*70}{RESET}\n")

    await llm_client.close()
    db_manager.close()
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
