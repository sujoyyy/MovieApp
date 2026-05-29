from flask import Flask, render_template, request, jsonify
import sqlite3
import urllib.request
import urllib.parse
import json

app = Flask(__name__)

# Server-side in-memory cache to ensure extreme load speeds and avoid rate-limiting
POSTER_CACHE = {}

def query_movies(selected_genres=None, era=None, max_runtime=240, industry='All', query_str=None, sort_by='rating', limit=30):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # 1. Base query selection
    sql = """
        SELECT type, title, genres, release_year, runtime_minutes, rating, plot_summary 
        FROM movies 
        WHERE 1=1
    """
    params = []
    
    # 2. Runtime constraints boundary
    if max_runtime:
        sql += " AND runtime_minutes <= ?"
        params.append(max_runtime)
        
    # 3. Industry filtering
    if industry == 'Bollywood':
        sql += " AND genres LIKE ?"
        params.append("%International Movies%")
    elif industry == 'Hollywood':
        sql += " AND genres NOT LIKE ?"
        params.append("%International Movies%")
        
    # 4. Release Era timeline calculations
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
            
    # 5. Selected genres wildcard loops
    if selected_genres:
        if isinstance(selected_genres, str):
            selected_genres = [g.strip() for g in selected_genres.split(',') if g.strip()]
        
        genre_conditions = []
        for genre in selected_genres:
            g_lower = genre.lower()
            if g_lower == 'biopic':
                # Biopics are mapped to Documentaries or Dramas with biographical plot indicators
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?) AND (plot_summary LIKE ? OR plot_summary LIKE ? OR plot_summary LIKE ? OR title LIKE ?)")
                params.extend(["%Documentaries%", "%Dramas%", "%biography%", "%biopic%", "%true story%", "%story%"])
            elif g_lower == 'horror' or g_lower == 'horror comedy':
                genre_conditions.append("(genres LIKE ?)")
                params.append("%Horror%")
            elif g_lower == 'fantasy' or g_lower == 'fantashy':
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Fantasy%", "%Sci-Fi%"])
            elif g_lower == 'mystery' or g_lower == 'mystry':
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Mysteries%", "%Thriller%"])
            elif g_lower == 'romantic' or g_lower == 'romance':
                genre_conditions.append("(genres LIKE ? OR genres LIKE ?)")
                params.extend(["%Romantic%", "%Comedies%"])
            else:
                genre_conditions.append("genres LIKE ?")
                params.append(f"%{genre}%")
        sql += " AND (" + " OR ".join(genre_conditions) + ")"
        
    # 6. Global text-matching query checks
    if query_str:
        sql += " AND (title LIKE ? OR plot_summary LIKE ? OR genres LIKE ?)"
        query_wildcard = f"%{query_str}%"
        params.extend([query_wildcard, query_wildcard, query_wildcard])
        
    # 7. Sorting parameters logic
    if sort_by == 'runtime' or sort_by == 'runtime_minutes':
        sql += " ORDER BY runtime_minutes ASC"
    elif sort_by == 'release_year' or sort_by == 'year':
        sql += " ORDER BY release_year DESC"
    else:
        sql += " ORDER BY rating DESC"
        
    # 8. Safe boundaries limit
    sql += " LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    raw_rows = cursor.fetchall()
    conn.close()
    
    processed = []
    for row in raw_rows:
        movie_genres = [g.strip().lower() for g in row[2].split(',')]
        match_count = 0
        if selected_genres:
            for ug in selected_genres:
                if any(ug.lower() in mg for mg in movie_genres):
                    match_count += 1
            match_percentage = int((match_count / len(selected_genres)) * 100)
            match_percentage = min(match_percentage, 100)
        else:
            match_percentage = 98 if row[5] >= 8.0 else 82 # Dynamic aesthetic placeholder
            
        processed.append({
            'type': row[0],
            'title': row[1],
            'genres': row[2],
            'year': row[3],
            'runtime': row[4],
            'rating': row[5],
            'plot': row[6],
            'match': match_percentage
        })
    return processed

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
    
    selected_genres = [g.strip() for g in genres.split(',') if g.strip()] if genres else None
    
    results = query_movies(
        selected_genres=selected_genres,
        era=era,
        max_runtime=max_runtime,
        industry=industry,
        query_str=query_str,
        sort_by=sort_by,
        limit=limit
    )
    return jsonify(results)

# Real movie poster fetcher route with zero configuration (no API key required)
@app.route('/api/poster', methods=['GET'])
def get_movie_poster():
    title = request.args.get('title')
    if not title:
        return jsonify({'poster': ''})
        
    if title in POSTER_CACHE:
        return jsonify({'poster': POSTER_CACHE[title]})
        
    try:
        url = f"https://imdb.iamidiotareyoutoo.com/search?q={urllib.parse.quote(title)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('ok') and data.get('description'):
                poster = data['description'][0].get('#IMG_POSTER')
                if poster:
                    POSTER_CACHE[title] = poster
                    return jsonify({'poster': poster})
    except Exception as e:
        print(f"Error fetching poster for {title}: {e}")
        
    return jsonify({'poster': ''})

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    search_triggered = False
    
    # Retrieve dynamic hero and seeded lists for a beautiful landing experience
    # Dynamic top-match hero: find the highest-rated Sci-Fi/Drama in our database
    hero_list = query_movies(selected_genres=['Sci-Fi'], limit=1)
    hero_movie = hero_list[0] if hero_list else {
        'title': 'Neon Labyrinth',
        'type': 'Movie',
        'year': 2024,
        'rating': 9.8,
        'plot': 'In a city where memories are traded like currency, a black-market data hunter discovers a sequence that shouldn\'t exist—a memory of a future that has already happened.',
        'genres': 'Sci-Fi, Thriller, Cyberpunk',
        'match': 98
    }

    # Curated Shelves
    rec_movies = query_movies(sort_by='rating', limit=8)
    scifi_movies = query_movies(selected_genres=['Sci-Fi'], limit=8)
    classic_movies = query_movies(era='90s', limit=8)

    if request.method == 'POST':
        # Global top search bar or filter panel submission
        search_q = request.form.get('search_q')
        
        if search_q:
            results = query_movies(query_str=search_q)
            search_triggered = True
        else:
            genres = request.form.getlist('genres')
            era = request.form.get('era')
            max_runtime = int(request.form.get('runtime', 240))
            industry = request.form.get('industry', 'All')
            
            results = query_movies(selected_genres=genres, era=era, max_runtime=max_runtime, industry=industry)
            search_triggered = True
            
    return render_template(
        'index.html', 
        active_page='home',
        results=results, 
        search_triggered=search_triggered,
        hero_movie=hero_movie,
        rec_movies=rec_movies,
        scifi_movies=scifi_movies,
        classic_movies=classic_movies
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

if __name__ == '__main__':
    app.run(debug=True)