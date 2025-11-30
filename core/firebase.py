# core/firebase.py

from dotenv import load_dotenv
load_dotenv()  # Load variables from .env

import os
import socket
import json
import firebase_admin
from firebase_admin import credentials, firestore
import google.auth.credentials

# --- AUTO-DETECTION HELPER ---
def is_emulator_running(host="127.0.0.1", port=9099):
    """
    Checks if the Firebase Auth Emulator is accepting connections.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

# Detect status
EMULATOR_ACTIVE = is_emulator_running()

# --- CONFIGURATION ---
if EMULATOR_ACTIVE:
    print(f"🔧 [AUTO-DETECT] Firebase Emulator found on port 9099. Switching to EMULATOR mode.")
    
    PROJECT_ID = "cognify-v2"  # Adjust to your Emulator project if needed
    
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
    os.environ["GCLOUD_PROJECT"] = PROJECT_ID
else:
    print(f"☁️ [AUTO-DETECT] No Emulator found. Switching to PRODUCTION mode.")
    PROJECT_ID = None  # Will be set from credentials

# --- INITIALIZATION ---
if not firebase_admin._apps:
    if EMULATOR_ACTIVE:
        # Emulator: Use anonymous credentials
        class LocalAnonymousCredential(credentials.Base):
            def get_credential(self):
                return google.auth.credentials.AnonymousCredentials()
        
        cred = LocalAnonymousCredential()
        firebase_admin.initialize_app(cred, {
            "projectId": PROJECT_ID
        })
    else:
        # Production: Load credentials from .env
        service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            try:
                cred_dict = json.loads(service_account_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                PROJECT_ID = cred_dict.get("project_id")
                print(f"✅ Firebase initialized in PRODUCTION mode for project: {PROJECT_ID}")
            except json.JSONDecodeError:
                raise ValueError("⚠️ Invalid JSON in FIREBASE_SERVICE_ACCOUNT_JSON environment variable.")
        else:
            raise ValueError("⚠️ FIREBASE_SERVICE_ACCOUNT_JSON not set in .env for Production mode.")

# --- FIRESTORE CLIENT ---
db = firestore.client()


