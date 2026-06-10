import sqlite3
import csv
import re
import datetime
import os
import urllib.request

def init_netflix_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # 1. Drop existing tables if they exist
    cursor.execute('DROP TABLE IF EXISTS movies')
    cursor.execute('DROP TABLE IF EXISTS user_likes')
    cursor.execute('DROP TABLE IF EXISTS reviews')
    cursor.execute('DROP TABLE IF EXISTS watchlists')
    cursor.execute('DROP TABLE IF EXISTS watchlist_items')
    cursor.execute('DROP TABLE IF EXISTS interactions')
    
    # 2. Re-create new schema tables
    cursor.execute('''
        CREATE TABLE movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            title TEXT NOT NULL,
            genres TEXT,
            release_year INTEGER,
            runtime_minutes INTEGER,
            rating REAL,
            plot_summary TEXT,
            language TEXT DEFAULT 'English'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE user_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_title TEXT,
            liked INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_title TEXT NOT NULL,
            user_id INTEGER DEFAULT 1,
            username TEXT DEFAULT 'Anonymous',
            rating INTEGER NOT NULL,
            review_text TEXT,
            helpful_votes INTEGER DEFAULT 0,
            sentiment TEXT DEFAULT 'Neutral',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            watchlist_name TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE watchlist_items (
            watchlist_id INTEGER,
            movie_title TEXT NOT NULL,
            PRIMARY KEY (watchlist_id, movie_title)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            movie_title TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Download TMDb/IMDb movie dataset if not present
    tmdb_path = 'tmdb_movies.csv'
    if not os.path.exists(tmdb_path):
        print("Downloading TMDb/IMDb movie dataset (10,000+ movies)...")
        try:
            url = "https://raw.githubusercontent.com/deepak525/Investigate_TMDb_Movies/master/tmdb-movies.csv"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(tmdb_path, 'wb') as f:
                    f.write(response.read())
            print("Download complete.")
        except Exception as e:
            print(f"Error downloading TMDb/IMDb dataset: {e}")
            
    # Download IMDb Movies India dataset if not present
    bolly_path = 'bollywood_movies.csv'
    if not os.path.exists(bolly_path):
        print("Downloading IMDb Movies India dataset (15,000+ movies)...")
        try:
            url = "https://raw.githubusercontent.com/PDurgaAnusha/Movie-rating-prediction/master/IMDb%20Movies%20India.csv"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(bolly_path, 'wb') as f:
                    f.write(response.read())
            print("Download complete.")
        except Exception as e:
            print(f"Error downloading IMDb Movies India dataset: {e}")
            
    inserted_titles = set()
    
    # 3. Read and parse Kaggle's netflix_titles.csv data stream
    try:
        with open('netflix_titles.csv', mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            movies_to_insert = []
            
            # Simulated dummy rating generation baseline
            base_rating = 7.2 
            
            for row in csv_reader:
                # Safe parsing boundary for runtime details
                duration_str = row.get('duration', '')
                runtime = 90 # Guaranteed default fallback initialization
                
                if duration_str:
                    if 'min' in duration_str:
                        minutes = re.findall(r'\d+', duration_str)
                        if minutes:
                            runtime = int(minutes[0])
                    elif 'Season' in duration_str:
                        seasons = re.findall(r'\d+', duration_str)
                        if seasons:
                            runtime = int(seasons[0]) * 45 # approximating 45 mins per episode
                
                # Heuristic mapping for multi-language recommendations
                title_val = row.get('title', 'Unknown Title').strip()
                if not title_val or title_val.lower() in inserted_titles:
                    continue
                
                # Dynamic iteration shifting baseline score
                base_rating = round((base_rating + 0.1) if base_rating < 9.4 else 6.1, 1)
                
                genres_val = row.get('listed_in', 'General')
                desc_val = row.get('description', 'No plot summary available.')
                country_val = row.get('country', '')
                cast_val = row.get('cast', '')
                
                lang = 'English'
                if 'bengali' in desc_val.lower() or 'bengali' in title_val.lower() or 'bengali' in genres_val.lower():
                    lang = 'Bengali'
                elif 'satyajit ray' in cast_val.lower() or 'satyajit' in desc_val.lower():
                    lang = 'Bengali'
                elif 'hindi' in desc_val.lower() or 'hindi' in title_val.lower() or 'bollywood' in desc_val.lower() or 'bollywood' in genres_val.lower():
                    lang = 'Hindi'
                elif 'india' in country_val.lower():
                    # Seed 80% Hindi and 20% Bengali for Indian titles
                    lang = 'Bengali' if (len(title_val) % 5 == 0) else 'Hindi'
                
                movies_to_insert.append((
                    row.get('type', 'Movie'),
                    title_val,
                    genres_val, 
                    int(row['release_year']) if row.get('release_year') and row['release_year'].isdigit() else 2000,
                    runtime,
                    base_rating,
                    desc_val,
                    lang
                ))
                inserted_titles.add(title_val.lower())
            
            # Efficient block transaction insertion execution
            cursor.executemany('''
                INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', movies_to_insert)
            print(f"Loaded {len(movies_to_insert)} netflix records.")
            
    except FileNotFoundError:
        print("Error: Please make sure 'netflix_titles.csv' file is kept inside this same directory path.")

    # 4. Read and parse TMDb/IMDb tmdb_movies.csv data stream
    tmdb_movies_to_insert = []
    if os.path.exists(tmdb_path):
        print("Parsing TMDb/IMDb movie dataset...")
        try:
            with open(tmdb_path, mode='r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    title_val = row.get('original_title', '').strip()
                    if not title_val or title_val.lower() in inserted_titles:
                        continue
                    
                    # Convert pipe genres to comma genres
                    genres_raw = row.get('genres', 'General')
                    genres_val = genres_raw.replace('|', ', ') if genres_raw else 'General'
                    
                    # Runtime
                    runtime_str = row.get('runtime', '90')
                    try:
                        runtime = int(runtime_str) if runtime_str else 90
                    except ValueError:
                        runtime = 90
                        
                    # Rating
                    rating_str = row.get('vote_average', '7.0')
                    try:
                        rating = float(rating_str) if rating_str else 7.0
                        rating = round(rating, 1)
                    except ValueError:
                        rating = 7.0
                        
                    # Release Year
                    year_str = row.get('release_year', '2015')
                    try:
                        release_year = int(year_str) if year_str else 2015
                    except ValueError:
                        release_year = 2015
                        
                    desc_val = row.get('overview', 'No plot summary available.')
                    if not desc_val:
                        desc_val = 'No plot summary available.'
                        
                    # Add to insert list
                    tmdb_movies_to_insert.append((
                        'Movie',
                        title_val,
                        genres_val,
                        release_year,
                        runtime,
                        rating,
                        desc_val,
                        'English' # Default TMDb to English
                    ))
                    inserted_titles.add(title_val.lower())
            
            if tmdb_movies_to_insert:
                cursor.executemany('''
                    INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', tmdb_movies_to_insert)
                print(f"Loaded {len(tmdb_movies_to_insert)} TMDb/IMDb records.")
        except Exception as e:
            print(f"Error parsing TMDb movie dataset: {e}")

    # 5. Read and parse IMDb Movies India (bollywood_movies.csv) data stream
    bollywood_movies_to_insert = []
    if os.path.exists(bolly_path):
        print("Parsing IMDb Movies India dataset...")
        try:
            with open(bolly_path, mode='r', encoding='latin1') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    title_val = row.get('Name', '').strip()
                    # Skip rows that are empty or header spaces
                    if not title_val or title_val == '' or title_val.lower() in inserted_titles:
                        continue
                    
                    # Parse Year (e.g. "(2019)" -> 2019)
                    year_val = 2015
                    if row.get('Year'):
                        match_yr = re.findall(r'\d{4}', row['Year'])
                        if match_yr:
                            year_val = int(match_yr[0])
                            
                    # Parse Duration (e.g. "109 min" -> 109)
                    runtime_val = 120
                    if row.get('Duration'):
                        match_rt = re.findall(r'\d+', row['Duration'])
                        if match_rt:
                            runtime_val = int(match_rt[0])
                            
                    # Parse Rating (default to 6.5)
                    rating_val = 6.5
                    if row.get('Rating'):
                        try:
                            rating_val = float(row['Rating'])
                            rating_val = round(rating_val, 1)
                        except ValueError:
                            rating_val = 6.5
                            
                    genre_val = row.get('Genre', 'Drama')
                    director_val = row.get('Director', 'Unknown Director')
                    actor1 = row.get('Actor 1', '')
                    actor2 = row.get('Actor 2', '')
                    actor3 = row.get('Actor 3', '')
                    
                    actors_list = [a for a in [actor1, actor2, actor3] if a]
                    actor_str = ", ".join(actors_list) if actors_list else "unknown actors"
                    
                    # Build summary using metadata
                    desc_val = f"A {genre_val} film directed by {director_val}, starring {actor_str}."
                    
                    # Determine language: default to Hindi (Bollywood), classify as Bengali if keywords match
                    lang = 'Hindi'
                    desc_lower = f"{title_val} {director_val} {actor_str}".lower()
                    bengali_surnames = {'sengupta', 'chatterjee', 'mukherjee', 'banerjee', 'ray', 'chakraborty', 'majumdar', 'bengali', 'ghosh', 'bose', 'sen', 'mitra', 'dutta', 'roy', 'dasgupta', 'ganguly'}
                    if any(surname in desc_lower for surname in bengali_surnames):
                        lang = 'Bengali'
                        
                    bollywood_movies_to_insert.append((
                        'Movie',
                        title_val,
                        genre_val,
                        year_val,
                        runtime_val,
                        rating_val,
                        desc_val,
                        lang
                    ))
                    inserted_titles.add(title_val.lower())
                    
            if bollywood_movies_to_insert:
                cursor.executemany('''
                    INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', bollywood_movies_to_insert)
                print(f"Loaded {len(bollywood_movies_to_insert)} IMDb Movies India records.")
        except Exception as e:
            print(f"Error parsing IMDb Movies India dataset: {e}")

    # 6. Insert custom blockbusters to ensure exact matches for user examples
    custom_movies = [
        ('Movie', 'Inception', 'Sci-Fi, Thriller, Action', 2010, 148, 8.8, 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.', 'English'),
        ('Movie', 'The Matrix', 'Sci-Fi, Action', 1999, 136, 8.7, 'When a beautiful stranger leads computer hacker Neo to a forbidding underworld, he discovers the shocking truth--the life he knows is the elaborate deception of an evil cyber-intelligence.', 'English'),
        ('Movie', 'Interstellar', 'Sci-Fi, Drama, Sci-Fi & Fantasy', 2014, 169, 8.6, 'When Earth becomes uninhabitable, a team of explorers travels through a wormhole in space in an attempt to ensure humanity\'s survival.', 'English'),
        ('Movie', 'Minority Report', 'Sci-Fi, Action, Thriller', 2002, 145, 7.6, 'In a future where a special police unit is able to arrest murderers before they commit their crimes, an officer from that unit is himself accused of a future murder.', 'English'),
        ('Movie', 'Blade Runner 2049', 'Sci-Fi, Drama, Thriller', 2017, 164, 8.0, 'A new blade runner, LAPD Officer K, unearths a long-buried secret that has the potential to plunge what\'s left of society into chaos.', 'English'),
        ('Movie', 'John Wick', 'Action, Thriller', 2014, 101, 7.4, 'An ex-hit-man comes out of retirement to track down the gangsters that killed his dog and took everything from him.', 'English'),
        
        # New to Old blockbusters across various eras and languages
        ('Movie', 'Dune: Part Two', 'Sci-Fi, Action & Adventure, Dramas', 2024, 166, 8.6, 'Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.', 'English'),
        ('Movie', 'Oppenheimer', 'Dramas, Biopic', 2023, 180, 8.4, 'The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.', 'English'),
        ('Movie', 'Everything Everywhere All at Once', 'Action & Adventure, Comedies, Sci-Fi', 2022, 139, 8.1, 'A middle-aged Chinese immigrant is swept up into an insane adventure in which she alone can save existence by exploring other universes.', 'English'),
        ('Movie', 'The Matrix Resurrections', 'Sci-Fi, Action & Adventure', 2021, 148, 5.7, 'To find out if his reality is a physical or mental construct, Thomas Anderson will have to choose to follow the white rabbit once more.', 'English'),
        ('Movie', 'Parasite', 'Thrillers, Dramas, International Movies', 2019, 132, 8.5, 'Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.', 'English'),
        ('Movie', '3 Idiots', 'Comedies, Dramas, International Movies', 2009, 170, 8.4, 'Two friends search for their long-lost companion. They revisit their college days and recall the memories of their friend who inspired them to think differently.', 'Hindi'),
        ('Movie', 'The Dark Knight', 'Action & Adventure, Thrillers, Dramas', 2008, 152, 9.0, 'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.', 'English'),
        ('Movie', 'Titanic', 'Romantic Movies, Dramas', 1997, 194, 7.9, 'A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic.', 'English'),
        ('Movie', 'Pulp Fiction', 'Cult Movies, Thrillers, Dramas', 1994, 154, 8.9, 'The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption.', 'English'),
        ('Movie', 'Back to the Future', 'Comedies, Sci-Fi & Fantasy, Classic Movies', 1985, 116, 8.5, 'Marty McFly, a 17-year-old high school student, is accidentally sent thirty years into the past in a time-traveling DeLorean invented by his close friend, the eccentric scientist Doc Brown.', 'English'),
        ('Movie', 'The Godfather', 'Classic Movies, Dramas', 1972, 175, 9.2, 'The aging patriarch of an organized crime dynasty in postwar New York City transfers control of his clandestine empire to his reluctant youngest son.', 'English'),
        ('Movie', 'Pather Panchali', 'Classic Movies, Dramas, International Movies', 1955, 115, 8.5, 'The life of a poor family in a Bengali village, centering on the young boy Apu, his sister Durga, and their struggle for survival.', 'Bengali'),
        ('Movie', 'Casablanca', 'Classic Movies, Romantic Movies, Dramas', 1942, 102, 8.5, 'A cynical American expatriate cafe owner struggles to decide whether or not to help his former lover and her fugitive husband escape the Nazis in French Morocco.', 'English')
    ]
    
    for m in custom_movies:
        if m[1].lower() not in inserted_titles:
            cursor.execute('''
                INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', m)
            inserted_titles.add(m[1].lower())
    
    # 7. Seed watchlist categories
    watchlists = [
        (1, "Weekend Watchlist"),
        (1, "Family Watchlist"),
        (1, "Action Collection"),
        (1, "Sci-Fi Collection")
    ]
    cursor.executemany("INSERT INTO watchlists (user_id, watchlist_name) VALUES (?, ?)", watchlists)
    
    # 8. Seed user liked movies for collaborative filtering
    likes = [
        (1, 'The Matrix', 1),
        (1, 'Inception', 1),
        (2, 'The Matrix', 1),
        (2, 'Inception', 1),
        (2, 'Interstellar', 1),
        (3, 'The Matrix', 1),
        (3, 'Inception', 1),
        (3, 'Minority Report', 1),
        (3, 'Blade Runner 2049', 1),
        (4, 'The Matrix', 1),
        (4, 'Inception', 1),
        (4, 'Interstellar', 1),
        (4, 'Blade Runner 2049', 1),
        (4, 'John Wick', 1)
    ]
    cursor.executemany("INSERT INTO user_likes (user_id, movie_title, liked) VALUES (?, ?, ?)", likes)
    
    # 9. Seed movie reviews with ratings & pre-analyzed sentiments
    reviews = [
        ('Inception', 1, 'Sarah K.', 5, 'An absolute masterpiece of cinema. Mind-bending and gorgeous!', 12, 'Positive'),
        ('Inception', 1, 'John D.', 5, 'Best movie of the decade. Hands down.', 8, 'Positive'),
        ('Inception', 1, 'Mike R.', 4, 'Very clever concept, though slightly confusing on the first watch.', 3, 'Positive'),
        ('Inception', 1, 'Amy T.', 2, 'Way too complex for no reason. Pretentious dialogue.', 0, 'Negative'),
        
        ('The Matrix', 1, 'TechGuy', 5, 'Revolutionary effects and philosophy. Re-defined action movies forever.', 25, 'Positive'),
        ('The Matrix', 1, 'FilmNerd', 4, 'Excellent story and visuals, a bit dated in the fashion department.', 2, 'Positive'),
        ('The Matrix', 1, 'RetroCine', 2, 'Highly overrated. Decent action but shallow plot.', 1, 'Negative'),
        
        ('Interstellar', 1, 'AstroC', 5, 'Visually spectacular and emotionally deep. The organ score by Hans Zimmer is legendary!', 19, 'Positive'),
        ('Interstellar', 1, 'NeilA', 4, 'Great scientific accuracy and stunning visuals, though the third act is a bit logic-defying.', 6, 'Positive'),
        ('Interstellar', 1, 'CineCritic', 3, 'Tries to be 2001: A Space Odyssey but gets bogged down in melodramatic family relationship plotlines.', 4, 'Neutral'),
        
        ('Minority Report', 1, 'PhilipK', 4, 'Great adaptation. Spielberg and Cruise at their best in sci-fi detective noir.', 5, 'Positive'),
        ('Minority Report', 1, 'RoboReview', 3, 'Entertaining chase movie, but is a bit long.', 1, 'Neutral'),
        
        ('Blade Runner 2049', 1, 'NeonDreamer', 5, 'A flawless sequel that rivals the original. Visually arresting.', 14, 'Positive'),
        ('Blade Runner 2049', 1, 'K_Replica', 4, 'Visually beautiful, excellent acting by Ryan Gosling. A bit slow-paced though.', 7, 'Positive'),
        ('Blade Runner 2049', 1, 'CineBored', 1, 'Unbearably long and boring. Pretty pictures but no substance.', 5, 'Negative')
    ]
    cursor.executemany("INSERT INTO reviews (movie_title, user_id, username, rating, review_text, helpful_votes, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)", reviews)
    
    conn.commit()
    print(f"Success! {len(inserted_titles)} unique records and structured metadata populated into movies.db.")
    conn.close()

if __name__ == '__main__':
    init_netflix_db()