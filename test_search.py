import requests
import urllib.parse
import re

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

queries = [
    '01315906086',
    'maksudur rahaman mishu',
    'maksudurrahamanmishu7',
    'maksudurrahamanmishu7@gmail.com'
]

for q in queries:
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
    try:
        res = session.get(url, timeout=8)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', res.text)
        print(f"Query: '{q}' | Status: {res.status_code} | Found emails in DDG: {emails}")
    except Exception as e:
        print(f"Error querying {q}: {e}")
