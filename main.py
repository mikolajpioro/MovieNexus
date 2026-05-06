from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import requests, random

app = FastAPI()
app.mount("/static", StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

base_url = "https://api.themoviedb.org/3"
image_base_url = "https://image.tmdb.org/t/p/w500"
api_key = "d4b594c5c529eeb02d2c93543bc1907d"

reviews: list[dict] = [
    {
        "id": 1,
        "author": "John Ballsini",
        "movie_title": "Reservoir dogs",
        "score": "10/10",
        "content": "This movie is amazing. It has trurly changed my outlook on storytelling as a whole.",
        "date_posted": "July 20, 2025",
    },
    {
        "id": 2,
        "author": "Mr Wellers",
        "movie_title": "The swamps blood banks",
        "score": "1/10",
        "content": "This movie is terrible. I hope that ill be the only living being to have ever saw it.",
        "date_posted": "December 25, 2026",
    },
    {
        "id": 3,
        "author": "Arkadiusz Tymura",
        "movie_title": "Tenet",
        "score": "7/10",
        "content": "Wtf did I just watch?",
        "date_posted": "July 16, 2024",
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

@app.get("/", include_in_schema=False, name="home")
@app.get("/reviews", include_in_schema=False, name="home")
def home_page(request: Request):

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
    return None


@app.get("/api/reviews")
def get_reviews():
    return reviews