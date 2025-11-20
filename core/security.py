from fastapi import Request, HTTPException, status, Header
from typing import List
from firebase_admin import auth
from core.firebase import db
from services.role_services import decode_user, get_user_role_id, get_user_role_designation

def verify_firebase_token(request: Request):
    auth_headers = request.headers.get("authorization")

    if not auth_headers:
        raise HTTPException(status=401, detail="Missing authorization header")
    
    try:
        token = auth_headers.split(" ")[1]
        return auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

def allowed_users(allowed_roles: List[str]):
    async def dependency(authorization: str = Header(...)):
        # Extract token from Authorization header
        token = authorization.replace("Bearer ", "")
        user = await decode_user(token)
        role_id = await get_user_role_id(user["uid"])
        designation = await get_user_role_designation(role_id)

        if designation not in [role.lower() for role in allowed_roles]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user
    return dependency