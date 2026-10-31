import os
import uuid
from typing import Optional

from fastapi import Depends, Request
from dotenv import load_dotenv
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy
)

from fastapi_users.db import SQLAlchemyUserDatabase
from app.db import User, get_user_db

load_dotenv()

SECRET = os.getenv("JWT_SECRET")
if not SECRET or len(SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be set to at least 32 characters")


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        del request
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        del token, request
        print(f"User {user.id} has requested a password reset.")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        del token, request
        print(f"Verification requested for user {user.id}.")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
