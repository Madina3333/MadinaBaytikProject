from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, autoincrement=True)# database id
    id = Column(Integer) #Telegram id
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


async def print_all_users(database_url: str):
    """
    Выводит всю информацию только о пользователях из таблицы 'users'.
    """
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()

    if not users:
        print("Нет пользователей в базе данных.")
        return

    print("=== СПИСОК ПОЛЬЗОВАТЕЛЕЙ ===")
    res = []
    for u in users:
        print(f"🔸 user_id: {u.user_id}")
        print(f"   id:       {u.id}")
        print(f"   Имя:                    {u.name}")
        print(f"   Username:               {u.username or '—'}")
        print(f"   Фото:                   {u.photo_path}")
        print(f"   О себе:                 {u.bio}")
        print("-" * 50)

        res.append({
            "user_id": u.user_id,
            "bio": u.bio
        })

    return res

#словарь отправляется гпт, тот подбирает 10 рекомендованных био и отправляет user_id и отправляет поочередно пользователю черезз бд по этим user_id

async def main():
    await print_all_users("sqlite+aiosqlite:///data.db")

asyncio.run(main())