from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr = Field(max_length=100)

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    image_file: str | None
    image_path: str

class UserPrivate(UserPublic):
    email: EmailStr


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: str | None = Field(default=None, max_length=100)
    image_file : str | None = Field(default=None, min_length=1, max_length=50)

class Token(BaseModel):
    access_token: str
    token_type: str

class ReviewBase(BaseModel):
    movie_title: str = Field(min_length=1, max_length=100)
    score: str | None = Field(default=None, min_length=1, max_length=10)
    content: str = Field(min_length=1)

class ReviewCreate(ReviewBase):
    user_id: int

class ReviewResponse(ReviewBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date_posted: datetime
    poster_url: Optional[str] = None
    user_id: int
    author: UserPublic

class ReviewUpdate(BaseModel):
    movie_title: str | None = Field(default=None, min_length=1, max_length=100)
    score: str | None = Field(default=None, min_length=1, max_length=10)
    content: str | None = Field(default=None, min_length=1)