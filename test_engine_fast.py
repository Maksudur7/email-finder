import re
import smtplib
import dns.resolver
import time
import sys
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def generate_ranked_email_candidates(name: str, phone: str = "", domains: list = None) -> tuple:
    """
    Generates email permutations ranked by probability.
    Returns (high_priority_candidates, all_candidates)
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

    # 1. Full joined name (e.g. maksudurrahamanmishu) - VERY COMMON in BD/Global
    high_priority_base.append(full_joined)

    # 2. Dotted / Underscore full name
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

    if len(parts) >= 3:
        # First + Middle (maksudurrahaman)
        mid_joined = "".join(middle_parts)
        secondary_base.append(f"{first}{mid_joined}")
        secondary_base.append(f"{mid_joined}{last}")

    # Suffixes prioritized:
    # High Priority Suffixes: No suffix, single digits (0-9), common numbers (7, 07, 77, 99, 123, 786), phone suffixes
    high_priority_suffixes = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "01", "07", "77", "99", "123", "786"]

    if phone:
        clean_phone = re.sub(r'\D', '', phone)
        if len(clean_phone) >= 4:
            high_priority_suffixes.insert(1, clean_phone[-2:])   # e.g., 86
            high_priority_suffixes.insert(2, clean_phone[-3:])   # e.g., 086
            high_priority_suffixes.insert(3, clean_phone[-4:])   # e.g., 6086
            high_priority_suffixes.insert(4, clean_phone[:3])    # e.g., 013

    # Secondary Suffixes: Years (1985..2025, 85..99, 00..25), digits 10..99
    secondary_suffixes = [str(y) for y in range(1985, 2026)]
    secondary_suffixes.extend([str(y) for y in range(85, 100)])
    secondary_suffixes.extend([f"0{y}" for y in range(1, 10)])
    secondary_suffixes.extend([str(y) for y in range(10, 50)])

    high_candidates = []
    secondary_candidates = []
    seen = set()

    for d in domains:
        # 1. High priority base x High priority suffixes
        for base in high_priority_base:
            for suf in high_priority_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    high_candidates.append(em)

        # 2. High priority base x Secondary suffixes
        for base in high_priority_base:
            for suf in secondary_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    secondary_candidates.append(em)

        # 3. Secondary base x High priority suffixes
        for base in secondary_base:
            for suf in high_priority_suffixes:
                em = f"{base}{suf}@{d}".lower()
                if em not in seen:
                    seen.add(em)
                    secondary_candidates.append(em)

    return high_candidates, secondary_candidates

# Test run
name = "maksudur rahaman mishu"
phone = "01315906086"
high_cands, sec_cands = generate_ranked_email_candidates(name, phone, ["gmail.com"])
target = "maksudurrahamanmishu7@gmail.com"

print(f"High Priority Candidates Count: {len(high_cands)}")
print(f"Is target in High Priority candidates? {target in high_cands}")
if target in high_cands:
    print(f"Target index in High Priority: {high_cands.index(target)}")

# Test SMTP verification on High Priority Candidates
mx_cache = {}

def verify_smtp_single(email):
    domain = email.split('@')[1]
    if domain not in mx_cache:
        try:
            answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
            mx_cache[domain] = str(answers[0].exchange).rstrip('.')
        except Exception:
            mx_cache[domain] = ""

    mx_host = mx_cache.get(domain)
    if not mx_host:
        return {"email": email, "valid": False, "msg": "No MX"}

    try:
        smtp = smtplib.SMTP(mx_host, port=25, timeout=4)
        smtp.ehlo("gmail.com")
        smtp.mail("verify@gmail.com")
        code, msg = smtp.rcpt(email)
        smtp.quit()
        msg_str = msg.decode('utf-8', errors='ignore') if isinstance(msg, bytes) else str(msg)
        return {"email": email, "valid": (code == 250), "code": code, "msg": msg_str}
    except Exception as e:
        return {"email": email, "valid": None, "msg": str(e)}

print("\nRunning SMTP check on Top High Priority Candidates...")
start_t = time.time()
verified_emails = []

with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [executor.submit(verify_smtp_single, em) for em in high_cands[:50]]
    for fut in as_completed(futures):
        res = fut.result()
        if res["valid"] is True:
            print(f"🔥 VERIFIED REAL EMAIL FOUND: {res['email']} ({res['msg']})")
            verified_emails.append(res["email"])

print(f"\nCompleted in {round(time.time() - start_t, 2)}s. Verified emails: {verified_emails}")
