import asyncio
from playwright.async_api import async_playwright
import re

async def scrape_truecaller_web(phone_number: str, country_code: str = "bd"):
    """
    Automated Playwright Web Scraper for Truecaller Web.
    """
    clean_num = re.sub(r'\D', '', phone_number)
    if clean_num.startswith('880'):
        clean_num = clean_num[3:]
    if not clean_num.startswith('0') and country_code == 'bd':
        clean_num = '0' + clean_num

    search_url = f"https://www.truecaller.com/search/{country_code}/{clean_num}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        try:
            print(f"Navigating to {search_url} ...")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            content = await page.content()
            
            # Extract name and email from page DOM
            name = "Not Found"
            email = "Not Found"
            
            # Check for header/h1/h2 title
            h1_elem = await page.query_selector('h1')
            if h1_elem:
                name_text = await h1_elem.inner_text()
                if name_text and "Search" not in name_text and "Truecaller" not in name_text:
                    name = name_text.strip()
                    
            # Extract emails via regex
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails_found = re.findall(email_pattern, content)
            clean_emails = [e.lower() for e in emails_found if not any(b in e.lower() for b in ['sentry', 'wix', 'schema', 'example', 'png', 'jpg'])]
            
            if clean_emails:
                email = clean_emails[0]
                
            await browser.close()
            return {
                "success": True,
                "phone": phone_number,
                "name": name,
                "email": email,
                "all_emails": list(set(clean_emails))
            }
        except Exception as e:
            await browser.close()
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    res = asyncio.run(scrape_truecaller_web("01712345678", "bd"))
    print("Scrape Result:", res)
