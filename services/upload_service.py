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
    Forces 'raw' resource_type and 'public' access_mode for PDFs to ensure they are viewable.
    """
    
    def _sync_upload_task():
        try:
            # 1. Determine resource type and format
            is_pdf = "pdf" in file.content_type.lower()
            res_type = "raw" if is_pdf else "auto"
            
            upload_format = None
            upload_type = None
            
            if is_pdf:
                # CRITICAL: Cloudinary needs specific settings for raw/PDF files
                res_type = "raw"
                upload_type = "upload" # Explicitly use standard upload type
                try:
                    # Extract extension to fix "N/A" format
                    upload_format = file.filename.rsplit('.', 1)[-1].lower()
                except IndexError:
                    pass
            
            # 2. Reset file pointer ensures we read from the start
            file.file.seek(0)
            
            # 3. Upload with ALL necessary parameters
            response = cloudinary.uploader.upload(
                file.file, 
                resource_type=res_type,
                folder="cognify_modules",
                public_id=file.filename.split('.')[0],
                use_filename=True,
                unique_filename=True,
                format=upload_format,   # Fixes the extension issue (N/A)
                access_mode="public"    # Signals that this file is for public access
            )
            
            # 4. Check for errors in the Cloudinary response
            if "error" in response:
                error_msg = response["error"].get("message", "Unknown Cloudinary error")
                raise Exception(f"Cloudinary Error: {error_msg}")

            # 5. Extract URL
            secure_url = response.get("secure_url")
            
            # 6. Validate URL exists
            if not secure_url:
                raise Exception("Upload succeeded but no secure_url was returned.")

            return secure_url
            
        except Exception as e:
            print(f"Cloudinary Upload Error: {e}")
            raise e

    try:
        # Run the sync upload function in a thread
        return await asyncio.to_thread(_sync_upload_task)
    except Exception as e:
        # This catches errors and sends a clear 500 to the frontend
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")