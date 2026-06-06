from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import sqlalchemy
import requests, random
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# model imports--------
import models
from database import Base, engine, get_db
# model imports--------

# schema imports--------
from schemas import ReviewCreate, ReviewResponse, UserCreate, UserResponse, ReviewUpdate
# schema imports--------

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory='static'), name='static')
app.mount("/media", StaticFiles(directory='media'), name='media')
templates = Jinja2Templates(directory='templates')

from keys import url, image_url, api_key_
# "https://api.themoviedb.org/3"
base_url = url
# "https://image.tmdb.org/t/p/w500"
image_base_url = image_url
api_key = api_key_


def get_random_movie():
    random_page = random.randint(1, 500)
    
    url = f"{base_url}/discover/movie"
    params = {
        "api_key": api_key,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": random_page
    }

    response = requests.get(url, params=params)

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

def get_movie_poster(movie_title: str):
    url = f"{base_url}/search/movie"

    params = {
        "api_key": api_key,
        "language": "en-US",
        "query": movie_title,
        "page": 1,
        "include_adult": "false"
    }

    try:
        response = requests.get(url, params=params)

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
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review))
    reviews = result.scalars().all()

    random_movies = []
    while len(random_movies) < 3:
        movie = get_random_movie()
        if movie not in random_movies:
            random_movies.append(movie)
    
    for review in reviews:
        if not review.poster_url or review.poster_url == "/static/defaultposter.jpg":
            poster_data = get_movie_poster(review.movie_title)
            if poster_data and poster_data.get("poster"):
                review.poster_url = poster_data["poster"]
                db.add(review)
    
    db.commit()

    return templates.TemplateResponse(
        request,
        "home.html",
        {"reviews": reviews, "movies": random_movies, "title": "Home"}
    )

@app.get("/reviews/{review_id}", include_in_schema=False, name="review_page")
def review_page(request: Request, review_id: int, db:Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review).where(models.Review.id == review_id))
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
def user_reviews(request: Request, user_id: int, db:Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review).where(models.Review.user_id == user_id))
    reviews = result.scalars().all()
    
    if reviews:
        title = f"{reviews[0].author.username}'s reviews"
        return templates.TemplateResponse(request, "users_reviews.html", {"reviews": reviews, "title": title})
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Couldn't find this user's reviews"
        )

# api endpoints----------------------

# NEW USER CREATION---------
@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user already exists"
        )
    
    result = db.execute(select(models.User).where(models.User.email == user.email))
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
    db.commit()
    db.refresh(new_user)
    return new_user
# NEW USER CREATION---------

# GET A USER BY ID----------
@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db:Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.id == user_id))
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
def get_users_reviews(user_id: int, db:Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    result = db.execute(select(models.Review).where(models.Review.user_id == user_id))
    reviews = result.scalars().all()
    return reviews
# GET REVIEWS CREATED BY A USER---------


# GET ALL REVIEWS---------
@app.get("/api/reviews", response_model=list[ReviewResponse])
def get_reviews(db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review))
    reviews = result.scalars().all()
    return reviews
# GET ALL REVIEWS---------

# CREATE A NEW REVIEW---------
@app.post("/api/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(review: ReviewCreate, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(select(models.User).where(models.User.id == review.user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    poster_data = get_movie_poster(review.movie_title)
    fetched_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"

    new_review = models.Review(
        movie_title=review.movie_title,
        score=review.score,
        content=review.content,
        user_id=review.user_id,
        poster_url=fetched_url
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    
    stmt = select(models.Review).where(models.Review.id == new_review.id).options(joinedload(models.Review.author))
    return db.execute(stmt).scalars().first()
# CREATE A NEW REVIEW---------

# GET A REVIEW BY ID----------
@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review).where(models.Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    return review
# GET A REVIEW BY ID----------

@app.put("/api/reviews/{review_id}", response_model=ReviewResponse)
def update_review_full(review_id: int, review_data: ReviewCreate, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Review).where(models.Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )
    if review_data.user_id != review.user_id:
        result = db.execute(select(models.User).where(models.User.id == review_data.user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    poster_data = get_movie_poster(review_data.movie_title)
    fetched_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"
        
    review.movie_title = review_data.movie_title
    review.score = review_data.score
    review.content = review_data.content
    review.poster_url = fetched_url
    
    db.commit()
    db.refresh(review)
    return review



#error routes------------------
@app.exception_handler(StarletteHTTPException)
def general_https_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error has occured. Please try again."
    )

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code = exception.status_code,
            content = {"detail": message},
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
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            content = {"detail": exception.errors()}
        )
    
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