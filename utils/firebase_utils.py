import requests
import os
import socket
from fastapi import HTTPException
from core.config import settings

# --- AUTO-DETECTION HELPER ---
def is_emulator_running(host="127.0.0.1", port=9099):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

# Check status once at module load
USE_EMULATOR = is_emulator_running()
AUTH_EMULATOR_HOST = "127.0.0.1:9099"

if USE_EMULATOR:
    print("🔧 [AUTH SERVICE] Using Emulator for Login")
else:
    print("☁️ [AUTH SERVICE] Using Production for Login")


def firebase_login_with_email(email: str, password: str):
    """
    Logs in using the Firebase REST API (Adapts to Emulator/Production).
    """
    if not settings.FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set in .env")

    # [FIX] Switch URL based on Auto-Detection
    if USE_EMULATOR:
        # Emulator URL
        base_url = f"http://{AUTH_EMULATOR_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    else:
        # Production URL
        base_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"

    url = f"{base_url}?key={settings.FIREBASE_API_KEY}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Login failed")
            if "INVALID_PASSWORD" in error_msg or "EMAIL_NOT_FOUND" in error_msg:
                raise HTTPException(status_code=400, detail="Invalid email or password")
            if "USER_DISABLED" in error_msg:
                raise HTTPException(status_code=403, detail="User account is disabled")
            raise HTTPException(status_code=400, detail=error_msg)
            
        return {
            "localId": data["localId"], 
            "idToken": data["idToken"],
            "refreshToken": data["refreshToken"],
            "expiresIn": data["expiresIn"],
            "email": data["email"]
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Connection to Auth Provider failed: {str(e)}")


def refresh_firebase_token(refresh_token: str):
    """
    Exchanges Refresh Token for ID Token (Adapts to Emulator/Production).
    """
    if not settings.FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set in .env")

    if USE_EMULATOR:
        base_url = f"http://{AUTH_EMULATOR_HOST}/securetoken.googleapis.com/v1/token"
    else:
        base_url = "https://securetoken.googleapis.com/v1/token"

    url = f"{base_url}?key={settings.FIREBASE_API_KEY}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()

        if response.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Token refresh failed")
            raise HTTPException(status_code=401, detail=error_msg)

        return {
            "token": data["id_token"],
            "refresh_token": data["refresh_token"],
            "user_id": data["user_id"]
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Connection to Auth Provider failed: {str(e)}")