import urllib.request
import json

url = "https://imdb.iamidiotareyoutoo.com/search?q=Interstellar"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        print(json.dumps(res, indent=2)[:1000])
except Exception as e:
    print("Error:", e)
