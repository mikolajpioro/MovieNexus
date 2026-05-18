from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class ReviewBase(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    movie_title: str = Field(min_length=1, max_length=100)
    score: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date_posted: str
    poster_url: Optional[str] = None