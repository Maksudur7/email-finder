import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import dns.resolver

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

EMAIL_BLACKLIST = {
    'example.com', 'domain.com', 'email.com', 'yourname@', 'name@', 'user@',
    'sentry.io', 'wixpress.com', 'schema.org', 'wordpress.org', 'bootstrap.com',
    'github.com', 'google.com', 'facebook.com', 'twitter.com', 'png@', 'jpg@',
    'support@', 'info@', 'admin@', 'sales@', 'privacy@', 'help@'
}

INVALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js')


def generate_email_candidates(name: str, domain_suffix: str = "gmail.com") -> list[str]:
    """
    Generates standard email permutations given a person's name.
    e.g. 'Maksudur Rahman' -> maksudur.rahman@gmail.com, maksudrahman@gmail.com
    """
    clean_name = re.sub(r'[^a-zA-Z\s]', '', name.strip().lower())
    parts = clean_name.split()
    
    if not parts:
        return []
        
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    
    candidates = []
    
    if first and last:
        candidates.extend([
            f"{first}.{last}@{domain_suffix}",
            f"{first}{last}@{domain_suffix}",
            f"{first[0]}{last}@{domain_suffix}",
            f"{first}.{last[0]}@{domain_suffix}",
            f"{last}.{first}@{domain_suffix}",
            f"{last}{first}@{domain_suffix}",
            f"{first}_{last}@{domain_suffix}"
        ])
    elif first:
        candidates.append(f"{first}@{domain_suffix}")
        
    return list(dict.fromkeys(candidates))


def verify_mx_record(domain: str) -> bool:
    """
    Verifies if a domain has valid MX mail server records.
    """
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except Exception:
        return False


def extract_emails_from_text(text: str) -> list[str]:
    """
    Extracts valid email addresses from web text.
    """
    if not text:
        return []
        
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(pattern, text)
    
    clean = []
    seen = set()
    for e in found:
        e_lower = e.lower().strip()
        if e_lower.endswith(INVALID_EXTENSIONS):
            continue
        if any(b in e_lower for b in EMAIL_BLACKLIST):
            continue
        if e_lower not in seen:
            seen.add(e_lower)
            clean.append(e_lower)
            
    return clean


def extract_names_from_text(text: str) -> list[str]:
    """
    Extracts potential names near phone/email listings.
    """
    names = []
    seen = set()
    patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*(?:\||-|–|•|\()\s*(?:Facebook|LinkedIn|Twitter|Instagram|GitHub|Contact|About)',
        r'(?:Profile of|Contact|Name:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
    ]
    generic = {'Facebook', 'LinkedIn', 'Twitter', 'Instagram', 'Contact', 'About', 'Home', 'Profile', 'Search', 'Google'}
    
    for pat in patterns:
        matches = re.findall(pat, text)
        for m in matches:
            m_str = m.strip() if isinstance(m, str) else m[0].strip()
            words = m_str.split()
            if 2 <= len(words) <= 4 and not any(w in generic for w in words):
                if m_str.lower() not in seen:
                    seen.add(m_str.lower())
                    names.append(m_str)
                    
    return names


def universal_search_finder(name: str = "", phone: str = "", domain: str = "gmail.com") -> dict:
    """
    Native Python Universal Email & Name Finder.
    Works by searching Name, Phone Number, or BOTH (Name + Phone).
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENTS[0]})
    
    snippets = []
    found_emails = []
    found_names = []
    
    clean_name = name.strip()
    clean_phone = phone.strip()
    
    queries = []
    
    # 1. Build Targeted Search Dorks
    if clean_name and clean_phone:
        queries = [
            f'"{clean_name}" "{clean_phone}" email OR contact OR @gmail.com',
            f'"{clean_name}" "{clean_phone}" site:facebook.com OR site:linkedin.com OR site:github.com',
            f'"{clean_phone}" "{clean_name}" @{domain}'
        ]
    elif clean_phone:
        queries = [
            f'"{clean_phone}" email OR contact OR @gmail.com OR @yahoo.com',
            f'"{clean_phone}" site:facebook.com OR site:linkedin.com OR site:github.com'
        ]
    elif clean_name:
        queries = [
            f'"{clean_name}" email OR contact OR @{domain}',
            f'"{clean_name}" site:facebook.com OR site:linkedin.com OR site:github.com'
        ]

    # 2. Execute Web Dorking via DuckDuckGo & Bing
    for q in queries:
        try:
            # DDG Search
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            res = session.get(ddg_url, timeout=7)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for body in soup.find_all('div', class_='result__body'):
                    text = body.get_text()
                    snippets.append(text)
        except Exception:
            pass
            
        try:
            # Bing Search
            bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}"
            res = session.get(bing_url, timeout=7)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for li in soup.find_all('li', class_='b_algo'):
                    snippets.append(li.get_text())
        except Exception:
            pass

    # 3. Extract Emails & Names from snippets
    for snip in snippets:
        em_list = extract_emails_from_text(snip)
        for e in em_list:
            if e not in found_emails:
                found_emails.append(e)
                
        nm_list = extract_names_from_text(snip)
        for nm in nm_list:
            if nm not in found_names:
                found_names.append(nm)

    # 4. Generate Name Permutations as fallback if name provided
    perm_candidates = []
    if clean_name and not found_emails:
        perm_candidates = generate_email_candidates(clean_name, domain)
        
    primary_email = found_emails[0] if found_emails else (perm_candidates[0] if perm_candidates else "Not Found")
    primary_name = clean_name if clean_name else (found_names[0] if found_names else "Not Found")

    return {
        "search_input": f"Name: '{clean_name}' | Phone: '{clean_phone}'",
        "primary_name": primary_name,
        "primary_email": primary_email,
        "found_emails": found_emails,
        "permutation_candidates": perm_candidates,
        "found_names": found_names,
        "total_emails": len(found_emails),
        "source": "Native Python OSINT & Dorking Engine"
    }
