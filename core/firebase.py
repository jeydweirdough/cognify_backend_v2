import firebase_admin
from firebase_admin import credentials, firestore
import os
import google.auth.credentials

# Check if we want to use the local emulator
USE_EMULATOR = os.getenv("USE_FIREBASE_EMULATOR", "False")

if USE_EMULATOR:
    # Tell the Firebase library to talk to localhost
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
    os.environ["GCLOUD_PROJECT"] = "demo-project"
    print("🔧 USING LOCAL FIREBASE EMULATOR")

# Check if already initialized to avoid errors during hot-reload
if not firebase_admin._apps:
    if USE_EMULATOR:
        # [FIX] Use credentials.Base instead of credentials.Credential
        class LocalAnonymousCredential(credentials.Base):
            def get_credential(self):
                return google.auth.credentials.AnonymousCredentials()
        
        cred = LocalAnonymousCredential()
        
        firebase_admin.initialize_app(cred, {
            "projectId": "cognify-c17e0"
        })
    else:
        # Production / Online Mode
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)

db = firestore.client()