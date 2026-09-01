import smtplib
import socket
import dns.resolver
import requests

def test_smtp(email):
    domain = email.split('@')[1]
    print(f"Checking MX for domain: {domain}")
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        mx_host = str(answers[0].exchange).rstrip('.')
        print(f"MX Host: {mx_host}")
    except Exception as e:
        print(f"MX lookup failed: {e}")
        return

    try:
        smtp = smtplib.SMTP(mx_host, port=25, timeout=10)
        smtp.ehlo("gmail.com")
        smtp.mail("test@gmail.com")
        code, msg = smtp.rcpt(email)
        print(f"RCPT TO {email} -> Code: {code}, Message: {msg.decode('utf-8', errors='ignore')}")
        smtp.quit()
    except Exception as e:
        print(f"SMTP error for {email}: {e}")

test_smtp("maksudurrahamanmishu7@gmail.com")
test_smtp("thisemaildefinitelydoesnotexist987654321@gmail.com")
