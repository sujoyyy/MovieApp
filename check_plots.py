import app

def check():
    for era in ['90s', 'Modern', '2000s', 'Classic']:
        print(f"--- Era: {era} ---")
        res = app.query_movies(era=era, limit=42)
        for m in res:
            title = m['title']
            plot = m['plot']
            genres = m['genres']
            rating = m['rating']
            year = m['year']
            
            # Check for potential JS breakers
            has_single_quote = "'" in plot or "'" in title or "'" in genres
            has_double_quote = '"' in plot or '"' in title or '"' in genres
            has_newline = '\n' in plot or '\r' in plot
            
            if has_single_quote or has_double_quote or has_newline:
                print(f"Movie: {title} ({year})")
                print(f"  Single quote: {has_single_quote}, Double quote: {has_double_quote}, Newline: {has_newline}")
                print(f"  Plot: {repr(plot)}")
                print()

if __name__ == '__main__':
    check()
