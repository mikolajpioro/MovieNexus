from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from contextlib import asynccontextmanager
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
import sqlalchemy
import httpx, random

# model imports----------
import models
from database import Base, engine, get_db
# model imports----------

# schema imports---------
from schemas import ReviewCreate, ReviewResponse, UserCreate, UserResponse, ReviewUpdate, UserUpdate
# schema imports---------

async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory='static'), name='static')
app.mount("/media", StaticFiles(directory='media'), name='media')
templates = Jinja2Templates(directory='templates')

from keys import url, image_url, api_key_
# "https://api.themoviedb.org/3"
base_url = url
# "https://image.tmdb.org/t/p/w500"
image_base_url = image_url
api_key = api_key_


async def get_random_movie():
    random_page = random.randint(1, 500)
    
    url = f"{base_url}/discover/movie"
    params = {
        "api_key": api_key,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": random_page
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results")
        
        if results:
            movie = random.choice(results)
            
            poster_path = movie.get("poster_path")
            return {
                "title": movie["title"],
                "id": movie["id"],
                "poster": f"{image_base_url}{poster_path}" if poster_path else None,
            }
    return None

async def get_movie_poster(movie_title: str):
    url = f"{base_url}/search/movie"

    params = {
        "api_key": api_key,
        "language": "en-US",
        "query": movie_title,
        "page": 1,
        "include_adult": "false"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results")

            if results:
                first_match = results[0]
                poster_path = first_match.get("poster_path")
                if poster_path:
                    return {
                        "poster": f"{image_base_url}{poster_path}"
                    }
    except Exception as ex:
        print(f"Failed to fetch the movie poster for {movie_title}")
        return None
    return None

@app.get("/", include_in_schema=False, name="home")
@app.get("/reviews", include_in_schema=False, name="reviews")
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        )
    reviews = result.scalars().all()

    random_movies = []
    while len(random_movies) < 3:
        movie = await get_random_movie()
        if movie not in random_movies:
            random_movies.append(movie)
    
    #-----OUTDATED------ 
    # for review in reviews:
    #     if not review.poster_url or review.poster_url == "/static/defaultposter.jpg":
    #         poster_data = get_movie_poster(review.movie_title)
    #         if poster_data and poster_data.get("poster"):
    #             review.poster_url = poster_data["poster"]
    #             db.add(review)
    #-----OUTDATED------ 
    
    await db.commit()

    return templates.TemplateResponse(
        request,
        "home.html",
        {"reviews": reviews, "movies": random_movies, "title": "Home"}
    )

@app.get("/reviews/{review_id}", include_in_schema=False, name="review_page")
async def review_page(request: Request, review_id: int, db:Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .where(models.Review.id == review_id))
    review = result.scalars().first()

    if review:
        title = f"{review.author.username}'s review"
        return templates.TemplateResponse(request, "review.html", {"review": review, "title": title})
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    
@app.get("/user_reviews/{user_id}", include_in_schema=False, name="user_reviews")
async def user_reviews(request: Request, user_id: int, db:Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
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
    )
    reviews = result.scalars().all()
    if reviews:
        title = f"{reviews[0].author.username}'s reviews"
    return templates.TemplateResponse(request, "users_reviews.html", {"reviews": reviews, "title": title})

# api endpoints----------------------
# NEW USER CREATION---------
@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user already exists"
        )
    
    result = await db.execute(select(models.User).where(models.User.email == user.email))
    exisisting_email = result.scalars().first()

    if exisisting_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this e-mail already exists"
        )
    
    new_user = models.User(
        username = user.username,
        email = user.email
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
# NEW USER CREATION---------

# GET A USER BY ID----------
@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db:Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if user:
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
# GET A USER BY ID----------

# GET REVIEWS CREATED BY A USER---------
@app.get("/api/users/{user_id}/reviews", response_model=list[ReviewResponse])
async def get_users_reviews(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User.where(models.User.id == user_id)))
    user = result.scalars.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .where(models.Review.user_id == user_id))
    reviews = result.scalars().all()
    return reviews
# GET REVIEWS CREATED BY A USER---------

# UPDATE USER PARTIALLY-----------------
@app.patch("/api/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user_update.username is not None and user_update.username != user.username:
        result = await db.execute(select(models.User).where(models.User.username == user_update.username))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )
    if user_update.email is not None and user_update.email != user.email:
        result = await db.execute(select(models.User).where(models.User.email == user_update.email))
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already taken"
            )
  
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return user
# UPDATE USER PARTIALLY-----------------

# DELETE USER---------------------------
@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
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

# GET ALL REVIEWS---------
@app.get("/api/reviews", response_model=list[ReviewResponse])
async def get_reviews(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        )
    reviews = result.scalars().all()
    return reviews
# GET ALL REVIEWS---------

# CREATE A NEW REVIEW---------
@app.post("/api/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
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
    
    stmt = select(models.Review).where(models.Review.id == new_review.id).options(joinedload(models.Review.author))
    return (await db.execute(stmt)).scalars().first()

# CREATE A NEW REVIEW---------

# GET A REVIEW BY ID----------
@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
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
@app.put("/api/reviews/{review_id}", response_model=ReviewResponse)
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
@app.patch("/api/reviews/{review_id}", response_model=ReviewResponse)
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
@app.delete("/api/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
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
# DELETE A REVIEW-------------------



#error routes------------------
@app.exception_handler(StarletteHTTPException)
async def general_https_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error has occured. Please try again."
    )

    message = (
        exception.detail
        if exception.detail
        else "An error has occured :("
    )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        status_code=exception.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)
    
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "detail": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request."
        },
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
    )