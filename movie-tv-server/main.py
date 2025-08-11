#!/usr/bin/env python3

import asyncio
import os
from typing import Any, Sequence
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.types as types
from enhanced_api import EnhancedMovieAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the enhanced API
tmdb_api_key = os.getenv('TMDB_API_KEY')
omdb_api_key = os.getenv('OMDB_API_KEY')
trakt_client_id = os.getenv('TRAKT_CLIENT_ID')
trakt_client_secret = os.getenv('TRAKT_CLIENT_SECRET')

if not all([tmdb_api_key, omdb_api_key, trakt_client_id, trakt_client_secret]):
    raise ValueError("TMDB_API_KEY, OMDB_API_KEY, TRAKT_CLIENT_ID, and TRAKT_CLIENT_SECRET must be set in environment variables")

movie_api = EnhancedMovieAPI(tmdb_api_key, omdb_api_key, trakt_client_id, trakt_client_secret)

# Create a server instance
server = Server("enhanced-movie-tv-mcp")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List available tools.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        Tool(
            name="search_movies",
            description="Search for movies by title with optional year filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Movie title to search for",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional release year to filter results (e.g., 2021)",
                        "minimum": 1900,
                        "maximum": 2030,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_enhanced_movie_details",
            description="Get comprehensive movie details with ratings from multiple sources (TMDB, IMDb, Rotten Tomatoes, Metacritic)",
            inputSchema={
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "TMDB movie ID (get this from search_movies results)",
                    },
                },
                "required": ["movie_id"],
            },
        ),
        Tool(
            name="find_rating_mismatches",
            description="Find movies where critics and audiences have significantly different opinions - often indicates unique 'vibes'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'Batman', 'sci-fi', 'horror')",
                    },
                    "min_mismatch": {
                        "type": "number",
                        "description": "Minimum rating difference between critics and audiences (default: 2.0)",
                        "minimum": 1.0,
                        "maximum": 5.0,
                        "default": 2.0,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="find_vibe_movies",
            description="Find movies with similar vibe to a reference movie but modified by a specific attribute",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference_movie": {
                        "type": "string",
                        "description": "Reference movie title to base recommendations on",
                    },
                    "vibe_modifier": {
                        "type": "string",
                        "enum": ["accessible", "grounded", "cerebral", "crowd_pleasing", "challenging"],
                        "description": "How to modify the vibe: accessible (more mainstream), grounded (more realistic), cerebral (more thoughtful), crowd_pleasing (more entertaining), challenging (more complex)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recommendations to return (default: 10)",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": ["reference_movie", "vibe_modifier"],
            },
        ),
        Tool(
            name="get_mood_recommendations",
            description="Get movie recommendations based on mood and optional time context",
            inputSchema={
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": ["cozy", "energetic", "thoughtful", "comfort"],
                        "description": "Desired mood: cozy (warm/relaxing), energetic (exciting/upbeat), thoughtful (cerebral/meaningful), comfort (familiar/soothing)",
                    },
                    "time_context": {
                        "type": "string",
                        "enum": ["morning", "late_night", "weekend"],
                        "description": "Optional time context to refine recommendations",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recommendations to return (default: 10)",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": ["mood"],
            },
        ),
        Tool(
            name="find_rating_personality",
            description="Find movies with specific critic/audience relationship patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "personality_type": {
                        "type": "string",
                        "enum": ["critics_darling", "crowd_pleaser", "universal_acclaim", "cult_classic", "prestige_accessible"],
                        "description": "Rating personality: critics_darling (critics love, audiences lukewarm), crowd_pleaser (audiences love, critics lukewarm), universal_acclaim (everyone loves), cult_classic (low critics, high audience, older), prestige_accessible (awards + entertaining)",
                    },
                    "genre_filter": {
                        "type": "string",
                        "description": "Optional genre to filter results (e.g., 'Action', 'Drama', 'Comedy')",
                    },
                },
                "required": ["personality_type"],
            },
        ),
        Tool(
            name="analyze_movie_vibe",
            description="Provide deep vibe analysis of a specific movie including mood profile, accessibility, and viewing recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "TMDB movie ID to analyze",
                    },
                },
                "required": ["movie_id"],
            },
        ),
        Tool(
            name="get_trakt_trending",
            description="Get trending movies or shows from Trakt.tv with real user behavior data",
            inputSchema={
                "type": "object",
                "properties": {
                    "media_type": {
                        "type": "string",
                        "enum": ["movies", "shows"],
                        "description": "Type of media to get trending data for",
                        "default": "movies",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_enhanced_movie_with_trakt",
            description="Get comprehensive movie details including TMDB, OMDb, and Trakt user behavior data",
            inputSchema={
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "TMDB movie ID to analyze with Trakt data",
                    },
                },
                "required": ["movie_id"],
            },
        ),
        Tool(
            name="find_movies_by_trakt_vibe",
            description="Find movies from Trakt user lists that match specific vibe keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "vibe_keyword": {
                        "type": "string",
                        "description": "Vibe keyword to search for (e.g., 'cozy', 'dark', 'uplifting', 'mind-bending')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recommendations to return (default: 10)",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": ["vibe_keyword"],
            },
        ),
        Tool(
            name="get_trakt_genre_recommendations",
            description="Get movie recommendations from Trakt based on genre with optional vibe filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "genre": {
                        "type": "string",
                        "description": "Genre to search for (e.g., 'Action', 'Drama', 'Comedy')",
                    },
                    "vibe_filter": {
                        "type": "string",
                        "enum": ["cozy", "intense", "accessible", "cult"],
                        "description": "Optional vibe filter to apply to genre results",
                    },
                },
                "required": ["genre"],
            },
        ),
        Tool(
            name="search_tv_shows",
            description="Search for TV shows by name with optional year filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "TV show name to search for",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional first air date year to filter results",
                        "minimum": 1950,
                        "maximum": 2030,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_tv_details",
            description="Get comprehensive details about a specific TV show including seasons, episodes, cast, and streaming info",
            inputSchema={
                "type": "object",
                "properties": {
                    "tv_id": {
                        "type": "integer",
                        "description": "TMDB TV show ID (get this from search_tv_shows results)",
                    },
                },
                "required": ["tv_id"],
            },
        ),
        Tool(
            name="get_trending",
            description="Get trending movies or TV shows",
            inputSchema={
                "type": "object",
                "properties": {
                    "media_type": {
                        "type": "string",
                        "enum": ["movie", "tv", "all"],
                        "description": "Type of media to get trending for",
                        "default": "movie",
                    },
                    "time_window": {
                        "type": "string",
                        "enum": ["day", "week"],
                        "description": "Time window for trending",
                        "default": "week",
                    },
                },
                "required": [],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """
    Handle tool execution requests.
    """
    try:
        if name == "search_movies":
            query = arguments.get("query")
            year = arguments.get("year")
            result = movie_api.search_movies(query, year)

            if result and 'results' in result:
                response = f"Found {result['total_results']} results for '{query}'"
                if year:
                    response += f" from {year}"
                response += ":\n\n"

                for i, movie in enumerate(result['results'][:10], 1):
                    release_year = ""
                    if movie.get('release_date'):
                        release_year = f" ({movie['release_date'][:4]})"

                    response += f"{i}. {movie['title']}{release_year}\n"
                    response += f"   ID: {movie['id']}\n"
                    response += f"   Rating: {movie.get('vote_average', 'N/A')}/10\n"
                    if movie.get('overview'):
                        overview = movie['overview'][:100] + "..." if len(movie['overview']) > 100 else movie['overview']
                        response += f"   Overview: {overview}\n"
                    response += "\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No movies found for '{query}'")]

        elif name == "get_enhanced_movie_details":
            movie_id = arguments.get("movie_id")
            result = movie_api.get_enhanced_movie_details(movie_id)

            if result:
                response = f"Enhanced Details for: {result['title']}\n"
                response += "=" * 50 + "\n\n"

                # Basic info
                if result.get('release_date'):
                    response += f"Release Date: {result['release_date']}\n"
                if result.get('runtime'):
                    hours = result['runtime'] // 60
                    minutes = result['runtime'] % 60
                    response += f"Runtime: {hours}h {minutes}m\n"

                # Ratings
                ratings = result.get('enhanced_ratings', {})
                response += "\nRatings:\n"
                response += f"   TMDb: {ratings.get('tmdb', 'N/A')}/10\n"
                response += f"   IMDb: {ratings.get('imdb', 'N/A')}/10\n"
                response += f"   Rotten Tomatoes: {ratings.get('rotten_tomatoes', 'N/A')}%\n"
                response += f"   Metacritic: {ratings.get('metacritic', 'N/A')}/100\n"

                # Additional info
                if result.get('awards'):
                    response += f"\nAwards: {result['awards']}\n"
                if result.get('box_office'):
                    response += f"Box Office: {result['box_office']}\n"

                # Analysis
                if result.get('rating_analysis'):
                    response += f"\nRating Analysis: {result['rating_analysis']}\n"

                # Plot
                if result.get('detailed_plot'):
                    response += f"\nPlot: {result['detailed_plot']}\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"Movie with ID {movie_id} not found")]

        elif name == "find_rating_mismatches":
            query = arguments.get("query")
            min_mismatch = arguments.get("min_mismatch", 2.0)
            result = movie_api.find_rating_mismatches(query, min_mismatch)

            if result:
                response = f"Found {len(result)} rating mismatches for '{query}':\n\n"
                for mismatch in result:
                    response += f"Movie: {mismatch['title']}"
                    if mismatch['year']:
                        response += f" ({mismatch['year']})"
                    response += "\n"
                    response += f"   IMDb: {mismatch['imdb_rating']}/10\n"
                    response += f"   Rotten Tomatoes: {mismatch['rotten_tomatoes']}%\n"
                    response += f"   Mismatch Degree: {mismatch['mismatch_degree']} points\n"
                    response += f"   Analysis: {mismatch['analysis']}\n\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No significant rating mismatches found for '{query}'")]

        elif name == "find_vibe_movies":
            reference_movie = arguments.get("reference_movie")
            vibe_modifier = arguments.get("vibe_modifier")
            limit = arguments.get("limit", 10)
            result = movie_api.find_vibe_movies(reference_movie, vibe_modifier, limit)

            if result:
                response = f"Movies like '{reference_movie}' but more {vibe_modifier}:\n\n"
                for i, movie in enumerate(result, 1):
                    response += f"{i}. {movie['title']}"
                    if movie.get('release_date'):
                        response += f" ({movie['release_date'][:4]})"
                    response += f" (ID: {movie['id']})\n"
                    if movie.get('overview'):
                        overview = movie['overview'][:80] + "..." if len(movie['overview']) > 80 else movie['overview']
                        response += f"   {overview}\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No movies found like '{reference_movie}' with {vibe_modifier} modifier")]

        elif name == "get_mood_recommendations":
            mood = arguments.get("mood")
            time_context = arguments.get("time_context")
            limit = arguments.get("limit", 10)
            result = movie_api.get_mood_recommendations(mood, time_context, limit)

            if result:
                response = f"Mood recommendations for '{mood}'"
                if time_context:
                    response += f" ({time_context})"
                response += ":\n\n"

                for i, movie in enumerate(result, 1):
                    response += f"{i}. {movie['title']}"
                    if movie.get('release_date'):
                        response += f" ({movie['release_date'][:4]})"
                    response += f" (ID: {movie['id']})\n"
                    if movie.get('overview'):
                        overview = movie['overview'][:80] + "..." if len(movie['overview']) > 80 else movie['overview']
                        response += f"   {overview}\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No mood recommendations found for '{mood}'")]

        elif name == "find_rating_personality":
            personality_type = arguments.get("personality_type")
            genre_filter = arguments.get("genre_filter")
            result = movie_api.find_rating_personality(personality_type, genre_filter)

            if result:
                response = f"Movies with '{personality_type}' rating personality"
                if genre_filter:
                    response += f" in {genre_filter} genre"
                response += ":\n\n"

                for i, movie in enumerate(result, 1):
                    response += f"{i}. {movie['title']}"
                    if movie.get('release_date'):
                        response += f" ({movie['release_date'][:4]})"
                    response += f" (ID: {movie['id']})\n"
                    if movie.get('overview'):
                        overview = movie['overview'][:80] + "..." if len(movie['overview']) > 80 else movie['overview']
                        response += f"   {overview}\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No movies found with '{personality_type}' rating personality")]

        elif name == "analyze_movie_vibe":
            movie_id = arguments.get("movie_id")
            result = movie_api.analyze_movie_vibe(movie_id)

            if result:
                response = f"Vibe Analysis for: {result['title']}\n"
                response += "=" * 50 + "\n\n"

                response += f"Vibe Tags: {', '.join(result.get('vibe_tags', []))}\n"
                response += f"Mood Profile: {result.get('mood_profile', 'N/A')}\n"
                response += f"Best Viewing Time: {result.get('best_time', 'N/A')}\n"
                response += f"Rating Personality: {result.get('rating_personality', 'N/A')}\n"
                response += f"Accessibility Score: {result.get('accessibility_score', 'N/A')}/10\n"
                response += f"Prestige Score: {result.get('prestige_score', 'N/A')}/10\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"Could not analyze movie with ID {movie_id}")]

        elif name == "get_trakt_trending":
            media_type = arguments.get("media_type", "movies")
            limit = arguments.get("limit", 10)
            result = movie_api.get_trakt_trending(media_type, limit)

            if result:
                response = f"Trending {media_type} on Trakt.tv (based on real user behavior):\n\n"
                for i, item in enumerate(result[:limit], 1):
                    if media_type == "movies":
                        movie = item.get('movie', item)
                        title = movie.get('title', 'Unknown')
                        year = movie.get('year', '')
                        tmdb_id = movie.get('ids', {}).get('tmdb', 'N/A')
                        response += f"{i}. {title}"
                        if year:
                            response += f" ({year})"
                        response += f" (TMDB ID: {tmdb_id})\n"
                    else:
                        show = item.get('show', item)
                        title = show.get('title', 'Unknown')
                        year = show.get('year', '')
                        response += f"{i}. {title}"
                        if year:
                            response += f" ({year})"
                        response += "\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No trending {media_type} found on Trakt")]

        elif name == "get_enhanced_movie_with_trakt":
            movie_id = arguments.get("movie_id")
            result = movie_api.get_enhanced_movie_with_trakt(movie_id)

            if result:
                response = f"Enhanced Details with Trakt Data: {result['title']}\n"
                response += "=" * 60 + "\n\n"

                # Basic info
                if result.get('release_date'):
                    response += f"Release Date: {result['release_date']}\n"
                if result.get('runtime'):
                    hours = result['runtime'] // 60
                    minutes = result['runtime'] % 60
                    response += f"Runtime: {hours}h {minutes}m\n"

                # Multi-source ratings
                ratings = result.get('enhanced_ratings', {})
                response += "\nRatings:\n"
                response += f"   TMDb: {ratings.get('tmdb', 'N/A')}/10\n"
                response += f"   IMDb: {ratings.get('imdb', 'N/A')}/10\n"
                response += f"   Rotten Tomatoes: {ratings.get('rotten_tomatoes', 'N/A')}%\n"
                response += f"   Metacritic: {ratings.get('metacritic', 'N/A')}/100\n"

                # Trakt community data
                trakt_data = result.get('trakt_data', {})
                if trakt_data:
                    response += "\nTrakt Community Data:\n"

                    stats = trakt_data.get('stats', {})
                    if stats:
                        response += f"   Watchers: {stats.get('watchers', 'N/A')}\n"
                        response += f"   Plays: {stats.get('plays', 'N/A')}\n"
                        response += f"   Collectors: {stats.get('collectors', 'N/A')}\n"

                    sentiment = trakt_data.get('community_sentiment', {})
                    if sentiment:
                        response += f"   Community Sentiment: {sentiment.get('sentiment', 'N/A')}\n"
                        response += f"   User Vibe: {sentiment.get('user_vibe', 'N/A')}\n"
                        if sentiment.get('common_themes'):
                            response += f"   Common Themes: {', '.join(sentiment['common_themes'])}\n"

                # Awards and box office
                if result.get('awards'):
                    response += f"\nAwards: {result['awards']}\n"
                if result.get('box_office'):
                    response += f"Box Office: {result['box_office']}\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"Movie with ID {movie_id} not found")]

        elif name == "find_movies_by_trakt_vibe":
            vibe_keyword = arguments.get("vibe_keyword")
            limit = arguments.get("limit", 10)
            result = movie_api.find_movies_by_trakt_list_vibe(vibe_keyword, limit)

            if result:
                response = f"Movies with '{vibe_keyword}' vibe from Trakt community lists:\n\n"
                for i, movie in enumerate(result, 1):
                    title = movie.get('title', 'Unknown')
                    year = movie.get('year', '')
                    tmdb_id = movie.get('ids', {}).get('tmdb', 'N/A')
                    response += f"{i}. {title}"
                    if year:
                        response += f" ({year})"
                    response += f" (TMDB ID: {tmdb_id})\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No movies found with '{vibe_keyword}' vibe from Trakt lists")]

        elif name == "get_trakt_genre_recommendations":
            genre = arguments.get("genre")
            vibe_filter = arguments.get("vibe_filter")
            result = movie_api.get_trakt_genre_recommendations(genre, vibe_filter)

            if result:
                response = f"Trakt recommendations for {genre}"
                if vibe_filter:
                    response += f" with {vibe_filter} vibe"
                response += ":\n\n"

                for i, movie in enumerate(result, 1):
                    title = movie.get('title', 'Unknown')
                    year = movie.get('year', '')
                    tmdb_id = movie.get('ids', {}).get('tmdb', 'N/A')
                    response += f"{i}. {title}"
                    if year:
                        response += f" ({year})"
                    response += f" (TMDB ID: {tmdb_id})\n"
                    response += "\n"
                return [types.TextContent(type="text", text=response)]
            else:
                filter_text = f" with {vibe_filter} vibe" if vibe_filter else ""
                return [types.TextContent(type="text", text=f"No {genre} recommendations found{filter_text}")]

        elif name == "search_tv_shows":
            query = arguments.get("query")
            year = arguments.get("year")
            result = movie_api.search_tv_shows(query, year)

            if result and 'results' in result:
                response = f"Found {result['total_results']} TV show results for '{query}'"
                if year:
                    response += f" from {year}"
                response += ":\n\n"

                for i, show in enumerate(result['results'][:10], 1):
                    first_air_year = ""
                    if show.get('first_air_date'):
                        first_air_year = f" ({show['first_air_date'][:4]})"

                    response += f"{i}. {show['name']}{first_air_year}\n"
                    response += f"   ID: {show['id']}\n"
                    response += f"   Rating: {show.get('vote_average', 'N/A')}/10\n"
                    if show.get('overview'):
                        overview = show['overview'][:100] + "..." if len(show['overview']) > 100 else show['overview']
                        response += f"   Overview: {overview}\n"
                    response += "\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"No TV shows found for '{query}'")]

        elif name == "get_tv_details":
            tv_id = arguments.get("tv_id")
            result = movie_api.get_tv_details(tv_id)

            if result:
                response = f"TV Show Details: {result['name']}\n"
                response += "=" * 50 + "\n\n"

                if result.get('first_air_date'):
                    response += f"First Air Date: {result['first_air_date']}\n"
                if result.get('last_air_date'):
                    response += f"Last Air Date: {result['last_air_date']}\n"
                if result.get('number_of_seasons'):
                    response += f"Seasons: {result['number_of_seasons']}\n"
                if result.get('number_of_episodes'):
                    response += f"Episodes: {result['number_of_episodes']}\n"
                if result.get('vote_average'):
                    response += f"Rating: {result['vote_average']}/10\n"
                if result.get('genres'):
                    genres = [genre['name'] for genre in result['genres']]
                    response += f"Genres: {', '.join(genres)}\n"
                if result.get('overview'):
                    response += f"\nOverview: {result['overview']}\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text=f"TV show with ID {tv_id} not found")]

        elif name == "get_trending":
            media_type = arguments.get("media_type", "movie")
            time_window = arguments.get("time_window", "week")
            result = movie_api.get_trending(media_type, time_window)

            if result and 'results' in result:
                response = f"Trending {media_type}s this {time_window}:\n\n"

                for i, item in enumerate(result['results'][:10], 1):
                    title = item.get('title') or item.get('name', 'Unknown')
                    date_field = 'release_date' if 'title' in item else 'first_air_date'
                    date = item.get(date_field, '')
                    year = f" ({date[:4]})" if date else ""

                    response += f"{i}. {title}{year}\n"
                    response += f"   ID: {item['id']}\n"
                    response += f"   Rating: {item.get('vote_average', 'N/A')}/10\n"
                    response += f"   Popularity: {item.get('popularity', 'N/A')}\n"
                    if item.get('overview'):
                        overview = item['overview'][:100] + "..." if len(item['overview']) > 100 else item['overview']
                        response += f"   Overview: {overview}\n"
                    response += "\n"

                return [types.TextContent(type="text", text=response)]
            else:
                return [types.TextContent(type="text", text="No trending content found")]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

async def main():
    # Run the server using stdin/stdout streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="enhanced-movie-tv-mcp",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())