# models.py
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    JSON, Integer
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    username = Column(String(32))
    name = Column(String(100), nullable=False)
    photo_path = Column(String(255), nullable=False)
    bio = Column(String(500), nullable=False)
    interests = Column(String(500))


class Swipes(Base):
    __tablename__ = 'swipes'
    id = Column(Integer, primary_key=True, autoincrement=True)  # ← INTEGER + autoincrement
    swiper_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    target_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    liked = Column(Boolean, nullable=False)
    __table_args__ = (UniqueConstraint('swiper_id', 'target_id', name='unique_swipe'),)

class Match(Base):
    __tablename__ = 'matches'
    id = Column(Integer, primary_key=True, autoincrement=True)  # ← тоже INTEGER
    user1_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    user2_id = Column(BigInteger, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id', name='unique_match'),)