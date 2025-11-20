from fastapi import APIRouter, HTTPException, Request, status, Depends

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(data: )