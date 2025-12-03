from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer) #Telegram id
    user_id = Column(Integer, primary_key=True, autoincrement=True)# database id
    username = Column(String(32))  # Может быть NULL
    name = Column(String(100), nullable=False)
    photo_path = Column(String(255), nullable=False)
    bio = Column(String(500), nullable=False)

class Swipes(Base):
    __tablename__ = 'swipes'
    id = Column(Integer, primary_key = True)
    swiper_id = Column(Integer, ForeignKey('users.id', ondelete = "CASCADE"), nullable = False)
    target_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)

    liked = Column(Boolean, nullable = False)

    # Уникальное ограничение: один пользователь может свайпнуть другого только один раз
    __table_args__ = (UniqueConstraint('swiper_id', 'target_id', name='unique_swipe'),)

class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key = True)
    user1_id = Column(Integer, ForeignKey('users.id', ondelete = "CASCADE"), nullable = False)
    user2_id = Column(Integer, ForeignKey('users.id', ondelete = "CASCADE"), nullable = False)

