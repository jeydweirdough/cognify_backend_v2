import asyncio
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
from core.config import settings

# 1. Configure Cloudinary globally
cloudinary.config( 
  cloud_name = settings.CLOUDINARY_CLOUD_NAME, 
  api_key = settings.CLOUDINARY_API_KEY, 
  api_secret = settings.CLOUDINARY_API_SECRET,
  secure = True
)

async def upload_file(file: UploadFile) -> str:
    """
    Uploads a file to Cloudinary.
    [CRITICAL FIX] Forces 'raw' resource_type for PDFs so browsers can view them.
    """
    
    def _sync_upload_task():
        try:
            # 1. Determine resource type
            # PDFs must be 'raw' to bypass image processing and open correctly in browsers
            # Images can remain 'auto'
            res_type = "raw" if "pdf" in file.content_type else "auto"
            
            # 2. Reset file pointer ensures we read from the start
            file.file.seek(0)
            
            # 3. Upload
            response = cloudinary.uploader.upload(
                file.file, 
                resource_type=res_type, # <--- THIS IS THE FIX
                folder="cognify_modules",
                public_id=file.filename.split('.')[0],
                use_filename=True,
                unique_filename=True
            )
            
            # 4. Return the secure URL
            return response.get("secure_url")
            
        except Exception as e:
            print(f"Cloudinary Upload Error: {e}")
            raise e

    try:
        return await asyncio.to_thread(_sync_upload_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")