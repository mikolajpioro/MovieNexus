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
from sqlalchemy.orm import session

import models
from database import Base, engine, get_db

from schemas import ReviewCreate, ReviewResponse, UserCreate, UserResponse

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


reviews: list[dict] = [
    {
        "id": 1,
        "author": "John Ballsini",
        "movie_title": "Reservoir dogs",
        "score": "10/10",
        "content": "This movie is amazing. It has trurly changed my outlook on storytelling as a whole.",
        "date_posted": "July 20, 2025",
        "poster_url": "/static/defaultposter.jpg",
    },
    {
        "id": 2,
        "author": "Mr Wellers",
        "movie_title": "The swamps blood banks",
        "score": "1/10",
        "content": "This movie is terrible. I hope that ill be the only living being to have ever saw it.",
        "date_posted": "December 25, 2026",
        "poster_url": "/static/defaultposter.jpg",
    },
    {
        "id": 3,
        "author": "Arkadiusz Tymura",
        "movie_title": "Gorgeous",
        "score": "7/10",
        "content": "Wtf did I just watch?",
        "date_posted": "July 16, 2024",
        "poster_url": "/static/defaultposter.jpg",
    }
]

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
@app.get("/reviews", include_in_schema=False, name="home")
def home_page(request: Request):

    for review in reviews:
        poster_data = get_movie_poster(review["movie_title"])
        if poster_data and poster_data.get("poster"):
            review["poster_url"] = poster_data["poster"]
        else:
            review["poster_url"] = "/static/defaultposter.jpg"

    random_movies = []
    while len(random_movies) < 3:
        movie = get_random_movie()
        if movie not in random_movies:
            random_movies.append(movie)
    
    return templates.TemplateResponse(request, "home.html", {"reviews": reviews, "title": "Home page", "movies": random_movies})

@app.get("/reviews/{review_id}", include_in_schema=False, name="review_page")
def review_page(request: Request, review_id: int):
    for review in reviews:
        if review.get("id") == review_id:
            title = f"{review['author']}'s review"
            return templates.TemplateResponse(request, "review.html", {"review": review, "title": title})
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not found"
    )



# api endpoints---------------
@app.get("/api/reviews", response_model=list[ReviewResponse])
def get_reviews():
    return reviews

@app.post("/api/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(review: ReviewCreate):
    max_id = 0
    for r in reviews:
        if r["id"] > max_id:
            max_id = r["id"]
    new_id = max_id + 1

    poster_data = get_movie_poster(review.movie_title)
    fetched_url = poster_data.get("poster") if poster_data else "/static/defaultposter.jpg"

    new_review = {
        "id": new_id,
        "author": review.author,
        "movie_title": review.movie_title,
        "score": review.score,
        "content": review.content,
        "date_posted": "June 21, 2027",
        "poster_url": fetched_url
    }
    reviews.append(new_review)
    return new_review


@app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
def get_post(review_id: int):
    for review in reviews:
        if review.get("id") == review_id:
            return review
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not found"
    )



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