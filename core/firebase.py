import firebase_admin
from firebase_admin import credentials, firestore
import os
import socket
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
    
    # [FIX] Changed from "demo-project" to "cognify-c17e0" to match your Emulator
    PROJECT_ID = "cognify-c17e0" 
    
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
    os.environ["GCLOUD_PROJECT"] = PROJECT_ID
else:
    print(f"☁️ [AUTO-DETECT] No Emulator found. Switching to PRODUCTION mode.")
    PROJECT_ID = None # Will be read from serviceAccountKey.json

# --- INITIALIZATION ---
if not firebase_admin._apps:
    if EMULATOR_ACTIVE:
        # Emulator: Use Anonymous Credentials
        class LocalAnonymousCredential(credentials.Base):
            def get_credential(self):
                return google.auth.credentials.AnonymousCredentials()
        
        cred = LocalAnonymousCredential()
        firebase_admin.initialize_app(cred, {
            "projectId": PROJECT_ID
        })
    else:
        # Production: Use Service Account
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
        else:
            # Fallback if file missing (optional warning)
            print("⚠️ Warning: serviceAccountKey.json not found for Production mode.")
            firebase_admin.initialize_app()

db = firestore.client()