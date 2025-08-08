#!/usr/bin/env python3
"""
Test script for enhanced TMDB + OMDb API integration
"""
import os
from dotenv import load_dotenv
from enhanced_api import EnhancedMovieAPI

def test_enhanced_api():
    # Load environment variables
    load_dotenv()

    tmdb_key = os.getenv('TMDB_API_KEY')
    omdb_key = os.getenv('OMDB_API_KEY')

    if not tmdb_key:
        print("Error: TMDB_API_KEY not found in .env file")
        return

    if not omdb_key:
        print("Error: OMDB_API_KEY not found in .env file")
        return

    # Create enhanced API instance
    api = EnhancedMovieAPI(tmdb_key, omdb_key)

    print("Testing Enhanced Movie API (TMDB + OMDb)...")
    print("=" * 60)

    # Test 1: Enhanced Movie Details
    print("1. Testing Enhanced Movie Details...")

    # Search for Inception first to get the ID
    search_result = api.search_movies("Inception", year=2010)
    if search_result.get('success') and search_result['movies']:
        inception_id = search_result['movies'][0]['id']
        print(f"Found Inception with ID: {inception_id}")

        # Get enhanced details
        enhanced_details = api.get_enhanced_movie_details(inception_id)

        if enhanced_details.get('success'):
            print(f"SUCCESS: Enhanced Details for: {enhanced_details['title']}")
            print(f"   Runtime: {enhanced_details['runtime_formatted']}")

            # Show all the ratings
            ratings = enhanced_details.get('ratings', {})
            print(f"   Ratings:")
            print(f"      TMDb: {ratings.get('tmdb', 'N/A')}/10")
            print(f"      IMDb: {ratings.get('imdb', 'N/A')}/10")
            print(f"      Rotten Tomatoes: {ratings.get('rotten_tomatoes', 'N/A')}%")
            print(f"      Metacritic: {ratings.get('metacritic', 'N/A')}/100")

            print(f"   Awards: {enhanced_details.get('awards', 'N/A')}")
            print(f"   Box Office: {enhanced_details.get('box_office', 'N/A')}")
            print(f"   Rating Analysis: {enhanced_details.get('rating_analysis', 'N/A')}")
        else:
            print(f"FAILED: Enhanced details failed: {enhanced_details.get('error')}")
    else:
        print("FAILED: Could not find Inception")
        return

    print("\n" + "=" * 60)

    # Test 2: Rating Mismatches
    print("2. Testing Rating Mismatch Detection...")
    mismatches = api.find_rating_mismatches("Batman", min_mismatch=1.5)

    if mismatches.get('success'):
        print(f"SUCCESS: Found {len(mismatches['mismatches'])} rating mismatches for 'Batman':")
        for mismatch in mismatches['mismatches']:
            print(f"   Movie: {mismatch['title']}")
            print(f"      IMDb: {mismatch['imdb_score']}/10")
            print(f"      Rotten Tomatoes: {mismatch['rt_score']}%")
            print(f"      Mismatch Degree: {mismatch['mismatch_degree']} points")
            print(f"      Analysis: {mismatch['analysis']}")
            print()
    else:
        print(f"FAILED: Rating mismatch search failed: {mismatches.get('error')}")

    print("\n" + "=" * 60)

    # Test 3: Basic functionality (ensuring we didn't break existing features)
    print("3. Testing Basic Search Functionality...")
    basic_search = api.search_movies("The Matrix")

    if basic_search.get('success'):
        print(f"SUCCESS: Found {basic_search['total_results']} results for 'The Matrix'")
        if basic_search['movies']:
            first_result = basic_search['movies'][0]
            print(f"   Top result: {first_result['title']} ({first_result['release_date'][:4]})")
            print(f"   Rating: {first_result['vote_average']}/10")
    else:
        print(f"FAILED: Basic search failed: {basic_search.get('error')}")

    print("\n" + "=" * 60)
    print("Enhanced API test complete!")

if __name__ == "__main__":
    test_enhanced_api()