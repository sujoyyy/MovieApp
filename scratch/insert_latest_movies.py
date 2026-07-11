import sqlite3

latest_movies = [
    # --- 2024 Blockbusters ---
    ("Movie", "Dune: Part Two", "Sci-Fi, Adventure, Action", 2024, 166, 8.8, 
     "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.", "English"),
    ("Movie", "Inside Out 2", "Animation, Comedy, Family", 2024, 96, 7.9, 
     "Follow Riley, in her teenage years, encountering new emotions like Anxiety, Envy, and Embarrassment.", "English"),
    ("Movie", "Deadpool & Wolverine", "Action, Comedy, Sci-Fi", 2024, 128, 8.0, 
     "Wolverine is recovering from his injuries when he crosses paths with the loudmouth Deadpool to defeat a common enemy.", "English"),
    ("Movie", "Gladiator II", "Action, Adventure, Drama", 2024, 150, 7.0, 
     "Years after witnessing the death of Maximus, Lucius is forced to enter the Colosseum after his home is conquered by tyrannical emperors.", "English"),
    ("Movie", "Wicked", "Fantasy, Musical, Romance", 2024, 160, 7.8, 
     "The untold story of the witches of Oz, focusing on Elphaba, the future Wicked Witch of the West, and Glinda.", "English"),
    ("Movie", "Furiosa: A Mad Max Saga", "Action, Sci-Fi, Adventure", 2024, 148, 7.6, 
     "The origin story of renegade warrior Furiosa before her encounter with Mad Max in Fury Road.", "English"),
    ("Movie", "Alien: Romulus", "Sci-Fi, Horror, Thriller", 2024, 119, 7.2, 
     "While scavenging the deep ends of a derelict space station, a group of young space colonizers come face to face with the most terrifying life force.", "English"),
    ("Movie", "The Substance", "Horror, Drama, Sci-Fi", 2024, 141, 7.7, 
     "A fading celebrity decides to use a black-market drug, a cell-replicating substance that temporarily creates a younger, better version of herself.", "English"),
    ("Movie", "Civil War", "Action, Drama, Thriller", 2024, 109, 7.1, 
     "A journey across a dystopian future America, following a team of military-embedded journalists as they race to reach D.C. before rebel factions descend.", "English"),
    ("Movie", "Twisters", "Action, Adventure, Thriller", 2024, 122, 6.8, 
     "An update to the 1996 film 'Twister', following storm chasers who risk their lives to test an experimental weather alert system.", "English"),
    ("Movie", "Conclave", "Thriller, Drama", 2024, 120, 7.5, 
     "Follows one of the world's most secretive and ancient events: selecting a new Pope, led by Cardinal Lawrence who uncovers a dark secret.", "English"),
    ("Movie", "Heretic", "Horror, Thriller", 2024, 110, 7.1, 
     "Two young missionaries are forced to prove their faith when they knock on the wrong door of a sinister homeowner.", "English"),

    # --- 2023 Masterpieces ---
    ("Movie", "Oppenheimer", "Drama, Biography, History", 2023, 180, 8.9, 
     "The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb during World War II.", "English"),
    ("Movie", "Barbie", "Comedy, Fantasy, Adventure", 2023, 114, 7.2, 
     "Stereotypical Barbie experiences a full-on existential crisis and must travel to the real world to understand herself.", "English"),
    ("Movie", "Spider-Man: Across the Spider-Verse", "Animation, Action, Adventure", 2023, 140, 8.7, 
     "Miles Morales catapults across the Multiverse, where he encounters a team of Spider-People charged with protecting its very existence.", "English"),
    ("Movie", "Killers of the Flower Moon", "Crime, Drama, History", 2023, 206, 7.6, 
     "Members of the Osage tribe in northeastern Oklahoma are murdered under mysterious circumstances in the 1920s, sparking a major FBI investigation.", "English"),
    ("Movie", "John Wick: Chapter 4", "Action, Thriller, Crime", 2023, 169, 7.7, 
     "John Wick uncovers a path to defeating The High Table. But before he can earn his freedom, Wick must face a new enemy.", "English"),
    ("Movie", "Past Lives", "Drama, Romance", 2023, 105, 7.9, 
     "Nora and Hae Sung, two deeply connected childhood friends, are wrested apart after Nora's family emigrates from South Korea.", "English"),
    ("Movie", "Anatomy of a Fall", "Drama, Thriller, Crime", 2023, 151, 7.8, 
     "A woman is suspected of murder after her husband's death in the snow, and her half-blind son faces a moral dilemma as the main witness.", "English"),
    ("Movie", "The Boy and the Heron", "Animation, Fantasy, Adventure", 2023, 124, 7.6, 
     "A young boy named Mahito yearning for his mother ventures into a world shared by the living and the dead, guided by a talking grey heron.", "English"),
    ("Movie", "Guardians of the Galaxy Vol. 3", "Sci-Fi, Action, Adventure", 2023, 150, 7.9, 
     "Still reeling from the loss of Gamora, Peter Quill rallies his team to defend the universe and protect one of their own.", "English"),
    ("Movie", "Poor Things", "Comedy, Sci-Fi, Romance", 2023, 141, 7.9, 
     "The incredible tale about the fantastical evolution of Bella Baxter, a young woman brought back to life by an unorthodox scientist.", "English"),
    ("Movie", "Godzilla Minus One", "Sci-Fi, Action, Drama", 2023, 124, 8.0, 
     "Post-war Japan is at its lowest point when a new crisis emerges in the form of a giant monster, baptized in the horrific power of the atomic bomb.", "English"),

    # --- 2022 Standouts ---
    ("Movie", "Avatar: The Way of Water", "Sci-Fi, Adventure, Action", 2022, 192, 7.6, 
     "Jake Sully lives with his newfound family on the extrasolar moon Pandora. Once a familiar threat returns, Jake must work with Neytiri.", "English"),
    ("Movie", "The Batman", "Action, Crime, Mystery", 2022, 176, 7.8, 
     "Batman ventures into Gotham City's underworld when a sadistic killer leaves behind a trail of cryptic clues.", "English"),
    ("Movie", "Top Gun: Maverick", "Action, Drama", 2022, 130, 8.3, 
     "After thirty years, Maverick is still pushing the envelope as a top naval aviator, training a detachment of graduates for a specialized mission.", "English"),
    ("Movie", "Everything Everywhere All at Once", "Sci-Fi, Comedy, Action", 2022, 139, 8.5, 
     "A middle-aged Chinese immigrant is swept up into an insane adventure in which she alone can save existence by exploring other universes.", "English"),
    ("Movie", "The Menu", "Comedy, Thriller, Horror", 2022, 107, 7.2, 
     "A young couple travels to a remote island to eat at an exclusive restaurant where the chef has prepared a lavish menu with shocking surprises.", "English"),
    ("Movie", "Nope", "Sci-Fi, Horror, Mystery", 2022, 130, 6.8, 
     "The residents of a lonely gulch in inland California bear witness to an uncanny and chilling discovery in the skies above.", "English"),

    # --- Indian Cinema (Bollywood & Pan-India) 2023-2024 ---
    ("Movie", "Kalki 2898 AD", "Sci-Fi, Action, Adventure", 2024, 180, 7.2, 
     "A modern avatar of Vishnu, a Hindu god, is believed to have descended to Earth to protect the world from evil forces in a post-apocalyptic future.", "Hindi"),
    ("Movie", "Jawan", "Action, Thriller", 2023, 168, 7.0, 
     "A personal vendetta drives a man to rectify the wrongs in society, while kept promised by a promise made years ago.", "Hindi"),
    ("Movie", "Pathaan", "Action, Thriller", 2023, 146, 6.0, 
     "An Indian agent races against a doomsday clock as a ruthless mercenary with a bitter vendetta threatens to unleash a bio-weapon.", "Hindi"),
    ("Movie", "Animal", "Action, Drama, Crime", 2023, 201, 6.2, 
     "A son's obsessive love for his father leads to a violent, bloody conflict when an assassin targets the family patriarch.", "Hindi"),
    ("Movie", "Fighter", "Action, Thriller", 2024, 166, 6.4, 
     "Top IAF aviators come together in the face of imminent danger to form Air Dragons, realizing the true meaning of camaraderie and patriotism.", "Hindi"),
    ("Movie", "Stree 2", "Comedy, Horror", 2024, 147, 7.5, 
     "In Chanderi, a headless monster named Sarkata kidnaps women, prompting the town's defenders to seek help from the legendary witch Stree.", "Hindi"),
    ("Movie", "Shaitaan", "Horror, Thriller", 2024, 132, 6.7, 
     "A family's weekend retreat turns into a nightmare when an uninvited guest uses black magic to hypnotize and take control of their daughter.", "Hindi")
]

def insert_movies():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    inserted_count = 0
    for m in latest_movies:
        m_type, title, genres, release_year, runtime, rating, plot, lang = m
        
        # Check if movie already exists
        cursor.execute("SELECT id FROM movies WHERE title = ? AND release_year = ?", (title, release_year))
        if cursor.fetchone():
            print(f"Skipping: '{title}' ({release_year}) already exists in the database.")
            continue
            
        cursor.execute("""
            INSERT INTO movies (type, title, genres, release_year, runtime_minutes, rating, plot_summary, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (m_type, title, genres, release_year, runtime, rating, plot, lang))
        inserted_count += 1
        print(f"Inserted: '{title}' ({release_year})")
        
    conn.commit()
    conn.close()
    print(f"\nSuccessfully inserted {inserted_count} new movie records.")

if __name__ == "__main__":
    insert_movies()
