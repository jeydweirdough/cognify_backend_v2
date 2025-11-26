import firebase_admin
from firebase_admin import credentials, firestore
from core.config import settings
import json

if not firebase_admin._apps:
    service_account_info = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    
    # Check if the input is a JSON string or a file path
    if isinstance(service_account_info, str) and service_account_info.strip().startswith("{"):
        cred_dict = json.loads(service_account_info)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate(service_account_info)

    # Initialize App (No storageBucket)
    firebase_admin.initialize_app(cred)

db = firestore.client()