from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key = True, autoincrement=False) #tg user_id
    name = Column(String, nullable = False)
    photo_path = Column(String, nullable = False)
    bio = Column(String, nullable = False)

class Swipes(Base):
    __tablename__ = 'swipes'
    id = Column(Integer, primary_key = True)
    swiper_id = Column(Integer, ForeignKey('user.id', ondelete = "CASCADE"), nullable = False)
    target_id = Column(Integer, ForeignKey('user.id', ondelete="CASCADE"), nullable=False)

    liked = Column(Boolean, nullable = False)

class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key = True)
    user1_id = Column(Integer, ForeignKey('user.id', ondelete = "CASCADE"), nullable = False)
    user2_id = Column(Integer, ForeignKey('user.id', ondelete = "CASCADE"), nullable = False)

