"""
Social & Web Profile Name Harvester
Extracts real person display names (First Name, Last Name) associated with a phone number
from Truecaller API, WhatsApp metadata, Facebook, LinkedIn, and web OSINT footprints.
"""

import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from truecaller_engine import search_truecaller, load_installation_id
from email_engine import parse_phone

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

GENERIC_WORDS = {
    'Facebook', 'LinkedIn', 'Twitter', 'Instagram', 'TikTok', 'WhatsApp',
    'Contact', 'About', 'Home', 'Profile', 'Search', 'Google', 'Phone',
    'Number', 'Directory', 'Truecaller', 'Mobile', 'Bangladesh', 'Dhaka',
    'Call', 'More', 'See', 'View', 'Download', 'Page', 'Post', 'Share', 'Details'
}


def clean_person_name(name_str: str) -> str:
    """Clean and standardize extracted person name."""
    if not name_str:
        return ""
    clean = re.sub(r'[^a-zA-Z\s]', ' ', name_str)
    words = clean.split()
    filtered = [w.capitalize() for w in words if w.capitalize() not in GENERIC_WORDS and len(w) > 1]
    if 2 <= len(filtered) <= 4:
        return " ".join(filtered)
    elif len(filtered) == 1 and len(words) >= 1:
        return filtered[0]
    return ""


def harvest_social_names(phone_number: str, default_country: str = "BD") -> dict:
    """
    Harvests real profile display names from multiple OSINT sources.
    Returns:
      {
        "primary_name": "...",
        "names": ["Name 1", "Name 2"],
        "sources": {"Truecaller": "...", "Facebook": "..."}
      }
    """
    phone_info = parse_phone(phone_number, default_country)
    e164 = phone_info.get("e164", phone_number)
    national = phone_info.get("national", phone_number).replace(" ", "").replace("-", "")

    extracted_names = []
    sources_map = {}

    # 1. Truecaller Database Lookup
    tc_token = load_installation_id()
    if tc_token:
        try:
            tc_res = search_truecaller(e164, country_code=default_country, installation_id=tc_token)
            if tc_res.get("success") and tc_res.get("name") and tc_res["name"] != "Not Found":
                name_clean = clean_person_name(tc_res["name"]) or tc_res["name"].strip()
                if name_clean and name_clean not in extracted_names:
                    extracted_names.append(name_clean)
                    sources_map[name_clean] = "Truecaller Official API"
        except Exception:
            pass

    # 2. Web OSINT Search Dorking (Facebook, LinkedIn, Google Snippets)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENTS[0], "Accept-Language": "en-US,en;q=0.9"})

    dork_queries = [
        f'"{e164}" site:facebook.com OR site:linkedin.com',
        f'"{national}" site:facebook.com OR site:linkedin.com OR site:truecaller.com',
        f'"{e164}" "name" OR "profile" OR "contact"'
    ]

    all_text = []

    for q in dork_queries:
        try:
            # DuckDuckGo HTML
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            res = session.get(ddg_url, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for body in soup.find_all('div', class_='result__body'):
                    all_text.append(body.get_text(separator=' '))
        except Exception:
            pass

        try:
            # Bing HTML
            bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}"
            res = session.get(bing_url, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for li in soup.find_all('li', class_='b_algo'):
                    all_text.append(li.get_text(separator=' '))
        except Exception:
            pass

    # Regex patterns for social profiles & display names
    name_patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:\||-|–|•|\(|\b)\s*(?:Facebook|LinkedIn|Twitter|Instagram|TikTok|Truecaller)',
        r'(?:Profile of|Contact|About|User|Name[:\s]+)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+-\s+Phone',
    ]

    for snippet in all_text:
        for pat in name_patterns:
            for match in re.finditer(pat, snippet):
                raw_m = match.group(1).strip()
                cleaned = clean_person_name(raw_m)
                if cleaned and cleaned not in extracted_names:
                    extracted_names.append(cleaned)
                    sources_map[cleaned] = "Social Web Dork"

    primary_name = extracted_names[0] if extracted_names else ""

    return {
        "primary_name": primary_name,
        "all_names": extracted_names,
        "sources": sources_map,
        "phone_e164": e164
    }


if __name__ == "__main__":
    res = harvest_social_names("01880829496")
    print("Harvested Social Names Result:", res)
