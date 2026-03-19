from datetime import datetime, time
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Time, JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(Text, nullable=True)
    lang = Column(Text, nullable=False, default="EN")
    scan_mode = Column(Text, nullable=False, default="ALL")
    strategies = Column(JSON, nullable=False, default=["TRINITY", "PANIC", "2B"])
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    watchlists = relationship("UserWatchlist", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("UserSchedule", back_populates="user", cascade="all, delete-orphan")
    scan_logs = relationship("ScanLog", back_populates="user", cascade="all, delete-orphan")


class UserWatchlist(Base):
    __tablename__ = "user_watchlists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(Text, nullable=False)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="watchlists")


class UserSchedule(Base):
    __tablename__ = "user_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scan_time = Column(Time, nullable=False)
    is_paused = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="schedules")


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    triggered_by = Column(Text, nullable=False)
    tickers_count = Column(Integer, nullable=False, default=0)
    signals_found = Column(Integer, nullable=False, default=0)
    status = Column(Text, nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    report_text = Column(Text, nullable=True)

    user = relationship("User", back_populates="scan_logs")
