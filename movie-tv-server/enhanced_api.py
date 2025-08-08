import requests
import json
from typing import Dict, List, Optional
from datetime import datetime

class EnhancedMovieAPI:
    """Combined TMDB + OMDb API wrapper for enriched movie data"""

    def __init__(self, tmdb_api_key: str, omdb_api_key: str):
        self.tmdb_api_key = tmdb_api_key
        self.omdb_api_key = omdb_api_key

        # TMDB config
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"

        # OMDb config
        self.omdb_base_url = "http://www.omdbapi.com/"

    def _make_tmdb_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a request to the TMDB API"""
        if params is None:
            params = {}

        params['api_key'] = self.tmdb_api_key

        try:
            response = requests.get(f"{self.tmdb_base_url}/{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Failed to fetch data from TMDB: {str(e)}",
                "success": False
            }

    def _make_omdb_request(self, params: Dict) -> Dict:
        """Make a request to the OMDb API"""
        params['apikey'] = self.omdb_api_key

        try:
            response = requests.get(self.omdb_base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # OMDb returns {"Response": "False"} for errors
            if data.get("Response") == "False":
                return {
                    "error": data.get("Error", "Unknown OMDb error"),
                    "success": False
                }

            return {**data, "success": True}
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Failed to fetch data from OMDb: {str(e)}",
                "success": False
            }

    def search_movies(self, query: str, year: Optional[int] = None, page: int = 1) -> Dict:
        """Search for movies using TMDB (keeping existing functionality)"""
        params = {
            "query": query,
            "page": page,
            "include_adult": False
        }

        if year:
            params["year"] = year

        data = self._make_tmdb_request("search/movie", params)

        if "error" in data:
            return data

        movies = []
        for movie in data.get("results", [])[:10]:
            movies.append({
                "id": movie["id"],
                "title": movie["title"],
                "release_date": movie.get("release_date", "Unknown"),
                "overview": movie.get("overview", "No overview available")[:200] + "...",
                "vote_average": movie.get("vote_average", 0),
                "poster_url": f"{self.image_base_url}{movie['poster_path']}" if movie.get("poster_path") else None
            })

        return {
            "query": query,
            "total_results": data.get("total_results", 0),
            "movies": movies,
            "success": True
        }

    def get_enhanced_movie_details(self, movie_id: int) -> Dict:
        """Get movie details combining TMDB + OMDb data"""
        # Get TMDB data first
        tmdb_data = self._make_tmdb_request(f"movie/{movie_id}")

        if "error" in tmdb_data:
            return tmdb_data

        # Get OMDb data using IMDb ID if available
        omdb_data = {}
        imdb_id = tmdb_data.get("imdb_id")

        if imdb_id:
            omdb_response = self._make_omdb_request({"i": imdb_id, "plot": "full"})
            if omdb_response.get("success"):
                omdb_data = omdb_response

        # If no IMDb ID, try searching OMDb by title and year
        if not omdb_data and tmdb_data.get("title") and tmdb_data.get("release_date"):
            release_year = tmdb_data["release_date"][:4] if tmdb_data["release_date"] else None
            if release_year:
                omdb_response = self._make_omdb_request({
                    "t": tmdb_data["title"],
                    "y": release_year,
                    "plot": "full"
                })
                if omdb_response.get("success"):
                    omdb_data = omdb_response

        # Combine the data
        return self._combine_movie_data(tmdb_data, omdb_data)

    def _combine_movie_data(self, tmdb_data: Dict, omdb_data: Dict) -> Dict:
        """Combine TMDB and OMDb data into enriched movie details"""
        # Start with TMDB data processing (existing logic)
        movie_id = tmdb_data["id"]

        # Get cast and crew from TMDB
        credits_data = self._make_tmdb_request(f"movie/{movie_id}/credits")

        # Process cast (top 10)
        cast = []
        if credits_data and "cast" in credits_data:
            for actor in credits_data["cast"][:10]:
                cast.append({
                    "name": actor["name"],
                    "character": actor.get("character", "Unknown"),
                    "profile_url": f"{self.image_base_url}{actor['profile_path']}" if actor.get("profile_path") else None
                })

        # Process crew (key roles only)
        crew = {}
        if credits_data and "crew" in credits_data:
            for person in credits_data["crew"]:
                job = person.get("job", "")
                if job in ["Director", "Producer", "Executive Producer", "Screenplay", "Story", "Music"]:
                    if job not in crew:
                        crew[job] = []
                    crew[job].append(person["name"])

        # Format runtime
        runtime_formatted = "Unknown"
        if tmdb_data.get("runtime"):
            hours = tmdb_data["runtime"] // 60
            minutes = tmdb_data["runtime"] % 60
            runtime_formatted = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        # Base movie data from TMDB
        result = {
            "id": movie_id,
            "title": tmdb_data["title"],
            "tagline": tmdb_data.get("tagline", ""),
            "overview": tmdb_data.get("overview", "No overview available"),
            "release_date": tmdb_data.get("release_date", "Unknown"),
            "runtime": tmdb_data.get("runtime", 0),
            "runtime_formatted": runtime_formatted,
            "genres": [g["name"] for g in tmdb_data.get("genres", [])],
            "tmdb_rating": tmdb_data.get("vote_average", 0),
            "tmdb_vote_count": tmdb_data.get("vote_count", 0),
            "budget": tmdb_data.get("budget", 0),
            "revenue": tmdb_data.get("revenue", 0),
            "production_companies": [c["name"] for c in tmdb_data.get("production_companies", [])],
            "cast": cast,
            "crew": crew,
            "poster_url": f"{self.image_base_url}{tmdb_data['poster_path']}" if tmdb_data.get("poster_path") else None,
            "imdb_id": tmdb_data.get("imdb_id", ""),
            "success": True
        }

        # Enrich with OMDb data if available
        if omdb_data:
            # Add multiple rating sources
            result["ratings"] = {
                "tmdb": result["tmdb_rating"],
                "imdb": self._safe_float(omdb_data.get("imdbRating", "N/A")),
                "rotten_tomatoes": self._extract_rt_score(omdb_data.get("Ratings", [])),
                "metacritic": self._safe_int(omdb_data.get("Metascore", "N/A"))
            }

            # Add additional OMDb fields
            result["awards"] = omdb_data.get("Awards", "N/A")
            result["box_office"] = omdb_data.get("BoxOffice", "N/A")
            result["omdb_plot"] = omdb_data.get("Plot", "")
            result["rated"] = omdb_data.get("Rated", "N/A")
            result["writer"] = omdb_data.get("Writer", "N/A")
            result["language"] = omdb_data.get("Language", "N/A")
            result["country"] = omdb_data.get("Country", "N/A")

            # Calculate rating analysis
            result["rating_analysis"] = self._analyze_ratings(result["ratings"])
        else:
            # No OMDb data available
            result["ratings"] = {"tmdb": result["tmdb_rating"]}
            result["rating_analysis"] = "OMDb data not available"

        return result

    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert string to float"""
        try:
            return float(value) if value != "N/A" else None
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: str) -> Optional[int]:
        """Safely convert string to int"""
        try:
            return int(value) if value != "N/A" else None
        except (ValueError, TypeError):
            return None

    def _extract_rt_score(self, ratings_list: List[Dict]) -> Optional[int]:
        """Extract Rotten Tomatoes score from OMDb ratings"""
        for rating in ratings_list:
            if rating.get("Source") == "Rotten Tomatoes":
                score_str = rating.get("Value", "")
                if "%" in score_str:
                    try:
                        return int(score_str.replace("%", ""))
                    except ValueError:
                        pass
        return None

    def _analyze_ratings(self, ratings: Dict) -> str:
        """Analyze rating patterns to detect interesting insights"""
        analysis = []

        tmdb = ratings.get("tmdb")
        imdb = ratings.get("imdb")
        rt = ratings.get("rotten_tomatoes")
        metacritic = ratings.get("metacritic")

        # Check for critic vs audience splits
        if rt and imdb:
            rt_decimal = rt / 10.0  # Convert RT percentage to 1-10 scale
            imdb_score = imdb

            if abs(rt_decimal - imdb_score) > 2.0:
                if rt_decimal > imdb_score:
                    analysis.append("Critics loved it more than audiences")
                else:
                    analysis.append("Audiences loved it more than critics")

        # Check for exceptionally high/low scores
        if imdb and imdb >= 8.5:
            analysis.append("Highly acclaimed (IMDb 8.5+)")
        elif imdb and imdb <= 5.0:
            analysis.append("Poorly received (IMDb 5.0 or below)")

        if rt and rt >= 90:
            analysis.append("Critics' choice (90%+ on RT)")
        elif rt and rt <= 30:
            analysis.append("Critically panned (30% or below on RT)")

        return "; ".join(analysis) if analysis else "Standard rating distribution"

    def find_rating_mismatches(self, query: str, min_mismatch: float = 2.0) -> Dict:
        """Find movies where critics and audiences disagree significantly"""
        # First search for movies
        search_results = self.search_movies(query)

        if not search_results.get("success"):
            return search_results

        mismatches = []

        for movie in search_results["movies"][:5]:  # Check top 5 results
            enhanced_details = self.get_enhanced_movie_details(movie["id"])

            if enhanced_details.get("success") and "ratings" in enhanced_details:
                ratings = enhanced_details["ratings"]
                imdb = ratings.get("imdb")
                rt = ratings.get("rotten_tomatoes")

                if imdb and rt:
                    rt_decimal = rt / 10.0
                    mismatch = abs(rt_decimal - imdb)

                    if mismatch >= min_mismatch:
                        mismatches.append({
                            "title": enhanced_details["title"],
                            "id": enhanced_details["id"],
                            "imdb_score": imdb,
                            "rt_score": rt,
                            "mismatch_degree": round(mismatch, 1),
                            "analysis": enhanced_details["rating_analysis"]
                        })

        return {
            "query": query,
            "mismatches": sorted(mismatches, key=lambda x: x["mismatch_degree"], reverse=True),
            "success": True
        }

    # Keep existing methods for TV shows and trending (unchanged)
    def search_tv_shows(self, query: str, first_air_date_year: Optional[int] = None, page: int = 1) -> Dict:
        """Search for TV shows by name (unchanged from original)"""
        params = {
            "query": query,
            "page": page,
            "include_adult": False
        }

        if first_air_date_year:
            params["first_air_date_year"] = first_air_date_year

        data = self._make_tmdb_request("search/tv", params)

        if "error" in data:
            return data

        shows = []
        for show in data.get("results", [])[:10]:
            shows.append({
                "id": show["id"],
                "name": show["name"],
                "first_air_date": show.get("first_air_date", "Unknown"),
                "overview": show.get("overview", "No overview available")[:200] + "...",
                "vote_average": show.get("vote_average", 0),
                "poster_url": f"{self.image_base_url}{show['poster_path']}" if show.get("poster_path") else None
            })

        return {
            "query": query,
            "total_results": data.get("total_results", 0),
            "shows": shows,
            "success": True
        }

    def get_trending(self, media_type: str = "movie", time_window: str = "week") -> Dict:
        """Get trending movies or TV shows (unchanged from original)"""
        if media_type not in ["movie", "tv", "all"]:
            return {"error": "media_type must be 'movie', 'tv', or 'all'", "success": False}

        if time_window not in ["day", "week"]:
            return {"error": "time_window must be 'day' or 'week'", "success": False}

        data = self._make_tmdb_request(f"trending/{media_type}/{time_window}")

        if "error" in data:
            return data

        trending_items = []
        for item in data.get("results", [])[:10]:
            title = item.get("title") or item.get("name", "Unknown Title")
            release_date = item.get("release_date") or item.get("first_air_date", "Unknown")

            trending_items.append({
                "id": item["id"],
                "title": title,
                "media_type": item.get("media_type", media_type),
                "release_date": release_date,
                "overview": item.get("overview", "No overview available")[:200] + "...",
                "vote_average": item.get("vote_average", 0),
                "poster_url": f"{self.image_base_url}{item['poster_path']}" if item.get("poster_path") else None
            })

        return {
            "media_type": media_type,
            "time_window": time_window,
            "trending": trending_items,
            "success": True
        }