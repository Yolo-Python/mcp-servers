import requests
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

class EnhancedMovieAPI:
    def __init__(self, tmdb_api_key: str, omdb_api_key: str, trakt_client_id: str, trakt_client_secret: str):
        self.tmdb_api_key = tmdb_api_key
        self.omdb_api_key = omdb_api_key
        self.trakt_client_id = trakt_client_id
        self.trakt_client_secret = trakt_client_secret
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.omdb_base_url = "http://www.omdbapi.com/"
        self.trakt_base_url = "https://api.trakt.tv"

    def _make_tmdb_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make a request to TMDB API"""
        if params is None:
            params = {}
        params['api_key'] = self.tmdb_api_key

        try:
            response = requests.get(f"{self.tmdb_base_url}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"TMDB API request failed: {e}")
            return None

    def _make_trakt_request(self, endpoint: str, params: Dict = None, headers: Dict = None) -> Optional[Dict]:
        """Make a request to Trakt.tv API"""
        if headers is None:
            headers = {}

        # Standard Trakt headers
        headers.update({
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.trakt_client_id
        })

        try:
            response = requests.get(f"{self.trakt_base_url}{endpoint}", params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Trakt API request failed: {e}")
            return None
    def _make_omdb_request(self, params: Dict) -> Optional[Dict]:
        """Make a request to OMDb API"""
        params['apikey'] = self.omdb_api_key

        try:
            response = requests.get(self.omdb_base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('Response') == 'False':
                return None
            return data
        except requests.exceptions.RequestException as e:
            print(f"OMDb API request failed: {e}")
            return None

    def search_movies(self, query: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for movies"""
        params = {'query': query}
        if year:
            params['year'] = str(year)
        return self._make_tmdb_request("/search/movie", params)

    def get_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get basic movie details from TMDB"""
        return self._make_tmdb_request(f"/movie/{movie_id}")

    def get_enhanced_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get enhanced movie details combining TMDB and OMDb data"""
        tmdb_data = self.get_movie_details(movie_id)
        if not tmdb_data:
            return None

        omdb_data = None
        if tmdb_data.get('imdb_id'):
            omdb_data = self._make_omdb_request({'i': tmdb_data['imdb_id']})

        enhanced_data = tmdb_data.copy()
        enhanced_data['omdb_data'] = omdb_data
        enhanced_data['enhanced_ratings'] = self._combine_ratings(tmdb_data, omdb_data)
        enhanced_data['rating_analysis'] = self._analyze_ratings(enhanced_data['enhanced_ratings'])

        if omdb_data:
            enhanced_data['awards'] = omdb_data.get('Awards', 'N/A')
            enhanced_data['box_office'] = omdb_data.get('BoxOffice', 'N/A')
            enhanced_data['detailed_plot'] = omdb_data.get('Plot', tmdb_data.get('overview', 'N/A'))

        return enhanced_data

    def _combine_ratings(self, tmdb_data: Dict, omdb_data: Optional[Dict]) -> Dict:
        """Combine ratings from multiple sources"""
        ratings = {
            'tmdb': tmdb_data.get('vote_average', 0),
            'imdb': 0,
            'rotten_tomatoes': 0,
            'metacritic': 0
        }

        if omdb_data:
            imdb_rating = omdb_data.get('imdbRating')
            if imdb_rating and imdb_rating != 'N/A':
                ratings['imdb'] = float(imdb_rating)

            for rating in omdb_data.get('Ratings', []):
                source = rating['Source'].lower()
                value = rating['Value']

                if 'rotten tomatoes' in source:
                    ratings['rotten_tomatoes'] = int(value.replace('%', ''))
                elif 'metacritic' in source:
                    ratings['metacritic'] = int(value.split('/')[0])

        return ratings

    def _analyze_ratings(self, ratings: Dict) -> str:
        """Analyze rating patterns to provide insights"""
        tmdb = ratings['tmdb']
        imdb = ratings['imdb']
        rt = ratings['rotten_tomatoes']
        metacritic = ratings['metacritic']

        if not any([imdb, rt, metacritic]):
            return "OMDb data not available"

        if imdb >= 8.5:
            return "Highly acclaimed (IMDb 8.5+)"
        elif rt > 0 and imdb > 0:
            rt_normalized = rt / 10  # Convert RT percentage to 10-point scale
            imdb_rt_diff = imdb - rt_normalized

            if abs(imdb_rt_diff) >= 1.5:
                if imdb_rt_diff > 0:
                    return "Audiences love it more than critics"
                else:
                    return "Critics love it more than audiences"
            else:
                return "Critics and audiences generally agree"
        else:
            return "Standard rating distribution"

    def find_rating_mismatches(self, query: str, min_mismatch: float = 2.0) -> List[Dict]:
        """Find movies where critics and audiences have different opinions"""
        search_results = self.search_movies(query)
        if not search_results or 'results' not in search_results:
            return []

        mismatches = []
        for movie in search_results['results'][:10]:  # Limit to first 10 results
            enhanced = self.get_enhanced_movie_details(movie['id'])
            if not enhanced:
                continue

            ratings = enhanced['enhanced_ratings']
            if ratings['imdb'] > 0 and ratings['rotten_tomatoes'] > 0:
                rt_normalized = ratings['rotten_tomatoes'] / 10
                mismatch = abs(ratings['imdb'] - rt_normalized)

                if mismatch >= min_mismatch:
                    mismatches.append({
                        'title': movie['title'],
                        'year': movie.get('release_date', '')[:4] if movie.get('release_date') else '',
                        'imdb_rating': ratings['imdb'],
                        'rotten_tomatoes': ratings['rotten_tomatoes'],
                        'mismatch_degree': round(mismatch, 1),
                        'analysis': enhanced['rating_analysis']
                    })

        return sorted(mismatches, key=lambda x: x['mismatch_degree'], reverse=True)

    def find_vibe_movies(self, reference_movie: str, vibe_modifier: str, limit: int = 10) -> List[Dict]:
        """Find movies with similar vibe but modified by the specified attribute"""
        # First, get the reference movie
        search_results = self.search_movies(reference_movie)
        if not search_results or not search_results['results']:
            return []

        ref_movie = search_results['results'][0]
        ref_details = self.get_enhanced_movie_details(ref_movie['id'])
        if not ref_details:
            return []

        ref_ratings = ref_details['enhanced_ratings']
        ref_genres = [g['name'] for g in ref_details.get('genres', [])]

        # Define vibe modifier rules
        vibe_rules = self._get_vibe_modifier_rules(vibe_modifier, ref_ratings)

        # Search for movies in similar genres
        recommendations = []
        for genre in ref_genres[:2]:  # Check top 2 genres
            genre_movies = self._search_by_genre_and_criteria(genre, vibe_rules, limit * 2)
            recommendations.extend(genre_movies)

        # Remove duplicates and the reference movie itself
        seen_ids = {ref_movie['id']}
        unique_recommendations = []
        for movie in recommendations:
            if movie['id'] not in seen_ids:
                seen_ids.add(movie['id'])
                unique_recommendations.append(movie)

        return unique_recommendations[:limit]

    def _get_vibe_modifier_rules(self, vibe_modifier: str, ref_ratings: Dict) -> Dict:
        """Define rules for different vibe modifiers"""
        rules = {
            'accessible': {
                'imdb_min': max(7.0, ref_ratings['imdb'] - 1.0),
                'imdb_audience_preference': True,  # IMDb >= RT
                'runtime_max': 140
            },
            'grounded': {
                'imdb_min': 6.5,
                'rt_imdb_gap_max': 1.0,  # Critics and audiences closer
                'exclude_genres': ['Fantasy', 'Science Fiction']
            },
            'cerebral': {
                'metacritic_min': 70,
                'rt_critics_preference': True,  # RT > IMDb
                'include_genres': ['Drama', 'Thriller', 'Science Fiction']
            },
            'crowd_pleasing': {
                'imdb_min': 7.5,
                'imdb_audience_preference': True,
                'exclude_genres': ['Documentary', 'Foreign']
            },
            'challenging': {
                'metacritic_min': 75,
                'rt_critics_preference': True,
                'include_genres': ['Drama', 'Mystery', 'Thriller']
            }
        }

        return rules.get(vibe_modifier, {
            'imdb_min': ref_ratings['imdb'] - 0.5,
            'similar_rating_profile': True
        })

    def get_mood_recommendations(self, mood: str, time_context: str = None, limit: int = 10) -> List[Dict]:
        """Get recommendations based on mood and time context"""
        mood_profiles = {
            'cozy': {
                'imdb_min': 7.5,
                'runtime_max': 120,
                'include_genres': ['Comedy', 'Romance', 'Family', 'Animation'],
                'exclude_genres': ['Horror', 'Thriller', 'War']
            },
            'energetic': {
                'include_genres': ['Action', 'Adventure', 'Comedy'],
                'rt_critics_preference': True,  # Well-crafted entertainment
                'runtime_min': 90
            },
            'thoughtful': {
                'metacritic_min': 70,
                'include_genres': ['Drama', 'Science Fiction', 'Mystery'],
                'awards_preferred': True
            },
            'comfort': {
                'imdb_min': 7.5,
                'familiar_genres': True,
                'release_year_max': datetime.now().year - 2  # Not too recent
            }
        }

        time_modifiers = {
            'morning': {'runtime_max': 120, 'light_content': True},
            'late_night': {'metacritic_min': 65, 'thoughtful_content': True},
            'weekend': {'any_length': True, 'entertainment_value_high': True}
        }

        profile = mood_profiles.get(mood, {})
        if time_context:
            time_mod = time_modifiers.get(time_context, {})
            profile.update(time_mod)

        return self._search_by_mood_profile(profile, limit)

    def find_rating_personality(self, personality_type: str, genre_filter: str = None) -> List[Dict]:
        """Find movies with specific critic/audience relationships"""
        personality_rules = {
            'critics_darling': {
                'rt_critics_much_higher': True,
                'metacritic_min': 75,
                'min_gap': 1.5
            },
            'crowd_pleaser': {
                'imdb_much_higher': True,
                'imdb_min': 7.5,
                'min_gap': 1.5
            },
            'universal_acclaim': {
                'imdb_min': 8.0,
                'rt_min': 85,
                'metacritic_min': 80
            },
            'cult_classic': {
                'rt_max': 70,
                'imdb_min': 7.5,
                'age_min': 5  # At least 5 years old
            },
            'prestige_accessible': {
                'awards_required': True,
                'imdb_min': 7.5,
                'metacritic_min': 70
            }
        }

        rules = personality_rules.get(personality_type, {})
        return self._search_by_personality_rules(rules, genre_filter)

    def analyze_movie_vibe(self, movie_id: int) -> Dict:
        """Provide deep vibe analysis of a specific movie"""
        details = self.get_enhanced_movie_details(movie_id)
        if not details:
            return {}

        ratings = details['enhanced_ratings']
        genres = [g['name'] for g in details.get('genres', [])]
        runtime = details.get('runtime', 0)

        # Determine vibe tags
        vibe_tags = []
        if ratings['metacritic'] >= 75:
            vibe_tags.append('cerebral')
        if ratings['imdb'] >= ratings['rotten_tomatoes'] / 10:
            vibe_tags.append('accessible')
        if ratings['imdb'] >= 7.5:
            vibe_tags.append('crowd-pleasing')
        if 'Drama' in genres and ratings['metacritic'] >= 70:
            vibe_tags.append('thoughtful')

        # Determine mood profile
        mood_profile = self._determine_mood_profile(ratings, genres, details.get('awards', ''))

        # Suggest best viewing time
        best_time = self._suggest_viewing_time(runtime, genres, ratings)

        return {
            'title': details['title'],
            'vibe_tags': vibe_tags,
            'mood_profile': mood_profile,
            'best_time': best_time,
            'rating_personality': details['rating_analysis'],
            'accessibility_score': self._calculate_accessibility(ratings),
            'prestige_score': self._calculate_prestige(ratings, details.get('awards', ''))
        }

    def _determine_mood_profile(self, ratings: Dict, genres: List, awards: str) -> str:
        """Determine the overall mood profile of a movie"""
        if 'N/A' not in awards and ('Oscar' in awards or 'Emmy' in awards):
            if ratings['imdb'] >= 7.5:
                return "Prestige entertainment"
            else:
                return "Acclaimed but challenging"

        if 'Comedy' in genres and ratings['imdb'] >= 7.0:
            return "Feel-good entertainment"
        elif 'Horror' in genres and ratings['rotten_tomatoes'] >= 80:
            return "Smart scary"
        elif 'Action' in genres and ratings['rotten_tomatoes'] > ratings['imdb'] * 10:
            return "Stylish thrills"
        elif ratings['metacritic'] >= 75:
            return "Thoughtful and rewarding"
        else:
            return "Solid entertainment"

    def _suggest_viewing_time(self, runtime: int, genres: List, ratings: Dict) -> str:
        """Suggest optimal viewing time based on movie characteristics"""
        if runtime <= 100 and any(g in genres for g in ['Comedy', 'Animation', 'Family']):
            return "Perfect for any time"
        elif runtime >= 150 or 'Drama' in genres:
            return "Weekend afternoon or evening"
        elif any(g in genres for g in ['Horror', 'Thriller']) and ratings['metacritic'] >= 70:
            return "Late night viewing"
        elif 'Action' in genres:
            return "Friday night entertainment"
        else:
            return "Weekend afternoon"

    def _calculate_accessibility(self, ratings: Dict) -> int:
        """Calculate how accessible/mainstream a movie is (1-10 scale)"""
        score = 5  # Base score

        if ratings['imdb'] >= 7.5:
            score += 2
        if ratings['imdb'] > ratings['rotten_tomatoes'] / 10:
            score += 1  # Audiences like it more than critics
        if ratings['rotten_tomatoes'] >= 85:
            score += 1

        return min(10, max(1, score))

    def _calculate_prestige(self, ratings: Dict, awards: str) -> int:
        """Calculate prestige/artistic merit score (1-10 scale)"""
        score = 5  # Base score

        if ratings['metacritic'] >= 80:
            score += 2
        if ratings['rotten_tomatoes'] >= 90:
            score += 1
        if 'Oscar' in awards or 'Emmy' in awards:
            score += 2
        if ratings['rotten_tomatoes'] > ratings['imdb'] * 10:
            score += 1  # Critics appreciate it more

        return min(10, max(1, score))

    # TMDB Discovery API Implementation
    def _search_by_genre_and_criteria(self, genre: str, criteria: Dict, limit: int) -> List[Dict]:
        """Search for movies by genre with specific criteria using TMDB Discovery API"""
        genre_map = {
            'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35, 'Crime': 80,
            'Documentary': 99, 'Drama': 18, 'Family': 10751, 'Fantasy': 14, 'History': 36,
            'Horror': 27, 'Music': 10402, 'Mystery': 9648, 'Romance': 10749, 'Science Fiction': 878,
            'TV Movie': 10770, 'Thriller': 53, 'War': 10752, 'Western': 37
        }

        params = {
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 100,  # Ensure meaningful number of votes
            'page': 1
        }

        # Add genre filter
        genre_id = genre_map.get(genre)
        if genre_id:
            params['with_genres'] = genre_id

        # Apply criteria rules
        if criteria.get('imdb_min'):
            params['vote_average.gte'] = criteria['imdb_min']
        if criteria.get('runtime_max'):
            params['with_runtime.lte'] = criteria['runtime_max']
        if criteria.get('runtime_min'):
            params['with_runtime.gte'] = criteria['runtime_min']
        if criteria.get('release_year_max'):
            params['primary_release_date.lte'] = f"{criteria['release_year_max']}-12-31"
        if criteria.get('exclude_genres'):
            exclude_ids = [str(genre_map.get(g, '')) for g in criteria['exclude_genres'] if genre_map.get(g)]
            if exclude_ids:
                params['without_genres'] = ','.join(exclude_ids)
        if criteria.get('include_genres'):
            include_ids = [str(genre_map.get(g, '')) for g in criteria['include_genres'] if genre_map.get(g)]
            if include_ids:
                params['with_genres'] = ','.join(include_ids)

        result = self._make_tmdb_request("/discover/movie", params)
        if result and 'results' in result:
            movies = result['results'][:limit]
            # Enhance with rating analysis for vibe matching
            return self._filter_by_advanced_criteria(movies, criteria)
        return []

    def _search_by_mood_profile(self, profile: Dict, limit: int) -> List[Dict]:
        """Search movies matching a mood profile using Discovery API"""
        params = {
            'sort_by': 'vote_average.desc',
            'vote_count.gte': 200,
            'page': 1
        }

        # Apply mood-specific filters
        if profile.get('imdb_min'):
            params['vote_average.gte'] = profile['imdb_min']
        if profile.get('runtime_max'):
            params['with_runtime.lte'] = profile['runtime_max']
        if profile.get('runtime_min'):
            params['with_runtime.gte'] = profile['runtime_min']
        if profile.get('release_year_max'):
            params['primary_release_date.lte'] = f"{profile['release_year_max']}-12-31"

        # Handle genre preferences
        genre_map = {
            'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35, 'Crime': 80,
            'Documentary': 99, 'Drama': 18, 'Family': 10751, 'Fantasy': 14, 'History': 36,
            'Horror': 27, 'Music': 10402, 'Mystery': 9648, 'Romance': 10749, 'Science Fiction': 878,
            'TV Movie': 10770, 'Thriller': 53, 'War': 10752, 'Western': 37
        }

        if profile.get('include_genres'):
            include_ids = [str(genre_map.get(g, '')) for g in profile['include_genres'] if genre_map.get(g)]
            if include_ids:
                params['with_genres'] = ','.join(include_ids)

        if profile.get('exclude_genres'):
            exclude_ids = [str(genre_map.get(g, '')) for g in profile['exclude_genres'] if genre_map.get(g)]
            if exclude_ids:
                params['without_genres'] = ','.join(exclude_ids)

        result = self._make_tmdb_request("/discover/movie", params)
        if result and 'results' in result:
            movies = result['results'][:limit * 2]  # Get more to filter
            return self._filter_by_mood_criteria(movies, profile, limit)
        return []

    def _search_by_personality_rules(self, rules: Dict, genre_filter: str = None) -> List[Dict]:
        """Search movies matching personality rules using Discovery API"""
        params = {
            'sort_by': 'vote_count.desc',  # Popular movies for better rating data
            'vote_count.gte': 500,  # Need sufficient votes for reliable patterns
            'page': 1
        }

        # Apply basic filters
        if rules.get('imdb_min'):
            params['vote_average.gte'] = rules['imdb_min']
        if rules.get('age_min'):
            current_year = datetime.now().year
            max_year = current_year - rules['age_min']
            params['primary_release_date.lte'] = f"{max_year}-12-31"

        # Genre filtering
        if genre_filter:
            genre_map = {
                'Action': 28, 'Adventure': 12, 'Animation': 16, 'Comedy': 35, 'Crime': 80,
                'Documentary': 99, 'Drama': 18, 'Family': 10751, 'Fantasy': 14, 'History': 36,
                'Horror': 27, 'Music': 10402, 'Mystery': 9648, 'Romance': 10749, 'Science Fiction': 878,
                'TV Movie': 10770, 'Thriller': 53, 'War': 10752, 'Western': 37
            }
            genre_id = genre_map.get(genre_filter)
            if genre_id:
                params['with_genres'] = genre_id

        result = self._make_tmdb_request("/discover/movie", params)
        if result and 'results' in result:
            movies = result['results'][:50]  # Get more movies to analyze
            return self._filter_by_personality_pattern(movies, rules)
        return []

    def _filter_by_advanced_criteria(self, movies: List[Dict], criteria: Dict) -> List[Dict]:
        """Filter movies by advanced criteria that require OMDb data"""
        filtered_movies = []

        for movie in movies:
            # Get enhanced details for rating analysis
            enhanced = self.get_enhanced_movie_details(movie['id'])
            if not enhanced:
                continue

            ratings = enhanced['enhanced_ratings']

            # Apply vibe-specific filters
            if criteria.get('imdb_audience_preference'):
                # IMDb should be >= RT (audience likes it more than critics)
                if ratings['rotten_tomatoes'] > 0:
                    rt_normalized = ratings['rotten_tomatoes'] / 10
                    if ratings['imdb'] < rt_normalized:
                        continue

            if criteria.get('rt_critics_preference'):
                # RT should be > IMDb (critics like it more than audiences)
                if ratings['rotten_tomatoes'] > 0:
                    rt_normalized = ratings['rotten_tomatoes'] / 10
                    if ratings['imdb'] >= rt_normalized:
                        continue

            if criteria.get('rt_imdb_gap_max'):
                # Gap between RT and IMDb should be small
                if ratings['rotten_tomatoes'] > 0:
                    rt_normalized = ratings['rotten_tomatoes'] / 10
                    gap = abs(ratings['imdb'] - rt_normalized)
                    if gap > criteria['rt_imdb_gap_max']:
                        continue

            if criteria.get('metacritic_min'):
                if ratings['metacritic'] < criteria['metacritic_min']:
                    continue

            filtered_movies.append(movie)

            if len(filtered_movies) >= 10:  # Limit results
                break

        return filtered_movies

    # Trakt.tv Integration Methods
    def get_trakt_trending(self, media_type: str = 'movies', limit: int = 10) -> List[Dict]:
        """Get trending movies/shows from Trakt with user behavior data"""
        endpoint = f"/movies/trending" if media_type == 'movies' else f"/shows/trending"
        params = {'limit': limit}

        result = self._make_trakt_request(endpoint, params)
        if result:
            return result
        return []

    def get_trakt_popular_lists(self, limit: int = 10) -> List[Dict]:
        """Get popular user-curated lists from Trakt for vibe inspiration"""
        endpoint = "/lists/popular"
        params = {'limit': limit}

        result = self._make_trakt_request(endpoint, params)
        if result:
            return result
        return []

    def get_trakt_movie_stats(self, tmdb_id: int) -> Optional[Dict]:
        """Get Trakt user behavior stats for a specific movie"""
        endpoint = f"/movies/{tmdb_id}/stats"

        result = self._make_trakt_request(endpoint)
        if result:
            return result
        return None

    def get_trakt_similar_movies(self, tmdb_id: int, limit: int = 10) -> List[Dict]:
        """Get movies similar to a given movie based on Trakt user behavior"""
        # First try Trakt's related movies
        endpoint = f"/movies/{tmdb_id}/related"
        params = {'limit': limit}

        result = self._make_trakt_request(endpoint, params)
        if result:
            return result
        return []

    def get_trakt_movie_comments(self, tmdb_id: int, limit: int = 10) -> List[Dict]:
        """Get user comments/reviews from Trakt for sentiment analysis"""
        endpoint = f"/movies/{tmdb_id}/comments"
        params = {'limit': limit, 'sort': 'likes'}  # Get most liked comments

        result = self._make_trakt_request(endpoint, params)
        if result:
            return result
        return []

    def search_trakt_lists_by_keyword(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Search Trakt lists by keyword for vibe-based collections"""
        endpoint = "/search/list"
        params = {'query': keyword, 'limit': limit}

        result = self._make_trakt_request(endpoint, params)
        if result:
            return result
        return []

    def get_enhanced_movie_with_trakt(self, movie_id: int) -> Optional[Dict]:
        """Get comprehensive movie details including Trakt user behavior data"""
        # Start with our existing enhanced details
        enhanced_data = self.get_enhanced_movie_details(movie_id)
        if not enhanced_data:
            return None

        # Add Trakt data
        trakt_stats = self.get_trakt_movie_stats(movie_id)
        trakt_comments = self.get_trakt_movie_comments(movie_id, 5)  # Top 5 comments
        trakt_similar = self.get_trakt_similar_movies(movie_id, 5)   # Top 5 similar

        enhanced_data['trakt_data'] = {
            'stats': trakt_stats,
            'user_comments': trakt_comments,
            'similar_movies': trakt_similar,
            'community_sentiment': self._analyze_trakt_comments(trakt_comments)
        }

        return enhanced_data

    def _analyze_trakt_comments(self, comments: List[Dict]) -> Dict:
        """Analyze Trakt comments for community sentiment and common themes"""
        if not comments:
            return {'sentiment': 'neutral', 'common_themes': [], 'user_vibe': 'unknown'}

        # Extract common keywords and sentiment indicators
        positive_words = ['love', 'amazing', 'brilliant', 'perfect', 'fantastic', 'incredible', 'masterpiece']
        negative_words = ['hate', 'terrible', 'awful', 'boring', 'disappointing', 'waste', 'bad']
        vibe_words = ['cozy', 'dark', 'funny', 'intense', 'relaxing', 'thrilling', 'emotional', 'uplifting']

        all_text = ' '.join([comment.get('comment', '').lower() for comment in comments])

        positive_count = sum(1 for word in positive_words if word in all_text)
        negative_count = sum(1 for word in negative_words if word in all_text)
        found_vibes = [word for word in vibe_words if word in all_text]

        # Determine sentiment
        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Extract user vibe
        user_vibe = found_vibes[0] if found_vibes else 'standard'

        return {
            'sentiment': sentiment,
            'common_themes': found_vibes,
            'user_vibe': user_vibe,
            'engagement_level': len(comments)
        }

    def find_movies_by_trakt_list_vibe(self, vibe_keyword: str, limit: int = 10) -> List[Dict]:
        """Find movies from Trakt lists that match a specific vibe keyword"""
        # Search for lists with the vibe keyword
        matching_lists = self.search_trakt_lists_by_keyword(vibe_keyword, 5)

        movie_recommendations = []

        for list_item in matching_lists:
            # Get the actual list contents (this would need list ID from the search result)
            list_id = list_item.get('ids', {}).get('trakt')
            if list_id:
                list_movies = self._get_trakt_list_items(list_id)
                movie_recommendations.extend(list_movies[:3])  # Top 3 from each list

        # Remove duplicates and limit results
        seen_ids = set()
        unique_movies = []
        for movie in movie_recommendations:
            movie_id = movie.get('ids', {}).get('tmdb')
            if movie_id and movie_id not in seen_ids:
                seen_ids.add(movie_id)
                unique_movies.append(movie)
                if len(unique_movies) >= limit:
                    break

        return unique_movies

    def _get_trakt_list_items(self, list_id: int, limit: int = 10) -> List[Dict]:
        """Get items from a specific Trakt list"""
        endpoint = f"/lists/{list_id}/items/movies"
        params = {'limit': limit}

        result = self._make_trakt_request(endpoint, params)
        if result:
            return [item.get('movie', {}) for item in result if item.get('movie')]
        return []

    def get_trakt_genre_recommendations(self, genre: str, vibe_filter: str = None) -> List[Dict]:
        """Get movie recommendations from Trakt based on genre and optional vibe filter"""
        # Use Trakt's genre-specific trending/popular endpoints
        endpoint = f"/movies/popular"
        params = {'limit': 50}  # Get more to filter by genre

        movies = self._make_trakt_request(endpoint, params)
        if not movies:
            return []

        # Filter by genre and vibe if specified
        filtered_movies = []
        for movie in movies:
            # This would require cross-referencing with TMDB for genre data
            tmdb_id = movie.get('ids', {}).get('tmdb')
            if tmdb_id:
                tmdb_details = self.get_movie_details(tmdb_id)
                if tmdb_details:
                    movie_genres = [g['name'] for g in tmdb_details.get('genres', [])]
                    if genre.lower() in [g.lower() for g in movie_genres]:
                        if vibe_filter:
                            # Apply vibe filtering using our existing logic
                            enhanced = self.get_enhanced_movie_with_trakt(tmdb_id)
                            if enhanced and self._matches_vibe_filter(enhanced, vibe_filter):
                                filtered_movies.append(movie)
                        else:
                            filtered_movies.append(movie)

                        if len(filtered_movies) >= 10:
                            break

        return filtered_movies

    def _matches_vibe_filter(self, enhanced_movie: Dict, vibe_filter: str) -> bool:
        """Check if a movie matches a specific vibe filter using combined data"""
        trakt_data = enhanced_movie.get('trakt_data', {})
        ratings = enhanced_movie.get('enhanced_ratings', {})

        if vibe_filter == 'cozy':
            # Check for positive community sentiment and family-friendly content
            sentiment = trakt_data.get('community_sentiment', {}).get('sentiment', 'neutral')
            user_vibe = trakt_data.get('community_sentiment', {}).get('user_vibe', '')
            return sentiment == 'positive' and ('cozy' in user_vibe or 'relaxing' in user_vibe)

        elif vibe_filter == 'intense':
            # Check for thrilling/intense community feedback
            user_vibe = trakt_data.get('community_sentiment', {}).get('user_vibe', '')
            return 'intense' in user_vibe or 'thrilling' in user_vibe

        elif vibe_filter == 'accessible':
            # High ratings across the board
            return ratings.get('imdb', 0) >= 7.0 and ratings.get('rotten_tomatoes', 0) >= 70

        elif vibe_filter == 'cult':
            # Lower mainstream ratings but strong community engagement
            engagement = trakt_data.get('community_sentiment', {}).get('engagement_level', 0)
            return engagement > 0 and ratings.get('rotten_tomatoes', 100) < 70

        return True  # Default to include if no specific filter

    def _filter_by_mood_criteria(self, movies: List[Dict], profile: Dict, limit: int) -> List[Dict]:
        """Filter movies by mood-specific criteria"""
        filtered_movies = []

        for movie in movies:
            # Basic genre filtering already applied by Discovery API

            # Apply advanced mood criteria
            if profile.get('light_content'):
                # Avoid heavy/dark genres for light moods
                genres = [g['name'] for g in movie.get('genres', [])]
                if any(g in genres for g in ['Horror', 'War', 'Crime']):
                    continue

            if profile.get('awards_preferred'):
                # Check if movie has awards (requires enhanced data)
                enhanced = self.get_enhanced_movie_details(movie['id'])
                if enhanced and enhanced.get('awards', 'N/A') == 'N/A':
                    continue

            if profile.get('familiar_genres'):
                # Prefer mainstream genres
                genres = [g['name'] for g in movie.get('genres', [])]
                if not any(g in genres for g in ['Comedy', 'Drama', 'Action', 'Romance']):
                    continue

            filtered_movies.append(movie)

            if len(filtered_movies) >= limit:
                break

        return filtered_movies

    def _filter_by_personality_pattern(self, movies: List[Dict], rules: Dict) -> List[Dict]:
        """Filter movies by rating personality patterns"""
        filtered_movies = []

        for movie in movies:
            enhanced = self.get_enhanced_movie_details(movie['id'])
            if not enhanced:
                continue

            ratings = enhanced['enhanced_ratings']

            # Skip movies without sufficient rating data
            if not (ratings['imdb'] > 0 and ratings['rotten_tomatoes'] > 0):
                continue

            rt_normalized = ratings['rotten_tomatoes'] / 10
            gap = ratings['imdb'] - rt_normalized

            # Apply personality rules
            if rules.get('rt_critics_much_higher'):
                if gap >= -rules.get('min_gap', 1.5):  # RT should be much higher than IMDb
                    continue

            if rules.get('imdb_much_higher'):
                if gap <= rules.get('min_gap', 1.5):  # IMDb should be much higher than RT
                    continue

            if rules.get('imdb_min') and ratings['imdb'] < rules['imdb_min']:
                continue

            if rules.get('rt_min') and ratings['rotten_tomatoes'] < rules['rt_min']:
                continue

            if rules.get('rt_max') and ratings['rotten_tomatoes'] > rules['rt_max']:
                continue

            if rules.get('metacritic_min') and ratings['metacritic'] < rules['metacritic_min']:
                continue

            if rules.get('awards_required'):
                awards = enhanced.get('awards', 'N/A')
                if 'N/A' in awards or not any(word in awards for word in ['Oscar', 'Emmy', 'Golden Globe']):
                    continue

            # Universal acclaim check
            if rules.get('imdb_min') and rules.get('rt_min') and rules.get('metacritic_min'):
                if (ratings['imdb'] >= rules['imdb_min'] and
                        ratings['rotten_tomatoes'] >= rules['rt_min'] and
                        ratings['metacritic'] >= rules['metacritic_min']):
                    filtered_movies.append(movie)
            else:
                filtered_movies.append(movie)

            if len(filtered_movies) >= 15:  # Reasonable limit
                break

        return filtered_movies

    # Original methods (unchanged)
    def search_tv_shows(self, query: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for TV shows"""
        params = {'query': query}
        if year:
            params['first_air_date_year'] = str(year)
        return self._make_tmdb_request("/search/tv", params)

    def get_tv_details(self, tv_id: int) -> Optional[Dict]:
        """Get TV show details"""
        return self._make_tmdb_request(f"/tv/{tv_id}")

    def get_trending(self, media_type: str = 'movie', time_window: str = 'week') -> Optional[Dict]:
        """Get trending movies or TV shows"""
        return self._make_tmdb_request(f"/trending/{media_type}/{time_window}")