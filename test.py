import requests

api_key = "YOUR_API_KEY"
movie_name = "Interstellar"

url = f"https://www.omdbapi.com/?t={movie_name}&apikey={api_key}"

response = requests.get(url).json()

if response["Response"] == "True":
    print("Poster URL:", response["Poster"])
else:
    print("Movie not found")