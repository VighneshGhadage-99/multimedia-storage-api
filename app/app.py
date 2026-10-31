from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Post, User, create_db_and_tables, get_async_session
from app.images import imagekit
from app.schemas import (
    FeedPostResponse,
    FeedResponse,
    PostCreate,
    PostResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
import os
import uuid
import shutil
import tempfile
from app.users import auth_backend, fastapi_users, current_active_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)

app.include_router(
    fastapi_users.get_register_router(UserRead,UserCreate), prefix="/auth", tags=["auth"]  
) 

app.include_router(
    fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"]
)

app.include_router(
    fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"]    
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)



@app.post("/upload", response_model=PostResponse)
async def upload_post(
    file: UploadFile = File(...),
    caption: str = Form(""),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):

    temp_file_path=None
    file_name = file.filename or "upload"
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file_name)[1]
        ) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        with open(temp_file_path, "rb") as image_file:
            upload_result = imagekit.upload_file(
                file=image_file,
                file_name=file_name,
                options=UploadFileRequestOptions(
                    use_unique_file_name=True,
                    tags=["backend-upload"],
                ),
            )

        if upload_result.url:
            post_data = PostCreate(
                caption=caption,
                url=upload_result.url,
                file_type="video"
                if (file.content_type or "").startswith("video/")
                else "image",
                file_name=upload_result.name,
            )
            post = Post(
                **post_data.model_dump(),
                user_id=user.id,
                imagekit_file_id=upload_result.file_id,
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post
        raise HTTPException(status_code=502, detail="ImageKit upload returned no URL")
    except HTTPException:
        raise
    except Exception as e:
       
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}") 
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        file.file.close()

    
@app.get("/feed", response_model=FeedResponse)
async def get_feed(
    session: AsyncSession = Depends(get_async_session),user: User = Depends(current_active_user)
) -> dict[str, list[FeedPostResponse]]:
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.user))
        .order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()
    posts_data=[]
    for post in posts:
        posts_data.append(
            {
            "id": str(post.id),
            "user_id": str(post.user_id) if post.user_id else None,
            "caption": post.caption,
            "url": post.url,
            "file_type": post.file_type,
            "file_name": post.file_name,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
            "is_owner": post.user_id == user.id,
            "email": post.user.email if post.user else None
            }
        )
    return {"posts": posts_data}



@app.delete("/posts/{post_id}")
async def delete_post(post_id:str,session: AsyncSession = Depends(get_async_session),user: User = Depends(current_active_user)):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user.id:
            raise HTTPException(status_code=500, detail="You do not have permission to delete this post")

        if not post.imagekit_file_id:
            raise HTTPException(
                status_code=409,
                detail="This post has no ImageKit file ID and cannot be deleted remotely",
            )

        # Delete the file from ImageKit
        delete_result = imagekit.delete_file(file_id=post.imagekit_file_id)
        if delete_result.response_metadata.http_status_code != 204:
            raise HTTPException(status_code=502, detail="Failed to delete file from ImageKit")
        
        await session.delete(post)
        await session.commit()
        return {"detail": "Post deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting post: {str(e)}")