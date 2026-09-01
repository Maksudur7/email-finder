"""
Google Account Recovery Automator ('Find Your Email')
Automates the Google Account Recovery flow via Playwright to verify if a First & Last Name match a registered phone number on Google.
"""

import asyncio
import re
from playwright.async_api import async_playwright

async def verify_google_account_name(phone_number: str, first_name: str, last_name: str) -> dict:
    """
    Automates https://accounts.google.com/signin/v2/usernamerecovery
    Inputs phone number and first/last name to check if Google recognizes the account.
    Returns:
      {
        "success": True/False,
        "matched": True/False,
        "phone": phone_number,
        "first_name": first_name,
        "last_name": last_name,
        "details": "..."
      }
    """
    clean_phone = re.sub(r'[^\d+]', '', phone_number)
    if not clean_phone:
        return {"success": False, "matched": False, "error": "Invalid phone number"}

    recovery_url = "https://accounts.google.com/signin/v2/usernamerecovery?hl=en"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        try:
            # 1. Navigate to Google Username Recovery
            await page.goto(recovery_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            # 2. Input Phone Number
            phone_input = await page.query_selector('input[type="email"], input[name="emailOrPhone"], input[id="fols-phone-or-email-input"], #identifierId, input[type="text"]')
            if not phone_input:
                await browser.close()
                return {"success": False, "matched": False, "error": "Phone input field not found on Google page"}

            await phone_input.fill(clean_phone)
            await page.wait_for_timeout(500)

            # Click Next / Submit
            next_btn = await page.query_selector('button:has-text("Next"), #search-custom-button, input[type="submit"]')
            if not next_btn:
                # Try finding button by role or span text
                next_btn = await page.query_selector('button')
            
            if next_btn:
                await next_btn.click()
                await page.wait_for_timeout(2500)

            # 3. Fill First & Last Name
            first_name_input = await page.query_selector('input[name="firstName"], input[id="firstName"]')
            last_name_input = await page.query_selector('input[name="lastName"], input[id="lastName"]')

            if first_name_input and last_name_input:
                await first_name_input.fill(first_name)
                await last_name_input.fill(last_name)
                await page.wait_for_timeout(500)

                # Click Next
                next_btn_2 = await page.query_selector('button:has-text("Next"), #search-custom-button, input[type="submit"]')
                if next_btn_2:
                    await next_btn_2.click()
                    await page.wait_for_timeout(3000)

            # 4. Check Result DOM
            content = await page.content()
            content_lower = content.lower()

            # Indications of failure
            fail_indicators = [
                "no account found",
                "couldn't find your google account",
                "no account found with that name",
                "make sure you spelled your name correctly"
            ]

            is_failed = any(fail in content_lower for fail in fail_indicators)

            # Indications of match / success
            success_indicators = [
                "send verification code",
                "get a verification code",
                "enter the code",
                "check your phone",
                "google will send a text message",
                "select how you want to get"
            ]

            is_matched = any(succ in content_lower for succ in success_indicators) or (not is_failed and "error" not in content_lower)

            await browser.close()
            return {
                "success": True,
                "matched": is_matched and not is_failed,
                "phone": clean_phone,
                "first_name": first_name,
                "last_name": last_name,
                "details": "Google account name matched phone" if (is_matched and not is_failed) else "No Google account match for this name"
            }

        except Exception as e:
            await browser.close()
            return {"success": False, "matched": False, "error": str(e)}


def run_google_account_verify_sync(phone_number: str, first_name: str, last_name: str) -> dict:
    """Synchronous wrapper for verify_google_account_name."""
    try:
        return asyncio.run(verify_google_account_name(phone_number, first_name, last_name))
    except Exception as e:
        return {"success": False, "matched": False, "error": str(e)}


if __name__ == "__main__":
    res = run_google_account_verify_sync("01712345678", "Maksudur", "Rahman")
    print("Google Verification Result:", res)
