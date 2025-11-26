from fastapi import UploadFile, HTTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from core.config import settings
import json

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """
    Authenticates using the existing Firebase Service Account.
    """
    try:
        info = settings.FIREBASE_SERVICE_ACCOUNT_JSON
        
        # Handle JSON string vs File Path
        if isinstance(info, str) and info.strip().startswith("{"):
            creds_dict = json.loads(info)
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            creds = service_account.Credentials.from_service_account_file(info, scopes=SCOPES)
            
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Drive Auth Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to authenticate with Google Drive")

async def upload_file(file: UploadFile) -> str:
    """
    Uploads a file to Google Drive and returns a viewable link.
    """
    service = get_drive_service()
    
    try:
        file_metadata = {
            'name': file.filename,
            'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
        }
        
        # Read file stream
        media = MediaIoBaseUpload(file.file, mimetype=file.content_type, resumable=True)
        
        # Execute Upload
        created_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()
        
        # Make the file publicly readable (so frontend can view it)
        permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        service.permissions().create(
            fileId=created_file.get('id'),
            body=permission,
            fields='id',
        ).execute()
        
        # Return the "WebViewLink" (Great for PDFs - opens in Drive Viewer)
        # For images, you might prefer 'webContentLink', but 'webViewLink' is safer/standard
        return created_file.get('webViewLink')
        
    except Exception as e:
        print(f"Drive Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"Google Drive upload failed: {str(e)}")