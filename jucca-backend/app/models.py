from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="seller")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BlacklistedKeyword(Base):
    __tablename__ = "policy_blacklisted_keywords"
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, unique=True, index=True)
    severity = Column(String, default="high")
    scope = Column(String, default="global")
    description = Column(Text, nullable=True)

class RestrictedBrand(Base):
    __tablename__ = "policy_restricted_brands"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String, unique=True, index=True)
    category = Column(String, nullable=True)
    country = Column(String, nullable=True)
    status = Column(String, default="restricted")
    condition = Column(Text, nullable=True)

class ProhibitedProduct(Base):
    __tablename__ = "policy_prohibited_products"
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True)
    category = Column(String, nullable=True)
    country = Column(String, nullable=True)
    status = Column(String, default="prohibited")
    notes = Column(Text, nullable=True)

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    user_id = Column(Integer, nullable=True)
    question = Column(Text)
    decision = Column(String)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
