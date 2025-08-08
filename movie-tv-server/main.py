#!/usr/bin/env python3
"""
Enhanced Movie/TV MCP Server
Provides comprehensive movie and TV show information with multi-source ratings via TMDB + OMDb APIs
"""
import asyncio
import json
import os
from typing import Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
from mcp.types import Tool, TextContent
from dotenv import load_dotenv
from enhanced_api import EnhancedMovieAPI

# Load environment variables
load_dotenv()

# Initialize the MCP server
app = Server("enhanced-movie-tv-mcp")

# Global Enhanced Movie API instance
movie_api: Optional[EnhancedMovieAPI] = None

def get_movie_api() -> EnhancedMovieAPI:
    """Get or create Enhanced Movie API instance"""
    global movie_api

    if movie_api is None:
        tmdb_key = os.getenv('TMDB_API_KEY')
        omdb_key = os.getenv('OMDB_API_KEY')

        if not tmdb_key:
            raise ValueError("TMDB_API_KEY environment variable is required")

        if not omdb_key:
            raise ValueError("OMDB_API_KEY environment variable is required")

        movie_api = EnhancedMovieAPI(tmdb_key, omdb_key)

    return movie_api

@app.list_tools()
async def handle_list_tools():
    """List available movie/TV tools"""
    return [
        Tool(
            name="search_movies",
            description="Search for movies by title with optional year filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Movie title to search for"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional release year to filter results (e.g., 2021)",
                        "minimum": 1900,
                        "maximum": 2030
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_enhanced_movie_details",
            description="Get comprehensive movie details with ratings from multiple sources (TMDB, IMDb, Rotten Tomatoes, Metacritic)",
            inputSchema={
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "TMDB movie ID (get this from search_movies results)"
                    }
                },
                "required": ["movie_id"]
            }
        ),
        Tool(
            name="find_rating_mismatches",
            description="Find movies where critics and audiences have significantly different opinions - often indicates unique 'vibes'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'Batman', 'sci-fi', 'horror')"
                    },
                    "min_mismatch": {
                        "type": "number",
                        "description": "Minimum rating difference between critics and audiences (default: 2.0)",
                        "minimum": 1.0,
                        "maximum": 5.0,
                        "default": 2.0
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_tv_shows",
            description="Search for TV shows by name with optional year filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "TV show name to search for"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional first air date year to filter results",
                        "minimum": 1950,
                        "maximum": 2030
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_tv_details",
            description="Get comprehensive details about a specific TV show including seasons, episodes, cast, and streaming info",
            inputSchema={
                "type": "object",
                "properties": {
                    "tv_id": {
                        "type": "integer",
                        "description": "TMDB TV show ID (get this from search_tv_shows results)"
                    }
                },
                "required": ["tv_id"]
            }
        ),
        Tool(
            name="get_trending",
            description="Get trending movies or TV shows",
            inputSchema={
                "type": "object",
                "properties": {
                    "media_type": {
                        "type": "string",
                        "description": "Type of media to get trending for",
                        "enum": ["movie", "tv", "all"],
                        "default": "movie"
                    },
                    "time_window": {
                        "type": "string",
                        "description": "Time window for trending",
                        "enum": ["day", "week"],
                        "default": "week"
                    }
                },
                "required": []
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    """Handle tool execution"""
    try:
        api = get_movie_api()

        if name == "search_movies":
            query = arguments["query"]
            year = arguments.get("year")
            result = api.search_movies(query, year)

            if result.get('success'):
                if result['movies']:
                    response = f"**Search Results for '{query}'**"
                    if year:
                        response += f" **({year})**"
                    response += f"\n\nFound {result['total_results']} movies:\n\n"

                    for i, movie in enumerate(result['movies'], 1):
                        response += f"**{i}. {movie['title']}** ({movie['release_date'][:4] if movie['release_date'] != 'Unknown' else 'Unknown'})\n"
                        response += f"   Rating: {movie['vote_average']}/10\n"
                        response += f"   ID: {movie['id']}\n"
                        response += f"   Overview: {movie['overview']}\n\n"
                else:
                    response = f"No movies found for '{query}'"
                    if year:
                        response += f" from {year}"
            else:
                response = f"**Error searching movies**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "get_enhanced_movie_details":
            movie_id = arguments["movie_id"]
            result = api.get_enhanced_movie_details(movie_id)

            if result.get('success'):
                response = f"**{result['title']}**"
                if result['tagline']:
                    response += f"\n*{result['tagline']}*"

                response += f"\n\n**Basic Information:**\n"
                response += f"• **Release Date**: {result['release_date']}\n"
                response += f"• **Runtime**: {result['runtime_formatted']}\n"
                response += f"• **Genres**: {', '.join(result['genres'])}\n"

                # Multi-source ratings
                ratings = result.get('ratings', {})
                response += f"\n**Ratings from Multiple Sources:**\n"
                response += f"• **TMDB**: {ratings.get('tmdb', 'N/A')}/10\n"
                response += f"• **IMDb**: {ratings.get('imdb', 'N/A')}/10\n"
                response += f"• **Rotten Tomatoes**: {ratings.get('rotten_tomatoes', 'N/A')}%\n"
                response += f"• **Metacritic**: {ratings.get('metacritic', 'N/A')}/100\n"

                # Rating analysis
                if result.get('rating_analysis'):
                    response += f"• **Rating Analysis**: {result['rating_analysis']}\n"

                # Awards and Box Office
                if result.get('awards') and result['awards'] != 'N/A':
                    response += f"\n**Awards**: {result['awards']}\n"

                if result.get('box_office') and result['box_office'] != 'N/A':
                    response += f"**Box Office**: {result['box_office']}\n"

                if result['budget'] > 0:
                    response += f"**Budget**: ${result['budget']:,}\n"
                if result['revenue'] > 0:
                    response += f"**Revenue**: ${result['revenue']:,}\n"

                if result['crew']:
                    response += f"\n**Key Crew:**\n"
                    for role, people in result['crew'].items():
                        response += f"• **{role}**: {', '.join(people)}\n"

                if result['cast']:
                    response += f"\n**Main Cast:**\n"
                    for actor in result['cast'][:5]:
                        response += f"• {actor['name']} as {actor['character']}\n"

                if result['production_companies']:
                    response += f"\n**Production**: {', '.join(result['production_companies'])}\n"

                response += f"\n**Overview:**\n{result['overview']}"

                if result.get('omdb_plot') and result['omdb_plot'] != result['overview']:
                    response += f"\n\n**Detailed Plot:**\n{result['omdb_plot']}"
            else:
                response = f"**Error getting movie details**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "find_rating_mismatches":
            query = arguments["query"]
            min_mismatch = arguments.get("min_mismatch", 2.0)
            result = api.find_rating_mismatches(query, min_mismatch)

            if result.get('success'):
                if result['mismatches']:
                    response = f"**Rating Mismatches for '{query}'**\n"
                    response += f"(Looking for {min_mismatch}+ point differences between critics and audiences)\n\n"

                    for i, mismatch in enumerate(result['mismatches'], 1):
                        response += f"**{i}. {mismatch['title']}**\n"
                        response += f"   IMDb (Audience): {mismatch['imdb_score']}/10\n"
                        response += f"   Rotten Tomatoes (Critics): {mismatch['rt_score']}%\n"
                        response += f"   Mismatch Degree: {mismatch['mismatch_degree']} points\n"
                        response += f"   Analysis: {mismatch['analysis']}\n"
                        response += f"   Movie ID: {mismatch['id']}\n\n"
                else:
                    response = f"No significant rating mismatches found for '{query}' with minimum {min_mismatch} point difference.\n"
                    response += "Try a lower mismatch threshold or different search term."
            else:
                response = f"**Error finding rating mismatches**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "search_tv_shows":
            query = arguments["query"]
            year = arguments.get("year")
            result = api.search_tv_shows(query, year)

            if result.get('success'):
                if result['shows']:
                    response = f"**TV Show Search Results for '{query}'**"
                    if year:
                        response += f" **({year})**"
                    response += f"\n\nFound {result['total_results']} shows:\n\n"

                    for i, show in enumerate(result['shows'], 1):
                        response += f"**{i}. {show['name']}** ({show['first_air_date'][:4] if show['first_air_date'] != 'Unknown' else 'Unknown'})\n"
                        response += f"   Rating: {show['vote_average']}/10\n"
                        response += f"   ID: {show['id']}\n"
                        response += f"   Overview: {show['overview']}\n\n"
                else:
                    response = f"No TV shows found for '{query}'"
                    if year:
                        response += f" from {year}"
            else:
                response = f"**Error searching TV shows**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "get_tv_details":
            tv_id = arguments["tv_id"]
            result = api.get_tv_details(tv_id)

            if result.get('success'):
                response = f"**{result['name']}**"
                if result['tagline']:
                    response += f"\n*{result['tagline']}*"

                response += f"\n\n**Show Information:**\n"
                response += f"• **First Aired**: {result['first_air_date']}\n"
                if result['last_air_date'] != 'Unknown':
                    response += f"• **Last Aired**: {result['last_air_date']}\n"
                response += f"• **Status**: {result['status']}\n"
                response += f"• **Seasons**: {result['number_of_seasons']}\n"
                response += f"• **Episodes**: {result['number_of_episodes']}\n"
                response += f"• **Episode Runtime**: {result['avg_episode_runtime']}\n"
                response += f"• **Type**: {result['type']}\n"
                response += f"• **Genres**: {', '.join(result['genres'])}\n"
                response += f"• **Rating**: {result['vote_average']}/10 ({result['vote_count']:,} votes)\n"

                if result['networks']:
                    response += f"• **Networks**: {', '.join(result['networks'])}\n"

                if result['creators']:
                    response += f"\n**Created by**: {', '.join(result['creators'])}\n"

                if result['cast']:
                    response += f"\n**Main Cast:**\n"
                    for actor in result['cast'][:5]:
                        response += f"• {actor['name']} as {actor['character']}\n"

                if result['production_companies']:
                    response += f"\n**Production**: {', '.join(result['production_companies'])}\n"

                if result['streaming']:
                    response += f"\n**Streaming Availability (US):**\n"
                    for platform_type, platforms in result['streaming'].items():
                        type_label = {"flatrate": "Subscription", "rent": "Rent", "buy": "Purchase"}
                        response += f"• **{type_label.get(platform_type, platform_type)}**: {', '.join(platforms)}\n"

                response += f"\n**Overview:**\n{result['overview']}"

                if result['homepage']:
                    response += f"\n\n**Official Website**: {result['homepage']}"
            else:
                response = f"**Error getting TV show details**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        elif name == "get_trending":
            media_type = arguments.get("media_type", "movie")
            time_window = arguments.get("time_window", "week")
            result = api.get_trending(media_type, time_window)

            if result.get('success'):
                type_label = {"movie": "Movies", "tv": "TV Shows", "all": "Movies & TV Shows"}
                window_label = {"day": "Today", "week": "This Week"}

                response = f"**Trending {type_label.get(media_type, media_type.title())} {window_label.get(time_window, time_window.title())}**\n\n"

                for i, item in enumerate(result['trending'], 1):
                    media_indicator = ""
                    if media_type == "all":
                        media_indicator = f" [{item['media_type'].upper()}]"

                    response += f"**{i}. {item['title']}{media_indicator}**\n"
                    response += f"   Rating: {item['vote_average']}/10\n"
                    response += f"   Release: {item['release_date'][:4] if item['release_date'] != 'Unknown' else 'Unknown'}\n"
                    response += f"   ID: {item['id']}\n"
                    response += f"   {item['overview']}\n\n"
            else:
                response = f"**Error getting trending content**: {result.get('error', 'Unknown error')}"

            return [TextContent(type="text", text=response)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        error_msg = f"**Error executing {name}**: {str(e)}"
        return [TextContent(type="text", text=error_msg)]

async def main():
    """Main entry point for local testing"""
    try:
        # Verify we can initialize the Enhanced Movie API
        get_movie_api()
        print("Enhanced Movie API (TMDB + OMDb) initialized successfully")
        print("Starting Enhanced Movie/TV MCP Server...")

        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="enhanced-movie-tv-mcp",
                    server_version="1.0.0",
                    capabilities=app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Make sure your .env file contains both TMDB_API_KEY and OMDB_API_KEY")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    asyncio.run(main())