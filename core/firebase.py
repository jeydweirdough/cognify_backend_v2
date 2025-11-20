import firebase_admin
from firebase_admin import credentials, firestore
from core.config import settings

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_JSON)

db = firestore.client()