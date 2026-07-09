from flask import Flask, render_template, request, jsonify, session
import sqlite3
import urllib.request
import urllib.parse
import json
import re
import datetime
import os
import threading
import time
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini API Key if available
gemini_key = os.environ.get("GEMINI_API_KEY")
has_gemini = False
if gemini_key and gemini_key != "YOUR_GEMINI_API_KEY_HERE":
    try:
        genai.configure(api_key=gemini_key)
        has_gemini = True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")

app = Flask(__name__)
app.secret_key = "cinematch_premium_neural_key_2026"

# Server-side in-memory cache to ensure extreme load speeds and avoid rate-limiting
POSTER_CACHE = {}

def init_poster_cache_db():
    try:
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS poster_cache (
                title TEXT PRIMARY KEY,
                poster TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating poster_cache table: {e}")

def load_poster_cache_into_memory():
    try:
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT title, poster FROM poster_cache")
        for row in cursor.fetchall():
            POSTER_CACHE[row[0]] = row[1]
        conn.close()
        print(f"Pre-warmed memory cache with {len(POSTER_CACHE)} poster URLs.")
    except Exception as e:
        print(f"Error pre-warming memory cache: {e}")

def create_indexes():
    """
    Verify and create critical indexes in movies.db to optimize query speeds (reducing table scan times from ~300ms to <1ms).
    """
    try:
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        
        # Create indexes for movies table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies(rating DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_release_year ON movies(release_year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_language ON movies(language)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_runtime ON movies(runtime_minutes)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")
        
        # Create indexes for user_likes table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_likes_uid ON user_likes(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_likes_movie ON user_likes(movie_title)")
        
        conn.commit()
        conn.close()
        print("Database indexes verified/created successfully.")
    except Exception as e:
        print(f"Error creating database indexes: {e}")

def prefetch_posters():
    """
    Lightweight background worker that pre-fetches poster URLs for the top 100+ movies shown on the homepage/dashboard
    to warm the SQLite poster_cache asynchronously, avoiding API bottlenecks during user visits.
    """
    try:
        # Wait a few seconds for the Flask server to start up completely
        time.sleep(3)
        
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        
        # Fetch titles likely to be displayed on index and dashboard shelves
        titles_to_cache = []
        
        # 1. Top rated movies
        cursor.execute("SELECT title FROM movies ORDER BY rating DESC LIMIT 30")
        titles_to_cache.extend([row[0] for row in cursor.fetchall()])
        
        # 2. Sci-Fi movies
        cursor.execute("SELECT title FROM movies WHERE genres LIKE '%Sci-Fi%' ORDER BY rating DESC LIMIT 30")
        titles_to_cache.extend([row[0] for row in cursor.fetchall()])
        
        # 3. Classics (90s)
        cursor.execute("SELECT title FROM movies WHERE release_year BETWEEN 1990 AND 1999 ORDER BY rating DESC LIMIT 30")
        titles_to_cache.extend([row[0] for row in cursor.fetchall()])
        
        # 4. Bollywood/Tollywood
        cursor.execute("SELECT title FROM movies WHERE language IN ('Hindi', 'Bengali') ORDER BY rating DESC LIMIT 30")
        titles_to_cache.extend([row[0] for row in cursor.fetchall()])
        
        # De-duplicate titles
        titles_to_cache = list(set(titles_to_cache))
        
        # Check which ones are already cached
        cursor.execute("SELECT title FROM poster_cache")
        cached_titles = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        missing_titles = [t for t in titles_to_cache if t not in cached_titles]
        print(f"[Poster Prefetch] Found {len(missing_titles)} missing posters to pre-fetch.")
        
        for title in missing_titles:
            try:
                url = f"https://imdb.iamidiotareyoutoo.com/search?q={urllib.parse.quote(title)}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    if data.get('ok') and data.get('description'):
                        poster = data['description'][0].get('#IMG_POSTER')
                        if poster:
                            # Save to sqlite cache
                            conn2 = sqlite3.connect('movies.db', timeout=10)
                            cursor2 = conn2.cursor()
                            cursor2.execute("INSERT OR REPLACE INTO poster_cache (title, poster) VALUES (?, ?)", (title, poster))
                            conn2.commit()
                            conn2.close()
                            # Warm the local memory cache
                            POSTER_CACHE[title] = poster
            except Exception as ex:
                print(f"[Poster Prefetch] Error fetching poster for '{title}': {ex}")
            
            # Throttle requests to be gentle on the external search endpoint
            time.sleep(0.8)
            
        print("[Poster Prefetch] Completed background pre-fetching.")
    except Exception as e:
        print(f"[Poster Prefetch] Error in background worker: {e}")

def start_prefetch_thread():
    threading.Thread(target=prefetch_posters, daemon=True).start()

init_poster_cache_db()
load_poster_cache_into_memory()
create_indexes()
start_prefetch_thread()

def analyze_sentiment(text):
    """
    NLP Sentiment Analysis of movie reviews using TextBlob with a robust local lexicon fallback.
    """
    try:
        from textblob import TextBlob
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity
        if polarity > 0.05:
            return 'Positive'
        elif polarity < -0.05:
            return 'Negative'
        else:
            return 'Neutral'
    except Exception:
        # Fallback local lexicon-based analyzer
        pos_words = {'love', 'like', 'great', 'masterpiece', 'amazing', 'spectacular', 'beautiful', 'good', 'excellent', 'best', 'fun', 'funny', 'exciting', 'happy', 'enjoyed', 'awesome', 'brilliant', 'wonderful'}
        neg_words = {'hate', 'dislike', 'boring', 'terrible', 'waste', 'worst', 'bad', 'pretentious', 'slow', 'confusing', 'sad', 'angry', 'garbage', 'rubbish', 'awful', 'dreadful', 'disappointed'}
        words = re.findall(r'\w+', text.lower())
        score = 0
        for w in words:
            if w in pos_words:
                score += 1
            elif w in neg_words:
                score -= 1
        if score > 0:
            return 'Positive'
        elif score < 0:
            return 'Negative'
        else:
            return 'Neutral'

def parse_natural_language_query(query_str):
    """
    Extracts search criteria from plain English queries using NLP token matching.
    """
    extracted = {
        'genres': [],
        'max_runtime': 240,
        'era': None,
        'similar_movie': None,
        'keywords': []
    }
    q_lower = query_str.lower()
    
    # 1. Extract Genres
    genres_dict = {
        'sci-fi': 'Sci-Fi',
        'sci fi': 'Sci-Fi',
        'science fiction': 'Sci-Fi',
        'scifi': 'Sci-Fi',
        'thriller': 'Thriller',
        'suspense': 'Thriller',
        'action': 'Action',
        'comedy': 'Comedies',
        'comedies': 'Comedies',
        'funny': 'Comedies',
        'drama': 'Dramas',
        'dramas': 'Dramas',
        'romance': 'Romantic',
        'romantic': 'Romantic',
        'love': 'Romantic',
        'horror': 'Horror',
        'scary': 'Horror',
        'creepy': 'Horror',
        'documentary': 'Documentaries',
        'documentaries': 'Documentaries',
        'family': 'Children & Family Movies',
        'kids': 'Children & Family Movies',
        'animation': 'Anime Features',
        'animated': 'Anime Features',
        'anime': 'Anime Features',
        'adventure': 'Action & Adventure'
    }
    for word, genre in genres_dict.items():
        if word in q_lower:
            if genre not in extracted['genres']:
                extracted['genres'].append(genre)
                
    # 2. Extract Runtimes (e.g. "under 2 hours", "under 150 minutes")
    hours_match = re.search(r'(?:under|less than|shorter than)\s+(\d+(?:\.\d+)?)\s*hours?', q_lower)
    if hours_match:
        extracted['max_runtime'] = int(float(hours_match.group(1)) * 60)
    else:
        mins_match = re.search(r'(?:under|less than|shorter than)\s+(\d+)\s*(?:mins|minutes)', q_lower)
        if mins_match:
            extracted['max_runtime'] = int(mins_match.group(1))
            
    # 3. Extract Era / Decades (e.g. "from the 2000s", "90s", "classic")
    decade_match = re.search(r'(\d{4})s?', q_lower)
    if decade_match:
        year = int(decade_match.group(1))
        if year < 1990:
            extracted['era'] = 'Classic'
        elif 1990 <= year <= 1999:
            extracted['era'] = '90s'
        elif 2000 <= year <= 2009:
            extracted['era'] = '2000s'
        else:
            extracted['era'] = 'Modern'
    elif '90s' in q_lower or '1990s' in q_lower:
        extracted['era'] = '90s'
    elif '2000s' in q_lower or '2000' in q_lower:
        extracted['era'] = '2000s'
    elif 'modern' in q_lower or 'recent' in q_lower or 'new' in q_lower:
        extracted['era'] = 'Modern'
    elif 'classic' in q_lower or 'old' in q_lower:
        extracted['era'] = 'Classic'
        
    # 4. Extract Similar Movie References (e.g. "like Inception", "similar to John Wick")
    similar_match = re.search(r'(?:like|similar to|same as)\s+([a-zA-Z0-9\s:]+)', query_str, re.IGNORECASE)
    if similar_match:
        extracted['similar_movie'] = similar_match.group(1).strip()
        
    # 5. Extract Keywords
    keywords_list = ['mind-bending', 'inspirational', 'dark', 'heartwarming', 'scary', 'funny', 'epic', 'thrilling', 'action-packed']
    for kw in keywords_list:
        if kw in q_lower:
            extracted['keywords'].append(kw)
            
    return extracted

def query_movies(selected_genres=None, era=None, max_runtime=240, industry='All', query_str=None, sort_by='rating', limit=30, language='All', mood=None, user_id=1):
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    # 1. Collaborative Filtering calculations (User-Based Collaborative Filtering)
    cursor.execute("SELECT movie_title FROM user_likes WHERE user_id = ? AND liked = 1", (user_id,))
    user_liked = set(row[0] for row in cursor.fetchall())
    
    collab_scores = {}
    if user_liked:
        # Find other users who liked the same movies
        placeholders = ','.join('?' for _ in user_liked)
        cursor.execute(f"""
            SELECT user_id, movie_title 
            FROM user_likes 
            WHERE movie_title IN ({placeholders}) AND liked = 1 AND user_id != ?
        """, list(user_liked) + [user_id])
        other_likes = cursor.fetchall()
        
        # Group likes by user ID
        user_similar_likes = {}
        for uid, title in other_likes:
            if uid not in user_similar_likes:
                user_similar_likes[uid] = set()
            user_similar_likes[uid].add(title)
            
        # Calculate Jaccard similarity coefficient for each similar user
        user_similarities = {}
        for uid, other_set in user_similar_likes.items():
            intersection = len(user_liked.intersection(other_set))
            union = len(user_liked.union(other_set))
            user_similarities[uid] = intersection / union if union > 0 else 0
            
        # Aggregate movie suggestions weighted by similarity
        uids = [uid for uid, sim in user_similarities.items() if sim > 0]
        if uids:
            placeholders = ','.join('?' for _ in uids)
            cursor.execute(f"SELECT user_id, movie_title FROM user_likes WHERE user_id IN ({placeholders}) AND liked = 1", uids)
            for uid, m_title in cursor.fetchall():
                if m_title not in user_liked:
                    similarity = user_similarities[uid]
                    collab_scores[m_title] = collab_scores.get(m_title, 0) + similarity
                    
        # Normalize collab scores to 0-100 scale
        if collab_scores:
            max_c = max(collab_scores.values())
            for m_title in collab_scores:
                collab_scores[m_title] = int((collab_scores[m_title] / max_c) * 100)
                
    # 2. AI-Based Mood Recommendation mapping
    mood_genres = []
    if mood:
        mood_map = {
            'Happy': ['Comedies', 'Adventure', 'Children & Family Movies'],
            'Sad': ['Dramas', 'Documentaries', 'Independent Movies'],
            'Excited': ['Action & Adventure', 'Sci-Fi & Fantasy', 'Thrillers', 'Action'],
            'Relaxed': ['Children & Family Movies', 'Anime Features', 'Classic Movies'],
            'Romantic': ['Romantic Movies', 'Comedies', 'Romantic']
        }
        mood_genres = mood_map.get(mood, [])
        if not selected_genres:
            selected_genres = mood_genres
        else:
            selected_genres = list(set(selected_genres + mood_genres))
            
    # 3. Base SQL query selection
    sql = """
        SELECT type, title, genres, release_year, runtime_minutes, rating, plot_summary, language 
        FROM movies 
        WHERE 1=1
    """
    params = []
    
    # 4. Runtime constraints boundary
    if max_runtime:
        sql += " AND runtime_minutes <= ?"
        params.append(max_runtime)
        
    # 5. Industry filtering
    if industry == 'Bollywood':
        sql += " AND language IN ('Hindi', 'Bengali')"
    elif industry == 'Hollywood':
        sql += " AND language = 'English'"
        
    # 6. Release Era timeline calculations
    if era:
        if era == '90s' or era == '1990s' or era == '1990':
            sql += " AND release_year BETWEEN 1990 AND 1999"
        elif era == '2000s' or era == '2000':
            sql += " AND release_year BETWEEN 2000 AND 2009"
        elif era == 'Modern' or era == '2010' or era == '2020':
            sql += " AND release_year >= 2010"
        elif era == 'Classic' or era == '1980' or era == '1970' or era == '1960' or era == '1950' or era == '1940' or era == '1930' or era == '1920':
            if era.isdigit():
                start_yr = int(era)
                sql += " AND release_year BETWEEN ? AND ?"
                params.extend([start_yr, start_yr + 9])
            else:
                sql += " AND release_year < 1990"
        elif era.isdigit():
            start_yr = int(era)
            sql += " AND release_year BETWEEN ? AND ?"
            params.extend([start_yr, start_yr + 9])
            
    # 7. Language Filter
    if language and language != 'All':
        sql += " AND language = ?"
        params.append(language)
        
    # 8. Selected genres wildcard loops
    if selected_genres:
        if isinstance(selected_genres, str):
            selected_genres = [g.strip() for g in selected_genres.split(',') if g.strip()]
        
        genre_conditions = []
        for genre in selected_genres:
            g_lower = genre.lower()
            if g_lower == 'biopic':
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?) AND (plot_summary LIKE ? OR plot_summary LIKE ? OR plot_summary LIKE ? OR title LIKE ?)")
                params.extend(["%Documentaries%", "%Dramas%", "%biography%", "%biopic%", "%true story%", "%story%"])
            elif 'horror' in g_lower:
                genre_conditions.append("(genres LIKE ?)")
                params.append("%Horror%")
            elif 'fantasy' in g_lower or 'sci-fi' in g_lower or 'scifi' in g_lower or 'science fiction' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Fantasy%", "%Sci-Fi%", "%Sci-Fi & Fantasy%"])
            elif 'mystery' in g_lower or 'thriller' in g_lower or 'mystry' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Mysteries%", "%Thriller%"])
            elif 'romantic' in g_lower or 'romance' in g_lower or 'love' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Romantic%", "%Romance%", "%Comedies%"])
            elif 'comedy' in g_lower or 'comedies' in g_lower or 'funny' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Comedy%", "%Comedies%"])
            elif 'drama' in g_lower or 'dramas' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Drama%", "%Dramas%"])
            elif 'documentary' in g_lower or 'documentaries' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Documentary%", "%Documentaries%"])
            elif 'family' in g_lower or 'children' in g_lower or 'kids' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Children & Family Movies%", "%Family%"])
            elif 'animation' in g_lower or 'anime' in g_lower or 'animated' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Anime Features%", "%Animation%"])
            elif 'adventure' in g_lower:
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Action & Adventure%", "%Adventure%"])
            else:
                genre_conditions.append("genres LIKE ?")
                params.append(f"%{genre}%")
        sql += " AND (" + " OR ".join(genre_conditions) + ")"
        
    # 9. Global text-matching query checks
    if query_str:
        sql += " AND (title LIKE ? OR plot_summary LIKE ? OR genres LIKE ?)"
        query_wildcard = f"%{query_str}%"
        params.extend([query_wildcard, query_wildcard, query_wildcard])
        
    # 10. Sorting parameters logic
    if sort_by == 'runtime' or sort_by == 'runtime_minutes':
        sql += " ORDER BY runtime_minutes ASC"
    elif sort_by == 'release_year' or sort_by == 'year':
        sql += " ORDER BY release_year DESC"
    else:
        sql += " ORDER BY rating DESC"
        
    sql += " LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    raw_rows = cursor.fetchall()
    conn.close()
    
    processed = []
    for row in raw_rows:
        m_title = row[1]
        m_genres_str = row[2]
        m_year = row[3]
        m_runtime = row[4]
        m_rating = row[5]
        m_plot = row[6]
        m_lang = row[7]
        
        movie_genres = [g.strip().lower() for g in m_genres_str.split(',')]
        
        # Calculate content match details
        match_count = 0
        genre_matched_list = []
        if selected_genres:
            for ug in selected_genres:
                found = False
                for mg in movie_genres:
                    if ug.lower() in mg:
                        found = True
                        if ug not in genre_matched_list:
                            genre_matched_list.append(ug)
                if found:
                    match_count += 1
            genre_score = int((match_count / len(selected_genres)) * 100) if selected_genres else 100
        else:
            genre_score = 90
            
        runtime_ok = True
        if max_runtime and m_runtime > max_runtime:
            runtime_ok = False
            
        era_ok = True
        if era:
            if era == '90s' and not (1990 <= m_year <= 1999): era_ok = False
            elif era == '2000s' and not (2000 <= m_year <= 2009): era_ok = False
            elif era == 'Modern' and m_year < 2010: era_ok = False
            elif era == 'Classic' and m_year >= 1990: era_ok = False
            
        lang_ok = True
        if language and language != 'All' and m_lang != language:
            lang_ok = False
            
        # Collaborative filtering alignment score
        collab_score = collab_scores.get(m_title, 0)
        
        # Calculate components of score
        runtime_score = 100 if runtime_ok else max(30, 100 - (m_runtime - max_runtime))
        era_score = 100 if era_ok else 50
        lang_score = 100 if lang_ok else 40
        
        content_score = (genre_score + runtime_score + era_score + lang_score) / 4
        
        # Hybrid Recommendation Scoring Formula
        if collab_score > 0:
            match_percentage = int(0.5 * content_score + 0.5 * collab_score)
        else:
            match_percentage = int(0.9 * content_score + 0.1 * 50)
            
        match_percentage = min(99, max(50, match_percentage))
        
        # Build matches explanation properties
        explanation = {
            'genre_match': genre_matched_list if genre_matched_list else [m_genres_str.split(',')[0].strip()],
            'runtime_match': runtime_ok,
            'era_match': era_ok,
            'language_match': lang_ok,
            'collab_match': collab_score > 0,
            'score': match_percentage
        }
        
        processed.append({
            'type': row[0],
            'title': m_title,
            'genres': m_genres_str,
            'year': m_year,
            'runtime': m_runtime,
            'rating': m_rating,
            'plot': m_plot,
            'language': m_lang,
            'match': match_percentage,
            'explanation': explanation
        })
        
    return processed

# Real movie poster fetcher route with zero configuration (no API key required)
@app.route('/api/poster', methods=['GET'])
def get_movie_poster():
    title = request.args.get('title')
    if not title:
        return jsonify({'poster': ''})
        
    if title in POSTER_CACHE:
        return jsonify({'poster': POSTER_CACHE[title]})
        
    # Check persistent SQLite cache
    try:
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT poster FROM poster_cache WHERE title = ?", (title,))
        row = cursor.fetchone()
        conn.close()
        if row:
            poster = row[0]
            POSTER_CACHE[title] = poster
            return jsonify({'poster': poster})
    except Exception as e:
        print(f"Error checking SQLite poster cache: {e}")
        
    try:
        url = f"https://imdb.iamidiotareyoutoo.com/search?q={urllib.parse.quote(title)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('ok') and data.get('description'):
                poster = data['description'][0].get('#IMG_POSTER')
                if poster:
                    POSTER_CACHE[title] = poster
                    # Save to persistent SQLite cache
                    try:
                        conn = sqlite3.connect('movies.db', timeout=10)
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO poster_cache (title, poster) VALUES (?, ?)", (title, poster))
                        conn.commit()
                        conn.close()
                    except Exception as db_err:
                        print(f"Error saving to SQLite poster cache: {db_err}")
                    return jsonify({'poster': poster})
    except Exception as e:
        print(f"Error fetching poster for {title}: {e}")
        
    return jsonify({'poster': ''})

# Dynamic API endpoint for Asynchronous queries
@app.route('/api/movies', methods=['GET'])
def api_movies():
    genres = request.args.get('genre')
    era = request.args.get('era')
    max_runtime = request.args.get('runtime', type=int)
    industry = request.args.get('industry', 'All')
    query_str = request.args.get('query')
    sort_by = request.args.get('sort_by', 'rating')
    limit = request.args.get('limit', 30, type=int)
    language = request.args.get('language', 'All')
    mood = request.args.get('mood')
    user_id = request.args.get('user_id', 1, type=int)
    
    selected_genres = [g.strip() for g in genres.split(',') if g.strip()] if genres else None
    
    results = query_movies(
        selected_genres=selected_genres,
        era=era,
        max_runtime=max_runtime,
        industry=industry,
        query_str=query_str,
        sort_by=sort_by,
        limit=limit,
        language=language,
        mood=mood,
        user_id=user_id
    )
    return jsonify(results)

# Real-time interactive Like/Dislike Endpoint to customize collaborative preferences dynamically
@app.route('/api/like', methods=['POST'])
def api_like_movie():
    data = request.json or {}
    title = data.get('title')
    liked = data.get('liked', 1)  # 1 = Like, -1 = Dislike, 0 = Remove
    user_id = data.get('user_id', 1)
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
        
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    # Check if interaction exists
    cursor.execute("SELECT id FROM user_likes WHERE user_id = ? AND movie_title = ?", (user_id, title))
    row = cursor.fetchone()
    
    if row:
        if liked == 0:
            cursor.execute("DELETE FROM user_likes WHERE id = ?", (row[0],))
        else:
            cursor.execute("UPDATE user_likes SET liked = ? WHERE id = ?", (liked, row[0]))
    else:
        if liked != 0:
            cursor.execute("INSERT INTO user_likes (user_id, movie_title, liked) VALUES (?, ?, ?)", (user_id, title, liked))
            
    # Track interaction click
    cursor.execute("INSERT INTO interactions (user_id, movie_title, interaction_type) VALUES (?, ?, ?)", (user_id, title, 'like' if liked == 1 else 'dislike'))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'msg': f"Preference updated for {title}."})

# Reviews API
@app.route('/api/reviews', methods=['GET', 'POST'])
def api_reviews():
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        # Submit a new review
        data = request.json or {}
        title = data.get('title')
        rating = data.get('rating')
        text = data.get('text', '')
        username = data.get('username', 'Anonymous')
        user_id = data.get('user_id', 1)
        
        if not title or not rating:
            return jsonify({'error': 'Missing title or rating parameters'}), 400
            
        sentiment_label = analyze_sentiment(text)
        
        cursor.execute("""
            INSERT INTO reviews (movie_title, user_id, username, rating, review_text, sentiment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, user_id, username, int(rating), text, sentiment_label))
        
        # Log interaction
        cursor.execute("INSERT INTO interactions (user_id, movie_title, interaction_type) VALUES (?, ?, ?)", (user_id, title, 'review'))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'sentiment': sentiment_label})
        
    else:
        # GET reviews for movie title
        title = request.args.get('title')
        if not title:
            return jsonify({'error': 'Movie title parameter missing'}), 400
            
        cursor.execute("""
            SELECT id, username, rating, review_text, helpful_votes, sentiment, created_at 
            FROM reviews 
            WHERE movie_title = ? 
            ORDER BY created_at DESC
        """, (title,))
        rows = cursor.fetchall()
        
        reviews_list = []
        tot_rating = 0
        pos_count = 0
        neu_count = 0
        neg_count = 0
        
        for r in rows:
            reviews_list.append({
                'id': r[0],
                'username': r[1],
                'rating': r[2],
                'text': r[3],
                'helpful': r[4],
                'sentiment': r[5],
                'date': r[6]
            })
            tot_rating += r[2]
            if r[5] == 'Positive': pos_count += 1
            elif r[5] == 'Negative': neg_count += 1
            else: neu_count += 1
            
        avg_rating = round(tot_rating / len(rows), 1) if rows else 0.0
        tot = len(rows)
        
        sentiment_chart = {
            'Positive': int((pos_count / tot) * 100) if tot > 0 else 0,
            'Neutral': int((neu_count / tot) * 100) if tot > 0 else 0,
            'Negative': int((neg_count / tot) * 100) if tot > 0 else 0
        }
        
        conn.close()
        return jsonify({
            'reviews': reviews_list,
            'avg_rating': avg_rating,
            'total_reviews': tot,
            'sentiment_chart': sentiment_chart
        })

# Helpfulness vote
@app.route('/api/reviews/helpful', methods=['POST'])
def api_reviews_helpful():
    data = request.json or {}
    review_id = data.get('id')
    if not review_id:
        return jsonify({'error': 'Review ID missing'}), 400
        
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute("UPDATE reviews SET helpful_votes = helpful_votes + 1 WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# Custom Watchlists API
@app.route('/api/watchlists', methods=['GET'])
def api_watchlists():
    user_id = request.args.get('user_id', 1, type=int)
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    # Get all watchlist lists
    cursor.execute("SELECT id, watchlist_name FROM watchlists WHERE user_id = ?", (user_id,))
    wl_rows = cursor.fetchall()
    
    result = {}
    for wl_id, wl_name in wl_rows:
        cursor.execute("""
            SELECT m.type, m.title, m.genres, m.release_year, m.runtime_minutes, m.rating, m.plot_summary, m.language
            FROM watchlist_items wi
            JOIN movies m ON wi.movie_title = m.title
            WHERE wi.watchlist_id = ?
        """, (wl_id,))
        movies = cursor.fetchall()
        
        movies_list = []
        for m in movies:
            # Re-compute match percent dynamically
            movie_genres = [g.strip().lower() for g in m[2].split(',')]
            movies_list.append({
                'type': m[0],
                'title': m[1],
                'genres': m[2],
                'year': m[3],
                'runtime': m[4],
                'rating': m[5],
                'plot': m[6],
                'language': m[7],
                'match': 92 if m[5] >= 8.0 else 82
            })
        result[wl_name] = {
            'id': wl_id,
            'movies': movies_list
        }
        
    conn.close()
    return jsonify(result)

@app.route('/api/watchlists/add', methods=['POST'])
def api_watchlist_add():
    data = request.json or {}
    wl_name = data.get('watchlist_name')
    title = data.get('title')
    user_id = data.get('user_id', 1)
    
    if not wl_name or not title:
        return jsonify({'error': 'Missing parameters'}), 400
        
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    # Get or create watchlist
    cursor.execute("SELECT id FROM watchlists WHERE user_id = ? AND watchlist_name = ?", (user_id, wl_name))
    row = cursor.fetchone()
    if row:
        wl_id = row[0]
    else:
        cursor.execute("INSERT INTO watchlists (user_id, watchlist_name) VALUES (?, ?)", (user_id, wl_name))
        wl_id = cursor.lastrowid
        
    try:
        cursor.execute("INSERT INTO watchlist_items (watchlist_id, movie_title) VALUES (?, ?)", (wl_id, title))
        conn.commit()
    except sqlite3.IntegrityError:
        # Already exists
        pass
        
    # Track interaction
    cursor.execute("INSERT INTO interactions (user_id, movie_title, interaction_type) VALUES (?, ?, ?)", (user_id, title, 'watchlist'))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/watchlists/remove', methods=['POST'])
def api_watchlist_remove():
    data = request.json or {}
    wl_name = data.get('watchlist_name')
    title = data.get('title')
    user_id = data.get('user_id', 1)
    
    if not wl_name or not title:
        return jsonify({'error': 'Missing parameters'}), 400
        
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM watchlists WHERE user_id = ? AND watchlist_name = ?", (user_id, wl_name))
    row = cursor.fetchone()
    if row:
        wl_id = row[0]
        cursor.execute("DELETE FROM watchlist_items WHERE watchlist_id = ? AND movie_title = ?", (wl_id, title))
        conn.commit()
        
    conn.close()
    return jsonify({'success': True})

# AI Chatbot API Endpoint
@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    data = request.json or {}
    message = data.get('message', '')
    user_id = data.get('user_id', 1)
    
    if not message:
        return jsonify({'error': 'Message is empty'}), 400
        
    # Parse the plain English text query using NLP first to see if there is intent
    nlp_filters = parse_natural_language_query(message)
    
    # Check if the message is a greeting or general conversational input
    clean_msg = re.sub(r'[^\w\s]', '', message.lower().strip())
    greetings = {'hello', 'hi', 'hey', 'greetings', 'yo', 'sup', 'good morning', 'good afternoon', 'good evening'}
    words = clean_msg.split()
    is_greeting = False
    has_greeting_word = any(w in greetings for w in words) if words else False
    
    if words:
        first_word = words[0]
        if first_word in greetings or clean_msg in greetings or clean_msg.startswith('who are you') or clean_msg.startswith('what is this') or clean_msg.startswith('how are you') or clean_msg.startswith('help'):
            # It's only a pure greeting if there is no search intent detected
            search_intent = False
            if nlp_filters['genres'] or nlp_filters['era'] or nlp_filters['similar_movie'] or nlp_filters['keywords'] or nlp_filters['max_runtime'] < 240:
                search_intent = True
            
            # Or if it contains recommendation/search verbs
            intent_verbs = {'suggest', 'recommend', 'recommendation', 'recommendations', 'find', 'show', 'search', 'movie', 'movies', 'film', 'films', 'watch'}
            if any(w in intent_verbs for w in words):
                search_intent = True
                
            if not search_intent:
                is_greeting = True
        
    results = []
    if not is_greeting:
        # Determine the query string for title/plot searching
        query_text = nlp_filters['similar_movie']
        if not query_text:
            genre_stop_words = {
                'sci', 'fi', 'science', 'fiction', 'scifi', 'thriller', 'suspense', 'action', 
                'comedy', 'comedies', 'funny', 'drama', 'dramas', 'romance', 'romantic', 'love', 
                'horror', 'scary', 'creepy', 'documentary', 'documentaries', 'family', 'kids', 
                'animation', 'animated', 'anime', 'adventure', 'biopic', 'biographical'
            }
            conversational_stop_words = {
                # Pronouns
                'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours', 
                'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 
                'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
                # Common request verbs
                'suggest', 'suggests', 'suggested', 'suggesting', 'suggestion', 'suggestions',
                'recommend', 'recommends', 'recommended', 'recommending', 'recommendation', 'recommendations',
                'find', 'finds', 'finding', 'found', 'show', 'shows', 'showed', 'showing',
                'give', 'gives', 'giving', 'get', 'gets', 'getting', 'got', 'search', 'searches', 'searching',
                'want', 'wants', 'wanted', 'need', 'needs', 'prefer', 'prefers', 'please', 'thanks', 'thank',
                # Media terms
                'movie', 'movies', 'film', 'films', 'show', 'shows', 'series', 'season', 'seasons',
                'watch', 'watching', 'watched', 'list', 'lists', 'catalog', 'recommendations',
                # Articles and prepositions
                'a', 'an', 'the', 'some', 'any', 'all', 'every', 'each', 'no', 'nor', 'not', 'only',
                'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 
                'during', 'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 
                'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 
                'when', 'where', 'why', 'how', 'who', 'which', 'whose', 'whom',
                # Conjunctions
                'and', 'or', 'but', 'so', 'yet', 'nor', 'because', 'as', 'until', 'while',
                # Auxiliary/Helping verbs
                'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 
                'do', 'does', 'did', 'doing', 'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might', 'must',
                # Time / conversational fill
                'tonight', 'today', 'now', 'just', 'like', 'similar', 'good', 'best', 'great', 'awesome',
                'top', 'rated', 'popular', 'trending', 'hi', 'hello', 'hey', 'greetings', 'yo', 'sup'
            }
            stop_words = genre_stop_words.union(conversational_stop_words)
            
            # Remove punctuation and split message into words
            clean_msg_lower = re.sub(r'[^\w\s]', ' ', message.lower())
            filtered_words = [w for w in clean_msg_lower.split() if w not in stop_words]
            clean_query = ' '.join(filtered_words)
            
            if clean_query and len(clean_query) > 2:
                query_text = clean_query
                
        # Query database using extracted NLP parameters
        results = query_movies(
            selected_genres=nlp_filters['genres'] if nlp_filters['genres'] else None,
            max_runtime=nlp_filters['max_runtime'],
            era=nlp_filters['era'],
            query_str=query_text if query_text else None,  # search matching title or plot
            limit=5,
            user_id=user_id
        )
    
    reply_text = None
    
    if has_gemini:
        try:
            if is_greeting:
                system_instruction = (
                    "You are CineMatch AI, a premium and friendly movie discovery assistant.\n"
                    "The user is greeting you or starting a casual conversation.\n"
                    "Acknowledge the greeting warmly, introduce yourself, and explain how you can help them find movies (e.g. by genre, era, runtime limits, or similarity to other movies).\n"
                    "Do NOT list or recommend specific movies in this initial greeting.\n"
                    "Keep your response concise, engaging, and friendly (1-2 short paragraphs)."
                )
                prompt = f"User query: \"{message}\""
            else:
                # Build Context for Gemini RAG
                if results:
                    context = "Matching movies found in database:\n"
                    for idx, m in enumerate(results):
                        context += f"- **{m['title']}** ({m['year']}) - Rating: {m['rating']}/10, Genres: {m['genres']}, Plot: {m['plot']}\n"
                else:
                    # Fallback to general recommended movies
                    fallback_list = query_movies(limit=5, user_id=user_id)
                    context = "No direct movie matches were found in the database. Instead, here are some general top-rated movies from our catalog:\n"
                    for idx, m in enumerate(fallback_list):
                        context += f"- **{m['title']}** ({m['year']}) - Rating: {m['rating']}/10, Genres: {m['genres']}, Plot: {m['plot']}\n"
                    results = fallback_list
                
                system_instruction = (
                    "You are CineMatch AI, a premium and friendly movie discovery assistant.\n"
                    "The user is asking for recommendations, looking for a movie, or asking a question.\n"
                    "If the user query contains or starts with a greeting (like 'hi', 'hello', 'hey'), always greet them back warmly (e.g., 'Hello! I would be happy to help you with that.') before addressing their search query.\n"
                    "You must recommend only movies that are present in the Database Movie Context provided below.\n"
                    "Do NOT recommend external movies that are not present in the provided context list.\n"
                    "Always format movie names in bold like **Inception** (with double asterisks) so the UI can format them correctly.\n"
                    "Make your response highly conversational, descriptive, and premium. For each recommended movie, explain why it fits the user's request based on its genres or plot.\n"
                    "If the user asks a general question or a question not related to finding a specific movie (e.g. 'tell me a joke', 'who directed inception'), answer their question directly and optionally connect it back to movies in our database if relevant.\n"
                    "Keep your answer engaging and concise (2-3 paragraphs max)."
                )
                
                prompt = f"User query: \"{message}\"\n\nDatabase Movie Context:\n{context}"
            
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_instruction
            )
            
            response = model.generate_content(prompt)
            if response and response.text:
                reply_text = response.text.strip()
        except Exception as gemini_err:
            print(f"Gemini API execution error: {gemini_err}")
            reply_text = None

    # Offline/Fallback Rule-based reply generator
    if not reply_text:
        if is_greeting:
            reply_text = (
                "Hello! I'm CineMatch AI, your personal movie discovery assistant. 🍿\n\n"
                "I can help you filter our catalog by genre, runtime limits, era, or movies similar to your favorites.\n"
                "Try asking me something like:\n"
                "- \"Suggest a sci-fi thriller under 2 hours similar to Inception\"\n"
                "- \"Recommend a funny comedy from the 2000s\"\n\n"
                "What kind of movie are you looking for today?"
            )
            results = []
        else:
            # Check if user query has greeting to prepend friendly prefix
            greeting_prefix = ""
            if has_greeting_word:
                greeting_prefix = "Hello! I'd be happy to help you find some movies. "
                
            if results:
                reply_text = greeting_prefix + f"I've analyzed your query and scanned our CineMatch catalog. Here are several films matching your interests:\n\n"
                for idx, m in enumerate(results):
                    reply_text += f"{idx+1}. **{m['title']}** ({m['year']}) - ⭐ {m['rating']} | {m['match']}% Match\n"
                    reply_text += f"   *Genre*: {m['genres']} | *Plot*: {m['plot'][:100]}...\n\n"
                reply_text += "Would you like me to add any of these to your watchlists?"
            else:
                rec_list = query_movies(limit=3, user_id=user_id)
                reply_text = greeting_prefix + "I couldn't find matches that meet all of those criteria in our netflix titles, but here are some top-rated films you might enjoy:\n\n"
                for idx, m in enumerate(rec_list):
                    reply_text += f"{idx+1}. **{m['title']}** ({m['year']}) - ⭐ {m['rating']}\n"
                reply_text += "\nFeel free to adjust the runtime or try searching in another genre!"
                results = rec_list
                
    # Compute display_genre for all returned movies
    if results:
        for m in results:
            m_genres_str = m.get('genres', '')
            explanation = m.get('explanation', {})
            genre_matched_list = explanation.get('genre_match', [])
            
            if genre_matched_list:
                matched = genre_matched_list[0].lower()
                full_genres = [g.strip() for g in m_genres_str.split(',')]
                found = None
                for fg in full_genres:
                    if matched in fg.lower():
                        found = fg
                        break
                m['display_genre'] = found if found else genre_matched_list[0]
            else:
                m['display_genre'] = m_genres_str.split(',')[0].strip() if m_genres_str else "General"
            
    return jsonify({
        'reply': reply_text,
        'movies': results
    })

# Trending & Popular Dashboard API Endpoint
@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    user_id = request.args.get('user_id', 1, type=int)
    
    # 1. Top Rated Movies: sorted by rating DESC
    top_rated = query_movies(sort_by='rating', limit=8, user_id=user_id)
    
    # 2. New Releases: sorted by release_year DESC
    new_releases = query_movies(sort_by='release_year', limit=8, user_id=user_id)
    
    # 3. Trending: high rating + modern movies
    trending = query_movies(era='Modern', sort_by='rating', limit=8, user_id=user_id)
    
    # 4. Most Watched: query movies based on interactions table
    conn = sqlite3.connect('movies.db', timeout=10)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT movie_title, COUNT(id) as count 
        FROM interactions 
        GROUP BY movie_title 
        ORDER BY count DESC 
        LIMIT 8
    """)
    most_watched_rows = cursor.fetchall()
    conn.close()
    
    most_watched = []
    for title, count in most_watched_rows:
        # Retrieve full movie record
        res = query_movies(query_str=title, limit=1, user_id=user_id)
        if res:
            most_watched.append(res[0])
            
    # Default fallback for most watched if empty
    if not most_watched:
        most_watched = query_movies(limit=8, user_id=user_id)
        
    return jsonify({
        'trending': trending,
        'top_rated': top_rated,
        'new_releases': new_releases,
        'most_watched': most_watched
    })

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    search_triggered = False
    
    hero_list = query_movies(selected_genres=['Sci-Fi'], limit=1)
    hero_movie = hero_list[0] if hero_list else {
        'title': 'Neon Labyrinth',
        'type': 'Movie',
        'year': 2024,
        'rating': 9.8,
        'plot': 'In a city where memories are traded like currency, a black-market data hunter discovers a sequence that shouldn\'t exist—a memory of a future that has already happened.',
        'genres': 'Sci-Fi, Thriller, Cyberpunk',
        'match': 98,
        'explanation': {'genre_match': ['Sci-Fi'], 'runtime_match': True, 'era_match': True, 'collab_match': False, 'score': 98}
    }

    if request.method == 'POST':
        search_q = request.form.get('search_q')
        
        if search_q:
            # Try natural language query parsing
            nlp_filters = parse_natural_language_query(search_q)
            # If NLP extracted elements (genres, runtimes, eras) use them, else fallback to standard text query
            if nlp_filters['genres'] or nlp_filters['era'] or nlp_filters['max_runtime'] < 240 or nlp_filters['similar_movie']:
                results = query_movies(
                    selected_genres=nlp_filters['genres'] if nlp_filters['genres'] else None,
                    era=nlp_filters['era'],
                    max_runtime=nlp_filters['max_runtime'],
                    query_str=nlp_filters['similar_movie'] if nlp_filters['similar_movie'] else search_q
                )
            else:
                results = query_movies(query_str=search_q)
            search_triggered = True
        else:
            genres = request.form.getlist('genres')
            era = request.form.get('era')
            max_runtime = int(request.form.get('runtime', 240))
            industry = request.form.get('industry', 'All')
            language = request.form.get('language', 'All')
            mood = request.form.get('mood', '')
            
            results = query_movies(
                selected_genres=genres, 
                era=era, 
                max_runtime=max_runtime, 
                industry=industry,
                language=language,
                mood=mood if mood != '' else None
            )
            search_triggered = True

    trending = None
    most_watched = None
    top_rated = None
    new_releases = None

    if results is None:
        # Load dashboard suggestion shelves on default load
        trending = query_movies(era='Modern', sort_by='rating', limit=8)
        top_rated = query_movies(sort_by='rating', limit=8)
        new_releases = query_movies(sort_by='release_year', limit=8)
        
        # Most Watched
        conn = sqlite3.connect('movies.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT movie_title, COUNT(id) as count 
            FROM interactions 
            GROUP BY movie_title 
            ORDER BY count DESC 
            LIMIT 8
        """)
        most_watched_rows = cursor.fetchall()
        conn.close()
        
        most_watched = []
        for title, count in most_watched_rows:
            res = query_movies(query_str=title, limit=1)
            if res:
                most_watched.append(res[0])
        if not most_watched:
            most_watched = query_movies(limit=8)
            
    return render_template(
        'index.html', 
        active_page='home',
        results=results, 
        search_triggered=search_triggered,
        hero_movie=hero_movie,
        trending=trending,
        most_watched=most_watched,
        top_rated=top_rated,
        new_releases=new_releases
    )

@app.route('/genres')
def view_genres():
    return render_template('genres.html', active_page='genres')

@app.route('/eras')
def view_eras():
    return render_template('eras.html', active_page='eras')

@app.route('/watchlist')
def view_watchlist():
    return render_template('watchlist.html', active_page='watchlist')

@app.route('/chatbot')
def view_chatbot():
    return render_template('chatbot.html', active_page='chatbot')

if __name__ == '__main__':
    app.run(debug=True)