import sqlite3

def print_counts():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    print("Language Distribution:")
    cursor.execute("SELECT language, count(id) FROM movies GROUP BY language")
    for r in cursor.fetchall():
        print(f"- {r[0]}: {r[1]} movies")
        
    cursor.execute("SELECT count(id) FROM movies WHERE language IN ('Hindi', 'Bengali')")
    bolly_count = cursor.fetchone()[0]
    print(f"\nTotal Bollywood Movies: {bolly_count}")
    
    conn.close()

if __name__ == '__main__':
    print_counts()