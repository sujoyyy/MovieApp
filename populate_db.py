import sqlite3
import csv
import re

def init_netflix_db():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Existing baseline structure drop and recreate rules
    cursor.execute('''
        DROP TABLE IF EXISTS movies
    ''')
    cursor.execute('''
        CREATE TABLE movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            title TEXT NOT NULL,
            genres TEXT,
            release_year INTEGER,
            runtime_minutes INTEGER,
            rating REAL,
            plot_summary TEXT
        )
    ''')
    
    # Reading Kaggle's netflix_titles.csv data stream
    try:
        with open('netflix_titles.csv', mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            movies_to_insert = []
            
            # Simulated dummy rating generation baseline
            base_rating = 7.2 
            
            for row in csv_reader:
                # 1. Safe parsing boundary for runtime details
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
                
                
                # 2. Dynamic iteration shifting baseline score
                base_rating = round((base_rating + 0.1) if base_rating < 9.4 else 6.1, 1)
                
                # 3. Clean string checks to append records securely
                movies_to_insert.append((
                    row.get('type', 'Movie'),
                    row.get('title', 'Unknown Title'),
                    row.get('listed_in', 'General'), 
                    int(row['release_year']) if row.get('release_year') and row['release_year'].isdigit() else 2000,
                    runtime,
                    base_rating,
                    row.get('description', 'No plot summary available.')
                ))
            
            # Efficient block transaction insertion execution
            cursor.executemany('''
                INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', movies_to_insert)
            
            conn.commit()
            print(f"Success! {len(movies_to_insert)} Netflix records structured into Knowledge Base.")
            
    except FileNotFoundError:
        print("Error: Please make sure 'netflix_titles.csv' file is kept inside this same directory path.")
        
    conn.close()

if __name__ == '__main__':
    init_netflix_db()