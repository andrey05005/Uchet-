from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    groups = relationship("DebtGroup", back_populates="user", cascade="all, delete-orphan")
    items = relationship("DebtItem", back_populates="user", cascade="all, delete-orphan")


class DebtGroup(Base):
    __tablename__ = "debt_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="groups")
    items = relationship("DebtItem", back_populates="group", cascade="all, delete-orphan")


class DebtItem(Base):
    __tablename__ = "debt_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("debt_groups.id"), nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="items")
    group = relationship("DebtGroup", back_populates="items")
