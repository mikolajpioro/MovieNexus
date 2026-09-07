from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from PIL import UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from image_utils import delete_profile_image, process_profile_image

from keys import url, image_url, api_key_
# "https://api.themoviedb.org/3"
base_url = url
# "https://image.tmdb.org/t/p/w500"
image_base_url = image_url
api_key = api_key_

import models
from database import get_db
from schemas import ReviewResponse, UserCreate, UserPrivate, UserPublic, UserUpdate, Token
from auth import create_access_token, hash_password, verify_password, CurrentUser
from config import settings

router = APIRouter()

# CREATE USER---------------------------
@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.lower()))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user already exists"
        )
    
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.lower()))
    
    exisisting_email = result.scalars().first()
    if exisisting_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this e-mail already exists"
        )
    
    new_user = models.User(
        username = user.username,
        email = user.email.lower(),
        password_hash=hash_password(user.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
# CREATE USER---------------------------

# LOGIN---------------------------------
# OAuth2PasswordRequestForm uses "username" field but we treat it as email
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.User)
        .where(func.lower(models.User.email) == form_data.username.lower())
    )

    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # create access token with user id as subject
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")
# LOGIN---------------------------------

# GET CURRENT USER----------------------
@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    return current_user
# GET CURRENT USER----------------------

# GET A USER BY ID----------
@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found"
        )
    else:
        return user
# GET A USER BY ID----------

# GET REVIEWS CREATED BY A USER---------
@router.get("/{user_id}/reviews", response_model=list[ReviewResponse])
async def get_user_reviews(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id) == user_id)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .where(models.Review.user_id == user_id)
        .order_by(models.Review.date_posted.desc())
    )
    reviews = result.scalars().all()
    return reviews
# GET REVIEWS CREATED BY A USER---------

# UPDATE USER PARTIALLY----------------
@router.patch("/{user_id}", response_model=UserPrivate)
async def update_user(user_id: int, current_user: CurrentUser, user_update: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):

    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user_update.username is not None and user_update.username.lower() != user.username.lower():
        result = await db.execute(select(models.User)
            .where(func.lower(models.User.username) == user_update.username.lower())
        )
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
    if user_update.email is not None and user_update.email.lower() != user.email.lower():
        result = await db.execute(select(models.User)
            .where(func.lower(models.User.email) == user_update.email.lower())
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already taken"
            )
  
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    
    await db.commit()
    await db.refresh(user)
    return user
# UPDATE USER PARTIALLY----------------

# DELETE USER---------------------------
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):

    if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this user"
            )

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
# DELETE USER---------------------------

# PROFILE PICTURE UPLOAD---------------------------
@router.patch("/{user_id}/picture", response_model=UserPrivate)
async def upload_profile_picture(user_id: int, file: UploadFile, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if current_user.id != user_id:
       raise HTTPException(
           status_code=status.HTTP_403_FORBIDDEN,
           detail="Not authorized to update this user's picture",
       ) 
   
    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size_bytes // (1025 * 1024)} MB",
        )

    try:
        new_filename = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. You can only upload in these formats (JPEG, PNG, GIF, WebP)"
        ) from err

    old_filename = current_user.image_file

    current_user.image_file = new_filename
    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        delete_profile_image(old_filename)

    return current_user
# PROFILE PICTURE UPLOAD---------------------------

# PROFILE PICTURE DELETION---------------------------
@router.delete("/{user_id}/pictures", response_model=UserPrivate)
async def delete_profile_picture(user_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    if current_user != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to delete this user's picture"
        )

    old_filename = current_user.image_file

    if old_filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete"
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)

    return current_user
# PROFILE PICTURE DELETION---------------------------