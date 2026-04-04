"""Database CRUD operations (Async)."""
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, delete, update
from .models import (
    Earning, Expense, BrandAlias, PaymentReminder,
    AuditLog, PaymentType, PaymentStatus, ExpenseCategory,
    OperationType, ReminderStatus, PendingConfirmation, utcnow
)


class EarningCRUD:
    """CRUD operations for Earnings."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        brand_name: str,
        amount_earned: float,
        payment_type: PaymentType,
        deliverables: Dict[str, int],
        entry_date: date,
        notes: Optional[str] = None,
        canonical_brand_id: Optional[int] = None
    ) -> Earning:
        """Create a new earning entry."""
        earning = Earning(
            brand_name=brand_name,
            amount_earned=amount_earned,
            payment_type=payment_type,
            deliverables=deliverables,
            entry_date=entry_date,
            notes=notes,
            canonical_brand_id=canonical_brand_id
        )
        db.add(earning)
        await db.flush()
        
        # Audit logging
        await AuditLogCRUD.create(
            db=db,
            operation_type=OperationType.CREATE,
            table_name="earnings",
            record_id=earning.id,
            new_values={
                "brand_name": brand_name,
                "amount_earned": amount_earned,
                "payment_type": payment_type.value,
                "deliverables": deliverables,
                "entry_date": entry_date.isoformat(),
                "notes": notes
            },
            success=True
        )
        
        return earning
    
    @staticmethod
    async def get_by_id(db: AsyncSession, earning_id: int) -> Optional[Earning]:
        """Get earning by ID."""
        stmt = select(Earning).where(Earning.id == earning_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_brand(db: AsyncSession, brand_name: str) -> List[Earning]:
        """Get all earnings for a brand."""
        stmt = select(Earning).where(
            func.lower(Earning.brand_name) == func.lower(brand_name)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_date_range(
        db: AsyncSession, 
        start_date: date, 
        end_date: date
    ) -> List[Earning]:
        """Get earnings within a date range."""
        stmt = select(Earning).where(
            and_(
                Earning.entry_date >= start_date,
                Earning.entry_date <= end_date
            )
        ).order_by(desc(Earning.entry_date))
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def update(
        db: AsyncSession, 
        earning_id: int, 
        **kwargs
    ) -> Optional[Earning]:
        """Update an earning entry."""
        earning = await EarningCRUD.get_by_id(db, earning_id)
        if not earning:
            return None
        
        # Store old values for audit log
        old_values = {
            "brand_name": earning.brand_name,
            "amount_earned": earning.amount_earned,
            "payment_type": earning.payment_type.value,
            "deliverables": earning.deliverables,
            "entry_date": earning.entry_date.isoformat(),
            "status": earning.status.value,
            "notes": earning.notes
        }
        
        for key, value in kwargs.items():
            if hasattr(earning, key):
                setattr(earning, key, value)

        earning.updated_at = utcnow()
        
        # Audit logging
        await AuditLogCRUD.create(
            db=db,
            operation_type=OperationType.UPDATE,
            table_name="earnings",
            record_id=earning.id,
            old_values=old_values,
            new_values={
                "brand_name": earning.brand_name,
                "amount_earned": earning.amount_earned,
                "payment_type": earning.payment_type.value,
                "deliverables": earning.deliverables,
                "entry_date": earning.entry_date.isoformat(),
                "status": earning.status.value,
                "notes": earning.notes
            },
            success=True
        )
        
        return earning
    
    @staticmethod
    async def delete(db: AsyncSession, earning_id: int) -> bool:
        """Delete an earning entry."""
        earning = await EarningCRUD.get_by_id(db, earning_id)
        if not earning:
            return False
        
        # Store values for audit log
        old_values = {
            "brand_name": earning.brand_name,
            "amount_earned": earning.amount_earned,
            "payment_type": earning.payment_type.value,
            "deliverables": earning.deliverables,
            "entry_date": earning.entry_date.isoformat(),
            "status": earning.status.value,
            "notes": earning.notes
        }
        
        await db.delete(earning)
        
        # Audit logging
        await AuditLogCRUD.create(
            db=db,
            operation_type=OperationType.DELETE,
            table_name="earnings",
            record_id=earning_id,
            old_values=old_values,
            success=True
        )
        
        return True
    
    @staticmethod
    async def search(
        db: AsyncSession,
        brand_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        payment_type: Optional[PaymentType] = None,
        status: Optional[PaymentStatus] = None,
        limit: Optional[int] = None
    ) -> List[Earning]:
        """Search earnings with multiple filters."""
        stmt = select(Earning)
        
        if brand_name:
            stmt = stmt.where(
                func.lower(Earning.brand_name).contains(func.lower(brand_name))
            )
        
        if start_date:
            stmt = stmt.where(Earning.entry_date >= start_date)
        
        if end_date:
            stmt = stmt.where(Earning.entry_date <= end_date)
        
        if payment_type:
            stmt = stmt.where(Earning.payment_type == payment_type)
        
        if status:
            stmt = stmt.where(Earning.status == status)
        
        stmt = stmt.order_by(desc(Earning.entry_date))
        
        if limit:
            stmt = stmt.limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_total_earnings(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> float:
        """Get total earnings for a period."""
        stmt = select(func.sum(Earning.amount_earned))

        if start_date:
            stmt = stmt.where(Earning.entry_date >= start_date)

        if end_date:
            stmt = stmt.where(Earning.entry_date <= end_date)

        result = await db.execute(stmt)
        val = result.scalar()
        return val if val else 0.0

    @staticmethod
    async def get_payment_type_breakdown(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, int]:
        """Get count of earnings by payment type (cash vs barter)."""
        stmt = select(Earning.payment_type, func.count(Earning.id))

        if start_date:
            stmt = stmt.where(Earning.entry_date >= start_date)

        if end_date:
            stmt = stmt.where(Earning.entry_date <= end_date)

        stmt = stmt.group_by(Earning.payment_type)
        result = await db.execute(stmt)
        return {pt.value: count for pt, count in result.all()}
    
    @staticmethod
    async def get_deliverables_summary(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, int]:
        """Get summary of deliverables for a period."""
        stmt = select(
            func.sum(func.json_extract(Earning.deliverables, '$.reels')),
            func.sum(func.json_extract(Earning.deliverables, '$.stories')),
            func.sum(func.json_extract(Earning.deliverables, '$.posts'))
        )

        if start_date:
            stmt = stmt.where(Earning.entry_date >= start_date)

        if end_date:
            stmt = stmt.where(Earning.entry_date <= end_date)

        result = await db.execute(stmt)
        row = result.first()

        return {
            'reels': int(row[0]) if row and row[0] else 0,
            'stories': int(row[1]) if row and row[1] else 0,
            'posts': int(row[2]) if row and row[2] else 0
        }


class ExpenseCRUD:
    """CRUD operations for Expenses."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        category: ExpenseCategory,
        amount: float,
        description: Optional[str] = None,
        expense_date: Optional[date] = None
    ) -> Expense:
        """Create a new expense entry."""
        if expense_date is None:
            from ..utils import get_ist_today
            expense_date = get_ist_today()
        
        expense = Expense(
            category=category,
            amount=amount,
            description=description,
            expense_date=expense_date
        )
        db.add(expense)
        await db.flush()
        
        # Audit logging
        await AuditLogCRUD.create(
            db=db,
            operation_type=OperationType.CREATE,
            table_name="expenses",
            record_id=expense.id,
            new_values={
                "category": category.value,
                "amount": amount,
                "description": description,
                "expense_date": expense_date.isoformat()
            },
            success=True
        )
        
        return expense
    
    @staticmethod
    async def get_by_id(db: AsyncSession, expense_id: int) -> Optional[Expense]:
        """Get expense by ID."""
        stmt = select(Expense).where(Expense.id == expense_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_date_range(
        db: AsyncSession,
        start_date: date,
        end_date: date
    ) -> List[Expense]:
        """Get expenses within a date range."""
        stmt = select(Expense).where(
            and_(
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date
            )
        ).order_by(desc(Expense.expense_date))
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_total_expenses(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> float:
        """Get total expenses for a period."""
        stmt = select(func.sum(Expense.amount))
        
        if start_date:
            stmt = stmt.where(Expense.expense_date >= start_date)
        
        if end_date:
            stmt = stmt.where(Expense.expense_date <= end_date)
        
        result = await db.execute(stmt)
        val = result.scalar()
        return val if val else 0.0
    
    @staticmethod
    async def get_expenses_by_category(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, float]:
        """Get expenses grouped by category."""
        stmt = select(
            Expense.category,
            func.sum(Expense.amount)
        )
        
        if start_date:
            stmt = stmt.where(Expense.expense_date >= start_date)
        
        if end_date:
            stmt = stmt.where(Expense.expense_date <= end_date)
        
        stmt = stmt.group_by(Expense.category)
        result = await db.execute(stmt)
        return {cat.value: total for cat, total in result.all()}


class BrandAliasCRUD:
    """CRUD operations for Brand Aliases."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        canonical_name: str,
        alias: str,
        confidence_score: float = 1.0,
        is_confirmed: bool = False
    ) -> BrandAlias:
        """Create a new brand alias."""
        brand_alias = BrandAlias(
            canonical_name=canonical_name,
            alias=alias,
            confidence_score=confidence_score,
            is_confirmed=is_confirmed
        )
        db.add(brand_alias)
        await db.flush()
        return brand_alias
    
    @staticmethod
    async def get_by_alias(db: AsyncSession, alias: str) -> Optional[BrandAlias]:
        """Get brand alias by alias name."""
        stmt = select(BrandAlias).where(
            func.lower(BrandAlias.alias) == func.lower(alias)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_aliases(db: AsyncSession, canonical_name: str) -> List[BrandAlias]:
        """Get all aliases for a canonical brand name."""
        stmt = select(BrandAlias).where(
            func.lower(BrandAlias.canonical_name) == func.lower(canonical_name)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


class PaymentReminderCRUD:
    """CRUD operations for Payment Reminders."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        earning_id: int,
        reminder_date: date,
        message: Optional[str] = None
    ) -> PaymentReminder:
        """Create a new payment reminder."""
        reminder = PaymentReminder(
            earning_id=earning_id,
            reminder_date=reminder_date,
            message=message
        )
        db.add(reminder)
        await db.flush()
        return reminder
    
    @staticmethod
    async def get_pending_reminders(db: AsyncSession, current_date: date) -> List[PaymentReminder]:
        """Get all pending reminders for current date."""
        stmt = select(PaymentReminder).where(
            and_(
                PaymentReminder.reminder_date <= current_date,
                PaymentReminder.status == ReminderStatus.PENDING
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def update_status(
        db: AsyncSession,
        reminder_id: int,
        status: ReminderStatus
    ) -> Optional[PaymentReminder]:
        """Update reminder status."""
        reminder = await db.get(PaymentReminder, reminder_id)
        if reminder:
            reminder.status = status
        return reminder


class AuditLogCRUD:
    """CRUD operations for Audit Log."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        operation_type: OperationType,
        table_name: str,
        record_id: Optional[int] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        user_message: Optional[str] = None,
        llm_response: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Create an audit log entry."""
        audit_log = AuditLog(
            operation_type=operation_type,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            user_message=user_message,
            llm_response=llm_response,
            success=success,
            error_message=error_message
        )
        db.add(audit_log)
        await db.flush()
        return audit_log


class PendingConfirmationCRUD:
    """CRUD operations for Persistent Confirmations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        confirmation_id: str,
        chat_id: int,
        operation: str,
        data: Dict[str, Any],
        ttl_minutes: int = 60
    ) -> PendingConfirmation:
        """Create a persistent confirmation state."""
        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        conf = PendingConfirmation(
            id=confirmation_id,
            chat_id=chat_id,
            operation=operation,
            data=data,
            expires_at=expires_at
        )
        db.add(conf)
        await db.flush()
        return conf

    @staticmethod
    async def get(db: AsyncSession, confirmation_id: str) -> Optional[PendingConfirmation]:
        """Get confirmation if not expired."""
        stmt = select(PendingConfirmation).where(
            and_(
                PendingConfirmation.id == confirmation_id,
                PendingConfirmation.expires_at > utcnow()
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, confirmation_id: str):
        """Delete confirmation."""
        stmt = delete(PendingConfirmation).where(PendingConfirmation.id == confirmation_id)
        await db.execute(stmt)

    @staticmethod
    async def cleanup_expired(db: AsyncSession):
        """Cleanup expired confirmations."""
        stmt = delete(PendingConfirmation).where(PendingConfirmation.expires_at <= utcnow())
        await db.execute(stmt)
