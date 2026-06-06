from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr = Field(max_length=100)

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_file: str | None
    image_path: str

class ReviewBase(BaseModel):
    movie_title: str = Field(min_length=1, max_length=100)
    score: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)

class ReviewCreate(ReviewBase):
    user_id: int

class ReviewUpdate(BaseModel):
    movie_title: str | None = Field(default=None, min_length=1, max_length=100)
    score: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1)

class ReviewResponse(ReviewBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date_posted: datetime
    poster_url: Optional[str] = None
    user_id: int
    author: UserResponse