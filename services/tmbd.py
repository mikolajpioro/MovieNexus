import httpx, random
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