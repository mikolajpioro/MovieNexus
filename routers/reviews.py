from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
import models
from database import get_db
from schemas import ReviewCreate, ReviewResponse, ReviewUpdate

from services.tmbd import get_movie_poster

from keys import url, image_url, api_key_
# "https://api.themoviedb.org/3"
base_url = url
# "https://image.tmdb.org/t/p/w500"
image_base_url = image_url
api_key = api_key_

router = APIRouter()

@router.get("", response_model=list[ReviewResponse])
async def get_reviews(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .order_by(models.Review.date_posted.desc())
        )
    reviews = result.scalars().all()
    return reviews
# GET ALL REVIEWS---------

# CREATE A NEW REVIEW---------
@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(review: ReviewCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == review.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    poster_data = await get_movie_poster(review.movie_title)
    fetched_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"

    new_review = models.Review(
        movie_title=review.movie_title,
        score=review.score,
        content=review.content,
        user_id=review.user_id,
        poster_url=fetched_url
    )
    db.add(new_review)
    await db.commit()
    await db.refresh(new_review, attribute_names=["author"])
    return new_review
# CREATE A NEW REVIEW---------

# GET A REVIEW BY ID----------
@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .where(models.Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    return review
# GET A REVIEW BY ID----------

# UPDATE A REVIEW FULLY----------
@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review_full(review_id: int, review_data: ReviewCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review).where(models.Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    if review_data.user_id != review.user_id:
        result = await db.execute(select(models.User).where(models.User.id == review_data.user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    if review_data.movie_title != review.movie_title:
        poster_data = await get_movie_poster(review_data.movie_title)
        fetched_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"
        
    review.movie_title = review_data.movie_title
    review.score = review_data.score
    review.content = review_data.content
    review.user_id = review_data.user_id
    review.poster_url = fetched_url
    
    await db.commit()
    await db.refresh(review)
    return review
# UPDATE A REVIEW FULLY----------

# UPDATE A REVIEW PARTIALLY----------
@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review_partial(review_id: int, review_data: ReviewUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(models.Review).options(selectinload(models.Review.author)).where(models.Review.id == review_id).options(joinedload(models.Review.author))
    review = await db.execute(stmt).scalars().first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
    update_data = review_data.model_dump(exclude_unset=True)
    title_change = "movie_title" in update_data and update_data["movie_title"] != review.movie_title

    for field, value in update_data.items():
        setattr(review, field, value)
    
    if title_change:
        poster_data = await get_movie_poster(update_data["movie_title"])
        review.poster_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"
    
    await db.commit()
    await db.refresh(review, attribute_names=["author"])
    return review
# UPDATE A REVIEW PARTIALLY----------

# DELETE A REVIEW--------------------
@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(review_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Review).where(models.Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    await db.delete(review)
    await db.commit()