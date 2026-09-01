import os
import json
import asyncio

try:
    import nest_asyncio
    nest_asyncio.apply()
except Exception:
    pass

import truecallerpy

TOKEN_FILE = "truecaller_token.json"

def save_installation_id(installation_id: str):
    """Saves Truecaller Installation ID token to local json file."""
    data = {"installation_id": installation_id.strip()}
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True

def load_installation_id() -> str:
    """Loads Truecaller Installation ID from file or env variable."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("installation_id", "")
        except Exception:
            pass
    return os.getenv("TRUECALLER_INSTALLATION_ID", "")

def send_truecaller_otp(phone_number: str) -> dict:
    """
    Sends Truecaller OTP asynchronously.
    """
    try:
        res = asyncio.run(truecallerpy.login(phone_number))
        return {"success": True, "data": res}
    except Exception as e:
        return {"success": False, "error": str(e)}

def verify_truecaller_otp(phone_number: str, login_response: dict, otp: str) -> dict:
    """
    Verifies Truecaller OTP asynchronously.
    """
    try:
        res = asyncio.run(truecallerpy.verify_otp(phone_number, login_response, otp))
        if isinstance(res, dict) and "installationId" in res:
            inst_id = res["installationId"]
            save_installation_id(inst_id)
            return {"success": True, "installation_id": inst_id, "raw": res}
        else:
            inst_id = res.get("installationId", "") if isinstance(res, dict) else ""
            if inst_id:
                save_installation_id(inst_id)
                return {"success": True, "installation_id": inst_id, "raw": res}
            return {"success": False, "error": f"Response: {res}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def search_truecaller(phone_number: str, country_code: str = "BD", installation_id: str = "") -> dict:
    """
    Performs official Truecaller lookup asynchronously.
    """
    token = installation_id or load_installation_id()
    if not token:
        return {"success": False, "error": "No Truecaller token set"}

    clean_num = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    
    try:
        res = asyncio.run(truecallerpy.search_phonenumber(clean_num, country_code, token))
        
        if not res or not isinstance(res, dict):
            return {"success": False, "error": "Invalid Truecaller response"}

        data_list = res.get("data", [])
        if not data_list:
            return {"success": False, "error": "No data found"}

        person = data_list[0]
        name = person.get("name", "")
        
        emails = []
        internet_addresses = person.get("internetAddresses", [])
        for ia in internet_addresses:
            if isinstance(ia, dict) and "id" in ia and "@" in ia["id"]:
                emails.append(ia["id"].strip().lower())
            elif isinstance(ia, dict) and "address" in ia and "@" in ia["address"]:
                emails.append(ia["address"].strip().lower())
                
        phones = person.get("phones", [])
        carrier_name = phones[0].get("carrier", "") if phones else ""
        
        addresses = person.get("addresses", [])
        city = addresses[0].get("city", "") if addresses else ""
        country = addresses[0].get("countryCode", country_code) if addresses else country_code

        return {
            "success": True,
            "name": name or "Not Found",
            "emails": emails,
            "primary_email": emails[0] if emails else "Not Found",
            "carrier": carrier_name,
            "city": city,
            "country": country
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
