from fastapi import APIRouter, Depends, HTTPException, status
import uuid
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.schemas import UserProfile, UserUpdate
from backend.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: uuid.UUID = Depends(get_current_user),
    conn = Depends(get_db)
):
    user = await UserService.get_user_by_id(conn, current_user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.patch("/me", response_model=UserProfile)
async def update_current_user(
    update_data: UserUpdate,
    current_user: uuid.UUID = Depends(get_current_user),
    conn = Depends(get_db)
):
    user = await UserService.update_user(conn, current_user, update_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.post("/me/complete-onboarding")
async def complete_onboarding(
    current_user: uuid.UUID = Depends(get_current_user),
    conn = Depends(get_db)
):
    await UserService.complete_onboarding(conn, current_user)
    return {"message": "Onboarding completed"}