from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from fastapi_users.db import  SQLAlchemyUserDatabase,SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID


DATABASE_URL = "sqlite+aiosqlite:///./test.db"


class Base(DeclarativeBase):
    pass

class User(Base, SQLAlchemyBaseUserTableUUID):
    posts=relationship("Post", back_populates="user")


class Post(Base):
    __tablename__ = "posts"

    id = Column(GUID(), primary_key=True, default=uuid4)
    user_id = Column(GUID(), ForeignKey("user.id"), nullable=True)
    caption = Column(Text)
    url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    imagekit_file_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    user = relationship("User", back_populates="posts")

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        post_columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"] for column in inspect(sync_conn).get_columns("posts")
            }
        )
        if "user_id" not in post_columns:
            await conn.exec_driver_sql(
                "ALTER TABLE posts ADD COLUMN user_id CHAR(36) REFERENCES user(id)"
            )
        if "imagekit_file_id" not in post_columns:
            await conn.exec_driver_sql(
                "ALTER TABLE posts ADD COLUMN imagekit_file_id VARCHAR"
            )

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)