# utils/firebase_utils.py
import requests
from fastapi import HTTPException
from core.config import settings

def firebase_login_with_email(email: str, password: str):
    """
    Logs in using the Firebase REST API to get an ID Token.
    """
    if not settings.FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set in .env")

    # Endpoint for signing in with password
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}"
    
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
            # Map common Firebase errors to readable messages
            if "INVALID_PASSWORD" in error_msg or "EMAIL_NOT_FOUND" in error_msg:
                raise HTTPException(status_code=400, detail="Invalid email or password")
            if "USER_DISABLED" in error_msg:
                raise HTTPException(status_code=403, detail="User account is disabled")
            raise HTTPException(status_code=400, detail=error_msg)
            
        return {
            "localId": data["localId"], # The UID
            "idToken": data["idToken"], # The JWT to send in headers
            "refreshToken": data["refreshToken"],
            "expiresIn": data["expiresIn"],
            "email": data["email"]
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Connection to Auth Provider failed: {str(e)}")

def refresh_firebase_token(refresh_token: str):
    """
    Exchanges a valid Refresh Token for a new ID Token via Firebase REST API.
    Required for the frontend axios interceptor.
    """
    if not settings.FIREBASE_API_KEY:
        raise ValueError("FIREBASE_API_KEY is not set in .env")

    url = f"https://securetoken.googleapis.com/v1/token?key={settings.FIREBASE_API_KEY}"
    
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
            "token": data["id_token"],          # New ID Token
            "refresh_token": data["refresh_token"], # New Refresh Token
            "user_id": data["user_id"]
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Connection to Auth Provider failed: {str(e)}")