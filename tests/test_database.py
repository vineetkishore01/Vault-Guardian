"""Tests for database operations (async)."""
import pytest
import asyncio
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.database.models import Base, Earning, Expense, BrandAlias, PaymentType, PaymentStatus, ExpenseCategory
from src.database.crud import EarningCRUD, ExpenseCRUD, BrandAliasCRUD


@pytest.fixture
async def db_session():
    """Create an async test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession)
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_earning(db_session):
    """Test creating an earning entry."""
    earning = await EarningCRUD.create(
        db=db_session,
        brand_name="Test Brand",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 2, "stories": 1, "posts": 0},
        entry_date=date.today()
    )

    assert earning.id is not None
    assert earning.brand_name == "Test Brand"
    assert earning.amount_earned == 5000.0
    assert earning.payment_type == PaymentType.CASH
    assert earning.deliverables == {"reels": 2, "stories": 1, "posts": 0}


@pytest.mark.asyncio
async def test_get_earning_by_id(db_session):
    """Test getting earning by ID."""
    earning = await EarningCRUD.create(
        db=db_session,
        brand_name="Test Brand",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 2, "stories": 1, "posts": 0},
        entry_date=date.today()
    )

    retrieved = await EarningCRUD.get_by_id(db_session, earning.id)

    assert retrieved is not None
    assert retrieved.id == earning.id
    assert retrieved.brand_name == "Test Brand"


@pytest.mark.asyncio
async def test_update_earning(db_session):
    """Test updating an earning entry."""
    earning = await EarningCRUD.create(
        db=db_session,
        brand_name="Test Brand",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 2, "stories": 1, "posts": 0},
        entry_date=date.today()
    )

    updated = await EarningCRUD.update(
        db=db_session,
        earning_id=earning.id,
        amount_earned=6000.0,
        status=PaymentStatus.RECEIVED
    )

    assert updated.amount_earned == 6000.0
    assert updated.status == PaymentStatus.RECEIVED


@pytest.mark.asyncio
async def test_delete_earning(db_session):
    """Test deleting an earning entry."""
    earning = await EarningCRUD.create(
        db=db_session,
        brand_name="Test Brand",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 2, "stories": 1, "posts": 0},
        entry_date=date.today()
    )

    result = await EarningCRUD.delete(db_session, earning.id)

    assert result is True

    retrieved = await EarningCRUD.get_by_id(db_session, earning.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_search_earnings(db_session):
    """Test searching earnings with filters."""
    await EarningCRUD.create(
        db=db_session,
        brand_name="Nike",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 2, "stories": 0, "posts": 0},
        entry_date=date.today()
    )

    await EarningCRUD.create(
        db=db_session,
        brand_name="Adidas",
        amount_earned=3000.0,
        payment_type=PaymentType.BARTER,
        deliverables={"reels": 0, "stories": 3, "posts": 1},
        entry_date=date.today()
    )

    results = await EarningCRUD.search(
        db=db_session,
        brand_name="Nike",
        payment_type=PaymentType.CASH
    )

    assert len(results) == 1
    assert results[0].brand_name == "Nike"


@pytest.mark.asyncio
async def test_create_expense(db_session):
    """Test creating an expense entry."""
    expense = await ExpenseCRUD.create(
        db=db_session,
        category=ExpenseCategory.VIDEO_EDITING,
        amount=2000.0,
        description="Video editing software"
    )

    assert expense.id is not None
    assert expense.category == ExpenseCategory.VIDEO_EDITING
    assert expense.amount == 2000.0
    assert expense.description == "Video editing software"


@pytest.mark.asyncio
async def test_get_total_earnings(db_session):
    """Test getting total earnings."""
    await EarningCRUD.create(
        db=db_session,
        brand_name="Brand A",
        amount_earned=5000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 1, "stories": 0, "posts": 0},
        entry_date=date.today()
    )

    await EarningCRUD.create(
        db=db_session,
        brand_name="Brand B",
        amount_earned=3000.0,
        payment_type=PaymentType.CASH,
        deliverables={"reels": 0, "stories": 2, "posts": 0},
        entry_date=date.today()
    )

    total = await EarningCRUD.get_total_earnings(db_session)

    assert total == 8000.0


@pytest.mark.asyncio
async def test_create_brand_alias(db_session):
    """Test creating a brand alias."""
    alias = await BrandAliasCRUD.create(
        db=db_session,
        canonical_name="Nike",
        alias="Nike India",
        confidence_score=0.95,
        is_confirmed=True
    )

    assert alias.id is not None
    assert alias.canonical_name == "Nike"
    assert alias.alias == "Nike India"
    assert alias.confidence_score == 0.95
    assert alias.is_confirmed is True
