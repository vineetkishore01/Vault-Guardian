"""Database models for Vault Guardian."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    Enum, ForeignKey, Text, JSON, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


def utcnow():
    """Get current UTC time as naive datetime (for SQLAlchemy defaults)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PaymentType(enum.Enum):
    """Payment type enumeration."""
    CASH = "cash"
    BARTER = "barter"


class PaymentStatus(enum.Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    RECEIVED = "received"
    OVERDUE = "overdue"


class ReminderStatus(enum.Enum):
    """Reminder status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"


class OperationType(enum.Enum):
    """Audit log operation type."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class ExpenseCategory(enum.Enum):
    """Expense category enumeration."""
    VIDEO_EDITING = "video_editing"
    TRAVEL = "travel"
    EQUIPMENT = "equipment"
    OTHER = "other"


class Earning(Base):
    """Earning model for influencer collaborations."""
    __tablename__ = "earnings"
    
    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String(255), nullable=False, index=True)
    canonical_brand_id = Column(Integer, ForeignKey('brand_aliases.id'), nullable=True)
    amount_earned = Column(Float, nullable=False)
    payment_type = Column(Enum(PaymentType), nullable=False, default=PaymentType.CASH)
    deliverables = Column(JSON, nullable=False, default=lambda: {"reels": 0, "stories": 0, "posts": 0})
    entry_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    notes = Column(Text, nullable=True)
    
    # Relationships
    canonical_brand = relationship("BrandAlias", back_populates="earnings")
    reminders = relationship("PaymentReminder", back_populates="earning", cascade="all, delete-orphan")


class Expense(Base):
    """Expense model for tracking business expenses."""
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(Enum(ExpenseCategory), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    expense_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class BrandAlias(Base):
    """Brand alias model for handling brand name variations."""
    __tablename__ = "brand_aliases"
    
    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(255), nullable=False, index=True)
    alias = Column(String(255), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=1.0)
    is_confirmed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    earnings = relationship("Earning", back_populates="canonical_brand")


class PaymentReminder(Base):
    """Payment reminder model."""
    __tablename__ = "payment_reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    earning_id = Column(Integer, ForeignKey('earnings.id'), nullable=False)
    reminder_date = Column(Date, nullable=False, index=True)
    status = Column(Enum(ReminderStatus), nullable=False, default=ReminderStatus.PENDING)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    earning = relationship("Earning", back_populates="reminders")


class AuditLog(Base):
    """Audit log for tracking all database operations."""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    operation_type = Column(Enum(OperationType), nullable=False, index=True)
    table_name = Column(String(50), nullable=False, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    user_message = Column(Text, nullable=True)
    llm_response = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)


class APIRateLimitLog(Base):
    """API rate limit logging."""
    __tablename__ = "api_rate_limit_log"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(255), nullable=False)
    request_timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)


class PendingConfirmation(Base):
    """Pending confirmation model for persisting states across restarts."""
    __tablename__ = "pending_confirmations"

    id = Column(String(255), primary_key=True, index=True)
    chat_id = Column(Integer, nullable=False, index=True)
    operation = Column(String(100), nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)