"""
Email Engine — High-Precision Dynamic Email & Name Finder
Powered by Dynamic Permutation Matrix, Parallel SMTP Mailbox Verification, and Web OSINT Dorking.
"""

import re
import socket
import smtplib
import urllib.parse
import random
import time
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier
import dns.resolver
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── User Agents ───────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

# ─── Junk Filters ──────────────────────────────────────────────────────────────
EMAIL_BLACKLIST_DOMAINS = {
    'example.com', 'domain.com', 'email.com', 'sentry.io', 'wixpress.com',
    'schema.org', 'wordpress.org', 'github.com', 'google.com', 'facebook.com',
    'twitter.com', 'w3.org', 'w3schools.com', 'mozilla.org', 'apple.com',
    'microsoft.com', 'cloudflare.com', 'duckduckgo.com',
}

EMAIL_BLACKLIST_PREFIXES = {
    'support', 'info', 'admin', 'sales', 'privacy', 'help', 'noreply',
    'no-reply', 'contact', 'webmaster', 'postmaster', 'abuse', 'error-lite',
}

INVALID_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.ico')


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PHONE NUMBER PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_phone(raw_phone: str, default_country: str = "BD") -> dict:
    """Parse phone number into E.164, national format, carrier, region, and search variants."""
    raw_phone = str(raw_phone).strip()
    if not raw_phone:
        return {}

    try:
        if not raw_phone.startswith('+') and not raw_phone.startswith('00'):
            parsed = phonenumbers.parse(raw_phone, default_country.upper())
        else:
            parsed = phonenumbers.parse(raw_phone)

        valid = phonenumbers.is_valid_number(parsed)
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        country_name = geocoder.description_for_number(parsed, "en") or "Unknown"
        carrier_name = carrier.name_for_number(parsed, "en") or "Unknown"
        region = phonenumbers.region_code_for_number(parsed) or default_country.upper()

        digits_only = re.sub(r'\D', '', raw_phone)
        variants = list(dict.fromkeys([
            e164,
            national.replace(' ', '').replace('-', ''),
            digits_only,
            intl
        ]))

        return {
            "valid": valid, "e164": e164, "national": national,
            "international": intl, "country": country_name,
            "carrier": carrier_name, "region": region, "variants": variants, "raw": raw_phone
        }
    except Exception:
        digits_only = re.sub(r'\D', '', raw_phone)
        return {
            "valid": bool(digits_only), "e164": f"+{digits_only}", "national": raw_phone,
            "international": raw_phone, "country": "Unknown", "carrier": "Unknown",
            "region": default_country.upper(), "variants": [raw_phone, digits_only], "raw": raw_phone
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DYNAMIC RANKED PERMUTATION MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

def generate_ranked_email_candidates(name: str, phone: str = "", domains: list = None) -> tuple:
    """
    Generates dynamic email permutations prioritized by real-world usage patterns.
    Returns (high_priority_candidates, secondary_candidates)
    """
    if domains is None:
        domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]

    clean_name = re.sub(r'[^a-zA-Z\s]', '', name.strip().lower())
    parts = clean_name.split()
    if not parts:
        return [], []

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    middle_parts = parts[1:-1] if len(parts) > 2 else (parts[1:2] if len(parts) == 2 else [])
    full_joined = "".join(parts)

    high_priority_base = []
    secondary_base = []

    # 1. Full joined name (e.g. maksudurrahamanmishu) - Highest priority in BD/Asia
    high_priority_base.append(full_joined)

    # 2. Dotted & Underscore full name
    high_priority_base.append(".".join(parts))
    high_priority_base.append("_".join(parts))

    if len(parts) >= 2:
        # First + Last (maksudurmishu)
        high_priority_base.append(f"{first}{last}")
        high_priority_base.append(f"{first}.{last}")
        high_priority_base.append(f"{first}_{last}")

        # First initial + Last (mmishu)
        secondary_base.append(f"{first[0]}{last}")
        secondary_base.append(f"{first[0]}.{last}")

        # First + Last initial (maksudurm)
        secondary_base.append(f"{first}{last[0]}")
        secondary_base.append(f"{first}.{last[0]}")

        # Reversed (mishumaksudur)
        secondary_base.append(f"{last}{first}")
        secondary_base.append(f"{last}.{first}")

    if len(parts) >= 3:
        mid_joined = "".join(middle_parts)
        secondary_base.append(f"{first}{mid_joined}")
        secondary_base.append(f"{mid_joined}{last}")
        secondary_base.append(f"{first[0]}{mid_joined[0]}{last}")

    # Suffix Matrix:
    # High Priority Suffixes: No suffix, single digits 0-9, common numbers (7, 07, 77, 99, 123, 786), phone suffixes
    high_priority_suffixes = [
        "", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "01", "07", "77", "88", "99", "123", "786"
    ]

    # Add phone suffixes if phone is provided
    if phone:
        clean_phone = re.sub(r'\D', '', phone)
        if len(clean_phone) >= 4:
            high_priority_suffixes.insert(1, clean_phone[-2:])   # e.g. 86
            high_priority_suffixes.insert(2, clean_phone[-3:])   # e.g. 086
            high_priority_suffixes.insert(3, clean_phone[-4:])   # e.g. 6086
            high_priority_suffixes.insert(4, clean_phone[:3])    # e.g. 013

    # Secondary Suffixes: Years (1985..2026, 85..99, 00..25), digits 10..50
    secondary_suffixes = [str(y) for y in range(1985, 2026)]
    secondary_suffixes.extend([str(y) for y in range(85, 100)])
    secondary_suffixes.extend([f"0{y}" for y in range(1, 10)])
    secondary_suffixes.extend([str(y) for y in range(10, 50)])

    high_candidates = []
    secondary_candidates = []
    seen = set()

    for d in domains:
        # High base x High suffixes
        for base in high_priority_base:
            for suf in high_priority_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    high_candidates.append(em)

        # High base x Secondary suffixes
        for base in high_priority_base:
            for suf in secondary_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    secondary_candidates.append(em)

        # Secondary base x High suffixes
        for base in secondary_base:
            for suf in high_priority_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    secondary_candidates.append(em)

    return high_candidates, secondary_candidates


def generate_email_permutations(name: str, domains: list = None) -> list:
    """Helper wrapper for backward compatibility with app.py."""
    high, sec = generate_ranked_email_candidates(name=name, domains=domains)
    return high + sec


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SMTP MAILBOX VERIFICATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

# Domain MX Cache
DOMAIN_MX_CACHE = {
    "gmail.com": "gmail-smtp-in.l.google.com",
    "yahoo.com": "mta7.am0.yahoodns.net",
    "outlook.com": "outlook-com.olc.protection.outlook.com",
    "hotmail.com": "hotmail-com.olc.protection.outlook.com",
}


def get_mx_record(domain: str) -> str:
    """Retrieve MX mail server hostname for a domain."""
    if domain in DOMAIN_MX_CACHE:
        return DOMAIN_MX_CACHE[domain]
    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=4)
        if answers:
            mx = str(sorted(answers, key=lambda r: r.preference)[0].exchange).rstrip('.')
            DOMAIN_MX_CACHE[domain] = mx
            return mx
    except Exception:
        pass
    return ""


def verify_email_smtp(email: str, timeout: int = 5, mx_cache: dict = None) -> dict:
    """
    Performs direct SMTP RCPT TO mailbox check against mail server.
    Returns {"email": str, "valid": bool/None, "code": int, "reason": str}
    - valid = True  --> Mailbox EXISTS (250 OK)
    - valid = False --> Mailbox DOES NOT EXIST (550)
    - valid = None  --> Uncertain (Blocked / Timeout)
    """
    email = email.strip().lower()
    parts = email.split('@')
    if len(parts) != 2:
        return {"email": email, "valid": False, "code": 0, "reason": "Invalid email syntax"}

    domain = parts[1]
    if mx_cache is not None and domain in mx_cache:
        mx_host = mx_cache[domain]
    else:
        mx_host = get_mx_record(domain)
        if mx_cache is not None:
            mx_cache[domain] = mx_host

    if not mx_host:
        return {"email": email, "valid": False, "code": 0, "reason": "No MX record found"}

    try:
        smtp = smtplib.SMTP(mx_host, port=25, timeout=timeout)
        smtp.ehlo("gmail.com")
        smtp.mail("verify@gmail.com")
        code, msg = smtp.rcpt(email)
        smtp.quit()

        msg_str = msg.decode('utf-8', errors='ignore') if isinstance(msg, bytes) else str(msg)
        if code == 250:
            return {"email": email, "valid": True, "code": code, "reason": f"SMTP 250 OK - Mailbox Verified"}
        elif code == 550:
            return {"email": email, "valid": False, "code": code, "reason": f"SMTP 550 - Mailbox does not exist"}
        else:
            return {"email": email, "valid": None, "code": code, "reason": f"SMTP {code} - {msg_str[:60]}"}
    except smtplib.SMTPConnectError:
        return {"email": email, "valid": None, "code": 0, "reason": "Port 25 blocked by network"}
    except socket.timeout:
        return {"email": email, "valid": None, "code": 0, "reason": "SMTP Timeout"}
    except Exception as e:
        return {"email": email, "valid": None, "code": 0, "reason": f"SMTP Exception: {str(e)[:60]}"}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. WEB OSINT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def extract_emails_from_text(text: str, target_domains: list = None) -> list:
    """Extract valid emails from web snippet text."""
    if not text:
        return []

    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    found = re.findall(pattern, text)

    clean = []
    seen = set()
    for e_raw in found:
        e = e_raw.lower().strip().rstrip('.')
        if any(e.endswith(ext) for ext in INVALID_EXTENSIONS):
            continue
        parts = e.split('@')
        if len(parts) != 2:
            continue
        prefix, domain = parts[0], parts[1]

        if domain in EMAIL_BLACKLIST_DOMAINS or prefix in EMAIL_BLACKLIST_PREFIXES:
            continue
        if len(domain.split('.')) < 2:
            continue

        if target_domains:
            if not any(domain == td or domain.endswith('.' + td) for td in target_domains):
                continue

        if e not in seen:
            seen.add(e)
            clean.append(e)

    return clean


def extract_names_from_text(text: str) -> list:
    """Extract person names from search result snippets."""
    names = []
    seen = set()

    GENERIC = {
        'Facebook', 'LinkedIn', 'Twitter', 'Instagram', 'TikTok', 'WhatsApp',
        'Contact', 'About', 'Home', 'Profile', 'Search', 'Google', 'Phone',
        'Number', 'Directory', 'Truecaller', 'Mobile', 'Bangladesh', 'Dhaka',
        'Call', 'More', 'See', 'View', 'Download', 'Page', 'Post', 'Share',
    }

    patterns = [
        r'([A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+){1,3})\s*[\||\-|–|•]\s*(?:Facebook|LinkedIn|Twitter|Instagram)',
        r'(?:Profile of|Contact|About|User|Name[:\s]+)\s*([A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+){1,3})',
        r'([A-Z][a-zÀ-ÿ]+\s+[A-Z][a-zÀ-ÿ]+)\s*-\s*Phone',
    ]

    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            m = match.group(1).strip()
            words = m.split()
            if 2 <= len(words) <= 4 and not any(w in GENERIC for w in words):
                if m.lower() not in seen:
                    seen.add(m.lower())
                    names.append(m)
    return names


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def search_duckduckgo(query: str, session: requests.Session) -> list:
    """Query DuckDuckGo for search result snippets."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    snippets = []
    try:
        res = session.get(url, timeout=7)
        if res.status_code == 200 and "error-lite" not in res.text:
            soup = BeautifulSoup(res.text, 'html.parser')
            for body in soup.find_all('div', class_='result__body'):
                t = body.get_text(separator=' ')
                if t:
                    snippets.append(t)
    except Exception:
        pass
    return snippets


def search_bing(query: str, session: requests.Session) -> list:
    """Query Bing for search result snippets."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=10"
    snippets = []
    try:
        res = session.get(url, timeout=7)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for li in soup.find_all('li', class_='b_algo'):
                t = li.get_text(separator=' ')
                if t:
                    snippets.append(t)
    except Exception:
        pass
    return snippets


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MASTER EMAIL FINDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def find_email_from_phone_and_name(
    phone: str = "",
    name: str = "",
    target_domains: list = None,
    do_smtp_verify: bool = True,
    max_smtp_checks: int = 60,
    progress_callback=None
) -> dict:
    """
    Master Email Finder: Takes Phone and/or Name, performs dynamic matrix permutation,
    web OSINT search, and parallel SMTP verification. Returns ranked results with 100% verified emails first.
    """
    if target_domains is None:
        target_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]

    def log(step, detail=""):
        if progress_callback:
            progress_callback(step, detail)

    session = _get_session()
    phone_info = {}
    directly_found_emails = []
    scraped_names = []

    phone = phone.strip()
    name = name.strip()

    # Phase 1: Phone Processing & OSINT Dorking
    if phone:
        log("🔍 Phase 1", "Parsing phone number metadata...")
        phone_info = parse_phone(phone)
        phone_variants = phone_info.get("variants", [phone])

        log("🌐 Phase 1", f"Performing Web OSINT dorking for phone: {phone_info.get('e164', phone)}")
        all_snippets = []

        for variant in phone_variants[:3]:
            # Dork variant + email domains
            for d in target_domains[:2]:
                q = f'"{variant}" @{d}'
                all_snippets.extend(search_duckduckgo(q, session))
                all_snippets.extend(search_bing(q, session))

            # Dork variant + social sites
            q_soc = f'"{variant}" site:facebook.com OR site:linkedin.com OR site:github.com'
            all_snippets.extend(search_duckduckgo(q_soc, session))
            all_snippets.extend(search_bing(q_soc, session))

        # Extract emails & names from snippets
        for snip in all_snippets:
            for e in extract_emails_from_text(snip, target_domains):
                if e not in directly_found_emails:
                    directly_found_emails.append(e)

            if not name:
                for nm in extract_names_from_text(snip):
                    if nm not in scraped_names:
                        scraped_names.append(nm)

    resolved_name = name or (scraped_names[0] if scraped_names else "")

    # Phase 2: Dynamic Matrix Permutation Generation
    log("🔮 Phase 2", f"Generating dynamic ranked permutations for: '{resolved_name or 'N/A'}'")
    high_candidates, secondary_candidates = [], []
    if resolved_name:
        high_candidates, secondary_candidates = generate_ranked_email_candidates(
            name=resolved_name,
            phone=phone,
            domains=target_domains
        )

    log("🔮 Phase 2", f"Generated {len(high_candidates)} High-Priority candidates and {len(secondary_candidates)} Secondary candidates")

    # Combine candidates to verify:
    # 1. Directly found emails from web OSINT (top priority)
    # 2. High priority permutation candidates
    # 3. Secondary permutation candidates
    candidates_to_check = []
    seen = set()

    for e in directly_found_emails:
        if e not in seen:
            seen.add(e)
            candidates_to_check.append(e)

    for e in high_candidates:
        if e not in seen:
            seen.add(e)
            candidates_to_check.append(e)

    for e in secondary_candidates:
        if e not in seen:
            seen.add(e)
            candidates_to_check.append(e)

    # Phase 3: Parallel SMTP Verification
    smtp_verified = []     # Code 250 (Mailbox Verified Real)
    smtp_uncertain = []    # Temporary limit / Port blocked
    smtp_invalid = []      # Code 550 (Mailbox does not exist)

    if do_smtp_verify and candidates_to_check:
        to_verify = candidates_to_check[:max_smtp_checks]
        log("✅ Phase 3", f"Running parallel SMTP check on top {len(to_verify)} candidate emails...")

        mx_cache = {}
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_email = {executor.submit(verify_email_smtp, em, 5, mx_cache): em for em in to_verify}

            checked_count = 0
            for fut in as_completed(future_to_email):
                checked_count += 1
                res = fut.result()
                if res["valid"] is True:
                    log("🔥 Match!", f"SMTP Verified REAL Email: {res['email']}")
                    smtp_verified.append(res)
                elif res["valid"] is False:
                    smtp_invalid.append(res)
                else:
                    smtp_uncertain.append(res)

        log("✅ Phase 3", f"SMTP Verification finished. Found {len(smtp_verified)} 100% verified real emails.")

    # Sort final ranked emails:
    # 1. SMTP Verified emails (highest confidence)
    # 2. Directly found emails from web
    # 3. Uncertain SMTP emails
    # 4. High priority candidates
    ranked_final = []
    seen_final = set()

    for item in smtp_verified:
        e = item["email"]
        if e not in seen_final:
            seen_final.add(e)
            ranked_final.append(e)

    for e in directly_found_emails:
        if e not in seen_final:
            seen_final.add(e)
            ranked_final.append(e)

    for item in smtp_uncertain:
        e = item["email"]
        if e not in seen_final:
            seen_final.add(e)
            ranked_final.append(e)

    for e in high_candidates:
        if e not in seen_final:
            seen_final.add(e)
            ranked_final.append(e)

    primary_email = ranked_final[0] if ranked_final else "Not Found"

    return {
        "phone_info": phone_info,
        "resolved_name": resolved_name,
        "scraped_names": scraped_names,
        "primary_email": primary_email,
        "smtp_verified": smtp_verified,
        "smtp_uncertain": smtp_uncertain,
        "smtp_invalid": smtp_invalid,
        "directly_found_emails": directly_found_emails,
        "high_priority_candidates": high_candidates,
        "all_emails_ranked": ranked_final,
        "total_high_candidates": len(high_candidates),
        "total_verified": len(smtp_verified),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 6. BULK FINDER
# ═══════════════════════════════════════════════════════════════════════════════

def bulk_find_emails(
    phone_list: list,
    name_list: list = None,
    target_domains: list = None,
    do_smtp_verify: bool = True,
    callback=None
) -> list:
    """Runs email finder sequentially for multiple entries."""
    if name_list is None:
        name_list = [""] * len(phone_list)

    while len(name_list) < len(phone_list):
        name_list.append("")

    results = []
    total = len(phone_list)

    for i in range(total):
        phone = str(phone_list[i]).strip()
        name = str(name_list[i]).strip() if i < len(name_list) else ""

        try:
            res = find_email_from_phone_and_name(
                phone=phone,
                name=name,
                target_domains=target_domains,
                do_smtp_verify=do_smtp_verify
            )
            res["input_phone"] = phone
            res["input_name"] = name
            res["index"] = i
            results.append(res)
        except Exception as e:
            results.append({
                "input_phone": phone,
                "input_name": name,
                "index": i,
                "primary_email": "Error",
                "smtp_verified": [],
                "all_emails_ranked": [],
                "error": str(e)
            })

        if callback:
            callback(i + 1, total)

        time.sleep(0.3)

    return results
