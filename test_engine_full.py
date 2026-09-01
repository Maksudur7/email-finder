import re
import smtplib
import socket
import dns.resolver
from concurrent.futures import ThreadPoolExecutor, as_completed

def generate_dynamic_permutations(name: str, phone: str = "", domains: list = None) -> list:
    if domains is None:
        domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]

    clean_name = re.sub(r'[^a-zA-Z\s]', '', name.strip().lower())
    parts = clean_name.split()
    if not parts:
        return []

    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    middle_parts = parts[1:-1] if len(parts) > 2 else (parts[1:2] if len(parts) == 2 else [])

    # Base name patterns
    name_patterns = []
    
    # Full joined name (e.g., maksudurrahamanmishu)
    full_joined = "".join(parts)
    name_patterns.append(full_joined)

    # Standard dot / underscore patterns
    full_dotted = ".".join(parts)
    name_patterns.append(full_dotted)
    name_patterns.append("_".join(parts))
    name_patterns.append("-".join(parts))

    if len(parts) >= 2:
        # First + Last (maksudurmishu)
        name_patterns.append(f"{first}{last}")
        name_patterns.append(f"{first}.{last}")
        name_patterns.append(f"{first}_{last}")
        
        # First initial + Last (mmishu)
        name_patterns.append(f"{first[0]}{last}")
        name_patterns.append(f"{first[0]}.{last}")
        
        # First + Last initial (maksudurm)
        name_patterns.append(f"{first}{last[0]}")
        name_patterns.append(f"{first}.{last[0]}")

        # Reverse (mishumaksudur)
        name_patterns.append(f"{last}{first}")
        name_patterns.append(f"{last}.{first}")

    if len(parts) >= 3:
        # First + Middle (maksudurrahaman)
        mid_joined = "".join(middle_parts)
        name_patterns.append(f"{first}{mid_joined}")
        name_patterns.append(f"{mid_joined}{last}")
        name_patterns.append(f"{first[0]}{mid_joined[0]}{last}")

    # Numeric Suffixes
    suffixes = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
                "01", "02", "07", "08", "09", "10", "11", "12", "77", "88", "99", "123", "786"]

    # Extract phone digits if phone is provided
    if phone:
        clean_phone = re.sub(r'\D', '', phone)
        if len(clean_phone) >= 4:
            suffixes.append(clean_phone[-2:])   # e.g., 86
            suffixes.append(clean_phone[-3:])   # e.g., 086
            suffixes.append(clean_phone[-4:])   # e.g., 6086
            suffixes.append(clean_phone[:3])    # e.g., 013

    # Add years
    for y in range(1985, 2026):
        suffixes.append(str(y))
    for y in range(85, 100):
        suffixes.append(str(y))
    for y in range(0, 10):
        suffixes.append(f"0{y}")

    # Generate full emails
    candidates = []
    seen = set()

    for pattern in name_patterns:
        for suf in suffixes:
            base_handle = f"{pattern}{suf}"
            for d in domains:
                email = f"{base_handle}@{d}".lower()
                if email not in seen:
                    seen.add(email)
                    candidates.append(email)

    return candidates

def check_single_email_smtp(email: str, mx_cache: dict) -> dict:
    domain = email.split('@')[1]
    if domain not in mx_cache:
        try:
            answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
            mx_cache[domain] = str(answers[0].exchange).rstrip('.')
        except Exception:
            mx_cache[domain] = ""

    mx_host = mx_cache.get(domain)
    if not mx_host:
        return {"email": email, "valid": False, "code": 0, "msg": "No MX record"}

    try:
        smtp = smtplib.SMTP(mx_host, port=25, timeout=5)
        smtp.ehlo("gmail.com")
        smtp.mail("verify@gmail.com")
        code, msg = smtp.rcpt(email)
        smtp.quit()

        msg_str = msg.decode('utf-8', errors='ignore') if isinstance(msg, bytes) else str(msg)
        if code == 250:
            return {"email": email, "valid": True, "code": code, "msg": msg_str}
        elif code == 550:
            return {"email": email, "valid": False, "code": code, "msg": msg_str}
        else:
            return {"email": email, "valid": None, "code": code, "msg": msg_str}
    except Exception as e:
        return {"email": email, "valid": None, "code": 0, "msg": str(e)}

# TEST RUN
name = "maksudur rahaman mishu"
phone = "01315906086"
candidates = generate_dynamic_permutations(name, phone, ["gmail.com"])
target = "maksudurrahamanmishu7@gmail.com"

print(f"Total candidates generated: {len(candidates)}")
print(f"Is target in candidates? {target in candidates}")

# Fast Parallel SMTP Check
mx_cache = {}
verified_found = []

print("Running fast parallel SMTP check on candidates...")
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(check_single_email_smtp, cand, mx_cache) for cand in candidates]
    for fut in as_completed(futures):
        res = fut.result()
        if res["valid"] is True:
            print(f"✅ VERIFIED REAL EMAIL FOUND: {res['email']} ({res['msg']})")
            verified_found.append(res['email'])

print(f"\nTotal Verified Emails Found: {verified_found}")
