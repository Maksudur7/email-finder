import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier
from concurrent.futures import ThreadPoolExecutor, as_completed
from truecaller_engine import search_truecaller, load_installation_id

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

EMAIL_BLACKLIST = {
    'example.com', 'domain.com', 'email.com', 'yourname@', 'name@', 'user@',
    'sentry.io', 'wixpress.com', 'schema.org', 'wordpress.org', 'bootstrap.com',
    'github.com', 'google.com', 'facebook.com', 'twitter.com', 'png@', 'jpg@',
    'support@', 'info@', 'admin@', 'sales@'
}

INVALID_EMAIL_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js')


def parse_and_format_phone(raw_phone: str, default_country_code: str = "BD"):
    """
    Parses and formats phone number into standard E164, National, and International formats.
    """
    raw_phone = str(raw_phone).strip()
    try:
        if not raw_phone.startswith('+') and not raw_phone.startswith('00'):
            if default_country_code.upper() == "BD" and raw_phone.startswith('01'):
                parsed_num = phonenumbers.parse(raw_phone, "BD")
            else:
                parsed_num = phonenumbers.parse(raw_phone, default_country_code.upper())
        else:
            parsed_num = phonenumbers.parse(raw_phone)

        if not phonenumbers.is_valid_number(parsed_num):
            clean_digits = re.sub(r'\D', '', raw_phone)
            return {
                "valid": True,
                "e164": f"+{clean_digits}",
                "national": raw_phone,
                "international": f"+{clean_digits}",
                "country": "Unknown",
                "carrier": "Unknown",
                "country_code": default_country_code.upper(),
                "raw": raw_phone
            }

        e164 = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
        national = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL)
        international = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        country_name = geocoder.description_for_number(parsed_num, "en") or "Unknown"
        carrier_name = carrier.name_for_number(parsed_num, "en") or "Unknown"
        region_code = phonenumbers.region_code_for_number(parsed_num) or default_country_code.upper()

        return {
            "valid": True,
            "e164": e164,
            "national": national,
            "international": international,
            "country": country_name,
            "carrier": carrier_name,
            "country_code": region_code,
            "raw": raw_phone
        }
    except Exception:
        clean_digits = re.sub(r'\D', '', raw_phone)
        return {
            "valid": bool(clean_digits),
            "e164": clean_digits,
            "national": raw_phone,
            "international": raw_phone,
            "country": "Unknown",
            "carrier": "Unknown",
            "country_code": default_country_code.upper(),
            "raw": raw_phone
        }


def extract_emails_from_text(text: str) -> list[str]:
    """
    Extracts valid email addresses from text using Regex.
    """
    if not text:
        return []
    
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found_emails = re.findall(pattern, text)
    
    clean_emails = []
    seen = set()
    for email in found_emails:
        email_lower = email.lower().strip()
        if email_lower.endswith(INVALID_EMAIL_EXTENSIONS):
            continue
        if any(black in email_lower for black in EMAIL_BLACKLIST):
            continue
        if email_lower not in seen:
            seen.add(email_lower)
            clean_emails.append(email_lower)
            
    return clean_emails


def extract_names_from_snippets(snippets: list[str]) -> list[str]:
    """
    Extracts potential owner names from web search snippets and social media profiles.
    """
    names = []
    seen = set()
    
    social_patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*(?:\||-|–|•|\(|\b)\s*(?:Facebook|LinkedIn|Twitter|Instagram|TikTok|Truecaller|WhatsApp)',
        r'(?:Profile of|Contact|About|User)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+-\s+Phone'
    ]
    
    generic_words = {'Facebook', 'LinkedIn', 'Twitter', 'Instagram', 'WhatsApp', 'Contact', 'About', 'Home', 'Profile', 'Search', 'Google', 'Phone', 'Number', 'Directory', 'Truecaller'}

    for text in snippets:
        for pattern in social_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                m_str = m.strip() if isinstance(m, str) else m[0].strip()
                words = m_str.split()
                if 2 <= len(words) <= 4 and not any(w in generic_words for w in words):
                    if m_str.lower() not in seen:
                        seen.add(m_str.lower())
                        names.append(m_str)

    return names


def search_duckduckgo(query: str, session: requests.Session) -> tuple[list[str], list[str]]:
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": USER_AGENTS[0], "Accept-Language": "en-US,en;q=0.9"}
    snippets, links = [], []
    try:
        res = session.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for result in soup.find_all('div', class_='result__body'):
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')
                title = title_elem.get_text() if title_elem else ""
                snippet = snippet_elem.get_text() if snippet_elem else ""
                snippets.append(f"{title} - {snippet}")
                if title_elem and title_elem.get('href'):
                    raw_href = title_elem['href']
                    if 'uddg=' in raw_href:
                        parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query).get('uddg', [])
                        if parsed_url:
                            links.append(parsed_url[0])
                    else:
                        links.append(raw_href)
    except Exception:
        pass
    return snippets, links


def search_bing(query: str, session: requests.Session) -> tuple[list[str], list[str]]:
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": USER_AGENTS[1], "Accept-Language": "en-US,en;q=0.9"}
    snippets, links = [], []
    try:
        res = session.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for li in soup.find_all('li', class_='b_algo'):
                h2 = li.find('h2')
                p = li.find('p')
                title = h2.get_text() if h2 else ""
                snippet = p.get_text() if p else ""
                snippets.append(f"{title} - {snippet}")
                a_tag = h2.find('a') if h2 else None
                if a_tag and a_tag.get('href'):
                    links.append(a_tag['href'])
    except Exception:
        pass
    return snippets, links


def lookup_phone_number(raw_phone: str, default_country: str = "BD", deep_crawl: bool = True, use_truecaller: bool = True) -> dict:
    """
    High-Precision Hybrid Phone Number -> Name & Email Finder Engine.
    Combines Truecaller Official Database API + Web OSINT Social Dorking.
    """
    phone_info = parse_and_format_phone(raw_phone, default_country)
    country_code = phone_info['country_code']
    
    primary_name = "Not Found"
    primary_email = "Not Found"
    all_emails = []
    all_names = []
    source_used = "Web OSINT"
    
    # ---------------------------------------------------------
    # STEP 1: Truecaller Official Database Lookup (Highest Accuracy)
    # ---------------------------------------------------------
    tc_token = load_installation_id()
    if use_truecaller and tc_token:
        tc_res = search_truecaller(phone_info['e164'], country_code=country_code, installation_id=tc_token)
        if tc_res.get("success"):
            if tc_res.get("name") and tc_res["name"] != "Not Found":
                primary_name = tc_res["name"]
                all_names.append(primary_name)
            if tc_res.get("emails"):
                all_emails.extend(tc_res["emails"])
                primary_email = tc_res["emails"][0]
            if tc_res.get("carrier") and tc_res["carrier"] != "Unknown":
                phone_info['carrier'] = tc_res["carrier"]
            source_used = "Truecaller Official API"

    # ---------------------------------------------------------
    # STEP 2: Web OSINT Dorking & Social Profile Extraction (Fallback/Enrichment)
    # ---------------------------------------------------------
    session = requests.Session()
    queries = [
        f'"{phone_info["e164"]}" email OR contact OR @gmail.com OR @yahoo.com',
        f'"{phone_info["national"].replace(" ", "").replace("-", "")}" site:facebook.com OR site:linkedin.com',
        f'"{phone_info["e164"]}" site:facebook.com OR site:linkedin.com OR site:truecaller.com'
    ]
    
    all_snippets = []
    links_to_crawl = []
    
    for q in queries:
        ddg_snippets, ddg_links = search_duckduckgo(q, session)
        bing_snippets, bing_links = search_bing(q, session)
        all_snippets.extend(ddg_snippets)
        all_snippets.extend(bing_snippets)
        links_to_crawl.extend(ddg_links[:2])
        links_to_crawl.extend(bing_links[:2])

    # Extract emails from snippets
    for snip in all_snippets:
        emails = extract_emails_from_text(snip)
        for e in emails:
            if e not in all_emails:
                all_emails.append(e)

    # Extract names from snippets if Truecaller didn't return a name
    if primary_name == "Not Found":
        extracted_names = extract_names_from_snippets(all_snippets)
        for nm in extracted_names:
            if nm not in all_names:
                all_names.append(nm)
        if all_names:
            primary_name = all_names[0]

    # Deep crawl top web links if email still not found
    if deep_crawl and links_to_crawl and primary_email == "Not Found":
        for link in list(dict.fromkeys(links_to_crawl))[:3]:
            try:
                res = session.get(link, headers={"User-Agent": USER_AGENTS[2]}, timeout=5)
                if res.status_code == 200:
                    page_emails = extract_emails_from_text(res.text)
                    for pe in page_emails:
                        if pe not in all_emails:
                            all_emails.append(pe)
            except Exception:
                pass

    if primary_email == "Not Found" and all_emails:
        primary_email = all_emails[0]

    return {
        "phone_number": phone_info['e164'],
        "national_format": phone_info['national'],
        "country": phone_info['country'],
        "carrier": phone_info['carrier'],
        "owner_name": primary_name,
        "email": primary_email,
        "all_names": all_names,
        "all_emails": all_emails,
        "total_emails_found": len(all_emails),
        "source": source_used,
        "tc_token_active": bool(tc_token)
    }


def batch_lookup_numbers(phone_list: list[str], default_country: str = "BD", max_workers: int = 5, callback=None) -> list[dict]:
    """
    Performs concurrent high-precision OSINT lookup on a list of phone numbers.
    """
    results = []
    total = len(phone_list)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_phone = {
            executor.submit(lookup_phone_number, phone, default_country, True, True): phone 
            for phone in phone_list if str(phone).strip()
        }
        
        completed_count = 0
        for future in as_completed(future_to_phone):
            completed_count += 1
            try:
                data = future.result()
                results.append(data)
            except Exception:
                phone = future_to_phone[future]
                results.append({
                    "phone_number": str(phone),
                    "national_format": str(phone),
                    "country": "Unknown",
                    "carrier": "Unknown",
                    "owner_name": "Error",
                    "email": "Error",
                    "all_names": [],
                    "all_emails": [],
                    "total_emails_found": 0,
                    "source": "Error",
                    "tc_token_active": False
                })
            
            if callback:
                callback(completed_count, total)
                
    return results
