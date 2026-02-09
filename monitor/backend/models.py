from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Text,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, nullable=False, index=True)
    cik = Column(String, nullable=True)
    name = Column(String, nullable=False)
    sector = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    market_cap = Column(Float, nullable=True)
    tracking_tier = Column(String, default="inactive")  # watchlist | monitoring | inactive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    fundamentals = relationship("FundamentalsQuarterly", back_populates="company", cascade="all, delete-orphan")
    filings = relationship("SecFiling", back_populates="company", cascade="all, delete-orphan")
    scores = relationship("DilutionScore", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.ticker} ({self.name})>"


class FundamentalsQuarterly(Base):
    __tablename__ = "fundamentals_quarterly"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_period", name="uq_company_period"),
    )

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    fiscal_period = Column(String, nullable=False)  # e.g. "2024-Q3"
    fiscal_year = Column(Integer, nullable=True)
    quarter = Column(Integer, nullable=True)
    shares_outstanding_diluted = Column(Float, nullable=True)
    free_cash_flow = Column(Float, nullable=True)
    stock_based_compensation = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    cash_and_equivalents = Column(Float, nullable=True)

    company = relationship("Company", back_populates="fundamentals")

    def __repr__(self):
        return f"<Fundamentals {self.fiscal_period} for company_id={self.company_id}>"


class SecFiling(Base):
    __tablename__ = "sec_filings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    accession_number = Column(String, unique=True, nullable=False)
    filing_type = Column(String, nullable=False)
    filed_date = Column(Date, nullable=True)
    filing_url = Column(String, nullable=True)
    is_dilution_event = Column(Boolean, default=False)
    dilution_type = Column(String, nullable=True)  # atm | registered_direct | follow_on | convertible | pipe
    offering_amount_dollars = Column(Float, nullable=True)

    company = relationship("Company", back_populates="filings")

    def __repr__(self):
        return f"<SecFiling {self.filing_type} {self.accession_number}>"


class DilutionScore(Base):
    __tablename__ = "dilution_scores"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    score_date = Column(Date, default=date.today)

    # Composite
    composite_score = Column(Float, nullable=False)

    # Sub-scores (0-100)
    share_cagr_score = Column(Float, nullable=True)
    fcf_burn_score = Column(Float, nullable=True)
    sbc_revenue_score = Column(Float, nullable=True)
    offering_freq_score = Column(Float, nullable=True)
    cash_runway_score = Column(Float, nullable=True)
    atm_active_score = Column(Float, nullable=True)

    # Underlying metrics
    share_cagr_3y = Column(Float, nullable=True)
    fcf_burn_rate = Column(Float, nullable=True)
    sbc_revenue_pct = Column(Float, nullable=True)
    offering_count_3y = Column(Integer, nullable=True)
    cash_runway_months = Column(Float, nullable=True)
    atm_program_active = Column(Boolean, nullable=True)
    price_change_12m = Column(Float, nullable=True)  # trailing 12-month split-adjusted return

    company = relationship("Company", back_populates="scores")

    def __repr__(self):
        return f"<DilutionScore {self.composite_score:.1f} for company_id={self.company_id}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=True)
    ticker = Column(String, nullable=True, index=True)  # NULL = global chat
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    def __repr__(self):
        return f"<Conversation {self.id} ticker={self.ticker}>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.role} in conv={self.conversation_id}>"


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    note_type = Column(String, default="note")  # "note" | "memo"
    ticker = Column(String, nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Note {self.id} type={self.note_type} ticker={self.ticker}>"
