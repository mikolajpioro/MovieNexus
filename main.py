from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi.exception_handlers import request_validation_exception_handler
from services.tmbd import get_random_movie

# model and router imports----------
import models
from database import Base, engine, get_db
from routers import reviews, users
# model imports----------

async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory='static'), name='static')
app.mount("/media", StaticFiles(directory='media'), name='media')

templates = Jinja2Templates(directory='templates')

# routers----------
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
# routers----------

from keys import url, image_url, api_key_
# "https://api.themoviedb.org/3"
base_url = url
# "https://image.tmdb.org/t/p/w500"
image_base_url = image_url
api_key = api_key_

@app.get("/", include_in_schema=False, name="home")
@app.get("/reviews", include_in_schema=False, name="reviews")
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .order_by(models.Review.date_posted.desc())
    )
    reviews = result.scalars().all()

    random_movies = []
    while len(random_movies) < 3:
        movie = await get_random_movie()
        if movie not in random_movies:
            random_movies.append(movie)
    
    await db.commit()
    return templates.TemplateResponse(request, "home.html", {"reviews": reviews, "movies": random_movies, "title": "Home"})

@app.get("/reviews{review_id}", include_in_schema=False, name="review_page")
async def review_page(request: Request, review_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Review)
        .options(selectinload(models.Review.author))
        .where(models.Review.id == review_id)
    )
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
        .order_by(models.Review.date_posted.desc())
    )
    reviews = result.scalars().all()
    if reviews:
        title = f"{reviews[0].author.username}'s reviews"
    return templates.TemplateResponse(request, "users_reviews.html", {"reviews": reviews, "title": title})

# Register and Login -----------------
@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})

@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})
# Register and Login -----------------

#error routes-------------------
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
#error routes-------------------