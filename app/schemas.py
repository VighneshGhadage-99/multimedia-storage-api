from datetime import datetime
from uuid import UUID
from fastapi_users import schemas
from pydantic import BaseModel


class PostCreate(BaseModel):
    caption: str | None = None
    url: str
    file_type: str
    file_name: str


class PostResponse(BaseModel):
    id: UUID
    caption: str | None
    url: str
    file_type: str
    file_name: str
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class FeedPostResponse(PostResponse):
    user_id: UUID | None
    is_owner: bool
    email: str | None = None


class FeedResponse(BaseModel):
    posts: list[FeedPostResponse]


class UserRead(schemas.BaseUser[UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass